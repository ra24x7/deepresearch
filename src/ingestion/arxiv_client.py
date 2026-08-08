import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from dateutil import parser as date_parser
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring as parse_untrusted_xml

from config import ArxivSettings
from ingestion.exceptions import ArxivAPIError, ArxivParseError, PDFDownloadError
from ingestion.ids import (
    pdf_filename,
    validate_arxiv_id,
    validate_category,
    validate_pdf_url,
    validate_yyyymmdd,
)
from ingestion.schemas import ArxivMetadata

_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}
_BACKOFF_BASE_SECONDS = 5.0
_BYTES_PER_MB = 1024 * 1024
_MAX_RESULTS_CEILING = 2000

# Monotonic timestamp of the last request issued by this process. Process-wide
# state is the point: the courtesy interval is owed to arXiv, not to a call site.
_last_request_at: float | None = None


def fetch_by_ids(ids: list[str], settings: ArxivSettings) -> list[ArxivMetadata]:
    ids = [validate_arxiv_id(arxiv_id) for arxiv_id in ids]
    params = {"id_list": ",".join(ids), "max_results": len(ids)}
    xml_text = _get_text_with_retry(settings.base_url, params, settings)
    return _parse_atom_xml(xml_text)


def fetch_by_query(
    category: str, from_date: str, to_date: str, max_results: int, settings: ArxivSettings
) -> list[ArxivMetadata]:
    search_query = (
        f"cat:{validate_category(category)} AND "
        f"submittedDate:[{validate_yyyymmdd(from_date)}0000 TO {validate_yyyymmdd(to_date)}2359]"
    )
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": _bounded_max_results(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    xml_text = _get_text_with_retry(settings.base_url, params, settings)
    return _parse_atom_xml(xml_text)


def download_pdf(metadata: ArxivMetadata, dest_dir: Path, settings: ArxivSettings) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / pdf_filename(metadata.arxiv_id)
    content = _get_bytes_with_retry(validate_pdf_url(metadata.pdf_url), settings)
    dest_path.write_bytes(content)
    return dest_path


def _bounded_max_results(max_results: int) -> int:
    value = int(max_results)
    if not 1 <= value <= _MAX_RESULTS_CEILING:
        raise ValueError(f"max_results must be between 1 and {_MAX_RESULTS_CEILING}: {max_results!r}")
    return value


def _wait_before_attempt(attempt: int, settings: ArxivSettings) -> None:
    # Retry backoff widens the same inter-request interval rather than adding a
    # second sleep on top of it — one wait per attempt, measured from the last request.
    min_interval = settings.rate_limit_seconds
    if attempt > 0:
        min_interval = max(min_interval, _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    _throttle(min_interval)


def _throttle(min_interval_seconds: float) -> None:
    global _last_request_at
    if _last_request_at is not None:
        remaining = min_interval_seconds - (time.monotonic() - _last_request_at)
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at = time.monotonic()


def _get_text_with_retry(url: str, params: dict, settings: ArxivSettings) -> str:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        _wait_before_attempt(attempt, settings)
        try:
            with httpx.Client(timeout=settings.timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_error = exc
    raise ArxivAPIError(f"arXiv API request failed after {settings.max_retries} attempts: {last_error}")


def _get_bytes_with_retry(url: str, settings: ArxivSettings) -> bytes:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        _wait_before_attempt(attempt, settings)
        try:
            with httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False) as client:
                response = client.get(url)
                response.raise_for_status()
                return _capped_body(response, url, settings)
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_error = exc
    raise PDFDownloadError(f"PDF download failed after {settings.max_retries} attempts: {last_error}")


def _capped_body(response: httpx.Response, url: str, settings: ArxivSettings) -> bytes:
    # A response body is remote input of remote-chosen length: read it against the
    # cap so an oversized (or endless) PDF cannot exhaust the worker's memory.
    limit = int(settings.max_download_mb * _BYTES_PER_MB)
    content = response.content
    if len(content) > limit:
        raise PDFDownloadError(f"download from {url} exceeds the {settings.max_download_mb} MB limit")
    return content


def _parse_atom_xml(xml_text: str) -> list[ArxivMetadata]:
    try:
        # defused: the response is remote input, and stdlib ElementTree expands
        # entities — one nested-entity payload is enough to exhaust the worker.
        root = parse_untrusted_xml(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ArxivParseError(f"Failed to parse arXiv XML response: {exc}") from exc

    return [_parse_entry(entry) for entry in root.findall("atom:entry", _ATOM_NAMESPACE)]


def _parse_entry(entry: ET.Element) -> ArxivMetadata:
    # Canonical versionless id — the golden dataset and all evidence joins use bare ids.
    arxiv_id = re.sub(r"v\d+$", "", entry.find("atom:id", _ATOM_NAMESPACE).text.split("/")[-1])
    title = " ".join(entry.find("atom:title", _ATOM_NAMESPACE).text.split())
    abstract = " ".join(entry.find("atom:summary", _ATOM_NAMESPACE).text.split())
    published = date_parser.isoparse(entry.find("atom:published", _ATOM_NAMESPACE).text).date()
    authors = tuple(
        author.find("atom:name", _ATOM_NAMESPACE).text for author in entry.findall("atom:author", _ATOM_NAMESPACE)
    )
    categories = tuple(category.get("term") for category in entry.findall("atom:category", _ATOM_NAMESPACE))
    pdf_url = _extract_pdf_url(entry)

    return ArxivMetadata(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        categories=categories,
        published=published,
        pdf_url=pdf_url,
    )


def _extract_pdf_url(entry: ET.Element) -> str:
    for link in entry.findall("atom:link", _ATOM_NAMESPACE):
        if link.get("type") == "application/pdf":
            url = link.get("href", "")
            return url.replace("http://arxiv.org/", "https://arxiv.org/")
    return ""

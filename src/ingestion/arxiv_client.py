import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from dateutil import parser as date_parser

from config import ArxivSettings
from ingestion.exceptions import ArxivAPIError, ArxivParseError, PDFDownloadError
from ingestion.schemas import ArxivMetadata

_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}
_BACKOFF_BASE_SECONDS = 5.0


def fetch_by_ids(ids: list[str], settings: ArxivSettings) -> list[ArxivMetadata]:
    params = {"id_list": ",".join(ids), "max_results": len(ids)}
    xml_text = _get_text_with_retry(settings.base_url, params, settings)
    return _parse_atom_xml(xml_text)


def fetch_by_query(
    category: str, from_date: str, to_date: str, max_results: int, settings: ArxivSettings
) -> list[ArxivMetadata]:
    search_query = f"cat:{category} AND submittedDate:[{from_date}0000 TO {to_date}2359]"
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    xml_text = _get_text_with_retry(settings.base_url, params, settings)
    return _parse_atom_xml(xml_text)


def download_pdf(metadata: ArxivMetadata, dest_dir: Path, settings: ArxivSettings) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{metadata.arxiv_id}.pdf"
    content = _get_bytes_with_retry(metadata.pdf_url, settings)
    dest_path.write_bytes(content)
    return dest_path


def _wait_before_attempt(attempt: int, settings: ArxivSettings) -> None:
    wait_seconds = settings.rate_limit_seconds if attempt == 0 else _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    time.sleep(wait_seconds)


def _get_text_with_retry(url: str, params: dict, settings: ArxivSettings) -> str:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        _wait_before_attempt(attempt, settings)
        try:
            with httpx.Client(timeout=settings.timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            last_error = exc
    raise ArxivAPIError(f"arXiv API request failed after {settings.max_retries} attempts: {last_error}")


def _get_bytes_with_retry(url: str, settings: ArxivSettings) -> bytes:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        _wait_before_attempt(attempt, settings)
        try:
            with httpx.Client(timeout=settings.timeout_seconds) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.content
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            last_error = exc
    raise PDFDownloadError(f"PDF download failed after {settings.max_retries} attempts: {last_error}")


def _parse_atom_xml(xml_text: str) -> list[ArxivMetadata]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArxivParseError(f"Failed to parse arXiv XML response: {exc}") from exc

    return [_parse_entry(entry) for entry in root.findall("atom:entry", _ATOM_NAMESPACE)]


def _parse_entry(entry: ET.Element) -> ArxivMetadata:
    arxiv_id = entry.find("atom:id", _ATOM_NAMESPACE).text.split("/")[-1]
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

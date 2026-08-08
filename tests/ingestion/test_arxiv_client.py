from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from config import ArxivSettings
from ingestion import arxiv_client
from ingestion.arxiv_client import download_pdf, fetch_by_ids, fetch_by_query
from ingestion.exceptions import ArxivAPIError, ArxivParseError, PDFDownloadError
from ingestion.schemas import ArxivMetadata

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ATOM_XML = (FIXTURES_DIR / "atom_response.xml").read_text()

SETTINGS = ArxivSettings(rate_limit_seconds=3.0, max_retries=3, timeout_seconds=10.0)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    arxiv_client._last_request_at = None


def _ok_response(text: str = ATOM_XML) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


def _error_response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    error = httpx.HTTPStatusError("server error", request=MagicMock(), response=response)
    response.raise_for_status.side_effect = error
    return response


def _patch_client(mocker, get_side_effect):
    client_instance = MagicMock()
    client_instance.get.side_effect = get_side_effect
    client_instance.__enter__.return_value = client_instance
    client_instance.__exit__.return_value = False
    mock_client_cls = mocker.patch("ingestion.arxiv_client.httpx.Client", return_value=client_instance)
    return mock_client_cls, client_instance


class TestFetchByIds:
    def test_parses_atom_xml_fixture_into_arxiv_metadata_list(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response()])

        results = fetch_by_ids(["2501.00001", "2501.00002"], SETTINGS)

        assert len(results) == 2
        first = results[0]
        assert first.arxiv_id == "2501.00001"
        assert first.title == "A Great Paper About RAG"
        assert first.authors == ("Jane Doe", "John Smith")
        assert first.categories == ("cs.AI", "cs.CL")
        assert first.published == date(2025, 1, 15)
        assert first.pdf_url == "https://arxiv.org/pdf/2501.00001v1"

    def test_retries_on_500_then_succeeds(self, mocker):
        sleep_mock = mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_error_response(500), _ok_response()])

        results = fetch_by_ids(["2501.00001"], SETTINGS)

        assert len(results) == 2
        # first attempt needs no throttle wait in a fresh process; the retry backs off
        assert sleep_mock.call_count == 1

    def test_raises_typed_error_after_max_retries_exhausted(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_error_response(500), _error_response(500), _error_response(500)])

        with pytest.raises(ArxivAPIError):
            fetch_by_ids(["2501.00001"], SETTINGS)

    def test_first_request_in_a_fresh_process_does_not_wait(self, mocker):
        sleep_mock = mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response()])

        fetch_by_ids(["2501.00001"], SETTINGS)

        sleep_mock.assert_not_called()

    def test_backoff_sleep_happens_before_the_retry_http_call(self, mocker):
        call_order = []
        mocker.patch("ingestion.arxiv_client.time.sleep", side_effect=lambda _: call_order.append("sleep"))
        responses = [_error_response(500), _ok_response()]
        client_instance = MagicMock()
        client_instance.get.side_effect = lambda *a, **kw: call_order.append("get") or responses.pop(0)
        client_instance.__enter__.return_value = client_instance
        client_instance.__exit__.return_value = False
        mocker.patch("ingestion.arxiv_client.httpx.Client", return_value=client_instance)

        fetch_by_ids(["2501.00001"], SETTINGS)

        assert call_order == ["get", "sleep", "get"]


class TestFetchByQuery:
    def test_returns_metadata_list_for_category_and_date_range(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response()])

        results = fetch_by_query("cs.AI", "20250101", "20250201", 10, SETTINGS)

        assert len(results) == 2


class TestDownloadPdf:
    def _metadata(self):
        return ArxivMetadata(
            arxiv_id="2501.00001",
            title="A Paper",
            authors=("Jane Doe",),
            abstract="abstract",
            categories=("cs.AI",),
            published=date(2025, 1, 15),
            pdf_url="https://arxiv.org/pdf/2501.00001v1",
        )

    def test_download_pdf_writes_bytes_to_dest_dir_and_returns_path(self, mocker, tmp_path):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        response = MagicMock()
        response.content = b"%PDF-1.4 fake pdf bytes"
        response.raise_for_status.return_value = None
        _patch_client(mocker, [response])

        result_path = download_pdf(self._metadata(), tmp_path, SETTINGS)

        assert result_path == tmp_path / "2501.00001.pdf"
        assert result_path.read_bytes() == b"%PDF-1.4 fake pdf bytes"

    def test_download_pdf_raises_typed_error_after_max_retries(self, mocker, tmp_path):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_error_response(503), _error_response(503), _error_response(503)])

        with pytest.raises(PDFDownloadError):
            download_pdf(self._metadata(), tmp_path, SETTINGS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestTransportErrorRetry:
    def test_connect_error_is_retried_then_succeeds(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [httpx.ConnectError("dns failure"), _ok_response()])

        results = fetch_by_ids(["2501.00001"], SETTINGS)

        assert len(results) == 2

    def test_connect_error_exhausting_retries_raises_typed_error(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [httpx.ConnectError("dns failure")] * SETTINGS.max_retries)

        with pytest.raises(ArxivAPIError, match="dns failure"):
            fetch_by_ids(["2501.00001"], SETTINGS)


class TestStatefulRateLimiting:
    def test_second_request_waits_only_the_remaining_interval(self, mocker):
        sleep_mock = mocker.patch("ingestion.arxiv_client.time.sleep")
        # first request at t=100, second issued at t=101 -> only 2s of the 3s left
        mocker.patch("ingestion.arxiv_client.time.monotonic", side_effect=[100.0, 101.0, 101.0])
        _patch_client(mocker, [_ok_response(), _ok_response()])

        fetch_by_ids(["2501.00001"], SETTINGS)
        fetch_by_ids(["2501.00002"], SETTINGS)

        sleep_mock.assert_called_once_with(pytest.approx(2.0))

    def test_no_wait_when_interval_already_elapsed_naturally(self, mocker):
        sleep_mock = mocker.patch("ingestion.arxiv_client.time.sleep")
        # a slow parse between calls: 45s elapsed, well past the 3s interval
        mocker.patch("ingestion.arxiv_client.time.monotonic", side_effect=[100.0, 145.0, 145.0])
        _patch_client(mocker, [_ok_response(), _ok_response()])

        fetch_by_ids(["2501.00001"], SETTINGS)
        fetch_by_ids(["2501.00002"], SETTINGS)

        sleep_mock.assert_not_called()


_ENTRY_MISSING_TITLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <published>2025-01-15T18:30:00Z</published>
    <summary>An abstract.</summary>
    <author><name>Jane Doe</name></author>
  </entry>
</feed>
"""


class TestMalformedAtomEntries:
    def test_entry_missing_a_required_field_raises_a_typed_parse_error(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response(_ENTRY_MISSING_TITLE)])

        with pytest.raises(ArxivParseError, match="atom:title"):
            fetch_by_ids(["2501.00001"], SETTINGS)

    def test_retry_exhaustion_keeps_the_transport_error_as_cause(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [httpx.ConnectError("no route")] * SETTINGS.max_retries)

        with pytest.raises(ArxivAPIError) as excinfo:
            fetch_by_ids(["2501.00001"], SETTINGS)

        assert isinstance(excinfo.value.__cause__, httpx.ConnectError)

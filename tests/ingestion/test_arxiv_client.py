from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from config import ArxivSettings
from ingestion.arxiv_client import download_pdf, fetch_by_ids, fetch_by_query
from ingestion.exceptions import ArxivAPIError, PDFDownloadError
from ingestion.schemas import ArxivMetadata

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ATOM_XML = (FIXTURES_DIR / "atom_response.xml").read_text()

SETTINGS = ArxivSettings(rate_limit_seconds=3.0, max_retries=3, timeout_seconds=10.0)


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
        assert first.arxiv_id == "2501.00001v1"
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
        assert sleep_mock.call_count == 2

    def test_raises_typed_error_after_max_retries_exhausted(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_error_response(500), _error_response(500), _error_response(500)])

        with pytest.raises(ArxivAPIError):
            fetch_by_ids(["2501.00001"], SETTINGS)

    def test_respects_rate_limit_before_first_request(self, mocker):
        sleep_mock = mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response()])

        fetch_by_ids(["2501.00001"], SETTINGS)

        sleep_mock.assert_any_call(SETTINGS.rate_limit_seconds)

    def test_sleep_happens_before_the_http_call_each_attempt(self, mocker):
        call_order = []
        mocker.patch("ingestion.arxiv_client.time.sleep", side_effect=lambda _: call_order.append("sleep"))
        client_instance = MagicMock()
        client_instance.get.side_effect = lambda *a, **kw: call_order.append("get") or _ok_response()
        client_instance.__enter__.return_value = client_instance
        client_instance.__exit__.return_value = False
        mocker.patch("ingestion.arxiv_client.httpx.Client", return_value=client_instance)

        fetch_by_ids(["2501.00001"], SETTINGS)

        assert call_order == ["sleep", "get"]


class TestFetchByQuery:
    def test_returns_metadata_list_for_category_and_date_range(self, mocker):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_ok_response()])

        results = fetch_by_query("cs.AI", "20250101", "20250201", 10, SETTINGS)

        assert len(results) == 2


class TestDownloadPdf:
    def _metadata(self):
        return ArxivMetadata(
            arxiv_id="2501.00001v1",
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

        assert result_path == tmp_path / "2501.00001v1.pdf"
        assert result_path.read_bytes() == b"%PDF-1.4 fake pdf bytes"

    def test_download_pdf_raises_typed_error_after_max_retries(self, mocker, tmp_path):
        mocker.patch("ingestion.arxiv_client.time.sleep")
        _patch_client(mocker, [_error_response(503), _error_response(503), _error_response(503)])

        with pytest.raises(PDFDownloadError):
            download_pdf(self._metadata(), tmp_path, SETTINGS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

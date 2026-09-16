"""Unit tests for the New Zealand Legislation integration."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nz_legislation import (
    LegislationError,
    _decode_xml_range,
    _fetch_xml_chunk,
    _rate_limit,
    _trusted_xml_url,
    nz_legislation,
)

pytestmark = pytest.mark.unit

API_HEADERS = {
    "X-RateLimit-Limit": "10000",
    "X-RateLimit-Remaining": "9998",
    "X-RateLimit-Reset": "1790000000",
}
XML_URL = "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml/"
VERSION_ID = "act_public_1990_109_en_2022-08-30"
WORK_ID = "act_public_1990_109"
SAMPLE_VERSION = {
    "title": "New Zealand Bill of Rights Act 1990",
    "version_id": VERSION_ID,
    "work_id": WORK_ID,
    "legislation_status": "in_force",
    "legislation_type": "act",
    "administering_agencies": ["Ministry of Justice"],
    "act_type": "public",
    "act_status": "in_force",
    "act_classification": "principal",
    "formats": [
        {"type": "html", "url": "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30/"},
        {"type": "xml", "url": XML_URL},
    ],
}
SAMPLE_WORK = {
    "work_id": WORK_ID,
    "legislation_status": "in_force",
    "legislation_type": "act",
    "administering_agencies": ["Ministry of Justice"],
    "act_type": "public",
    "act_status": "in_force",
    "act_classification": "principal",
    "latest_matching_version": {
        "title": "New Zealand Bill of Rights Act 1990",
        "version_id": VERSION_ID,
        "is_latest_version": True,
        "formats": SAMPLE_VERSION["formats"],
    },
}


def response(data, headers=None):
    return FetchResponse(status=200, headers=headers or API_HEADERS, data=data)


class TestHelpers:
    def test_rate_limit_is_case_insensitive_and_ignores_invalid_values(self):
        assert _rate_limit({"x-ratelimit-limit": "10000", "X-RATELIMIT-REMAINING": "bad"}) == {
            "limit": 10000,
            "remaining": None,
            "reset_at": None,
        }

    @pytest.mark.parametrize(
        "url",
        [
            XML_URL,
            "https://legislation.govt.nz/act/public/1990/109/en/latest.xml",
        ],
    )
    def test_trusted_xml_url_accepts_only_official_https_hosts(self, url):
        assert _trusted_xml_url([{"type": "xml", "url": url}]) == url

    @pytest.mark.parametrize(
        "url",
        [
            "http://www.legislation.govt.nz/act.xml",
            "https://example.test/act.xml",
            "https://www.legislation.govt.nz.evil.test/act.xml",
            "https://user@example.test@www.legislation.govt.nz/act.xml",
            "https://www.legislation.govt.nz:8443/act.xml",
            "https://www.legislation.govt.nz:invalid/act.xml",
        ],
    )
    def test_trusted_xml_url_rejects_unsafe_urls(self, url):
        with pytest.raises(LegislationError, match="untrusted"):
            _trusted_xml_url([{"type": "xml", "url": url}])

    def test_trusted_xml_url_reports_unavailable_format(self):
        with pytest.raises(LegislationError, match="does not provide"):
            _trusted_xml_url([{"type": "pdf", "url": "https://www.legislation.govt.nz/a.pdf"}])

    def test_xml_range_preserves_utf8_character_boundaries(self):
        prefix = b'<?xml version="1.0"?>'
        body = prefix + b"a" * (999 - len(prefix)) + "ā".encode() + b"z"

        xml, returned_bytes, total_bytes, next_offset = _decode_xml_range(
            body, "bytes 0-1001/2000", offset=0, max_bytes=1000
        )

        assert xml == prefix.decode() + "a" * (999 - len(prefix))
        assert returned_bytes == 999
        assert total_bytes == 2000
        assert next_offset == 999

    @pytest.mark.parametrize(
        "body, content_range, error",
        [
            (b"abc", "invalid", "invalid XML byte range"),
            (b"abc", "bytes 2-4/10", "invalid XML byte range"),
            (b"ab", "bytes 0-2/10", "incomplete XML byte range"),
            (b"\xffab", "bytes 0-2/10", "not valid UTF-8"),
            (b"<html>", "bytes 0-5/10", "unexpected XML response"),
        ],
    )
    def test_xml_range_rejects_invalid_provider_data(self, body, content_range, error):
        with pytest.raises(LegislationError, match=error):
            _decode_xml_range(body, content_range, offset=0, max_bytes=1000)

    async def test_xml_fetch_rejects_html_and_sends_only_bounded_public_headers(self):
        response = MagicMock(status=206, headers={"Content-Type": "text/html"})
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            with pytest.raises(LegislationError, match="unexpected XML response"):
                await _fetch_xml_chunk(XML_URL, offset=1000, max_bytes=2000)

        request = session.get.call_args
        assert request.args == (XML_URL,)
        assert request.kwargs == {
            "headers": {
                "Accept": "application/xml",
                "Accept-Encoding": "identity",
                "Range": "bytes=1000-3002",
            },
            "allow_redirects": False,
            "ssl": True,
        }


class TestSearchLegislation:
    async def test_returns_normalised_work_and_pagination(self, mock_context):
        mock_context.fetch.return_value = response({"results": [SAMPLE_WORK], "page": 2, "per_page": 1, "total": 3})

        result = await nz_legislation.execute_action(
            "search_legislation",
            {"search_term": "rights", "search_field": "title", "page": 2, "per_page": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["works"][0]["work_id"] == WORK_ID
        assert data["works"][0]["latest_matching_version"]["is_latest_version"] is True
        assert data["has_next_page"] is True
        assert data["rate_limit"]["remaining"] == 9998

    async def test_sends_all_documented_filters_and_api_key_header(self, mock_context):
        mock_context.fetch.return_value = response({"results": [], "page": 1, "per_page": 100, "total": 0})
        inputs = {
            "search_term": "privacy",
            "search_field": "content",
            "page": 1,
            "per_page": 100,
            "legislation_status": "in_force",
            "legislation_type": "act",
            "act_type": "public",
            "act_classification": "principal",
            "act_status": "in_force",
            "administering_agencies": "Ministry of Justice",
            "sort_by": "most_recently_updated",
            "publisher": "Parliamentary Counsel Office",
        }

        await nz_legislation.execute_action("search_legislation", inputs, mock_context)

        request = mock_context.fetch.call_args
        assert request.args[0] == "https://api.legislation.govt.nz/v0/works/"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["headers"] == {"Accept": "application/json", "X-Api-Key": "test_api_key"}
        assert request.kwargs["params"] == inputs

    async def test_defaults_page_and_page_size(self, mock_context):
        mock_context.fetch.return_value = response({"results": [], "page": 1, "per_page": 20, "total": 0})

        await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"page": 1, "per_page": 20}

    @pytest.mark.parametrize(
        "inputs, expected",
        [
            ({"act_status": "in_force"}, "legislation_type='act'"),
            (
                {"legislation_type": "act", "instrument_status": "in_force"},
                "legislation_type='secondary_legislation'",
            ),
            ({"legislation_type": "act", "bill_status": "current"}, "legislation_type='bill'"),
        ],
    )
    async def test_rejects_type_specific_filter_mismatches(self, mock_context, inputs, expected):
        result = await nz_legislation.execute_action("search_legislation", inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert expected in result.result.message
        mock_context.fetch.assert_not_called()

    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.return_value = response({"page": 1, "total": 0})

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected response" in result.result.message

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (HTTPError(401, "Invalid API key", {}), "rejected the API key"),
            (HTTPError(403, "Forbidden", {}), "burst limit"),
            (HTTPError(500, "Internal Server Error", {}), "Try again later"),
            (RateLimitError(120, 429, "Rate limit", {}), "120 seconds"),
        ],
    )
    async def test_maps_provider_errors_without_leaking_response(self, mock_context, exc, expected):
        mock_context.fetch.side_effect = exc

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert expected in result.result.message
        assert "Internal Server Error" not in result.result.message

    async def test_missing_api_key_is_action_error(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {"api_key": " "}}

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API key is required" in result.result.message

    async def test_missing_required_credential_is_sdk_validation_error(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


class TestListVersions:
    async def test_returns_versions_and_request_shape(self, mock_context):
        mock_context.fetch.return_value = response({"results": [SAMPLE_VERSION], "total": 3, "page": 2, "per_page": 1})

        result = await nz_legislation.execute_action(
            "list_versions", {"work_id": WORK_ID, "sort": "asc", "page": 2, "per_page": 1}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["versions"][0]["version_id"] == VERSION_ID
        assert result.result.data["count"] == 1
        assert result.result.data["total"] == 3
        assert result.result.data["has_next_page"] is True
        request = mock_context.fetch.call_args
        assert request.args[0].endswith(f"/works/{WORK_ID}/versions/")
        assert request.kwargs["params"] == {"sort": "asc", "page": 2, "per_page": 1}

    async def test_defaults_to_descending_order(self, mock_context):
        mock_context.fetch.return_value = response({"results": [], "total": 0})

        await nz_legislation.execute_action("list_versions", {"work_id": WORK_ID}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"sort": "desc", "page": 1, "per_page": 20}

    async def test_not_found_names_work(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found", {})

        result = await nz_legislation.execute_action("list_versions", {"work_id": WORK_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "requested work" in result.result.message


class TestGetVersion:
    async def test_returns_version_metadata_and_formats(self, mock_context):
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        result = await nz_legislation.execute_action("get_version", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION
        version = result.result.data["version"]
        assert version["title"] == "New Zealand Bill of Rights Act 1990"
        assert version["formats"][1] == {"type": "xml", "url": XML_URL}
        assert version["bill_type"] is None
        assert mock_context.fetch.call_args.args[0].endswith(f"/versions/{VERSION_ID}/")

    async def test_invalid_identifier_is_rejected_before_handler(self, mock_context):
        result = await nz_legislation.execute_action("get_version", {"version_id": "../../secret"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    async def test_not_found_names_version(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found", {})

        result = await nz_legislation.execute_action("get_version", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "requested version" in result.result.message


class TestGetVersionXml:
    async def test_fetches_official_xml_without_forwarding_api_key(self, mock_context):
        xml = "<?xml version='1.0'?><act>law</act>"
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.return_value = (xml, len(xml.encode()), len(xml.encode()), None)
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "max_bytes": 1000}, mock_context
            )

        assert result.type == ResultType.ACTION
        assert result.result.data["xml"] == xml
        assert result.result.data["truncated"] is False
        assert result.result.data["next_offset"] is None
        assert mock_context.fetch.call_args_list == [
            call(
                f"https://api.legislation.govt.nz/v0/versions/{VERSION_ID}/",
                method="GET",
                headers={"Accept": "application/json", "X-Api-Key": "test_api_key"},
            ),
        ]
        fetch_xml.assert_awaited_once_with(XML_URL, 0, 1000)

    async def test_chunks_xml_with_unambiguous_next_offset(self, mock_context):
        xml = "a" * 2500
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.return_value = (xml[1000:2000], 1000, 2500, 2000)
            result = await nz_legislation.execute_action(
                "get_version_xml",
                {"version_id": VERSION_ID, "offset": 1000, "max_bytes": 1000},
                mock_context,
            )

        data = result.result.data
        assert data["xml"] == "a" * 1000
        assert data["offset"] == 1000
        assert data["returned_bytes"] == 1000
        assert data["total_bytes"] == 2500
        assert data["truncated"] is True
        assert data["next_offset"] == 2000

    async def test_reports_missing_xml_without_second_request(self, mock_context):
        version = {**SAMPLE_VERSION, "formats": [{"type": "pdf", "url": "https://example.test/a.pdf"}]}
        mock_context.fetch.return_value = response(version)

        result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "does not provide an XML format" in result.result.message
        assert mock_context.fetch.await_count == 1

    async def test_rejects_untrusted_provider_xml_url_without_fetching_it(self, mock_context):
        version = {**SAMPLE_VERSION, "formats": [{"type": "xml", "url": "https://evil.test/act.xml"}]}
        mock_context.fetch.return_value = response(version)

        result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "untrusted" in result.result.message
        assert mock_context.fetch.await_count == 1

    async def test_rejects_offset_beyond_document(self, mock_context):
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = LegislationError("offset is outside the XML document's byte range.")
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "offset": 10}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "outside the XML document's byte range" in result.result.message

    async def test_rejects_unexpected_xml_response(self, mock_context):
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = LegislationError(
                "The New Zealand Legislation website returned an unexpected XML response."
            )
            result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected XML response" in result.result.message

    async def test_xml_document_not_found_is_distinct_from_missing_version(self, mock_context):
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = LegislationError(
                "The New Zealand Legislation website could not find the requested XML document."
            )
            result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "requested XML document" in result.result.message

    async def test_xml_network_error_is_curated(self, mock_context):
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = aiohttp.ClientConnectionError("private network detail")
            result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "The New Zealand Legislation website could not provide the XML document."
        assert "private network detail" not in result.result.message

    @pytest.mark.parametrize("max_bytes", [999, 100001])
    async def test_xml_chunk_size_bounds_are_schema_validated(self, mock_context, max_bytes):
        result = await nz_legislation.execute_action(
            "get_version_xml", {"version_id": VERSION_ID, "max_bytes": max_bytes}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

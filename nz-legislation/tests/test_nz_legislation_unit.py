"""Unit tests for the New Zealand Legislation integration."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, call, patch

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nz_legislation import (
    LegislationError,
    _canonical_xml_url,
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
    "publisher": "Parliamentary Counsel Office",
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
XML_SOURCE = {
    "version_id": VERSION_ID,
    "source_url": XML_URL.removesuffix("/"),
}


def response(data, headers=None):
    return FetchResponse(status=200, headers=API_HEADERS if headers is None else headers, data=data)


class TestHelpers:
    def test_canonical_xml_url_is_derived_from_all_version_id_components(self):
        assert _canonical_xml_url("secondary-legislation_agency-drafted_~2025_42_en_2025-03-04") == (
            "https://www.legislation.govt.nz/secondary-legislation/agency-drafted/~2025/42/en/2025-03-04.xml"
        )

    @pytest.mark.parametrize("version_id", ["act_public_1990_109_en", "act_public_1990_109_en_2022-08-30_extra"])
    def test_canonical_xml_url_rejects_non_six_part_identifier(self, version_id):
        with pytest.raises(LegislationError, match="six-part"):
            _canonical_xml_url(version_id)

    @pytest.mark.parametrize(
        "headers, expected",
        [
            (
                {"x-ratelimit-limit": "10000", "X-RATELIMIT-REMAINING": "0", "X-RateLimit-Reset": "1790000000"},
                {"limit": 10000, "remaining": 0, "reset_at": 1790000000},
            ),
            (
                {"X-RateLimit-Limit": "25000", "X-RateLimit-Remaining": "bad"},
                {"limit": 25000, "remaining": None, "reset_at": None},
            ),
            ({}, {"limit": None, "remaining": None, "reset_at": None}),
        ],
    )
    def test_rate_limit_is_advisory_and_tolerates_missing_or_invalid_headers(self, headers, expected):
        assert _rate_limit(headers) == expected

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
            "https://www.legislation.govt.nz/act.xml?api_key=must-not-be-sent",
            "https://www.legislation.govt.nz/act.xml#fragment",
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

    async def test_xml_fetch_reports_public_website_rate_limit(self):
        response = MagicMock(status=429, headers={})
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            with pytest.raises(LegislationError, match="website temporarily rate-limited XML requests"):
                await _fetch_xml_chunk(XML_URL, offset=0, max_bytes=1000)

    @pytest.mark.parametrize(
        "status, expected",
        [
            (404, "could not find the requested XML document"),
            (416, "offset is outside the XML document's byte range"),
            (403, "refused the XML document request"),
            (500, "could not provide the XML document"),
            (200, "did not return a bounded XML byte range"),
        ],
    )
    async def test_xml_fetch_maps_unusable_http_responses(self, status, expected):
        response = MagicMock(status=status, headers={})
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            with pytest.raises(LegislationError, match=expected):
                await _fetch_xml_chunk(XML_URL, offset=0, max_bytes=1000)


class TestSharedErrors:
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("search_legislation", {}),
            ("list_versions", {"work_id": WORK_ID}),
            ("get_version", {"version_id": VERSION_ID}),
            ("get_version_xml", {"version_id": VERSION_ID}),
        ],
    )
    async def test_daily_quota_error_uses_provider_reset_not_sdk_retry_delay(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RateLimitError(120, 429, "provider detail", {})

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "midnight New Zealand time" in result.result.message
        assert "120" not in result.result.message
        fetch_xml.assert_not_awaited()

    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("search_legislation", {}),
            ("list_versions", {"work_id": WORK_ID}),
            ("get_version", {"version_id": VERSION_ID}),
            ("get_version_xml", {"version_id": VERSION_ID}),
        ],
    )
    @pytest.mark.parametrize(
        "network_error",
        [aiohttp.ClientConnectionError("private network detail"), TimeoutError("private timeout detail")],
    )
    async def test_api_network_errors_are_curated(self, mock_context, action, inputs, network_error):
        mock_context.fetch.side_effect = network_error

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "could not" in result.result.message
        assert "private" not in result.result.message
        fetch_xml.assert_not_awaited()

    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("search_legislation", {}),
            ("list_versions", {"work_id": WORK_ID}),
            ("get_version", {"version_id": VERSION_ID}),
            ("get_version_xml", {"version_id": VERSION_ID}),
        ],
    )
    async def test_unexpected_errors_are_logged_without_blaming_inputs(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RuntimeError("private detail containing test_api_key")

        result = await nz_legislation.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected error" in result.result.message
        assert "inputs" not in result.result.message
        assert "test_api_key" not in result.result.message
        mock_context.logger.error.assert_called_once_with(
            "Unexpected %s executing New Zealand Legislation action %s", "RuntimeError", action
        )


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
        assert data["works"][0]["publisher"] == "Parliamentary Counsel Office"
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

    async def test_rejects_a_search_page_the_provider_did_not_honour(self, mock_context):
        mock_context.fetch.return_value = response({"results": [], "page": 1, "per_page": 20, "total": 100})

        result = await nz_legislation.execute_action("search_legislation", {"page": 2, "per_page": 20}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "did not honour the requested search page" in result.result.message

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

    async def test_rejects_non_object_result_instead_of_dropping_it(self, mock_context):
        mock_context.fetch.return_value = response(
            {"results": [SAMPLE_WORK, "bad"], "page": 1, "per_page": 20, "total": 2}
        )

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected response" in result.result.message

    @pytest.mark.parametrize(
        "path, invalid_value",
        [
            (("work_id",), None),
            (("publisher",), 42),
            (("administering_agencies",), ["Ministry of Justice", 42]),
            (("latest_matching_version",), None),
            (("latest_matching_version", "title"), None),
            (("latest_matching_version", "formats"), [{"type": "xml"}]),
            (("act_status",), 42),
        ],
    )
    async def test_rejects_malformed_work_fields_instead_of_normalising_them(self, mock_context, path, invalid_value):
        work = deepcopy(SAMPLE_WORK)
        target = work
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = invalid_value
        mock_context.fetch.return_value = response({"results": [work], "page": 1, "per_page": 20, "total": 1})

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected response" in result.result.message

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (HTTPError(401, "Invalid API key: test_api_key", {}), "rejected the API key"),
            (HTTPError(403, "Forbidden: test_api_key", {}), "burst limit"),
            (HTTPError(500, "Internal Server Error: test_api_key", {}), "Try again later"),
        ],
    )
    async def test_maps_provider_errors_without_leaking_response(self, mock_context, exc, expected):
        mock_context.fetch.side_effect = exc

        result = await nz_legislation.execute_action("search_legislation", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert expected in result.result.message
        assert "test_api_key" not in result.result.message

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
        mock_context.fetch.return_value = response({"results": [], "total": 0, "page": 1, "per_page": 20})

        await nz_legislation.execute_action("list_versions", {"work_id": WORK_ID}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"sort": "desc", "page": 1, "per_page": 20}

    async def test_rejects_a_version_page_the_provider_did_not_honour(self, mock_context):
        mock_context.fetch.return_value = response({"results": [SAMPLE_VERSION], "total": 3, "page": 1, "per_page": 1})

        result = await nz_legislation.execute_action(
            "list_versions", {"work_id": WORK_ID, "page": 2, "per_page": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "did not honour the requested version page" in result.result.message

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

    @pytest.mark.parametrize(
        "field, invalid_value",
        [
            ("title", None),
            ("version_id", None),
            ("administering_agencies", ["Ministry of Justice", 42]),
            ("formats", [{"type": "xml"}]),
            ("act_status", 42),
        ],
    )
    async def test_rejects_malformed_version_fields_instead_of_normalising_them(
        self, mock_context, field, invalid_value
    ):
        version = deepcopy(SAMPLE_VERSION)
        version[field] = invalid_value
        mock_context.fetch.return_value = response(version)

        result = await nz_legislation.execute_action("get_version", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected response" in result.result.message

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
    async def test_rejects_non_six_part_version_id_before_authenticated_request(self, mock_context):
        result = await nz_legislation.execute_action(
            "get_version_xml", {"version_id": "act_public_1990_109_en"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    async def test_fetches_official_xml_without_forwarding_api_key(self, mock_context):
        xml = "<?xml version='1.0'?><act>law</act>"
        mock_context.fetch.return_value = response(SAMPLE_VERSION)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.return_value = (xml, len(xml.encode()), len(xml.encode()), None)
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "max_bytes": 1000}, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["source"] == XML_SOURCE
        assert data["xml"] == xml
        assert data["truncated"] is False
        assert data["next_offset"] is None
        assert mock_context.fetch.call_args_list == [
            call(
                f"https://api.legislation.govt.nz/v0/versions/{VERSION_ID}/",
                method="GET",
                headers={"Accept": "application/json", "X-Api-Key": "test_api_key"},
            ),
        ]
        fetch_xml.assert_awaited_once_with(XML_SOURCE["source_url"], 0, 1000)

    async def test_replaces_latest_alias_with_version_bound_canonical_url(self, mock_context):
        version = deepcopy(SAMPLE_VERSION)
        version["formats"][1]["url"] = "https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml"
        mock_context.fetch.return_value = response(version)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.return_value = ("<?xml version='1.0'?>", 21, 21, None)
            result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.result.data["source"] == XML_SOURCE
        fetch_xml.assert_awaited_once_with(XML_SOURCE["source_url"], 0, 20_000)

    async def test_chunks_xml_with_unambiguous_next_offset(self, mock_context):
        xml = "a" * 2500

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.return_value = (xml[1000:2000], 1000, 2500, 2000)
            result = await nz_legislation.execute_action(
                "get_version_xml",
                {"version_id": VERSION_ID, "source": XML_SOURCE, "offset": 1000, "max_bytes": 1000},
                mock_context,
            )

        data = result.result.data
        assert data["source"] == XML_SOURCE
        assert data["xml"] == "a" * 1000
        assert data["offset"] == 1000
        assert data["returned_bytes"] == 1000
        assert data["total_bytes"] == 2500
        assert data["truncated"] is True
        assert data["next_offset"] == 2000
        assert data["rate_limit"] == {"limit": None, "remaining": None, "reset_at": None}
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_awaited_once_with(XML_SOURCE["source_url"], 1000, 1000)

    async def test_rejects_continuation_source_for_another_version(self, mock_context):
        source = {**XML_SOURCE, "version_id": "act_public_1991_1_en_1991-01-01"}

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "source": source, "offset": 1000}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "does not match version_id" in result.result.message
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_not_awaited()

    async def test_rejects_untrusted_continuation_url_without_authenticated_request(self, mock_context):
        source = {**XML_SOURCE, "source_url": "https://evil.test/act.xml"}

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "source": source, "offset": 1000}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "does not match version_id" in result.result.message
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_not_awaited()

    async def test_rejects_different_official_document_as_continuation_source(self, mock_context):
        source = {
            **XML_SOURCE,
            "source_url": "https://www.legislation.govt.nz/act/public/1991/1/en/1991-01-01.xml",
        }

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action(
                "get_version_xml", {"version_id": VERSION_ID, "source": source, "offset": 1000}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "does not match version_id" in result.result.message
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_not_awaited()

    async def test_rejects_metadata_for_a_different_version_before_xml_fetch(self, mock_context):
        version = {**SAMPLE_VERSION, "version_id": "act_public_1991_1_en_1991-01-01"}
        mock_context.fetch.return_value = response(version)

        with patch("nz_legislation._fetch_xml_chunk", new_callable=AsyncMock) as fetch_xml:
            result = await nz_legislation.execute_action("get_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "different version" in result.result.message
        fetch_xml.assert_not_awaited()

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

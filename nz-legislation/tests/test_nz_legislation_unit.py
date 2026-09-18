"""Unit tests for the New Zealand Legislation integration."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nz_legislation import (
    MAX_XML_DOCUMENT_BYTES,
    LegislationError,
    _canonical_xml_url,
    _fetch_xml_document,
    _get_xml_provisions,
    _rate_limit,
    _search_xml_provisions,
    nz_legislation,
)

pytestmark = pytest.mark.unit

API_HEADERS = {
    "X-RateLimit-Limit": "10000",
    "X-RateLimit-Remaining": "9998",
    "X-RateLimit-Reset": "1790000000",
}
XML_URL = "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml/"
CANONICAL_XML_URL = XML_URL.removesuffix("/")
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

    def test_search_xml_provisions_returns_complete_matching_provisions(self):
        document = (
            b'<?xml version="1.0" encoding="UTF-8"?><act>'
            b'<prov id="one"><label>230</label><heading>Theft</heading>'
            b"<prov.body><para><text>Taking property.</text></para></prov.body></prov>"
            b'<prov id="two"><label>231</label><heading>Burglary</heading><prov.body><para>'
            b"<text>Every one commits BURGLARY who enters without authority.</text>"
            b"</para></prov.body></prov></act>"
        )

        matches, total_matches = _search_xml_provisions(document, "burglary", max_results=10)

        assert total_matches == 1
        assert matches == [
            {
                "provision_id": "two",
                "label": "231",
                "heading": "Burglary",
                "text": "231 Burglary Every one commits BURGLARY who enters without authority.",
                "text_truncated": False,
            }
        ]

    def test_search_xml_provisions_preserves_inline_citation_punctuation(self):
        document = b"""<?xml version="1.0" encoding="UTF-8"?><act>
          <prov id="DLM225501" toc="yes"><label denominator="yes">5</label>
            <heading>Justified limitations</heading><prov.body><subprov><label denominator="no"/>
              <para><text>Subject to <citation jurisdiction="nz"><intref href="DLM225500">
                section 4</intref></citation>, the rights and freedoms contained in this Bill of Rights may be
                subject only to reasonable limits.</text></para>
            </subprov></prov.body>
          </prov>
        </act>"""

        matches, total_matches = _search_xml_provisions(document, "section 4, the rights", max_results=10)

        assert total_matches == 1
        assert matches[0]["text"] == (
            "5 Justified limitations Subject to section 4, the rights and freedoms contained in this Bill of Rights "
            "may be subject only to reasonable limits."
        )

    def test_search_xml_provisions_reports_matches_beyond_result_limit(self):
        document = b"""<?xml version="1.0"?><act>
          <prov id="one"><heading>Burglary one</heading></prov>
          <prov id="two"><heading>Burglary two</heading></prov>
        </act>"""

        matches, total_matches = _search_xml_provisions(document, "burglary", max_results=1)

        assert [match["provision_id"] for match in matches] == ["one"]
        assert total_matches == 2

    @pytest.mark.parametrize(
        "selector, expected_ids",
        [
            ({"section": "35", "provision_id": None}, ["main-35", "schedule-35"]),
            ({"section": None, "provision_id": "main-35"}, ["main-35"]),
        ],
    )
    def test_get_xml_provisions_uses_exact_selector(self, selector, expected_ids):
        document = b"""<?xml version="1.0"?><act>
          <prov id="main-35"><label>35</label><heading>Main offence</heading></prov>
          <prov id="section-35a"><label>35A</label><heading>Different section</heading></prov>
          <prov id="schedule-35"><label>35</label><heading>Schedule provision</heading></prov>
        </act>"""

        matches, total_matches = _get_xml_provisions(document, **selector)

        assert [match["provision_id"] for match in matches] == expected_ids
        assert total_matches == len(expected_ids)

    @pytest.mark.parametrize(
        "selector",
        [
            {"section": None, "provision_id": None},
            {"section": "35", "provision_id": "main-35"},
        ],
    )
    def test_get_xml_provisions_requires_exactly_one_selector(self, selector):
        with pytest.raises(LegislationError, match="exactly one"):
            _get_xml_provisions(b"<?xml version='1.0'?><act/>", **selector)

    @pytest.mark.parametrize(
        "document, error",
        [
            (b"\xffab", "not valid UTF-8"),
            (b"<html></html>", "unexpected XML response"),
            (b"<?xml version='1.0'?><act>", "malformed XML"),
        ],
    )
    def test_search_xml_provisions_rejects_invalid_documents(self, document, error):
        with pytest.raises(LegislationError, match=error):
            _search_xml_provisions(document, "law", max_results=10)

    async def test_xml_fetch_downloads_once_with_api_key_without_range(self):
        document = b"<?xml version='1.0'?><act/>"
        response = MagicMock(status=200, headers={"Content-Type": "text/html", "Content-Length": "10"})
        response.headers = {"Content-Type": "application/xml", "Content-Length": str(len(document))}
        response.content.read = AsyncMock(side_effect=[document, b""])
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            result = await _fetch_xml_document(XML_URL, "test_api_key")

        assert result == document

        request = session.get.call_args
        assert request.args == (XML_URL,)
        assert request.kwargs == {
            "headers": {
                "Accept": "application/xml",
                "Accept-Encoding": "identity",
                "X-Api-Key": "test_api_key",
            },
            "allow_redirects": False,
            "ssl": True,
        }
        assert response.content.read.await_count == 2

    @pytest.mark.parametrize(
        "status, expected",
        [
            (202, "unexpected HTTP 202"),
            (302, "unexpected HTTP 302"),
            (401, "rejected the API key"),
            (403, "refused the XML document request"),
            (404, "could not find the requested XML document"),
            (429, "temporarily rate-limited XML requests"),
            (500, "could not provide the XML document"),
        ],
    )
    async def test_xml_fetch_requires_200_and_maps_errors(self, status, expected):
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
                await _fetch_xml_document(XML_URL, "test_api_key")

    async def test_xml_fetch_rejects_non_xml_content_type(self):
        response = MagicMock(status=200, headers={"Content-Type": "text/html"})
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            with pytest.raises(LegislationError, match="content type text/html, not XML"):
                await _fetch_xml_document(XML_URL, "test_api_key")

    async def test_xml_fetch_rejects_document_over_content_length_limit(self):
        response = MagicMock(
            status=200,
            headers={"Content-Type": "application/xml", "Content-Length": str(MAX_XML_DOCUMENT_BYTES + 1)},
        )
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with patch("nz_legislation.aiohttp.ClientSession", return_value=session_context):
            with pytest.raises(LegislationError, match="too large"):
                await _fetch_xml_document(XML_URL, "test_api_key")

    async def test_xml_fetch_rejects_stream_over_limit_without_content_length(self):
        response = MagicMock(status=200, headers={"Content-Type": "application/xml"})
        response.content.read = AsyncMock(side_effect=[b"12345678", b"9"])
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("nz_legislation.MAX_XML_DOCUMENT_BYTES", 8),
            patch("nz_legislation.aiohttp.ClientSession", return_value=session_context),
        ):
            with pytest.raises(LegislationError, match="too large"):
                await _fetch_xml_document(XML_URL, "test_api_key")


class TestSharedErrors:
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("search_legislation", {}),
            ("list_versions", {"work_id": WORK_ID}),
            ("get_version", {"version_id": VERSION_ID}),
        ],
    )
    async def test_daily_quota_error_uses_provider_reset_not_sdk_retry_delay(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RateLimitError(120, 429, "provider detail", {})

        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock) as fetch_xml:
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
        ],
    )
    @pytest.mark.parametrize(
        "network_error",
        [aiohttp.ClientConnectionError("private network detail"), TimeoutError("private timeout detail")],
    )
    async def test_api_network_errors_are_curated(self, mock_context, action, inputs, network_error):
        mock_context.fetch.side_effect = network_error

        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock) as fetch_xml:
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
            (HTTPError(422, "Invalid request: test_api_key", {}), "cannot be completed as submitted"),
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


class TestGetVersionProvision:
    async def test_returns_exact_section_from_one_xml_download(self, mock_context):
        document = b"""<?xml version="1.0"?><act>
          <prov id="DLM434650"><label>35</label><heading>Driving offence</heading>
            <prov.body><para><text>Operates a motor vehicle recklessly.</text></para></prov.body>
          </prov>
          <prov id="other"><label>35A</label><heading>Other offence</heading></prov>
        </act>"""

        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock, return_value=document) as fetch_xml:
            result = await nz_legislation.execute_action(
                "get_version_provision", {"version_id": VERSION_ID, "section": "35"}, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["version_id"] == VERSION_ID
        assert data["source_url"] == CANONICAL_XML_URL
        assert data["section"] == "35"
        assert data["provision_id"] is None
        assert data["returned_matches"] == data["total_matches"] == 1
        assert data["has_more_matches"] is False
        assert data["provisions"][0]["provision_id"] == "DLM434650"
        assert data["provisions"][0]["label"] == "35"
        assert "recklessly" in data["provisions"][0]["text"]
        assert data["document_bytes"] == len(document)
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_awaited_once_with(CANONICAL_XML_URL, "test_api_key")

    async def test_returns_exact_provision_id(self, mock_context):
        document = b"""<?xml version="1.0"?><act>
          <prov id="one"><label>35</label><heading>Main offence</heading></prov>
          <prov id="two"><label>35</label><heading>Schedule offence</heading></prov>
        </act>"""

        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock, return_value=document):
            result = await nz_legislation.execute_action(
                "get_version_provision", {"version_id": VERSION_ID, "provision_id": "two"}, mock_context
            )

        assert result.type == ResultType.ACTION
        assert [item["provision_id"] for item in result.result.data["provisions"]] == ["two"]

    @pytest.mark.parametrize(
        "inputs",
        [
            {"version_id": VERSION_ID},
            {"version_id": VERSION_ID, "section": "35", "provision_id": "DLM434650"},
        ],
    )
    async def test_requires_exactly_one_selector(self, mock_context, inputs):
        result = await nz_legislation.execute_action("get_version_provision", inputs, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


class TestSearchVersionXml:
    async def test_rejects_non_six_part_version_id_before_authenticated_request(self, mock_context):
        result = await nz_legislation.execute_action(
            "search_version_xml",
            {"version_id": "act_public_1990_109_en", "search_term": "rights"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    async def test_fetches_once_and_returns_matching_provisions(self, mock_context):
        document = (
            b'<?xml version="1.0"?><act><prov id="rights"><label>21</label>'
            b"<heading>Unreasonable search and seizure</heading><prov.body><para>"
            b"<text>Everyone has the right to be secure against unreasonable search or seizure.</text>"
            b'</para></prov.body></prov><prov id="other"><label>22</label><heading>Liberty</heading>'
            b"<prov.body><para><text>Other law.</text></para></prov.body></prov></act>"
        )
        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock, return_value=document) as fetch_xml:
            result = await nz_legislation.execute_action(
                "search_version_xml",
                {"version_id": VERSION_ID, "search_term": "UNREASONABLE SEARCH", "max_results": 5},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["version_id"] == VERSION_ID
        assert data["source_url"] == CANONICAL_XML_URL
        assert data["search_term"] == "UNREASONABLE SEARCH"
        assert data["returned_matches"] == data["total_matches"] == 1
        assert data["has_more_matches"] is False
        assert data["document_bytes"] == len(document)
        assert data["matches"][0]["provision_id"] == "rights"
        assert data["matches"][0]["label"] == "21"
        assert data["matches"][0]["heading"] == "Unreasonable search and seizure"
        assert "right to be secure" in data["matches"][0]["text"]
        mock_context.fetch.assert_not_called()
        fetch_xml.assert_awaited_once_with(CANONICAL_XML_URL, "test_api_key")

    async def test_uses_version_bound_canonical_url(self, mock_context):
        with patch(
            "nz_legislation._fetch_xml_document",
            new_callable=AsyncMock,
            return_value=b"<?xml version='1.0'?><act/>",
        ) as fetch_xml:
            result = await nz_legislation.execute_action(
                "search_version_xml", {"version_id": VERSION_ID, "search_term": "rights"}, mock_context
            )

        assert result.result.data["source_url"] == CANONICAL_XML_URL
        fetch_xml.assert_awaited_once_with(CANONICAL_XML_URL, "test_api_key")

    async def test_limits_returned_matches_without_another_xml_request(self, mock_context):
        document = b"""<?xml version="1.0"?><act>
          <prov id="one"><heading>Rights one</heading></prov>
          <prov id="two"><heading>Rights two</heading></prov>
        </act>"""

        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock, return_value=document) as fetch_xml:
            result = await nz_legislation.execute_action(
                "search_version_xml",
                {"version_id": VERSION_ID, "search_term": "rights", "max_results": 1},
                mock_context,
            )

        data = result.result.data
        assert [match["provision_id"] for match in data["matches"]] == ["one"]
        assert data["returned_matches"] == 1
        assert data["total_matches"] == 2
        assert data["has_more_matches"] is True
        fetch_xml.assert_awaited_once()

    async def test_rejects_unexpected_xml_response(self, mock_context):
        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = LegislationError(
                "The New Zealand Legislation website returned an unexpected XML response."
            )
            result = await nz_legislation.execute_action(
                "search_version_xml", {"version_id": VERSION_ID, "search_term": "rights"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected XML response" in result.result.message

    async def test_xml_document_not_found_is_distinct_from_missing_version(self, mock_context):
        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = LegislationError(
                "The New Zealand Legislation website could not find the requested XML document."
            )
            result = await nz_legislation.execute_action(
                "search_version_xml", {"version_id": VERSION_ID, "search_term": "rights"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "requested XML document" in result.result.message

    async def test_xml_network_error_is_curated(self, mock_context):
        with patch("nz_legislation._fetch_xml_document", new_callable=AsyncMock) as fetch_xml:
            fetch_xml.side_effect = aiohttp.ClientConnectionError("private network detail")
            result = await nz_legislation.execute_action(
                "search_version_xml", {"version_id": VERSION_ID, "search_term": "rights"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "The New Zealand Legislation website could not provide the XML document."
        assert "private network detail" not in result.result.message

    @pytest.mark.parametrize("max_results", [0, 21])
    async def test_max_results_bounds_are_schema_validated(self, mock_context, max_results):
        result = await nz_legislation.execute_action(
            "search_version_xml",
            {"version_id": VERSION_ID, "search_term": "rights", "max_results": max_results},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    async def test_search_term_is_required(self, mock_context):
        result = await nz_legislation.execute_action("search_version_xml", {"version_id": VERSION_ID}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    async def test_search_term_must_include_non_whitespace_text(self, mock_context):
        result = await nz_legislation.execute_action(
            "search_version_xml", {"version_id": VERSION_ID, "search_term": "   "}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "must include text" in result.result.message
        mock_context.fetch.assert_not_called()

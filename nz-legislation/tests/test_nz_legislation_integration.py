"""
Read-only end-to-end tests for the New Zealand Legislation integration.

These tests call the real API and require NZ_LEGISLATION_API_KEY in .env or
the environment. Request a key from contact@pco.govt.nz.

Run safely (all tests are read-only):
    pytest nz-legislation/tests/test_nz_legislation_integration.py -m "integration and not destructive"

The default pytest configuration and test_*_integration.py name exclude this
file from CI.
"""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nz_legislation import nz_legislation

pytestmark = pytest.mark.integration

KNOWN_WORK_ID = "act_public_1990_109"
KNOWN_VERSION_ID = "act_public_1990_109_en_2022-08-30"


@pytest_asyncio.fixture
async def live_context(env_credentials):
    api_key = env_credentials("NZ_LEGISLATION_API_KEY")
    if not api_key:
        pytest.skip("NZ_LEGISLATION_API_KEY not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": api_key}}

    async with aiohttp.ClientSession() as session:

        async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, timeout=None, **kwargs):
            client_timeout = aiohttp.ClientTimeout(total=timeout or 30)
            async with session.request(
                method,
                url,
                json=json,
                headers=headers,
                params=params,
                timeout=client_timeout,
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = await resp.json(content_type=None)
                else:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

        ctx.fetch = AsyncMock(side_effect=real_fetch)
        yield ctx


class TestSearchLegislation:
    async def test_title_search_returns_matching_work_metadata(self, live_context):
        result = await nz_legislation.execute_action(
            "search_legislation",
            {"search_term": '"New Zealand Bill of Rights Act"', "search_field": "title", "per_page": 5},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["works"]
        assert len(data["works"]) <= 5
        assert data["total"] >= len(data["works"])
        assert all(work["work_id"] for work in data["works"])
        assert all(work["publisher"] in {"Agency", "Parliamentary Counsel Office"} for work in data["works"])
        assert all(work["latest_matching_version"] for work in data["works"])
        assert data["rate_limit"]["limit"] > 0

    async def test_filtered_browse_respects_page_size(self, live_context):
        result = await nz_legislation.execute_action(
            "search_legislation",
            {
                "legislation_type": "act",
                "act_status": "in_force",
                "publisher": "Parliamentary Counsel Office",
                "sort_by": "year_desc",
                "page": 2,
                "per_page": 2,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        works = data["works"]
        assert data["page"] == 2
        assert len(works) == 2
        assert all(work["legislation_type"] == "act" for work in works)
        assert all(work["act_status"] == "in_force" for work in works)
        assert all(work["publisher"] == "Parliamentary Counsel Office" for work in works)

    async def test_no_matches_returns_an_empty_final_page(self, live_context):
        result = await nz_legislation.execute_action(
            "search_legislation",
            {
                "search_term": "zzzz-no-such-legislation-987654321",
                "search_field": "title",
                "per_page": 2,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["works"] == []
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total"] == 0
        assert data["has_next_page"] is False

    async def test_bill_results_support_nullable_overall_status(self, live_context):
        result = await nz_legislation.execute_action(
            "search_legislation",
            {"legislation_type": "bill", "bill_status": "current", "per_page": 5},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        works = result.result.data["works"]
        assert works
        assert all(work["legislation_type"] == "bill" for work in works)
        assert all(work["bill_status"] == "current" for work in works)
        assert all(work["legislation_status"] is None for work in works)


class TestListVersions:
    async def test_lists_distinct_pages_of_known_work_versions(self, live_context):
        first = await nz_legislation.execute_action(
            "list_versions", {"work_id": KNOWN_WORK_ID, "sort": "asc", "page": 1, "per_page": 2}, live_context
        )
        second = await nz_legislation.execute_action(
            "list_versions", {"work_id": KNOWN_WORK_ID, "sort": "asc", "page": 2, "per_page": 2}, live_context
        )

        assert first.type == ResultType.ACTION, first.result
        assert second.type == ResultType.ACTION, second.result
        first_data = first.result.data
        second_data = second.result.data
        assert first_data["work_id"] == KNOWN_WORK_ID
        assert first_data["page"] == 1
        assert second_data["page"] == 2
        assert first_data["per_page"] == second_data["per_page"] == 2
        assert first_data["count"] == second_data["count"] == 2
        assert first_data["total"] == second_data["total"]
        assert first_data["total"] > first_data["count"]
        assert first_data["has_next_page"] is True
        first_ids = {version["version_id"] for version in first_data["versions"]}
        second_ids = {version["version_id"] for version in second_data["versions"]}
        assert first_ids.isdisjoint(second_ids)
        assert all(version["work_id"] == KNOWN_WORK_ID for version in first_data["versions"])
        assert all(version["formats"] for version in first_data["versions"])

    async def test_unknown_work_returns_an_empty_version_page(self, live_context):
        unknown_work_id = "act_public_9999_999999"
        result = await nz_legislation.execute_action(
            "list_versions", {"work_id": unknown_work_id, "per_page": 2}, live_context
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["work_id"] == unknown_work_id
        assert data["versions"] == []
        assert data["count"] == 0
        assert data["total"] == 0
        assert data["has_next_page"] is False


class TestGetVersion:
    async def test_gets_known_version_with_format_links(self, live_context):
        result = await nz_legislation.execute_action("get_version", {"version_id": KNOWN_VERSION_ID}, live_context)

        assert result.type == ResultType.ACTION, result.result
        version = result.result.data["version"]
        assert version["version_id"] == KNOWN_VERSION_ID
        assert version["work_id"] == KNOWN_WORK_ID
        assert version["title"]
        assert {item["type"] for item in version["formats"]} >= {"html", "pdf", "xml"}

    async def test_unknown_version_returns_action_error(self, live_context):
        result = await nz_legislation.execute_action(
            "get_version", {"version_id": "act_public_9999_999999_en_9999-12-31"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "version" in result.result.message


class TestAuthentication:
    async def test_invalid_api_key_returns_action_error(self, live_context):
        live_context.auth = {
            "auth_type": "Custom",
            "credentials": {"api_key": "not-a-valid-key"},  # nosec B105
        }

        result = await nz_legislation.execute_action(
            "search_legislation", {"search_term": "rights", "per_page": 1}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "API key" in result.result.message


class TestGetVersionXml:
    async def test_returns_first_bounded_xml_chunk(self, live_context):
        result = await nz_legislation.execute_action(
            "get_version_xml",
            {"version_id": KNOWN_VERSION_ID, "max_bytes": 1000},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["version_id"] == KNOWN_VERSION_ID
        assert data["xml"].startswith("<?xml")
        assert 997 <= data["returned_bytes"] <= 1000
        assert data["total_bytes"] > data["returned_bytes"]
        assert data["truncated"] is True
        assert data["next_offset"] == data["returned_bytes"]
        assert data["source_url"] == "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml"

    async def test_next_offset_returns_next_non_overlapping_chunk(self, live_context):
        first = await nz_legislation.execute_action(
            "get_version_xml",
            {"version_id": KNOWN_VERSION_ID, "max_bytes": 1000},
            live_context,
        )
        assert first.type == ResultType.ACTION, first.result
        first_data = first.result.data

        second = await nz_legislation.execute_action(
            "get_version_xml",
            {
                "version_id": KNOWN_VERSION_ID,
                "offset": first_data["next_offset"],
                "max_bytes": 1000,
            },
            live_context,
        )

        assert second.type == ResultType.ACTION, second.result
        second_data = second.result.data
        assert second_data["source_url"] == first_data["source_url"]
        assert second_data["offset"] == first_data["returned_bytes"]
        assert second_data["xml"] != first_data["xml"]
        assert second_data["total_bytes"] == first_data["total_bytes"]
        assert second_data["rate_limit"] == {"limit": None, "remaining": None, "reset_at": None}
        assert live_context.fetch.await_count == 1

    async def test_final_chunk_matches_the_public_xml_document(self, live_context):
        first = await nz_legislation.execute_action(
            "get_version_xml",
            {"version_id": KNOWN_VERSION_ID, "max_bytes": 1000},
            live_context,
        )
        assert first.type == ResultType.ACTION, first.result
        first_data = first.result.data
        api_key = live_context.auth["credentials"]["api_key"]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                first_data["source_url"],
                headers={
                    "Accept": "application/xml",
                    "Accept-Encoding": "identity",
                    "X-Api-Key": api_key,
                },
                allow_redirects=False,
            ) as response:
                assert response.status == 200
                document = await response.read()

        offset = max(0, len(document) - 1000)
        while True:
            try:
                expected_xml = document[offset:].decode("utf-8")
                break
            except UnicodeDecodeError as exc:
                assert exc.start == 0
                offset += 1

        final = await nz_legislation.execute_action(
            "get_version_xml",
            {
                "version_id": KNOWN_VERSION_ID,
                "offset": offset,
                "max_bytes": 1000,
            },
            live_context,
        )

        assert final.type == ResultType.ACTION, final.result
        data = final.result.data
        assert data["xml"] == expected_xml
        assert data["offset"] == offset
        assert data["returned_bytes"] == len(document) - offset
        assert data["total_bytes"] == len(document)
        assert data["truncated"] is False
        assert data["next_offset"] is None

    async def test_offset_at_end_of_document_returns_action_error(self, live_context):
        first = await nz_legislation.execute_action(
            "get_version_xml",
            {"version_id": KNOWN_VERSION_ID, "max_bytes": 1000},
            live_context,
        )
        assert first.type == ResultType.ACTION, first.result

        result = await nz_legislation.execute_action(
            "get_version_xml",
            {
                "version_id": KNOWN_VERSION_ID,
                "offset": first.result.data["total_bytes"],
                "max_bytes": 1000,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "outside" in result.result.message

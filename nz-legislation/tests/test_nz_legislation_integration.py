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
                "per_page": 2,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        works = result.result.data["works"]
        assert len(works) <= 2
        assert all(work["legislation_type"] == "act" for work in works)
        assert all(work["act_status"] == "in_force" for work in works)


class TestListVersions:
    async def test_lists_known_work_versions(self, live_context):
        result = await nz_legislation.execute_action(
            "list_versions", {"work_id": KNOWN_WORK_ID, "sort": "asc", "per_page": 2}, live_context
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["work_id"] == KNOWN_WORK_ID
        assert data["versions"]
        assert data["count"] == len(data["versions"])
        assert data["count"] == 2
        assert data["total"] > data["count"]
        assert data["has_next_page"] is True
        assert all(version["work_id"] == KNOWN_WORK_ID for version in data["versions"])
        assert all(version["formats"] for version in data["versions"])


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
        assert data["source_url"].startswith("https://www.legislation.govt.nz/")

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
            {"version_id": KNOWN_VERSION_ID, "offset": first_data["next_offset"], "max_bytes": 1000},
            live_context,
        )

        assert second.type == ResultType.ACTION, second.result
        second_data = second.result.data
        assert second_data["offset"] == first_data["returned_bytes"]
        assert second_data["xml"] != first_data["xml"]
        assert second_data["total_bytes"] == first_data["total_bytes"]

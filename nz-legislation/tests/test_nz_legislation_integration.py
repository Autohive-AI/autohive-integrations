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
CRIMES_ACT_VERSION_ID = "act_public_1961_43_en_2026-08-08"
LAND_TRANSPORT_ACT_VERSION_ID = "act_public_1998_110_en_2026-08-08"


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


class TestGetVersionProvision:
    async def test_returns_land_transport_act_section_35(self, live_context):
        result = await nz_legislation.execute_action(
            "get_version_provision",
            {"version_id": LAND_TRANSPORT_ACT_VERSION_ID, "section": "35"},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["source_url"].endswith("/act/public/1998/110/en/2026-08-08.xml")
        assert data["returned_matches"] >= 1
        section = next(item for item in data["provisions"] if item["provision_id"] == "DLM434650")
        assert section["label"] == "35"
        assert section["heading"] == "Contravention of section 7, or section 22 where no injury or death involved"
        assert "operates a motor vehicle recklessly" in section["text"]
        assert data["document_bytes"] > 1_000_000
        assert live_context.fetch.await_count == 0


class TestSearchVersionXml:
    async def test_finds_current_crimes_act_burglary_provisions(self, live_context):
        result = await nz_legislation.execute_action(
            "search_version_xml",
            {"version_id": CRIMES_ACT_VERSION_ID, "search_term": "burglary"},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        matches_by_label = {match["label"]: match for match in data["matches"]}
        assert matches_by_label.keys() >= {"231", "232", "233"}
        assert matches_by_label["231"]["heading"] == "Burglary"
        assert "Every one commits burglary" in matches_by_label["231"]["text"]
        assert data["document_bytes"] > 1_000_000

    async def test_returns_matching_provision_from_one_xml_download(self, live_context):
        result = await nz_legislation.execute_action(
            "search_version_xml",
            {"version_id": KNOWN_VERSION_ID, "search_term": "unreasonable search or seizure"},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["version_id"] == KNOWN_VERSION_ID
        assert data["search_term"] == "unreasonable search or seizure"
        assert data["matches"]
        assert data["returned_matches"] == data["total_matches"]
        assert data["has_more_matches"] is False
        assert data["document_bytes"] > 0
        assert data["source_url"] == "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml"
        assert any(match["label"] == "21" for match in data["matches"])
        assert any("unreasonable search or seizure" in match["text"].lower() for match in data["matches"])
        assert live_context.fetch.await_count == 0

    async def test_no_matching_provision_returns_empty_results(self, live_context):
        result = await nz_legislation.execute_action(
            "search_version_xml",
            {"version_id": KNOWN_VERSION_ID, "search_term": "zzzz-no-such-provision-987654321"},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["matches"] == []
        assert data["returned_matches"] == data["total_matches"] == 0
        assert data["has_more_matches"] is False

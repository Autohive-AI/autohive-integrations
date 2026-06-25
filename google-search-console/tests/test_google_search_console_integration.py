"""
End-to-end integration tests for the Google Search Console integration.

These tests call the real Google Search Console API and require a valid
OAuth2 access token set in GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN.

This integration uses the Google API Python client directly (not context.fetch),
so the live_context only needs to provide real auth credentials.

Run read-only tests (safe):
    pytest google-search-console/tests/test_google_search_console_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest
from unittest.mock import MagicMock
from autohive_integrations_sdk import ResultType

from google_search_console import google_search_console as integration

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN", "")

# Optional: provide a known verified site URL to avoid chaining list_sites first.
TEST_SITE_URL = os.environ.get("GOOGLE_SEARCH_CONSOLE_TEST_SITE_URL", "")

skip_if_no_token = pytest.mark.skipif(
    not ACCESS_TOKEN,
    reason="GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN required",
)


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("GOOGLE_SEARCH_CONSOLE_ACCESS_TOKEN not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}  # nosec B105
    return ctx


async def _first_site_url(live_context) -> str:
    """Return a site URL from the account, or skip if none exist."""
    if TEST_SITE_URL:
        return TEST_SITE_URL
    result = await integration.execute_action("list_sites", {}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"list_sites failed: {result.result.message}")
    sites = result.result.data.get("sites", [])
    if not sites:
        pytest.skip("No verified sites on this account to test with")
    return sites[0]["site_url"]


# =============================================================================
# LIST SITES
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_sites_returns_list(live_context):
    result = await integration.execute_action("list_sites", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "sites" in data
    assert isinstance(data["sites"], list)
    assert isinstance(data["site_count"], int)


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_sites_item_has_expected_fields(live_context):
    result = await integration.execute_action("list_sites", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    sites = result.result.data["sites"]
    if not sites:
        pytest.skip("No verified sites on this account")
    site = sites[0]
    assert "site_url" in site
    assert "permission_level" in site


# =============================================================================
# QUERY ANALYTICS
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_query_analytics_returns_data(live_context):
    site_url = await _first_site_url(live_context)

    result = await integration.execute_action(
        "query_analytics",
        {
            "site_url": site_url,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "row_limit": 10,
        },
        live_context,
    )

    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "rows" in data
    assert isinstance(data["rows"], list)
    assert isinstance(data["row_count"], int)
    assert data["row_count"] == len(data["rows"])


@skip_if_no_token
@pytest.mark.asyncio
async def test_query_analytics_with_dimensions(live_context):
    site_url = await _first_site_url(live_context)

    result = await integration.execute_action(
        "query_analytics",
        {
            "site_url": site_url,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "dimensions": ["query"],
            "row_limit": 5,
        },
        live_context,
    )

    assert result.type == ResultType.ACTION, result.result.message
    rows = result.result.data["rows"]
    if rows:
        assert "query" in rows[0]
        assert "clicks" in rows[0]
        assert "impressions" in rows[0]
        assert "ctr" in rows[0]
        assert "position" in rows[0]


@skip_if_no_token
@pytest.mark.asyncio
async def test_query_analytics_row_limit_respected(live_context):
    site_url = await _first_site_url(live_context)

    result = await integration.execute_action(
        "query_analytics",
        {
            "site_url": site_url,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "dimensions": ["query"],
            "row_limit": 3,
        },
        live_context,
    )

    assert result.type == ResultType.ACTION, result.result.message
    assert len(result.result.data["rows"]) <= 3


# =============================================================================
# LIST SITEMAPS
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_sitemaps_returns_list(live_context):
    site_url = await _first_site_url(live_context)

    result = await integration.execute_action("list_sitemaps", {"site_url": site_url}, live_context)

    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "sitemaps" in data
    assert isinstance(data["sitemaps"], list)
    assert isinstance(data["sitemap_count"], int)


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_sitemaps_item_has_expected_fields(live_context):
    site_url = await _first_site_url(live_context)

    result = await integration.execute_action("list_sitemaps", {"site_url": site_url}, live_context)

    assert result.type == ResultType.ACTION, result.result.message
    sitemaps = result.result.data["sitemaps"]
    if not sitemaps:
        pytest.skip("No sitemaps found for this site")
    sm = sitemaps[0]
    assert "path" in sm
    assert "last_submitted" in sm
    assert "is_pending" in sm
    assert "is_sitemap_index" in sm


# =============================================================================
# GET SITEMAP
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_sitemap_returns_details(live_context):
    site_url = await _first_site_url(live_context)

    list_result = await integration.execute_action("list_sitemaps", {"site_url": site_url}, live_context)
    assert list_result.type == ResultType.ACTION, list_result.result.message

    sitemaps = list_result.result.data.get("sitemaps", [])
    if not sitemaps:
        pytest.skip("No sitemaps found for this site — cannot test get_sitemap")

    sitemap_url = sitemaps[0]["path"]

    result = await integration.execute_action(
        "get_sitemap",
        {"site_url": site_url, "sitemap_url": sitemap_url},
        live_context,
    )

    assert result.type == ResultType.ACTION, result.result.message
    assert "sitemap" in result.result.data
    assert isinstance(result.result.data["sitemap"], dict)


# =============================================================================
# INSPECT URL
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_inspect_url_returns_inspection_result(live_context):
    site_url = await _first_site_url(live_context)

    # inspection_url must be a full HTTPS page URL; sc-domain: properties are not valid page URLs
    if site_url.startswith("sc-domain:"):
        inspection_url = f"https://{site_url[len('sc-domain:') :]}"
    else:
        inspection_url = site_url

    result = await integration.execute_action(
        "inspect_url",
        {"site_url": site_url, "inspection_url": inspection_url},
        live_context,
    )

    assert result.type == ResultType.ACTION, result.result.message
    assert "inspection_result" in result.result.data
    assert isinstance(result.result.data["inspection_result"], dict)

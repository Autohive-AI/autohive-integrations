"""
Unit tests for the Google Search Console integration (SDK 2.0.0).

Covers all five actions (query_analytics, list_sites, inspect_url,
list_sitemaps, get_sitemap) via mocked Google API client.

Each action is tested for: happy path, empty/edge-case results,
exception path (ActionError), and missing required inputs (VALIDATION_ERROR).
"""

import pytest
from unittest.mock import MagicMock, patch
from autohive_integrations_sdk import ResultType

from google_search_console import google_search_console as integration

pytestmark = pytest.mark.unit


# =============================================================================
# BUILD CREDENTIALS
# =============================================================================


def test_build_credentials_reads_access_token(mock_context):
    from google_search_console import build_credentials

    with patch("google_search_console.Credentials") as mock_creds_cls:
        build_credentials(mock_context)
        mock_creds_cls.assert_called_once_with(
            token="test_token",  # nosec B106
            token_uri="https://oauth2.googleapis.com/token",
        )


# =============================================================================
# QUERY ANALYTICS
# =============================================================================


@pytest.mark.asyncio
async def test_query_analytics_success_with_dimensions(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {
            "rows": [
                {"keys": ["python tutorial"], "clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 3.5},
                {"keys": ["python basics"], "clicks": 50, "impressions": 800, "ctr": 0.0625, "position": 5.2},
            ]
        }

        result = await integration.execute_action(
            "query_analytics",
            {
                "site_url": "https://example.com",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "dimensions": ["query"],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["row_count"] == 2
        assert data["rows"][0]["query"] == "python tutorial"
        assert data["rows"][0]["clicks"] == 100
        assert data["rows"][0]["impressions"] == 1000
        assert data["rows"][0]["ctr"] == 0.1
        assert data["rows"][0]["position"] == 3.5
        assert data["rows"][1]["query"] == "python basics"


@pytest.mark.asyncio
async def test_query_analytics_empty_rows(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {}

        result = await integration.execute_action(
            "query_analytics",
            {"site_url": "https://example.com", "start_date": "2024-01-01", "end_date": "2024-01-31"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["rows"] == []
        assert result.result.data["row_count"] == 0


@pytest.mark.asyncio
async def test_query_analytics_maps_multiple_dimensions(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {
            "rows": [{"keys": ["python", "MOBILE"], "clicks": 10, "impressions": 200, "ctr": 0.05, "position": 8.0}]
        }

        result = await integration.execute_action(
            "query_analytics",
            {
                "site_url": "https://example.com",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "dimensions": ["query", "device"],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        row = result.result.data["rows"][0]
        assert row["query"] == "python"
        assert row["device"] == "MOBILE"


@pytest.mark.asyncio
async def test_query_analytics_passes_optional_params(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {}

        await integration.execute_action(
            "query_analytics",
            {
                "site_url": "https://example.com",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "row_limit": 100,
                "start_row": 50,
                "dimension_filter_groups": [
                    {"filters": [{"dimension": "country", "operator": "equals", "expression": "USA"}]}
                ],
            },
            mock_context,
        )

        call_args = mock_service.searchanalytics.return_value.query.call_args
        body = call_args.kwargs["body"]
        assert body["rowLimit"] == 100
        assert body["startRow"] == 50
        assert "dimensionFilterGroups" in body


@pytest.mark.asyncio
async def test_query_analytics_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action(
        "query_analytics",
        {"site_url": "https://example.com"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_query_analytics_default_row_limit_and_start_row(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {}

        await integration.execute_action(
            "query_analytics",
            {"site_url": "https://example.com", "start_date": "2024-01-01", "end_date": "2024-01-31"},
            mock_context,
        )

        body = mock_service.searchanalytics.return_value.query.call_args.kwargs["body"]
        assert body["rowLimit"] == 25000
        assert body["startRow"] == 0


@pytest.mark.asyncio
async def test_query_analytics_omits_dimensions_when_not_provided(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {}

        await integration.execute_action(
            "query_analytics",
            {"site_url": "https://example.com", "start_date": "2024-01-01", "end_date": "2024-01-31"},
            mock_context,
        )

        body = mock_service.searchanalytics.return_value.query.call_args.kwargs["body"]
        assert "dimensions" not in body
        assert "dimensionFilterGroups" not in body


@pytest.mark.asyncio
async def test_query_analytics_exception_returns_action_error(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_build.side_effect = Exception("API error")

        result = await integration.execute_action(
            "query_analytics",
            {"site_url": "https://example.com", "start_date": "2024-01-01", "end_date": "2024-01-31"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


# =============================================================================
# LIST SITES
# =============================================================================


@pytest.mark.asyncio
async def test_list_sites_success(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sites.return_value.list.return_value.execute.return_value = {
            "siteEntry": [
                {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
                {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteFullUser"},
            ]
        }

        result = await integration.execute_action("list_sites", {}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["site_count"] == 2
        assert data["sites"][0]["site_url"] == "https://example.com/"
        assert data["sites"][0]["permission_level"] == "siteOwner"
        assert data["sites"][1]["site_url"] == "sc-domain:example.com"


@pytest.mark.asyncio
async def test_list_sites_empty(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sites.return_value.list.return_value.execute.return_value = {}

        result = await integration.execute_action("list_sites", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["sites"] == []
        assert result.result.data["site_count"] == 0


@pytest.mark.asyncio
async def test_list_sites_site_missing_fields_defaults_to_empty_string(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sites.return_value.list.return_value.execute.return_value = {"siteEntry": [{}]}

        result = await integration.execute_action("list_sites", {}, mock_context)

        assert result.type == ResultType.ACTION
        site = result.result.data["sites"][0]
        assert site["site_url"] == ""
        assert site["permission_level"] == ""


@pytest.mark.asyncio
async def test_list_sites_calls_api_list(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sites.return_value.list.return_value.execute.return_value = {}

        await integration.execute_action("list_sites", {}, mock_context)

        mock_service.sites.return_value.list.assert_called_once()


@pytest.mark.asyncio
async def test_list_sites_exception_returns_action_error(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_build.side_effect = Exception("Credentials expired")

        result = await integration.execute_action("list_sites", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Credentials expired" in result.result.message


# =============================================================================
# INSPECT URL
# =============================================================================


@pytest.mark.asyncio
async def test_inspect_url_success(mock_context):
    inspection_data = {
        "coverageState": "Submitted and indexed",
        "robotsTxtState": "ALLOWED",
        "indexingState": "INDEXING_ALLOWED",
        "verdict": "PASS",
    }
    with (
        patch("google_search_console.build_credentials") as mock_creds,
        patch("google_search_console.build") as mock_build,
    ):
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.urlInspection.return_value.index.return_value.inspect.return_value.execute.return_value = {
            "inspectionResult": inspection_data
        }

        result = await integration.execute_action(
            "inspect_url",
            {"site_url": "https://example.com", "inspection_url": "https://example.com/page"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["inspection_result"] == inspection_data


@pytest.mark.asyncio
async def test_inspect_url_empty_inspection_result(mock_context):
    with (
        patch("google_search_console.build_credentials") as mock_creds,
        patch("google_search_console.build") as mock_build,
    ):
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.urlInspection.return_value.index.return_value.inspect.return_value.execute.return_value = {}

        result = await integration.execute_action(
            "inspect_url",
            {"site_url": "https://example.com", "inspection_url": "https://example.com/page"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["inspection_result"] == {}


@pytest.mark.asyncio
async def test_inspect_url_request_body_contains_both_urls(mock_context):
    with (
        patch("google_search_console.build_credentials") as mock_creds,
        patch("google_search_console.build") as mock_build,
    ):
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.urlInspection.return_value.index.return_value.inspect.return_value.execute.return_value = {}

        await integration.execute_action(
            "inspect_url",
            {"site_url": "https://example.com", "inspection_url": "https://example.com/about"},
            mock_context,
        )

        call_args = mock_service.urlInspection.return_value.index.return_value.inspect.call_args
        body = call_args.kwargs["body"]
        assert body["siteUrl"] == "https://example.com"
        assert body["inspectionUrl"] == "https://example.com/about"


@pytest.mark.asyncio
async def test_inspect_url_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action(
        "inspect_url",
        {"site_url": "https://example.com"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_inspect_url_exception_returns_action_error(mock_context):
    with (
        patch("google_search_console.build_credentials") as mock_creds,
        patch("google_search_console.build") as mock_build,
    ):
        mock_creds.return_value = MagicMock()
        mock_build.side_effect = Exception("URL not found")

        result = await integration.execute_action(
            "inspect_url",
            {"site_url": "https://example.com", "inspection_url": "https://example.com/page"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "URL not found" in result.result.message


# =============================================================================
# LIST SITEMAPS
# =============================================================================


@pytest.mark.asyncio
async def test_list_sitemaps_success(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sitemaps.return_value.list.return_value.execute.return_value = {
            "sitemap": [
                {
                    "path": "https://example.com/sitemap.xml",
                    "lastSubmitted": "2024-01-15T00:00:00Z",
                    "isPending": False,
                    "isSitemapsIndex": False,
                },
                {
                    "path": "https://example.com/sitemap-index.xml",
                    "lastSubmitted": "2024-01-10T00:00:00Z",
                    "isPending": False,
                    "isSitemapsIndex": True,
                },
            ]
        }

        result = await integration.execute_action("list_sitemaps", {"site_url": "https://example.com"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["sitemap_count"] == 2
        assert data["sitemaps"][0]["path"] == "https://example.com/sitemap.xml"
        assert data["sitemaps"][0]["last_submitted"] == "2024-01-15T00:00:00Z"
        assert data["sitemaps"][0]["is_pending"] is False
        assert data["sitemaps"][0]["is_sitemap_index"] is False
        assert data["sitemaps"][1]["is_sitemap_index"] is True


@pytest.mark.asyncio
async def test_list_sitemaps_empty(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sitemaps.return_value.list.return_value.execute.return_value = {}

        result = await integration.execute_action("list_sitemaps", {"site_url": "https://example.com"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["sitemaps"] == []
        assert result.result.data["sitemap_count"] == 0


@pytest.mark.asyncio
async def test_list_sitemaps_passes_site_url_to_api(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sitemaps.return_value.list.return_value.execute.return_value = {}

        await integration.execute_action("list_sitemaps", {"site_url": "https://example.com"}, mock_context)

        call_args = mock_service.sitemaps.return_value.list.call_args
        assert call_args.kwargs["siteUrl"] == "https://example.com"


@pytest.mark.asyncio
async def test_list_sitemaps_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action("list_sitemaps", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_sitemaps_exception_returns_action_error(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_build.side_effect = Exception("Site not found")

        result = await integration.execute_action("list_sitemaps", {"site_url": "https://example.com"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Site not found" in result.result.message


# =============================================================================
# GET SITEMAP
# =============================================================================


@pytest.mark.asyncio
async def test_get_sitemap_success(mock_context):
    sitemap_data = {
        "path": "https://example.com/sitemap.xml",
        "lastSubmitted": "2024-01-15T00:00:00Z",
        "isPending": False,
        "isSitemapsIndex": False,
        "contents": [{"type": "WEB", "submitted": 120, "indexed": 110}],
    }
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sitemaps.return_value.get.return_value.execute.return_value = sitemap_data

        result = await integration.execute_action(
            "get_sitemap",
            {"site_url": "https://example.com", "sitemap_url": "https://example.com/sitemap.xml"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["sitemap"] == sitemap_data


@pytest.mark.asyncio
async def test_get_sitemap_passes_correct_args(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.sitemaps.return_value.get.return_value.execute.return_value = {}

        await integration.execute_action(
            "get_sitemap",
            {"site_url": "https://example.com", "sitemap_url": "https://example.com/sitemap.xml"},
            mock_context,
        )

        call_args = mock_service.sitemaps.return_value.get.call_args
        assert call_args.kwargs["siteUrl"] == "https://example.com"
        assert call_args.kwargs["feedpath"] == "https://example.com/sitemap.xml"


@pytest.mark.asyncio
async def test_get_sitemap_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action("get_sitemap", {"site_url": "https://example.com"}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_sitemap_exception_returns_action_error(mock_context):
    with patch("google_search_console.build_search_console_service") as mock_build:
        mock_build.side_effect = Exception("Sitemap not found")

        result = await integration.execute_action(
            "get_sitemap",
            {"site_url": "https://example.com", "sitemap_url": "https://example.com/sitemap.xml"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Sitemap not found" in result.result.message

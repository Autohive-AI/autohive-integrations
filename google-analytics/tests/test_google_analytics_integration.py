"""
End-to-end integration tests for the Google Analytics integration.

These tests call the real Google Analytics Data API (via the google-analytics-data
Python SDK) and require valid credentials set in environment variables (via .env
or export).

Required:
    GOOGLE_ANALYTICS_ACCESS_TOKEN  — OAuth2 access token with analytics.readonly scope
    GOOGLE_ANALYTICS_TEST_PROPERTY_ID  — GA4 property ID (e.g. "123456789")

Run read-only tests (safe, default):
    pytest google-analytics/tests/test_google_analytics_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest

from autohive_integrations_sdk.integration import ResultType

from google_analytics import google_analytics

pytestmark = pytest.mark.integration

GA_PROPERTY_ID = os.environ.get("GOOGLE_ANALYTICS_TEST_PROPERTY_ID", "")


def require_property_id():
    if not GA_PROPERTY_ID:
        pytest.skip("GOOGLE_ANALYTICS_TEST_PROPERTY_ID not set")


@pytest.fixture
def live_context(env_credentials, make_context):
    """Real ExecutionContext backed by a live Google OAuth token.

    This integration calls the Google Analytics Data API directly via the
    google-analytics-data Python SDK — not via context.fetch — so no real_fetch
    wrapper is needed (Variant 4 from the writing-integration-tests skill).
    """
    access_token = env_credentials("GOOGLE_ANALYTICS_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("GOOGLE_ANALYTICS_ACCESS_TOKEN not set — skipping integration tests")
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )


# ---------------------------------------------------------------------------
# Read-Only Tests
# ---------------------------------------------------------------------------


class TestRunReport:
    async def test_returns_rows_and_count(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": GA_PROPERTY_ID,
                "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                "metrics": [{"name": "activeUsers"}],
                "limit": 5,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "rows" in data
        assert "row_count" in data
        assert isinstance(data["rows"], list)
        assert data["row_count"] == len(data["rows"])

    async def test_with_dimensions_row_keys_match(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": GA_PROPERTY_ID,
                "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                "dimensions": [{"name": "country"}],
                "metrics": [{"name": "sessions"}],
                "limit": 5,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        rows = result.result.data["rows"]
        if rows:
            assert "country" in rows[0]
            assert "sessions" in rows[0]

    async def test_limit_respected(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": GA_PROPERTY_ID,
                "date_ranges": [{"start_date": "30daysAgo", "end_date": "today"}],
                "dimensions": [{"name": "country"}],
                "metrics": [{"name": "activeUsers"}],
                "limit": 3,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["rows"]) <= 3

    async def test_multiple_date_ranges_accepted(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": GA_PROPERTY_ID,
                "date_ranges": [
                    {"start_date": "7daysAgo", "end_date": "today"},
                    {"start_date": "14daysAgo", "end_date": "7daysAgo"},
                ],
                "metrics": [{"name": "activeUsers"}],
                "limit": 5,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "rows" in result.result.data

    async def test_multiple_metrics_all_appear_in_rows(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": GA_PROPERTY_ID,
                "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
                "limit": 2,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        rows = result.result.data["rows"]
        if rows:
            assert "activeUsers" in rows[0]
            assert "sessions" in rows[0]


class TestRunRealtimeReport:
    async def test_returns_rows_and_count(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_realtime_report",
            {
                "property_id": GA_PROPERTY_ID,
                "metrics": [{"name": "activeUsers"}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "rows" in data
        assert "row_count" in data
        assert isinstance(data["rows"], list)
        assert data["row_count"] == len(data["rows"])

    async def test_with_dimensions_row_keys_match(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_realtime_report",
            {
                "property_id": GA_PROPERTY_ID,
                "dimensions": [{"name": "country"}],
                "metrics": [{"name": "activeUsers"}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        rows = result.result.data["rows"]
        if rows:
            assert "country" in rows[0]
            assert "activeUsers" in rows[0]

    async def test_limit_respected(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_realtime_report",
            {
                "property_id": GA_PROPERTY_ID,
                "metrics": [{"name": "activeUsers"}],
                "limit": 2,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["rows"]) <= 2

    async def test_multiple_metrics_all_appear_in_rows(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "run_realtime_report",
            {
                "property_id": GA_PROPERTY_ID,
                "metrics": [{"name": "activeUsers"}, {"name": "screenPageViews"}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        rows = result.result.data["rows"]
        if rows:
            assert "activeUsers" in rows[0]
            assert "screenPageViews" in rows[0]


class TestGetMetadata:
    async def test_returns_non_empty_dimensions_and_metrics(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "get_metadata",
            {"property_id": GA_PROPERTY_ID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "dimensions" in data
        assert "metrics" in data
        assert len(data["dimensions"]) > 0
        assert len(data["metrics"]) > 0

    async def test_dimension_objects_have_required_fields(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "get_metadata",
            {"property_id": GA_PROPERTY_ID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        dim = result.result.data["dimensions"][0]
        assert "api_name" in dim
        assert "ui_name" in dim
        assert "description" in dim

    async def test_metric_objects_have_required_fields(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "get_metadata",
            {"property_id": GA_PROPERTY_ID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        metric = result.result.data["metrics"][0]
        assert "api_name" in metric
        assert "ui_name" in metric
        assert "description" in metric

    async def test_known_dimension_present(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "get_metadata",
            {"property_id": GA_PROPERTY_ID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        api_names = {d["api_name"] for d in result.result.data["dimensions"]}
        assert "country" in api_names

    async def test_known_metric_present(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "get_metadata",
            {"property_id": GA_PROPERTY_ID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        api_names = {m["api_name"] for m in result.result.data["metrics"]}
        assert "activeUsers" in api_names


class TestBatchRunReports:
    async def test_returns_correct_number_of_reports(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "batch_run_reports",
            {
                "property_id": GA_PROPERTY_ID,
                "requests": [
                    {
                        "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                        "dimensions": [{"name": "country"}],
                        "metrics": [{"name": "activeUsers"}],
                        "limit": 3,
                    },
                    {
                        "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                        "dimensions": [{"name": "deviceCategory"}],
                        "metrics": [{"name": "sessions"}],
                        "limit": 3,
                    },
                ],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "reports" in data
        assert len(data["reports"]) == 2

    async def test_each_report_has_rows_and_row_count(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "batch_run_reports",
            {
                "property_id": GA_PROPERTY_ID,
                "requests": [
                    {
                        "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                        "metrics": [{"name": "activeUsers"}],
                        "limit": 2,
                    }
                ],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        report = result.result.data["reports"][0]
        assert "rows" in report
        assert "row_count" in report
        assert report["row_count"] == len(report["rows"])

    async def test_batch_limit_per_request_respected(self, live_context):
        require_property_id()
        result = await google_analytics.execute_action(
            "batch_run_reports",
            {
                "property_id": GA_PROPERTY_ID,
                "requests": [
                    {
                        "date_ranges": [{"start_date": "30daysAgo", "end_date": "today"}],
                        "dimensions": [{"name": "country"}],
                        "metrics": [{"name": "activeUsers"}],
                        "limit": 2,
                    }
                ],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["reports"][0]["rows"]) <= 2

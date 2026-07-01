import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autohive_integrations_sdk.integration import ResultType

from google_analytics import format_report_response, google_analytics

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def make_report_response(dimension_names, metric_names, row_data):
    """Build a mock RunReportResponse compatible with format_report_response."""
    response = MagicMock()
    response.dimension_headers = [SimpleNamespace(name=n) for n in dimension_names]
    response.metric_headers = [SimpleNamespace(name=n) for n in metric_names]
    rows = []
    for dim_vals, metric_vals in row_data:
        row = MagicMock()
        row.dimension_values = [SimpleNamespace(value=v) for v in dim_vals]
        row.metric_values = [SimpleNamespace(value=v) for v in metric_vals]
        rows.append(row)
    response.rows = rows
    return response


# ---------------------------------------------------------------------------
# Helper: format_report_response
# ---------------------------------------------------------------------------


class TestFormatReportResponse:
    def test_maps_dimension_and_metric_values_to_dict_keys(self):
        response = make_report_response(
            ["country", "city"],
            ["activeUsers", "sessions"],
            [(["US", "New York"], ["100", "200"])],
        )
        rows = format_report_response(response)
        assert len(rows) == 1
        assert rows[0]["country"] == "US"
        assert rows[0]["city"] == "New York"
        assert rows[0]["activeUsers"] == "100"
        assert rows[0]["sessions"] == "200"

    def test_empty_rows_returns_empty_list(self):
        response = make_report_response(["country"], ["activeUsers"], [])
        assert format_report_response(response) == []

    def test_multiple_rows_all_mapped(self):
        response = make_report_response(
            ["country"],
            ["activeUsers"],
            [(["US"], ["100"]), (["UK"], ["50"]), (["AU"], ["25"])],
        )
        rows = format_report_response(response)
        assert len(rows) == 3
        assert rows[1]["country"] == "UK"
        assert rows[2]["activeUsers"] == "25"

    def test_no_dimensions_only_metrics(self):
        response = make_report_response([], ["activeUsers"], [([], ["500"])])
        rows = format_report_response(response)
        assert rows == [{"activeUsers": "500"}]


# ---------------------------------------------------------------------------
# Action: run_report
# ---------------------------------------------------------------------------


class TestRunReport:
    async def test_success_returns_rows_and_count(self, mock_context):
        mock_response = make_report_response(
            ["country"],
            ["activeUsers"],
            [(["US"], ["100"]), (["UK"], ["50"])],
        )
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.run_report.return_value = mock_response

            result = await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

        data = result.result.data
        assert data["row_count"] == 2
        assert len(data["rows"]) == 2
        assert data["rows"][0]["country"] == "US"

    async def test_property_id_formatted_with_prefix(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_report.call_args[0][0]
            assert call_arg.property == "properties/123456789"

    async def test_dimensions_passed_when_provided(self, mock_context):
        mock_response = make_report_response(["country", "city"], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "dimensions": [{"name": "country"}, {"name": "city"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_report.call_args[0][0]
            assert len(call_arg.dimensions) == 2

    async def test_dimensions_empty_when_omitted(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_report.call_args[0][0]
            assert call_arg.dimensions == []

    async def test_default_limit_and_offset_applied(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_report.call_args[0][0]
            assert call_arg.limit == 10000
            assert call_arg.offset == 0

    async def test_exception_returns_action_error(self, mock_context):
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.run_report.side_effect = Exception("API quota exceeded")

            result = await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "API quota exceeded" in result.result.message

    async def test_missing_metrics_returns_validation_error(self, mock_context):
        result = await google_analytics.execute_action(
            "run_report",
            {
                "property_id": "123456789",
                "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
            },
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR

    async def test_response_has_no_result_bool_field(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [([], ["10"])])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.run_report.return_value = mock_response

            result = await google_analytics.execute_action(
                "run_report",
                {
                    "property_id": "123456789",
                    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

        assert "result" not in result.result.data
        assert "error" not in result.result.data


# ---------------------------------------------------------------------------
# Action: run_realtime_report
# ---------------------------------------------------------------------------


class TestRunRealtimeReport:
    async def test_success_returns_rows_and_count(self, mock_context):
        mock_response = make_report_response(["country"], ["activeUsers"], [(["US"], ["42"])])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.run_realtime_report.return_value = mock_response

            result = await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

        data = result.result.data
        assert data["row_count"] == 1
        assert data["rows"][0]["country"] == "US"
        assert data["rows"][0]["activeUsers"] == "42"

    async def test_property_id_formatted_with_prefix(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_realtime_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_realtime_report.call_args[0][0]
            assert call_arg.property == "properties/123456789"

    async def test_dimensions_passed_when_provided(self, mock_context):
        mock_response = make_report_response(["country"], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_realtime_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "dimensions": [{"name": "country"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_realtime_report.call_args[0][0]
            assert len(call_arg.dimensions) == 1

    async def test_dimensions_empty_when_omitted(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_realtime_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

            call_arg = mock_client.run_realtime_report.call_args[0][0]
            assert call_arg.dimensions == []

    async def test_exception_returns_action_error(self, mock_context):
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.run_realtime_report.side_effect = Exception("Permission denied")

            result = await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "metrics": [{"name": "activeUsers"}],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Permission denied" in result.result.message

    async def test_missing_metrics_returns_validation_error(self, mock_context):
        result = await google_analytics.execute_action(
            "run_realtime_report",
            {"property_id": "123456789"},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR

    async def test_custom_limit_passed_to_request(self, mock_context):
        mock_response = make_report_response([], ["activeUsers"], [])
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.run_realtime_report.return_value = mock_response

            await google_analytics.execute_action(
                "run_realtime_report",
                {
                    "property_id": "123456789",
                    "metrics": [{"name": "activeUsers"}],
                    "limit": 50,
                },
                mock_context,
            )

            call_arg = mock_client.run_realtime_report.call_args[0][0]
            assert call_arg.limit == 50


# ---------------------------------------------------------------------------
# Action: get_metadata
# ---------------------------------------------------------------------------


class TestGetMetadata:
    async def test_success_returns_dimensions_and_metrics(self, mock_context):
        mock_response = MagicMock()
        mock_response.dimensions = [
            SimpleNamespace(api_name="country", ui_name="Country", description="User country"),
            SimpleNamespace(api_name="city", ui_name="City", description="User city"),
        ]
        mock_response.metrics = [
            SimpleNamespace(api_name="activeUsers", ui_name="Active Users", description="Active users count"),
        ]

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.get_metadata.return_value = mock_response

            result = await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

        data = result.result.data
        assert len(data["dimensions"]) == 2
        assert data["dimensions"][0]["api_name"] == "country"
        assert data["dimensions"][0]["ui_name"] == "Country"
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["api_name"] == "activeUsers"

    async def test_metadata_name_formatted_with_path(self, mock_context):
        mock_response = MagicMock()
        mock_response.dimensions = []
        mock_response.metrics = []

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.get_metadata.return_value = mock_response

            await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

            call_arg = mock_client.get_metadata.call_args[0][0]
            assert call_arg.name == "properties/123456789/metadata"

    async def test_dimension_shape_has_required_fields(self, mock_context):
        mock_response = MagicMock()
        mock_response.dimensions = [SimpleNamespace(api_name="date", ui_name="Date", description="The date")]
        mock_response.metrics = []

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.get_metadata.return_value = mock_response

            result = await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

        dim = result.result.data["dimensions"][0]
        assert "api_name" in dim
        assert "ui_name" in dim
        assert "description" in dim

    async def test_metric_shape_has_required_fields(self, mock_context):
        mock_response = MagicMock()
        mock_response.dimensions = []
        mock_response.metrics = [SimpleNamespace(api_name="sessions", ui_name="Sessions", description="Session count")]

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.get_metadata.return_value = mock_response

            result = await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

        metric = result.result.data["metrics"][0]
        assert "api_name" in metric
        assert "ui_name" in metric
        assert "description" in metric

    async def test_empty_metadata_returns_empty_lists(self, mock_context):
        mock_response = MagicMock()
        mock_response.dimensions = []
        mock_response.metrics = []

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.get_metadata.return_value = mock_response

            result = await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

        assert result.result.data["dimensions"] == []
        assert result.result.data["metrics"] == []

    async def test_exception_returns_action_error(self, mock_context):
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.get_metadata.side_effect = Exception("Property not found")

            result = await google_analytics.execute_action(
                "get_metadata",
                {"property_id": "123456789"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Property not found" in result.result.message

    async def test_missing_property_id_returns_validation_error(self, mock_context):
        result = await google_analytics.execute_action(
            "get_metadata",
            {},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR


# ---------------------------------------------------------------------------
# Action: batch_run_reports
# ---------------------------------------------------------------------------


class TestBatchRunReports:
    async def test_success_returns_multiple_reports(self, mock_context):
        mock_report_1 = make_report_response(["country"], ["activeUsers"], [(["US"], ["100"])])
        mock_report_2 = make_report_response(["deviceCategory"], ["sessions"], [(["mobile"], ["200"])])
        mock_batch = MagicMock()
        mock_batch.reports = [mock_report_1, mock_report_2]

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.batch_run_reports.return_value = mock_batch

            result = await google_analytics.execute_action(
                "batch_run_reports",
                {
                    "property_id": "123456789",
                    "requests": [
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "metrics": [{"name": "activeUsers"}],
                        },
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "metrics": [{"name": "sessions"}],
                        },
                    ],
                },
                mock_context,
            )

        data = result.result.data
        assert len(data["reports"]) == 2
        assert data["reports"][0]["row_count"] == 1
        assert data["reports"][0]["rows"][0]["country"] == "US"
        assert data["reports"][1]["rows"][0]["deviceCategory"] == "mobile"

    async def test_batch_property_id_formatted_with_prefix(self, mock_context):
        mock_batch = MagicMock()
        mock_batch.reports = []

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.batch_run_reports.return_value = mock_batch

            await google_analytics.execute_action(
                "batch_run_reports",
                {
                    "property_id": "123456789",
                    "requests": [
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "metrics": [{"name": "activeUsers"}],
                        }
                    ],
                },
                mock_context,
            )

            call_arg = mock_client.batch_run_reports.call_args[0][0]
            assert call_arg.property == "properties/123456789"

    async def test_report_shape_has_rows_and_row_count(self, mock_context):
        mock_report = make_report_response([], ["activeUsers"], [([], ["500"])])
        mock_batch = MagicMock()
        mock_batch.reports = [mock_report]

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.batch_run_reports.return_value = mock_batch

            result = await google_analytics.execute_action(
                "batch_run_reports",
                {
                    "property_id": "123456789",
                    "requests": [
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "metrics": [{"name": "activeUsers"}],
                        }
                    ],
                },
                mock_context,
            )

        report = result.result.data["reports"][0]
        assert "rows" in report
        assert "row_count" in report
        assert report["row_count"] == len(report["rows"])

    async def test_request_dimensions_passed_when_provided(self, mock_context):
        mock_batch = MagicMock()
        mock_batch.reports = [make_report_response(["country"], ["activeUsers"], [])]

        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.batch_run_reports.return_value = mock_batch

            await google_analytics.execute_action(
                "batch_run_reports",
                {
                    "property_id": "123456789",
                    "requests": [
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "dimensions": [{"name": "country"}],
                            "metrics": [{"name": "activeUsers"}],
                        }
                    ],
                },
                mock_context,
            )

            call_arg = mock_client.batch_run_reports.call_args[0][0]
            assert len(call_arg.requests[0].dimensions) == 1

    async def test_exception_returns_action_error(self, mock_context):
        with patch("google_analytics.BetaAnalyticsDataClient") as mock_cls:
            mock_cls.return_value.batch_run_reports.side_effect = Exception("Batch quota exceeded")

            result = await google_analytics.execute_action(
                "batch_run_reports",
                {
                    "property_id": "123456789",
                    "requests": [
                        {
                            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
                            "metrics": [{"name": "activeUsers"}],
                        }
                    ],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Batch quota exceeded" in result.result.message

    async def test_missing_requests_returns_validation_error(self, mock_context):
        result = await google_analytics.execute_action(
            "batch_run_reports",
            {"property_id": "123456789"},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR

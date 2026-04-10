from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any, List
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunRealtimeReportRequest,
    GetMetadataRequest,
    BatchRunReportsRequest,
    RunReportResponse,
)
from google.oauth2.credentials import Credentials

google_analytics = Integration.load()

def build_credentials(context: ExecutionContext):
    """Build Google credentials from ExecutionContext.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        Google credentials object
    """
    access_token = context.auth['credentials']['access_token']

    creds = Credentials(
        token=access_token,
        token_uri='https://oauth2.googleapis.com/token'
    )

    return creds

def build_analytics_client(context: ExecutionContext):
    """Build Google Analytics Data API client.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        BetaAnalyticsDataClient instance
    """
    credentials = build_credentials(context)
    client = BetaAnalyticsDataClient(credentials=credentials)
    return client

def format_report_response(response: RunReportResponse) -> List[Dict[str, Any]]:
    """Format a report response into a list of dictionaries.

    Args:
        response: RunReportResponse from the Analytics API

    Returns:
        List of dictionaries with dimension and metric values
    """
    rows = []

    for row in response.rows:
        row_dict = {}

        # Add dimension values
        for i, dimension_value in enumerate(row.dimension_values):
            dimension_name = response.dimension_headers[i].name
            row_dict[dimension_name] = dimension_value.value

        # Add metric values
        for i, metric_value in enumerate(row.metric_values):
            metric_name = response.metric_headers[i].name
            row_dict[metric_name] = metric_value.value

        rows.append(row_dict)

    return rows

@google_analytics.action("run_report")
class RunReport(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Generate a customized report of Google Analytics event data."""
        try:
            client = build_analytics_client(context)
            property_id = inputs['property_id']

            # Build date ranges
            date_ranges = [
                DateRange(
                    start_date=dr['start_date'],
                    end_date=dr['end_date']
                )
                for dr in inputs['date_ranges']
            ]

            # Build dimensions (optional)
            dimensions = []
            if 'dimensions' in inputs and inputs['dimensions']:
                dimensions = [
                    Dimension(name=d['name'])
                    for d in inputs['dimensions']
                ]

            # Build metrics
            metrics = [
                Metric(name=m['name'])
                for m in inputs['metrics']
            ]

            # Create request
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=date_ranges,
                dimensions=dimensions,
                metrics=metrics,
                limit=inputs.get('limit', 10000),
                offset=inputs.get('offset', 0)
            )

            # Execute request
            response = client.run_report(request)

            # Format response
            rows = format_report_response(response)

            return ActionResult(
                data={
                    "rows": rows,
                    "row_count": len(rows),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "rows": [],
                    "row_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_analytics.action("run_realtime_report")
class RunRealtimeReport(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get real-time Google Analytics data for the last 30 minutes."""
        try:
            client = build_analytics_client(context)
            property_id = inputs['property_id']

            # Build dimensions (optional)
            dimensions = []
            if 'dimensions' in inputs and inputs['dimensions']:
                dimensions = [
                    Dimension(name=d['name'])
                    for d in inputs['dimensions']
                ]

            # Build metrics
            metrics = [
                Metric(name=m['name'])
                for m in inputs['metrics']
            ]

            # Create request
            request = RunRealtimeReportRequest(
                property=f"properties/{property_id}",
                dimensions=dimensions,
                metrics=metrics,
                limit=inputs.get('limit', 10000)
            )

            # Execute request
            response = client.run_realtime_report(request)

            # Format response (reuse the same format function)
            rows = format_report_response(response)

            return ActionResult(
                data={
                    "rows": rows,
                    "row_count": len(rows),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "rows": [],
                    "row_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_analytics.action("get_metadata")
class GetMetadata(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve available dimensions and metrics for a Google Analytics property."""
        try:
            client = build_analytics_client(context)
            property_id = inputs['property_id']

            # Create request
            request = GetMetadataRequest(
                name=f"properties/{property_id}/metadata"
            )

            # Execute request
            response = client.get_metadata(request)

            # Format dimensions
            dimensions = []
            for dimension in response.dimensions:
                dimensions.append({
                    "api_name": dimension.api_name,
                    "ui_name": dimension.ui_name,
                    "description": dimension.description
                })

            # Format metrics
            metrics = []
            for metric in response.metrics:
                metrics.append({
                    "api_name": metric.api_name,
                    "ui_name": metric.ui_name,
                    "description": metric.description
                })

            return ActionResult(
                data={
                    "dimensions": dimensions,
                    "metrics": metrics,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "dimensions": [],
                    "metrics": [],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@google_analytics.action("batch_run_reports")
class BatchRunReports(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Run multiple reports in a single API call for efficiency."""
        try:
            client = build_analytics_client(context)
            property_id = inputs['property_id']

            # Build report requests
            report_requests = []
            for req in inputs['requests']:
                # Build date ranges
                date_ranges = [
                    DateRange(
                        start_date=dr['start_date'],
                        end_date=dr['end_date']
                    )
                    for dr in req['date_ranges']
                ]

                # Build dimensions (optional)
                dimensions = []
                if 'dimensions' in req and req['dimensions']:
                    dimensions = [
                        Dimension(name=d['name'])
                        for d in req['dimensions']
                    ]

                # Build metrics
                metrics = [
                    Metric(name=m['name'])
                    for m in req['metrics']
                ]

                # Create individual report request
                report_request = RunReportRequest(
                    property=f"properties/{property_id}",
                    date_ranges=date_ranges,
                    dimensions=dimensions,
                    metrics=metrics,
                    limit=req.get('limit', 10000),
                    offset=req.get('offset', 0)
                )

                report_requests.append(report_request)

            # Create batch request
            batch_request = BatchRunReportsRequest(
                property=f"properties/{property_id}",
                requests=report_requests
            )

            # Execute batch request
            response = client.batch_run_reports(batch_request)

            # Format responses
            reports = []
            for report_response in response.reports:
                rows = format_report_response(report_response)
                reports.append({
                    "rows": rows,
                    "row_count": len(rows)
                })

            return ActionResult(
                data={
                    "reports": reports,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "reports": [],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

"""
End-to-end integration tests for the AWS integration.

Requires credentials in environment variables or a .env file at the repo root:
    AWS_ACCESS_KEY_ID     -- AWS access key
    AWS_SECRET_ACCESS_KEY -- AWS secret access key
    AWS_REGION            -- AWS region (default: us-east-1)

Optional — needed for service-specific tests:
    AWS_DETECTOR_ID   -- GuardDuty detector ID (for list/get/archive finding tests)
    AWS_TRAIL_NAME    -- CloudTrail trail name (for get_trail_status, get_event_selectors)
    AWS_LOG_GROUP     -- CloudWatch Logs group name (for filter_log_events)
    AWS_LOG_STREAM    -- CloudWatch Logs stream name (for get_log_events; requires AWS_LOG_GROUP)
    AWS_ALARM_NAME    -- CloudWatch alarm name (for get_alarm_history, set_alarm_state)
    AWS_FINDING_ARN   -- Security Hub finding ARN (for get_finding_details, update_finding_workflow)

Run safely (read-only):
    pytest aws/tests/test_aws_integration.py -m "integration and not destructive"

Run destructive (mutates real data):
    pytest aws/tests/test_aws_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from autohive_integrations_sdk import ResultType
from aws.aws import aws  # noqa: E402

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_DETECTOR_ID = os.getenv("AWS_DETECTOR_ID", "")
AWS_TRAIL_NAME = os.getenv("AWS_TRAIL_NAME", "")
AWS_LOG_GROUP = os.getenv("AWS_LOG_GROUP", "")
AWS_LOG_STREAM = os.getenv("AWS_LOG_STREAM", "")
AWS_ALARM_NAME = os.getenv("AWS_ALARM_NAME", "")
AWS_FINDING_ARN = os.getenv("AWS_FINDING_ARN", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY,
        reason="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY required",
    ),
]


@pytest.fixture
def live_context():
    class _Ctx:
        auth = {
            "aws_access_key_id": AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
            "aws_region": AWS_REGION,
        }

    return _Ctx()


# ---- Security Hub ----


@pytest.mark.asyncio
async def test_get_findings(live_context):
    result = await aws.execute_action("get_findings", {"max_results": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "findings" in result.result.data


@pytest.mark.asyncio
async def test_get_finding_details(live_context):
    finding_arn = AWS_FINDING_ARN
    if not finding_arn:
        list_result = await aws.execute_action("get_findings", {"max_results": 1}, live_context)
        findings = list_result.result.data.get("findings", [])
        if not findings:
            pytest.skip("No Security Hub findings available")
        finding_arn = findings[0].get("Id", "")
    result = await aws.execute_action("get_finding_details", {"finding_arn": finding_arn}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "finding" in result.result.data


@pytest.mark.asyncio
async def test_get_insights(live_context):
    result = await aws.execute_action("get_insights", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "insights" in result.result.data


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_update_finding_workflow(live_context):
    finding_arn = AWS_FINDING_ARN
    if not finding_arn:
        pytest.skip("AWS_FINDING_ARN required for update_finding_workflow")
    result = await aws.execute_action(
        "update_finding_workflow",
        {"finding_arns": [finding_arn], "workflow_status": "NOTIFIED"},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- GuardDuty ----


@pytest.mark.asyncio
async def test_list_detectors(live_context):
    result = await aws.execute_action("list_detectors", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "detector_ids" in result.result.data


@pytest.mark.asyncio
async def test_list_guardduty_findings(live_context):
    detector_id = AWS_DETECTOR_ID
    if not detector_id:
        list_result = await aws.execute_action("list_detectors", {}, live_context)
        ids = list_result.result.data.get("detector_ids", [])
        if not ids:
            pytest.skip("No GuardDuty detectors found")
        detector_id = ids[0]
    result = await aws.execute_action("list_guardduty_findings", {"detector_id": detector_id}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "finding_ids" in result.result.data


@pytest.mark.asyncio
async def test_get_guardduty_finding_details(live_context):
    detector_id = AWS_DETECTOR_ID
    if not detector_id:
        list_result = await aws.execute_action("list_detectors", {}, live_context)
        ids = list_result.result.data.get("detector_ids", [])
        if not ids:
            pytest.skip("No GuardDuty detectors found")
        detector_id = ids[0]
    finding_result = await aws.execute_action("list_guardduty_findings", {"detector_id": detector_id}, live_context)
    finding_ids = finding_result.result.data.get("finding_ids", [])
    if not finding_ids:
        pytest.skip("No GuardDuty findings found")
    result = await aws.execute_action(
        "get_guardduty_finding_details",
        {"detector_id": detector_id, "finding_ids": finding_ids[:1]},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "findings" in result.result.data


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_archive_findings(live_context):
    detector_id = AWS_DETECTOR_ID
    if not detector_id:
        pytest.skip("AWS_DETECTOR_ID required for archive_findings")
    finding_result = await aws.execute_action(
        "list_guardduty_findings",
        {"detector_id": detector_id},
        live_context,
    )
    finding_ids = finding_result.result.data.get("finding_ids", [])
    if not finding_ids:
        pytest.skip("No GuardDuty findings to archive")
    result = await aws.execute_action(
        "archive_findings",
        {"detector_id": detector_id, "finding_ids": finding_ids[:1]},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- CloudWatch ----


@pytest.mark.asyncio
async def test_list_metrics(live_context):
    result = await aws.execute_action("list_metrics", {"namespace": "AWS/EC2"}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "metrics" in result.result.data


@pytest.mark.asyncio
async def test_get_metric_data(live_context):
    result = await aws.execute_action(
        "get_metric_data",
        {
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-02T00:00:00Z",
            "metric_data_queries": [
                {
                    "Id": "m1",
                    "MetricStat": {
                        "Metric": {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization"},
                        "Period": 3600,
                        "Stat": "Average",
                    },
                }
            ],
        },
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "metric_data_results" in result.result.data


@pytest.mark.asyncio
async def test_describe_alarms(live_context):
    result = await aws.execute_action("describe_alarms", {"max_records": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "metric_alarms" in result.result.data


@pytest.mark.asyncio
async def test_get_alarm_history(live_context):
    alarm_name = AWS_ALARM_NAME
    kwargs = {}
    if alarm_name:
        kwargs["alarm_name"] = alarm_name
    result = await aws.execute_action("get_alarm_history", kwargs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "alarm_history_items" in result.result.data


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_set_alarm_state(live_context):
    if not AWS_ALARM_NAME:
        pytest.skip("AWS_ALARM_NAME required for set_alarm_state")
    result = await aws.execute_action(
        "set_alarm_state",
        {
            "alarm_name": AWS_ALARM_NAME,
            "state_value": "OK",
            "state_reason": "Autohive integration test - resetting to OK",
        },
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- CloudWatch Logs ----


@pytest.mark.asyncio
async def test_describe_log_groups(live_context):
    result = await aws.execute_action("describe_log_groups", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "log_groups" in result.result.data


@pytest.mark.asyncio
async def test_filter_log_events(live_context):
    if not AWS_LOG_GROUP:
        pytest.skip("AWS_LOG_GROUP required for filter_log_events")
    result = await aws.execute_action(
        "filter_log_events",
        {"log_group_name": AWS_LOG_GROUP},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "events" in result.result.data


@pytest.mark.asyncio
async def test_get_log_events(live_context):
    if not AWS_LOG_GROUP or not AWS_LOG_STREAM:
        pytest.skip("AWS_LOG_GROUP and AWS_LOG_STREAM required for get_log_events")
    result = await aws.execute_action(
        "get_log_events",
        {"log_group_name": AWS_LOG_GROUP, "log_stream_name": AWS_LOG_STREAM},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "events" in result.result.data


# ---- CloudTrail ----


@pytest.mark.asyncio
async def test_lookup_events(live_context):
    result = await aws.execute_action("lookup_events", {"max_results": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "events" in result.result.data


@pytest.mark.asyncio
async def test_describe_trails(live_context):
    result = await aws.execute_action("describe_trails", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "trails" in result.result.data


@pytest.mark.asyncio
async def test_get_trail_status(live_context):
    if not AWS_TRAIL_NAME:
        pytest.skip("AWS_TRAIL_NAME required for get_trail_status")
    result = await aws.execute_action("get_trail_status", {"trail_name": AWS_TRAIL_NAME}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "is_logging" in result.result.data


@pytest.mark.asyncio
async def test_get_event_selectors(live_context):
    if not AWS_TRAIL_NAME:
        pytest.skip("AWS_TRAIL_NAME required for get_event_selectors")
    result = await aws.execute_action("get_event_selectors", {"trail_name": AWS_TRAIL_NAME}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "event_selectors" in result.result.data

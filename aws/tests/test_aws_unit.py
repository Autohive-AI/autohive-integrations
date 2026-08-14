import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import MagicMock, patch
from autohive_integrations_sdk import ResultType
from aws import aws  # noqa: E402

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Security Hub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_findings(mock_context):
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": [{"Id": "arn:aws:finding/1"}], "NextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_findings", {"max_results": 5}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "findings" in result.result.data


@pytest.mark.asyncio
async def test_get_findings_error(mock_context):
    mock_client = MagicMock()
    mock_client.get_findings.side_effect = Exception("Access denied")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_findings", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Access denied" in result.result.message


@pytest.mark.asyncio
async def test_get_finding_details(mock_context):
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": [{"Id": "arn:aws:finding/1", "ProductArn": "arn:aws:product"}]}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_finding_details", {"finding_arn": "arn:aws:finding/1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["finding"] is not None


@pytest.mark.asyncio
async def test_update_finding_workflow(mock_context):
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": [{"Id": "arn:aws:finding/1", "ProductArn": "arn:aws:product"}]}
    mock_client.batch_update_findings.return_value = {
        "ProcessedFindings": [{"Id": "arn:aws:finding/1"}],
        "UnprocessedFindings": [],
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "update_finding_workflow",
            {"finding_arns": ["arn:aws:finding/1"], "workflow_status": "RESOLVED"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert "processed_findings" in result.result.data


@pytest.mark.asyncio
async def test_get_insights(mock_context):
    mock_client = MagicMock()
    mock_client.get_insights.return_value = {
        "Insights": [
            {"InsightArn": "arn:aws:insight/1", "Name": "Test Insight", "Filters": {}, "GroupByAttribute": "Type"}
        ],
        "NextToken": None,
    }
    mock_client.get_insight_results.return_value = {
        "InsightResults": {"InsightArn": "arn:aws:insight/1", "ResultValues": []}
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_insights", {"max_results": 5}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "insights" in result.result.data


# ---------------------------------------------------------------------------
# GuardDuty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_detectors(mock_context):
    mock_client = MagicMock()
    mock_client.list_detectors.return_value = {"DetectorIds": ["abc123"], "NextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_detectors", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["detector_ids"] == ["abc123"]


@pytest.mark.asyncio
async def test_list_guardduty_findings(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {"FindingIds": ["id1", "id2"], "NextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_guardduty_findings", {"detector_id": "abc123"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["finding_ids"] == ["id1", "id2"]


@pytest.mark.asyncio
async def test_list_guardduty_findings_error(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.side_effect = Exception("DetectorNotFoundException")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_guardduty_findings", {"detector_id": "bad"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "DetectorNotFoundException" in result.result.message


@pytest.mark.asyncio
async def test_get_guardduty_finding_details(mock_context):
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": [{"Id": "id1", "Type": "Recon"}]}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "get_guardduty_finding_details",
            {"detector_id": "abc123", "finding_ids": ["id1"]},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["findings"]) == 1


@pytest.mark.asyncio
async def test_archive_findings(mock_context):
    mock_client = MagicMock()
    mock_client.archive_findings.return_value = {}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "archive_findings",
            {"detector_id": "abc123", "finding_ids": ["id1"]},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["success"] is True


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_inspector_findings(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {
        "findings": [{"findingArn": "arn:aws:inspector2:us-east-1:1:finding/abc", "severity": "CRITICAL"}],
        "nextToken": None,
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_inspector_findings", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["findings"][0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_list_inspector_findings_defaults_to_active_status(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {"findings": [], "nextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        await aws.execute_action("list_inspector_findings", {}, mock_context)
    filter_criteria = mock_client.list_findings.call_args.kwargs["filterCriteria"]
    assert filter_criteria["findingStatus"] == [{"comparison": "EQUALS", "value": "ACTIVE"}]


@pytest.mark.asyncio
async def test_list_inspector_findings_status_all_omits_filter(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {"findings": [], "nextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        await aws.execute_action("list_inspector_findings", {"status": "ALL"}, mock_context)
    assert "filterCriteria" not in mock_client.list_findings.call_args.kwargs


@pytest.mark.asyncio
async def test_list_inspector_findings_default_sort_is_severity_desc(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {"findings": [], "nextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        await aws.execute_action("list_inspector_findings", {}, mock_context)
    assert mock_client.list_findings.call_args.kwargs["sortCriteria"] == {"field": "SEVERITY", "sortOrder": "DESC"}


@pytest.mark.asyncio
async def test_list_inspector_findings_last_hours_builds_time_range(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.return_value = {"findings": [], "nextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        await aws.execute_action("list_inspector_findings", {"last_hours": 24}, mock_context)
    filter_criteria = mock_client.list_findings.call_args.kwargs["filterCriteria"]
    time_range = filter_criteria["firstObservedAt"][0]
    assert (time_range["endInclusive"] - time_range["startInclusive"]).total_seconds() == pytest.approx(
        24 * 3600, abs=2
    )


@pytest.mark.asyncio
async def test_list_inspector_findings_last_hours_with_next_token_rejected(mock_context):
    mock_client = MagicMock()
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "list_inspector_findings",
            {"last_hours": 24, "next_token": "page-2"},  # nosec B105
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "last_hours" in result.result.message
    mock_client.list_findings.assert_not_called()


@pytest.mark.asyncio
async def test_list_inspector_findings_error(mock_context):
    mock_client = MagicMock()
    mock_client.list_findings.side_effect = Exception("Throttled")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_inspector_findings", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Throttled" in result.result.message


@pytest.mark.asyncio
async def test_get_inspector_finding_details(mock_context):
    mock_client = MagicMock()
    mock_client.batch_get_finding_details.return_value = {
        "findingDetails": [{"findingArn": "arn:aws:inspector2:us-east-1:1:finding/abc", "riskScore": 9}],
        "errors": [],
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "get_inspector_finding_details",
            {"finding_arns": ["arn:aws:inspector2:us-east-1:1:finding/abc"]},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["findings"][0]["riskScore"] == 9


@pytest.mark.asyncio
async def test_get_inspector_finding_details_batches_in_groups_of_10(mock_context):
    mock_client = MagicMock()
    mock_client.batch_get_finding_details.side_effect = [
        {"findingDetails": [{"findingArn": f"arn{i}"} for i in range(10)], "errors": []},
        {"findingDetails": [{"findingArn": f"arn{i}"} for i in range(10, 15)], "errors": []},
    ]
    arns = [f"arn{i}" for i in range(15)]
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_inspector_finding_details", {"finding_arns": arns}, mock_context)
    assert mock_client.batch_get_finding_details.call_count == 2
    assert len(result.result.data["findings"]) == 15


@pytest.mark.asyncio
async def test_get_inspector_finding_details_error(mock_context):
    mock_client = MagicMock()
    mock_client.batch_get_finding_details.side_effect = Exception("AccessDeniedException")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_inspector_finding_details", {"finding_arns": ["arn0"]}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "AccessDeniedException" in result.result.message


@pytest.mark.asyncio
async def test_get_inspector_finding_details_empty_list_rejected_by_schema(mock_context):
    # config.json's minItems: 1 rejects finding_arns: [] before the action even runs,
    # instead of silently returning a successful empty result.
    mock_client = MagicMock()
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_inspector_finding_details", {"finding_arns": []}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_client.batch_get_finding_details.assert_not_called()


@pytest.mark.asyncio
async def test_get_inspector_finding_details_empty_list_rejected_by_code_guard(mock_context):
    # Belt-and-suspenders: the action itself also rejects an empty list, in case it's
    # ever invoked directly (bypassing config.json schema validation).
    from actions.inspector import GetInspectorFindingDetailsAction

    mock_client = MagicMock()
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await GetInspectorFindingDetailsAction().execute({"finding_arns": []}, mock_context)
    assert result.message == "finding_arns must contain at least one ARN"
    mock_client.batch_get_finding_details.assert_not_called()


# ---------------------------------------------------------------------------
# CloudWatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_metrics(mock_context):
    mock_client = MagicMock()
    mock_client.list_metrics.return_value = {
        "Metrics": [{"Namespace": "AWS/EC2", "MetricName": "CPUUtilization"}],
        "NextToken": None,
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("list_metrics", {"namespace": "AWS/EC2"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["metrics"]) == 1


@pytest.mark.asyncio
async def test_get_metric_data(mock_context):
    mock_client = MagicMock()
    mock_client.get_metric_data.return_value = {"MetricDataResults": [{"Id": "m1", "Timestamps": [], "Values": []}]}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "get_metric_data",
            {
                "metric_data_queries": [
                    {
                        "Id": "m1",
                        "MetricStat": {
                            "Metric": {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization"},
                            "Period": 300,
                            "Stat": "Average",
                        },
                    }
                ],
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-02T00:00:00Z",
            },
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert "metric_data_results" in result.result.data


@pytest.mark.asyncio
async def test_describe_alarms(mock_context):
    mock_client = MagicMock()
    mock_client.describe_alarms.return_value = {
        "MetricAlarms": [{"AlarmName": "cpu-alarm"}],
        "CompositeAlarms": [],
        "NextToken": None,
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("describe_alarms", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["metric_alarms"]) == 1


@pytest.mark.asyncio
async def test_get_alarm_history(mock_context):
    mock_client = MagicMock()
    mock_client.describe_alarm_history.return_value = {"AlarmHistoryItems": [], "NextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_alarm_history", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "alarm_history_items" in result.result.data


@pytest.mark.asyncio
async def test_set_alarm_state(mock_context):
    mock_client = MagicMock()
    mock_client.set_alarm_state.return_value = {}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "set_alarm_state",
            {"alarm_name": "cpu-alarm", "state_value": "OK", "state_reason": "Testing"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["success"] is True


@pytest.mark.asyncio
async def test_set_alarm_state_error(mock_context):
    mock_client = MagicMock()
    mock_client.set_alarm_state.side_effect = Exception("ResourceNotFoundException")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "set_alarm_state",
            {"alarm_name": "bad-alarm", "state_value": "OK", "state_reason": "test"},
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "ResourceNotFoundException" in result.result.message


# ---------------------------------------------------------------------------
# CloudWatch Logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_describe_log_groups(mock_context):
    mock_client = MagicMock()
    mock_client.describe_log_groups.return_value = {
        "logGroups": [{"logGroupName": "/aws/lambda/fn"}],
        "nextToken": None,
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("describe_log_groups", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["log_groups"]) == 1


@pytest.mark.asyncio
async def test_filter_log_events(mock_context):
    mock_client = MagicMock()
    mock_client.filter_log_events.return_value = {
        "events": [{"message": "ERROR something failed", "timestamp": 1000}],
        "searchedLogStreams": [],
        "nextToken": None,
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "filter_log_events",
            {"log_group_name": "/aws/lambda/fn", "filter_pattern": "ERROR"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_get_log_events(mock_context):
    mock_client = MagicMock()
    mock_client.get_log_events.return_value = {
        "events": [{"message": "log line", "timestamp": 1000}],
        "nextForwardToken": "fwd-token",
        "nextBackwardToken": "bwd-token",
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "get_log_events",
            {"log_group_name": "/aws/lambda/fn", "log_stream_name": "stream-1"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert "events" in result.result.data


@pytest.mark.asyncio
async def test_get_log_events_error(mock_context):
    mock_client = MagicMock()
    mock_client.get_log_events.side_effect = Exception("ResourceNotFoundException")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action(
            "get_log_events",
            {"log_group_name": "/aws/lambda/fn", "log_stream_name": "bad-stream"},
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "ResourceNotFoundException" in result.result.message


# ---------------------------------------------------------------------------
# CloudTrail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_events(mock_context):
    mock_client = MagicMock()
    mock_client.lookup_events.return_value = {"Events": [{"EventName": "RunInstances"}], "NextToken": None}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("lookup_events", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_describe_trails(mock_context):
    mock_client = MagicMock()
    mock_client.describe_trails.return_value = {
        "trailList": [{"Name": "management-events", "TrailARN": "arn:aws:cloudtrail:trail"}]
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("describe_trails", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["trails"]) == 1


@pytest.mark.asyncio
async def test_get_trail_status(mock_context):
    mock_client = MagicMock()
    mock_client.get_trail_status.return_value = {"IsLogging": True, "LatestDeliveryTime": "2024-01-01"}
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_trail_status", {"trail_name": "management-events"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "trail_status" in result.result.data


@pytest.mark.asyncio
async def test_get_event_selectors(mock_context):
    mock_client = MagicMock()
    mock_client.get_event_selectors.return_value = {
        "TrailARN": "arn:aws:cloudtrail:trail",
        "EventSelectors": [{"ReadWriteType": "All"}],
        "AdvancedEventSelectors": [],
    }
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_event_selectors", {"trail_name": "management-events"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "event_selectors" in result.result.data


@pytest.mark.asyncio
async def test_get_event_selectors_error(mock_context):
    mock_client = MagicMock()
    mock_client.get_event_selectors.side_effect = Exception("TrailNotFoundException")
    with patch("helpers.boto3.client", return_value=mock_client):
        result = await aws.execute_action("get_event_selectors", {"trail_name": "bad-trail"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "TrailNotFoundException" in result.result.message

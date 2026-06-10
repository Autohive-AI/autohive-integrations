import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from autohive_integrations_sdk import ResultType
from aws import aws  # noqa: E402

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_DETECTOR_ID = os.getenv("AWS_DETECTOR_ID", "")
AWS_TRAIL_NAME = os.getenv("AWS_TRAIL_NAME", "")
AWS_LOG_GROUP = os.getenv("AWS_LOG_GROUP", "")
AWS_LOG_STREAM = os.getenv("AWS_LOG_STREAM", "")

pytestmark = pytest.mark.skipif(
    not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY,
    reason="AWS credentials not set in environment",
)


@pytest.fixture
def live_context():
    ctx_auth = {
        "aws_access_key_id": AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
        "aws_region": AWS_REGION,
    }

    class _Ctx:
        auth = ctx_auth

    return _Ctx()


@pytest.mark.asyncio
async def test_get_findings_live(live_context):
    result = await aws.execute_action("get_findings", {"max_results": 5}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "findings" in result.result.data


@pytest.mark.asyncio
async def test_list_detectors_live(live_context):
    result = await aws.execute_action("list_detectors", {}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "detector_ids" in result.result.data


@pytest.mark.asyncio
async def test_list_metrics_live(live_context):
    result = await aws.execute_action("list_metrics", {"namespace": "AWS/EC2"}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "metrics" in result.result.data


@pytest.mark.asyncio
async def test_describe_alarms_live(live_context):
    result = await aws.execute_action("describe_alarms", {"max_records": 5}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "metric_alarms" in result.result.data


@pytest.mark.asyncio
async def test_describe_log_groups_live(live_context):
    result = await aws.execute_action("describe_log_groups", {"limit": 5}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "log_groups" in result.result.data


@pytest.mark.asyncio
async def test_lookup_events_live(live_context):
    result = await aws.execute_action("lookup_events", {"max_results": 5}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "events" in result.result.data


@pytest.mark.asyncio
async def test_describe_trails_live(live_context):
    result = await aws.execute_action("describe_trails", {}, live_context)
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type == ResultType.SUCCESS:
        assert "trails" in result.result.data

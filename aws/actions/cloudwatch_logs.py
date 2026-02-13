from autohive_integrations_sdk import ActionHandler, ExecutionContext
from aws import integration
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any
from datetime import datetime


def _iso_to_epoch_ms(iso_string: str) -> int:
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


@integration.action("describe_log_groups")
class DescribeLogGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "logs")
            kwargs = {"limit": inputs.get("limit", 50)}
            if inputs.get("log_group_name_prefix"):
                kwargs["logGroupNamePrefix"] = inputs["log_group_name_prefix"]
            if inputs.get("next_token"):
                kwargs["nextToken"] = inputs["next_token"]
            response = await run_sync(client.describe_log_groups, **kwargs)
            return success_result({
                "log_groups": response.get("logGroups", []),
                "next_token": response.get("nextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("filter_log_events")
class FilterLogEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "logs")
            kwargs = {
                "logGroupName": inputs["log_group_name"],
                "limit": inputs.get("limit", 50)
            }
            if inputs.get("log_stream_names"):
                kwargs["logStreamNames"] = inputs["log_stream_names"]
            if inputs.get("filter_pattern"):
                kwargs["filterPattern"] = inputs["filter_pattern"]
            if inputs.get("start_time"):
                kwargs["startTime"] = _iso_to_epoch_ms(inputs["start_time"])
            if inputs.get("end_time"):
                kwargs["endTime"] = _iso_to_epoch_ms(inputs["end_time"])
            if inputs.get("next_token"):
                kwargs["nextToken"] = inputs["next_token"]
            response = await run_sync(client.filter_log_events, **kwargs)
            return success_result({
                "events": response.get("events", []),
                "searched_log_streams": response.get("searchedLogStreams", []),
                "next_token": response.get("nextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_log_events")
class GetLogEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "logs")
            kwargs = {
                "logGroupName": inputs["log_group_name"],
                "logStreamName": inputs["log_stream_name"],
                "limit": inputs.get("limit", 50),
                "startFromHead": inputs.get("start_from_head", True)
            }
            if inputs.get("start_time"):
                kwargs["startTime"] = _iso_to_epoch_ms(inputs["start_time"])
            if inputs.get("end_time"):
                kwargs["endTime"] = _iso_to_epoch_ms(inputs["end_time"])
            if inputs.get("next_token"):
                kwargs["nextToken"] = inputs["next_token"]
            response = await run_sync(client.get_log_events, **kwargs)
            return success_result({
                "events": response.get("events", []),
                "next_forward_token": response.get("nextForwardToken"),
                "next_backward_token": response.get("nextBackwardToken")
            })
        except Exception as e:
            return error_result(e)

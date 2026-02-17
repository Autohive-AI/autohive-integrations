from autohive_integrations_sdk import ActionHandler, ExecutionContext
from aws import integration
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any
from datetime import datetime


@integration.action("list_metrics")
class ListMetricsAction(ActionHandler):
    """List available CloudWatch metrics, optionally filtered by namespace, name, or dimensions."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudwatch")
            kwargs = {}
            if inputs.get("namespace"):
                kwargs["Namespace"] = inputs["namespace"]
            if inputs.get("metric_name"):
                kwargs["MetricName"] = inputs["metric_name"]
            if inputs.get("dimensions"):
                kwargs["Dimensions"] = inputs["dimensions"]
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.list_metrics, **kwargs)
            return success_result({
                "metrics": response.get("Metrics", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_metric_data")
class GetMetricDataAction(ActionHandler):
    """Retrieve CloudWatch metric data for one or more metrics over a time period."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudwatch")
            start_time = datetime.fromisoformat(inputs["start_time"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(inputs["end_time"].replace("Z", "+00:00"))
            kwargs = {
                "MetricDataQueries": inputs["metric_data_queries"],
                "StartTime": start_time,
                "EndTime": end_time
            }
            response = await run_sync(client.get_metric_data, **kwargs)
            return success_result({
                "metric_data_results": response.get("MetricDataResults", [])
            })
        except Exception as e:
            return error_result(e)


@integration.action("describe_alarms")
class DescribeAlarmsAction(ActionHandler):
    """List and filter CloudWatch alarms by name, prefix, or state."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudwatch")
            kwargs = {"MaxRecords": inputs.get("max_records", 50)}
            if inputs.get("alarm_names"):
                kwargs["AlarmNames"] = inputs["alarm_names"]
            if inputs.get("alarm_name_prefix"):
                kwargs["AlarmNamePrefix"] = inputs["alarm_name_prefix"]
            if inputs.get("state_value"):
                kwargs["StateValue"] = inputs["state_value"]
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.describe_alarms, **kwargs)
            return success_result({
                "metric_alarms": response.get("MetricAlarms", []),
                "composite_alarms": response.get("CompositeAlarms", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_alarm_history")
class GetAlarmHistoryAction(ActionHandler):
    """Retrieve the history of state changes and actions for CloudWatch alarms."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudwatch")
            kwargs = {"MaxRecords": inputs.get("max_records", 50)}
            if inputs.get("alarm_name"):
                kwargs["AlarmName"] = inputs["alarm_name"]
            if inputs.get("alarm_types"):
                kwargs["AlarmTypes"] = inputs["alarm_types"]
            if inputs.get("history_item_type"):
                kwargs["HistoryItemType"] = inputs["history_item_type"]
            if inputs.get("start_date"):
                kwargs["StartDate"] = datetime.fromisoformat(inputs["start_date"].replace("Z", "+00:00"))
            if inputs.get("end_date"):
                kwargs["EndDate"] = datetime.fromisoformat(inputs["end_date"].replace("Z", "+00:00"))
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.describe_alarm_history, **kwargs)
            return success_result({
                "alarm_history_items": response.get("AlarmHistoryItems", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("set_alarm_state")
class SetAlarmStateAction(ActionHandler):
    """Temporarily set the state of a CloudWatch alarm for testing or maintenance."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudwatch")
            kwargs = {
                "AlarmName": inputs["alarm_name"],
                "StateValue": inputs["state_value"],
                "StateReason": inputs["state_reason"]
            }
            await run_sync(client.set_alarm_state, **kwargs)
            return success_result({
                "success": True
            })
        except Exception as e:
            return error_result(e)

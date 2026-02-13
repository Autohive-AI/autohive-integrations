from autohive_integrations_sdk import ActionHandler, ExecutionContext
from aws import integration
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any
from datetime import datetime


@integration.action("lookup_events")
class LookupEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudtrail")
            kwargs = {"MaxResults": inputs.get("max_results", 50)}
            if inputs.get("lookup_attributes"):
                kwargs["LookupAttributes"] = [
                    {"AttributeKey": attr["attribute_key"], "AttributeValue": attr["attribute_value"]}
                    for attr in inputs["lookup_attributes"]
                ]
            if inputs.get("start_time"):
                kwargs["StartTime"] = datetime.fromisoformat(inputs["start_time"].replace("Z", "+00:00"))
            if inputs.get("end_time"):
                kwargs["EndTime"] = datetime.fromisoformat(inputs["end_time"].replace("Z", "+00:00"))
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.lookup_events, **kwargs)
            return success_result({
                "events": response.get("Events", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("describe_trails")
class DescribeTrailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudtrail")
            kwargs = {}
            if inputs.get("trail_name_list"):
                kwargs["trailNameList"] = inputs["trail_name_list"]
            if "include_shadow_trails" in inputs:
                kwargs["includeShadowTrails"] = inputs["include_shadow_trails"]
            else:
                kwargs["includeShadowTrails"] = True
            response = await run_sync(client.describe_trails, **kwargs)
            return success_result({
                "trails": response.get("trailList", [])
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_trail_status")
class GetTrailStatusAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudtrail")
            kwargs = {"Name": inputs["trail_name"]}
            response = await run_sync(client.get_trail_status, **kwargs)
            trail_status = {k: v for k, v in response.items() if k != "ResponseMetadata"}
            return success_result({
                "trail_status": trail_status
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_event_selectors")
class GetEventSelectorsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "cloudtrail")
            kwargs = {"TrailName": inputs["trail_name"]}
            response = await run_sync(client.get_event_selectors, **kwargs)
            return success_result({
                "trail_arn": response.get("TrailARN"),
                "event_selectors": response.get("EventSelectors", []),
                "advanced_event_selectors": response.get("AdvancedEventSelectors", [])
            })
        except Exception as e:
            return error_result(e)

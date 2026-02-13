from autohive_integrations_sdk import ActionHandler, ExecutionContext
from aws import integration
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any


@integration.action("list_detectors")
class ListDetectorsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "guardduty")
            kwargs = {"MaxResults": inputs.get("max_results", 50)}
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.list_detectors, **kwargs)
            return success_result({
                "detector_ids": response.get("DetectorIds", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("list_guardduty_findings")
class ListGuardDutyFindingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "guardduty")
            kwargs = {
                "DetectorId": inputs["detector_id"],
                "MaxResults": inputs.get("max_results", 50)
            }
            if inputs.get("finding_criteria"):
                kwargs["FindingCriteria"] = inputs["finding_criteria"]
            if inputs.get("sort_criteria"):
                kwargs["SortCriteria"] = inputs["sort_criteria"]
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.list_findings, **kwargs)
            return success_result({
                "finding_ids": response.get("FindingIds", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_guardduty_finding_details")
class GetGuardDutyFindingDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "guardduty")
            kwargs = {
                "DetectorId": inputs["detector_id"],
                "FindingIds": inputs["finding_ids"]
            }
            response = await run_sync(client.get_findings, **kwargs)
            return success_result({
                "findings": response.get("Findings", [])
            })
        except Exception as e:
            return error_result(e)


@integration.action("archive_findings")
class ArchiveFindingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "guardduty")
            kwargs = {
                "DetectorId": inputs["detector_id"],
                "FindingIds": inputs["finding_ids"]
            }
            await run_sync(client.archive_findings, **kwargs)
            return success_result({
                "success": True
            })
        except Exception as e:
            return error_result(e)

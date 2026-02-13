"""
AWS Security Hub actions - Findings management and security insights.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aws import integration
from autohive_integrations_sdk import ActionHandler, ExecutionContext
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any


@integration.action("get_findings")
class GetFindingsAction(ActionHandler):
    """
    List and filter security findings from AWS Security Hub.

    Supports optional filters in the GetFindings API format, pagination
    via next_token, and a configurable max_results limit.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "securityhub")
            kwargs = {"MaxResults": inputs.get("max_results", 20)}
            if inputs.get("filters"):
                kwargs["Filters"] = inputs["filters"]
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.get_findings, **kwargs)
            return success_result({
                "findings": response.get("Findings", []),
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_finding_details")
class GetFindingDetailsAction(ActionHandler):
    """
    Get detailed information about a specific Security Hub finding by its ARN.

    Uses the GetFindings API with an Id filter set to EQUALS the provided
    finding_arn, and returns the first matching finding or null.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "securityhub")
            finding_arn = inputs["finding_arn"]
            kwargs = {
                "Filters": {
                    "Id": [{"Value": finding_arn, "Comparison": "EQUALS"}]
                },
                "MaxResults": 1
            }
            response = await run_sync(client.get_findings, **kwargs)
            findings = response.get("Findings", [])
            finding = findings[0] if findings else None
            return success_result({"finding": finding})
        except Exception as e:
            return error_result(e)


@integration.action("update_finding_workflow")
class UpdateFindingWorkflowAction(ActionHandler):
    """
    Update the workflow status of one or more Security Hub findings.

    Accepts a list of finding ARNs, looks up each finding to obtain its
    ProductArn, then calls BatchUpdateFindings to set the new workflow
    status. An optional note can be attached to the findings.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "securityhub")
            finding_arns = inputs["finding_arns"]
            workflow_status = inputs["workflow_status"]
            note = inputs.get("note")

            # Look up each finding to get its ProductArn
            lookup_kwargs = {
                "Filters": {
                    "Id": [
                        {"Value": arn, "Comparison": "EQUALS"}
                        for arn in finding_arns
                    ]
                },
                "MaxResults": len(finding_arns)
            }
            lookup_response = await run_sync(client.get_findings, **lookup_kwargs)
            findings = lookup_response.get("Findings", [])

            # Build FindingIdentifiers from the looked-up findings
            finding_identifiers = [
                {"Id": f["Id"], "ProductArn": f["ProductArn"]}
                for f in findings
            ]

            if not finding_identifiers:
                return success_result({
                    "processed_findings": [],
                    "unprocessed_findings": [
                        {"FindingIdentifier": {"Id": arn}, "ErrorCode": "FindingNotFound",
                         "ErrorMessage": "Finding not found"}
                        for arn in finding_arns
                    ]
                })

            update_kwargs = {
                "FindingIdentifiers": finding_identifiers,
                "Workflow": {"Status": workflow_status}
            }

            if note:
                update_kwargs["Note"] = {
                    "Text": note,
                    "UpdatedBy": "autohive-integration"
                }

            response = await run_sync(client.batch_update_findings, **update_kwargs)
            return success_result({
                "processed_findings": response.get("ProcessedFindings", []),
                "unprocessed_findings": response.get("UnprocessedFindings", [])
            })
        except Exception as e:
            return error_result(e)


@integration.action("get_insights")
class GetInsightsAction(ActionHandler):
    """
    Get security insight results from AWS Security Hub.

    Retrieves insight ARNs via GetInsights, then fetches result details
    for each insight using GetInsightResults. Supports filtering by
    specific insight ARNs and pagination.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "securityhub")
            kwargs = {"MaxResults": inputs.get("max_results", 20)}
            if inputs.get("insight_arns"):
                kwargs["InsightArns"] = inputs["insight_arns"]
            if inputs.get("next_token"):
                kwargs["NextToken"] = inputs["next_token"]
            response = await run_sync(client.get_insights, **kwargs)
            insights = response.get("Insights", [])

            # Fetch results for each insight
            enriched_insights = []
            for insight in insights:
                insight_data = {
                    "insight_arn": insight.get("InsightArn"),
                    "name": insight.get("Name"),
                    "filters": insight.get("Filters"),
                    "group_by_attribute": insight.get("GroupByAttribute")
                }
                try:
                    result_response = await run_sync(
                        client.get_insight_results,
                        InsightArn=insight["InsightArn"]
                    )
                    insight_data["results"] = result_response.get("InsightResults", {})
                except Exception:
                    insight_data["results"] = None
                enriched_insights.append(insight_data)

            return success_result({
                "insights": enriched_insights,
                "next_token": response.get("NextToken")
            })
        except Exception as e:
            return error_result(e)

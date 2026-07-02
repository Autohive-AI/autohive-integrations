"""
AWS Inspector actions - Direct vulnerability findings from Amazon Inspector v2.

Unlike Security Hub's get_findings (which reads a forwarded copy of Inspector
findings that can lag behind), these actions query Inspector directly for
up-to-date results.
"""

from datetime import datetime, timedelta, timezone
from autohive_integrations_sdk import ActionHandler, ExecutionContext
from aws import aws
from helpers import create_boto3_client, run_sync, success_result, error_result
from typing import Dict, Any


@aws.action("list_inspector_findings")
class ListInspectorFindingsAction(ActionHandler):
    """
    List and filter vulnerability findings directly from Amazon Inspector.

    Supports optional filter criteria in the Inspector2 ListFindings API
    format, pagination via next_token, and a configurable max_results limit.
    A `last_hours` shortcut filters to findings first observed within that
    window, and results default to sorting by severity (highest first).

    `last_hours` is resolved to an absolute [now - last_hours, now] range on
    every call. Since this action is stateless, combining it with next_token
    would recompute a shifted window on each page and desync the filter from
    the token AWS is paginating against, so that combination is rejected —
    pass an explicit filter_criteria.firstObservedAt range instead when
    paginating past the first page.

    Unlike a bare ListFindings call, this defaults to ACTIVE findings only
    (matching the Inspector console's "By Lambda function" / summary views),
    since CLOSED and SUPPRESSED findings otherwise dominate the result set.
    Pass status="ALL" to see every finding regardless of status.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            if inputs.get("last_hours") and inputs.get("next_token"):
                raise ValueError(
                    "last_hours cannot be combined with next_token: each call recomputes the time "
                    "window from 'now', which would desync it from the paginated request. Use "
                    "filter_criteria.firstObservedAt with an explicit, fixed range instead when "
                    "paginating past the first page."
                )

            client = create_boto3_client(context, "inspector2")
            kwargs = {"maxResults": inputs.get("max_results", 50)}

            filter_criteria = dict(inputs.get("filter_criteria") or {})
            if inputs.get("last_hours"):
                now = datetime.now(timezone.utc)
                filter_criteria["firstObservedAt"] = filter_criteria.get("firstObservedAt", []) + [
                    {
                        "startInclusive": now - timedelta(hours=inputs["last_hours"]),
                        "endInclusive": now,
                    }
                ]
            status = inputs.get("status", "ACTIVE")
            if status and status != "ALL" and "findingStatus" not in filter_criteria:
                filter_criteria["findingStatus"] = [{"comparison": "EQUALS", "value": status}]
            if filter_criteria:
                kwargs["filterCriteria"] = filter_criteria

            kwargs["sortCriteria"] = inputs.get("sort_criteria") or {"field": "SEVERITY", "sortOrder": "DESC"}

            if inputs.get("next_token"):
                kwargs["nextToken"] = inputs["next_token"]
            response = await run_sync(client.list_findings, **kwargs)
            return success_result(
                {
                    "findings": response.get("findings", []),
                    "next_token": response.get("nextToken"),
                }
            )
        except Exception as e:
            return error_result(e)


@aws.action("get_inspector_finding_details")
class GetInspectorFindingDetailsAction(ActionHandler):
    """
    Get detailed information about one or more Amazon Inspector findings by ARN.

    BatchGetFindingDetails accepts at most 10 ARNs per call, so requests are
    split into batches of 10 and the results merged.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            client = create_boto3_client(context, "inspector2")
            finding_arns = inputs["finding_arns"]

            findings = []
            errors = []
            for i in range(0, len(finding_arns), 10):
                batch = finding_arns[i : i + 10]
                response = await run_sync(client.batch_get_finding_details, findingArns=batch)
                findings.extend(response.get("findingDetails", []))
                errors.extend(response.get("errors", []))

            return success_result({"findings": findings, "errors": errors})
        except Exception as e:
            return error_result(e)

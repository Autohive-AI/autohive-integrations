from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Dict, Any
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone

jira = Integration.load()

# =============================================================================
# ENVIRONMENT CONFIGURATION
# JIRA_CLOUD_ID: Pin to a specific Atlassian Cloud ID to skip auto-discovery.
#                Useful when the OAuth account has access to multiple Jira sites.
# =============================================================================

JIRA_CLOUD_ID_OVERRIDE = os.environ.get("JIRA_CLOUD_ID")
ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"


# ---- Helper Functions ----


def get_access_token(context: ExecutionContext) -> str:
    """Extract and validate the OAuth access token from context."""
    credentials = context.auth.get("credentials", {})
    token = (credentials.get("access_token") or "").strip()
    if not token:
        raise ValueError("access_token is required — ensure the Jira OAuth connection is authorised")
    if "\n" in token or "\r" in token:
        raise ValueError("access_token contains invalid characters")
    return token


async def get_cloud_id(access_token: str, context: ExecutionContext) -> str:
    """
    Return the Atlassian Cloud ID for the authenticated account.
    Uses JIRA_CLOUD_ID env var if set to skip the API call.
    If the account has multiple Jira sites, set JIRA_CLOUD_ID to pin one.
    """
    if JIRA_CLOUD_ID_OVERRIDE:
        return JIRA_CLOUD_ID_OVERRIDE

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    try:
        resources = await context.fetch(ACCESSIBLE_RESOURCES_URL, headers=headers)
    except Exception as e:
        raise Exception(f"Failed to discover Jira Cloud ID: {e}")

    if not resources:
        raise ValueError(
            "No Jira Cloud sites found for this OAuth token. "
            "Ensure the token has the correct scopes and the account has access to a Jira site."
        )

    jira_resource = next(
        (r for r in resources if any("jira" in s.lower() for s in r.get("scopes", []))),
        None,
    )
    if jira_resource:
        return jira_resource["id"]

    return resources[0]["id"]


def api_url(cloud_id: str, path: str) -> str:
    """Build a Jira REST API v3 URL using the Atlassian cloud ID."""
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3{path}"


def agile_url(cloud_id: str, path: str) -> str:
    """Build a Jira Agile API v1 URL using the Atlassian cloud ID."""
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0{path}"


def safe_path(value: str) -> str:
    """URL-encode a path segment."""
    return urllib.parse.quote(str(value), safe="")


def format_jira_datetime(dt_string: str = None) -> str:
    """
    Format a datetime string into the exact format Jira requires for worklog started:
    "2021-01-17T12:34:00.000+0000"  (no colon in offset, mandatory .000 milliseconds)

    Wrong formats silently return HTTP 500 from Jira with no useful error.
    Accepted: 2021-01-17T12:34:00.000+0000
    Rejected: 2021-01-17T12:34:00.000+00:00 (colon in offset)
    Rejected: 2021-01-17T12:34:00+0000 (missing milliseconds)
    Rejected: 2021-01-17T12:34:00Z (Zulu shorthand)

    If dt_string is None, returns current UTC time in the correct format.
    """
    if dt_string is None:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    # Already in correct format — return as-is
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$", dt_string):
        return dt_string

    # Has colon in offset (ISO 8601 standard) — remove the colon
    # e.g. 2021-01-17T12:34:00.000+00:00 -> 2021-01-17T12:34:00.000+0000
    fixed = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", dt_string)
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$", fixed):
        return fixed

    # Missing milliseconds — add .000
    # e.g. 2021-01-17T12:34:00+0000 -> 2021-01-17T12:34:00.000+0000
    fixed = re.sub(r"(\d{2}:\d{2}:\d{2})([+-]\d{4})$", r"\1.000\2", fixed)
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$", fixed):
        return fixed

    # Z suffix — replace with +0000
    fixed = re.sub(r"Z$", ".000+0000", re.sub(r"(\d{2}:\d{2}:\d{2})Z$", r"\1.000+0000", dt_string))
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$", fixed):
        return fixed

    # Last resort: parse and reformat in UTC
    try:
        parsed = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    except Exception:
        raise ValueError(
            f"Cannot parse datetime '{dt_string}'. "
            "Use format: '2021-01-17T12:34:00.000+0000' (no colon in timezone offset, milliseconds required)"
        )


def text_to_adf(text: str) -> dict:
    """Convert a plain text string to Atlassian Document Format (ADF)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def jira_request(
    method: str,
    url: str,
    access_token: str,
    context: ExecutionContext,
    params: dict = None,
    payload: dict = None,
    raw_body: str = None,
):
    """
    Make an authenticated HTTP request to the Jira API.
    Returns the response body.
    Raises on non-2xx responses.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if raw_body is not None:
        body = await context.fetch(url, method=method, params=params, data=raw_body, headers=headers)
    else:
        body = await context.fetch(url, method=method, params=params, json=payload, headers=headers)
    return body


# ---- Action Handlers ----


@jira.action("create_issue")
class CreateIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            summary = inputs["summary"]
            issue_type = inputs.get("issueType", "Task")

            fields: Dict[str, Any] = {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }

            description = inputs.get("description")
            if description:
                fields["description"] = text_to_adf(description)

            assignee_id = inputs.get("assigneeAccountId")
            if assignee_id:
                fields["assignee"] = {"accountId": assignee_id}

            priority = inputs.get("priority")
            if priority:
                fields["priority"] = {"name": priority}

            labels = inputs.get("labels")
            if labels:
                fields["labels"] = labels

            parent_key = inputs.get("parentKey")
            if parent_key:
                fields["parent"] = {"key": parent_key}

            custom_fields = inputs.get("customFields")
            if custom_fields and isinstance(custom_fields, dict):
                fields.update(custom_fields)

            payload = {"fields": fields}
            url = api_url(cloud_id, "/issue")
            body = await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "issueId": body.get("id") if isinstance(body, dict) else None,
                    "issueKey": body.get("key") if isinstance(body, dict) else None,
                    "issueUrl": body.get("self") if isinstance(body, dict) else None,
                    "message": "Issue created successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error creating issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_issue")
class GetIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            fields_param = inputs.get("fields")
            expand = inputs.get("expand")

            params: Dict[str, Any] = {}
            if fields_param:
                params["fields"] = fields_param
            if expand:
                params["expand"] = expand

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}")
            body = await jira_request("GET", url, access_token, context, params=params or None)

            fields_data = body.get("fields", {}) if isinstance(body, dict) else {}
            assignee = fields_data.get("assignee") or {}
            reporter = fields_data.get("reporter") or {}
            status = fields_data.get("status") or {}
            priority = fields_data.get("priority") or {}
            issue_type = fields_data.get("issuetype") or {}
            project = fields_data.get("project") or {}

            return ActionResult(
                data={
                    "result": True,
                    "issueId": body.get("id"),
                    "issueKey": body.get("key"),
                    "summary": fields_data.get("summary"),
                    "description": fields_data.get("description"),
                    "status": status.get("name"),
                    "statusCategory": (status.get("statusCategory") or {}).get("name"),
                    "priority": priority.get("name"),
                    "issueType": issue_type.get("name"),
                    "projectKey": project.get("key"),
                    "projectName": project.get("name"),
                    "assigneeAccountId": assignee.get("accountId"),
                    "assigneeDisplayName": assignee.get("displayName"),
                    "reporterAccountId": reporter.get("accountId"),
                    "reporterDisplayName": reporter.get("displayName"),
                    "created": fields_data.get("created"),
                    "updated": fields_data.get("updated"),
                    "dueDate": fields_data.get("duedate"),
                    "labels": fields_data.get("labels", []),
                    "components": [c.get("name") for c in (fields_data.get("components") or [])],
                    "fixVersions": [v.get("name") for v in (fields_data.get("fixVersions") or [])],
                    "subtasks": fields_data.get("subtasks", []),
                    "parent": fields_data.get("parent"),
                    "rawFields": fields_data,
                    "issueUrl": body.get("self"),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("update_issue")
class UpdateIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            fields: Dict[str, Any] = {}

            summary = inputs.get("summary")
            if summary:
                fields["summary"] = summary

            description = inputs.get("description")
            if description:
                fields["description"] = text_to_adf(description)

            assignee_id = inputs.get("assigneeAccountId")
            if assignee_id is not None:
                fields["assignee"] = {"accountId": assignee_id} if assignee_id else None

            priority = inputs.get("priority")
            if priority:
                fields["priority"] = {"name": priority}

            labels = inputs.get("labels")
            if labels is not None:
                fields["labels"] = labels

            due_date = inputs.get("dueDate")
            if due_date:
                fields["duedate"] = due_date

            fix_versions = inputs.get("fixVersions")
            if fix_versions is not None:
                fields["fixVersions"] = [{"name": v} for v in fix_versions]

            components = inputs.get("components")
            if components is not None:
                fields["components"] = [{"name": c} for c in components]

            custom_fields = inputs.get("customFields")
            if custom_fields and isinstance(custom_fields, dict):
                fields.update(custom_fields)

            if not fields:
                raise ValueError("At least one field to update must be provided")

            payload: Dict[str, Any] = {"fields": fields}
            notify_users = inputs.get("notifyUsers", True)
            params = {} if notify_users else {"notifyUsers": "false"}

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}")
            await jira_request("PUT", url, access_token, context, params=params or None, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "message": "Issue updated successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error updating issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("delete_issue")
class DeleteIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            delete_subtasks = inputs.get("deleteSubtasks", False)

            params = {"deleteSubtasks": "true" if delete_subtasks else "false"}
            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}")
            await jira_request("DELETE", url, access_token, context, params=params)

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "message": "Issue deleted successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error deleting issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("search_issues")
class SearchIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            jql = inputs["jql"]
            max_results = inputs.get("maxResults", 50)
            next_page_token = inputs.get("nextPageToken")
            fields = inputs.get(
                "fields",
                [
                    "summary",
                    "status",
                    "assignee",
                    "priority",
                    "issuetype",
                    "created",
                    "updated",
                ],
            )
            expand = inputs.get("expand")

            # /search/jql uses nextPageToken pagination — startAt is no longer supported
            fields_list = fields if isinstance(fields, list) else fields.split(",")

            payload: Dict[str, Any] = {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields_list,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token
            if expand:
                payload["expand"] = expand if isinstance(expand, list) else [expand]

            url = api_url(cloud_id, "/search/jql")
            body = await jira_request("POST", url, access_token, context, payload=payload)

            issues = []
            for issue in body.get("issues") or []:
                f = issue.get("fields") or {}
                status = f.get("status") or {}
                assignee = f.get("assignee") or {}
                priority = f.get("priority") or {}
                issue_type = f.get("issuetype") or {}
                issues.append(
                    {
                        "issueId": issue.get("id"),
                        "issueKey": issue.get("key"),
                        "summary": f.get("summary"),
                        "status": status.get("name"),
                        "priority": priority.get("name"),
                        "issueType": issue_type.get("name"),
                        "assigneeDisplayName": assignee.get("displayName"),
                        "assigneeAccountId": assignee.get("accountId"),
                        "created": f.get("created"),
                        "updated": f.get("updated"),
                        "rawFields": f,
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issues": issues,
                    "total": body.get("total", len(issues)),
                    "maxResults": body.get("maxResults", max_results),
                    "nextPageToken": body.get("nextPageToken"),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error searching issues: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_issue_transitions")
class GetIssueTransitionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/transitions")
            body = await jira_request("GET", url, access_token, context)

            transitions = []
            for t in body.get("transitions") or []:
                to_status = t.get("to") or {}
                transitions.append(
                    {
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "toStatusId": to_status.get("id"),
                        "toStatusName": to_status.get("name"),
                        "toStatusCategory": (to_status.get("statusCategory") or {}).get("name"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "transitions": transitions,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error getting transitions: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("transition_issue")
class TransitionIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            transition_id = inputs["transitionId"]

            payload: Dict[str, Any] = {"transition": {"id": str(transition_id)}}

            comment = inputs.get("comment")
            if comment:
                payload["update"] = {"comment": [{"add": {"body": text_to_adf(comment)}}]}

            resolution = inputs.get("resolution")
            if resolution:
                payload["fields"] = {"resolution": {"name": resolution}}

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/transitions")
            await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "transitionId": transition_id,
                    "message": "Issue transitioned successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error transitioning issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("assign_issue")
class AssignIssueAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            account_id = inputs.get("accountId")

            payload = {"accountId": account_id}
            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/assignee")
            await jira_request("PUT", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "accountId": account_id,
                    "message": "Issue assigned successfully" if account_id else "Issue unassigned successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error assigning issue: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("add_comment")
class AddCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            body_text = inputs["body"]
            visibility_type = inputs.get("visibilityType")
            visibility_value = inputs.get("visibilityValue")

            payload: Dict[str, Any] = {"body": text_to_adf(body_text)}

            if visibility_type and visibility_value:
                payload["visibility"] = {
                    "type": visibility_type,
                    "value": visibility_value,
                }

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/comment")
            response_body = await jira_request("POST", url, access_token, context, payload=payload)

            author = (response_body.get("author") or {}) if isinstance(response_body, dict) else {}

            return ActionResult(
                data={
                    "result": True,
                    "commentId": response_body.get("id") if isinstance(response_body, dict) else None,
                    "issueKey": issue_key,
                    "authorDisplayName": author.get("displayName"),
                    "authorAccountId": author.get("accountId"),
                    "created": response_body.get("created") if isinstance(response_body, dict) else None,
                    "message": "Comment added successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error adding comment: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_comments")
class GetCommentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            order_by = inputs.get("orderBy", "created")

            params = {
                "startAt": start_at,
                "maxResults": max_results,
                "orderBy": order_by,
            }

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/comment")
            body = await jira_request("GET", url, access_token, context, params=params)

            comments = []
            for c in body.get("comments") or []:
                author = c.get("author") or {}
                comments.append(
                    {
                        "commentId": c.get("id"),
                        "authorDisplayName": author.get("displayName"),
                        "authorAccountId": author.get("accountId"),
                        "body": c.get("body"),
                        "created": c.get("created"),
                        "updated": c.get("updated"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "comments": comments,
                    "total": body.get("total", len(comments)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving comments: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("update_comment")
class UpdateCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            comment_id = inputs["commentId"]
            body_text = inputs["body"]

            payload: Dict[str, Any] = {"body": text_to_adf(body_text)}

            visibility_type = inputs.get("visibilityType")
            visibility_value = inputs.get("visibilityValue")
            if visibility_type and visibility_value:
                payload["visibility"] = {
                    "type": visibility_type,
                    "value": visibility_value,
                }

            url = api_url(
                cloud_id,
                f"/issue/{safe_path(issue_key)}/comment/{safe_path(comment_id)}",
            )
            response_body = await jira_request("PUT", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "commentId": comment_id,
                    "issueKey": issue_key,
                    "updated": response_body.get("updated") if isinstance(response_body, dict) else None,
                    "message": "Comment updated successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error updating comment: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            comment_id = inputs["commentId"]

            url = api_url(
                cloud_id,
                f"/issue/{safe_path(issue_key)}/comment/{safe_path(comment_id)}",
            )
            await jira_request("DELETE", url, access_token, context)

            return ActionResult(
                data={
                    "result": True,
                    "commentId": comment_id,
                    "issueKey": issue_key,
                    "message": "Comment deleted successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error deleting comment: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("list_projects")
class ListProjectsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            project_type = inputs.get("projectType")
            query = inputs.get("query")
            order_by = inputs.get("orderBy", "name")

            params: Dict[str, Any] = {
                "startAt": start_at,
                "maxResults": max_results,
                "orderBy": order_by,
            }
            if project_type:
                params["typeKey"] = project_type
            if query:
                params["query"] = query

            url = api_url(cloud_id, "/project/search")
            body = await jira_request("GET", url, access_token, context, params=params)

            projects = []
            for p in body.get("values") or []:
                lead = p.get("lead") or {}
                projects.append(
                    {
                        "projectId": p.get("id"),
                        "projectKey": p.get("key"),
                        "name": p.get("name"),
                        "description": p.get("description"),
                        "projectType": p.get("projectTypeKey"),
                        "style": p.get("style"),
                        "leadDisplayName": lead.get("displayName"),
                        "leadAccountId": lead.get("accountId"),
                        "url": p.get("self"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "projects": projects,
                    "total": body.get("total", len(projects)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error listing projects: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_project")
class GetProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            expand = inputs.get("expand")

            params = {}
            if expand:
                params["expand"] = expand

            url = api_url(cloud_id, f"/project/{safe_path(project_key)}")
            body = await jira_request("GET", url, access_token, context, params=params or None)

            lead = (body.get("lead") or {}) if isinstance(body, dict) else {}

            return ActionResult(
                data={
                    "result": True,
                    "projectId": body.get("id"),
                    "projectKey": body.get("key"),
                    "name": body.get("name"),
                    "description": body.get("description"),
                    "projectType": body.get("projectTypeKey"),
                    "style": body.get("style"),
                    "leadDisplayName": lead.get("displayName"),
                    "leadAccountId": lead.get("accountId"),
                    "issueTypes": [
                        {"id": it.get("id"), "name": it.get("name")} for it in (body.get("issueTypes") or [])
                    ],
                    "components": [{"id": c.get("id"), "name": c.get("name")} for c in (body.get("components") or [])],
                    "versions": [
                        {
                            "id": v.get("id"),
                            "name": v.get("name"),
                            "released": v.get("released"),
                        }
                        for v in (body.get("versions") or [])
                    ],
                    "url": body.get("self"),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving project: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_project_components")
class GetProjectComponentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            url = api_url(cloud_id, f"/project/{safe_path(project_key)}/components")
            body = await jira_request("GET", url, access_token, context)

            components = []
            for c in body if isinstance(body, list) else []:
                lead = c.get("lead") or {}
                components.append(
                    {
                        "componentId": c.get("id"),
                        "name": c.get("name"),
                        "description": c.get("description"),
                        "leadDisplayName": lead.get("displayName"),
                        "leadAccountId": lead.get("accountId"),
                        "assigneeType": c.get("assigneeType"),
                        "url": c.get("self"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "projectKey": project_key,
                    "components": components,
                    "count": len(components),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving components: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_project_versions")
class GetProjectVersionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            order_by = inputs.get("orderBy", "sequence")

            params = {
                "startAt": start_at,
                "maxResults": max_results,
                "orderBy": order_by,
            }

            url = api_url(cloud_id, f"/project/{safe_path(project_key)}/version")
            body = await jira_request("GET", url, access_token, context, params=params)

            versions = []
            for v in body.get("values") or []:
                versions.append(
                    {
                        "versionId": v.get("id"),
                        "name": v.get("name"),
                        "description": v.get("description"),
                        "released": v.get("released"),
                        "archived": v.get("archived"),
                        "releaseDate": v.get("releaseDate"),
                        "startDate": v.get("startDate"),
                        "url": v.get("self"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "projectKey": project_key,
                    "versions": versions,
                    "total": body.get("total", len(versions)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving versions: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("create_project_version")
class CreateProjectVersionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            name = inputs["name"]

            payload: Dict[str, Any] = {"name": name, "project": project_key}

            description = inputs.get("description")
            if description:
                payload["description"] = description

            release_date = inputs.get("releaseDate")
            if release_date:
                payload["releaseDate"] = release_date

            start_date = inputs.get("startDate")
            if start_date:
                payload["startDate"] = start_date

            if inputs.get("released") is not None:
                payload["released"] = inputs["released"]

            url = api_url(cloud_id, "/version")
            body = await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "versionId": body.get("id") if isinstance(body, dict) else None,
                    "name": body.get("name") if isinstance(body, dict) else None,
                    "projectKey": project_key,
                    "message": "Version created successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error creating version: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            url = api_url(cloud_id, "/myself")
            body = await jira_request("GET", url, access_token, context)

            return ActionResult(
                data={
                    "result": True,
                    "accountId": body.get("accountId") if isinstance(body, dict) else None,
                    "displayName": body.get("displayName") if isinstance(body, dict) else None,
                    "emailAddress": body.get("emailAddress") if isinstance(body, dict) else None,
                    "active": body.get("active") if isinstance(body, dict) else None,
                    "locale": body.get("locale") if isinstance(body, dict) else None,
                    "timeZone": body.get("timeZone") if isinstance(body, dict) else None,
                    "avatarUrls": body.get("avatarUrls") if isinstance(body, dict) else None,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving current user: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_user")
class GetUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            account_id = inputs["accountId"]
            params = {"accountId": account_id}

            url = api_url(cloud_id, "/user")
            body = await jira_request("GET", url, access_token, context, params=params)

            return ActionResult(
                data={
                    "result": True,
                    "accountId": body.get("accountId") if isinstance(body, dict) else None,
                    "displayName": body.get("displayName") if isinstance(body, dict) else None,
                    "emailAddress": body.get("emailAddress") if isinstance(body, dict) else None,
                    "active": body.get("active") if isinstance(body, dict) else None,
                    "timeZone": body.get("timeZone") if isinstance(body, dict) else None,
                    "avatarUrls": body.get("avatarUrls") if isinstance(body, dict) else None,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving user: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("search_users")
class SearchUsersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            query = inputs["query"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)

            params = {"query": query, "startAt": start_at, "maxResults": max_results}

            url = api_url(cloud_id, "/user/search")
            body = await jira_request("GET", url, access_token, context, params=params)

            users = []
            for u in body if isinstance(body, list) else []:
                users.append(
                    {
                        "accountId": u.get("accountId"),
                        "displayName": u.get("displayName"),
                        "emailAddress": u.get("emailAddress"),
                        "active": u.get("active"),
                        "timeZone": u.get("timeZone"),
                    }
                )

            return ActionResult(
                data={"result": True, "users": users, "count": len(users)},
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error searching users: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("list_boards")
class ListBoardsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            board_type = inputs.get("type")
            project_key_filter = inputs.get("projectKeyOrId")
            name_filter = inputs.get("name")

            params: Dict[str, Any] = {"startAt": start_at, "maxResults": max_results}
            if board_type:
                params["type"] = board_type
            if project_key_filter:
                params["projectKeyOrId"] = project_key_filter
            if name_filter:
                params["name"] = name_filter

            url = agile_url(cloud_id, "/board")
            body = await jira_request("GET", url, access_token, context, params=params)

            boards = []
            for b in body.get("values") or []:
                location = b.get("location") or {}
                boards.append(
                    {
                        "boardId": b.get("id"),
                        "name": b.get("name"),
                        "type": b.get("type"),
                        "projectKey": location.get("projectKey"),
                        "projectName": location.get("projectName"),
                        "url": b.get("self"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "boards": boards,
                    "total": body.get("total", len(boards)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error listing boards: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_sprints")
class GetSprintsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            board_id = inputs["boardId"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            state = inputs.get("state")

            params: Dict[str, Any] = {"startAt": start_at, "maxResults": max_results}
            if state:
                params["state"] = state

            url = agile_url(cloud_id, f"/board/{safe_path(str(board_id))}/sprint")
            body = await jira_request("GET", url, access_token, context, params=params)

            sprints = []
            for s in body.get("values") or []:
                sprints.append(
                    {
                        "sprintId": s.get("id"),
                        "name": s.get("name"),
                        "state": s.get("state"),
                        "startDate": s.get("startDate"),
                        "endDate": s.get("endDate"),
                        "completeDate": s.get("completeDate"),
                        "goal": s.get("goal"),
                        "url": s.get("self"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "boardId": board_id,
                    "sprints": sprints,
                    "total": body.get("total", len(sprints)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving sprints: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_sprint_issues")
class GetSprintIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            sprint_id = inputs["sprintId"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            jql = inputs.get("jql")
            fields = inputs.get("fields", ["summary", "status", "assignee", "priority", "issuetype"])

            params: Dict[str, Any] = {
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ",".join(fields) if isinstance(fields, list) else fields,
            }
            if jql:
                params["jql"] = jql

            url = agile_url(cloud_id, f"/sprint/{safe_path(str(sprint_id))}/issue")
            body = await jira_request("GET", url, access_token, context, params=params)

            issues = []
            for issue in body.get("issues") or []:
                f = issue.get("fields") or {}
                status = f.get("status") or {}
                assignee = f.get("assignee") or {}
                priority = f.get("priority") or {}
                issue_type = f.get("issuetype") or {}
                issues.append(
                    {
                        "issueId": issue.get("id"),
                        "issueKey": issue.get("key"),
                        "summary": f.get("summary"),
                        "status": status.get("name"),
                        "priority": priority.get("name"),
                        "issueType": issue_type.get("name"),
                        "assigneeDisplayName": assignee.get("displayName"),
                        "assigneeAccountId": assignee.get("accountId"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "sprintId": sprint_id,
                    "issues": issues,
                    "total": body.get("total", len(issues)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving sprint issues: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("add_worklog")
class AddWorklogAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            time_spent = inputs["timeSpent"]

            # adjustEstimate and related fields MUST be query params, not body fields
            # Putting them in the body causes HTTP 400 "Unrecognized field"
            adjust_estimate = inputs.get("adjustEstimate", "auto")
            params: Dict[str, Any] = {"adjustEstimate": adjust_estimate}

            new_estimate = inputs.get("newEstimate")
            if new_estimate and adjust_estimate == "new":
                params["newEstimate"] = new_estimate

            reduce_by = inputs.get("reduceBy")
            if reduce_by and adjust_estimate == "manual":
                params["reduceBy"] = reduce_by

            # started must be in exact Jira format: "2021-01-17T12:34:00.000+0000"
            # Wrong format silently returns HTTP 500 with no useful error message
            started_raw = inputs.get("started")
            started = format_jira_datetime(started_raw)

            payload: Dict[str, Any] = {"timeSpent": time_spent, "started": started}

            comment = inputs.get("comment")
            if comment:
                payload["comment"] = text_to_adf(comment)

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/worklog")
            body = await jira_request("POST", url, access_token, context, params=params, payload=payload)

            author = (body.get("author") or {}) if isinstance(body, dict) else {}

            return ActionResult(
                data={
                    "result": True,
                    "worklogId": body.get("id") if isinstance(body, dict) else None,
                    "issueKey": issue_key,
                    "timeSpent": body.get("timeSpent") if isinstance(body, dict) else None,
                    "timeSpentSeconds": body.get("timeSpentSeconds") if isinstance(body, dict) else None,
                    "authorDisplayName": author.get("displayName"),
                    "authorAccountId": author.get("accountId"),
                    "started": body.get("started") if isinstance(body, dict) else None,
                    "message": "Worklog added successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error adding worklog: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_worklogs")
class GetWorklogsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)

            params = {"startAt": start_at, "maxResults": max_results}

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/worklog")
            body = await jira_request("GET", url, access_token, context, params=params)

            worklogs = []
            for w in body.get("worklogs") or []:
                author = w.get("author") or {}
                worklogs.append(
                    {
                        "worklogId": w.get("id"),
                        "authorDisplayName": author.get("displayName"),
                        "authorAccountId": author.get("accountId"),
                        "timeSpent": w.get("timeSpent"),
                        "timeSpentSeconds": w.get("timeSpentSeconds"),
                        "started": w.get("started"),
                        "created": w.get("created"),
                        "updated": w.get("updated"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "worklogs": worklogs,
                    "total": body.get("total", len(worklogs)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving worklogs: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("link_issues")
class LinkIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            link_type = inputs["linkType"]
            inward_issue_key = inputs["inwardIssueKey"]
            outward_issue_key = inputs["outwardIssueKey"]

            payload: Dict[str, Any] = {
                "type": {"name": link_type},
                "inwardIssue": {"key": inward_issue_key},
                "outwardIssue": {"key": outward_issue_key},
            }

            comment = inputs.get("comment")
            if comment:
                payload["comment"] = {"body": text_to_adf(comment)}

            url = api_url(cloud_id, "/issueLink")
            await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "linkType": link_type,
                    "inwardIssueKey": inward_issue_key,
                    "outwardIssueKey": outward_issue_key,
                    "message": "Issues linked successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error linking issues: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_issue_link_types")
class GetIssueLinkTypesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            url = api_url(cloud_id, "/issueLinkType")
            body = await jira_request("GET", url, access_token, context)

            link_types = []
            for lt in body.get("issueLinkTypes") or []:
                link_types.append(
                    {
                        "id": lt.get("id"),
                        "name": lt.get("name"),
                        "inward": lt.get("inward"),
                        "outward": lt.get("outward"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "linkTypes": link_types,
                    "count": len(link_types),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving link types: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("add_watcher")
class AddWatcherAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            account_id = inputs["accountId"]

            # Jira's add-watcher endpoint expects a raw JSON-encoded string as the body
            raw_body = json.dumps(account_id)
            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/watchers")
            await jira_request("POST", url, access_token, context, raw_body=raw_body)

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "accountId": account_id,
                    "message": "Watcher added successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error adding watcher: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_watchers")
class GetWatchersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/watchers")
            body = await jira_request("GET", url, access_token, context)

            watchers = []
            for w in body.get("watchers") or []:
                watchers.append(
                    {
                        "accountId": w.get("accountId"),
                        "displayName": w.get("displayName"),
                        "active": w.get("active"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "watchCount": body.get("watchCount", len(watchers)) if isinstance(body, dict) else len(watchers),
                    "isWatching": body.get("isWatching") if isinstance(body, dict) else None,
                    "watchers": watchers,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving watchers: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_issue_types")
class GetIssueTypesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs.get("projectKey")

            if project_key:
                url = api_url(cloud_id, f"/project/{safe_path(project_key)}/issuetypes")
            else:
                url = api_url(cloud_id, "/issuetype")

            body = await jira_request("GET", url, access_token, context)

            issue_types = [
                {
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "description": it.get("description"),
                    "subtask": it.get("subtask"),
                    "hierarchyLevel": it.get("hierarchyLevel"),
                }
                for it in (body if isinstance(body, list) else [])
            ]

            return ActionResult(
                data={
                    "result": True,
                    "issueTypes": issue_types,
                    "count": len(issue_types),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving issue types: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_priorities")
class GetPrioritiesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            url = api_url(cloud_id, "/priority")
            body = await jira_request("GET", url, access_token, context)

            priorities = []
            for p in body if isinstance(body, list) else []:
                priorities.append(
                    {
                        "priorityId": p.get("id"),
                        "name": p.get("name"),
                        "description": p.get("description"),
                        "statusColor": p.get("statusColor"),
                        "iconUrl": p.get("iconUrl"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "priorities": priorities,
                    "count": len(priorities),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving priorities: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_fields")
class GetFieldsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            url = api_url(cloud_id, "/field")
            body = await jira_request("GET", url, access_token, context)

            fields = []
            custom_only = inputs.get("customOnly", False)

            for f in body if isinstance(body, list) else []:
                is_custom = f.get("custom", False)
                if custom_only and not is_custom:
                    continue
                schema = f.get("schema") or {}
                fields.append(
                    {
                        "fieldId": f.get("id"),
                        "name": f.get("name"),
                        "custom": is_custom,
                        "orderable": f.get("orderable"),
                        "navigable": f.get("navigable"),
                        "searchable": f.get("searchable"),
                        "type": schema.get("type"),
                        "system": schema.get("system"),
                        "clauseNames": f.get("clauseNames", []),
                    }
                )

            return ActionResult(
                data={"result": True, "fields": fields, "count": len(fields)},
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving fields: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_issue_changelog")
class GetIssueChangelogAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_key = inputs["issueKey"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 100)

            params = {"startAt": start_at, "maxResults": max_results}

            url = api_url(cloud_id, f"/issue/{safe_path(issue_key)}/changelog")
            body = await jira_request("GET", url, access_token, context, params=params)

            changelog = []
            for entry in body.get("values") or []:
                author = entry.get("author") or {}
                items = []
                for item in entry.get("items") or []:
                    items.append(
                        {
                            "field": item.get("field"),
                            "fieldType": item.get("fieldtype"),
                            "from": item.get("from"),
                            "fromString": item.get("fromString"),
                            "to": item.get("to"),
                            "toString": item.get("toString"),
                        }
                    )
                changelog.append(
                    {
                        "id": entry.get("id"),
                        "authorDisplayName": author.get("displayName"),
                        "authorAccountId": author.get("accountId"),
                        "created": entry.get("created"),
                        "items": items,
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "issueKey": issue_key,
                    "changelog": changelog,
                    "total": body.get("total", len(changelog)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving changelog: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("bulk_create_issues")
class BulkCreateIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            issue_updates = inputs["issues"]
            if not isinstance(issue_updates, list) or len(issue_updates) == 0:
                raise ValueError("issues must be a non-empty list of issue definitions")
            if len(issue_updates) > 50:
                raise ValueError("Maximum 50 issues can be created in a single bulk request")

            issue_list = []
            for item in issue_updates:
                fields: Dict[str, Any] = {
                    "project": {"key": item["projectKey"]},
                    "summary": item["summary"],
                    "issuetype": {"name": item.get("issueType", "Task")},
                }
                if item.get("description"):
                    fields["description"] = text_to_adf(item["description"])
                if item.get("assigneeAccountId"):
                    fields["assignee"] = {"accountId": item["assigneeAccountId"]}
                if item.get("priority"):
                    fields["priority"] = {"name": item["priority"]}
                if item.get("labels"):
                    fields["labels"] = item["labels"]
                issue_list.append({"fields": fields})

            payload = {"issueUpdates": issue_list}
            url = api_url(cloud_id, "/issue/bulk")
            body = await jira_request("POST", url, access_token, context, payload=payload)

            created = []
            for issue in body.get("issues") or []:
                created.append({"issueId": issue.get("id"), "issueKey": issue.get("key")})

            errors = body.get("errors", []) if isinstance(body, dict) else []

            return ActionResult(
                data={
                    "result": True,
                    "created": created,
                    "createdCount": len(created),
                    "errors": errors,
                    "message": f"Created {len(created)} issues",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error bulk creating issues: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_board_issues")
class GetBoardIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            board_id = inputs["boardId"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            jql = inputs.get("jql")
            fields = inputs.get("fields", ["summary", "status", "assignee", "priority", "issuetype"])

            params: Dict[str, Any] = {
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ",".join(fields) if isinstance(fields, list) else fields,
            }
            if jql:
                params["jql"] = jql

            url = agile_url(cloud_id, f"/board/{safe_path(str(board_id))}/issue")
            body = await jira_request("GET", url, access_token, context, params=params)

            issues = []
            for issue in body.get("issues") or []:
                f = issue.get("fields") or {}
                status = f.get("status") or {}
                assignee = f.get("assignee") or {}
                priority = f.get("priority") or {}
                issue_type = f.get("issuetype") or {}
                issues.append(
                    {
                        "issueId": issue.get("id"),
                        "issueKey": issue.get("key"),
                        "summary": f.get("summary"),
                        "status": status.get("name"),
                        "priority": priority.get("name"),
                        "issueType": issue_type.get("name"),
                        "assigneeDisplayName": assignee.get("displayName"),
                        "assigneeAccountId": assignee.get("accountId"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "boardId": board_id,
                    "issues": issues,
                    "total": body.get("total", len(issues)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving board issues: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_backlog_issues")
class GetBacklogIssuesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            board_id = inputs["boardId"]
            start_at = inputs.get("startAt", 0)
            max_results = inputs.get("maxResults", 50)
            jql = inputs.get("jql")
            fields = inputs.get("fields", ["summary", "status", "assignee", "priority", "issuetype"])

            params: Dict[str, Any] = {
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ",".join(fields) if isinstance(fields, list) else fields,
            }
            if jql:
                params["jql"] = jql

            url = agile_url(cloud_id, f"/board/{safe_path(str(board_id))}/backlog")
            body = await jira_request("GET", url, access_token, context, params=params)

            issues = []
            for issue in body.get("issues") or []:
                f = issue.get("fields") or {}
                status = f.get("status") or {}
                assignee = f.get("assignee") or {}
                issues.append(
                    {
                        "issueId": issue.get("id"),
                        "issueKey": issue.get("key"),
                        "summary": f.get("summary"),
                        "status": status.get("name"),
                        "assigneeDisplayName": assignee.get("displayName"),
                        "assigneeAccountId": assignee.get("accountId"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "boardId": board_id,
                    "issues": issues,
                    "total": body.get("total", len(issues)),
                    "startAt": body.get("startAt", start_at),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving backlog: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("move_issues_to_sprint")
class MoveIssuesToSprintAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            sprint_id = inputs["sprintId"]
            issue_keys = inputs["issueKeys"]

            if not isinstance(issue_keys, list) or len(issue_keys) == 0:
                raise ValueError("issueKeys must be a non-empty list")

            payload = {"issues": issue_keys}
            url = agile_url(cloud_id, f"/sprint/{safe_path(str(sprint_id))}/issue")
            await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "sprintId": sprint_id,
                    "issueKeys": issue_keys,
                    "message": f"Moved {len(issue_keys)} issue(s) to sprint {sprint_id}",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error moving issues to sprint: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("create_sprint")
class CreateSprintAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            board_id = inputs["boardId"]
            name = inputs["name"]

            payload: Dict[str, Any] = {"name": name, "originBoardId": board_id}

            start_date = inputs.get("startDate")
            if start_date:
                payload["startDate"] = start_date

            end_date = inputs.get("endDate")
            if end_date:
                payload["endDate"] = end_date

            goal = inputs.get("goal")
            if goal:
                payload["goal"] = goal

            url = agile_url(cloud_id, "/sprint")
            body = await jira_request("POST", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "sprintId": body.get("id") if isinstance(body, dict) else None,
                    "name": body.get("name") if isinstance(body, dict) else None,
                    "state": body.get("state") if isinstance(body, dict) else None,
                    "boardId": board_id,
                    "message": "Sprint created successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error creating sprint: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("update_sprint")
class UpdateSprintAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            sprint_id = inputs["sprintId"]
            payload: Dict[str, Any] = {}

            name = inputs.get("name")
            if name:
                payload["name"] = name

            state = inputs.get("state")
            if state:
                payload["state"] = state

            start_date = inputs.get("startDate")
            if start_date:
                payload["startDate"] = start_date

            end_date = inputs.get("endDate")
            if end_date:
                payload["endDate"] = end_date

            goal = inputs.get("goal")
            if goal is not None:
                payload["goal"] = goal

            if not payload:
                raise ValueError("At least one field to update must be provided")

            url = agile_url(cloud_id, f"/sprint/{safe_path(str(sprint_id))}")
            body = await jira_request("PUT", url, access_token, context, payload=payload)

            return ActionResult(
                data={
                    "result": True,
                    "sprintId": sprint_id,
                    "name": body.get("name") if isinstance(body, dict) else None,
                    "state": body.get("state") if isinstance(body, dict) else None,
                    "message": "Sprint updated successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error updating sprint: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_project_roles")
class GetProjectRolesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            project_key = inputs["projectKey"]
            url = api_url(cloud_id, f"/project/{safe_path(project_key)}/role")
            body = await jira_request("GET", url, access_token, context)

            roles = []
            if isinstance(body, dict):
                for role_name, role_url in body.items():
                    role_id = role_url.rstrip("/").split("/")[-1] if role_url else None
                    roles.append({"name": role_name, "roleId": role_id, "url": role_url})

            return ActionResult(
                data={
                    "result": True,
                    "projectKey": project_key,
                    "roles": roles,
                    "count": len(roles),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving project roles: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_status_categories")
class GetStatusCategoriesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            url = api_url(cloud_id, "/statuscategory")
            body = await jira_request("GET", url, access_token, context)

            categories = []
            for sc in body if isinstance(body, list) else []:
                categories.append(
                    {
                        "id": sc.get("id"),
                        "key": sc.get("key"),
                        "name": sc.get("name"),
                        "colorName": sc.get("colorName"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "statusCategories": categories,
                    "count": len(categories),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving status categories: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("list_dashboards")
class ListDashboardsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            params = {
                "startAt": inputs.get("startAt", 0),
                "maxResults": min(int(inputs.get("maxResults", 50)), 100),
            }
            filter_val = inputs.get("filter")
            if filter_val:
                params["filter"] = filter_val

            url = api_url(cloud_id, "/dashboard")
            body = await jira_request("GET", url, access_token, context, params=params)

            dashboards = []
            for d in body.get("dashboards", []) if isinstance(body, dict) else []:
                dashboards.append(
                    {
                        "id": d.get("id"),
                        "name": d.get("name"),
                        "self": d.get("self"),
                        "view": d.get("view"),
                        "isFavourite": d.get("isFavourite"),
                        "owner": d.get("owner", {}).get("displayName") if isinstance(d.get("owner"), dict) else None,
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "dashboards": dashboards,
                    "total": body.get("total") if isinstance(body, dict) else None,
                    "startAt": body.get("startAt") if isinstance(body, dict) else None,
                    "count": len(dashboards),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error listing dashboards: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_dashboard")
class GetDashboardAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            dashboard_id = inputs["dashboardId"]
            url = api_url(cloud_id, f"/dashboard/{safe_path(str(dashboard_id))}")
            body = await jira_request("GET", url, access_token, context)

            return ActionResult(
                data={
                    "result": True,
                    "id": body.get("id"),
                    "name": body.get("name"),
                    "self": body.get("self"),
                    "view": body.get("view"),
                    "isFavourite": body.get("isFavourite"),
                    "owner": body.get("owner", {}).get("displayName") if isinstance(body.get("owner"), dict) else None,
                    "popularity": body.get("popularity"),
                    "rank": body.get("rank"),
                    "sharePermissions": body.get("sharePermissions", []),
                    "editPermissions": body.get("editPermissions", []),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving dashboard: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("search_dashboards")
class SearchDashboardsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            params = {
                "startAt": inputs.get("startAt", 0),
                "maxResults": min(int(inputs.get("maxResults", 50)), 100),
            }
            query = inputs.get("dashboardName")
            if query:
                params["dashboardName"] = query
            account_id = inputs.get("accountId")
            if account_id:
                params["accountId"] = account_id
            owner = inputs.get("owner")
            if owner:
                params["owner"] = owner
            group_id = inputs.get("groupId")
            if group_id:
                params["groupId"] = group_id
            order_by = inputs.get("orderBy")
            if order_by:
                params["orderBy"] = order_by

            url = api_url(cloud_id, "/dashboard/search")
            body = await jira_request("GET", url, access_token, context, params=params)

            dashboards = []
            for d in body.get("values", []) if isinstance(body, dict) else []:
                dashboards.append(
                    {
                        "id": d.get("id"),
                        "name": d.get("name"),
                        "self": d.get("self"),
                        "view": d.get("view"),
                        "isFavourite": d.get("isFavourite"),
                        "owner": d.get("owner", {}).get("displayName") if isinstance(d.get("owner"), dict) else None,
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "dashboards": dashboards,
                    "total": body.get("total") if isinstance(body, dict) else None,
                    "startAt": body.get("startAt") if isinstance(body, dict) else None,
                    "count": len(dashboards),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error searching dashboards: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )


@jira.action("get_dashboard_gadgets")
class GetDashboardGadgetsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            access_token = get_access_token(context)
            cloud_id = await get_cloud_id(access_token, context)

            dashboard_id = inputs["dashboardId"]
            url = api_url(cloud_id, f"/dashboard/{safe_path(str(dashboard_id))}/gadget")
            body = await jira_request("GET", url, access_token, context)

            gadgets = []
            for g in body.get("gadgets", []) if isinstance(body, dict) else []:
                gadgets.append(
                    {
                        "id": g.get("id"),
                        "moduleKey": g.get("moduleKey"),
                        "uri": g.get("uri"),
                        "title": g.get("title"),
                        "color": g.get("color"),
                        "position": g.get("position"),
                    }
                )

            return ActionResult(
                data={
                    "result": True,
                    "dashboardId": dashboard_id,
                    "gadgets": gadgets,
                    "count": len(gadgets),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "message": f"Error retrieving dashboard gadgets: {str(e)}",
                    "error": str(e),
                },
                cost_usd=None,
            )

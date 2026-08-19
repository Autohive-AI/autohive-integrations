"""
GitHub integration - Issue actions - issues, issue comments, and the
organization-level issue types and issue fields that issues can be tagged with.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("list_issues")
class ListIssues(ActionHandler):
    """List issues for a repository"""

    @handle_github_errors("list_issues")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issues = await GitHubAPI.get_issues(
            context,
            inputs["owner"],
            inputs["repo"],
            state=inputs.get("state", "all"),
            sort=inputs.get("sort", "created"),
            direction=inputs.get("direction", "desc"),
            since=inputs.get("since"),
            labels=inputs.get("labels"),
        )

        return ActionResult(
            data=[
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "description": issue["body"],
                    "state": issue["state"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "closed_at": issue["closed_at"],
                    "author": {
                        "login": issue["user"]["login"],
                        "avatar_url": issue["user"]["avatar_url"],
                    },
                    "assignees": [{"login": assignee["login"]} for assignee in issue.get("assignees", [])],
                    "labels": [{"name": label["name"], "color": label["color"]} for label in issue.get("labels", [])],
                    "url": issue["html_url"],
                }
                for issue in issues
            ],
            cost_usd=0.0,
        )


@github.action("get_issue")
class GetIssue(ActionHandler):
    """Get a specific issue"""

    @handle_github_errors("get_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.get_issue(context, inputs["owner"], inputs["repo"], inputs["issue_number"])

        return ActionResult(
            data={
                "number": issue["number"],
                "title": issue["title"],
                "description": issue["body"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "closed_at": issue["closed_at"],
                "author": {
                    "login": issue["user"]["login"],
                    "avatar_url": issue["user"]["avatar_url"],
                },
                "assignees": [{"login": assignee["login"]} for assignee in issue.get("assignees", [])],
                "labels": [{"name": label["name"], "color": label["color"]} for label in issue.get("labels", [])],
                "comments": issue.get("comments", 0),
                "url": issue["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("create_issue")
class CreateIssue(ActionHandler):
    """Create a new issue"""

    @handle_github_errors("create_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.create_issue(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["title"],
            body=inputs.get("body"),
            assignees=inputs.get("assignees"),
            labels=inputs.get("labels"),
            milestone=inputs.get("milestone"),
        )

        return ActionResult(
            data={
                "number": issue["number"],
                "title": issue["title"],
                "description": issue["body"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "author": {
                    "login": issue["user"]["login"],
                    "avatar_url": issue["user"]["avatar_url"],
                },
                "assignees": [{"login": assignee["login"]} for assignee in issue.get("assignees", [])],
                "labels": [{"name": label["name"], "color": label["color"]} for label in issue.get("labels", [])],
                "url": issue["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("update_issue")
class UpdateIssue(ActionHandler):
    """Update an existing issue"""

    @handle_github_errors("update_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.update_issue(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            title=inputs.get("title"),
            body=inputs.get("body"),
            state=inputs.get("state"),
            assignees=inputs.get("assignees"),
            labels=inputs.get("labels"),
            milestone=inputs.get("milestone"),
        )

        return ActionResult(
            data={
                "number": issue["number"],
                "title": issue["title"],
                "description": issue["body"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "closed_at": issue["closed_at"],
                "author": {
                    "login": issue["user"]["login"],
                    "avatar_url": issue["user"]["avatar_url"],
                },
                "assignees": [{"login": assignee["login"]} for assignee in issue.get("assignees", [])],
                "labels": [{"name": label["name"], "color": label["color"]} for label in issue.get("labels", [])],
                "url": issue["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("create_issue_comment")
class CreateIssueComment(ActionHandler):
    """Create a comment on an issue"""

    @handle_github_errors("create_issue_comment")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comment = await GitHubAPI.create_issue_comment(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            inputs["body"],
        )

        return ActionResult(
            data={
                "id": comment["id"],
                "body": comment["body"],
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"],
                "author": {
                    "login": comment["user"]["login"],
                    "avatar_url": comment["user"]["avatar_url"],
                },
                "url": comment["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("get_issue_comments")
class GetIssueComments(ActionHandler):
    """Get comments for an issue"""

    @handle_github_errors("get_issue_comments")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comments = await GitHubAPI.get_issue_comments(context, inputs["owner"], inputs["repo"], inputs["issue_number"])

        return ActionResult(
            data=[
                {
                    "id": comment["id"],
                    "body": comment["body"],
                    "created_at": comment["created_at"],
                    "updated_at": comment["updated_at"],
                    "author": {
                        "login": comment["user"]["login"],
                        "avatar_url": comment["user"]["avatar_url"],
                    },
                    "url": comment["html_url"],
                }
                for comment in comments
            ],
            cost_usd=0.0,
        )


# =============================================================================
# ORGANIZATION ISSUE TYPES AND ISSUE FIELDS
# =============================================================================
#
# Issue types and issue fields are configured once per organization and then
# applied to individual issues. Both endpoints live under /orgs/{org}/ rather
# than under a repository, and both need the `read:org` scope (fine-grained
# tokens need the organization "Issue Types"/"Issue Fields" read permission).
#
# Reference: https://docs.github.com/en/rest/orgs/issue-types
#            https://docs.github.com/en/rest/orgs/issue-fields


async def _list_org_issue_types(context: ExecutionContext, org: str) -> List[Dict[str, Any]]:
    """GET /orgs/{org}/issue-types — the issue types defined on an organization."""
    url = f"{GitHubAPI.BASE_URL}/orgs/{org}/issue-types"
    return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data or []


async def _list_org_issue_fields(context: ExecutionContext, org: str) -> List[Dict[str, Any]]:
    """GET /orgs/{org}/issue-fields — the custom issue fields defined on an organization."""
    url = f"{GitHubAPI.BASE_URL}/orgs/{org}/issue-fields"
    return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data or []


@github.action("list_issue_types")
class ListIssueTypes(ActionHandler):
    """List the issue types configured for an organization"""

    @handle_github_errors("list_issue_types")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue_types = await _list_org_issue_types(context, inputs["org"])

        return ActionResult(
            data=[
                {
                    "id": issue_type.get("id"),
                    "node_id": issue_type.get("node_id"),
                    "name": issue_type.get("name"),
                    "description": issue_type.get("description"),
                    "color": issue_type.get("color"),
                    "is_enabled": issue_type.get("is_enabled"),
                    "created_at": issue_type.get("created_at"),
                    "updated_at": issue_type.get("updated_at"),
                }
                for issue_type in issue_types
            ],
            cost_usd=0.0,
        )


@github.action("list_issue_fields")
class ListIssueFields(ActionHandler):
    """List the custom issue fields configured for an organization"""

    @handle_github_errors("list_issue_fields")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue_fields = await _list_org_issue_fields(context, inputs["org"])

        return ActionResult(
            data=[
                {
                    "id": issue_field.get("id"),
                    "node_id": issue_field.get("node_id"),
                    "name": issue_field.get("name"),
                    "description": issue_field.get("description"),
                    "data_type": issue_field.get("data_type"),
                    "visibility": issue_field.get("visibility"),
                    "options": (
                        [
                            {
                                "id": option.get("id"),
                                "name": option.get("name"),
                                "description": option.get("description"),
                                "color": option.get("color"),
                                "priority": option.get("priority"),
                            }
                            for option in issue_field["options"]
                        ]
                        if issue_field.get("options")
                        else None
                    ),
                    "created_at": issue_field.get("created_at"),
                    "updated_at": issue_field.get("updated_at"),
                }
                for issue_field in issue_fields
            ],
            cost_usd=0.0,
        )

"""
GitHub integration - Sub-issue actions - issue hierarchy management.

Two identifiers are in play and they are not interchangeable:

- The **parent** is addressed by its repository issue ``number`` (the value in
  the issue's URL), which goes in the path.
- The **child** is addressed by its issue ``id`` — GitHub's global database id,
  returned as ``id`` on any issue payload — which goes in the request body as
  ``sub_issue_id``. Passing an issue number here silently targets the wrong
  issue or 404s.

Note also that the remove endpoint uses a **singular** ``sub_issue`` path
segment while list/add use the plural ``sub_issues``, and that it is a DELETE
that carries a JSON body.

All three write endpoints respond with the parent issue after the change.

Reference: https://docs.github.com/en/rest/issues/sub-issues
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional

from github import github
from helpers import GitHubAPI, handle_github_errors


# =============================================================================
# API HELPERS
# =============================================================================


def _sub_issues_url(owner: str, repo: str, issue_number: int) -> str:
    """Collection URL for a parent issue's sub-issues."""
    return f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/sub_issues"


def _shape_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a GitHub issue payload into the integration's issue output.

    ``user`` can be null on issues authored by since-deleted accounts, and
    ``sub_issues_summary`` is only present on issues that participate in a
    hierarchy — both are treated as optional.
    """
    author = issue.get("user")
    summary = issue.get("sub_issues_summary")

    return {
        "id": issue.get("id"),
        "number": issue.get("number"),
        "title": issue.get("title"),
        "description": issue.get("body"),
        "state": issue.get("state"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "author": (
            {
                "login": author.get("login"),
                "avatar_url": author.get("avatar_url"),
            }
            if author
            else None
        ),
        "assignees": [{"login": assignee.get("login")} for assignee in issue.get("assignees") or []],
        "labels": [{"name": label.get("name"), "color": label.get("color")} for label in issue.get("labels") or []],
        "sub_issues_summary": (
            {
                "total": summary.get("total"),
                "completed": summary.get("completed"),
                "percent_completed": summary.get("percent_completed"),
            }
            if summary
            else None
        ),
        "url": issue.get("html_url"),
    }


async def _fetch_sub_issues(
    context: ExecutionContext, owner: str, repo: str, issue_number: int, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """GET /repos/{owner}/{repo}/issues/{issue_number}/sub_issues"""
    return await GitHubAPI.paginated_fetch(context, _sub_issues_url(owner, repo, issue_number), limit=limit)


async def _add_sub_issue(
    context: ExecutionContext,
    owner: str,
    repo: str,
    issue_number: int,
    sub_issue_id: int,
    replace_parent: Optional[bool] = None,
) -> Dict[str, Any]:
    """POST /repos/{owner}/{repo}/issues/{issue_number}/sub_issues

    ``sub_issue_id`` is the child issue's id, and the child must live under the
    same repository owner as the parent.
    """
    data: Dict[str, Any] = {"sub_issue_id": sub_issue_id}
    if replace_parent is not None:
        data["replace_parent"] = replace_parent

    url = _sub_issues_url(owner, repo, issue_number)
    return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data


async def _remove_sub_issue(
    context: ExecutionContext, owner: str, repo: str, issue_number: int, sub_issue_id: int
) -> Dict[str, Any]:
    """DELETE /repos/{owner}/{repo}/issues/{issue_number}/sub_issue

    The path segment is singular here, unlike the list and add endpoints.
    """
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/sub_issue"
    data: Dict[str, Any] = {"sub_issue_id": sub_issue_id}
    return (await context.fetch(url, method="DELETE", json=data, headers=GitHubAPI.get_headers(context))).data


async def _reprioritize_sub_issue(
    context: ExecutionContext,
    owner: str,
    repo: str,
    issue_number: int,
    sub_issue_id: int,
    after_id: Optional[int] = None,
    before_id: Optional[int] = None,
) -> Dict[str, Any]:
    """PATCH /repos/{owner}/{repo}/issues/{issue_number}/sub_issues/priority

    Every id here is an issue id, not an issue number. GitHub accepts exactly
    one of ``after_id`` / ``before_id``.
    """
    data: Dict[str, Any] = {"sub_issue_id": sub_issue_id}
    if after_id is not None:
        data["after_id"] = after_id
    if before_id is not None:
        data["before_id"] = before_id

    url = f"{_sub_issues_url(owner, repo, issue_number)}/priority"
    return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("list_sub_issues")
class ListSubIssues(ActionHandler):
    """List the sub-issues of a parent issue"""

    @handle_github_errors("list_sub_issues")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        sub_issues = await _fetch_sub_issues(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            limit=inputs.get("limit"),
        )

        return ActionResult(data=[_shape_issue(sub_issue) for sub_issue in sub_issues], cost_usd=0.0)


@github.action("add_sub_issue")
class AddSubIssue(ActionHandler):
    """Add an existing issue as a sub-issue of a parent issue"""

    @handle_github_errors("add_sub_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        parent = await _add_sub_issue(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            inputs["sub_issue_id"],
            replace_parent=inputs.get("replace_parent"),
        )

        return ActionResult(
            data={
                "added": True,
                "sub_issue_id": inputs["sub_issue_id"],
                "parent": _shape_issue(parent),
            },
            cost_usd=0.0,
        )


@github.action("remove_sub_issue")
class RemoveSubIssue(ActionHandler):
    """Remove a sub-issue from its parent issue"""

    @handle_github_errors("remove_sub_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        parent = await _remove_sub_issue(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            inputs["sub_issue_id"],
        )

        return ActionResult(
            data={
                "removed": True,
                "sub_issue_id": inputs["sub_issue_id"],
                "parent": _shape_issue(parent),
            },
            cost_usd=0.0,
        )


@github.action("reprioritize_sub_issue")
class ReprioritizeSubIssue(ActionHandler):
    """Move a sub-issue to a different position in its parent's list"""

    @handle_github_errors("reprioritize_sub_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        after_id = inputs.get("after_id")
        before_id = inputs.get("before_id")
        if (after_id is None) == (before_id is None):
            raise ValueError(
                "Provide exactly one of 'after_id' or 'before_id' (both are sub-issue ids) "
                "to say where the sub-issue should sit in the parent's list."
            )

        parent = await _reprioritize_sub_issue(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            inputs["sub_issue_id"],
            after_id=after_id,
            before_id=before_id,
        )

        return ActionResult(
            data={
                "reprioritized": True,
                "sub_issue_id": inputs["sub_issue_id"],
                "parent": _shape_issue(parent),
            },
            cost_usd=0.0,
        )

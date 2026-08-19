"""
GitHub integration - Label actions - repository and issue label management.

Label names are free text and routinely contain spaces, slashes and colons
("good first issue", "area/api", "type: bug"), so every label name that goes
into a URL path is percent-encoded with ``safe=""`` — the same treatment
``GitHubAPI.get_release_by_tag`` gives tag names.

Reference: https://docs.github.com/en/rest/issues/labels
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from github import github
from helpers import GitHubAPI, handle_github_errors


# =============================================================================
# API HELPERS
# =============================================================================


def _labels_url(owner: str, repo: str) -> str:
    """Collection URL for a repository's labels."""
    return f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/labels"


def _label_url(owner: str, repo: str, name: str) -> str:
    """URL for a single label, percent-encoding names containing spaces or '/'."""
    return f"{_labels_url(owner, repo)}/{quote(name, safe='')}"


def _normalize_color(color: Optional[str]) -> Optional[str]:
    """Strip a leading '#' — GitHub rejects colors that include it."""
    return color.lstrip("#") if color else color


def _shape_label(label: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a GitHub label payload into the integration's label output."""
    return {
        "id": label.get("id"),
        "node_id": label.get("node_id"),
        "name": label.get("name"),
        "color": label.get("color"),
        "description": label.get("description"),
        "default": label.get("default", False),
        "url": label.get("url"),
    }


async def _list_repo_labels(
    context: ExecutionContext, owner: str, repo: str, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """GET /repos/{owner}/{repo}/labels — every label defined on a repository."""
    return await GitHubAPI.paginated_fetch(context, _labels_url(owner, repo), limit=limit)


async def _list_issue_labels(
    context: ExecutionContext, owner: str, repo: str, issue_number: int, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """GET /repos/{owner}/{repo}/issues/{issue_number}/labels — labels applied to one issue."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    return await GitHubAPI.paginated_fetch(context, url, limit=limit)


async def _get_label(context: ExecutionContext, owner: str, repo: str, name: str) -> Dict[str, Any]:
    """GET /repos/{owner}/{repo}/labels/{name}"""
    url = _label_url(owner, repo, name)
    return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data


async def _create_label(
    context: ExecutionContext,
    owner: str,
    repo: str,
    name: str,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """POST /repos/{owner}/{repo}/labels"""
    data: Dict[str, Any] = {"name": name}
    if color:
        data["color"] = _normalize_color(color)
    if description is not None:
        data["description"] = description

    url = _labels_url(owner, repo)
    return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data


async def _update_label(
    context: ExecutionContext,
    owner: str,
    repo: str,
    name: str,
    new_name: Optional[str] = None,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """PATCH /repos/{owner}/{repo}/labels/{name} — ``new_name`` renames the label."""
    data: Dict[str, Any] = {}
    if new_name:
        data["new_name"] = new_name
    if color:
        data["color"] = _normalize_color(color)
    if description is not None:
        data["description"] = description

    url = _label_url(owner, repo, name)
    return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data


async def _delete_label(context: ExecutionContext, owner: str, repo: str, name: str) -> None:
    """DELETE /repos/{owner}/{repo}/labels/{name} — returns 204 with no body."""
    url = _label_url(owner, repo, name)
    await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("list_labels")
class ListLabels(ActionHandler):
    """List all labels defined in a repository"""

    @handle_github_errors("list_labels")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        labels = await _list_repo_labels(context, inputs["owner"], inputs["repo"], limit=inputs.get("limit"))

        return ActionResult(data=[_shape_label(label) for label in labels], cost_usd=0.0)


@github.action("list_issue_labels")
class ListIssueLabels(ActionHandler):
    """List the labels currently applied to an issue"""

    @handle_github_errors("list_issue_labels")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        labels = await _list_issue_labels(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["issue_number"],
            limit=inputs.get("limit"),
        )

        return ActionResult(data=[_shape_label(label) for label in labels], cost_usd=0.0)


@github.action("get_label")
class GetLabel(ActionHandler):
    """Get a single label by name"""

    @handle_github_errors("get_label")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        label = await _get_label(context, inputs["owner"], inputs["repo"], inputs["name"])

        return ActionResult(data=_shape_label(label), cost_usd=0.0)


@github.action("create_label")
class CreateLabel(ActionHandler):
    """Create a new label in a repository"""

    @handle_github_errors("create_label")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        label = await _create_label(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["name"],
            color=inputs.get("color"),
            description=inputs.get("description"),
        )

        return ActionResult(data=_shape_label(label), cost_usd=0.0)


@github.action("update_label")
class UpdateLabel(ActionHandler):
    """Update a label's name, color or description"""

    @handle_github_errors("update_label")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        label = await _update_label(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["name"],
            new_name=inputs.get("new_name"),
            color=inputs.get("color"),
            description=inputs.get("description"),
        )

        return ActionResult(data=_shape_label(label), cost_usd=0.0)


@github.action("delete_label")
class DeleteLabel(ActionHandler):
    """Delete a label from a repository"""

    @handle_github_errors("delete_label")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _delete_label(context, inputs["owner"], inputs["repo"], inputs["name"])

        return ActionResult(data={"deleted": True, "name": inputs["name"]}, cost_usd=0.0)

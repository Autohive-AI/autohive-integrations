"""
GitHub integration - Gist actions.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional
from datetime import timezone

from github import github
from helpers import GitHubAPI, handle_github_errors, _parse_iso_utc


@github.action("create_gist")
class CreateGist(ActionHandler):
    """Create a new gist"""

    @handle_github_errors("create_gist")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        gist = await GitHubAPI.create_gist(
            context,
            inputs.get("description", ""),
            inputs["files"],
            public=inputs.get("public", True),
        )

        return ActionResult(
            data={
                "id": gist["id"],
                "description": gist["description"],
                "public": gist["public"],
                "files": {name: {"size": file["size"], "type": file["type"]} for name, file in gist["files"].items()},
                "created_at": gist["created_at"],
                "updated_at": gist["updated_at"],
                "url": gist["html_url"],
            },
            cost_usd=0.0,
        )


# =============================================================================
# GIST READ AND UPDATE
# =============================================================================
#
# Truncation (https://docs.github.com/en/rest/gists/gists#truncation):
#   * GET /gists/{gist_id} embeds up to 1 MB of ``content`` per file. When a file
#     was cut short its own ``truncated`` flag is true and the full text has to be
#     fetched from ``raw_url`` — or, past 10 MB, cloned from ``git_pull_url``.
#   * The gist's top-level ``truncated`` flag means something different: the gist
#     holds more than 300 files and only the first 300 are listed.
#   * List responses (GET /gists, GET /users/{username}/gists) carry no file
#     ``content`` at all — only per-file metadata. So ``list_gists`` returns
#     metadata and only ``get_gist`` returns content.
#
# All of these need the `gist` scope; secret gists of other users stay invisible.
#
# Reference: https://docs.github.com/en/rest/gists/gists


def _gist_file_metadata(gist_file: Dict[str, Any]) -> Dict[str, Any]:
    """Shape one gist file without its content."""
    return {
        "filename": gist_file.get("filename"),
        "type": gist_file.get("type"),
        "language": gist_file.get("language"),
        "size": gist_file.get("size"),
        "raw_url": gist_file.get("raw_url"),
        "truncated": gist_file.get("truncated"),
    }


def _gist_file_with_content(gist_file: Dict[str, Any]) -> Dict[str, Any]:
    """Shape one gist file including the content GitHub inlined for it."""
    return {
        **_gist_file_metadata(gist_file),
        "content": gist_file.get("content"),
        "encoding": gist_file.get("encoding"),
    }


def _gist_summary(gist: Dict[str, Any], *, include_content: bool) -> Dict[str, Any]:
    """Shape a gist payload, with or without inlined file content."""
    owner = gist.get("owner")
    shape_file = _gist_file_with_content if include_content else _gist_file_metadata

    return {
        "id": gist.get("id"),
        "description": gist.get("description"),
        "public": gist.get("public"),
        "owner": (
            {
                "login": owner.get("login"),
                "avatar_url": owner.get("avatar_url"),
                "url": owner.get("html_url"),
            }
            if owner
            else None
        ),
        "files": {name: shape_file(gist_file) for name, gist_file in (gist.get("files") or {}).items() if gist_file},
        # True when the gist has more than 300 files and only the first 300 are listed.
        "truncated": gist.get("truncated"),
        "comments": gist.get("comments"),
        "created_at": gist.get("created_at"),
        "updated_at": gist.get("updated_at"),
        "git_pull_url": gist.get("git_pull_url"),
        "url": gist.get("html_url"),
    }


async def _list_gists(
    context: ExecutionContext,
    username: Optional[str] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """GET /gists (authenticated user) or GET /users/{username}/gists."""
    normalised_since = None
    if since is not None:
        since_dt = _parse_iso_utc(since)
        if since_dt is None:
            raise ValueError(
                f"'since' must be an ISO 8601 date or timestamp (e.g. 2024-01-31T00:00:00Z), got '{since}'."
            )
        normalised_since = since_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return await GitHubAPI.list_gists(context, username=username, since=normalised_since, limit=limit)


def _build_gist_update_payload(
    description: Optional[str],
    files: Optional[Dict[str, Any]],
    delete_files: Optional[List[str]],
) -> Dict[str, Any]:
    """Turn the action inputs into a PATCH /gists/{gist_id} body.

    GitHub's ``files`` object is keyed by each file's *current* name, and its
    semantics are unforgiving: a value of ``null`` deletes the file, and so does
    an object that contains neither ``content`` nor ``filename``. Rather than
    letting a malformed entry silently destroy a file, deletion is expressed only
    through the separate ``delete_files`` list, and anything ambiguous raises.
    """
    payload: Dict[str, Any] = {}

    if description is not None:
        payload["description"] = description

    file_changes: Dict[str, Any] = {}
    for filename, change in (files or {}).items():
        if not isinstance(change, dict):
            raise ValueError(
                f"files['{filename}'] must be an object with 'content' and/or 'filename'. "
                "To delete a file, list its name in 'delete_files' instead."
            )

        # Whitelist the keys GitHub acts on, so a typo can't turn into a deletion.
        update = {key: change[key] for key in ("content", "filename") if change.get(key) is not None}
        if not update:
            raise ValueError(
                f"files['{filename}'] sets neither 'content' nor 'filename'. GitHub deletes a file given "
                "such an entry — list the name in 'delete_files' if that is what you meant."
            )
        file_changes[filename] = update

    for filename in delete_files or []:
        if filename in file_changes:
            raise ValueError(f"'{filename}' appears in both 'files' and 'delete_files' — pick one.")
        file_changes[filename] = None

    if file_changes:
        payload["files"] = file_changes

    if not payload:
        raise ValueError("Nothing to update: supply at least one of 'description', 'files' or 'delete_files'.")

    return payload


async def _update_gist(context: ExecutionContext, gist_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """PATCH /gists/{gist_id} — update a gist's description and/or its files."""
    url = f"{GitHubAPI.BASE_URL}/gists/{gist_id}"
    return (await context.fetch(url, method="PATCH", json=payload, headers=GitHubAPI.get_headers(context))).data


@github.action("get_gist")
class GetGist(ActionHandler):
    """Get a single gist, including the content of each of its files"""

    @handle_github_errors("get_gist")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        gist = await GitHubAPI.get_gist(context, inputs["gist_id"])

        return ActionResult(data=_gist_summary(gist, include_content=True), cost_usd=0.0)


@github.action("list_gists")
class ListGists(ActionHandler):
    """List a user's public gists, or the authenticated user's gists"""

    @handle_github_errors("list_gists")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        gists = await _list_gists(
            context,
            username=inputs.get("username"),
            since=inputs.get("since"),
            limit=inputs.get("limit"),
        )

        return ActionResult(
            data=[_gist_summary(gist, include_content=False) for gist in gists],
            cost_usd=0.0,
        )


@github.action("update_gist")
class UpdateGist(ActionHandler):
    """Update a gist's description, or edit, rename and delete its files"""

    @handle_github_errors("update_gist")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        payload = _build_gist_update_payload(
            inputs.get("description"),
            inputs.get("files"),
            inputs.get("delete_files"),
        )
        gist = await _update_gist(context, inputs["gist_id"], payload)

        return ActionResult(data=_gist_summary(gist, include_content=False), cost_usd=0.0)

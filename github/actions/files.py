"""
GitHub integration - File actions - read, create, update, and delete repository files.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote
import base64

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("get_file_content")
class GetFileContent(ActionHandler):
    """Get file content from repository"""

    @handle_github_errors("get_file_content")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        file_data = await GitHubAPI.get_file_content(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["path"],
            ref=inputs.get("ref"),
        )

        return ActionResult(
            data={
                "type": file_data["type"],
                "content": file_data["content"],
                "sha": file_data["sha"],
                "size": file_data["size"],
                "name": file_data["name"],
                "path": file_data["path"],
                "entries": file_data["entries"],
            },
            cost_usd=0.0,
        )


@github.action("create_file")
class CreateFile(ActionHandler):
    """Create a new file in repository"""

    @handle_github_errors("create_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.create_file(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["path"],
            inputs["message"],
            inputs["content"],
            branch=inputs.get("branch"),
        )

        return ActionResult(
            data={
                "content": {
                    "name": result["content"]["name"],
                    "path": result["content"]["path"],
                    "sha": result["content"]["sha"],
                    "size": result["content"]["size"],
                },
                "commit": {
                    "sha": result["commit"]["sha"],
                    "message": result["commit"]["message"],
                },
            },
            cost_usd=0.0,
        )


@github.action("update_file")
class UpdateFile(ActionHandler):
    """Update an existing file in repository"""

    @handle_github_errors("update_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.update_file(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["path"],
            inputs["message"],
            inputs["content"],
            inputs["sha"],
            branch=inputs.get("branch"),
        )

        return ActionResult(
            data={
                "content": {
                    "name": result["content"]["name"],
                    "path": result["content"]["path"],
                    "sha": result["content"]["sha"],
                    "size": result["content"]["size"],
                },
                "commit": {
                    "sha": result["commit"]["sha"],
                    "message": result["commit"]["message"],
                },
            },
            cost_usd=0.0,
        )


@github.action("delete_file")
class DeleteFile(ActionHandler):
    """Delete a file from repository"""

    @handle_github_errors("delete_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.delete_file(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["path"],
            inputs["message"],
            inputs["sha"],
            branch=inputs.get("branch"),
        )

        return ActionResult(
            data={
                "deleted": True,
                "path": inputs["path"],
                "commit": {
                    "sha": result["commit"]["sha"],
                    "message": result["commit"]["message"],
                },
            },
            cost_usd=0.0,
        )


# =============================================================================
# MULTI-FILE COMMITS (Git Data API)
#
# The Contents API can only touch one file per commit. Committing several files
# atomically means driving the lower-level Git Data API by hand:
#
#   1. GET   /git/ref/heads/{branch}      -> the current head commit SHA
#   2. GET   /git/commits/{head_sha}      -> the tree that commit points at
#  (2b. POST /git/blobs                   -> one blob per base64 file, if any)
#   3. POST  /git/trees                   -> a new tree layered on the base tree
#   4. POST  /git/commits                 -> a commit for the new tree
#   5. PATCH /git/refs/heads/{branch}     -> move the branch onto the commit
#
# The sequence is not transactional. A failure before step 5 leaves at most a
# few unreferenced git objects, which GitHub garbage-collects; the branch never
# moves. Every step therefore reports which step failed and whether anything
# was committed, so the caller can tell a safe retry from a partial state.
# =============================================================================

_DEFAULT_TREE_MODE = "100644"
_TREE_FILE_MODES = ("100644", "100755", "120000")
_TEXT_ENCODING = "utf-8"
_BASE64_ENCODING = "base64"
_SUPPORTED_ENCODINGS = (_TEXT_ENCODING, _BASE64_ENCODING)


def _push_step_error(step: str, exc: Exception, consequence: str) -> RuntimeError:
    """Build the error raised when one step of the push sequence fails."""
    return RuntimeError(f"Push files failed at {step}: {exc}. {consequence}")


def _normalized_file_change(index: int, entry: Any) -> Dict[str, Any]:
    """Validate one requested file change and normalise it for the tree call.

    Raises ``ValueError`` with an actionable message; every file is validated
    before any HTTP request is made, so a bad payload never leaves a partially
    applied commit behind.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"files[{index}] must be an object with 'path' and 'content'.")

    path = entry.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"files[{index}] is missing a non-empty 'path'.")
    path = path.strip()
    if path.startswith("/"):
        raise ValueError(f"files[{index}] path '{path}' must be relative to the repository root (no leading '/').")

    content = entry.get("content")
    if not isinstance(content, str):
        raise ValueError(f"files[{index}] ('{path}') must supply 'content' as a string.")

    mode = entry.get("mode") or _DEFAULT_TREE_MODE
    if mode not in _TREE_FILE_MODES:
        raise ValueError(
            f"files[{index}] ('{path}') has unsupported mode '{mode}'. Use one of {', '.join(_TREE_FILE_MODES)}."
        )

    encoding = (entry.get("encoding") or _TEXT_ENCODING).lower()
    if encoding not in _SUPPORTED_ENCODINGS:
        raise ValueError(
            f"files[{index}] ('{path}') has unsupported encoding '{encoding}'. "
            f"Use one of {', '.join(_SUPPORTED_ENCODINGS)}."
        )

    if encoding == _BASE64_ENCODING:
        # Binary content cannot ride inline in a tree entry — it is uploaded as
        # its own blob first. Validate it here so a bad payload fails before
        # any request rather than committing a corrupted file.
        content = "".join(content.split())
        try:
            base64.b64decode(content, validate=True)
        except Exception as exc:
            raise ValueError(f"files[{index}] ('{path}') is not valid base64: {exc}") from exc
    else:
        try:
            content.encode(_TEXT_ENCODING)
        except UnicodeEncodeError as exc:
            raise ValueError(
                f"files[{index}] ('{path}') is not valid UTF-8 text: {exc}. "
                "Set encoding to 'base64' to push binary content."
            ) from exc

    return {"path": path, "content": content, "mode": mode, "encoding": encoding}


def _build_file_changes(files: Any, delete_paths: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate the whole change set before the first HTTP call."""
    if files is None:
        files = []
    if not isinstance(files, list):
        raise ValueError("'files' must be an array of objects with 'path' and 'content'.")

    if delete_paths is None:
        delete_paths = []
    if not isinstance(delete_paths, list):
        raise ValueError("'delete_paths' must be an array of repository file paths.")

    changes = [_normalized_file_change(index, entry) for index, entry in enumerate(files)]

    deletions: List[str] = []
    for index, path in enumerate(delete_paths):
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"delete_paths[{index}] must be a non-empty repository file path.")
        deletions.append(path.strip().lstrip("/"))

    if not changes and not deletions:
        raise ValueError("Nothing to commit: supply at least one entry in 'files' or in 'delete_paths'.")

    seen = set()
    for path in [change["path"] for change in changes] + deletions:
        if path in seen:
            raise ValueError(f"Path '{path}' appears more than once in this commit. Each path may appear only once.")
        seen.add(path)

    return changes, deletions


async def _get_branch_head_sha(context: ExecutionContext, owner: str, repo: str, branch: str) -> Optional[str]:
    """Step 1 — read the commit a branch currently points at."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/ref/heads/{quote(branch, safe='/')}"
    ref_payload = (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data
    return (ref_payload.get("object") or {}).get("sha")


async def _get_commit_tree_sha(context: ExecutionContext, owner: str, repo: str, commit_sha: str) -> Optional[str]:
    """Step 2 — read the tree a commit points at, to use as the base tree."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/commits/{commit_sha}"
    commit_payload = (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data
    return (commit_payload.get("tree") or {}).get("sha")


async def _create_blob(context: ExecutionContext, owner: str, repo: str, content: str, encoding: str) -> Optional[str]:
    """Step 2b — upload one blob, used for base64 (binary) content."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/blobs"
    data = {"content": content, "encoding": encoding}
    blob_payload = (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data
    return blob_payload.get("sha")


async def _create_tree(
    context: ExecutionContext, owner: str, repo: str, base_tree: str, entries: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Step 3 — layer the changed paths over the base tree."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/trees"
    data = {"base_tree": base_tree, "tree": entries}
    return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data


async def _create_commit(
    context: ExecutionContext, owner: str, repo: str, message: str, tree_sha: str, parent_sha: str
) -> Dict[str, Any]:
    """Step 4 — create the commit object for the new tree."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/commits"
    data = {"message": message, "tree": tree_sha, "parents": [parent_sha]}
    return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data


async def _update_branch_ref(
    context: ExecutionContext, owner: str, repo: str, branch: str, sha: str, force: bool = False
) -> Dict[str, Any]:
    """Step 5 — move the branch onto the new commit."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/refs/heads/{quote(branch, safe='/')}"
    data = {"sha": sha, "force": force}
    return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data


async def _push_files(
    context: ExecutionContext,
    owner: str,
    repo: str,
    branch: str,
    message: str,
    files: Any,
    delete_paths: Any = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Commit several file changes to a branch as one atomic commit."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("'message' must be a non-empty commit message.")

    changes, deletions = _build_file_changes(files, delete_paths)

    try:
        head_sha = await _get_branch_head_sha(context, owner, repo, branch)
    except Exception as exc:
        raise _push_step_error(
            f"step 1 of 5 (reading the ref for branch '{branch}')",
            exc,
            "Nothing was committed and the branch is unchanged — check the branch name, then retry.",
        ) from exc

    if not head_sha:
        raise RuntimeError(
            f"Push files failed at step 1 of 5 (reading the ref for branch '{branch}'): "
            "GitHub returned no head commit for the branch. Nothing was committed."
        )

    try:
        base_tree_sha = await _get_commit_tree_sha(context, owner, repo, head_sha)
    except Exception as exc:
        raise _push_step_error(
            f"step 2 of 5 (reading the base commit {head_sha})",
            exc,
            "Nothing was committed and the branch is unchanged.",
        ) from exc

    if not base_tree_sha:
        raise RuntimeError(
            f"Push files failed at step 2 of 5 (reading the base commit {head_sha}): "
            "GitHub returned no tree for the head commit. Nothing was committed."
        )

    tree_entries: List[Dict[str, Any]] = []
    for change in changes:
        entry: Dict[str, Any] = {"path": change["path"], "mode": change["mode"], "type": "blob"}
        if change["encoding"] == _BASE64_ENCODING:
            try:
                blob_sha = await _create_blob(context, owner, repo, change["content"], _BASE64_ENCODING)
            except Exception as exc:
                raise _push_step_error(
                    f"step 2b of 5 (uploading a base64 blob for '{change['path']}')",
                    exc,
                    "No commit was created and the branch is unchanged.",
                ) from exc
            entry["sha"] = blob_sha
        else:
            # Inline content lets GitHub write the blob as part of the tree
            # call, saving one request per file. UTF-8 text only.
            entry["content"] = change["content"]
        tree_entries.append(entry)

    # A null sha removes the path from the tree — this is how a delete is
    # expressed in the Git Data API.
    tree_entries.extend({"path": path, "mode": _DEFAULT_TREE_MODE, "type": "blob", "sha": None} for path in deletions)

    try:
        new_tree = await _create_tree(context, owner, repo, base_tree_sha, tree_entries)
    except Exception as exc:
        raise _push_step_error(
            "step 3 of 5 (creating the new tree)",
            exc,
            "No commit was created and the branch is unchanged. Paths listed in delete_paths must already exist.",
        ) from exc

    new_tree_sha = new_tree.get("sha")
    if not new_tree_sha:
        raise RuntimeError(
            "Push files failed at step 3 of 5 (creating the new tree): GitHub returned no tree SHA. "
            "No commit was created and the branch is unchanged."
        )

    try:
        commit = await _create_commit(context, owner, repo, message, new_tree_sha, head_sha)
    except Exception as exc:
        raise _push_step_error(
            "step 4 of 5 (creating the commit)",
            exc,
            "The branch is unchanged; the tree object created in step 3 is unreferenced and will be "
            "garbage-collected. Safe to retry.",
        ) from exc

    commit_sha = commit.get("sha")
    if not commit_sha:
        raise RuntimeError(
            "Push files failed at step 4 of 5 (creating the commit): GitHub returned no commit SHA. "
            "The branch is unchanged."
        )

    try:
        await _update_branch_ref(context, owner, repo, branch, commit_sha, force=force)
    except Exception as exc:
        raise _push_step_error(
            f"step 5 of 5 (moving branch '{branch}' to commit {commit_sha})",
            exc,
            f"Commit {commit_sha} exists but the branch still points at {head_sha}. If the branch moved on "
            "since step 1, GitHub rejected the move as a non-fast-forward — re-run to rebuild on the new "
            "head, or turn on force to overwrite it.",
        ) from exc

    return {
        "commit": commit,
        "tree_sha": new_tree_sha,
        "parent_sha": head_sha,
        "written_paths": [change["path"] for change in changes],
        "deleted_paths": deletions,
    }


@github.action("push_files")
class PushFiles(ActionHandler):
    """Commit several files to a branch in a single commit.

    Runs the Git Data API sequence (read ref, read base commit, create tree,
    create commit, move ref) so every file lands in one commit instead of one
    commit per file. The sequence is not transactional: if a step fails, the
    error names the step and says whether anything was committed.
    """

    @handle_github_errors("push_files")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await _push_files(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["branch"],
            inputs["message"],
            inputs["files"],
            delete_paths=inputs.get("delete_paths"),
            force=bool(inputs.get("force", False)),
        )

        commit = result["commit"]
        author = commit.get("author") or {}

        return ActionResult(
            data={
                "commit": {
                    "sha": commit.get("sha"),
                    "message": commit.get("message"),
                    "url": commit.get("html_url"),
                    "author": {"name": author.get("name"), "email": author.get("email"), "date": author.get("date")},
                },
                "branch": inputs["branch"],
                "tree_sha": result["tree_sha"],
                "parent_sha": result["parent_sha"],
                "written_paths": result["written_paths"],
                "deleted_paths": result["deleted_paths"],
                "files_changed": len(result["written_paths"]) + len(result["deleted_paths"]),
            },
            cost_usd=0.0,
        )

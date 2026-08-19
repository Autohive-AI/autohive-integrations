"""
GitHub integration - Pull request actions - create, read, merge, and manage reviewers.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional

from github import github
from helpers import GitHubAPI, handle_github_errors, _commit_summary


@github.action("list_pull_requests")
class ListPullRequests(ActionHandler):
    """List pull requests for a repository"""

    @handle_github_errors("list_pull_requests")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        prs = await GitHubAPI.get_pull_requests(
            context,
            inputs["owner"],
            inputs["repo"],
            state=inputs.get("state", "all"),
            sort=inputs.get("sort", "updated"),
            direction=inputs.get("direction", "desc"),
            after=inputs.get("after"),
            before=inputs.get("before"),
            author=inputs.get("author"),
            limit=inputs.get("limit"),
            max_pages=inputs.get("max_pages", 10),
        )

        return ActionResult(
            data=[
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "description": pr.get("body"),
                    "state": pr["state"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "closed_at": pr.get("closed_at"),
                    "draft": pr.get("draft", False),
                    "author": {
                        "login": pr["user"]["login"],
                        "avatar_url": pr["user"]["avatar_url"],
                    },
                    "url": pr["html_url"],
                }
                for pr in prs
            ],
            cost_usd=0.0,
        )


@github.action("get_pull_request")
class GetPullRequest(ActionHandler):
    """Get detailed information about a pull request"""

    @handle_github_errors("get_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        pr = await GitHubAPI.get_pull_request(context, inputs["owner"], inputs["repo"], inputs["pull_number"])

        return ActionResult(
            data={
                "number": pr["number"],
                "title": pr["title"],
                "description": pr.get("body"),
                "state": pr["state"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "merged_at": pr.get("merged_at"),
                "closed_at": pr.get("closed_at"),
                "draft": pr.get("draft", False),
                "mergeable": pr.get("mergeable"),
                "mergeable_state": pr.get("mergeable_state"),
                "merged": pr.get("merged", False),
                "author": {
                    "login": pr["user"]["login"],
                    "avatar_url": pr["user"]["avatar_url"],
                },
                "assignees": [{"login": assignee["login"]} for assignee in pr.get("assignees", [])],
                "requested_reviewers": [{"login": reviewer["login"]} for reviewer in pr.get("requested_reviewers", [])],
                "labels": [{"name": label["name"], "color": label["color"]} for label in pr.get("labels", [])],
                "head": {
                    "ref": pr["head"]["ref"],
                    "sha": pr["head"]["sha"],
                    "repo": {
                        "name": pr["head"]["repo"]["name"],
                        "full_name": pr["head"]["repo"]["full_name"],
                    },
                },
                "base": {
                    "ref": pr["base"]["ref"],
                    "sha": pr["base"]["sha"],
                    "repo": {
                        "name": pr["base"]["repo"]["name"],
                        "full_name": pr["base"]["repo"]["full_name"],
                    },
                },
                "url": pr["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("create_pull_request")
class CreatePullRequest(ActionHandler):
    """Create a new pull request"""

    @handle_github_errors("create_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        pr = await GitHubAPI.create_pull_request(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["title"],
            inputs["head"],
            inputs["base"],
            body=inputs.get("body"),
            draft=inputs.get("draft", False),
            maintainer_can_modify=inputs.get("maintainer_can_modify", True),
        )

        return ActionResult(
            data={
                "id": pr["id"],
                "node_id": pr["node_id"],
                "number": pr["number"],
                "title": pr["title"],
                "body": pr["body"],
                "state": pr["state"],
                "html_url": pr["html_url"],
                "url": pr.get("url", pr["html_url"]),
                "diff_url": pr["diff_url"],
                "patch_url": pr["patch_url"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "draft": pr["draft"],
                "merged": pr.get("merged"),
                "mergeable": pr.get("mergeable"),
                "mergeable_state": pr.get("mergeable_state"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
                "user": {
                    "avatar_url": pr["user"]["avatar_url"],
                    "login": pr["user"]["login"],
                    "id": pr["user"]["id"],
                },
                "author_association": pr.get("author_association"),
                "assignee": {
                    "login": pr["assignee"]["login"],
                    "id": pr["assignee"]["id"],
                    "avatar_url": pr["assignee"]["avatar_url"],
                }
                if pr.get("assignee")
                else None,
                "assignees": [
                    {"login": a["login"], "id": a["id"], "avatar_url": a["avatar_url"]} for a in pr.get("assignees", [])
                ],
                "requested_reviewers": [
                    {"login": r["login"], "id": r["id"], "avatar_url": r["avatar_url"]}
                    for r in pr.get("requested_reviewers", [])
                ],
                "requested_teams": [
                    {"id": t["id"], "name": t["name"], "slug": t["slug"]} for t in pr.get("requested_teams", [])
                ],
                "labels": [{"name": label["name"], "color": label["color"]} for label in pr.get("labels", [])],
                "milestone": {
                    "id": pr["milestone"]["id"],
                    "number": pr["milestone"]["number"],
                    "title": pr["milestone"]["title"],
                    "state": pr["milestone"]["state"],
                }
                if pr.get("milestone")
                else None,
                "head": {
                    "ref": pr["head"]["ref"],
                    "sha": pr["head"]["sha"],
                    "repo": {
                        "name": pr["head"]["repo"]["name"],
                        "full_name": pr["head"]["repo"]["full_name"],
                        "id": pr["head"]["repo"]["id"],
                    },
                },
                "base": {
                    "ref": pr["base"]["ref"],
                    "sha": pr["base"]["sha"],
                    "repo": {
                        "name": pr["base"]["repo"]["name"],
                        "full_name": pr["base"]["repo"]["full_name"],
                        "id": pr["base"]["repo"]["id"],
                    },
                },
                "comments": pr.get("comments", 0),
                "review_comments": pr.get("review_comments", 0),
                "commits": pr.get("commits", 0),
                "additions": pr.get("additions", 0),
                "deletions": pr.get("deletions", 0),
                "changed_files": pr.get("changed_files", 0),
            },
            cost_usd=0.0,
        )


@github.action("merge_pull_request")
class MergePullRequest(ActionHandler):
    """Merge a pull request"""

    @handle_github_errors("merge_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.merge_pull_request(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            commit_title=inputs.get("commit_title"),
            commit_message=inputs.get("commit_message"),
            merge_method=inputs.get("merge_method", "merge"),
        )

        return ActionResult(
            data={
                "merged": True,
                "message": result.get("message"),
                "sha": result.get("sha"),
                "commit_title": inputs.get("commit_title") or result.get("commit_title"),
                "commit_message": inputs.get("commit_message") or result.get("commit_message"),
            },
            cost_usd=0.0,
        )


@github.action("add_pull_request_reviewers")
class AddPullRequestReviewers(ActionHandler):
    """Add reviewers to a pull request"""

    @handle_github_errors("add_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.add_pull_request_reviewers(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            reviewers=inputs.get("reviewers"),
            team_reviewers=inputs.get("team_reviewers"),
        )

        return ActionResult(
            data={
                "requested_reviewers": [
                    {"login": reviewer["login"], "id": reviewer["id"]}
                    for reviewer in result.get("requested_reviewers", [])
                ],
                "requested_teams": [
                    {"slug": team["slug"], "id": team["id"], "name": team["name"]}
                    for team in result.get("requested_teams", [])
                ],
            },
            cost_usd=0.0,
        )


@github.action("remove_pull_request_reviewers")
class RemovePullRequestReviewers(ActionHandler):
    """Remove reviewers from a pull request"""

    @handle_github_errors("remove_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.remove_pull_request_reviewers(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            reviewers=inputs.get("reviewers"),
            team_reviewers=inputs.get("team_reviewers"),
        )

        return ActionResult(
            data={
                "requested_reviewers": [
                    {"login": reviewer["login"], "id": reviewer["id"]}
                    for reviewer in result.get("requested_reviewers", [])
                ],
                "requested_teams": [
                    {"slug": team["slug"], "id": team["id"], "name": team["name"]}
                    for team in result.get("requested_teams", [])
                ],
            },
            cost_usd=0.0,
        )


@github.action("list_pull_request_reviewers")
class ListPullRequestReviewers(ActionHandler):
    """List reviewers for a pull request"""

    @handle_github_errors("list_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.list_pull_request_reviewers(
            context, inputs["owner"], inputs["repo"], inputs["pull_number"]
        )

        return ActionResult(
            data={
                "users": [
                    {
                        "login": user["login"],
                        "id": user["id"],
                        "avatar_url": user["avatar_url"],
                    }
                    for user in result.get("users", [])
                ],
                "teams": [
                    {"slug": team["slug"], "id": team["id"], "name": team["name"]} for team in result.get("teams", [])
                ],
            },
            cost_usd=0.0,
        )


# =============================================================================
# API HELPERS
# =============================================================================

# Media types the "Get a pull request" endpoint accepts to return the raw diff
# instead of the JSON representation.
_DIFF_MEDIA_TYPES = {
    "diff": "application/vnd.github.diff",
    "patch": "application/vnd.github.patch",
}


async def _update_pull_request_branch(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    expected_head_sha: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge the base branch into a pull request's head branch.

    ``PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch`` answers
    ``202 Accepted`` with ``{"message", "url"}`` — the merge runs as a background
    job, so the pull request itself is not part of the response.
    """
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/update-branch"
    body: Dict[str, Any] = {}
    if expected_head_sha:
        body["expected_head_sha"] = expected_head_sha

    fetch_result = await context.fetch(url, method="PUT", json=body, headers=GitHubAPI.get_headers(context))
    return fetch_result.data or {}


async def _get_pull_request_raw(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    media_type: str,
) -> str:
    """Fetch a pull request under a non-JSON media type, returning the body as text."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
    fetch_result = await context.fetch(url, headers=GitHubAPI.get_headers(context, accept=media_type))
    raw_body = fetch_result.data
    if raw_body is None:
        return ""
    return raw_body if isinstance(raw_body, str) else str(raw_body)


async def _get_combined_status(context: ExecutionContext, owner: str, repo: str, ref: str) -> Dict[str, Any]:
    """Get the combined commit status for a git ref (GET /repos/.../commits/{ref}/status)."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/commits/{ref}/status"
    fetch_result = await context.fetch(url, headers=GitHubAPI.get_headers(context))
    return fetch_result.data or {}


async def _create_review_comment_reply(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    comment_id: int,
    body: str,
) -> Dict[str, Any]:
    """Reply to an existing review comment, threading under it."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies"
    fetch_result = await context.fetch(url, method="POST", json={"body": body}, headers=GitHubAPI.get_headers(context))
    return fetch_result.data or {}


def _review_comment_summary(comment: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a review (inline) comment. GitHub nulls ``user`` for deleted accounts."""
    author = comment.get("user")
    return {
        "id": comment.get("id"),
        "body": comment.get("body"),
        "path": comment.get("path"),
        "line": comment.get("line"),
        "start_line": comment.get("start_line"),
        "side": comment.get("side"),
        "start_side": comment.get("start_side"),
        "diff_hunk": comment.get("diff_hunk"),
        "commit_id": comment.get("commit_id"),
        "in_reply_to_id": comment.get("in_reply_to_id"),
        "pull_request_review_id": comment.get("pull_request_review_id"),
        "author_association": comment.get("author_association"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "author": {"login": author.get("login"), "avatar_url": author.get("avatar_url")} if author else None,
        "url": comment.get("html_url"),
    }


def _branch_ref_summary(ref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Shape a PR head/base ref. ``repo`` is null once a fork has been deleted."""
    ref = ref or {}
    repo = ref.get("repo")
    return {
        "ref": ref.get("ref"),
        "sha": ref.get("sha"),
        "label": ref.get("label"),
        "repo": {"name": repo.get("name"), "full_name": repo.get("full_name")} if repo else None,
    }


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("update_pull_request")
class UpdatePullRequest(ActionHandler):
    """Update a pull request's title, body, state, base branch, or maintainer-edit flag"""

    @handle_github_errors("update_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        pr = await GitHubAPI.update_pull_request(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            title=inputs.get("title"),
            body=inputs.get("body"),
            state=inputs.get("state"),
            base=inputs.get("base"),
            maintainer_can_modify=inputs.get("maintainer_can_modify"),
        )

        author = pr.get("user")

        return ActionResult(
            data={
                "number": pr.get("number"),
                "title": pr.get("title"),
                "description": pr.get("body"),
                "state": pr.get("state"),
                "draft": pr.get("draft", False),
                "merged": pr.get("merged", False),
                "mergeable": pr.get("mergeable"),
                "mergeable_state": pr.get("mergeable_state"),
                "maintainer_can_modify": pr.get("maintainer_can_modify"),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "author": {"login": author.get("login"), "avatar_url": author.get("avatar_url")} if author else None,
                "head": _branch_ref_summary(pr.get("head")),
                "base": _branch_ref_summary(pr.get("base")),
                "url": pr.get("html_url"),
            },
            cost_usd=0.0,
        )


@github.action("update_pull_request_branch")
class UpdatePullRequestBranch(ActionHandler):
    """Bring a pull request's branch up to date by merging the base branch into it"""

    @handle_github_errors("update_pull_request_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await _update_pull_request_branch(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            expected_head_sha=inputs.get("expected_head_sha"),
        )

        return ActionResult(
            data={
                "pull_number": inputs["pull_number"],
                "queued": True,
                "message": result.get("message"),
                "url": result.get("url"),
            },
            cost_usd=0.0,
        )


@github.action("get_pull_request_diff")
class GetPullRequestDiff(ActionHandler):
    """Get the full diff or patch text for a pull request"""

    @handle_github_errors("get_pull_request_diff")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        diff_format = inputs.get("format", "diff")
        media_type = _DIFF_MEDIA_TYPES.get(diff_format)
        if media_type is None:
            raise ValueError(f"Unsupported format '{diff_format}'. Use 'diff' or 'patch'.")

        content = await _get_pull_request_raw(
            context, inputs["owner"], inputs["repo"], inputs["pull_number"], media_type
        )

        return ActionResult(
            data={
                "pull_number": inputs["pull_number"],
                "format": diff_format,
                "content": content,
                "length": len(content),
            },
            cost_usd=0.0,
        )


@github.action("get_pull_request_files")
class GetPullRequestFiles(ActionHandler):
    """List the files changed by a pull request, with per-file line counts and patches"""

    @handle_github_errors("get_pull_request_files")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/pulls/{inputs['pull_number']}/files"
        files: List[Dict[str, Any]] = await GitHubAPI.paginated_fetch(
            context,
            url,
            limit=inputs.get("limit"),
            max_pages=inputs.get("max_pages", 10),
        )

        include_patch = inputs.get("include_patch", True)

        return ActionResult(
            data=[
                {
                    "filename": changed_file.get("filename"),
                    "previous_filename": changed_file.get("previous_filename"),
                    "status": changed_file.get("status"),
                    "additions": changed_file.get("additions", 0),
                    "deletions": changed_file.get("deletions", 0),
                    "changes": changed_file.get("changes", 0),
                    "sha": changed_file.get("sha"),
                    # GitHub omits `patch` for binary files and for diffs over ~20k lines.
                    "patch": changed_file.get("patch") if include_patch else None,
                    "url": changed_file.get("blob_url"),
                    "raw_url": changed_file.get("raw_url"),
                }
                for changed_file in files
            ],
            cost_usd=0.0,
        )


@github.action("get_pull_request_status")
class GetPullRequestStatus(ActionHandler):
    """Get the combined CI status for a pull request's head commit"""

    @handle_github_errors("get_pull_request_status")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        # The combined-status endpoint keys off a git ref, not a PR number, so
        # the head SHA has to be resolved from the pull request first.
        pr = await GitHubAPI.get_pull_request(context, inputs["owner"], inputs["repo"], inputs["pull_number"])
        head_sha = (pr.get("head") or {}).get("sha")
        if not head_sha:
            raise ValueError(f"Pull request #{inputs['pull_number']} has no head commit SHA to check status for.")

        status = await _get_combined_status(context, inputs["owner"], inputs["repo"], head_sha)

        return ActionResult(
            data={
                "pull_number": inputs["pull_number"],
                "sha": status.get("sha", head_sha),
                "state": status.get("state"),
                "total_count": status.get("total_count", 0),
                "statuses": [
                    {
                        "context": check.get("context"),
                        "state": check.get("state"),
                        "description": check.get("description"),
                        "target_url": check.get("target_url"),
                        "created_at": check.get("created_at"),
                        "updated_at": check.get("updated_at"),
                    }
                    for check in status.get("statuses", [])
                ],
                "url": status.get("commit_url"),
            },
            cost_usd=0.0,
        )


@github.action("get_pull_request_comments")
class GetPullRequestComments(ActionHandler):
    """List the inline review comments left on a pull request's diff"""

    @handle_github_errors("get_pull_request_comments")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/pulls/{inputs['pull_number']}/comments"
        params: Dict[str, Any] = {}
        if inputs.get("sort"):
            params["sort"] = inputs["sort"]
        if inputs.get("direction"):
            params["direction"] = inputs["direction"]
        if inputs.get("since"):
            params["since"] = inputs["since"]

        comments: List[Dict[str, Any]] = await GitHubAPI.paginated_fetch(
            context,
            url,
            params=params,
            limit=inputs.get("limit"),
            max_pages=inputs.get("max_pages", 10),
        )

        return ActionResult(
            data=[_review_comment_summary(comment) for comment in comments],
            cost_usd=0.0,
        )


@github.action("add_reply_to_pull_request_comment")
class AddReplyToPullRequestComment(ActionHandler):
    """Reply to an existing inline review comment, keeping the reply in the same thread"""

    @handle_github_errors("add_reply_to_pull_request_comment")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        reply = await _create_review_comment_reply(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            inputs["comment_id"],
            inputs["body"],
        )

        return ActionResult(data=_review_comment_summary(reply), cost_usd=0.0)


@github.action("list_pull_request_commits")
class ListPullRequestCommits(ActionHandler):
    """List the commits contained in a pull request"""

    @handle_github_errors("list_pull_request_commits")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/pulls/{inputs['pull_number']}/commits"
        commits: List[Dict[str, Any]] = await GitHubAPI.paginated_fetch(
            context,
            url,
            limit=inputs.get("limit"),
            max_pages=inputs.get("max_pages", 10),
        )

        return ActionResult(
            data=[_commit_summary(commit) for commit in commits],
            cost_usd=0.0,
        )

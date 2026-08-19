"""
Shared helpers for the GitHub integration.

Houses the GitHub REST API client (``GitHubAPI``), the error-handling decorator
every action wraps its ``execute`` method in, and the response-shaping helpers
used across action modules.

GitHub API Version: 2022-11-28
Reference: https://docs.github.com/en/rest
"""

from autohive_integrations_sdk import (
    ExecutionContext,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, List, Callable, Optional
from urllib.parse import quote
from functools import wraps
from datetime import datetime, timezone
import asyncio
import base64
import logging

logger = logging.getLogger(__name__)


def _parse_iso_utc(value: str, *, end_of_day: bool = False) -> Optional[datetime]:
    """Parse an ISO 8601 date or datetime into an aware UTC datetime.

    Handles a trailing ``Z`` and naive values (assumed UTC). A bare date
    (``YYYY-MM-DD``) maps to the start of that day, or to the last microsecond
    of it when ``end_of_day`` is set — preserving the inclusive whole-day
    semantics of the Search API's ``created:>=`` / ``created:<=`` qualifiers
    (e.g. ``before="2024-01-01"`` still matches a PR created at
    ``2024-01-01T09:00:00Z``). Returns ``None`` for unparseable input.
    """
    if not value:
        return None
    text = value.strip()
    date_only = "T" not in text and " " not in text
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if date_only and end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


# =============================================================================
# ERROR HANDLING
# =============================================================================


def handle_github_errors(action_name: str):
    """
    Decorator that wraps action execute methods with error handling.

    Catches exceptions and returns ActionResult with error data for common GitHub
    API error codes (401, 403, 404, 422) with user-friendly messages.
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
            try:
                # Validate token is present
                credentials = context.auth.get("credentials", {})
                token = credentials.get("access_token")
                if not token:
                    return ActionError(
                        message=(
                            "GitHub authentication failed: No access token found. Please reconnect your GitHub account."
                        )
                    )

                return await func(self, inputs, context)

            except asyncio.CancelledError:
                # Defensive: convert Python-side task cancellation into an
                # ActionError if cancellation reaches the action coroutine.
                # This does not catch Lambda hard timeouts or caller-side
                # invocation cancellation.
                logger.warning(
                    "CancelledError caught in action %s — cooperative cancellation reached the action coroutine",
                    action_name,
                )
                return ActionError(
                    message=(
                        f"Action '{action_name}' was cancelled before completing. "
                        "If listing a large dataset, try narrowing the request with filters."
                    )
                )
            except Exception as e:
                return ActionError(message=str(e))

        return wrapper

    return decorator


class GitHubAPI:
    """Helper class for GitHub API operations with comprehensive functionality"""

    BASE_URL = "https://api.github.com"
    GRAPHQL_URL = "https://api.github.com/graphql"

    # The Search API caps every query at 1000 results no matter how far you
    # paginate, and runs its own rate limit: 30 requests/minute, or only 10 for
    # code search. See https://docs.github.com/en/rest/search
    SEARCH_MAX_RESULTS = 1000

    @staticmethod
    def get_headers(context: ExecutionContext, accept: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        """
        Build authentication headers for GitHub API requests.
        GitHub uses Bearer token authentication with OAuth2 tokens.

        ``accept`` overrides the media type for endpoints that return something
        other than JSON — e.g. ``application/vnd.github.diff`` for a PR diff.
        """
        credentials = context.auth.get("credentials", {})
        token = credentials.get("access_token", "")

        return {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    @staticmethod
    async def paginated_fetch(
        context: ExecutionContext,
        url: str,
        params: Dict[str, Any] = None,
        data_key: str = None,
        max_pages: int = 10,
        limit: int = None,
        filter_fn: Callable[[Dict[str, Any]], bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generic paginated fetch that handles GitHub's pagination automatically.

        Bounded by max_pages to prevent unbounded loops on large datasets
        (e.g. list_commits on a repo with thousands of commits) from running
        until the Lambda runtime cancels the task.

        Args:
            context: ExecutionContext
            url: API endpoint URL
            params: Query parameters
            data_key: Key to extract from response (e.g., 'workflows', 'workflow_runs')
            max_pages: Hard cap on pages fetched. Raises TimeoutError when exceeded.
            limit: Stop and return as soon as this many (matching) items are
                collected, without fetching (or raising on) further pages. Only
                correct for endpoints that return results in the order the caller
                wants the first N of.
            filter_fn: Optional predicate applied to each item before it counts
                toward ``limit``. This lets callers that filter client-side still
                stop early — pagination ends as soon as ``limit`` *matching* items
                are found, rather than scanning to ``max_pages`` and risking a
                spurious TimeoutError when page 1 already satisfied the request.
        """
        if params is None:
            params = {}

        params.setdefault("per_page", 100)
        params.setdefault("page", 1)
        # Don't request more per page than we ultimately need — but only when we
        # return items verbatim. With a filter, pages get thinned post-fetch, so
        # we keep full pages and let the limit count matches instead.
        if limit and filter_fn is None:
            params["per_page"] = min(params["per_page"], limit)

        all_items = []
        headers = GitHubAPI.get_headers(context)
        pages_fetched = 0
        while True:
            if limit and len(all_items) >= limit:
                return all_items[:limit]

            if pages_fetched >= max_pages:
                logger.warning(
                    "paginated_fetch hit max_pages cap (url=%s, max_pages=%d, items_collected=%d)",
                    url,
                    max_pages,
                    len(all_items),
                )
                raise TimeoutError(
                    f"GitHub pagination stopped after {max_pages} pages "
                    f"({len(all_items)} items). Narrow the request with filters "
                    "(e.g. sha, path, since, until) or raise max_pages."
                )

            fetch_result = await context.fetch(url, params=params, headers=headers)
            pages_fetched += 1
            response = fetch_result.data

            # Extract items from response
            if data_key and isinstance(response, dict):
                items = response.get(data_key, [])
            elif isinstance(response, list):
                items = response
            else:
                items = [response] if response else []

            if not items:
                break

            # Detect the last page from the raw page size, before filtering
            # thins it (a full page with everything filtered out is still full).
            page_size = len(items)
            if filter_fn is not None:
                items = [item for item in items if filter_fn(item)]

            all_items.extend(items)

            # Check if we got less than per_page items, meaning this is the last page
            if page_size < params["per_page"]:
                break

            params["page"] += 1

        return all_items[:limit] if limit else all_items

    # ---- Repository Operations ----

    @staticmethod
    async def create_repository(
        context: ExecutionContext,
        name: str,
        description: str = None,
        private: bool = False,
        auto_init: bool = False,
        gitignore_template: str = None,
        license_template: str = None,
        org: str = None,
        homepage: str = None,
        has_issues: bool = True,
        has_projects: bool = True,
        has_wiki: bool = True,
    ) -> Dict[str, Any]:
        """Create a new repository"""
        if org:
            url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        data = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
            "has_issues": has_issues,
            "has_projects": has_projects,
            "has_wiki": has_wiki,
        }

        if description:
            data["description"] = description
        if homepage:
            data["homepage"] = homepage
        if gitignore_template:
            data["gitignore_template"] = gitignore_template
        if license_template:
            data["license_template"] = license_template

        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_repository(context: ExecutionContext, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository details"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def list_repositories(
        context: ExecutionContext,
        username: str = None,
        org: str = None,
        type: str = "all",
        sort: str = "updated",
        direction: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List repositories for user or organization"""
        if org:
            url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        elif username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        params = {"type": type, "sort": sort, "direction": direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def list_user_repositories(
        context: ExecutionContext,
        username: str = None,
        type: str = "all",
        sort: str = "updated",
        direction: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List repositories for a specific user or authenticated user"""
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        params = {"type": type, "sort": sort, "direction": direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def list_organization_repositories(
        context: ExecutionContext,
        org: str,
        type: str = "all",
        sort: str = "updated",
        direction: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List repositories for a specific organization"""
        url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        params = {"type": type, "sort": sort, "direction": direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def update_repository(context: ExecutionContext, owner: str, repo: str, **kwargs) -> Dict[str, Any]:
        """Update repository settings"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        data = {k: v for k, v in kwargs.items() if v is not None}
        return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def delete_repository(context: ExecutionContext, owner: str, repo: str) -> None:
        """Delete a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    # ---- Commit Operations ----

    @staticmethod
    async def get_commits(
        context: ExecutionContext,
        owner: str,
        repo: str,
        sha: str = None,
        path: str = None,
        since: str = None,
        until: str = None,
        max_pages: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get commits for a repository (bounded by max_pages)"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {}

        if sha:
            params["sha"] = sha
        if path:
            params["path"] = path
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        return await GitHubAPI.paginated_fetch(context, url, params, max_pages=max_pages)

    @staticmethod
    async def get_commit(context: ExecutionContext, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Get a specific commit"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/commits/{sha}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def compare_branches(
        context: ExecutionContext, owner: str, repo: str, base: str, head: str
    ) -> Dict[str, Any]:
        """Compare two branches"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/compare/{base}...{head}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    # ---- Issue Operations ----

    @staticmethod
    async def get_issues(
        context: ExecutionContext,
        owner: str,
        repo: str,
        state: str = "all",
        sort: str = "created",
        direction: str = "desc",
        since: str = None,
        labels: str = None,
    ) -> List[Dict[str, Any]]:
        """Get issues for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {"state": state, "sort": sort, "direction": direction}

        if since:
            params["since"] = since
        if labels:
            params["labels"] = labels

        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def get_issue(context: ExecutionContext, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get a specific issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def create_issue(
        context: ExecutionContext,
        owner: str,
        repo: str,
        title: str,
        body: str = None,
        assignees: List[str] = None,
        labels: List[str] = None,
        milestone: int = None,
    ) -> Dict[str, Any]:
        """Create a new issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues"
        data = {"title": title}

        if body:
            data["body"] = body
        if assignees:
            data["assignees"] = assignees
        if labels:
            data["labels"] = labels
        if milestone:
            data["milestone"] = milestone

        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def update_issue(
        context: ExecutionContext,
        owner: str,
        repo: str,
        issue_number: int,
        title: str = None,
        body: str = None,
        state: str = None,
        assignees: List[str] = None,
        labels: List[str] = None,
        milestone: int = None,
    ) -> Dict[str, Any]:
        """Update an existing issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        data = {}

        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state
        if assignees:
            data["assignees"] = assignees
        if labels:
            data["labels"] = labels
        if milestone is not None:
            data["milestone"] = milestone

        return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_issue_comments(
        context: ExecutionContext, owner: str, repo: str, issue_number: int
    ) -> List[Dict[str, Any]]:
        """Get comments for an issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def create_issue_comment(
        context: ExecutionContext, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        """Create a comment on an issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = {"body": body}
        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    # ---- Pull Request Operations ----

    @staticmethod
    async def get_pull_requests(
        context: ExecutionContext,
        owner: str,
        repo: str,
        state: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        after: str = None,
        before: str = None,
        author: str = None,
        limit: int = None,
        max_pages: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get pull requests for a repository via the REST List Pull Requests endpoint.

        Uses ``GET /repos/{owner}/{repo}/pulls`` rather than the Search API
        (``/search/issues``). The Search API matches ``repo:owner/repo`` against
        GitHub's search index and returns ``HTTP 422`` ("the listed users and
        repositories cannot be searched...") for any repo missing from that index,
        which excludes many private repos the token can still read via the REST
        API. This endpoint has no such restriction.

        ``state``/``sort``/``direction`` are sent natively (the config ``sort``
        enum values are exactly this endpoint's accepted values). ``author``/
        ``after``/``before`` are not query qualifiers on this endpoint, so they
        are applied client-side after fetching. Pagination is delegated to
        ``paginated_fetch`` and bounded by ``max_pages`` (raises ``TimeoutError``
        when exceeded); narrow with ``state``/``author``/``after``/``before`` for
        full coverage on large repos. ``limit`` caps the returned list.

        ``limit`` is always pushed into ``paginated_fetch``, which stops as soon
        as that many *matching* PRs are collected — even with a client-side
        filter, since the filter runs per page during pagination. So a request
        like ``author="kai", limit=10`` returns once page 1 yields 10 of kai's
        PRs instead of scanning to ``max_pages`` and risking a spurious
        TimeoutError. ``after``/``before`` are compared as parsed UTC datetimes
        (not raw strings) so a bare date is inclusive of the whole day, matching
        the old Search API ``created:>=`` / ``created:<=`` semantics.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {"state": state, "sort": sort, "direction": direction}

        author_lower = author.lower() if author else None
        after_dt = _parse_iso_utc(after) if after else None
        if after and after_dt is None:
            raise ValueError(f"Invalid after date/time: {after!r}")
        before_dt = _parse_iso_utc(before, end_of_day=True) if before else None
        if before and before_dt is None:
            raise ValueError(f"Invalid before date/time: {before!r}")

        def matches(pr: Dict[str, Any]) -> bool:
            if author_lower is not None and pr.get("user", {}).get("login", "").lower() != author_lower:
                return False
            if after_dt or before_dt:
                created = _parse_iso_utc(pr.get("created_at"))
                if created is None:
                    return False
                if after_dt and created < after_dt:
                    return False
                if before_dt and created > before_dt:
                    return False
            return True

        filter_fn = matches if (author_lower or after_dt or before_dt) else None
        prs = await GitHubAPI.paginated_fetch(
            context, url, params, max_pages=max_pages, limit=limit, filter_fn=filter_fn
        )

        return prs[:limit] if limit else prs

    @staticmethod
    async def get_pull_request(context: ExecutionContext, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """Get detailed information about a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def create_pull_request(
        context: ExecutionContext,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = None,
        draft: bool = False,
        maintainer_can_modify: bool = True,
    ) -> Dict[str, Any]:
        """Create a new pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls"
        data = {
            "title": title,
            "head": head,
            "base": base,
            "draft": draft,
            "maintainer_can_modify": maintainer_can_modify,
        }

        if body:
            data["body"] = body

        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def update_pull_request(
        context: ExecutionContext, owner: str, repo: str, pull_number: int, **kwargs
    ) -> Dict[str, Any]:
        """Update a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
        data = {k: v for k, v in kwargs.items() if v is not None}
        return (await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def merge_pull_request(
        context: ExecutionContext,
        owner: str,
        repo: str,
        pull_number: int,
        commit_title: str = None,
        commit_message: str = None,
        merge_method: str = "merge",
    ) -> Dict[str, Any]:
        """Merge a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/merge"
        data = {"merge_method": merge_method}

        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message

        return (await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def add_pull_request_reviewers(
        context: ExecutionContext,
        owner: str,
        repo: str,
        pull_number: int,
        reviewers: List[str] = None,
        team_reviewers: List[str] = None,
    ) -> Dict[str, Any]:
        """Request reviewers for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        data = {}

        if reviewers:
            data["reviewers"] = reviewers
        if team_reviewers:
            data["team_reviewers"] = team_reviewers

        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def remove_pull_request_reviewers(
        context: ExecutionContext,
        owner: str,
        repo: str,
        pull_number: int,
        reviewers: List[str] = None,
        team_reviewers: List[str] = None,
    ) -> Dict[str, Any]:
        """Remove reviewers from a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        data = {}

        if reviewers:
            data["reviewers"] = reviewers
        if team_reviewers:
            data["team_reviewers"] = team_reviewers

        return (await context.fetch(url, method="DELETE", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def list_pull_request_reviewers(
        context: ExecutionContext, owner: str, repo: str, pull_number: int
    ) -> Dict[str, Any]:
        """List reviewers for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def create_pull_request_review(
        context: ExecutionContext,
        owner: str,
        repo: str,
        pull_number: int,
        commit_id: str = None,
        body: str = None,
        event: str = None,
        comments: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a review for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        data = {}

        if commit_id:
            data["commit_id"] = commit_id
        if body:
            data["body"] = body
        if event:
            data["event"] = event
        if comments:
            data["comments"] = comments

        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    # ---- Branch Operations ----

    @staticmethod
    async def list_branches(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List branches for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def get_branch(context: ExecutionContext, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        """Get branch details"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches/{branch}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def create_branch(
        context: ExecutionContext, owner: str, repo: str, branch_name: str, sha: str
    ) -> Dict[str, Any]:
        """Create a new branch"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/refs"
        data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def delete_branch(context: ExecutionContext, owner: str, repo: str, branch: str) -> None:
        """Delete a branch"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_branch_protection(context: ExecutionContext, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        """Get branch protection rules"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches/{branch}/protection"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    # ---- Webhook Operations ----

    @staticmethod
    async def create_webhook(
        context: ExecutionContext,
        owner: str,
        repo: str,
        url: str,
        events: List[str],
        content_type: str = "json",
        secret: str = None,
        active: bool = True,
    ) -> Dict[str, Any]:
        """Create a webhook"""
        webhook_url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks"

        config = {"url": url, "content_type": content_type}

        if secret:
            config["secret"] = secret

        data = {"name": "web", "active": active, "events": events, "config": config}

        return (
            await context.fetch(
                webhook_url,
                method="POST",
                json=data,
                headers=GitHubAPI.get_headers(context),
            )
        ).data

    @staticmethod
    async def list_webhooks(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List webhooks for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def delete_webhook(context: ExecutionContext, owner: str, repo: str, hook_id: int) -> None:
        """Delete a webhook"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks/{hook_id}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    # ---- File Operations ----

    @staticmethod
    async def get_file_content(
        context: ExecutionContext, owner: str, repo: str, path: str, ref: str = None
    ) -> Dict[str, Any]:
        """Get file content from repository, or a directory listing when path is a directory"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"
        params = {}

        if ref:
            params["ref"] = ref

        fetch_result = await context.fetch(
            url,
            params=params if params else None,
            headers=GitHubAPI.get_headers(context),
        )
        response = fetch_result.data

        # GitHub returns a list of entries when the path is a directory
        if isinstance(response, list):
            return {
                "type": "dir",
                "content": "",
                "sha": "",
                "size": 0,
                "name": path.rstrip("/").split("/")[-1],
                "path": path,
                "entries": [
                    {
                        "name": entry.get("name", ""),
                        "path": entry.get("path", ""),
                        "type": entry.get("type", ""),
                        "sha": entry.get("sha", ""),
                        "size": entry.get("size", 0),
                        "download_url": entry.get("download_url") or "",
                    }
                    for entry in response
                ],
            }

        # Decode base64 content
        content = base64.b64decode(response.get("content", "").replace("\n", "")).decode("utf-8")

        return {
            "type": response.get("type", "file"),
            "content": content,
            "sha": response.get("sha", ""),
            "size": response.get("size", 0),
            "name": response.get("name", ""),
            "path": response.get("path", ""),
            "entries": [],
        }

    @staticmethod
    async def create_file(
        context: ExecutionContext,
        owner: str,
        repo: str,
        path: str,
        message: str,
        content: str,
        branch: str = None,
    ) -> Dict[str, Any]:
        """Create a new file in repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        # Encode content to base64
        content_bytes = content.encode("utf-8")
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        data = {"message": message, "content": content_base64}

        if branch:
            data["branch"] = branch

        return (await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def update_file(
        context: ExecutionContext,
        owner: str,
        repo: str,
        path: str,
        message: str,
        content: str,
        sha: str,
        branch: str = None,
    ) -> Dict[str, Any]:
        """Update an existing file in repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        # Encode content to base64
        content_bytes = content.encode("utf-8")
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        data = {"message": message, "content": content_base64, "sha": sha}

        if branch:
            data["branch"] = branch

        return (await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def delete_file(
        context: ExecutionContext,
        owner: str,
        repo: str,
        path: str,
        message: str,
        sha: str,
        branch: str = None,
    ) -> Dict[str, Any]:
        """Delete a file from repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        data = {"message": message, "sha": sha}

        if branch:
            data["branch"] = branch

        return (await context.fetch(url, method="DELETE", json=data, headers=GitHubAPI.get_headers(context))).data

    # ---- Gist Operations ----

    @staticmethod
    async def create_gist(
        context: ExecutionContext,
        description: str,
        files: Dict[str, Any],
        public: bool = True,
    ) -> Dict[str, Any]:
        """Create a gist"""
        url = f"{GitHubAPI.BASE_URL}/gists"
        data = {"description": description, "public": public, "files": files}
        return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_gist(context: ExecutionContext, gist_id: str) -> Dict[str, Any]:
        """Get gist details"""
        url = f"{GitHubAPI.BASE_URL}/gists/{gist_id}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def list_gists(
        context: ExecutionContext,
        username: str = None,
        since: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        """List gists for a user, or for the authenticated user when username is omitted.

        ``since`` is an ISO 8601 timestamp filter applied by GitHub, not by us —
        filtering client-side would still have to page through every older gist
        first and could trip ``paginated_fetch``'s page cap for heavy gist users.
        """
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/gists"
        else:
            url = f"{GitHubAPI.BASE_URL}/gists"

        params = {"since": since} if since else None
        return await GitHubAPI.paginated_fetch(context, url, params=params, limit=limit)

    # ---- User Operations ----

    @staticmethod
    async def get_user(context: ExecutionContext, username: str = None) -> Dict[str, Any]:
        """Get user information"""
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}"
        else:
            url = f"{GitHubAPI.BASE_URL}/user"

        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    # ---- Organization Operations ----

    @staticmethod
    async def list_organization_members(context: ExecutionContext, org: str, role: str = "all") -> List[Dict[str, Any]]:
        """List organization members"""
        url = f"{GitHubAPI.BASE_URL}/orgs/{org}/members"
        params = {"role": role}
        return await GitHubAPI.paginated_fetch(context, url, params)

    # ---- GitHub Actions/Workflows ----

    @staticmethod
    async def list_workflows(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List workflows for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
        return await GitHubAPI.paginated_fetch(context, url, params={}, data_key="workflows")

    @staticmethod
    async def get_workflow_runs(
        context: ExecutionContext,
        owner: str,
        repo: str,
        workflow_id: str,
        status: str = None,
        branch: str = None,
    ) -> List[Dict[str, Any]]:
        """Get workflow runs"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        params = {}

        if status:
            params["status"] = status
        if branch:
            params["branch"] = branch

        return await GitHubAPI.paginated_fetch(context, url, params, "workflow_runs")

    # -------------------------------------------------------------------------
    # Tag Operations
    # Reference: https://docs.github.com/en/rest/repos/repos#list-repository-tags
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_tags(
        context: ExecutionContext,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        List tags for a repository (single page fetch).

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            per_page: Number of results per page (max 100)
            page: Page number to fetch

        Returns:
            List of tag objects with name, commit SHA, and download URLs
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/tags"
        params = {"per_page": per_page, "page": page}
        return (await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))).data

    # -------------------------------------------------------------------------
    # Release Operations
    # Reference: https://docs.github.com/en/rest/releases/releases
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_releases(
        context: ExecutionContext,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        List releases for a repository (single page fetch).

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            per_page: Number of results per page (max 100)
            page: Page number to fetch

        Returns:
            List of release objects (does not include regular Git tags)
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases"
        params = {"per_page": per_page, "page": page}
        return (await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_release(context: ExecutionContext, owner: str, repo: str, release_id: int) -> Dict[str, Any]:
        """
        Get a specific release by ID.

        Args:
            owner: Repository owner
            repo: Repository name
            release_id: The unique identifier of the release

        Returns:
            Release object with full details including assets
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/{release_id}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_latest_release(context: ExecutionContext, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get the latest published release for a repository.

        The latest release is the most recent non-prerelease, non-draft release.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Latest release object
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/latest"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    @staticmethod
    async def get_release_by_tag(context: ExecutionContext, owner: str, repo: str, tag: str) -> Dict[str, Any]:
        """
        Get a release by tag name.

        Note: Tag is URL-encoded to handle special characters like '/' or spaces.

        Args:
            owner: Repository owner
            repo: Repository name
            tag: Tag name (e.g., 'v1.0.0', 'release/2024-01')

        Returns:
            Release object matching the tag
        """
        encoded_tag = quote(tag, safe="")
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/tags/{encoded_tag}"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    # ---- Rate Limiting ----

    @staticmethod
    async def get_rate_limit(context: ExecutionContext) -> Dict[str, Any]:
        """Get current rate limit status"""
        url = f"{GitHubAPI.BASE_URL}/rate_limit"
        return (await context.fetch(url, headers=GitHubAPI.get_headers(context))).data

    # ---- Search Operations ----

    @staticmethod
    async def search(
        context: ExecutionContext,
        endpoint: str,
        query: str,
        sort: str = None,
        order: str = None,
        limit: int = None,
        max_pages: int = 3,
        extra_params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Query a GitHub Search API endpoint, following pagination.

        Search differs from the rest of the REST API in three ways that this
        method encapsulates so callers don't have to:

        1. Results come back enveloped as ``{total_count, incomplete_results,
           items}`` rather than a bare array.
        2. GitHub returns at most 1000 results for any query, however far you
           paginate. ``total_count`` still reports the true total, so the two
           are reported separately.
        3. Search has its own, much tighter rate limit (30 requests/minute; 10
           for code search), which is why ``max_pages`` defaults to 3 here
           rather than the 10 used by ``paginated_fetch``.

        Args:
            endpoint: Search path segment — ``"code"``, ``"commits"``,
                ``"issues"``, ``"repositories"``, or ``"users"``.
            query: The ``q`` search query, including any qualifiers.
            sort: Sort field. Endpoint-specific; omit for best match.
            order: ``"asc"`` or ``"desc"``. Only meaningful alongside ``sort``.
            limit: Stop once this many items are collected.
            max_pages: Hard cap on pages fetched.
            extra_params: Additional query parameters for the endpoint.

        Returns:
            ``{"items": [...], "total_count": int, "incomplete_results": bool,
            "capped": bool}`` where ``capped`` marks a query whose true total
            exceeds what the Search API will hand back.
        """
        url = f"{GitHubAPI.BASE_URL}/search/{endpoint}"

        params: Dict[str, Any] = {"q": query, "per_page": 100, "page": 1}
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if extra_params:
            params.update(extra_params)

        if limit:
            params["per_page"] = min(params["per_page"], limit)

        headers = GitHubAPI.get_headers(context)
        items: List[Dict[str, Any]] = []
        total_count = 0
        incomplete = False
        pages_fetched = 0

        while True:
            if limit and len(items) >= limit:
                break
            if pages_fetched >= max_pages:
                logger.warning(
                    "search hit max_pages cap (endpoint=%s, max_pages=%d, items=%d)",
                    endpoint,
                    max_pages,
                    len(items),
                )
                break

            fetch_result = await context.fetch(url, params=params, headers=headers)
            pages_fetched += 1
            payload = fetch_result.data or {}

            total_count = payload.get("total_count", 0)
            incomplete = incomplete or payload.get("incomplete_results", False)
            page_items = payload.get("items", []) or []

            if not page_items:
                break

            items.extend(page_items)

            if len(page_items) < params["per_page"]:
                break
            if len(items) >= GitHubAPI.SEARCH_MAX_RESULTS:
                break

            params["page"] += 1

        if limit:
            items = items[:limit]

        return {
            "items": items,
            "total_count": total_count,
            "incomplete_results": incomplete,
            "capped": total_count > GitHubAPI.SEARCH_MAX_RESULTS,
        }

    # ---- GraphQL ----

    @staticmethod
    async def graphql(
        context: ExecutionContext,
        query: str,
        variables: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query or mutation against GitHub's GraphQL API.

        Used only where the REST API has no equivalent. GraphQL answers with
        HTTP 200 even when the operation failed, putting failures in an
        ``errors`` array, so this raises on that array rather than letting a
        caller treat a failed mutation as success.

        Returns the ``data`` object from the response.
        """
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        fetch_result = await context.fetch(
            GitHubAPI.GRAPHQL_URL,
            method="POST",
            json=payload,
            headers=GitHubAPI.get_headers(context),
        )
        response = fetch_result.data or {}

        errors = response.get("errors")
        if errors:
            messages = "; ".join(e.get("message", str(e)) for e in errors)
            raise ValueError(f"GitHub GraphQL error: {messages}")

        return response.get("data") or {}


# =============================================================================
# RESPONSE SHAPING
# =============================================================================


def _commit_signature(sig: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # GitHub may return a null author/committer for commits whose email isn't
    # linked to a GitHub user (deleted accounts, bot-authored commits, etc.).
    sig = sig or {}
    return {"name": sig.get("name"), "email": sig.get("email"), "date": sig.get("date")}


def _commit_summary(commit: Dict[str, Any]) -> Dict[str, Any]:
    inner = commit.get("commit") or {}
    return {
        "sha": commit.get("sha"),
        "author": _commit_signature(inner.get("author")),
        "committer": _commit_signature(inner.get("committer")),
        "message": inner.get("message"),
        "url": commit.get("html_url"),
    }

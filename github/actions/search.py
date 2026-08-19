"""
GitHub integration - Search actions - code, commits, issues, PRs, repositories, users, and orgs.

Seven actions sit on top of four Search API endpoints:

===========================  ==========================  ===============================
Action                       Endpoint                    Injected qualifier
===========================  ==========================  ===============================
``search_code``              ``GET /search/code``        --
``search_commits``           ``GET /search/commits``     --
``search_issues``            ``GET /search/issues``      ``is:issue``
``search_pull_requests``     ``GET /search/issues``      ``is:pr``
``search_repositories``      ``GET /search/repositories``--
``search_users``             ``GET /search/users``       ``type:user``
``search_orgs``              ``GET /search/users``       ``type:org``
===========================  ==========================  ===============================

There is no ``/search/orgs`` endpoint — it returns 404. Organizations are found
through ``/search/users`` with ``type:org``, which is why ``search_orgs`` and
``search_users`` share an endpoint the same way ``search_issues`` and
``search_pull_requests`` do.

Search is rate limited far more tightly than the rest of the REST API: 30
requests/minute for authenticated callers, and only 10/minute for code search.
Every query is also capped at 1000 results however far you paginate, so each
action returns ``total_count`` (the true match count) and ``capped`` alongside
the items.

Reference: https://docs.github.com/en/rest/search/search
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, Callable, Optional, Sequence

from github import github
from helpers import GitHubAPI, handle_github_errors, _commit_summary

# 100 results per page, so 10 pages covers the Search API's 1000-result ceiling.
# Without an explicit limit we stay at the helper's conservative default rather
# than burning the 30 req/min search budget on an open-ended query.
_RESULTS_PER_PAGE = 100
_DEFAULT_MAX_PAGES = 3
_MAX_PAGES_CAP = 10

# Qualifiers that already pin a /search/issues query to one result type. If the
# caller supplied any of these we leave the query alone rather than appending a
# second, contradictory one (e.g. "is:pr is:issue" matches nothing).
_ISSUE_TYPE_QUALIFIERS = (
    "is:issue",
    "is:pr",
    "is:pull-request",
    "type:issue",
    "type:pr",
    "type:pull-request",
)

# Same idea for /search/users, which returns personal accounts and
# organizations together unless the query narrows it.
_ACCOUNT_TYPE_QUALIFIERS = ("type:user", "type:org", "type:organization")


def _with_qualifier(query: str, qualifier: str, equivalents: Sequence[str]) -> str:
    """Append ``qualifier`` to ``query`` unless the caller already scoped it.

    ``equivalents`` lists every qualifier that answers the same question, so a
    user who writes their own ``is:pr`` isn't handed ``is:pr is:pr``.
    A leading ``-`` is stripped before comparing: an explicit ``-is:pr`` is
    still the caller taking control of the result type.
    """
    wanted = {token.lower() for token in equivalents}
    for token in (query or "").split():
        if token.lower().lstrip("-") in wanted:
            return query
    return f"{query} {qualifier}".strip() if query else qualifier


def _max_pages_for(limit: Optional[int]) -> int:
    """Pick a page budget that can actually satisfy ``limit``.

    ``GitHubAPI.search`` defaults to 3 pages to protect the search rate limit,
    which would silently truncate a caller asking for 500 results.
    """
    if not limit:
        return _DEFAULT_MAX_PAGES
    pages = -(-int(limit) // _RESULTS_PER_PAGE)
    return max(1, min(_MAX_PAGES_CAP, pages))


async def _run_search(
    context: ExecutionContext,
    endpoint: str,
    query: str,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Run one Search API query.

    Takes sort/order/limit explicitly rather than the whole ``inputs`` dict so
    each action reads them via ``inputs.get(...)`` inside ``execute``, which is
    the only place the config-sync checker looks for input usage.
    """
    return await GitHubAPI.search(
        context,
        endpoint,
        query,
        sort=sort,
        order=order,
        limit=limit,
        max_pages=_max_pages_for(limit),
    )


def _search_result(results: Dict[str, Any], shaper: Callable[[Dict[str, Any]], Dict[str, Any]]) -> ActionResult:
    """Wrap shaped items in the envelope every search action returns.

    ``total_count`` is GitHub's true match count, which can be far larger than
    the items returned — ``capped`` flags exactly that case so a workflow can
    tell "1000 results" from "the first 1000 of 50,000".
    """
    return ActionResult(
        data={
            "total_count": results.get("total_count", 0),
            "incomplete_results": results.get("incomplete_results", False),
            "capped": results.get("capped", False),
            "items": [shaper(item) for item in results.get("items", [])],
        },
        cost_usd=0.0,
    )


# =============================================================================
# RESULT SHAPING
# =============================================================================


def _repo_full_name(item: Dict[str, Any]) -> Optional[str]:
    """Best-effort ``owner/repo`` for a search hit.

    Code and commit hits embed a full repository object; issue and PR hits only
    carry ``repository_url`` (``https://api.github.com/repos/owner/repo``), so
    the name is recovered from the tail of that URL.
    """
    repository = item.get("repository") or {}
    if repository.get("full_name"):
        return repository["full_name"]

    repository_url = item.get("repository_url") or ""
    marker = "/repos/"
    if marker in repository_url:
        return repository_url.split(marker, 1)[1] or None
    return None


def _account_summary(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # GitHub nulls the actor on commits and issues from deleted accounts.
    if not user:
        return None
    return {"login": user.get("login"), "avatar_url": user.get("avatar_url")}


def _shape_repository(repo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "owner": _account_summary(repo.get("owner")),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "open_issues": repo.get("open_issues_count"),
        "topics": repo.get("topics") or [],
        "private": repo.get("private"),
        "updated_at": repo.get("updated_at"),
        "url": repo.get("html_url"),
    }


def _shape_issue(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "author": _account_summary(item.get("user")),
        "repository": _repo_full_name(item),
        "labels": [label.get("name") for label in (item.get("labels") or [])],
        "comments": item.get("comments"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "url": item.get("html_url"),
    }


def _shape_pull_request(item: Dict[str, Any]) -> Dict[str, Any]:
    # /search/issues returns PRs in the issue shape; the PR-only extras live in
    # the nested "pull_request" object rather than at the top level.
    pull_request = item.get("pull_request") or {}
    shaped = _shape_issue(item)
    shaped["draft"] = item.get("draft")
    shaped["merged_at"] = pull_request.get("merged_at")
    return shaped


def _shape_code(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": item.get("name"),
        "path": item.get("path"),
        "sha": item.get("sha"),
        "repository": _repo_full_name(item),
        "url": item.get("html_url"),
    }


def _shape_account(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "login": item.get("login"),
        "id": item.get("id"),
        "type": item.get("type"),
        "avatar_url": item.get("avatar_url"),
        "url": item.get("html_url"),
    }


def _shape_commit(item: Dict[str, Any]) -> Dict[str, Any]:
    shaped = _commit_summary(item)
    shaped["repository"] = _repo_full_name(item)
    return shaped


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("search_code")
class SearchCode(ActionHandler):
    """Search file contents across GitHub."""

    @handle_github_errors("search_code")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        results = await _run_search(
            context,
            "code",
            inputs["query"],
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_code)


@github.action("search_commits")
class SearchCommits(ActionHandler):
    """Search commit messages and metadata across GitHub."""

    @handle_github_errors("search_commits")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        results = await _run_search(
            context,
            "commits",
            inputs["query"],
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_commit)


@github.action("search_issues")
class SearchIssues(ActionHandler):
    """Search issues across GitHub, excluding pull requests."""

    @handle_github_errors("search_issues")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = _with_qualifier(inputs["query"], "is:issue", _ISSUE_TYPE_QUALIFIERS)
        results = await _run_search(
            context,
            "issues",
            query,
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_issue)


@github.action("search_pull_requests")
class SearchPullRequests(ActionHandler):
    """Search pull requests across GitHub."""

    @handle_github_errors("search_pull_requests")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = _with_qualifier(inputs["query"], "is:pr", _ISSUE_TYPE_QUALIFIERS)
        results = await _run_search(
            context,
            "issues",
            query,
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_pull_request)


@github.action("search_repositories")
class SearchRepositories(ActionHandler):
    """Search repositories across GitHub."""

    @handle_github_errors("search_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        results = await _run_search(
            context,
            "repositories",
            inputs["query"],
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_repository)


@github.action("search_users")
class SearchUsers(ActionHandler):
    """Search personal GitHub accounts."""

    @handle_github_errors("search_users")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = _with_qualifier(inputs["query"], "type:user", _ACCOUNT_TYPE_QUALIFIERS)
        results = await _run_search(
            context,
            "users",
            query,
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_account)


@github.action("search_orgs")
class SearchOrgs(ActionHandler):
    """Search GitHub organizations."""

    @handle_github_errors("search_orgs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        # There is no /search/orgs endpoint (404) — organizations are accounts
        # on /search/users, separated from people by the type: qualifier.
        query = _with_qualifier(inputs["query"], "type:org", _ACCOUNT_TYPE_QUALIFIERS)
        results = await _run_search(
            context,
            "users",
            query,
            sort=inputs.get("sort"),
            order=inputs.get("order"),
            limit=inputs.get("limit"),
        )
        return _search_result(results, _shape_account)

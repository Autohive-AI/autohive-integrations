"""
GitHub integration - Repository actions - create, read, update, delete, and list repositories.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("create_repository")
class CreateRepository(ActionHandler):
    """Create a new repository"""

    @handle_github_errors("create_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repo = await GitHubAPI.create_repository(
            context,
            name=inputs["name"],
            description=inputs.get("description"),
            private=inputs.get("private", False),
            auto_init=inputs.get("auto_init", False),
            gitignore_template=inputs.get("gitignore_template"),
            license_template=inputs.get("license_template"),
            org=inputs.get("org"),
            homepage=inputs.get("homepage"),
            has_issues=inputs.get("has_issues", True),
            has_projects=inputs.get("has_projects", True),
            has_wiki=inputs.get("has_wiki", True),
        )

        return ActionResult(
            data={
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo["description"],
                "private": repo["private"],
                "default_branch": repo["default_branch"],
                "created_at": repo["created_at"],
                "updated_at": repo["updated_at"],
                "pushed_at": repo["pushed_at"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"],
                "html_url": repo["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("get_repository")
class GetRepository(ActionHandler):
    """Get repository details"""

    @handle_github_errors("get_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repo_data = await GitHubAPI.get_repository(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data={
                "name": repo_data["name"],
                "full_name": repo_data["full_name"],
                "description": repo_data.get("description"),
                "default_branch": repo_data["default_branch"],
                "created_at": repo_data["created_at"],
                "updated_at": repo_data["updated_at"],
                "pushed_at": repo_data["pushed_at"],
                "language": repo_data.get("language"),
                "visibility": repo_data["visibility"],
                "private": repo_data["private"],
                "fork": repo_data["fork"],
                "forks_count": repo_data["forks_count"],
                "stargazers_count": repo_data["stargazers_count"],
                "watchers_count": repo_data["watchers_count"],
                "open_issues_count": repo_data["open_issues_count"],
                "url": repo_data["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("list_repositories")
class ListRepositories(ActionHandler):
    """List repositories"""

    @handle_github_errors("list_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_repositories(
            context,
            username=inputs.get("username"),
            org=inputs.get("org"),
            type=inputs.get("type", "all"),
            sort=inputs.get("sort", "updated"),
            direction=inputs.get("direction", "desc"),
        )

        return ActionResult(
            data=[
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo["description"],
                    "private": repo["private"],
                    "fork": repo["fork"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                    "pushed_at": repo["pushed_at"],
                    "language": repo.get("language"),
                    "default_branch": repo["default_branch"],
                    "visibility": repo.get("visibility"),
                    "url": repo["html_url"],
                }
                for repo in repos
            ],
            cost_usd=0.0,
        )


@github.action("update_repository")
class UpdateRepository(ActionHandler):
    """Update repository settings"""

    @handle_github_errors("update_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        update_data = {
            "name": inputs.get("name"),
            "description": inputs.get("description"),
            "private": inputs.get("private"),
            "has_issues": inputs.get("has_issues"),
            "has_wiki": inputs.get("has_wiki"),
        }

        repo = await GitHubAPI.update_repository(context, inputs["owner"], inputs["repo"], **update_data)

        return ActionResult(
            data={
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo["description"],
                "private": repo["private"],
                "has_issues": repo["has_issues"],
                "has_wiki": repo["has_wiki"],
                "updated_at": repo["updated_at"],
                "url": repo["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("delete_repository")
class DeleteRepository(ActionHandler):
    """Delete a repository"""

    @handle_github_errors("delete_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_repository(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data={"deleted": True, "repository": f"{inputs['owner']}/{inputs['repo']}"},
            cost_usd=0.0,
        )


@github.action("list_user_repositories")
class ListUserRepositories(ActionHandler):
    """List repositories for a specific user or authenticated user"""

    @handle_github_errors("list_user_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_user_repositories(
            context,
            username=inputs.get("username"),
            type=inputs.get("type", "all"),
            sort=inputs.get("sort", "updated"),
            direction=inputs.get("direction", "desc"),
        )

        return ActionResult(
            data=[
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description"),
                    "private": repo["private"],
                    "fork": repo["fork"],
                    "html_url": repo["html_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                    "language": repo.get("language"),
                    "stargazers_count": repo["stargazers_count"],
                    "forks_count": repo["forks_count"],
                    "open_issues_count": repo["open_issues_count"],
                    "default_branch": repo["default_branch"],
                }
                for repo in repos
            ],
            cost_usd=0.0,
        )


@github.action("list_organization_repositories")
class ListOrganizationRepositories(ActionHandler):
    """List repositories for a specific organization"""

    @handle_github_errors("list_organization_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_organization_repositories(
            context,
            org=inputs["org"],
            type=inputs.get("type", "all"),
            sort=inputs.get("sort", "updated"),
            direction=inputs.get("direction", "desc"),
        )

        return ActionResult(
            data=[
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description"),
                    "private": repo["private"],
                    "fork": repo["fork"],
                    "html_url": repo["html_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                    "language": repo.get("language"),
                    "stargazers_count": repo["stargazers_count"],
                    "forks_count": repo["forks_count"],
                    "open_issues_count": repo["open_issues_count"],
                    "default_branch": repo["default_branch"],
                }
                for repo in repos
            ],
            cost_usd=0.0,
        )


# =============================================================================
# EXTENDED REPOSITORY OPERATIONS
#
# These call the REST API directly rather than through ``GitHubAPI`` because
# they cover endpoints the shared client does not wrap yet.
# =============================================================================


async def _fork_repository(
    context: ExecutionContext,
    owner: str,
    repo: str,
    organization: Optional[str] = None,
    name: Optional[str] = None,
    default_branch_only: Optional[bool] = None,
) -> Dict[str, Any]:
    """Create a fork via ``POST /repos/{owner}/{repo}/forks``.

    Returns ``202 Accepted`` with the (freshly created) repository object.
    Forking runs asynchronously on GitHub's side, so the git objects of the
    returned repository may not be readable for a short while.
    """
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/forks"

    data: Dict[str, Any] = {}
    if organization:
        data["organization"] = organization
    if name:
        data["name"] = name
    if default_branch_only is not None:
        data["default_branch_only"] = default_branch_only

    return (await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))).data


async def _get_repository_tree(
    context: ExecutionContext,
    owner: str,
    repo: str,
    tree_sha: str,
    recursive: bool = False,
) -> Dict[str, Any]:
    """Fetch a git tree via ``GET /repos/{owner}/{repo}/git/trees/{tree_sha}``.

    ``tree_sha`` accepts a tree/commit SHA or a ref name (branch or tag), so
    slashes are preserved when escaping. GitHub treats *any* value of the
    ``recursive`` query parameter as "recurse" — including ``0`` and ``false``
    — so the parameter is omitted entirely for a shallow read.
    """
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/trees/{quote(tree_sha, safe='/')}"
    params = {"recursive": "1"} if recursive else None

    return (await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))).data


async def _list_repository_collaborators(
    context: ExecutionContext,
    owner: str,
    repo: str,
    affiliation: Optional[str] = None,
    permission: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List collaborators via ``GET /repos/{owner}/{repo}/collaborators``."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/collaborators"

    params: Dict[str, Any] = {}
    if affiliation:
        params["affiliation"] = affiliation
    if permission:
        params["permission"] = permission

    return await GitHubAPI.paginated_fetch(context, url, params, limit=limit)


def _collaborator_summary(collaborator: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a collaborator entry, tolerating fields GitHub omits."""
    permissions = collaborator.get("permissions") or {}

    return {
        "login": collaborator.get("login"),
        "id": collaborator.get("id"),
        "avatar_url": collaborator.get("avatar_url"),
        "url": collaborator.get("html_url"),
        "role_name": collaborator.get("role_name"),
        "permissions": {
            "pull": permissions.get("pull"),
            "triage": permissions.get("triage"),
            "push": permissions.get("push"),
            "maintain": permissions.get("maintain"),
            "admin": permissions.get("admin"),
        },
    }


@github.action("fork_repository")
class ForkRepository(ActionHandler):
    """Fork a repository into your account or an organization.

    Forking is asynchronous: GitHub answers 202 Accepted immediately, and the
    fork's git objects (branches, files, commits) may not be readable for a
    short period afterwards. Poll the fork with Get Repository before pushing
    to it rather than assuming it is ready the moment this action returns.
    """

    @handle_github_errors("fork_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        fork = await _fork_repository(
            context,
            inputs["owner"],
            inputs["repo"],
            organization=inputs.get("organization"),
            name=inputs.get("name"),
            default_branch_only=inputs.get("default_branch_only"),
        )

        fork_owner = fork.get("owner") or {}
        parent = fork.get("parent") or {}

        return ActionResult(
            data={
                "id": fork.get("id"),
                "name": fork.get("name"),
                "full_name": fork.get("full_name"),
                "owner": {"login": fork_owner.get("login"), "avatar_url": fork_owner.get("avatar_url")},
                "private": fork.get("private"),
                "fork": fork.get("fork"),
                "default_branch": fork.get("default_branch"),
                "created_at": fork.get("created_at"),
                "clone_url": fork.get("clone_url"),
                "ssh_url": fork.get("ssh_url"),
                "url": fork.get("html_url"),
                "source": parent.get("full_name") or f"{inputs['owner']}/{inputs['repo']}",
                "pending": True,
            },
            cost_usd=0.0,
        )


@github.action("get_repository_tree")
class GetRepositoryTree(ActionHandler):
    """List every file and directory recorded in a git tree.

    GitHub caps a tree response at 100,000 entries / 7 MB. When that cap is
    hit the response is silently cut short, so ``truncated`` is returned
    alongside the entries — treat a truncated result as a partial listing and
    walk the tree one directory at a time instead.
    """

    @handle_github_errors("get_repository_tree")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        tree_data = await _get_repository_tree(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["tree_sha"],
            recursive=bool(inputs.get("recursive", False)),
        )

        entries = tree_data.get("tree") or []

        return ActionResult(
            data={
                "sha": tree_data.get("sha"),
                "url": tree_data.get("url"),
                "truncated": bool(tree_data.get("truncated", False)),
                "entry_count": len(entries),
                "tree": [
                    {
                        "path": entry.get("path"),
                        "mode": entry.get("mode"),
                        "type": entry.get("type"),
                        "sha": entry.get("sha"),
                        "size": entry.get("size"),
                        "url": entry.get("url"),
                    }
                    for entry in entries
                ],
            },
            cost_usd=0.0,
        )


@github.action("list_repository_collaborators")
class ListRepositoryCollaborators(ActionHandler):
    """List the people who have access to a repository, with their permissions"""

    @handle_github_errors("list_repository_collaborators")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        collaborators = await _list_repository_collaborators(
            context,
            inputs["owner"],
            inputs["repo"],
            affiliation=inputs.get("affiliation"),
            permission=inputs.get("permission"),
            limit=inputs.get("limit"),
        )

        return ActionResult(
            data=[_collaborator_summary(collaborator) for collaborator in collaborators],
            cost_usd=0.0,
        )

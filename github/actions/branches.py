"""
GitHub integration - Branch actions - branches, branch protection, and branch comparison.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ActionError, ExecutionContext
from typing import Dict, Any

from github import github
from helpers import GitHubAPI, handle_github_errors, _commit_signature


@github.action("list_branches")
class ListBranches(ActionHandler):
    """List branches for a repository"""

    @handle_github_errors("list_branches")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        branches = await GitHubAPI.list_branches(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data=[
                {
                    "name": branch["name"],
                    "protected": branch["protected"],
                    "commit": {
                        "sha": branch["commit"]["sha"],
                        "url": branch["commit"]["url"],
                    },
                }
                for branch in branches
            ],
            cost_usd=0.0,
        )


@github.action("get_branch")
class GetBranch(ActionHandler):
    """Get branch details"""

    @handle_github_errors("get_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        branch = await GitHubAPI.get_branch(context, inputs["owner"], inputs["repo"], inputs["branch"])

        return ActionResult(
            data={
                "name": branch["name"],
                "protected": branch["protected"],
                "commit": {
                    "sha": branch["commit"]["sha"],
                    "url": branch["commit"]["url"],
                },
                "protection": branch.get("protection", {}),
            },
            cost_usd=0.0,
        )


@github.action("create_branch")
class CreateBranch(ActionHandler):
    """Create a new branch"""

    @handle_github_errors("create_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.create_branch(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["branch_name"],
            inputs["sha"],
        )

        return ActionResult(
            data={
                "ref": result["ref"],
                "url": result["url"],
                "object": {
                    "sha": result["object"]["sha"],
                    "type": result["object"]["type"],
                    "url": result["object"]["url"],
                },
            },
            cost_usd=0.0,
        )


@github.action("delete_branch")
class DeleteBranch(ActionHandler):
    """Delete a branch"""

    @handle_github_errors("delete_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_branch(context, inputs["owner"], inputs["repo"], inputs["branch"])

        return ActionResult(data={"deleted": True, "branch": inputs["branch"]}, cost_usd=0.0)


@github.action("get_branch_protection")
class GetBranchProtection(ActionHandler):
    """Get branch protection rules"""

    @handle_github_errors("get_branch_protection")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            protection = await GitHubAPI.get_branch_protection(
                context, inputs["owner"], inputs["repo"], inputs["branch"]
            )

            return ActionResult(
                data={
                    "enabled": True,
                    "required_status_checks": protection.get("required_status_checks", {}).get("contexts", [])
                    if protection.get("required_status_checks")
                    else [],
                    "enforce_admins": protection.get("enforce_admins", {}).get("enabled", False)
                    if protection.get("enforce_admins")
                    else False,
                    "required_pull_request_reviews": {
                        "required_approving_review_count": protection.get("required_pull_request_reviews", {}).get(
                            "required_approving_review_count", 0
                        )
                        if protection.get("required_pull_request_reviews")
                        else 0,
                        "dismiss_stale_reviews": protection.get("required_pull_request_reviews", {}).get(
                            "dismiss_stale_reviews", False
                        )
                        if protection.get("required_pull_request_reviews")
                        else False,
                        "require_code_owner_reviews": protection.get("required_pull_request_reviews", {}).get(
                            "require_code_owner_reviews", False
                        )
                        if protection.get("required_pull_request_reviews")
                        else False,
                    },
                    "restrictions": {
                        "users": [user["login"] for user in protection.get("restrictions", {}).get("users", [])]
                        if protection.get("restrictions")
                        else [],
                        "teams": [team["slug"] for team in protection.get("restrictions", {}).get("teams", [])]
                        if protection.get("restrictions")
                        else [],
                    },
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=f"Branch protection not available: {e}")


@github.action("diff_branch_to_branch")
class DiffBranchToBranch(ActionHandler):
    """Compare two branches"""

    @handle_github_errors("diff_branch_to_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        diff_data = await GitHubAPI.compare_branches(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["base_branch"],
            inputs["head_branch"],
        )

        return ActionResult(
            data={
                "status": diff_data.get("status"),
                "ahead_by": diff_data.get("ahead_by"),
                "behind_by": diff_data.get("behind_by"),
                "total_commits": diff_data.get("total_commits"),
                "commits": [
                    {
                        "sha": commit.get("sha"),
                        # GitHub returns a null author for commits whose email isn't
                        # linked to an account (deleted users, some bot commits), so
                        # this reuses the same guard list_commits got in 2.4.0.
                        "author": _commit_signature((commit.get("commit") or {}).get("author")),
                        "message": (commit.get("commit") or {}).get("message"),
                        "url": commit.get("html_url"),
                    }
                    for commit in diff_data.get("commits", [])
                ],
                "files": [
                    {
                        "filename": file["filename"],
                        "status": file["status"],
                        "additions": file["additions"],
                        "deletions": file["deletions"],
                        "changes": file["changes"],
                        "patch": file.get("patch") or "",
                    }
                    for file in diff_data.get("files", [])
                ],
            },
            cost_usd=0.0,
        )

"""
GitHub integration - Commit actions - commit history and individual commit details.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from github import github
from helpers import GitHubAPI, handle_github_errors, _commit_summary


@github.action("list_commits")
class ListCommits(ActionHandler):
    """List commits for a repository"""

    @handle_github_errors("list_commits")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        commits = await GitHubAPI.get_commits(
            context,
            inputs["owner"],
            inputs["repo"],
            sha=inputs.get("sha"),
            path=inputs.get("path"),
            since=inputs.get("since"),
            until=inputs.get("until"),
            max_pages=inputs.get("max_pages", 10),
        )

        return ActionResult(
            data=[_commit_summary(commit) for commit in commits],
            cost_usd=0.0,
        )


@github.action("get_commit")
class GetCommit(ActionHandler):
    """Get a specific commit"""

    @handle_github_errors("get_commit")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        commit = await GitHubAPI.get_commit(context, inputs["owner"], inputs["repo"], inputs["sha"])

        return ActionResult(
            data={
                **_commit_summary(commit),
                "stats": commit.get("stats", {}),
                "files": commit.get("files", []),
            },
            cost_usd=0.0,
        )

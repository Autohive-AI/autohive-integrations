"""
GitHub integration - Miscellaneous actions - rate limit and other platform utilities.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from github import github
from helpers import GitHubAPI, handle_github_errors


def _resource_usage(resource):
    """Shape one rate-limit resource block, tolerating GitHub omitting it."""
    if not resource:
        return None
    return {
        "limit": resource.get("limit"),
        "remaining": resource.get("remaining"),
        "reset": resource.get("reset"),
        "used": resource.get("used"),
    }


@github.action("get_rate_limit")
class GetRateLimit(ActionHandler):
    """Get current rate limit status"""

    @handle_github_errors("get_rate_limit")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        rate_limit = await GitHubAPI.get_rate_limit(context)
        resources = rate_limit.get("resources") or {}

        return ActionResult(
            data={
                # GitHub omits whole resource blocks depending on the token type -
                # `graphql` in particular is absent for some tokens - so a missing
                # block reports as null rather than raising a KeyError.
                name: _resource_usage(resources.get(name))
                for name in ("core", "search", "graphql")
            },
            cost_usd=0.0,
        )

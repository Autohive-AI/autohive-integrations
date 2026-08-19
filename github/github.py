"""
GitHub Integration for Autohive Platform

This module provides comprehensive GitHub API integration including:
- Repository management (CRUD operations)
- Issues, labels, sub-issues, and Pull Requests
- Branches, Tags, and Releases
- Workflows and Actions
- Search across code, commits, issues, PRs, repositories, users, and orgs
- Security alerts (code scanning, Dependabot, secret scanning, advisories)
- File operations and Gists

Action handlers live in the ``actions`` package; shared API plumbing lives in
``helpers``. Importing ``actions`` below registers every handler.

GitHub API Version: 2022-11-28
Reference: https://docs.github.com/en/rest
"""

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
)

from helpers import GitHubAPI

github = Integration.load()

import actions  # noqa: E402, F401  - imported for its handler-registration side effect


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


@github.connected_account()
class GitHubConnectedAccountHandler(ConnectedAccountHandler):
    """
    Handler for fetching connected GitHub account information.
    This is called once when a user authorizes the integration and the
    information is cached for display in the UI.
    """

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch GitHub user information for the connected account.

        Returns:
            ConnectedAccountInfo with user's email, username, name, avatar, etc.
            Falls back to an empty ConnectedAccountInfo when the GitHub API call
            fails (e.g., revoked/expired token, 5xx outage). The SDK does not
            catch exceptions raised from this handler, so letting one propagate
            crashes the Lambda with "Unhandled". Auth failures surface to the
            user the next time they run an action.
        """
        try:
            user_data = await GitHubAPI.get_user(context)
        except Exception as e:
            context.logger.warning(f"Failed to fetch GitHub account info: {e}")
            return ConnectedAccountInfo()

        name = user_data.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []

        return ConnectedAccountInfo(
            email=user_data.get("email"),
            username=user_data.get("login"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=user_data.get("avatar_url"),
            organization=user_data.get("company"),
            user_id=str(user_data.get("id")) if user_data.get("id") else None,
        )

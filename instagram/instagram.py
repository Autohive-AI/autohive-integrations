"""
Instagram Business/Creator Integration for Autohive

This module provides comprehensive Instagram management including:
- Account information retrieval
- Media publishing (images, videos, reels, carousels, stories)
- Media retrieval and deletion
- Comment management (read, reply, hide, delete)
- Account and media insights/analytics
- Mentions and hashtag discovery
- Direct messaging

All actions use the Instagram Graph API v24.0.
"""

from autohive_integrations_sdk import Integration, ExecutionContext, ConnectedAccountHandler, ConnectedAccountInfo
import os

from helpers import INSTAGRAM_GRAPH_API_BASE

config_path = os.path.join(os.path.dirname(__file__), "config.json")
instagram = Integration.load(config_path)

# Import actions to register handlers
import actions  # noqa: F401 - registers action handlers


@instagram.connected_account()
class InstagramConnectedAccountHandler(ConnectedAccountHandler):
    """
    Handler for fetching connected Instagram account information.
    This is called once when a user authorizes the integration and the
    information is cached for display in the UI.
    """

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch Instagram user information for the connected account.

        Returns:
            ConnectedAccountInfo with user's username, name, avatar, etc.
        """
        fields = ",".join([
            "id",
            "username",
            "name",
            "profile_picture_url"
        ])

        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/me",
            method="GET",
            params={"fields": fields}
        )

        name = response.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []

        return ConnectedAccountInfo(
            username=response.get("username"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=response.get("profile_picture_url"),
            user_id=response.get("id")
        )

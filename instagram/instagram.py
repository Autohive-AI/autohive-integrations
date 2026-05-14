import os
import sys

# Ensure this directory is in sys.path so subpackages can resolve helpers and instagram
sys.path.insert(0, os.path.dirname(__file__))

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
)

from helpers import INSTAGRAM_GRAPH_API_BASE

instagram = Integration.load(os.path.join(os.path.dirname(__file__), "config.json"))

sys.modules.setdefault("instagram", sys.modules[__name__])

import actions  # noqa: F401, E402 - registers action handlers


@instagram.connected_account()
class InstagramConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        fields = ",".join(["id", "username", "name", "profile_picture_url"])
        response = await context.fetch(f"{INSTAGRAM_GRAPH_API_BASE}/me", method="GET", params={"fields": fields})
        data = response.data
        name = data.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []
        return ConnectedAccountInfo(
            username=data.get("username"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=data.get("profile_picture_url"),
            user_id=data.get("id"),
        )

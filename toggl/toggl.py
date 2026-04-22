from typing import Dict, Any
import base64
from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError

# Create the integration using the config.json
toggl = Integration.load()


def _basic_auth_header_for_api_token(api_token: str) -> Dict[str, str]:
    # Per Toggl docs: use Basic auth with username=api_token and password="api_token"
    token_pair = f"{api_token}:api_token".encode("utf-8")
    encoded = base64.b64encode(token_pair).decode("ascii")
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


@toggl.action("create_time_entry")
class CreateTimeEntry(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_token = context.auth.get("credentials").get("api_token")
        if not api_token:
            return ActionError(message="Toggl API token is required in auth (field 'api_token').")

        workspace_id = inputs["workspace_id"]

        body: Dict[str, Any] = {
            # Required by Toggl when creating a TE
            "created_with": "autohive-integrations",
            # Mirror incoming fields if present
            "description": inputs.get("description"),
            "start": inputs.get("start"),
            "stop": inputs.get("stop"),
            "duration": inputs.get("duration"),
            "project_id": inputs.get("project_id"),
            "task_id": inputs.get("task_id"),
            "billable": inputs.get("billable", False),
            "tags": inputs.get("tags"),
            "tag_ids": inputs.get("tag_ids"),
            "user_id": inputs.get("user_id"),
            "workspace_id": workspace_id,
        }

        # Remove keys with None values to avoid API complaints
        body = {k: v for k, v in body.items() if v is not None}

        headers = _basic_auth_header_for_api_token(api_token)
        url = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries"

        try:
            resp = await context.fetch(url, method="POST", headers=headers, json=body)
            return ActionResult(data=resp.data, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))

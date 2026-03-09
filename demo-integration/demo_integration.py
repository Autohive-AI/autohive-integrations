from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Dict, Any

demo_integration = Integration.load()

BASE_URL = "https://api.example.com/v1"


def get_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build request headers with authentication."""
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@demo_integration.action("get_data")
class GetDataAction(ActionHandler):
    """Retrieves data from the API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get("limit", 10)
            headers = get_headers(context)

            response = await context.fetch(
                f"{BASE_URL}/data?limit={limit}", method="GET", headers=headers
            )

            return ActionResult(data={"result": True, "data": response}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

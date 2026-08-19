"""
GitHub integration - Webhook actions - repository webhook management.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("create_webhook")
class CreateWebhook(ActionHandler):
    """Create a webhook"""

    @handle_github_errors("create_webhook")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webhook = await GitHubAPI.create_webhook(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["url"],
            inputs["events"],
            content_type=inputs.get("content_type", "json"),
            secret=inputs.get("secret"),
            active=inputs.get("active", True),
        )

        return ActionResult(
            data={
                "id": webhook["id"],
                "name": webhook["name"],
                "active": webhook["active"],
                "events": webhook["events"],
                "config": {
                    "url": webhook["config"]["url"],
                    "content_type": webhook["config"]["content_type"],
                },
                "created_at": webhook["created_at"],
                "updated_at": webhook["updated_at"],
                "url": webhook["url"],
            },
            cost_usd=0.0,
        )


@github.action("list_webhooks")
class ListWebhooks(ActionHandler):
    """List webhooks for a repository"""

    @handle_github_errors("list_webhooks")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webhooks = await GitHubAPI.list_webhooks(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data=[
                {
                    "id": webhook["id"],
                    "name": webhook["name"],
                    "active": webhook["active"],
                    "events": webhook["events"],
                    "config": {
                        "url": webhook["config"]["url"],
                        "content_type": webhook["config"]["content_type"],
                    },
                    "created_at": webhook["created_at"],
                    "updated_at": webhook["updated_at"],
                    "url": webhook["url"],
                }
                for webhook in webhooks
            ],
            cost_usd=0.0,
        )


@github.action("delete_webhook")
class DeleteWebhook(ActionHandler):
    """Delete a webhook"""

    @handle_github_errors("delete_webhook")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_webhook(context, inputs["owner"], inputs["repo"], inputs["hook_id"])

        return ActionResult(data={"deleted": True, "hook_id": inputs["hook_id"]}, cost_usd=0.0)

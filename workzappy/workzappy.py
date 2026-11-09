import asyncio

import aiohttp
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, HTTPError, Integration

workzappy = Integration.load()
BASE_URL = "https://app.workzappy.com/openapi/api"
NO_RETRY = 1_000


@workzappy.action("create_task")
class CreateTask(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        credentials = context.auth["credentials"]
        try:
            auth = await context.fetch(
                f"{BASE_URL}/authorize/access-permanent-token",
                method="POST",
                json={"clientId": credentials["client_id"], "secretKey": credentials["secret_key"]},
            )
        except (HTTPError, aiohttp.ClientError, asyncio.TimeoutError):
            return ActionError(message="Could not authenticate with WorkZappy. Check the connection and credentials.")

        auth_data = _success_data(auth.data)
        token = auth_data.get("accessToken")
        if not isinstance(token, str) or not token:
            return ActionError(message="WorkZappy authentication failed. Check your personal API credentials.")

        fields = {"summary": inputs["summary"]}
        if (description := inputs.get("description")) is not None:
            fields["description"] = description

        try:
            result = await context.fetch(
                f"{BASE_URL}/issue/add",
                method="POST",
                headers={"accessToken": token},
                json={"projectId": inputs["project_id"], "issueTypeId": inputs["task_type_id"], "data": fields},
                # A lost response can hide a successful write. Avoid retrying the POST.
                retry_count=NO_RETRY,
            )
        except (HTTPError, aiohttp.ClientError, asyncio.TimeoutError):
            return ActionError(
                message="WorkZappy did not confirm creation. Check the destination project before retrying."
            )

        task_id = _success_data(result.data).get("id")
        if type(task_id) is not int or task_id < 1:
            return ActionError(
                message="WorkZappy did not confirm creation. Check the project and task type before retrying."
            )
        return ActionResult(data={"task_id": task_id})


def _success_data(payload: object) -> dict:
    if isinstance(payload, dict) and payload.get("code") == "0" and isinstance(payload.get("data"), dict):
        return payload["data"]
    return {}

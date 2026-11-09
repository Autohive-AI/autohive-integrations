import asyncio

import aiohttp
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, HTTPError, Integration

workzappy = Integration.load()
BASE_URL = "https://app.workzappy.com/openapi/api"
NO_RETRY = 1_000


@workzappy.action("create_task")
class CreateTask(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        token = await _access_token(context)
        if isinstance(token, ActionError):
            return token

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


async def _access_token(context: ExecutionContext) -> str | ActionError:
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

    return token


async def _request(
    context: ExecutionContext,
    path: str,
    method: str,
    output: str,
    expected_type: type,
    *,
    params: dict | None = None,
    body: dict | None = None,
    write: bool = False,
) -> ActionResult | ActionError:
    token = await _access_token(context)
    if isinstance(token, ActionError):
        return token

    try:
        response = await context.fetch(
            f"{BASE_URL}{path}",
            method=method,
            headers={"accessToken": token},
            params=params,
            json=body,
            retry_count=NO_RETRY if write else 0,
        )
    except (HTTPError, aiohttp.ClientError, asyncio.TimeoutError):
        return _request_error(write)

    payload = response.data
    if not isinstance(payload, dict) or payload.get("code") != "0":
        return _request_error(write)
    data = payload.get("data")
    if not isinstance(data, expected_type) or (write and isinstance(data, dict) and data.get("success") is False):
        return _request_error(write)
    return ActionResult(data={output: data})


def _request_error(write: bool) -> ActionError:
    if write:
        return ActionError(message="WorkZappy did not confirm the change. Check the destination before retrying.")
    return ActionError(message="WorkZappy could not complete the request. Check the inputs and API key permissions.")


@workzappy.action("list_projects")
class ListProjects(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        return await _request(context, "/project/list", "GET", "projects", list)


@workzappy.action("get_project")
class GetProject(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        return await _request(context, "/project/get", "GET", "project", dict, params=payload)


@workzappy.action("list_project_members")
class ListProjectMembers(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        return await _request(context, "/user/project-user-list", "GET", "members", list, params=payload)


@workzappy.action("list_task_types")
class ListTaskTypes(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        return await _request(context, "/issue/type-list", "GET", "task_types", list, params=payload)


@workzappy.action("get_task_scheme")
class GetTaskScheme(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"], "issueTypeId": inputs["task_type_id"]}
        return await _request(context, "/issue/issue-scheme", "GET", "scheme", dict, params=payload)


@workzappy.action("get_task")
class GetTask(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"id": inputs["task_id"]}
        return await _request(context, "/issue/v2/get", "GET", "task", dict, params=payload)


@workzappy.action("search_tasks")
class SearchTasks(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        if (value := inputs.get("summary")) is not None:
            payload["summary"] = value
        if (value := inputs.get("page_number")) is not None:
            payload["pageNumber"] = value
        if (value := inputs.get("page_size")) is not None:
            payload["pageSize"] = value
        return await _request(context, "/issue/v2/page", "POST", "page", dict, body=payload)


@workzappy.action("update_task")
class UpdateTask(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"id": inputs["task_id"], "data": inputs["fields"]}
        return await _request(context, "/issue/update", "PATCH", "result", dict, body=payload, write=True)


@workzappy.action("remove_task")
class RemoveTask(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"id": inputs["task_id"]}
        return await _request(context, "/issue/remove", "DELETE", "result", dict, body=payload, write=True)


@workzappy.action("list_task_comments")
class ListTaskComments(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"commentModule": "issue", "linkId": inputs["task_id"]}
        if (value := inputs.get("page_number")) is not None:
            payload["pageNumber"] = value
        if (value := inputs.get("page_size")) is not None:
            payload["pageSize"] = value
        return await _request(context, "/comment/page", "POST", "page", dict, body=payload)


@workzappy.action("add_task_comment")
class AddTaskComment(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"commentModule": "issue", "linkId": inputs["task_id"], "plainContent": inputs["content"]}
        if (value := inputs.get("parent_comment_id")) is not None:
            payload["commentId"] = value
        payload["content"] = inputs["content"]
        return await _request(context, "/comment/add", "POST", "comment", dict, body=payload, write=True)


@workzappy.action("list_project_phases")
class ListProjectPhases(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        return await _request(context, "/sprint/list-with-count", "POST", "phases", list, body=payload)


@workzappy.action("list_project_tags")
class ListProjectTags(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectId": inputs["project_id"]}
        return await _request(context, "/tag/list", "POST", "tags", list, body=payload)


@workzappy.action("create_project")
class CreateProject(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"projectName": inputs["project_name"], "templateCode": inputs["template_code"]}
        if (value := inputs.get("description")) is not None:
            payload["description"] = value
        if (value := inputs.get("leader_id")) is not None:
            payload["leaderId"] = value
        return await _request(context, "/project/add", "POST", "project", dict, body=payload, write=True)


@workzappy.action("update_project")
class UpdateProject(ActionHandler):
    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult | ActionError:
        payload = {"id": inputs["project_id"], "data": inputs["fields"]}
        return await _request(context, "/project/update", "PATCH", "result", dict, body=payload, write=True)

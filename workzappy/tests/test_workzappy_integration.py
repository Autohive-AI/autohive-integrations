from uuid import uuid4

import pytest
from autohive_integrations_sdk import ResultType

from ..workzappy import workzappy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def run_action(context, action, **inputs):
    result = await workzappy.execute_action(action, inputs, context)
    assert result.type == ResultType.ACTION, f"{action} failed. Check credentials, permissions, and test data."
    return result.result.data


@pytest.fixture
def live_id(env_credentials):
    def get(name):
        value = env_credentials(f"WORKZAPPY_{name}")
        if not value:
            pytest.skip(f"WORKZAPPY_{name} is required")
        return int(value)

    return get


async def test_list_projects_with_live_credentials(live_auth):
    async with live_auth:
        result = await run_action(live_auth, "list_projects")
    assert isinstance(result["projects"], list)


@pytest.mark.parametrize(
    "action, output, kind",
    [
        ("get_project", "project", dict),
        ("list_project_members", "members", list),
        ("list_task_types", "task_types", list),
        ("search_tasks", "page", dict),
        ("list_project_phases", "phases", list),
        ("list_project_tags", "tags", list),
    ],
)
async def test_project_reads(live_auth, live_id, action, output, kind):
    project_id = live_id("PROJECT_ID")
    async with live_auth:
        result = await run_action(live_auth, action, project_id=project_id)
    assert isinstance(result[output], kind)
    if action == "get_project":
        assert result[output]["id"] == project_id
    if action == "search_tasks":
        assert isinstance(result[output]["list"], list)


async def test_get_task_scheme(live_auth, live_id):
    project_id = live_id("PROJECT_ID")
    task_type_id = live_id("TASK_TYPE_ID")
    async with live_auth:
        result = await run_action(live_auth, "get_task_scheme", project_id=project_id, task_type_id=task_type_id)
    assert isinstance(result["scheme"]["fields"], list)


@pytest.mark.parametrize("action, output", [("get_task", "task"), ("list_task_comments", "page")])
async def test_task_reads(live_auth, live_id, action, output):
    task_id = live_id("TASK_ID")
    async with live_auth:
        result = await run_action(live_auth, action, task_id=task_id)
    if action == "get_task":
        assert result[output]["id"] == task_id
    else:
        assert isinstance(result[output]["list"], list)


@pytest.fixture
def enable_writes(env_credentials):
    if env_credentials("WORKZAPPY_RUN_WRITE_TESTS") != "1":
        pytest.skip("Set WORKZAPPY_RUN_WRITE_TESTS=1 for writes against a disposable workspace")


@pytest.mark.destructive
async def test_task_write_lifecycle(live_auth, live_id, enable_writes):
    project_id = live_id("PROJECT_ID")
    task_type_id = live_id("TASK_TYPE_ID")
    summary = f"Autohive integration test {uuid4().hex}"
    async with live_auth:
        created = await run_action(
            live_auth,
            "create_task",
            project_id=project_id,
            task_type_id=task_type_id,
            summary=summary,
            status_id=live_id("STATUS_ID"),
        )
        task_id = created["task_id"]
        try:
            updated = await run_action(
                live_auth, "update_task", task_id=task_id, fields={"summary": f"{summary} updated"}
            )
            assert updated["result"]["success"] is True
            task = await run_action(live_auth, "get_task", task_id=task_id)
            assert task["task"]["singleFields"]["summary"]["value"] == f"{summary} updated"
            comment = await run_action(live_auth, "add_task_comment", task_id=task_id, content=summary)
            assert comment["comment"]["id"]
        finally:
            removed = await run_action(live_auth, "remove_task", task_id=task_id)
            assert removed["result"]["success"] is True


@pytest.mark.destructive
async def test_project_write_lifecycle(live_auth, env_credentials, live_id, enable_writes):
    template_code = env_credentials("WORKZAPPY_PROJECT_TEMPLATE_CODE")
    if not template_code:
        pytest.skip("WORKZAPPY_PROJECT_TEMPLATE_CODE is required")
    name = f"Autohive integration test {uuid4().hex[:12]}"
    async with live_auth:
        created = await run_action(
            live_auth,
            "create_project",
            project_name=name,
            template_code=template_code,
            leader_id=live_id("PROJECT_LEADER_ID"),
        )
        project_id = created["project"]["id"]
        updated = await run_action(
            live_auth, "update_project", project_id=project_id, fields={"pname": f"{name} updated"}
        )
        assert updated["result"]["success"] is True
        project = await run_action(live_auth, "get_project", project_id=project_id)
        assert project["project"]["projectName"] == f"{name} updated"

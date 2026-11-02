"""Sandbox checks. Writes require both the destructive marker and an explicit opt-in."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from autohive_integrations_sdk import ExecutionContext, RateLimitError, ResultType
from procore.procore import procore

CONFIG = json.loads(Path(__file__).parents[1].joinpath("config.json").read_text())

pytestmark = pytest.mark.integration


@pytest.fixture
async def sandbox():
    token = os.environ.get("PROCORE_ACCESS_TOKEN")
    company_id = os.environ.get("PROCORE_COMPANY_ID")
    project_id = os.environ.get("PROCORE_PROJECT_ID")
    if not token or not company_id or not project_id:
        pytest.skip("Set PROCORE_ACCESS_TOKEN, PROCORE_COMPANY_ID, and PROCORE_PROJECT_ID for a sandbox")
    auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
    async with ExecutionContext(auth=auth) as context:
        yield context, {"environment": "sandbox", "company_id": int(company_id), "project_id": int(project_id)}


async def execute(sandbox, name, **inputs):
    context, defaults = sandbox
    properties = CONFIG["actions"][name]["input_schema"]["properties"]
    action_defaults = {key: value for key, value in defaults.items() if key in properties}
    try:
        result = await procore.execute_action(name, {**action_defaults, **inputs}, context)
    except RateLimitError as error:
        # Only retry an explicit quota rejection, never an ambiguous write failure.
        await asyncio.sleep(max(0, error.retry_after))
        result = await procore.execute_action(name, {**action_defaults, **inputs}, context)
    assert result.type == ResultType.ACTION, f"{name} did not return an action result"
    return result.result.data


@pytest.mark.parametrize(
    "name",
    [
        "list_companies",
        "list_projects",
        "get_project",
        "list_rfis",
        "list_submittals",
        "list_project_users",
        "list_project_vendors",
        "list_locations",
        "list_submittal_types",
        "list_submittal_statuses",
        "get_document_root",
    ],
)
async def test_sandbox_read_actions(sandbox, name):
    data = await execute(sandbox, name)
    if name.startswith("list_"):
        assert isinstance(data["items"], list)
        assert all(isinstance(item, dict) and "id" in item for item in data["items"])
    else:
        assert isinstance(data["result"]["id"], int)


async def find_file(sandbox, root):
    """Search a bounded number of folders, including nested sample documents."""
    pending = [root]
    seen = set()
    while pending and len(seen) < 50:
        candidate = pending.pop()
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        folder = (
            candidate
            if candidate is root
            else (await execute(sandbox, "get_folder", folder_id=candidate["id"]))["result"]
        )
        if folder.get("files"):
            return folder["files"][0]["id"]
        children = [child for child in folder.get("folders", []) if child.get("has_children")]
        # Prefer folders advertising files, reducing API calls on seeded sandboxes.
        pending.extend(sorted(children, key=lambda child: bool(child.get("has_children_files"))))
    pytest.skip("Sandbox project needs an existing document file (searched at most 50 folders)")


@pytest.mark.destructive
async def test_all_actions_against_disposable_sandbox_records(sandbox):
    if os.environ.get("PROCORE_RUN_WRITE_TESTS") != "1":
        pytest.skip("Set PROCORE_RUN_WRITE_TESTS=1 to create disposable sandbox records")
    called = set()

    async def call(name, **inputs):
        data = await execute(sandbox, name, **inputs)
        called.add(name)
        return data

    # Discover all required existing fixtures before creating any records.
    await call("list_companies")
    await call("list_projects")
    original = await call("get_project")
    assert original["result"]["id"] == sandbox[1]["project_id"]
    users = await call("list_project_users")
    vendors = await call("list_project_vendors")
    if not users["items"] or not vendors["items"]:
        pytest.skip("Sandbox project needs at least one user and vendor")
    uid = users["items"][0]["id"]
    vid = vendors["items"][0]["id"]
    assert (await call("get_project_user", user_id=uid))["result"]["id"] == uid
    assert (await call("get_project_vendor", vendor_id=vid))["result"]["id"] == vid
    for name in ["list_locations", "list_submittal_types", "list_submittal_statuses", "list_rfis", "list_submittals"]:
        await call(name)
    root = (await call("get_document_root"))["result"]
    fid = await find_file(sandbox, root)
    assert (await call("get_file", file_id=fid))["result"]["id"] == fid
    tag = f"Autohive integration test {uuid4().hex[:12]}"

    # The connector has no folder delete action; this uniquely named empty folder remains.
    folder = (await call("create_folder", folder={"name": tag}))["result"]
    folder_id = folder["id"]
    assert (await call("get_folder", folder_id=folder_id))["result"]["name"] == tag

    project = (await call("create_project", project={"name": tag}))["result"]
    try:
        updated = await call("update_project", project_id=project["id"], project={"name": tag + " updated"})
        assert updated["result"]["name"] == tag + " updated"
    finally:
        await execute(sandbox, "update_project", project_id=project["id"], project={"active": False})

    rfi = (
        await call(
            "create_rfi",
            rfi={
                "subject": tag,
                "rfi_manager_id": uid,
                "draft": True,
                "question": {"body": "Disposable sandbox integration test"},
            },
        )
    )["result"]
    rid = rfi["id"]
    try:
        assert (await call("get_rfi", rfi_id=rid))["result"]["subject"] == tag
        updated = await call("update_rfi", rfi_id=rid, rfi={"subject": tag + " updated"})
        assert updated["result"]["subject"] == tag + " updated"
        await call("recycle_rfi", rfi_id=rid)
        await call("restore_rfi", rfi_id=rid)
        # Restore can return 204; confirm state with a subsequent read instead.
        assert (await call("get_rfi", rfi_id=rid))["result"]["id"] == rid
    finally:
        await execute(sandbox, "recycle_rfi", rfi_id=rid)

    number = uuid4().hex[:8]
    submittal = (
        await call(
            "create_submittal",
            send_emails=False,
            submittal={
                "number": number,
                "title": tag,
                "submittal_manager_id": uid,
            },
        )
    )["result"]
    sid = submittal["id"]
    try:
        assert (await call("get_submittal", submittal_id=sid))["result"]["title"] == tag
        updated = await call(
            "update_submittal",
            submittal_id=sid,
            send_emails=False,
            submittal={"number": number, "title": tag + " updated"},
        )
        assert updated["result"]["title"] == tag + " updated"
        assert isinstance((await call("list_submittal_revisions", submittal_id=sid))["items"], list)
        assert isinstance((await call("get_submittal_workflow", submittal_id=sid))["result"], dict)
    finally:
        await call("delete_submittal", submittal_id=sid)

    # An action added to config must also be exercised here before claiming full live coverage.
    assert called == set(CONFIG["actions"])

"""
End-to-end integration tests for the GUIDEcx integration.

These call the real GUIDEcx Open API (v3) and require a valid bearer token in
the GUIDECX_API_TOKEN environment variable (via .env or export). Generate one
in the GUIDEcx web app under Company Settings -> Open API; creating tokens
requires a workspace admin role.

Run read-only tests (safe — default):
    pytest guidecx/tests/test_guidecx_integration.py -m "integration and not destructive"

Run destructive tests (UPDATE a real task, POST a real note — run deliberately
against a sandbox workspace, never in CI, never by reviewers):
    pytest guidecx/tests/test_guidecx_integration.py -m "integration and destructive"

Never runs in CI: the default marker filter (-m unit) excludes these, and the
test_*_integration.py filename is not matched by python_files in pyproject.toml.

Environment variables (see root .env.example):
    GUIDECX_API_TOKEN            (required)
    GUIDECX_TEST_PROJECT_ID      (optional — otherwise the first project the
                                  token can see is used)
    GUIDECX_TEST_CUSTOMER_ID     (optional — otherwise a customer ID is
                                  derived from the first project that has a
                                  customer, via its _links.customer path)
    GUIDECX_TEST_TASK_ID         (required for the destructive tests only —
                                  they refuse to run without an explicit target)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import aiohttp  # noqa: E402
import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType  # noqa: E402

from guidecx.guidecx import guidecx  # noqa: E402

pytestmark = pytest.mark.integration

API_TOKEN = os.environ.get("GUIDECX_API_TOKEN", "")
TEST_PROJECT_ID = os.environ.get("GUIDECX_TEST_PROJECT_ID", "")
TEST_TASK_ID = os.environ.get("GUIDECX_TEST_TASK_ID", "")
TEST_CUSTOMER_ID = os.environ.get("GUIDECX_TEST_CUSTOMER_ID", "")

skip_if_no_creds = pytest.mark.skipif(not API_TOKEN, reason="GUIDECX_API_TOKEN required")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with a GUIDEcx token.

    The integration builds its own Authorization header from context.auth, so
    unlike the platform-OAuth integrations nothing needs to be injected here —
    the fixture only has to perform real HTTP and raise HTTPError on non-2xx to
    mirror the SDK's fetch contract.
    """

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, body=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, data=body, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {"api_token": API_TOKEN},
    }
    return ctx


async def resolve_project_id(live_context):
    """Return a usable project ID — the env override, else the first one."""
    if TEST_PROJECT_ID:
        return TEST_PROJECT_ID
    result = await guidecx.execute_action("list_projects", {"limit": 1}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"could not list projects: {result.result}")
    projects = result.result.data.get("projects", [])
    if not projects:
        pytest.skip("No projects visible to this token")
    return str(projects[0]["id"])


# ---- Read-Only Tests ----


@skip_if_no_creds
class TestListProjects:
    @pytest.mark.asyncio
    async def test_returns_projects(self, live_context):
        result = await guidecx.execute_action("list_projects", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert isinstance(data["projects"], list)
        assert isinstance(data["has_more"], bool)

    @pytest.mark.asyncio
    async def test_respects_limit(self, live_context):
        result = await guidecx.execute_action("list_projects", {"limit": 1}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert len(result.result.data["projects"]) <= 1

    @pytest.mark.asyncio
    async def test_offset_paginates(self, live_context):
        first = await guidecx.execute_action("list_projects", {"limit": 1, "offset": 0}, live_context)
        assert first.type == ResultType.ACTION, first.result
        if not first.result.data["has_more"]:
            pytest.skip("Workspace has only one project; nothing to paginate")

        second = await guidecx.execute_action("list_projects", {"limit": 1, "offset": 1}, live_context)

        assert second.type == ResultType.ACTION, second.result
        assert second.result.data["projects"][0]["id"] != first.result.data["projects"][0]["id"]

    @pytest.mark.asyncio
    async def test_status_category_filter_accepted(self, live_context):
        result = await guidecx.execute_action(
            "list_projects", {"status_category": ["IN_PROGRESS"], "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION, result.result
        for project in result.result.data["projects"]:
            assert project.get("statusCategory") == "IN_PROGRESS"


@skip_if_no_creds
class TestGetProject:
    @pytest.mark.asyncio
    async def test_returns_the_requested_project(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("get_project", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert result.result.data["project"]["id"] == project_id

    @pytest.mark.asyncio
    async def test_unknown_id_returns_error(self, live_context):
        result = await guidecx.execute_action(
            "get_project", {"project_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


@skip_if_no_creds
class TestListMilestones:
    @pytest.mark.asyncio
    async def test_returns_milestones_for_a_project(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_milestones", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["milestones"], list)


@skip_if_no_creds
class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_for_a_project(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_tasks", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["tasks"], list)

    @pytest.mark.asyncio
    async def test_status_category_filter_accepted(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "list_tasks", {"project_id": project_id, "status_category": ["DONE"], "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION, result.result
        for task in result.result.data["tasks"]:
            assert task.get("statusCategory") == "DONE"

    @pytest.mark.asyncio
    async def test_type_filter_accepted(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "list_tasks", {"project_id": project_id, "type_filter": "TASK"}, live_context
        )

        assert result.type == ResultType.ACTION, result.result


async def resolve_customer_id(live_context):
    """Return a usable customer ID — the env override, else one discovered.

    Projects have no ``customerId`` field, but a project that has a customer
    exposes ``_links.customer`` as ``/api/v3/customers/{customerId}``, so the ID
    is the last path segment. Projects with no customer omit the link.
    """
    if TEST_CUSTOMER_ID:
        return TEST_CUSTOMER_ID

    result = await guidecx.execute_action("list_projects", {"limit": 100}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"could not list projects: {result.result}")

    for project in result.result.data["projects"]:
        link = (project.get("_links") or {}).get("customer")
        if link:
            return str(link).rstrip("/").rsplit("/", 1)[-1]

    pytest.skip("No project in this workspace has an associated customer")
    # pytest.skip raises, so this is unreachable. It is spelled out so the
    # function has no implicit fall-through return: an implicit None here would
    # be indistinguishable from a real customer ID going missing.
    raise AssertionError("unreachable: pytest.skip always raises")


@skip_if_no_creds
class TestGetCustomer:
    @pytest.mark.asyncio
    async def test_returns_the_requested_customer(self, live_context):
        customer_id = await resolve_customer_id(live_context)

        result = await guidecx.execute_action("get_customer", {"customer_id": customer_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert result.result.data["customer"]["id"] == customer_id

    @pytest.mark.asyncio
    async def test_unknown_id_returns_error(self, live_context):
        result = await guidecx.execute_action(
            "get_customer", {"customer_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


@skip_if_no_creds
class TestAuthFailure:
    @pytest.mark.asyncio
    async def test_bad_token_returns_error(self, live_context):
        live_context.auth = {"auth_type": "Custom", "credentials": {"api_token": "not-a-real-token"}}  # nosec B105 - test fixture, not a real credential

        result = await guidecx.execute_action("list_projects", {}, live_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Destructive Tests ----
#
# These modify real GUIDEcx data. They require GUIDECX_TEST_TASK_ID to be set
# explicitly so they can never touch an arbitrary task picked at runtime.
# Only run with: pytest -m "integration and destructive"

skip_if_no_task = pytest.mark.skipif(not TEST_TASK_ID, reason="GUIDECX_TEST_TASK_ID required for destructive tests")


@skip_if_no_creds
@skip_if_no_task
@pytest.mark.destructive
class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_priority_and_restore(self, live_context):
        project_id = await resolve_project_id(live_context)

        before = await guidecx.execute_action("list_tasks", {"project_id": project_id, "limit": 100}, live_context)
        assert before.type == ResultType.ACTION, before.result
        original = next((t for t in before.result.data["tasks"] if t["id"] == TEST_TASK_ID), None)
        if original is None:
            pytest.skip(f"Task {TEST_TASK_ID} is not in project {project_id}")

        original_priority = original.get("priority") or "MEDIUM"
        new_priority = "LOW" if original_priority != "LOW" else "HIGH"

        try:
            result = await guidecx.execute_action(
                "update_task",
                {"project_id": project_id, "task_id": TEST_TASK_ID, "priority": new_priority},
                live_context,
            )

            assert result.type == ResultType.ACTION, result.result
            assert result.result.data["task"]["priority"] == new_priority
        finally:
            await guidecx.execute_action(
                "update_task",
                {"project_id": project_id, "task_id": TEST_TASK_ID, "priority": original_priority},
                live_context,
            )


@skip_if_no_creds
@skip_if_no_task
@pytest.mark.destructive
class TestUpdateTaskStatus:
    @pytest.mark.asyncio
    async def test_status_update_is_partial_and_restores(self, live_context):
        """Setting status must not disturb the task's other fields.

        The endpoint is named "upsert", so the risk is that it behaves as a full
        replace and blanks everything the request omits. This asserts the
        surrounding fields survive a status-only update.
        """
        project_id = await resolve_project_id(live_context)

        listing = await guidecx.execute_action("list_tasks", {"project_id": project_id, "limit": 100}, live_context)
        assert listing.type == ResultType.ACTION, listing.result
        original = next((t for t in listing.result.data["tasks"] if t["id"] == TEST_TASK_ID), None)
        if original is None:
            pytest.skip(f"Task {TEST_TASK_ID} is not in project {project_id}")

        original_status = original.get("status")
        new_status = "In Progress" if original_status != "In Progress" else "Not Started"

        try:
            result = await guidecx.execute_action(
                "update_task",
                {"project_id": project_id, "task_id": TEST_TASK_ID, "status": new_status},
                live_context,
            )

            assert result.type == ResultType.ACTION, result.result
            updated = result.result.data["task"]
            assert updated["status"] == new_status
            # A status-only update must leave everything else alone.
            assert updated["name"] == original["name"]
            assert updated.get("responsibility") == original.get("responsibility")
            assert updated.get("priority") == original.get("priority")
        finally:
            if original_status:
                await guidecx.execute_action(
                    "update_task",
                    {"project_id": project_id, "task_id": TEST_TASK_ID, "status": original_status},
                    live_context,
                )

    @pytest.mark.asyncio
    async def test_unknown_status_label_returns_error(self, live_context):
        # GUIDEcx rejects labels that do not exist in the workspace rather than
        # silently ignoring them.
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "update_task",
            {"project_id": project_id, "task_id": TEST_TASK_ID, "status": "Definitely Not A Status"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not valid" in result.result.message


@skip_if_no_creds
@skip_if_no_task
@pytest.mark.destructive
class TestAddTaskNote:
    @pytest.mark.asyncio
    async def test_posts_an_internal_note(self, live_context):
        # internal_only keeps the note off the customer-facing view. There is
        # no delete-message endpoint in v3, so this note cannot be cleaned up.
        result = await guidecx.execute_action(
            "add_task_note",
            {
                "task_id": TEST_TASK_ID,
                "content": "Autohive integration test note - safe to ignore.",
                "internal_only": True,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        messages = result.result.data["messages"]
        assert len(messages) == 1
        assert messages[0].get("id")


# ---- Read-Only Tests: structure, team and time ----


@skip_if_no_creds
class TestListPhases:
    @pytest.mark.asyncio
    async def test_returns_phases_for_a_project(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_phases", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["phases"], list)

    @pytest.mark.asyncio
    async def test_phases_carry_name_and_sort_order(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_phases", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        phases = result.result.data["phases"]
        if not phases:
            pytest.skip("Project has no phases")
        for phase in phases:
            assert phase["id"]
            assert phase.get("name")
            assert isinstance(phase.get("sortOrder"), int)


@skip_if_no_creds
class TestListProjectMembers:
    @pytest.mark.asyncio
    async def test_returns_the_project_team(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_project_members", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result
        members = result.result.data["members"]
        assert isinstance(members, list)
        # A project always has at least a project manager.
        assert members, "expected at least one member on the project team"
        for member in members:
            assert member["id"]
            assert member.get("email")

    @pytest.mark.asyncio
    async def test_project_role_filter_accepted(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "list_project_members",
            {"project_id": project_id, "project_role": ["PROJECT_MANAGER"]},
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        for member in result.result.data["members"]:
            assert member.get("projectRole") == "PROJECT_MANAGER"


@skip_if_no_creds
class TestListMembers:
    @pytest.mark.asyncio
    async def test_returns_workspace_members(self, live_context):
        result = await guidecx.execute_action("list_members", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        members = result.result.data["members"]
        assert members, "expected at least the token's own member record"
        for member in members:
            assert member["id"]
            assert member.get("email")

    @pytest.mark.asyncio
    async def test_status_filter_is_applied(self, live_context):
        result = await guidecx.execute_action("list_members", {"status": ["ACTIVE"]}, live_context)

        assert result.type == ResultType.ACTION, result.result
        for member in result.result.data["members"]:
            assert member.get("status") == "ACTIVE"

    @pytest.mark.asyncio
    async def test_email_filter_narrows_results(self, live_context):
        everyone = await guidecx.execute_action("list_members", {"limit": 100}, live_context)
        assert everyone.type == ResultType.ACTION, everyone.result
        members = everyone.result.data["members"]
        if not members:
            pytest.skip("No members visible to this token")
        target = members[0]["email"]

        result = await guidecx.execute_action("list_members", {"email": [target]}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert [m["email"] for m in result.result.data["members"]] == [target]


@skip_if_no_creds
class TestListRoles:
    @pytest.mark.asyncio
    async def test_returns_roles_with_category(self, live_context):
        result = await guidecx.execute_action("list_roles", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        roles = result.result.data["roles"]
        assert roles, "expected at least one configured role"
        for role in roles:
            assert role["id"]
            assert role.get("category") in ("INTERNAL", "EXTERNAL", None)


@skip_if_no_creds
class TestListTimeCategories:
    @pytest.mark.asyncio
    async def test_returns_a_list(self, live_context):
        # A workspace with no billing configured has no time categories, so an
        # empty list is a valid result here.
        result = await guidecx.execute_action("list_time_categories", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["time_categories"], list)


@skip_if_no_creds
class TestListTimeRecords:
    @pytest.mark.asyncio
    async def test_returns_a_list(self, live_context):
        result = await guidecx.execute_action("list_time_records", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["time_records"], list)

    @pytest.mark.asyncio
    async def test_project_filter_accepted(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action("list_time_records", {"project_id": project_id}, live_context)

        assert result.type == ResultType.ACTION, result.result

    @pytest.mark.asyncio
    async def test_worked_after_filter_accepted(self, live_context):
        result = await guidecx.execute_action(
            "list_time_records", {"worked_after": "2020-01-01T00:00:00Z"}, live_context
        )

        assert result.type == ResultType.ACTION, result.result


@skip_if_no_creds
class TestListWebhooks:
    @pytest.mark.asyncio
    async def test_returns_a_list(self, live_context):
        result = await guidecx.execute_action("list_webhooks", {}, live_context)

        assert result.type == ResultType.ACTION, result.result
        assert isinstance(result.result.data["webhooks"], list)

    @pytest.mark.asyncio
    async def test_include_disabled_accepted(self, live_context):
        result = await guidecx.execute_action("list_webhooks", {"include_disabled": True}, live_context)

        assert result.type == ResultType.ACTION, result.result


@skip_if_no_creds
class TestDeleteWebhookErrors:
    @pytest.mark.asyncio
    async def test_unknown_id_returns_error(self, live_context):
        result = await guidecx.execute_action(
            "delete_webhook", {"webhook_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


@skip_if_no_creds
class TestRemoveProjectMemberErrors:
    @pytest.mark.asyncio
    async def test_unknown_member_returns_error(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "remove_project_member",
            {"project_id": project_id, "member_id": "00000000-0000-0000-0000-000000000000"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Destructive Tests: webhook lifecycle and time logging ----


@skip_if_no_creds
@pytest.mark.destructive
class TestWebhookLifecycle:
    @pytest.mark.asyncio
    async def test_create_update_then_delete(self, live_context):
        """Full webhook round trip, cleaning up after itself.

        example.com is used deliberately: it is reserved by RFC 2606 and cannot
        receive traffic, so a stray delivery goes nowhere.
        """
        created = await guidecx.execute_action(
            "upsert_webhook",
            {
                "event_type": "task.updated",
                "url": "https://example.com/autohive-lifecycle",
                "description": "AUTOHIVE TEST lifecycle",
            },
            live_context,
        )
        assert created.type == ResultType.ACTION, created.result
        webhook_id = created.result.data["webhook"]["id"]
        assert webhook_id

        try:
            listing = await guidecx.execute_action("list_webhooks", {"limit": 100}, live_context)
            assert listing.type == ResultType.ACTION, listing.result
            assert webhook_id in [w["id"] for w in listing.result.data["webhooks"]]

            updated = await guidecx.execute_action(
                "upsert_webhook",
                {
                    "webhook_id": webhook_id,
                    "event_type": "task.updated",
                    "url": "https://example.com/autohive-lifecycle-updated",
                    "description": "AUTOHIVE TEST lifecycle updated",
                },
                live_context,
            )
            assert updated.type == ResultType.ACTION, updated.result
            assert updated.result.data["webhook"]["id"] == webhook_id
            assert updated.result.data["webhook"]["url"].endswith("-updated")
        finally:
            deleted = await guidecx.execute_action("delete_webhook", {"webhook_id": webhook_id}, live_context)
            assert deleted.type == ResultType.ACTION, deleted.result

        gone = await guidecx.execute_action("list_webhooks", {"limit": 100, "include_disabled": True}, live_context)
        assert gone.type == ResultType.ACTION, gone.result
        assert webhook_id not in [w["id"] for w in gone.result.data["webhooks"]]


@skip_if_no_creds
@skip_if_no_task
@pytest.mark.destructive
class TestLogTime:
    @pytest.mark.asyncio
    async def test_log_time_on_task_appears_in_search(self, live_context):
        # Time records cannot be deleted through the v3 API, so this logs a
        # deliberately tiny amount against the designated test task.
        members = await guidecx.execute_action("list_members", {"status": ["ACTIVE"], "limit": 1}, live_context)
        assert members.type == ResultType.ACTION, members.result
        if not members.result.data["members"]:
            pytest.skip("No active member available to attribute time to")
        member_id = members.result.data["members"][0]["id"]

        result = await guidecx.execute_action(
            "log_task_time",
            {
                "task_id": TEST_TASK_ID,
                "member_id": member_id,
                "hours_worked": 0.01,
                "date_of_work": "2026-08-03T00:00:00Z",
                "comment": "AUTOHIVE TEST - task time entry",
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        record = result.result.data["time_record"]
        assert record["id"]
        assert record["hoursWorked"] == 0.01

        found = await guidecx.execute_action("list_time_records", {"task_id": TEST_TASK_ID}, live_context)
        assert found.type == ResultType.ACTION, found.result
        assert record["id"] in [r["id"] for r in found.result.data["time_records"]]

    @pytest.mark.asyncio
    async def test_log_time_on_project(self, live_context):
        project_id = await resolve_project_id(live_context)
        members = await guidecx.execute_action("list_members", {"status": ["ACTIVE"], "limit": 1}, live_context)
        assert members.type == ResultType.ACTION, members.result
        if not members.result.data["members"]:
            pytest.skip("No active member available to attribute time to")
        member_id = members.result.data["members"][0]["id"]

        result = await guidecx.execute_action(
            "log_project_time",
            {
                "project_id": project_id,
                "member_id": member_id,
                "hours_worked": 0.01,
                "date_of_work": "2026-08-03T00:00:00Z",
                "comment": "AUTOHIVE TEST - project time entry",
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, result.result
        assert result.result.data["time_record"]["hoursWorked"] == 0.01


# ---- Destructive Tests: structural writes ----
#
# These create real records. v3 has no delete endpoint for projects, phases,
# milestones or tasks, so anything built here stays in the workspace; only the
# dependency is removable. Everything is named with an AUTOHIVE TEST prefix so
# it is identifiable in the UI, and the customer domain is example.com, which
# RFC 2606 reserves so no mail can reach a real address.


@skip_if_no_creds
@pytest.mark.destructive
class TestCreateProjectTree:
    @pytest.mark.asyncio
    async def test_build_and_read_back_a_full_project(self, live_context):
        created = await guidecx.execute_action(
            "create_project",
            {
                "name": "AUTOHIVE TEST - e2e tree",
                "customer_name": "AUTOHIVE TEST - e2e Co",
                "customer_domain": "example.com",
                "cash_value": 100,
            },
            live_context,
        )
        assert created.type == ResultType.ACTION, created.result
        project = created.result.data["project"]
        project_id = project["id"]
        assert project_id
        # A new project starts in the PENDING category.
        assert project.get("statusCategory") == "PENDING"

        # The inline customer is created alongside the project and its ID is
        # returned, having been parsed out of _links.customer.
        customer_id = created.result.data["customer_id"]
        assert customer_id
        customer = await guidecx.execute_action("get_customer", {"customer_id": customer_id}, live_context)
        assert customer.type == ResultType.ACTION, customer.result
        assert customer.result.data["customer"]["domain"] == "example.com"

        renamed = await guidecx.execute_action(
            "update_project",
            {"project_id": project_id, "name": "AUTOHIVE TEST - e2e tree (renamed)"},
            live_context,
        )
        assert renamed.type == ResultType.ACTION, renamed.result
        assert renamed.result.data["project"]["name"].endswith("(renamed)")

        phase = await guidecx.execute_action(
            "create_phase", {"project_id": project_id, "name": "AUTOHIVE TEST - phase"}, live_context
        )
        assert phase.type == ResultType.ACTION, phase.result
        phase_id = phase.result.data["phase"]["id"]

        milestone = await guidecx.execute_action(
            "create_milestone",
            {"project_id": project_id, "phase_id": phase_id, "name": "AUTOHIVE TEST - milestone"},
            live_context,
        )
        assert milestone.type == ResultType.ACTION, milestone.result
        milestone_id = milestone.result.data["milestone"]["id"]

        task = await guidecx.execute_action(
            "create_task",
            {
                "project_id": project_id,
                "milestone_id": milestone_id,
                "name": "AUTOHIVE TEST - task",
                "priority": "HIGH",
                "estimated_hours": 1,
            },
            live_context,
        )
        assert task.type == ResultType.ACTION, task.result
        assert task.result.data["task"]["priority"] == "HIGH"
        # A newly created task starts in the workspace's not-started label.
        assert task.result.data["task"]["statusCategory"] == "NOT_STARTED"

        # Read the structure back through the list actions.
        phases = await guidecx.execute_action("list_phases", {"project_id": project_id}, live_context)
        assert phases.type == ResultType.ACTION, phases.result
        assert phase_id in [p["id"] for p in phases.result.data["phases"]]

        milestones = await guidecx.execute_action("list_milestones", {"project_id": project_id}, live_context)
        assert milestones.type == ResultType.ACTION, milestones.result
        assert milestone_id in [m["id"] for m in milestones.result.data["milestones"]]

        tasks = await guidecx.execute_action("list_tasks", {"project_id": project_id}, live_context)
        assert tasks.type == ResultType.ACTION, tasks.result
        assert task.result.data["task"]["id"] in [t["id"] for t in tasks.result.data["tasks"]]

    @pytest.mark.asyncio
    async def test_task_under_a_project_instead_of_a_milestone_fails(self, live_context):
        """A milestone ID is structurally required; a project ID will not do.

        Passing the project as the milestone means parentId is not a milestone,
        which GUIDEcx rejects. This guards the create_task contract.
        """
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "create_task",
            {"project_id": project_id, "milestone_id": project_id, "name": "AUTOHIVE TEST - should not exist"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_update_project_with_unknown_status_returns_error(self, live_context):
        project_id = await resolve_project_id(live_context)

        result = await guidecx.execute_action(
            "update_project", {"project_id": project_id, "status": "Definitely Not A Status"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


@skip_if_no_creds
@pytest.mark.destructive
class TestDependencyLifecycle:
    @pytest.mark.asyncio
    async def test_add_list_then_remove(self, live_context):
        """Full dependency round trip between two freshly created tasks.

        Dependencies are the one structural write v3 can undo, so this cleans up
        after itself; the two tasks it needs cannot be deleted.
        """
        project_id = await resolve_project_id(live_context)

        milestones = await guidecx.execute_action(
            "list_milestones", {"project_id": project_id, "limit": 1}, live_context
        )
        assert milestones.type == ResultType.ACTION, milestones.result
        if not milestones.result.data["milestones"]:
            pytest.skip("Project has no milestone to hang tasks off")
        milestone_id = milestones.result.data["milestones"][0]["id"]

        made = []
        for label in ("dep parent", "dep child"):
            created = await guidecx.execute_action(
                "create_task",
                {"project_id": project_id, "milestone_id": milestone_id, "name": f"AUTOHIVE TEST - {label}"},
                live_context,
            )
            assert created.type == ResultType.ACTION, created.result
            made.append(created.result.data["task"]["id"])
        parent_id, dependent_id = made

        added = await guidecx.execute_action(
            "add_dependency", {"parent_id": parent_id, "dependent_id": dependent_id}, live_context
        )
        assert added.type == ResultType.ACTION, added.result
        assert added.result.data["dependency"]["parentId"] == parent_id

        try:
            listed = await guidecx.execute_action("list_dependencies", {"dependent_id": [dependent_id]}, live_context)
            assert listed.type == ResultType.ACTION, listed.result
            pairs = [(d["parentId"], d["dependentId"]) for d in listed.result.data["dependencies"]]
            assert (parent_id, dependent_id) in pairs
            assert listed.result.data["count"] == len(listed.result.data["dependencies"])
        finally:
            removed = await guidecx.execute_action(
                "remove_dependency", {"parent_id": parent_id, "dependent_id": dependent_id}, live_context
            )
            assert removed.type == ResultType.ACTION, removed.result

        gone = await guidecx.execute_action("list_dependencies", {"dependent_id": [dependent_id]}, live_context)
        assert gone.type == ResultType.ACTION, gone.result
        remaining = [(d["parentId"], d["dependentId"]) for d in gone.result.data["dependencies"]]
        assert (parent_id, dependent_id) not in remaining

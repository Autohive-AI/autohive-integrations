"""
End-to-end integration tests for the Typeform integration.

These tests call the real Typeform API and require a valid access token set in
the TYPEFORM_ACCESS_TOKEN environment variable (via .env or export).

Run read-only tests (safe — default):
    pytest typeform/tests/test_typeform_integration.py -m "integration and not destructive"

Run destructive tests (create/update/delete real forms, workspaces, themes, webhooks):
    pytest typeform/tests/test_typeform_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these, and
the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import HTTPError, RateLimitError

from typeform.typeform import typeform

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("TYPEFORM_ACCESS_TOKEN", "")

# Optional pre-existing object IDs. When unset, read tests fall back to chaining
# (list → get) and skip gracefully if the account has no such objects.
TEST_FORM_ID = os.environ.get("TYPEFORM_TEST_FORM_ID", "")
TEST_WORKSPACE_ID = os.environ.get("TYPEFORM_TEST_WORKSPACE_ID", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("TYPEFORM_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        # Mirror the SDK's fetch contract: raise RateLimitError on 429 and
        # HTTPError on any other non-ok status, so error-path assertions exercise
        # the same code the production SDK does.
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=merged_headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", str(data))
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


async def _first_form_id(live_context):
    """Return a form id from the account, or skip if none exist."""
    if TEST_FORM_ID:
        return TEST_FORM_ID
    result = await typeform.execute_action("list_forms", {"page_size": 1}, live_context)
    forms = result.result.data.get("forms", [])
    if not forms:
        pytest.skip("No forms on this account to test with")
    return forms[0]["id"]


# =============================================================================
# READ-ONLY TESTS
# =============================================================================


class TestGetCurrentUser:
    async def test_returns_user(self, live_context):
        result = await typeform.execute_action("get_current_user", {}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["user"], dict)
        assert "user_id" in data["user"] or "email" in data["user"]


class TestListForms:
    async def test_returns_forms_list(self, live_context):
        result = await typeform.execute_action("list_forms", {}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["forms"], list)
        assert isinstance(data["total_items"], int)

    async def test_page_size_respected(self, live_context):
        result = await typeform.execute_action("list_forms", {"page_size": 1}, live_context)
        assert len(result.result.data["forms"]) <= 1


class TestGetForm:
    async def test_fetches_form_details(self, live_context):
        form_id = await _first_form_id(live_context)
        result = await typeform.execute_action("get_form", {"form_id": form_id}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert data["form"]["id"] == form_id

    async def test_nonexistent_form_returns_action_error(self, live_context):
        from autohive_integrations_sdk.integration import ResultType

        result = await typeform.execute_action("get_form", {"form_id": "nonexistent_form_xyz"}, live_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListResponses:
    async def test_returns_responses_list(self, live_context):
        form_id = await _first_form_id(live_context)
        result = await typeform.execute_action("list_responses", {"form_id": form_id, "page_size": 5}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["responses"], list)
        assert "total_items" in data
        assert "page_count" in data


class TestListWorkspaces:
    async def test_returns_workspaces_list(self, live_context):
        result = await typeform.execute_action("list_workspaces", {}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["workspaces"], list)


class TestGetWorkspace:
    async def test_fetches_workspace_details(self, live_context):
        if TEST_WORKSPACE_ID:
            workspace_id = TEST_WORKSPACE_ID
        else:
            list_result = await typeform.execute_action("list_workspaces", {"page_size": 1}, live_context)
            workspaces = list_result.result.data["workspaces"]
            if not workspaces:
                pytest.skip("No workspaces on this account to test with")
            workspace_id = workspaces[0]["id"]

        result = await typeform.execute_action("get_workspace", {"workspace_id": workspace_id}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert data["workspace"]["id"] == workspace_id


class TestListThemes:
    async def test_returns_themes_list(self, live_context):
        result = await typeform.execute_action("list_themes", {}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["themes"], list)


class TestGetTheme:
    async def test_fetches_theme_details(self, live_context):
        list_result = await typeform.execute_action("list_themes", {"page_size": 1}, live_context)
        themes = list_result.result.data["themes"]
        if not themes:
            pytest.skip("No themes on this account to test with")
        theme_id = themes[0]["id"]
        result = await typeform.execute_action("get_theme", {"theme_id": theme_id}, live_context)
        assert result.result.data["theme"]["id"] == theme_id


class TestListImages:
    async def test_returns_images_list(self, live_context):
        result = await typeform.execute_action("list_images", {}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["images"], list)


class TestGetImage:
    async def test_fetches_image_details(self, live_context):
        list_result = await typeform.execute_action("list_images", {}, live_context)
        images = list_result.result.data["images"]
        if not images:
            pytest.skip("No images on this account to test with")
        image_id = images[0]["id"]
        result = await typeform.execute_action("get_image", {"image_id": image_id}, live_context)
        assert result.result.data["image"]["id"] == image_id


class TestListWebhooks:
    async def test_returns_webhooks_list(self, live_context):
        form_id = await _first_form_id(live_context)
        result = await typeform.execute_action("list_webhooks", {"form_id": form_id}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["webhooks"], list)


# =============================================================================
# DESTRUCTIVE TESTS (create/update/delete real data)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestFormLifecycle:
    """create → get → update → delete a real form, cleaning up at the end."""

    async def test_full_lifecycle(self, live_context):
        title = f"Integration Test Form {os.getpid()}"
        create_result = await typeform.execute_action(
            "create_form",
            {"title": title, "fields": [{"type": "short_text", "title": "Your name?"}]},
            live_context,
        )
        form = create_result.result.data["form"]
        form_id = form["id"]
        assert form_id

        try:
            # Read it back
            get_result = await typeform.execute_action("get_form", {"form_id": form_id}, live_context)
            assert get_result.result.data["form"]["id"] == form_id

            # Update the title
            update_result = await typeform.execute_action(
                "update_form", {"form_id": form_id, "title": title + " (updated)"}, live_context
            )
            assert update_result.result.data["result"] is True
            assert update_result.result.data["form"]["title"] == title + " (updated)"
        finally:
            delete_result = await typeform.execute_action("delete_form", {"form_id": form_id}, live_context)
            assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
class TestWorkspaceLifecycle:
    """create → update → delete a real workspace."""

    async def test_full_lifecycle(self, live_context):
        name = f"Integration Test WS {os.getpid()}"
        create_result = await typeform.execute_action("create_workspace", {"name": name}, live_context)
        workspace_id = create_result.result.data["workspace"]["id"]
        assert workspace_id

        try:
            update_result = await typeform.execute_action(
                "update_workspace", {"workspace_id": workspace_id, "name": name + " (updated)"}, live_context
            )
            assert update_result.result.data["workspace"]["name"] == name + " (updated)"
        finally:
            delete_result = await typeform.execute_action(
                "delete_workspace", {"workspace_id": workspace_id}, live_context
            )
            assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
class TestThemeLifecycle:
    """create → delete a real theme."""

    async def test_create_then_delete(self, live_context):
        create_result = await typeform.execute_action(
            "create_theme",
            {
                "name": f"Integration Test Theme {os.getpid()}",
                "colors": {"question": "#3D3D3D", "answer": "#4FB0AE", "button": "#4FB0AE", "background": "#FFFFFF"},
            },
            live_context,
        )
        theme = create_result.result.data["theme"]
        theme_id = theme["id"]
        assert theme_id

        delete_result = await typeform.execute_action("delete_theme", {"theme_id": theme_id}, live_context)
        assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
class TestWebhookLifecycle:
    """create → get → delete a webhook on an existing form."""

    async def test_full_lifecycle(self, live_context):
        form_id = await _first_form_id(live_context)
        tag = f"integration_test_{os.getpid()}"

        create_result = await typeform.execute_action(
            "create_webhook",
            {"form_id": form_id, "tag": tag, "url": "https://example.com/webhook", "enabled": False},
            live_context,
        )
        assert create_result.result.data["result"] is True

        try:
            get_result = await typeform.execute_action("get_webhook", {"form_id": form_id, "tag": tag}, live_context)
            assert get_result.result.data["webhook"]["tag"] == tag
        finally:
            delete_result = await typeform.execute_action(
                "delete_webhook", {"form_id": form_id, "tag": tag}, live_context
            )
            assert delete_result.result.data["deleted"] is True

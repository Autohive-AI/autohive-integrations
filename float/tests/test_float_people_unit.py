import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

float_integration = _mod.float

pytestmark = pytest.mark.unit

SAMPLE_PERSON = {
    "people_id": 123,
    "name": "Alice Smith",
    "email": "alice@example.com",
    "job_title": "Engineer",
    "active": True,
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "api_key": "test_api_key",  # nosec B105
            "application_name": "Test App",
            "contact_email": "test@example.com",
        }
    }
    return ctx


# ---- List People ----


class TestListPeople:
    @pytest.mark.asyncio
    async def test_list_people_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[{"people_id": 123, "name": "Alice Smith", "email": "alice@example.com", "active": 1}],
        )

        result = await float_integration.execute_action("list_people", {}, mock_context)

        assert result.result.data[0]["people_id"] == 123

    @pytest.mark.asyncio
    async def test_list_people_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {}, mock_context)

        call_args = mock_context.fetch.call_args
        url = call_args.kwargs.get("url", call_args.args[0] if call_args.args else "")
        assert "https://api.float.com/v3/people" in url

    @pytest.mark.asyncio
    async def test_list_people_with_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {"active": True, "department_id": 5}, mock_context)

        call_args = mock_context.fetch.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("active") == 1
        assert params.get("department_id") == 5

    @pytest.mark.asyncio
    async def test_list_people_per_page_renamed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {"per_page": 25}, mock_context)

        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params.get("per-page") == 25

    @pytest.mark.asyncio
    async def test_list_people_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await float_integration.execute_action("list_people", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_list_people_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        result = await float_integration.execute_action("list_people", {}, mock_context)

        assert result.result.data == []


# ---- Get Person ----


class TestGetPerson:
    @pytest.mark.asyncio
    async def test_get_person_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        result = await float_integration.execute_action("get_person", {"people_id": 123}, mock_context)

        assert result.result.data["people_id"] == 123
        assert result.result.data["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_get_person_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action("get_person", {"people_id": 123}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/people/123")

    @pytest.mark.asyncio
    async def test_get_person_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_person", {"people_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Create Person ----


class TestCreatePerson:
    @pytest.mark.asyncio
    async def test_create_person_happy_path(self, mock_context):
        created = {**SAMPLE_PERSON, "people_id": 456}
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=created)

        result = await float_integration.execute_action("create_person", {"name": "Bob Jones"}, mock_context)

        assert result.result.data["people_id"] == 456

    @pytest.mark.asyncio
    async def test_create_person_request_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action("create_person", {"name": "Bob Jones"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs.get("method") == "POST"

    @pytest.mark.asyncio
    async def test_create_person_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action(
            "create_person", {"name": "Bob Jones", "email": "bob@example.com", "job_title": "Dev"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs.get("json", {})
        assert body["name"] == "Bob Jones"
        assert body["email"] == "bob@example.com"
        assert body["job_title"] == "Dev"

    @pytest.mark.asyncio
    async def test_create_person_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Validation error")

        result = await float_integration.execute_action("create_person", {"name": "Bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Validation error" in result.result.message


# ---- Update Person ----


class TestUpdatePerson:
    @pytest.mark.asyncio
    async def test_update_person_happy_path(self, mock_context):
        updated = {**SAMPLE_PERSON, "job_title": "Senior Engineer"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await float_integration.execute_action(
            "update_person", {"people_id": 123, "job_title": "Senior Engineer"}, mock_context
        )

        assert result.result.data["job_title"] == "Senior Engineer"

    @pytest.mark.asyncio
    async def test_update_person_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action("update_person", {"people_id": 123, "name": "Updated"}, mock_context)

        assert mock_context.fetch.call_args.kwargs.get("method") == "PATCH"

    @pytest.mark.asyncio
    async def test_update_person_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update failed")

        result = await float_integration.execute_action("update_person", {"people_id": 123}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Update failed" in result.result.message


# ---- Delete Person ----


class TestDeletePerson:
    @pytest.mark.asyncio
    async def test_delete_person_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_person", {"people_id": 123}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_person_uses_delete_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await float_integration.execute_action("delete_person", {"people_id": 123}, mock_context)

        assert mock_context.fetch.call_args.kwargs.get("method") == "DELETE"

    @pytest.mark.asyncio
    async def test_delete_person_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete failed")

        result = await float_integration.execute_action("delete_person", {"people_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Delete failed" in result.result.message

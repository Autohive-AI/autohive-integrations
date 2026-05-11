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

_spec = importlib.util.spec_from_file_location("front_mod", os.path.join(_parent, "front.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

front = _mod.front  # the Integration instance

pytestmark = pytest.mark.unit

# ---- Sample Data ----

SAMPLE_TEAMMATE = {
    "id": "tea_123",
    "email": "agent@example.com",
    "username": "agent1",
    "first_name": "Agent",
    "last_name": "One",
    "is_admin": False,
    "is_available": True,
    "is_blocked": False,
    "type": "user",
    "custom_fields": {},
}


# ---- Fixtures ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Teammates ----


class TestListTeammates:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("list_teammates", {}, mock_context)

        assert len(result.result.data["teammates"]) == 1
        assert result.result.data["teammates"][0]["email"] == "agent@example.com"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_teammates", {"limit": 20}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/teammates"

    @pytest.mark.asyncio
    async def test_limit_param_sent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_teammates", {"limit": 20}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        result = await front.execute_action("list_teammates", {}, mock_context)

        assert result.result.data["teammates"] == []

    @pytest.mark.asyncio
    async def test_teammate_fields_mapped(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("list_teammates", {}, mock_context)

        t = result.result.data["teammates"][0]
        assert t["id"] == "tea_123"
        assert t["username"] == "agent1"
        assert t["first_name"] == "Agent"
        assert t["is_admin"] is False

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_teammates", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetTeammate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEAMMATE)

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert result.result.data["teammate"]["id"] == "tea_123"
        assert result.result.data["teammate"]["email"] == "agent@example.com"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEAMMATE)

        await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/teammates/tea_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Teammate not found"})

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_response_has_teammate_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEAMMATE)

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert "teammate" in result.result.data


class TestFindTeammate:
    @pytest.mark.asyncio
    async def test_match_by_email(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "agent@example.com"}, mock_context)

        assert len(result.result.data["teammates"]) == 1
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "nonexistent"}, mock_context)

        assert result.result.data["teammates"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_partial_name_match(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "agent"}, mock_context)

        # Should match first_name "Agent"
        assert len(result.result.data["teammates"]) == 1

    @pytest.mark.asyncio
    async def test_match_by_username(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "agent1"}, mock_context)

        assert len(result.result.data["teammates"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("find_teammate", {"search_query": "john"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

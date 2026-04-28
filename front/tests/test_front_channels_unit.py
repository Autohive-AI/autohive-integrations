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

SAMPLE_CHANNEL = {
    "id": "cha_123",
    "name": "Support Email",
    "type": "smtp",
    "address": "support@example.com",
}

SAMPLE_TEMPLATE = {
    "id": "tpl_123",
    "name": "Welcome Template",
    "subject": "Welcome!",
    "body": "<p>Welcome to our service</p>",
    "attachments": [],
    "metadata": {},
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


# ---- Channels ----


class TestListChannels:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_CHANNEL]})

        result = await front.execute_action("list_channels", {}, mock_context)

        assert len(result.result.data["channels"]) == 1
        assert result.result.data["channels"][0]["id"] == "cha_123"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_channels", {"limit": 20}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api2.frontapp.com/channels"
        assert call_args.kwargs["params"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        result = await front.execute_action("list_channels", {}, mock_context)

        assert result.result.data["channels"] == []

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_channels", {"limit": 200}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await front.execute_action("list_channels", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        result = await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert result.result.data["channel"]["id"] == "cha_123"
        assert result.result.data["channel"]["type"] == "smtp"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/channels/cha_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Channel not found"})

        result = await front.execute_action("get_channel", {"channel_id": "cha_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_response_has_channel_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        result = await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert "channel" in result.result.data


# ---- Templates ----


class TestListMessageTemplates:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEMPLATE]})

        result = await front.execute_action("list_message_templates", {}, mock_context)

        assert len(result.result.data["templates"]) == 1
        assert result.result.data["templates"][0]["id"] == "tpl_123"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_message_templates", {"limit": 10}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/message_templates"

    @pytest.mark.asyncio
    async def test_template_fields_mapped(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEMPLATE]})

        result = await front.execute_action("list_message_templates", {}, mock_context)

        tpl = result.result.data["templates"][0]
        assert tpl["name"] == "Welcome Template"
        assert tpl["subject"] == "Welcome!"
        assert tpl["body"] == "<p>Welcome to our service</p>"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_message_templates", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetMessageTemplate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEMPLATE)

        result = await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert result.result.data["template"]["id"] == "tpl_123"
        assert result.result.data["template"]["name"] == "Welcome Template"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEMPLATE)

        await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/message_templates/tpl_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Template not found"})

        result = await front.execute_action("get_message_template", {"message_template_id": "tpl_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

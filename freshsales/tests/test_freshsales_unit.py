import importlib.util
import json
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("freshsales_mod", os.path.join(_parent, "freshsales.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

freshsales = _mod.freshsales  # the Integration instance
get_auth_headers = _mod.get_auth_headers
get_base_url = _mod.get_base_url
build_body = _mod.build_body

CONFIG_PATH = os.path.join(_parent, "config.json")

pytestmark = pytest.mark.unit


# ---- Config/Handler Sync ----


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        defined_actions = set(config.get("actions", {}).keys())
        registered_actions = set(freshsales._action_handlers.keys())

        missing_handlers = defined_actions - registered_actions
        extra_handlers = registered_actions - defined_actions

        assert not missing_handlers, f"Missing handlers for actions: {missing_handlers}"
        assert not extra_handlers, f"Extra handlers without config: {extra_handlers}"


# ---- Helper Function Tests ----


class TestGetAuthHeaders:
    def test_token_header_format(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Authorization"] == "Token token=test_api_key"  # nosec B105

    def test_content_type_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Content-Type"] == "application/json"


class TestGetBaseUrl:
    def test_bare_alias(self, mock_context):
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"

    def test_full_domain_pasted(self, mock_context):
        mock_context.auth["credentials"]["bundle_alias"] = "https://testcompany.myfreshworks.com/"
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"

    def test_domain_without_protocol(self, mock_context):
        mock_context.auth["credentials"]["bundle_alias"] = "testcompany.myfreshworks.com"
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"


class TestBuildBody:
    def test_includes_only_provided_fields(self):
        body = build_body({"a": 1, "b": None, "d": "x"}, ("a", "b", "c"))
        assert body == {"a": 1}

    def test_keeps_falsy_but_not_none_values(self):
        body = build_body({"a": 0, "b": ""}, ("a", "b"))
        assert body == {"a": 0, "b": ""}


# ---- List Views ----


class TestListViews:
    @pytest.mark.asyncio
    async def test_happy_path_returns_views(self, mock_context):
        views = [{"id": 1, "name": "My Contacts"}, {"id": 4, "name": "All Contacts"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": views})

        result = await freshsales.execute_action("list_views", {"entity": "contacts"}, mock_context)

        assert result.result.data["views"] == views
        assert result.result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_accounts_entity_maps_to_sales_accounts_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": []})

        await freshsales.execute_action("list_views", {"entity": "accounts"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "testcompany.myfreshworks.com/crm/sales/api/sales_accounts/filters" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await freshsales.execute_action("list_views", {"entity": "deals"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message

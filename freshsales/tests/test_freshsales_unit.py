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


# ---- Sample Data ----

SAMPLE_CONTACT = {
    "id": 3001,
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "mobile_number": "555-0100",
}


# ---- Contact Tests ----


class TestCreateContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contact(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        result = await freshsales.execute_action(
            "create_contact", {"first_name": "Jane", "email": "jane@example.com"}, mock_context
        )

        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_request_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        await freshsales.execute_action(
            "create_contact", {"first_name": "Jane", "email": "jane@example.com", "owner_id": 7}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://testcompany.myfreshworks.com/crm/sales/api/contacts"
        assert call_args.kwargs["method"] == "POST"
        expected_json = {"contact": {"first_name": "Jane", "email": "jane@example.com", "owner_id": 7}}
        assert call_args.kwargs["json"] == expected_json
        assert call_args.kwargs["headers"]["Authorization"] == "Token token=test_api_key"  # nosec B105

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_contact", {"first_name": "Jane"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "create failed" in result.result.message


class TestGetContact:
    @pytest.mark.asyncio
    async def test_happy_path_and_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        result = await freshsales.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_include_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        await freshsales.execute_action("get_contact", {"contact_id": 3001, "include": "owner,deals"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"include": "owner,deals"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateContact:
    @pytest.mark.asyncio
    async def test_happy_path_put_with_wrapped_body(self, mock_context):
        updated = {**SAMPLE_CONTACT, "job_title": "CTO"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": updated})

        result = await freshsales.execute_action(
            "update_contact", {"contact_id": 3001, "job_title": "CTO"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"contact": {"job_title": "CTO"}}
        assert result.result.data["contact"]["job_title"] == "CTO"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteContact:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["contact_id"] == 3001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListContacts:
    @pytest.mark.asyncio
    async def test_explicit_view_id_lists_directly(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"contacts": [SAMPLE_CONTACT], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_contacts", {"view_id": 42}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/contacts/view/42" in call_args.args[0]
        assert call_args.kwargs["params"]["page"] == 1
        assert result.result.data["contacts"] == [SAMPLE_CONTACT]
        assert result.result.data["meta"] == {"total": 1}
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_auto_resolves_all_view_when_view_id_omitted(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"filters": [{"id": 9, "name": "My Contacts"}, {"id": 4, "name": "All Contacts"}]},
            ),
            FetchResponse(status=200, headers={}, data={"contacts": [SAMPLE_CONTACT], "meta": {}}),
        ]

        result = await freshsales.execute_action("list_contacts", {}, mock_context)

        first_url = mock_context.fetch.call_args_list[0].args[0]
        second_url = mock_context.fetch.call_args_list[1].args[0]
        assert first_url.endswith("/contacts/filters")
        assert "/contacts/view/4" in second_url
        assert result.result.data["contacts"] == [SAMPLE_CONTACT]

    @pytest.mark.asyncio
    async def test_pagination_and_sort_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contacts": [], "meta": {}})

        await freshsales.execute_action(
            "list_contacts", {"view_id": 42, "page": 3, "sort": "updated_at", "sort_type": "desc"}, mock_context
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params == {"page": 3, "sort": "updated_at", "sort_type": "desc"}

    @pytest.mark.asyncio
    async def test_no_views_available_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": []})

        result = await freshsales.execute_action("list_contacts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "No list views available" in result.result.message


# ---- Account Tests ----

SAMPLE_ACCOUNT = {"id": 2001, "name": "Widgetz.io", "website": "https://widgetz.io"}


class TestCreateAccount:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body_and_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": SAMPLE_ACCOUNT})

        result = await freshsales.execute_action("create_account", {"name": "Widgetz.io"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"sales_account": {"name": "Widgetz.io"}}
        assert result.result.data["account"] == SAMPLE_ACCOUNT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_account", {"name": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_happy_path_and_include(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": SAMPLE_ACCOUNT})

        result = await freshsales.execute_action("get_account", {"account_id": 2001, "include": "owner"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"include": "owner"}
        assert result.result.data["account"] == SAMPLE_ACCOUNT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateAccount:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_ACCOUNT, "city": "Auckland"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": updated})

        input_data = {"account_id": 2001, "city": "Auckland"}
        result = await freshsales.execute_action("update_account", input_data, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"sales_account": {"city": "Auckland"}}
        assert result.result.data["account"]["city"] == "Auckland"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteAccount:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_account", {"account_id": 2001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["account_id"] == 2001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAccounts:
    @pytest.mark.asyncio
    async def test_explicit_view_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"sales_accounts": [SAMPLE_ACCOUNT], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_accounts", {"view_id": 8}, mock_context)

        assert "/sales_accounts/view/8" in mock_context.fetch.call_args.args[0]
        assert result.result.data["accounts"] == [SAMPLE_ACCOUNT]

    @pytest.mark.asyncio
    async def test_auto_resolves_view(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"filters": [{"id": 6, "name": "All Accounts"}]}),
            FetchResponse(status=200, headers={}, data={"sales_accounts": [], "meta": {}}),
        ]

        await freshsales.execute_action("list_accounts", {}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0].endswith("/sales_accounts/filters")
        assert "/sales_accounts/view/6" in mock_context.fetch.call_args_list[1].args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_accounts", {"view_id": 8}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

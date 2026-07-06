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

    @pytest.mark.asyncio
    async def test_falls_back_to_first_view_when_no_all_view(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"filters": [{"id": 7, "name": "My Contacts"}, {"id": 9, "name": "Hot leads"}]},
            ),
            FetchResponse(status=200, headers={}, data={"contacts": [], "meta": {}}),
        ]

        await freshsales.execute_action("list_contacts", {}, mock_context)

        assert "/contacts/view/7" in mock_context.fetch.call_args_list[1].args[0]


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


# ---- Deal Tests ----

SAMPLE_DEAL = {"id": 4001, "name": "Big deal", "amount": "23456.0", "sales_account_id": 2001}


class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": SAMPLE_DEAL})

        result = await freshsales.execute_action(
            "create_deal", {"name": "Big deal", "amount": 23456, "sales_account_id": 2001}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"deal": {"name": "Big deal", "amount": 23456, "sales_account_id": 2001}}
        assert result.result.data["deal"] == SAMPLE_DEAL

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_deal", {"name": "X", "amount": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_happy_path_and_include(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": SAMPLE_DEAL})

        result = await freshsales.execute_action("get_deal", {"deal_id": 4001, "include": "owner"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"include": "owner"}
        assert result.result.data["deal"] == SAMPLE_DEAL

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateDeal:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_DEAL, "amount": "99999.0"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": updated})

        result = await freshsales.execute_action("update_deal", {"deal_id": 4001, "amount": 99999}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"deal": {"amount": 99999}}
        assert result.result.data["deal"]["amount"] == "99999.0"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteDeal:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_deal", {"deal_id": 4001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["deal_id"] == 4001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListDeals:
    @pytest.mark.asyncio
    async def test_explicit_view_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"deals": [SAMPLE_DEAL], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_deals", {"view_id": 12}, mock_context)

        assert "/deals/view/12" in mock_context.fetch.call_args.args[0]
        assert result.result.data["deals"] == [SAMPLE_DEAL]

    @pytest.mark.asyncio
    async def test_auto_resolves_view(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"filters": [{"id": 3, "name": "All Deals"}]}),
            FetchResponse(status=200, headers={}, data={"deals": [], "meta": {}}),
        ]

        await freshsales.execute_action("list_deals", {}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0].endswith("/deals/filters")
        assert "/deals/view/3" in mock_context.fetch.call_args_list[1].args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_deals", {"view_id": 12}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Task Tests ----

SAMPLE_TASK = {
    "id": 5001,
    "title": "Follow up",
    "due_date": "2026-07-10T10:00:00Z",
    "targetable_type": "Contact",
    "targetable_id": 3001,
    "status": 0,
}


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": SAMPLE_TASK})

        inputs = {
            "title": "Follow up",
            "due_date": "2026-07-10T10:00:00Z",
            "targetable_type": "Contact",
            "targetable_id": 3001,
        }
        result = await freshsales.execute_action("create_task", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"task": inputs}
        assert result.result.data["task"] == SAMPLE_TASK

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_task",
            {"title": "X", "due_date": "2026-07-10", "targetable_type": "Contact", "targetable_id": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetTask:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": SAMPLE_TASK})

        result = await freshsales.execute_action("get_task", {"task_id": 5001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["task"] == SAMPLE_TASK

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_mark_done_via_status(self, mock_context):
        done = {**SAMPLE_TASK, "status": 1}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": done})

        result = await freshsales.execute_action("update_task", {"task_id": 5001, "status": 1}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"task": {"status": 1}}
        assert result.result.data["task"]["status"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_task", {"task_id": 5001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["task_id"] == 5001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListTasks:
    @pytest.mark.asyncio
    async def test_default_filter_open(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"tasks": [SAMPLE_TASK]})

        result = await freshsales.execute_action("list_tasks", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks")
        assert call_args.kwargs["params"] == {"filter": "open"}
        assert result.result.data["tasks"] == [SAMPLE_TASK]

    @pytest.mark.asyncio
    async def test_explicit_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"tasks": []})

        await freshsales.execute_action("list_tasks", {"filter": "completed"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"filter": "completed"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


SAMPLE_APPOINTMENT = {
    "id": 6001,
    "title": "Demo call",
    "from_date": "2026-07-10T10:00:00Z",
    "end_date": "2026-07-10T11:00:00Z",
    "targetable_type": "Contact",
    "targetable_id": 3001,
}


class TestCreateAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        response_data = {"appointment": SAMPLE_APPOINTMENT}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        inputs = {
            "title": "Demo call",
            "from_date": "2026-07-10T10:00:00Z",
            "end_date": "2026-07-10T11:00:00Z",
            "targetable_type": "Contact",
            "targetable_id": 3001,
        }
        result = await freshsales.execute_action("create_appointment", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"appointment": inputs}
        assert result.result.data["appointment"] == SAMPLE_APPOINTMENT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_appointment",
            {
                "title": "X",
                "from_date": "2026-07-10T10:00:00Z",
                "end_date": "2026-07-10T11:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": 1,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetAppointment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        response_data = {"appointment": SAMPLE_APPOINTMENT}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await freshsales.execute_action("get_appointment", {"appointment_id": 6001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["appointment"] == SAMPLE_APPOINTMENT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_APPOINTMENT, "location": "Zoom"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointment": updated})

        result = await freshsales.execute_action(
            "update_appointment", {"appointment_id": 6001, "location": "Zoom"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"appointment": {"location": "Zoom"}}
        assert result.result.data["appointment"]["location"] == "Zoom"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_appointment", {"appointment_id": 6001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["appointment_id"] == 6001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAppointments:
    @pytest.mark.asyncio
    async def test_no_filter_by_default(self, mock_context):
        response_data = {"appointments": [SAMPLE_APPOINTMENT]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await freshsales.execute_action("list_appointments", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments")
        assert call_args.kwargs["params"] == {}
        assert result.result.data["appointments"] == [SAMPLE_APPOINTMENT]

    @pytest.mark.asyncio
    async def test_explicit_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointments": []})

        await freshsales.execute_action("list_appointments", {"filter": "upcoming"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"filter": "upcoming"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_appointments", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


SAMPLE_NOTE = {"id": 7001, "description": "Call summary", "targetable_type": "Contact", "targetable_id": 3001}


class TestCreateNote:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"note": SAMPLE_NOTE})

        inputs = {"description": "Call summary", "targetable_type": "Contact", "targetable_id": 3001}
        result = await freshsales.execute_action("create_note", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"note": inputs}
        assert result.result.data["note"] == SAMPLE_NOTE

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_note", {"description": "X", "targetable_type": "Contact", "targetable_id": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateNote:
    @pytest.mark.asyncio
    async def test_happy_path_put(self, mock_context):
        updated = {**SAMPLE_NOTE, "description": "Updated summary"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"note": updated})

        result = await freshsales.execute_action(
            "update_note", {"note_id": 7001, "description": "Updated summary"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes/7001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"note": {"description": "Updated summary"}}
        assert result.result.data["note"]["description"] == "Updated summary"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_note", {"note_id": 7001, "description": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteNote:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_note", {"note_id": 7001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes/7001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["note_id"] == 7001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_note", {"note_id": 7001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestSearch:
    @pytest.mark.asyncio
    async def test_happy_path_returns_results(self, mock_context):
        results = [{"id": 3001, "type": "contact", "name": "Jane Doe"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=results)

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/search")
        assert call_args.kwargs["params"]["q"] == "jane"
        assert call_args.kwargs["params"]["include"] == "contact,sales_account,deal"
        assert result.result.data["results"] == results
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_custom_include_entities(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshsales.execute_action("search", {"query": "acme", "include": "sales_account"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["include"] == "sales_account"

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"unexpected": True})

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        assert result.result.data["results"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("search failed")

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

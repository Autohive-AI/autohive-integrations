import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType
from dynamics365.dynamics365 import dynamics365

pytestmark = pytest.mark.unit


def make_fetch(data):
    return AsyncMock(return_value=FetchResponse(status=200, headers={}, data=data))


# ---- list_accounts ----

@pytest.mark.asyncio
async def test_list_accounts(mock_context):
    mock_context.fetch = make_fetch({"value": [{"accountid": "a1", "name": "Acme"}]})
    result = await dynamics365.execute_action("list_accounts", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["accounts"][0]["name"] == "Acme"
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_accounts_with_filter(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    result = await dynamics365.execute_action(
        "list_accounts", {"name": "Test", "limit": 5}, mock_context
    )
    assert result.type == ResultType.ACTION
    call_kwargs = mock_context.fetch.call_args[1]
    assert "contains(name,'Test')" in call_kwargs.get("params", {}).get("$filter", "")
    assert call_kwargs["params"]["$top"] == 5


@pytest.mark.asyncio
async def test_list_accounts_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("network error"))
    result = await dynamics365.execute_action("list_accounts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "network error" in result.result.message


# ---- get_account ----

@pytest.mark.asyncio
async def test_get_account(mock_context):
    mock_context.fetch = make_fetch({"accountid": "a1", "name": "Acme"})
    result = await dynamics365.execute_action("get_account", {"account_id": "a1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["account"]["accountid"] == "a1"


@pytest.mark.asyncio
async def test_get_account_api_error(mock_context):
    mock_context.fetch = make_fetch({"error": {"message": "Record not found"}})
    result = await dynamics365.execute_action("get_account", {"account_id": "bad-id"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Record not found" in result.result.message


# ---- create_account ----

@pytest.mark.asyncio
async def test_create_account(mock_context):
    mock_context.fetch = make_fetch({"accountid": "new-a1", "name": "New Corp"})
    result = await dynamics365.execute_action(
        "create_account",
        {"name": "New Corp", "email": "info@newcorp.com", "phone": "555-1234"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["account"]["name"] == "New Corp"


@pytest.mark.asyncio
async def test_create_account_sends_correct_fields(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action(
        "create_account",
        {"name": "Corp", "email": "x@corp.com", "website": "https://corp.com"},
        mock_context,
    )
    call_json = mock_context.fetch.call_args[1]["json"]
    assert call_json["name"] == "Corp"
    assert call_json["emailaddress1"] == "x@corp.com"
    assert call_json["websiteurl"] == "https://corp.com"


# ---- update_account ----

@pytest.mark.asyncio
async def test_update_account(mock_context):
    mock_context.fetch = make_fetch(None)
    result = await dynamics365.execute_action(
        "update_account",
        {"account_id": "a1", "name": "Updated Corp"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["updated"] is True
    assert result.result.data["account_id"] == "a1"


# ---- list_contacts ----

@pytest.mark.asyncio
async def test_list_contacts(mock_context):
    mock_context.fetch = make_fetch({"value": [{"contactid": "c1", "lastname": "Smith"}]})
    result = await dynamics365.execute_action("list_contacts", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_contacts_with_email_filter(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    result = await dynamics365.execute_action(
        "list_contacts", {"email": "john@example.com"}, mock_context
    )
    assert result.type == ResultType.ACTION
    call_kwargs = mock_context.fetch.call_args[1]
    assert "emailaddress1 eq 'john@example.com'" in call_kwargs["params"]["$filter"]


@pytest.mark.asyncio
async def test_list_contacts_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("timeout"))
    result = await dynamics365.execute_action("list_contacts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- get_contact ----

@pytest.mark.asyncio
async def test_get_contact(mock_context):
    mock_context.fetch = make_fetch({"contactid": "c1", "firstname": "John", "lastname": "Smith"})
    result = await dynamics365.execute_action("get_contact", {"contact_id": "c1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["contact"]["contactid"] == "c1"


# ---- create_contact ----

@pytest.mark.asyncio
async def test_create_contact(mock_context):
    mock_context.fetch = make_fetch({"contactid": "new-c1", "lastname": "Doe"})
    result = await dynamics365.execute_action(
        "create_contact",
        {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["contact"]["lastname"] == "Doe"


@pytest.mark.asyncio
async def test_create_contact_with_account_binding(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action(
        "create_contact",
        {"last_name": "Doe", "account_id": "a1"},
        mock_context,
    )
    call_json = mock_context.fetch.call_args[1]["json"]
    assert "parentcustomerid_account@odata.bind" in call_json
    assert "/accounts(a1)" in call_json["parentcustomerid_account@odata.bind"]


# ---- update_contact ----

@pytest.mark.asyncio
async def test_update_contact(mock_context):
    mock_context.fetch = make_fetch(None)
    result = await dynamics365.execute_action(
        "update_contact",
        {"contact_id": "c1", "job_title": "Manager"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["updated"] is True


# ---- list_leads ----

@pytest.mark.asyncio
async def test_list_leads(mock_context):
    mock_context.fetch = make_fetch({"value": [{"leadid": "l1", "lastname": "Jones"}]})
    result = await dynamics365.execute_action("list_leads", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_leads_with_name_filter(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    await dynamics365.execute_action("list_leads", {"last_name": "Jones"}, mock_context)
    call_kwargs = mock_context.fetch.call_args[1]
    assert "contains(lastname,'Jones')" in call_kwargs["params"]["$filter"]


# ---- get_lead ----

@pytest.mark.asyncio
async def test_get_lead(mock_context):
    mock_context.fetch = make_fetch({"leadid": "l1", "lastname": "Jones"})
    result = await dynamics365.execute_action("get_lead", {"lead_id": "l1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["lead"]["leadid"] == "l1"


# ---- create_lead ----

@pytest.mark.asyncio
async def test_create_lead(mock_context):
    mock_context.fetch = make_fetch({"leadid": "new-l1"})
    result = await dynamics365.execute_action(
        "create_lead",
        {"first_name": "Bob", "last_name": "Jones", "company": "Jones LLC", "email": "bob@jones.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_create_lead_sends_correct_fields(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action(
        "create_lead",
        {"last_name": "Jones", "company": "Jones LLC", "topic": "Product inquiry"},
        mock_context,
    )
    call_json = mock_context.fetch.call_args[1]["json"]
    assert call_json["lastname"] == "Jones"
    assert call_json["companyname"] == "Jones LLC"
    assert call_json["subject"] == "Product inquiry"


# ---- qualify_lead ----

@pytest.mark.asyncio
async def test_qualify_lead(mock_context):
    mock_context.fetch = make_fetch({"value": [{"id": "new-c1", "logicalname": "contact"}]})
    result = await dynamics365.execute_action(
        "qualify_lead",
        {"lead_id": "l1", "create_account": True, "create_contact": True},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["qualified"] is True


# ---- list_opportunities ----

@pytest.mark.asyncio
async def test_list_opportunities(mock_context):
    mock_context.fetch = make_fetch({"value": [{"opportunityid": "o1", "name": "Big Deal"}]})
    result = await dynamics365.execute_action("list_opportunities", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_opportunities_status_filter(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    await dynamics365.execute_action("list_opportunities", {"status": "Won"}, mock_context)
    call_kwargs = mock_context.fetch.call_args[1]
    assert "statecode eq 1" in call_kwargs["params"]["$filter"]


# ---- get_opportunity ----

@pytest.mark.asyncio
async def test_get_opportunity(mock_context):
    mock_context.fetch = make_fetch({"opportunityid": "o1", "name": "Big Deal"})
    result = await dynamics365.execute_action("get_opportunity", {"opportunity_id": "o1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["opportunity"]["opportunityid"] == "o1"


# ---- create_opportunity ----

@pytest.mark.asyncio
async def test_create_opportunity(mock_context):
    mock_context.fetch = make_fetch({"opportunityid": "new-o1", "name": "New Deal"})
    result = await dynamics365.execute_action(
        "create_opportunity",
        {"name": "New Deal", "estimated_value": 50000.0, "close_date": "2026-12-31"},
        mock_context,
    )
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_create_opportunity_with_account(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action(
        "create_opportunity",
        {"name": "Deal", "account_id": "a1"},
        mock_context,
    )
    call_json = mock_context.fetch.call_args[1]["json"]
    assert "parentaccountid_account@odata.bind" in call_json
    assert "/accounts(a1)" in call_json["parentaccountid_account@odata.bind"]


# ---- list_tasks ----

@pytest.mark.asyncio
async def test_list_tasks(mock_context):
    mock_context.fetch = make_fetch({"value": [{"activityid": "t1", "subject": "Follow up"}]})
    result = await dynamics365.execute_action("list_tasks", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_tasks_status_filter(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    await dynamics365.execute_action("list_tasks", {"status": "Completed"}, mock_context)
    call_kwargs = mock_context.fetch.call_args[1]
    assert "statecode eq 1" in call_kwargs["params"]["$filter"]


# ---- create_task ----

@pytest.mark.asyncio
async def test_create_task(mock_context):
    mock_context.fetch = make_fetch({"activityid": "new-t1", "subject": "Call client"})
    result = await dynamics365.execute_action(
        "create_task",
        {"subject": "Call client", "priority": "High", "due_date": "2026-07-01"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["task"]["subject"] == "Call client"


@pytest.mark.asyncio
async def test_create_task_priority_mapping(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action("create_task", {"subject": "Low prio", "priority": "Low"}, mock_context)
    call_json = mock_context.fetch.call_args[1]["json"]
    assert call_json["prioritycode"] == 0


@pytest.mark.asyncio
async def test_create_task_with_regarding(mock_context):
    mock_context.fetch = make_fetch(None)
    await dynamics365.execute_action(
        "create_task",
        {"subject": "Follow up", "regarding_id": "a1", "regarding_type": "account"},
        mock_context,
    )
    call_json = mock_context.fetch.call_args[1]["json"]
    assert "regardingobjectid_account@odata.bind" in call_json
    assert "/accounts(a1)" in call_json["regardingobjectid_account@odata.bind"]


@pytest.mark.asyncio
async def test_create_task_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("auth error"))
    result = await dynamics365.execute_action("create_task", {"subject": "Test"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "auth error" in result.result.message

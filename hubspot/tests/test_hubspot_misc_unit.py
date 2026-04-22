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

_spec = importlib.util.spec_from_file_location("hubspot_mod", os.path.join(_parent, "hubspot.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

hubspot = _mod.hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- Lists ----


class TestGetLists:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "lists": [
                    {"listId": "1", "name": "Newsletter"},
                    {"listId": "2", "name": "Leads"},
                ],
                "total": 2,
                "hasMore": False,
            },
        )

        result = await hubspot.execute_action("get_lists", {}, mock_context)

        data = result.result.data
        assert data["total_lists"] == 2
        assert len(data["lists"]) == 2
        assert data["lists"][0]["name"] == "Newsletter"
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"lists": [], "total": 0, "hasMore": False}
        )

        await hubspot.execute_action("get_lists", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args[0][0] == "https://api.hubapi.com/crm/v3/lists/search"

    @pytest.mark.asyncio
    async def test_with_processing_type_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"lists": [], "total": 0, "hasMore": False}
        )

        await hubspot.execute_action("get_lists", {"processing_types": ["MANUAL"]}, mock_context)

        call_args = mock_context.fetch.call_args
        body = call_args[1]["json"]
        assert body["processingTypes"] == ["MANUAL"]

    @pytest.mark.asyncio
    async def test_response_data_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "lists": [{"listId": "1", "name": "A"}],
                "total": 5,
                "hasMore": True,
            },
        )

        result = await hubspot.execute_action("get_lists", {}, mock_context)

        data = result.result.data
        assert "lists" in data
        assert "total_lists" in data
        assert "total_available" in data
        assert "has_more" in data
        assert data["total_available"] == 5
        assert data["has_more"] is True


class TestGetList:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "list": {
                    "listId": "42",
                    "name": "VIP Contacts",
                    "processingType": "MANUAL",
                }
            },
        )

        result = await hubspot.execute_action("get_list", {"list_id": "42"}, mock_context)

        data = result.result.data
        assert data["list"]["listId"] == "42"
        assert data["list"]["name"] == "VIP Contacts"

    @pytest.mark.asyncio
    async def test_request_url_contains_list_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"list": {}})

        await hubspot.execute_action("get_list", {"list_id": "99"}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v3/lists/99" in url

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"list": {"listId": "7", "name": "Test", "processingType": "DYNAMIC"}},
        )

        result = await hubspot.execute_action("get_list", {"list_id": "7"}, mock_context)

        data = result.result.data
        assert "list" in data
        assert data["list"]["processingType"] == "DYNAMIC"


class TestSearchLists:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "lists": [
                    {"listId": "10", "name": "Newsletter Subscribers"},
                ]
            },
        )

        result = await hubspot.execute_action("search_lists", {"query": "Newsletter"}, mock_context)

        data = result.result.data
        assert data["total"] == 1
        assert data["results"][0]["name"] == "Newsletter Subscribers"

    @pytest.mark.asyncio
    async def test_request_url_and_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"lists": []})

        await hubspot.execute_action("search_lists", {"query": "VIP"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args[0][0] == "https://api.hubapi.com/crm/v3/lists/search"
        body = call_args[1]["json"]
        assert body["query"] == "VIP"

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"lists": [{"listId": "1"}, {"listId": "2"}]},
        )

        result = await hubspot.execute_action("search_lists", {"query": "test"}, mock_context)

        data = result.result.data
        assert "results" in data
        assert "total" in data
        assert "has_more" in data
        assert data["total"] == 2


class TestGetListMemberships:
    @pytest.mark.asyncio
    async def test_happy_path_single_page(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"recordId": "101", "membershipTimestamp": "2025-01-01T00:00:00Z"},
                    {"recordId": "102", "membershipTimestamp": "2025-01-02T00:00:00Z"},
                ],
                "paging": {},
            },
        )

        result = await hubspot.execute_action("get_list_memberships", {"list_id": "5"}, mock_context)

        data = result.result.data
        assert data["list_id"] == "5"
        assert data["total_memberships"] == 2
        assert len(data["memberships"]) == 2
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_request_url_contains_list_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "paging": {}})

        await hubspot.execute_action("get_list_memberships", {"list_id": "88"}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v3/lists/88/memberships" in url

    @pytest.mark.asyncio
    async def test_pagination_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "paging": {}})

        await hubspot.execute_action("get_list_memberships", {"list_id": "5", "limit": 50}, mock_context)

        params = mock_context.fetch.call_args[1]["params"]
        assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_response_has_memberships(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": [{"recordId": "1"}], "paging": {}},
        )

        result = await hubspot.execute_action("get_list_memberships", {"list_id": "5"}, mock_context)

        data = result.result.data
        assert "memberships" in data
        assert "total_memberships" in data
        assert "has_more" in data
        assert "list_id" in data


class TestGetListMembers:
    LIST_META_RESPONSE = FetchResponse(
        status=200,
        headers={},
        data={
            "list": {
                "listId": "42",
                "name": "Newsletter",
                "size": 2,
                "processingType": "MANUAL",
                "objectTypeId": "0-1",
            }
        },
    )

    MEMBERSHIPS_RESPONSE = FetchResponse(
        status=200,
        headers={},
        data={
            "results": [
                {"recordId": "101", "membershipTimestamp": "2025-01-01T00:00:00Z"},
                {"recordId": "102", "membershipTimestamp": "2025-01-02T00:00:00Z"},
            ],
            "paging": {},
        },
    )

    CONTACTS_RESPONSE = FetchResponse(
        status=200,
        headers={},
        data={
            "results": [
                {"id": "101", "properties": {"email": "a@example.com", "firstname": "Alice"}},
                {"id": "102", "properties": {"email": "b@example.com", "firstname": "Bob"}},
            ]
        },
    )

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        result = await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        data = result.result.data
        assert data["retrieved_count"] == 2
        assert data["total_members"] == 2
        assert data["list_metadata"]["name"] == "Newsletter"
        assert len(data["members"]) == 2
        assert data["members"][0]["email"] == "a@example.com"
        assert data["members"][1]["email"] == "b@example.com"

    @pytest.mark.asyncio
    async def test_request_sequence(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        assert mock_context.fetch.call_count == 3
        # Call 1: list metadata
        assert "/crm/v3/lists/42" in mock_context.fetch.call_args_list[0].args[0]
        # Call 2: memberships
        assert "/crm/v3/lists/42/memberships" in mock_context.fetch.call_args_list[1].args[0]
        # Call 3: batch contact read
        assert "/contacts/batch/read" in mock_context.fetch.call_args_list[2].args[0]

    @pytest.mark.asyncio
    async def test_batch_contact_payload(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        batch_call = mock_context.fetch.call_args_list[2]
        assert batch_call.kwargs["method"] == "POST"
        payload = batch_call.kwargs["json"]
        ids = [inp["id"] for inp in payload["inputs"]]
        assert "101" in ids
        assert "102" in ids

    @pytest.mark.asyncio
    async def test_membership_timestamps_included(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        result = await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        members = result.result.data["members"]
        assert members[0]["membership_timestamp"] == "2025-01-01T00:00:00Z"
        assert members[1]["membership_timestamp"] == "2025-01-02T00:00:00Z"

    @pytest.mark.asyncio
    async def test_timestamps_excluded_when_disabled(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        result = await hubspot.execute_action(
            "get_list_members",
            {"list_id": "42", "include_membership_timestamps": False},
            mock_context,
        )

        members = result.result.data["members"]
        assert "membership_timestamp" not in members[0]

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        result = await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        data = result.result.data
        assert "list_metadata" in data
        assert "members" in data
        assert "total_members" in data
        assert "retrieved_count" in data
        assert "performance_stats" in data
        assert "total_api_calls" in data["performance_stats"]

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        empty_memberships = FetchResponse(
            status=200, headers={}, data={"results": [], "paging": {}}
        )
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            empty_memberships,
        ]

        result = await hubspot.execute_action("get_list_members", {"list_id": "42"}, mock_context)

        data = result.result.data
        assert data["members"] == []
        assert data["retrieved_count"] == 0
        # No batch contact call needed for empty list
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_custom_contact_properties(self, mock_context):
        mock_context.fetch.side_effect = [
            self.LIST_META_RESPONSE,
            self.MEMBERSHIPS_RESPONSE,
            self.CONTACTS_RESPONSE,
        ]

        await hubspot.execute_action(
            "get_list_members",
            {"list_id": "42", "contact_properties": ["email", "company"]},
            mock_context,
        )

        batch_call = mock_context.fetch.call_args_list[2]
        payload = batch_call.kwargs["json"]
        assert payload["properties"] == ["email", "company"]


# ---- Associations ----


class TestGetContactAssociations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "c1"}]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "d1"}, {"toObjectId": "d2"}]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={"results": []},
            ),
        ]

        result = await hubspot.execute_action(
            "get_contact_associations",
            {"contact_id": "100", "association_types": ["companies", "deals", "meetings"]},
            mock_context,
        )

        data = result.result.data
        assert data["contact_id"] == "100"
        assert data["total_associations"] == 3
        assert data["summary"]["companies_count"] == 1
        assert data["summary"]["deals_count"] == 2
        assert data["summary"]["meetings_count"] == 0

    @pytest.mark.asyncio
    async def test_request_url_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action(
            "get_contact_associations",
            {"contact_id": "55", "association_types": ["companies"]},
            mock_context,
        )

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v4/objects/contacts/55/associations/companies" in url

    @pytest.mark.asyncio
    async def test_response_associations_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"toObjectId": "x1"}]}
        )

        result = await hubspot.execute_action(
            "get_contact_associations",
            {"contact_id": "55", "association_types": ["deals"]},
            mock_context,
        )

        data = result.result.data
        assert "associations" in data
        assert "summary" in data
        assert "total_associations" in data
        assert data["associations"]["deals"] == [{"toObjectId": "x1"}]

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("API error"),
            FetchResponse(status=200, headers={}, data={"results": [{"toObjectId": "d1"}]}),
        ]

        result = await hubspot.execute_action(
            "get_contact_associations",
            {"contact_id": "55", "association_types": ["companies", "deals"]},
            mock_context,
        )

        data = result.result.data
        assert data["summary"]["companies_count"] == 0
        assert data["associations"]["companies"] == []
        assert data["summary"]["deals_count"] == 1


class TestGetCompanyAssociations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "c1"}, {"toObjectId": "c2"}]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "d1"}]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={"results": []},
            ),
        ]

        result = await hubspot.execute_action(
            "get_company_associations",
            {"company_id": "200", "association_types": ["contacts", "deals", "tickets"]},
            mock_context,
        )

        data = result.result.data
        assert data["company_id"] == "200"
        assert data["total_associations"] == 3
        assert data["summary"]["contacts_count"] == 2
        assert data["summary"]["deals_count"] == 1
        assert data["summary"]["tickets_count"] == 0

    @pytest.mark.asyncio
    async def test_request_url_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action(
            "get_company_associations",
            {"company_id": "200", "association_types": ["contacts"]},
            mock_context,
        )

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v4/objects/companies/200/associations/contacts" in url

    @pytest.mark.asyncio
    async def test_response_associations_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"toObjectId": "c1"}]}
        )

        result = await hubspot.execute_action(
            "get_company_associations",
            {"company_id": "200", "association_types": ["deals"]},
            mock_context,
        )

        data = result.result.data
        assert "associations" in data
        assert "summary" in data
        assert data["associations"]["deals"] == [{"toObjectId": "c1"}]

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("timeout"),
            FetchResponse(status=200, headers={}, data={"results": []}),
        ]

        result = await hubspot.execute_action(
            "get_company_associations",
            {"company_id": "200", "association_types": ["contacts", "deals"]},
            mock_context,
        )

        data = result.result.data
        assert data["summary"]["contacts_count"] == 0
        assert data["associations"]["contacts"] == []
        assert data["summary"]["deals_count"] == 0


class TestGetDealAssociations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "c1"}]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={"results": [{"toObjectId": "co1"}]},
            ),
        ]

        result = await hubspot.execute_action(
            "get_deal_associations",
            {"deal_id": "300", "association_types": ["contacts", "companies"]},
            mock_context,
        )

        data = result.result.data
        assert data["deal_id"] == "300"
        assert data["total_associations"] == 2
        assert data["summary"]["contacts_count"] == 1
        assert data["summary"]["companies_count"] == 1

    @pytest.mark.asyncio
    async def test_request_url_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action(
            "get_deal_associations",
            {"deal_id": "300", "association_types": ["companies"]},
            mock_context,
        )

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v4/objects/deals/300/associations/companies" in url

    @pytest.mark.asyncio
    async def test_response_associations_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"toObjectId": "co1"}]}
        )

        result = await hubspot.execute_action(
            "get_deal_associations",
            {"deal_id": "300", "association_types": ["contacts"]},
            mock_context,
        )

        data = result.result.data
        assert "associations" in data
        assert "summary" in data
        assert data["associations"]["contacts"] == [{"toObjectId": "co1"}]

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("server error"),
            FetchResponse(status=200, headers={}, data={"results": [{"toObjectId": "c1"}]}),
        ]

        result = await hubspot.execute_action(
            "get_deal_associations",
            {"deal_id": "300", "association_types": ["contacts", "companies"]},
            mock_context,
        )

        data = result.result.data
        assert data["summary"]["contacts_count"] == 0
        assert data["associations"]["contacts"] == []
        assert data["summary"]["companies_count"] == 1


# ---- Owner ----


class TestGetOwner:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "77",
                "email": "owner@example.com",
                "firstName": "Jane",
                "lastName": "Doe",
            },
        )

        result = await hubspot.execute_action("get_owner", {"owner_id": "77"}, mock_context)

        data = result.result.data
        assert data["owner"]["id"] == "77"
        assert data["owner"]["email"] == "owner@example.com"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action("get_owner", {"owner_id": "999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve owner" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_contains_owner_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "77", "email": "a@b.com"})

        await hubspot.execute_action("get_owner", {"owner_id": "77"}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert "/crm/v3/owners/77" in url

    @pytest.mark.asyncio
    async def test_response_data_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "10", "email": "test@example.com", "firstName": "A", "lastName": "B"},
        )

        result = await hubspot.execute_action("get_owner", {"owner_id": "10"}, mock_context)

        data = result.result.data
        assert "owner" in data
        assert isinstance(data["owner"], dict)
        assert data["owner"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_error_message_content(self, mock_context):
        mock_context.fetch.side_effect = Exception("404 Owner not found")

        result = await hubspot.execute_action("get_owner", {"owner_id": "bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "owner" in result.result.message.lower()
        assert "404" in result.result.message


# ---- Marketing Emails ----


class TestGetMarketingEmails:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "e1",
                        "name": "Welcome Email",
                        "subject": "Welcome!",
                        "type": "REGULAR",
                        "state": "PUBLISHED",
                        "createdAt": "2025-01-01",
                        "updatedAt": "2025-01-02",
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_marketing_emails", {}, mock_context)

        data = result.result.data
        assert data["total"] == 1
        assert data["emails"][0]["id"] == "e1"
        assert data["emails"][0]["name"] == "Welcome Email"
        assert data["emails"][0]["subject"] == "Welcome!"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_marketing_emails", {}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert url == "https://api.hubapi.com/marketing/v3/emails"

    @pytest.mark.asyncio
    async def test_with_pagination_after(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_marketing_emails", {"after": "abc123"}, mock_context)

        params = mock_context.fetch.call_args[1]["params"]
        assert params["after"] == "abc123"

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [{"id": "e1", "name": "X", "subject": "Y"}],
                "paging": {"next": {"after": "xyz"}},
            },
        )

        result = await hubspot.execute_action("get_marketing_emails", {}, mock_context)

        data = result.result.data
        assert "emails" in data
        assert "total" in data
        assert "paging" in data
        assert data["paging"]["next"]["after"] == "xyz"


# ---- Campaigns ----


class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "camp1",
                        "properties": {
                            "hs_name": "Spring Sale",
                            "hs_start_date": "2025-03-01",
                            "hs_end_date": "2025-03-31",
                            "hs_campaign_status": "ACTIVE",
                            "hs_notes": None,
                            "hs_owner": "owner1",
                        },
                        "createdAt": "2025-02-15",
                        "updatedAt": "2025-03-01",
                    }
                ],
                "total": 1,
            },
        )

        result = await hubspot.execute_action("get_campaigns", {}, mock_context)

        data = result.result.data
        assert data["total"] == 1
        assert data["campaigns"][0]["id"] == "camp1"
        assert data["campaigns"][0]["name"] == "Spring Sale"
        assert data["campaigns"][0]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "total": 0})

        await hubspot.execute_action("get_campaigns", {}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert url == "https://api.hubapi.com/marketing/v3/campaigns"

    @pytest.mark.asyncio
    async def test_with_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "total": 0})

        await hubspot.execute_action("get_campaigns", {"limit": 10}, mock_context)

        params = mock_context.fetch.call_args[1]["params"]
        assert params["limit"] == 10

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "c1", "properties": {"hs_name": "A"}, "createdAt": "2025-01-01", "updatedAt": "2025-01-02"}
                ],
                "total": 5,
                "paging": {"next": {"after": "c2"}},
            },
        )

        result = await hubspot.execute_action("get_campaigns", {}, mock_context)

        data = result.result.data
        assert "campaigns" in data
        assert "total" in data
        assert data["total"] == 5
        assert "paging" in data


class TestGetCampaign:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "camp42",
                "properties": {
                    "hs_name": "Product Launch",
                    "hs_start_date": "2025-04-01",
                    "hs_end_date": "2025-04-30",
                    "hs_campaign_status": "ACTIVE",
                    "hs_notes": "Big launch",
                    "hs_owner": "owner2",
                    "hs_audience": "Enterprise",
                    "hs_currency_code": "USD",
                    "hs_utm": "spring2025",
                    "hs_color_hex": "#FF5733",
                    "hs_budget_items_sum_amount": "10000",
                    "hs_spend_items_sum_amount": "5000",
                },
                "createdAt": "2025-03-15",
                "updatedAt": "2025-04-01",
                "assets": {"emails": 3, "landing_pages": 1},
            },
        )

        result = await hubspot.execute_action("get_campaign", {"campaign_id": "camp42"}, mock_context)

        data = result.result.data
        campaign = data["campaign"]
        assert campaign["id"] == "camp42"
        assert campaign["name"] == "Product Launch"
        assert campaign["budget_total"] == "10000"
        assert campaign["assets"] == {"emails": 3, "landing_pages": 1}

    @pytest.mark.asyncio
    async def test_request_url_contains_campaign_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "c99", "properties": {}, "createdAt": "", "updatedAt": ""},
        )

        await hubspot.execute_action("get_campaign", {"campaign_id": "c99"}, mock_context)

        url = mock_context.fetch.call_args[0][0]
        assert "/marketing/v3/campaigns/c99" in url

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "c1",
                "properties": {"hs_name": "Test", "hs_campaign_status": "DRAFT"},
                "createdAt": "2025-01-01",
                "updatedAt": "2025-01-02",
            },
        )

        result = await hubspot.execute_action("get_campaign", {"campaign_id": "c1"}, mock_context)

        data = result.result.data
        assert "campaign" in data
        assert data["campaign"]["id"] == "c1"
        assert data["campaign"]["name"] == "Test"
        assert data["campaign"]["status"] == "DRAFT"


class TestGetCampaignAssets:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "lp1",
                        "name": "Spring Landing Page",
                        "metrics": {"VIEWS": 500, "SUBMISSIONS": 25},
                    }
                ]
            },
        )

        result = await hubspot.execute_action(
            "get_campaign_assets",
            {"campaign_id": "camp42", "asset_type": "LANDING_PAGE"},
            mock_context,
        )

        data = result.result.data
        assert data["campaign_id"] == "camp42"
        assert data["asset_type"] == "LANDING_PAGE"
        assert data["total"] == 1
        assert data["assets"][0]["name"] == "Spring Landing Page"
        assert data["assets"][0]["metrics"]["VIEWS"] == 500

    @pytest.mark.asyncio
    async def test_request_url_contains_campaign_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action(
            "get_campaign_assets",
            {"campaign_id": "c55", "asset_type": "FORM"},
            mock_context,
        )

        url = mock_context.fetch.call_args[0][0]
        assert "/marketing/v3/campaigns/c55/assets/FORM" in url

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [{"id": "a1", "name": "Form A", "metrics": {}}],
                "paging": {"next": {"after": "a2"}},
            },
        )

        result = await hubspot.execute_action(
            "get_campaign_assets",
            {"campaign_id": "c55", "asset_type": "FORM"},
            mock_context,
        )

        data = result.result.data
        assert "assets" in data
        assert "total" in data
        assert "campaign_id" in data
        assert "asset_type" in data
        assert "paging" in data
        assert data["total"] == 1


class TestGetCampaignPerformance:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        landing_page_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "lp1",
                        "name": "Main LP",
                        "metrics": {
                            "VIEWS": 1000,
                            "SUBMISSIONS": 50,
                            "CONTACTS_FIRST_TOUCH": 30,
                            "CONTACTS_LAST_TOUCH": 20,
                            "CUSTOMERS": 5,
                        },
                    }
                ],
                "paging": {},
            },
        )
        email_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "em1",
                        "name": "Promo Email",
                        "metrics": {"SENT": 2000, "OPEN": 800, "CLICKS": 150},
                    }
                ],
                "paging": {},
            },
        )
        form_response = FetchResponse(
            status=200,
            headers={},
            data={"results": [], "paging": {}},
        )
        blog_response = FetchResponse(
            status=200,
            headers={},
            data={"results": [], "paging": {}},
        )

        mock_context.fetch.side_effect = [
            landing_page_response,
            email_response,
            form_response,
            blog_response,
        ]

        result = await hubspot.execute_action(
            "get_campaign_performance",
            {"campaign_id": "camp42", "start_date": "2025-03-01", "end_date": "2025-03-31"},
            mock_context,
        )

        data = result.result.data
        assert data["campaign_id"] == "camp42"

        lp = data["assets"]["landing_pages"]
        assert lp["count"] == 1
        assert lp["totals"]["views"] == 1000
        assert lp["totals"]["submissions"] == 50

        emails = data["assets"]["marketing_emails"]
        assert emails["count"] == 1
        assert emails["totals"]["sent"] == 2000
        assert emails["totals"]["open"] == 800

        summary = data["summary"]
        assert summary["total_landing_page_views"] == 1000
        assert summary["total_emails_sent"] == 2000
        assert summary["total_email_clicks"] == 150
        assert summary["total_form_submissions"] == 0

    @pytest.mark.asyncio
    async def test_empty_asset_results(self, mock_context):
        empty_response = FetchResponse(status=200, headers={}, data={"results": [], "paging": {}})
        mock_context.fetch.side_effect = [empty_response] * 4

        result = await hubspot.execute_action(
            "get_campaign_performance",
            {"campaign_id": "camp1", "start_date": "2025-01-01", "end_date": "2025-01-31"},
            mock_context,
        )

        data = result.result.data
        assert data["assets"]["landing_pages"]["count"] == 0
        assert data["assets"]["marketing_emails"]["count"] == 0
        assert data["assets"]["forms"]["count"] == 0
        assert data["assets"]["blog_posts"]["count"] == 0
        assert data["summary"]["total_landing_page_views"] == 0
        assert data["summary"]["total_emails_sent"] == 0

    @pytest.mark.asyncio
    async def test_summary_calculated(self, mock_context):
        lp_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "lp1", "name": "LP1", "metrics": {"VIEWS": 200, "SUBMISSIONS": 10}},
                    {"id": "lp2", "name": "LP2", "metrics": {"VIEWS": 300, "SUBMISSIONS": 15}},
                ],
                "paging": {},
            },
        )
        email_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "em1", "name": "E1", "metrics": {"SENT": 500, "OPEN": 200, "CLICKS": 50}},
                ],
                "paging": {},
            },
        )
        empty = FetchResponse(status=200, headers={}, data={"results": [], "paging": {}})
        mock_context.fetch.side_effect = [lp_response, email_response, empty, empty]

        result = await hubspot.execute_action(
            "get_campaign_performance",
            {"campaign_id": "camp1", "start_date": "2025-01-01", "end_date": "2025-01-31"},
            mock_context,
        )

        data = result.result.data
        assert data["summary"]["total_landing_page_views"] == 500
        assert data["summary"]["total_landing_page_submissions"] == 25
        assert data["summary"]["total_emails_sent"] == 500
        assert data["summary"]["total_email_opens"] == 200
        assert data["summary"]["total_email_clicks"] == 50

    @pytest.mark.asyncio
    async def test_exception_in_one_asset_type(self, mock_context):
        lp_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "lp1", "name": "LP1", "metrics": {"VIEWS": 100, "SUBMISSIONS": 5}},
                ],
                "paging": {},
            },
        )
        empty = FetchResponse(status=200, headers={}, data={"results": [], "paging": {}})
        mock_context.fetch.side_effect = [
            lp_response,
            Exception("email API down"),
            empty,
            empty,
        ]

        result = await hubspot.execute_action(
            "get_campaign_performance",
            {"campaign_id": "camp1", "start_date": "2025-01-01", "end_date": "2025-01-31"},
            mock_context,
        )

        data = result.result.data
        assert data["assets"]["landing_pages"]["count"] == 1
        assert data["assets"]["landing_pages"]["totals"]["views"] == 100
        assert data["assets"]["marketing_emails"]["count"] == 0
        assert "error" in data["assets"]["marketing_emails"]
        assert data["assets"]["forms"]["count"] == 0

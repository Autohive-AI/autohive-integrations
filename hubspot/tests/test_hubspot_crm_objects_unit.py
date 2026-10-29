import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit

OBJECTS_URL = "https://api.hubapi.com/crm/objects/2026-09"
ACCOUNT_URL = "https://api.hubapi.com/account-info/2026-09/details"
OWNERS_URL = "https://api.hubapi.com/crm/owners/2026-09"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def search_page(*ids, after=None, total=None):
    data = {"total": len(ids) if total is None else total, "results": [{"id": i, "properties": {}} for i in ids]}
    if after:
        data["paging"] = {"next": {"after": after}}
    return ok(data)


def account(ui_domain="app.hubspot.com"):
    return ok({"portalId": 4242, "uiDomain": ui_domain, "timeZone": "Pacific/Auckland"})


def deal_stage(stage):
    return {"propertyName": "dealstage", "operator": "EQ", "value": stage}


async def search(mock_context, **inputs):
    return await hubspot.execute_action("search_crm_objects", {"object_type": "deals", **inputs}, mock_context)


# ---- Search CRM records ----


class TestSearchCrmObjects:
    @pytest.mark.asyncio
    async def test_filters_are_one_and_group(self, mock_context):
        mock_context.fetch.return_value = search_page("1")

        await search(
            mock_context,
            filters=[deal_stage("closedwon"), {"propertyName": "amount", "operator": "GTE", "value": 10000}],
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{OBJECTS_URL}/deals/search"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "limit": 100,
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"},
                        {"propertyName": "amount", "operator": "GTE", "value": "10000"},
                    ]
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_filter_groups_are_ored(self, mock_context):
        mock_context.fetch.return_value = search_page()

        await search(mock_context, filter_groups=[{"filters": [deal_stage("a")]}, {"filters": [deal_stage("b")]}])

        groups = mock_context.fetch.call_args.kwargs["json"]["filterGroups"]
        assert groups == [{"filters": [deal_stage("a")]}, {"filters": [deal_stage("b")]}]

    @pytest.mark.asyncio
    async def test_values_are_sent_as_hubspot_strings(self, mock_context):
        mock_context.fetch.return_value = search_page()

        await search(
            mock_context,
            filters=[
                {"propertyName": "hs_is_closed", "operator": "EQ", "value": False},
                {"propertyName": "amount", "operator": "BETWEEN", "value": 5, "highValue": 10.5},
                {"propertyName": "pipeline", "operator": "IN", "values": ["default", 7]},
            ],
        )

        assert mock_context.fetch.call_args.kwargs["json"]["filterGroups"][0]["filters"] == [
            {"propertyName": "hs_is_closed", "operator": "EQ", "value": "false"},
            {"propertyName": "amount", "operator": "BETWEEN", "value": "5", "highValue": "10.5"},
            {"propertyName": "pipeline", "operator": "IN", "values": ["default", "7"]},
        ]

    @pytest.mark.asyncio
    async def test_associated_with_alone_is_its_own_group(self, mock_context):
        mock_context.fetch.return_value = search_page()

        await hubspot.execute_action(
            "search_crm_objects",
            {"object_type": "emails", "associated_with": {"object_type": "deals", "id": "55"}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["filterGroups"] == [
            {"filters": [{"propertyName": "associations.deal", "operator": "EQ", "value": "55"}]}
        ]

    @pytest.mark.asyncio
    async def test_associated_with_is_added_to_every_group(self, mock_context):
        mock_context.fetch.return_value = search_page()

        await search(
            mock_context,
            filter_groups=[{"filters": [deal_stage("a")]}, {"filters": [deal_stage("b")]}],
            associated_with={"object_type": "companies", "id": "9"},
        )

        link = {"propertyName": "associations.company", "operator": "EQ", "value": "9"}
        assert mock_context.fetch.call_args.kwargs["json"]["filterGroups"] == [
            {"filters": [link, deal_stage("a")]},
            {"filters": [link, deal_stage("b")]},
        ]

    @pytest.mark.asyncio
    async def test_filters_and_filter_groups_together_rejected(self, mock_context):
        result = await search(mock_context, filters=[deal_stage("a")], filter_groups=[{"filters": [deal_stage("b")]}])

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Give filters or filter_groups, not both"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_more_than_18_filters_rejected(self, mock_context):
        group = {"filters": [deal_stage(str(n)) for n in range(5)]}

        result = await search(mock_context, filter_groups=[group] * 4)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "HubSpot allows at most 18 filters in a search; 20 were given"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_filter_counts_toward_group_limit(self, mock_context):
        result = await search(
            mock_context,
            filters=[deal_stage(str(n)) for n in range(6)],
            associated_with={"object_type": "contacts", "id": "1"},
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "HubSpot allows at most 6 filters in a group; one has 7"

    @pytest.mark.asyncio
    async def test_query_properties_sort_and_cursor_sent(self, mock_context):
        mock_context.fetch.return_value = search_page()

        await search(
            mock_context,
            query="renewal",
            properties=["dealname", "amount"],
            sort_property="closedate",
            sort_direction="DESCENDING",
            limit=200,
            after="200",
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {
            "limit": 200,
            "query": "renewal",
            "properties": ["dealname", "amount"],
            "sorts": [{"propertyName": "closedate", "direction": "DESCENDING"}],
            "after": "200",
        }

    @pytest.mark.asyncio
    async def test_next_page_cursor_returned(self, mock_context):
        mock_context.fetch.return_value = search_page("1", "2", after="2", total=40)

        result = await search(mock_context, limit=2)

        data = result.result.data
        assert [record["id"] for record in data["results"]] == ["1", "2"]
        assert (data["count"], data["total"], data["has_more"], data["after"]) == (2, 40, True, "2")

    @pytest.mark.asyncio
    async def test_last_page_has_no_cursor(self, mock_context):
        mock_context.fetch.return_value = search_page("1")

        data = (await search(mock_context)).result.data

        assert (data["has_more"], data["after"]) == (False, None)

    @pytest.mark.asyncio
    async def test_record_urls_use_the_account_domain(self, mock_context):
        mock_context.fetch.side_effect = [search_page("7"), account("app-eu1.hubspot.com")]

        result = await search(mock_context, include_urls=True)

        assert mock_context.fetch.call_args.args[0] == ACCOUNT_URL
        assert result.result.data["results"][0]["url"] == "https://app-eu1.hubspot.com/contacts/4242/record/0-3/7"

    @pytest.mark.asyncio
    async def test_url_hubspot_returns_is_kept(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"total": 1, "results": [{"id": "7", "properties": {}, "url": "https://app.hubspot.com/x/7"}]}
        )

        result = await search(mock_context, include_urls=True)

        assert result.result.data["results"][0]["url"] == "https://app.hubspot.com/x/7"
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_custom_object_records_get_urls(self, mock_context):
        mock_context.fetch.side_effect = [search_page("7"), account()]

        result = await hubspot.execute_action(
            "search_crm_objects", {"object_type": "2-123", "include_urls": True}, mock_context
        )

        assert result.result.data["results"][0]["url"] == "https://app.hubspot.com/contacts/4242/record/2-123/7"

    @pytest.mark.asyncio
    async def test_types_without_record_pages_get_no_urls(self, mock_context):
        mock_context.fetch.return_value = search_page("7")

        result = await hubspot.execute_action(
            "search_crm_objects", {"object_type": "tasks", "include_urls": True}, mock_context
        )

        assert "url" not in result.result.data["results"][0]
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Unknown property dealstagez")

        result = await search(mock_context, filters=[{"propertyName": "dealstagez", "operator": "HAS_PROPERTY"}])

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to search deals: HTTP 400: Unknown property dealstagez"

    @pytest.mark.asyncio
    async def test_object_type_cannot_change_the_path(self, mock_context):
        result = await hubspot.execute_action("search_crm_objects", {"object_type": "deals/../owners"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# ---- Get CRM records ----


def links(record_id, *to_ids, after=None):
    row = {"from": {"id": record_id}, "to": [{"toObjectId": int(i), "associationTypes": []} for i in to_ids]}
    if after:
        row["paging"] = {"next": {"after": after}}
    return {"status": "COMPLETE", "results": [row]}


class TestGetCrmObjects:
    @pytest.mark.asyncio
    async def test_reads_records_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"status": "COMPLETE", "results": [{"id": "1", "properties": {}}]})

        result = await hubspot.execute_action(
            "get_crm_objects",
            {"object_type": "contacts", "ids": ["1"], "properties": ["email"]},
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{OBJECTS_URL}/contacts/batch/read"
        assert call.kwargs["json"] == {"inputs": [{"id": "1"}], "properties": ["email"], "propertiesWithHistory": []}
        assert result.result.data == {"results": [{"id": "1", "properties": {}}], "total": 1, "not_found": []}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("properties", [None, [], ["firstname"], ["email", "firstname"]])
    @pytest.mark.parametrize("id_property", ["email", "external_id"])
    async def test_unique_lookup_preserves_default_or_explicit_properties(self, mock_context, properties, id_property):
        mock_context.fetch.return_value = ok({"status": "COMPLETE", "results": []})
        inputs = {"object_type": "contacts", "ids": ["lookup-value"], "id_property": id_property}
        if properties is not None:
            inputs["properties"] = properties
        original_properties = list(properties or [])

        await hubspot.execute_action("get_crm_objects", inputs, mock_context)

        expected = list(original_properties)
        if expected and id_property not in expected:
            expected.append(id_property)
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "inputs": [{"id": "lookup-value"}],
            "properties": expected,
            "propertiesWithHistory": [],
            "idProperty": id_property,
        }
        assert properties is None or properties == original_properties

    @pytest.mark.asyncio
    async def test_missing_ids_reported(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "status": "COMPLETE",
                "results": [{"id": "1", "properties": {}}],
                "errors": [{"category": "OBJECT_NOT_FOUND", "context": {"ids": ["2", "3"]}}],
            },
            status=207,
        )

        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "deals", "ids": ["1", "2", "3"]}, mock_context
        )

        assert result.result.data["not_found"] == ["2", "3"]
        assert "errors" not in result.result.data

    @pytest.mark.asyncio
    async def test_no_ids_found_is_not_an_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "deals", "ids": ["8", "9"]}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data == {"results": [], "total": 0, "not_found": ["8", "9"]}

    @pytest.mark.asyncio
    async def test_other_record_errors_reported(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"status": "COMPLETE", "results": [], "errors": [{"category": "VALIDATION_ERROR", "message": "Bad ID"}]},
            status=207,
        )

        result = await hubspot.execute_action("get_crm_objects", {"object_type": "deals", "ids": ["x"]}, mock_context)

        assert result.result.data["errors"] == ["Bad ID"]

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Missing scopes")

        result = await hubspot.execute_action("get_crm_objects", {"object_type": "quotes", "ids": ["1"]}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to read quotes: HTTP 403: Missing scopes"

    @pytest.mark.asyncio
    async def test_linked_records_added_per_type(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"status": "COMPLETE", "results": [{"id": "5", "properties": {}}]}),
            ok(links("5", "11", "12")),
            ok({"status": "COMPLETE", "results": [], "errors": [{"category": "OBJECT_NOT_FOUND"}]}, status=207),
        ]

        result = await hubspot.execute_action(
            "get_crm_objects",
            {"object_type": "deals", "ids": ["5"], "associations": ["contacts", "companies"]},
            mock_context,
        )

        record = result.result.data["results"][0]
        assert [link["toObjectId"] for link in record["associations"]["contacts"]] == [11, 12]
        assert record["associations"]["companies"] == []
        assert "associations_with_more" not in record
        urls = [call.args[0] for call in mock_context.fetch.call_args_list[1:]]
        assert urls == [
            "https://api.hubapi.com/crm/associations/2026-09/deals/contacts/batch/read",
            "https://api.hubapi.com/crm/associations/2026-09/deals/companies/batch/read",
        ]

    @pytest.mark.asyncio
    async def test_linked_records_capped_at_100(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"status": "COMPLETE", "results": [{"id": "5", "properties": {}}]}),
            ok(links("5", *range(1, 101), after="next")),
        ]

        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "companies", "ids": ["5"], "associations": ["contacts"]}, mock_context
        )

        record = result.result.data["results"][0]
        assert len(record["associations"]["contacts"]) == 100
        assert record["associations_with_more"] == ["contacts"]
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_failed_link_read_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"status": "COMPLETE", "results": [{"id": "5", "properties": {}}]}),
            HTTPError(500, "Server error"),
        ]

        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "deals", "ids": ["5"], "associations": ["contacts"]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Read 1 deals but not their links: HTTP 500: Server error"

    @pytest.mark.asyncio
    async def test_record_urls_added(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"status": "COMPLETE", "results": [{"id": "5", "properties": {}}]}),
            account(),
        ]

        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "tickets", "ids": ["5"], "include_urls": True}, mock_context
        )

        assert result.result.data["results"][0]["url"] == "https://app.hubspot.com/contacts/4242/record/0-5/5"

    @pytest.mark.asyncio
    async def test_more_than_100_ids_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action(
            "get_crm_objects", {"object_type": "deals", "ids": [str(n) for n in range(101)]}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# ---- Object properties ----


PROPERTIES = {
    "results": [
        {
            "name": "dealstage",
            "label": "Deal Stage",
            "type": "enumeration",
            "fieldType": "select",
            "groupName": "dealinformation",
            "description": "Stage of the deal",
            "hubspotDefined": True,
            "options": [{"label": "Closed Won", "value": "closedwon", "displayOrder": 1, "hidden": False}],
        },
        {"name": "architect_name", "label": "Architect", "type": "string", "fieldType": "text"},
    ]
}


class TestGetObjectProperties:
    @pytest.mark.asyncio
    async def test_lists_names_labels_and_types(self, mock_context):
        mock_context.fetch.return_value = ok(PROPERTIES)

        result = await hubspot.execute_action("get_object_properties", {"object_type": "deals"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.hubapi.com/crm/properties/2026-09/deals"
        assert result.result.data == {
            "properties": [
                {"name": "dealstage", "label": "Deal Stage", "type": "enumeration"},
                {"name": "architect_name", "label": "Architect", "type": "string"},
            ],
            "total": 2,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", ["ARCHITECT", "_name"])
    async def test_query_matches_label_or_name(self, mock_context, query):
        mock_context.fetch.return_value = ok(PROPERTIES)

        result = await hubspot.execute_action(
            "get_object_properties", {"object_type": "deals", "query": query}, mock_context
        )

        assert [prop["name"] for prop in result.result.data["properties"]] == ["architect_name"]

    @pytest.mark.asyncio
    async def test_details_include_option_values(self, mock_context):
        mock_context.fetch.return_value = ok(PROPERTIES)

        result = await hubspot.execute_action(
            "get_object_properties", {"object_type": "deals", "include_details": True}, mock_context
        )

        stage, architect = result.result.data["properties"]
        assert stage["options"] == [{"label": "Closed Won", "value": "closedwon"}]
        assert stage["hubspotDefined"] is True
        assert architect["options"] == []
        assert architect["hubspotDefined"] is False

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Unable to infer object type")

        result = await hubspot.execute_action("get_object_properties", {"object_type": "widgets"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to list widgets properties: HTTP 400: Unable to infer object type"


# ---- Owners ----


def owners_page(*owners, after=None):
    data = {"results": list(owners)}
    if after:
        data["paging"] = {"next": {"after": after}}
    return ok(data)


def owner(owner_id, first, last, email=None):
    return {"id": owner_id, "firstName": first, "lastName": last, "email": email, "userId": 1, "teams": []}


class TestSearchOwners:
    @pytest.mark.asyncio
    async def test_email_lookup(self, mock_context):
        mock_context.fetch.return_value = owners_page(owner("7", "Ana", "Lee", "ana@example.com"))

        result = await hubspot.execute_action("search_owners", {"email": "ana@example.com"}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == OWNERS_URL
        assert call.kwargs["params"] == {"limit": 100, "email": "ana@example.com"}
        assert result.result.data["owners"][0]["id"] == "7"
        assert result.result.data["complete"] is True

    @pytest.mark.asyncio
    async def test_name_matches_part_of_full_name_across_pages(self, mock_context):
        mock_context.fetch.side_effect = [
            owners_page(owner("1", "John", "Smith"), owner("2", None, None, "api@example.com"), after="a"),
            owners_page(owner("3", "Johnny", None), owner("4", "Ana", "Johnson")),
        ]

        result = await hubspot.execute_action("search_owners", {"name": "john"}, mock_context)

        assert [o["id"] for o in result.result.data["owners"]] == ["1", "3", "4"]
        assert mock_context.fetch.call_args.kwargs["params"] == {"limit": 100, "after": "a"}

    @pytest.mark.asyncio
    async def test_no_filter_lists_every_owner(self, mock_context):
        mock_context.fetch.return_value = owners_page(owner("1", "A", "B"), owner("2", "C", "D"))

        result = await hubspot.execute_action("search_owners", {}, mock_context)

        assert result.result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_page_cap_reported_as_incomplete(self, mock_context):
        mock_context.fetch.return_value = owners_page(owner("1", "A", "B"), after="more")

        result = await hubspot.execute_action("search_owners", {"name": "a"}, mock_context)

        assert mock_context.fetch.call_count == 20
        assert result.result.data["complete"] is False

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Missing scopes")

        result = await hubspot.execute_action("search_owners", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to list owners: HTTP 403: Missing scopes"


# ---- Account details ----


class TestGetAccountDetails:
    @pytest.mark.asyncio
    async def test_returns_account(self, mock_context):
        mock_context.fetch.return_value = account()

        result = await hubspot.execute_action("get_account_details", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == ACCOUNT_URL
        assert result.result.data["account"]["timeZone"] == "Pacific/Auckland"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Expired token")

        result = await hubspot.execute_action("get_account_details", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to read account details: HTTP 401: Expired token"

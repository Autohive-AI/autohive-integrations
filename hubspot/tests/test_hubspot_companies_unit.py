import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- Get Company Notes ----


class TestGetCompanyNotes:
    @pytest.mark.asyncio
    async def test_happy_path_with_timestamp_conversion(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "note-1",
                        "properties": {
                            "hs_note_body": "First note",
                            "hs_timestamp": "2025-03-15T10:30:00.000Z",
                            "hs_createdate": "2025-03-15T10:30:00.000Z",
                            "hs_lastmodifieddate": "2025-03-16T08:00:00.000Z",
                        },
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_company_notes", {"company_id": "123"}, mock_context)

        data = result.result.data
        assert data["company_id"] == "123"
        assert data["total"] == 1
        assert len(data["notes"]) == 1
        # Timestamps should be converted to UTC strings
        props = data["notes"][0]["properties"]
        assert "UTC" in props["hs_timestamp"]
        assert "UTC" in props["hs_createdate"]
        assert "UTC" in props["hs_lastmodifieddate"]

    @pytest.mark.asyncio
    async def test_empty_notes(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": []},
        )

        result = await hubspot.execute_action("get_company_notes", {"company_id": "999"}, mock_context)

        data = result.result.data
        assert data["company_id"] == "999"
        assert data["total"] == 0
        assert data["notes"] == []

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_company_notes", {"company_id": "42"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/objects/notes/search"
        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        payload = call_kwargs["json"]
        filters = payload["filterGroups"][0]["filters"]
        assert filters[0]["propertyName"] == "associations.company"
        assert filters[0]["value"] == "42"

    @pytest.mark.asyncio
    async def test_limit_respected_at_boundary(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_company_notes", {"company_id": "1", "limit": 200}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 200

    @pytest.mark.asyncio
    async def test_default_limit_is_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_company_notes", {"company_id": "1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 100

    @pytest.mark.asyncio
    async def test_custom_properties_in_request(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        custom_props = ["hs_note_body", "custom_field"]
        await hubspot.execute_action(
            "get_company_notes",
            {"company_id": "1", "properties": custom_props},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"] == custom_props

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await hubspot.execute_action("get_company_notes", {"company_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve notes for company 123" in result.result.message


# ---- Get Company ----


class TestGetCompany:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "456",
                "properties": {
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "industry": "Technology",
                },
            },
        )

        result = await hubspot.execute_action("get_company", {"company_id": "456"}, mock_context)

        data = result.result.data
        assert data["company"]["id"] == "456"
        assert data["company"]["properties"]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_custom_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "456",
                "properties": {"name": "Acme Corp", "custom_field": "value"},
            },
        )

        result = await hubspot.execute_action(
            "get_company",
            {"company_id": "456", "properties": ["name", "custom_field"]},
            mock_context,
        )

        call_url = mock_context.fetch.call_args.args[0]
        assert "properties=name,custom_field" in call_url
        assert result.result.data["company"]["properties"]["custom_field"] == "value"

    @pytest.mark.asyncio
    async def test_request_url_contains_company_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "77", "properties": {}})

        await hubspot.execute_action("get_company", {"company_id": "77"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "/crm/v3/objects/companies/77" in call_url

    @pytest.mark.asyncio
    async def test_default_properties_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action("get_company", {"company_id": "1"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "properties=name,domain,phone" in call_url
        assert "industry" in call_url

    @pytest.mark.asyncio
    async def test_response_data_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "5", "properties": {"name": "TestCo"}},
        )

        result = await hubspot.execute_action("get_company", {"company_id": "5"}, mock_context)

        data = result.result.data
        assert "company" in data
        assert data["company"]["id"] == "5"
        assert isinstance(data["company"], dict)


# ---- Create Company ----


class TestCreateCompany:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "789",
                "properties": {"name": "New Co", "domain": "newco.com"},
            },
        )

        result = await hubspot.execute_action(
            "create_company",
            {"properties": {"name": "New Co", "domain": "newco.com"}},
            mock_context,
        )

        data = result.result.data
        assert data["company"]["id"] == "789"
        assert data["company"]["properties"]["name"] == "New Co"

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["json"] == {"properties": {"name": "New Co", "domain": "newco.com"}}

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action("create_company", {"properties": {"name": "X"}}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/objects/companies"
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action(
            "create_company",
            {"properties": {"name": "Wrapped", "domain": "w.com"}},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in payload
        assert payload["properties"]["name"] == "Wrapped"
        assert payload["properties"]["domain"] == "w.com"

    @pytest.mark.asyncio
    async def test_response_contains_company(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "99", "properties": {"name": "Result Co"}},
        )

        result = await hubspot.execute_action("create_company", {"properties": {"name": "Result Co"}}, mock_context)

        assert "company" in result.result.data
        assert result.result.data["company"]["id"] == "99"


# ---- Update Company ----


class TestUpdateCompany:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "456",
                "properties": {"name": "Updated Corp", "industry": "Finance"},
            },
        )

        result = await hubspot.execute_action(
            "update_company",
            {
                "company_id": "456",
                "properties": {"name": "Updated Corp", "industry": "Finance"},
            },
            mock_context,
        )

        data = result.result.data
        assert data["company"]["id"] == "456"
        assert data["company"]["properties"]["name"] == "Updated Corp"

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["json"] == {"properties": {"name": "Updated Corp", "industry": "Finance"}}

    @pytest.mark.asyncio
    async def test_request_url_contains_company_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "88", "properties": {}})

        await hubspot.execute_action(
            "update_company",
            {"company_id": "88", "properties": {"name": "X"}},
            mock_context,
        )

        call_url = mock_context.fetch.call_args.args[0]
        assert "/crm/v3/objects/companies/88" in call_url

    @pytest.mark.asyncio
    async def test_request_method_is_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action(
            "update_company",
            {"company_id": "1", "properties": {"name": "Y"}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action(
            "update_company",
            {"company_id": "1", "properties": {"industry": "Tech", "city": "Auckland"}},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in payload
        assert payload["properties"]["industry"] == "Tech"
        assert payload["properties"]["city"] == "Auckland"


# ---- Search Companies ----


class TestSearchCompanies:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "1", "properties": {"name": "Acme"}},
                    {"id": "2", "properties": {"name": "Acme Labs"}},
                ],
                "total": 2,
            },
        )

        result = await hubspot.execute_action(
            "search_companies",
            {"query": "Acme", "limit": 10},
            mock_context,
        )

        data = result.result.data
        assert len(data["results"]) == 2
        assert data["results"][0]["properties"]["name"] == "Acme"

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["json"]["query"] == "Acme"
        assert call_kwargs["json"]["limit"] == 10

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "total": 0})

        await hubspot.execute_action("search_companies", {"query": "test", "limit": 25}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "test"
        assert payload["limit"] == 25

    @pytest.mark.asyncio
    async def test_default_limit_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [], "total": 0})

        await hubspot.execute_action("search_companies", {"query": "x"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 100

    @pytest.mark.asyncio
    async def test_response_data_passthrough(self, mock_context):
        raw = {"results": [{"id": "1"}], "total": 1, "paging": {"next": {"after": "1"}}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=raw)

        result = await hubspot.execute_action("search_companies", {"query": "q"}, mock_context)

        data = result.result.data
        assert data["results"] == [{"id": "1"}]
        assert data["total"] == 1
        assert data["paging"]["next"]["after"] == "1"


# ---- Search Companies by Owner Name ----


class TestSearchCompaniesByOwnerName:
    @pytest.mark.asyncio
    async def test_owner_found_returns_companies(self, mock_context):
        mock_context.fetch.side_effect = [
            # First call: owners list
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "owner-1",
                            "firstName": "Jane",
                            "lastName": "Doe",
                            "email": "jane@example.com",
                        },
                        {
                            "id": "owner-2",
                            "firstName": "John",
                            "lastName": "Smith",
                            "email": "john@example.com",
                        },
                    ]
                },
            ),
            # Second call: companies search
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "c1",
                            "properties": {
                                "name": "Company A",
                                "hubspot_owner_id": "owner-1",
                            },
                        },
                    ]
                },
            ),
        ]

        result = await hubspot.execute_action(
            "search_companies_by_owner_name",
            {"owner_name": "Jane Doe"},
            mock_context,
        )

        data = result.result.data
        assert data["success"] is True
        assert data["owner"]["id"] == "owner-1"
        assert data["owner"]["firstName"] == "Jane"
        assert data["total"] == 1
        assert data["companies"][0]["properties"]["name"] == "Company A"

    @pytest.mark.asyncio
    async def test_owner_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "owner-1",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "email": "jane@example.com",
                    }
                ]
            },
        )

        result = await hubspot.execute_action(
            "search_companies_by_owner_name",
            {"owner_name": "Unknown Person"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await hubspot.execute_action(
            "search_companies_by_owner_name",
            {"owner_name": "Jane Doe"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to search companies by owner name" in result.result.message

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "o1",
                            "firstName": "Jane",
                            "lastName": "Doe",
                            "email": "j@e.com",
                        },
                    ]
                },
            ),
            FetchResponse(status=200, headers={}, data={"results": []}),
        ]

        result = await hubspot.execute_action(
            "search_companies_by_owner_name", {"owner_name": "jAnE dOe"}, mock_context
        )

        assert result.result.data["success"] is True
        assert result.result.data["owner"]["id"] == "o1"

    @pytest.mark.asyncio
    async def test_first_name_only_match(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "o2",
                            "firstName": "Alice",
                            "lastName": "Smith",
                            "email": "a@e.com",
                        },
                    ]
                },
            ),
            FetchResponse(status=200, headers={}, data={"results": []}),
        ]

        result = await hubspot.execute_action("search_companies_by_owner_name", {"owner_name": "Alice"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["owner"]["firstName"] == "Alice"

    @pytest.mark.asyncio
    async def test_owner_found_request_includes_properties(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "o1",
                            "firstName": "Jane",
                            "lastName": "Doe",
                            "email": "j@e.com",
                        },
                    ]
                },
            ),
            FetchResponse(status=200, headers={}, data={"results": []}),
        ]

        await hubspot.execute_action(
            "search_companies_by_owner_name",
            {"owner_name": "Jane Doe", "properties": ["name", "domain"]},
            mock_context,
        )

        # Second call is the companies search
        search_call = mock_context.fetch.call_args_list[1]
        payload = search_call.kwargs["json"]
        assert payload["properties"] == ["name", "domain"]

    @pytest.mark.asyncio
    async def test_response_includes_paging(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [
                        {
                            "id": "o1",
                            "firstName": "Jane",
                            "lastName": "Doe",
                            "email": "j@e.com",
                        },
                    ]
                },
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "results": [{"id": "c1", "properties": {"name": "Co"}}],
                    "paging": {"next": {"after": "100"}},
                },
            ),
        ]

        result = await hubspot.execute_action(
            "search_companies_by_owner_name", {"owner_name": "Jane Doe"}, mock_context
        )

        assert result.result.data["paging"] == {"next": {"after": "100"}}


# ---- Get Company Properties ----


SAMPLE_PROPERTIES_RESPONSE = {
    "results": [
        {
            "name": "name",
            "label": "Company Name",
            "type": "string",
            "fieldType": "text",
            "groupName": "companyinformation",
            "hubspotDefined": True,
            "description": "The name of the company",
            "options": [],
        },
        {
            "name": "custom_score",
            "label": "Custom Score",
            "type": "number",
            "fieldType": "number",
            "groupName": "custom_group",
            "hubspotDefined": False,
            "description": "A custom scoring field",
            "options": [],
        },
    ]
}

SAMPLE_PROPERTIES_WITH_ENUM = {
    "results": [
        {
            "name": "industry",
            "label": "Industry",
            "type": "enumeration",
            "fieldType": "select",
            "groupName": "companyinformation",
            "hubspotDefined": True,
            "description": "The industry the company belongs to",
            "options": [
                {"label": "Technology", "value": "TECHNOLOGY"},
                {"label": "Finance", "value": "FINANCE"},
            ],
        },
    ]
}


class TestGetCompanyProperties:
    @pytest.mark.asyncio
    async def test_include_details_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_company_properties",
            {"include_details": True},
            mock_context,
        )

        data = result.result.data
        assert data["total_properties"] == 2
        assert data["custom_properties_count"] == 1
        assert data["properties"][0]["name"] == "name"
        assert data["properties"][0]["label"] == "Company Name"
        assert data["properties"][1]["hubspotDefined"] is False

    @pytest.mark.asyncio
    async def test_include_details_false(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_company_properties",
            {"include_details": False},
            mock_context,
        )

        data = result.result.data
        assert data["total_properties"] == 2
        assert data["custom_properties_count"] == 1
        assert data["properties"] == ["name", "custom_score"]

    @pytest.mark.asyncio
    async def test_custom_properties_count(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_company_properties",
            {"include_details": True},
            mock_context,
        )

        assert result.result.data["custom_properties_count"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        await hubspot.execute_action("get_company_properties", {"include_details": True}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/properties/companies"

    @pytest.mark.asyncio
    async def test_description_included_in_details(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action("get_company_properties", {"include_details": True}, mock_context)

        for prop in result.result.data["properties"]:
            assert "description" in prop

    @pytest.mark.asyncio
    async def test_options_included_for_enumeration(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_WITH_ENUM)

        result = await hubspot.execute_action("get_company_properties", {"include_details": True}, mock_context)

        prop = result.result.data["properties"][0]
        assert prop["type"] == "enumeration"
        assert len(prop["options"]) == 2
        assert prop["options"][0]["value"] == "TECHNOLOGY"


# ---- Get Deal Properties ----


class TestGetDealProperties:
    @pytest.mark.asyncio
    async def test_include_details_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_deal_properties",
            {"include_details": True},
            mock_context,
        )

        data = result.result.data
        assert data["total_properties"] == 2
        assert data["properties"][0]["label"] == "Company Name"

    @pytest.mark.asyncio
    async def test_include_details_false(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_deal_properties",
            {"include_details": False},
            mock_context,
        )

        data = result.result.data
        assert data["properties"] == ["name", "custom_score"]
        assert data["custom_properties_count"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        await hubspot.execute_action("get_deal_properties", {"include_details": True}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/properties/deals"

    @pytest.mark.asyncio
    async def test_description_included_in_details(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action("get_deal_properties", {"include_details": True}, mock_context)

        for prop in result.result.data["properties"]:
            assert "description" in prop

    @pytest.mark.asyncio
    async def test_options_included_for_enumeration(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_WITH_ENUM)

        result = await hubspot.execute_action("get_deal_properties", {"include_details": True}, mock_context)

        prop = result.result.data["properties"][0]
        assert prop["type"] == "enumeration"
        assert len(prop["options"]) == 2


# ---- Get Contact Properties ----


class TestGetContactProperties:
    @pytest.mark.asyncio
    async def test_include_details_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_contact_properties",
            {"include_details": True},
            mock_context,
        )

        data = result.result.data
        assert data["total_properties"] == 2
        assert data["properties"][1]["name"] == "custom_score"

    @pytest.mark.asyncio
    async def test_include_details_false(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action(
            "get_contact_properties",
            {"include_details": False},
            mock_context,
        )

        data = result.result.data
        assert data["properties"] == ["name", "custom_score"]
        assert data["custom_properties_count"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        await hubspot.execute_action("get_contact_properties", {"include_details": True}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/properties/contacts"

    @pytest.mark.asyncio
    async def test_description_included_in_details(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_RESPONSE)

        result = await hubspot.execute_action("get_contact_properties", {"include_details": True}, mock_context)

        for prop in result.result.data["properties"]:
            assert "description" in prop

    @pytest.mark.asyncio
    async def test_options_included_for_enumeration(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROPERTIES_WITH_ENUM)

        result = await hubspot.execute_action("get_contact_properties", {"include_details": True}, mock_context)

        prop = result.result.data["properties"][0]
        assert prop["type"] == "enumeration"
        assert len(prop["options"]) == 2

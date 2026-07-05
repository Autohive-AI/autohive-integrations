import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType
from pipedrive.pipedrive import pipedrive

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# ---- Deals ----


class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "title": "Big Deal"}})

        result = await pipedrive.execute_action("create_deal", {"title": "Big Deal"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deal"]["id"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("create_deal", {"title": "Big Deal"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "title": "Big Deal"}})

        result = await pipedrive.execute_action("get_deal", {"deal_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deal"]["title"] == "Big Deal"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("get_deal", {"deal_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateDeal:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "title": "Updated"}})

        result = await pipedrive.execute_action("update_deal", {"deal_id": 1, "title": "Updated"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deal"]["title"] == "Updated"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("update_deal", {"deal_id": 1, "title": "Updated"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListDeals:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1}, {"id": 2}]})

        result = await pipedrive.execute_action("list_deals", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["deals"]) == 2

    @pytest.mark.asyncio
    async def test_no_data_defaults_empty(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await pipedrive.execute_action("list_deals", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deals"] == []

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_deals", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteDeal:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1}})

        result = await pipedrive.execute_action("delete_deal", {"deal_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("delete_deal", {"deal_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Persons ----


class TestCreatePerson:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Jane Doe"}})

        result = await pipedrive.execute_action("create_person", {"name": "Jane Doe"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["person"]["name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("create_person", {"name": "Jane Doe"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetPerson:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Jane Doe"}})

        result = await pipedrive.execute_action("get_person", {"person_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["person"]["id"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("get_person", {"person_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdatePerson:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Updated"}})

        result = await pipedrive.execute_action("update_person", {"person_id": 1, "name": "Updated"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["person"]["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("update_person", {"person_id": 1, "name": "Updated"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListPersons:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1}]})

        result = await pipedrive.execute_action("list_persons", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["persons"] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_persons", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeletePerson:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1}})

        result = await pipedrive.execute_action("delete_person", {"person_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("delete_person", {"person_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Organizations ----


class TestCreateOrganization:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Acme"}})

        result = await pipedrive.execute_action("create_organization", {"name": "Acme"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["organization"]["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("create_organization", {"name": "Acme"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetOrganization:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Acme"}})

        result = await pipedrive.execute_action("get_organization", {"org_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["organization"]["id"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("get_organization", {"org_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateOrganization:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Updated"}})

        result = await pipedrive.execute_action("update_organization", {"org_id": 1, "name": "Updated"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["organization"]["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("update_organization", {"org_id": 1, "name": "Updated"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListOrganizations:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1}]})

        result = await pipedrive.execute_action("list_organizations", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["organizations"] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_organizations", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteOrganization:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1}})

        result = await pipedrive.execute_action("delete_organization", {"org_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("delete_organization", {"org_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Activities ----


class TestCreateActivity:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "subject": "Call"}})

        result = await pipedrive.execute_action("create_activity", {"subject": "Call", "type": "call"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["activity"]["subject"] == "Call"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("create_activity", {"subject": "Call", "type": "call"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetActivity:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "subject": "Call"}})

        result = await pipedrive.execute_action("get_activity", {"activity_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["activity"]["id"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("get_activity", {"activity_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateActivity:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "done": 1}})

        result = await pipedrive.execute_action("update_activity", {"activity_id": 1, "done": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["activity"]["done"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("update_activity", {"activity_id": 1, "done": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListActivities:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1}]})

        result = await pipedrive.execute_action("list_activities", {"done": True}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["activities"] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_done_false_sends_zero(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        await pipedrive.execute_action("list_activities", {"done": False}, mock_context)

        _, kwargs = mock_context.fetch.call_args
        assert kwargs["params"]["done"] == 0

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_activities", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteActivity:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1}})

        result = await pipedrive.execute_action("delete_activity", {"activity_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("delete_activity", {"activity_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Notes ----


class TestCreateNote:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "content": "Hello"}})

        result = await pipedrive.execute_action("create_note", {"content": "Hello"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["note"]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("create_note", {"content": "Hello"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListNotes:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1}]})

        result = await pipedrive.execute_action("list_notes", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["notes"] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_notes", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Pipelines ----


class TestListPipelines:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1, "name": "Sales"}]})

        result = await pipedrive.execute_action("list_pipelines", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["pipelines"] == [{"id": 1, "name": "Sales"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_pipelines", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetPipeline:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": 1, "name": "Sales"}})

        result = await pipedrive.execute_action("get_pipeline", {"pipeline_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["pipeline"]["name"] == "Sales"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("get_pipeline", {"pipeline_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Stages ----


class TestListStages:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": 1, "name": "Lead In"}]})

        result = await pipedrive.execute_action("list_stages", {"pipeline_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["stages"] == [{"id": 1, "name": "Lead In"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("list_stages", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Search ----


class TestSearch:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"items": [{"item": {"id": 1}}]}})

        result = await pipedrive.execute_action("search", {"term": "acme"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["items"] == [{"item": {"id": 1}}]

    @pytest.mark.asyncio
    async def test_exact_match_stringified(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"items": []}})

        await pipedrive.execute_action("search", {"term": "acme", "exact_match": True}, mock_context)

        _, kwargs = mock_context.fetch.call_args
        assert kwargs["params"]["exact_match"] == "true"

    @pytest.mark.asyncio
    async def test_no_data_defaults_empty(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await pipedrive.execute_action("search", {"term": "acme"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["items"] == []

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await pipedrive.execute_action("search", {"term": "acme"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

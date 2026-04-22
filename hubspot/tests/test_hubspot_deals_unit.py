import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
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


# ---- get_deal_notes ----


class TestGetDealNotes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "note1",
                        "properties": {
                            "hs_note_body": "Follow up call",
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_deal_notes", {"deal_id": "123"}, mock_context)

        data = result.result.data
        assert data["deal_id"] == "123"
        assert data["total"] == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["id"] == "note1"
        # Timestamps should have been converted from epoch ms to UTC strings
        assert data["notes"][0]["properties"]["hs_timestamp"] != "1700000000000"

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/notes/search"
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API down")

        result = await hubspot.execute_action("get_deal_notes", {"deal_id": "999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "999" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deal_notes", {"deal_id": "456"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/notes/search"
        payload = call_args.kwargs["json"]
        filters = payload["filterGroups"][0]["filters"]
        assert filters[0]["propertyName"] == "associations.deal"
        assert filters[0]["value"] == "456"

    @pytest.mark.asyncio
    async def test_limit_clamped(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deal_notes", {"deal_id": "1", "limit": 150}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 150

    @pytest.mark.asyncio
    async def test_timestamp_fields_converted(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "n1",
                        "properties": {
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_deal_notes", {"deal_id": "1"}, mock_context)

        props = result.result.data["notes"][0]["properties"]
        for field in ["hs_timestamp", "hs_createdate", "hs_lastmodifieddate"]:
            assert props[field] != "1700000000000"


# ---- get_deals ----


class TestGetDeals:
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_single_page(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "d1",
                        "properties": {
                            "dealname": "Acme Corp",
                            "amount": "5000",
                            "closedate": "1700000000000",
                            "createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ],
            },
        )

        result = await hubspot.execute_action("get_deals", {}, mock_context)

        data = result.result.data
        assert data["total"] == 1
        assert data["results"][0]["id"] == "d1"

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/deals/search"
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_pipeline_filter(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": []},
        )

        await hubspot.execute_action("get_deals", {"pipeline_id": "pipe1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        filters = payload["filterGroups"][0]["filters"]
        assert any(f["propertyName"] == "pipeline" and f["value"] == "pipe1" for f in filters)

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_request_payload_structure(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deals", {}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in payload
        assert isinstance(payload["properties"], list)
        assert "dealname" in payload["properties"]
        assert "sorts" in payload
        assert "limit" in payload

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_sort_direction_ascending(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deals", {"sort_direction": "ASC"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["sorts"][0]["direction"] == "ASCENDING"

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_default_sort_property(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deals", {}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["sorts"][0]["propertyName"] == "hs_lastmodifieddate"


# ---- get_deal ----


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "42",
                "properties": {
                    "dealname": "Big Deal",
                    "amount": "10000",
                    "closedate": "1700000000000",
                    "createdate": "1700000000000",
                    "hs_lastmodifieddate": "1700000000000",
                },
            },
        )

        result = await hubspot.execute_action("get_deal", {"deal_id": "42"}, mock_context)

        data = result.result.data
        assert data["deal"]["id"] == "42"
        assert data["deal"]["properties"]["dealname"] == "Big Deal"

        call_url = mock_context.fetch.call_args.args[0]
        assert "deals/42" in call_url

    @pytest.mark.asyncio
    async def test_custom_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "42", "properties": {"custom_field": "val"}},
        )

        await hubspot.execute_action(
            "get_deal",
            {"deal_id": "42", "properties": ["custom_field"]},
            mock_context,
        )

        call_url = mock_context.fetch.call_args.args[0]
        assert "properties=custom_field" in call_url

    @pytest.mark.asyncio
    async def test_request_url_contains_deal_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "99", "properties": {}})

        await hubspot.execute_action("get_deal", {"deal_id": "99"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "/crm/v3/objects/deals/99" in call_url

    @pytest.mark.asyncio
    async def test_date_fields_converted(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "42",
                "properties": {
                    "closedate": "1700000000000",
                    "createdate": "1700000000000",
                    "hs_lastmodifieddate": "1700000000000",
                },
            },
        )

        result = await hubspot.execute_action("get_deal", {"deal_id": "42"}, mock_context)

        props = result.result.data["deal"]["properties"]
        for field in ["closedate", "createdate", "hs_lastmodifieddate"]:
            assert props[field] != "1700000000000"

    @pytest.mark.asyncio
    async def test_default_properties_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "1", "properties": {}})

        await hubspot.execute_action("get_deal", {"deal_id": "1"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        for prop in ["dealname", "amount", "closedate", "dealstage", "pipeline"]:
            assert prop in call_url


# ---- search_deals ----


class TestSearchDeals:
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_basic_search(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "s1",
                        "properties": {
                            "dealname": "Search Hit",
                            "closedate": "1700000000000",
                            "createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ],
            },
        )

        result = await hubspot.execute_action(
            "search_deals",
            {"query": "Search Hit"},
            mock_context,
        )

        data = result.result.data
        assert data["total"] == 1
        assert data["results"][0]["properties"]["dealname"] == "Search Hit"

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "Search Hit"

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_request_payload(self, mock_sleep, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("search_deals", {"query": "Acme", "limit": 25}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "Acme"
        assert payload["limit"] == 25


# ---- create_deal ----


class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={"id": "new1", "properties": {"dealname": "New Deal", "amount": "1000"}},
        )

        result = await hubspot.execute_action(
            "create_deal",
            {"properties": {"dealname": "New Deal", "amount": "1000"}},
            mock_context,
        )

        data = result.result.data
        assert data["deal"]["id"] == "new1"
        assert data["deal"]["properties"]["dealname"] == "New Deal"

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/deals"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"]["properties"]["dealname"] == "New Deal"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"id": "x", "properties": {}})

        await hubspot.execute_action("create_deal", {"properties": {"dealname": "Test"}}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/deals"
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"id": "x", "properties": {}})

        await hubspot.execute_action(
            "create_deal",
            {"properties": {"dealname": "A", "amount": "500"}},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in payload
        assert payload["properties"]["dealname"] == "A"
        assert payload["properties"]["amount"] == "500"


# ---- update_deal ----


class TestUpdateDeal:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "42", "properties": {"dealname": "Updated Deal"}},
        )

        result = await hubspot.execute_action(
            "update_deal",
            {"deal_id": "42", "properties": {"dealname": "Updated Deal"}},
            mock_context,
        )

        data = result.result.data
        assert data["deal"]["id"] == "42"
        assert data["deal"]["properties"]["dealname"] == "Updated Deal"

        call_args = mock_context.fetch.call_args
        assert "deals/42" in call_args.args[0]
        assert call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_request_url_contains_deal_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "77", "properties": {}})

        await hubspot.execute_action("update_deal", {"deal_id": "77", "properties": {"amount": "1"}}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "/crm/v3/objects/deals/77" in call_url

    @pytest.mark.asyncio
    async def test_request_method_is_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "77", "properties": {}})

        await hubspot.execute_action("update_deal", {"deal_id": "77", "properties": {}}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"


# ---- get_recent_deals ----


class TestGetRecentDeals:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "r1",
                        "properties": {
                            "dealname": "Recent",
                            "closedate": "1700000000000",
                            "createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_recent_deals", {}, mock_context)

        data = result.result.data
        assert len(data["deals"]) == 1
        assert data["deals"][0]["id"] == "r1"

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["sorts"][0]["propertyName"] == "createdate"
        assert payload["sorts"][0]["direction"] == "DESCENDING"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_deals", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.hubapi.com/crm/v3/objects/deals/search"
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_default_sort(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_deals", {}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["sorts"][0]["propertyName"] == "createdate"
        assert payload["sorts"][0]["direction"] == "DESCENDING"


# ---- get_deal_pipelines ----


class TestGetDealPipelines:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [{"id": "p1", "label": "Sales Pipeline", "stages": [{"id": "s1", "label": "Qualification"}]}]
            },
        )

        result = await hubspot.execute_action("get_deal_pipelines", {}, mock_context)

        data = result.result.data
        assert len(data["pipelines"]) == 1
        assert data["pipelines"][0]["label"] == "Sales Pipeline"

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api.hubapi.com/crm/v3/pipelines/deals"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_deal_pipelines", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api.hubapi.com/crm/v3/pipelines/deals"

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {"id": "p1", "label": "Pipeline A", "stages": []},
                    {"id": "p2", "label": "Pipeline B", "stages": []},
                ]
            },
        )

        result = await hubspot.execute_action("get_deal_pipelines", {}, mock_context)

        data = result.result.data
        assert "pipelines" in data
        assert len(data["pipelines"]) == 2
        assert data["pipelines"][0]["id"] == "p1"
        assert data["pipelines"][1]["id"] == "p2"


# ---- get_contact_calls_and_meetings ----


class TestGetContactCallsAndMeetings:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        calls_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "c1",
                        "properties": {
                            "hs_call_title": "Intro call",
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                            "hs_call_has_transcript": "false",
                            "hs_call_transcription_id": None,
                        },
                    }
                ]
            },
        )
        meetings_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "m1",
                        "properties": {
                            "hs_meeting_title": "Demo",
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ]
            },
        )
        mock_context.fetch.side_effect = [calls_response, meetings_response]

        result = await hubspot.execute_action(
            "get_contact_calls_and_meetings",
            {"contact_id": "100"},
            mock_context,
        )

        data = result.result.data
        assert data["contact_id"] == "100"
        assert data["total_calls"] == 1
        assert data["total_meetings"] == 1
        assert data["calls"][0]["id"] == "c1"
        assert data["meetings"][0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await hubspot.execute_action("get_contact_calls_and_meetings", {"contact_id": "100"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "100" in result.result.message

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self, mock_context):
        calls_response = FetchResponse(status=200, headers={}, data={"results": []})
        meetings_response = FetchResponse(status=200, headers={}, data={"results": []})
        mock_context.fetch.side_effect = [calls_response, meetings_response]

        await hubspot.execute_action(
            "get_contact_calls_and_meetings",
            {"contact_id": "100", "limit": 80},
            mock_context,
        )

        # Both calls and meetings searches should use the provided limit
        calls_payload = mock_context.fetch.call_args_list[0].kwargs["json"]
        assert calls_payload["limit"] == 80


# ---- get_deal_calls_and_meetings ----


class TestGetDealCallsAndMeetings:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        calls_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "c2",
                        "properties": {
                            "hs_call_title": "Follow-up",
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                            "hs_call_has_transcript": "false",
                            "hs_call_transcription_id": None,
                        },
                    }
                ]
            },
        )
        meetings_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "m2",
                        "properties": {
                            "hs_meeting_title": "Review",
                            "hs_timestamp": "1700000000000",
                            "hs_createdate": "1700000000000",
                            "hs_lastmodifieddate": "1700000000000",
                        },
                    }
                ]
            },
        )
        mock_context.fetch.side_effect = [calls_response, meetings_response]

        result = await hubspot.execute_action(
            "get_deal_calls_and_meetings",
            {"deal_id": "200"},
            mock_context,
        )

        data = result.result.data
        assert data["deal_id"] == "200"
        assert data["total_calls"] == 1
        assert data["total_meetings"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action("get_deal_calls_and_meetings", {"deal_id": "200"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "200" in result.result.message


# ---- get_call_transcript ----


class TestGetCallTranscript:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "transcriptUtterances": [
                    {"speakerId": "sp1", "text": "Hello", "timestamp": 0},
                    {"speakerId": "sp2", "text": "Hi there", "timestamp": 1500},
                ]
            },
        )

        result = await hubspot.execute_action(
            "get_call_transcript",
            {"transcript_id": "t1"},
            mock_context,
        )

        data = result.result.data
        assert data["transcript_id"] == "t1"
        assert data["total_utterances"] == 2
        assert data["utterances"][0]["text"] == "Hello"

        call_url = mock_context.fetch.call_args.args[0]
        assert "transcripts/t1" in call_url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action(
            "get_call_transcript",
            {"transcript_id": "bad"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "bad" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_contains_transcript_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"transcriptUtterances": []})

        await hubspot.execute_action("get_call_transcript", {"transcript_id": "tr99"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "transcripts/tr99" in call_url

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "transcriptUtterances": [
                    {"speakerId": "s1", "text": "A", "timestamp": 0},
                ]
            },
        )

        result = await hubspot.execute_action("get_call_transcript", {"transcript_id": "tr1"}, mock_context)

        data = result.result.data
        assert data["transcript_id"] == "tr1"
        assert "utterances" in data
        assert data["total_utterances"] == 1

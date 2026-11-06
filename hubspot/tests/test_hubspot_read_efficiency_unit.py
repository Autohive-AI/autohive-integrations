"""Keep legacy read actions bounded and avoid fetching unrequested detail."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType
from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


@pytest.fixture
def ctx():
    context = MagicMock()
    context.fetch = AsyncMock()
    context.metadata = {}
    context.config = {"max_retries": 3}
    return context


async def test_filtered_tasks_only_fetch_requested_task_properties(ctx):
    ctx.fetch.return_value = ok({"results": [{"id": "1", "properties": {"hs_task_subject": "Call"}}], "total": 400})
    result = await hubspot.execute_action(
        "list_tasks", {"owner_id": "7", "limit": 1, "hs_task_properties": ["hs_task_subject"]}, ctx
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["total_matching"] == 400
    assert "associations" not in result.result.data["tasks"][0]
    assert ctx.fetch.call_count == 1
    assert ctx.fetch.call_args.kwargs["json"]["properties"] == ["hs_task_subject"]


@pytest.mark.parametrize("include", [False, True])
async def test_unfiltered_tasks_only_request_associations_when_enabled(ctx, include):
    ctx.fetch.return_value = ok({"results": []})
    result = await hubspot.execute_action("list_tasks", {"include_associations": include}, ctx)
    assert result.type == ResultType.ACTION
    assert ("associations" in ctx.fetch.call_args.kwargs["params"]) == include
    assert ctx.fetch.call_count == 1


@pytest.mark.parametrize("object_type", ["contact", "deal"])
async def test_call_history_does_not_download_transcripts_by_default(ctx, object_type):
    ctx.fetch.side_effect = [
        ok(
            {
                "results": [
                    {"id": "8", "properties": {"hs_call_has_transcript": "true", "hs_call_transcription_id": "9"}}
                ]
            }
        ),
        ok({"results": []}),
    ]
    result = await hubspot.execute_action(f"get_{object_type}_calls_and_meetings", {f"{object_type}_id": "1"}, ctx)
    assert result.type == ResultType.ACTION
    assert "transcript" not in result.result.data["calls"][0]
    assert ctx.fetch.call_count == 2
    assert all("/transcripts/" not in call.args[0] for call in ctx.fetch.call_args_list)


async def test_deal_history_can_still_include_transcripts(ctx):
    ctx.fetch.side_effect = [
        ok(
            {
                "results": [
                    {"id": "8", "properties": {"hs_call_has_transcript": "true", "hs_call_transcription_id": "9"}}
                ]
            }
        ),
        ok({"transcriptUtterances": [{"text": "Hello"}]}),
        ok({"results": []}),
    ]
    result = await hubspot.execute_action(
        "get_deal_calls_and_meetings", {"deal_id": "1", "include_transcripts": True}, ctx
    )
    assert result.result.data["calls"][0]["transcript"] == [{"text": "Hello"}]
    assert ctx.fetch.call_count == 3


async def test_deal_date_bounds_and_zero_amount_are_sent_to_hubspot(ctx):
    ctx.fetch.return_value = ok(
        {"results": [{"id": "1", "properties": {}}], "total": 300, "paging": {"next": {"after": "1"}}}
    )
    result = await hubspot.execute_action(
        "search_deals",
        {
            "close_date_start": "2026-10-01",
            "close_date_end": "2026-11-01",
            "max_amount": 0,
            "properties": ["dealname"],
            "limit": 1,
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 1
    payload = ctx.fetch.call_args.kwargs["json"]
    assert payload["filterGroups"] == [
        {
            "filters": [
                {"propertyName": "closedate", "operator": "GTE", "value": "1790812800000"},
                {"propertyName": "closedate", "operator": "LTE", "value": "1793491200000"},
                {"propertyName": "amount", "operator": "LTE", "value": "0"},
            ]
        }
    ]
    assert payload["properties"] == ["dealname"]
    assert result.result.data["total_matching"] == 300
    assert result.result.data["pagination"]["after"] == "1"


async def test_year_intersects_date_bounds_without_exceeding_filter_limits(ctx):
    ctx.fetch.return_value = ok({"results": []})
    await hubspot.execute_action(
        "search_deals",
        {
            "year": 2026,
            "close_date_start": "2026-10-01",
            "close_date_end": "2027-01-01",
            "pipeline_id": "0",
            "deal_stage": "closedwon",
            "min_amount": 0,
            "max_amount": 100,
        },
        ctx,
    )
    filters = ctx.fetch.call_args.kwargs["json"]["filterGroups"][0]["filters"]
    assert len(filters) == 6
    assert [f["value"] for f in filters if f["propertyName"] == "closedate"] == ["1790812800000", "1798761599000"]


@pytest.mark.parametrize(
    "dates",
    [
        {"close_date_start": "invalid"},
        {"close_date_start": "2026-11-01", "close_date_end": "2026-10-01"},
        {"year": 2026, "close_date_start": "2027-01-01"},
    ],
)
async def test_bad_date_ranges_fail_before_request(ctx, dates):
    result = await hubspot.execute_action("search_deals", dates, ctx)
    assert result.type == ResultType.ACTION_ERROR
    ctx.fetch.assert_not_called()


async def test_deal_search_does_not_autopage_without_fetch_all(ctx):
    ctx.fetch.return_value = ok({"results": [{"id": "1", "properties": {}}], "paging": {"next": {"after": "1"}}})
    result = await hubspot.execute_action("search_deals", {"limit": 2, "max_total": 10}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 1
    assert result.result.data["pagination"]["after"] == "1"


async def test_explicit_deal_export_still_pages_and_returns_remaining_cursor(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"id": "1", "properties": {}}], "paging": {"next": {"after": "1"}}}),
        ok({"results": [{"id": "2", "properties": {}}], "paging": {"next": {"after": "2"}}}),
    ]
    result = await hubspot.execute_action("search_deals", {"fetch_all": True, "limit": 1, "max_total": 2}, ctx)
    assert result.result.data["total"] == 2
    assert ctx.fetch.call_count == 2
    assert ctx.fetch.call_args_list[1].kwargs["json"]["after"] == "1"
    assert result.result.data["pagination"]["after"] == "2"


async def test_list_member_ids_skip_contact_reads_and_resume_from_cursor(ctx):
    ctx.fetch.side_effect = [
        ok({"list": {"listId": "5", "size": 1000}}),
        ok(
            {
                "results": [{"recordId": "8", "membershipTimestamp": "2026-10-29T00:00:00Z"}],
                "paging": {"next": {"after": "9"}},
            }
        ),
    ]
    result = await hubspot.execute_action(
        "get_list_members", {"list_id": "5", "limit": 1, "after": "7", "include_contact_details": False}, ctx
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 2
    assert ctx.fetch.call_args.kwargs["params"] == {"limit": 1, "after": "7"}
    data = result.result.data
    assert data["members"] == [{"contact_id": "8", "membership_timestamp": "2026-10-29T00:00:00Z"}]
    assert data["after"] == "9" and data["has_more"] is True
    assert data["performance_stats"]["total_api_calls"] == 2


async def test_list_member_default_is_small_and_exhausted_cursor_is_null(ctx):
    ctx.fetch.side_effect = [ok({"list": {"size": 0}}), ok({"results": []})]
    result = await hubspot.execute_action("get_list_members", {"list_id": "5"}, ctx)
    assert ctx.fetch.call_args.kwargs["params"]["limit"] == 50
    assert result.result.data["after"] is None
    assert result.result.data["has_more"] is False


async def test_owner_id_skips_directory_lookup_on_company_pages(ctx):
    ctx.fetch.return_value = ok({"results": [], "paging": {"next": {"after": "20"}}})
    result = await hubspot.execute_action("search_companies_by_owner_name", {"owner_id": "7", "after": "10"}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 1
    assert ctx.fetch.call_args.args[0].endswith("/companies/search")
    payload = ctx.fetch.call_args.kwargs["json"]
    assert payload["filterGroups"][0]["filters"][0]["value"] == "7"
    assert payload["after"] == "10"
    assert result.result.data["owner"]["id"] == "7"


async def test_owner_email_is_filtered_by_hubspot(ctx):
    ctx.fetch.side_effect = [ok({"results": [{"id": "7", "email": "rep@example.com"}]}), ok({"results": []})]
    result = await hubspot.execute_action("search_companies_by_owner_name", {"owner_email": "rep@example.com"}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 2
    assert ctx.fetch.call_args_list[0].kwargs["params"]["email"] == "rep@example.com"


@pytest.mark.parametrize("inputs", [{}, {"owner_name": "   "}])
async def test_company_owner_search_requires_an_identifier(ctx, inputs):
    result = await hubspot.execute_action("search_companies_by_owner_name", inputs, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Provide an owner_id, owner_email or owner_name"
    ctx.fetch.assert_not_called()


async def test_default_member_page_fetches_only_50_contacts_and_keeps_next_cursor(ctx):
    members = [{"recordId": str(i), "membershipTimestamp": "2026-10-29T00:00:00Z"} for i in range(50)]
    ctx.fetch.side_effect = [
        ok({"list": {"size": 1000}}),
        ok({"results": members, "paging": {"next": {"after": "50"}}}),
        ok(
            {
                "results": [
                    {"id": m["recordId"], "properties": {"email": f"{m['recordId']}@example.com"}} for m in members
                ]
            }
        ),
    ]
    result = await hubspot.execute_action("get_list_members", {"list_id": "5"}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 3
    assert ctx.fetch.call_args_list[1].kwargs["params"] == {"limit": 50}
    assert len(ctx.fetch.call_args.kwargs["json"]["inputs"]) == 50
    assert result.result.data["retrieved_count"] == 50
    assert result.result.data["total_members"] == 1000
    assert result.result.data["after"] == "50"


async def test_explicit_member_export_continues_memberships_and_keeps_final_cursor(ctx):
    ctx.fetch.side_effect = [
        ok({"list": {"size": 1000}}),
        ok(
            {
                "results": [{"recordId": str(i), "membershipTimestamp": "2026-10-29T00:00:00Z"} for i in range(250)],
                "paging": {"next": {"after": "250"}},
            }
        ),
        ok(
            {
                "results": [{"recordId": "250", "membershipTimestamp": "2026-10-29T00:00:00Z"}],
                "paging": {"next": {"after": "251"}},
            }
        ),
    ]
    result = await hubspot.execute_action(
        "get_list_members", {"list_id": "5", "limit": 251, "include_contact_details": False}, ctx
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_count == 3
    assert ctx.fetch.call_args_list[2].kwargs["params"] == {"limit": 1, "after": "250"}
    assert result.result.data["retrieved_count"] == 251
    assert result.result.data["after"] == "251"

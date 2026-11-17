"""Live contact actions; use a dedicated permitted contact with a known available work email."""

import pytest

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


async def test_search_contacts(live_context, contact_identifier, check_live_records):
    result = await lusha.execute_action("search_contacts", {"contacts": [contact_identifier]}, live_context)
    _, records = check_live_records(result)
    assert len(records) == 1
    assert isinstance(records[0].get("id"), str)


async def test_enrich_contacts(live_context, contact_identifier, check_live_records):
    search = await lusha.execute_action("search_contacts", {"contacts": [contact_identifier]}, live_context)
    _, previews = check_live_records(search)
    contact_id = previews[0]["id"]
    result = await lusha.execute_action(
        "enrich_contacts", {"ids": [contact_id], "reveal": ["emails"], "waterfallEnabled": False}, live_context
    )
    data, records = check_live_records(result)
    assert records[0]["id"] == contact_id
    assert isinstance(records[0].get("emails"), list)
    assert bool(records[0]["emails"]), "Use a test contact with a known available Lusha email"
    assert isinstance(data.get("billing"), dict)


async def test_search_and_enrich_contacts(live_context, contact_identifier, check_live_records):
    result = await lusha.execute_action(
        "search_and_enrich_contacts", {"contacts": [contact_identifier], "reveal": ["emails"]}, live_context
    )
    data, records = check_live_records(result)
    if any(record.get("statusReason") == "WATERFALL_NOT_IN_PLAN" for record in [data, *records]):
        assert bool(data.get("warnings")), "Expected integration guidance for a Waterfall plan restriction"
        pytest.skip("WATERFALL_NOT_IN_PLAN: full combined enrichment is blocked on this test account")
    assert isinstance(records[0].get("emails"), list)
    assert bool(records[0]["emails"]), "The combined endpoint did not return the fixture's known available email"
    assert isinstance(data.get("billing"), dict)

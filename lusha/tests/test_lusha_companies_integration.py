"""Live company lookup and enrichment actions. These tests consume Lusha credits."""

import pytest

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


async def test_search_companies(live_context, company_domain, check_live_records):
    result = await lusha.execute_action("search_companies", {"companies": [{"domain": company_domain}]}, live_context)
    _, records = check_live_records(result)
    assert len(records) == 1
    assert isinstance(records[0].get("id"), str)


async def test_enrich_companies(live_context, company_domain, check_live_records):
    search = await lusha.execute_action("search_companies", {"companies": [{"domain": company_domain}]}, live_context)
    _, previews = check_live_records(search)
    company_id = previews[0]["id"]
    result = await lusha.execute_action("enrich_companies", {"ids": [company_id]}, live_context)
    data, records = check_live_records(result)
    assert records[0]["id"] == company_id
    assert isinstance(records[0].get("name"), str)
    assert isinstance(data.get("billing"), dict)


async def test_search_and_enrich_companies(live_context, company_domain, check_live_records):
    result = await lusha.execute_action(
        "search_and_enrich_companies", {"companies": [{"domain": company_domain}]}, live_context
    )
    data, records = check_live_records(result)
    assert len(records) == 1
    assert isinstance(records[0].get("id"), str)
    assert isinstance(records[0].get("name"), str)
    assert isinstance(data.get("billing"), dict)

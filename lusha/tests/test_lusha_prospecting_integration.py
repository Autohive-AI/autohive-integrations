"""Live prospecting with bounded pages and an explicit company-domain criterion."""

import pytest
from autohive_integrations_sdk import ResultType

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("action", ["prospect_contacts", "prospect_companies"])
async def test_prospecting(live_context, company_domain, action):
    entity = "contacts" if action == "prospect_contacts" else "companies"
    filter_type = "seniority" if entity == "contacts" else "sizes"
    discovery = await lusha.execute_action("list_filter_types", {"entity": entity}, live_context)
    assert discovery.type == ResultType.ACTION
    assert any(item["filterType"] == filter_type for item in discovery.result.data["availableFilters"])
    lookup = await lusha.execute_action(
        "get_filter_values", {"entity": entity, "filter_type": filter_type}, live_context
    )
    assert lookup.type == ResultType.ACTION
    values = lookup.result.data["values"]
    assert isinstance(values, list) and bool(values)
    filters = {"companies": {"include": {"domains": [company_domain]}}}
    if entity == "contacts":
        assert all(isinstance(value.get("id"), int) for value in values)
        filters["contacts"] = {"include": {"seniorityIds": [value["id"] for value in values]}}
    else:
        assert all(isinstance(value, dict) and ("min" in value or "max" in value) for value in values)
        filters["companies"]["include"]["sizes"] = [
            {key: value[key] for key in ("min", "max") if key in value} for value in values
        ]
    result = await lusha.execute_action(
        action,
        {"filters": filters, "page": 0, "size": 10},
        live_context,
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data.get("results"), list)
    assert bool(data["results"]), "Use a public company domain with known prospecting results"
    assert len(data["results"]) <= 10
    assert data["pagination"]["page"] == 0
    # Lusha may report the actual returned page size (e.g. one matching company).
    assert isinstance(data["pagination"]["size"], int)
    assert len(data["results"]) <= data["pagination"]["size"] <= 10
    assert all(isinstance(record.get("id"), str) for record in data["results"])
    assert all(not record.get("error") for record in data["results"])
    assert isinstance(data.get("requestId"), str)
    assert isinstance(data["billing"]["creditsCharged"], (int, float))
    assert isinstance(data["billing"]["resultsReturned"], int)


async def test_prospect_contacts_exclude_dnc(live_context, company_domain):
    result = await lusha.execute_action(
        "prospect_contacts",
        {
            "filters": {"companies": {"include": {"domains": [company_domain]}}},
            "size": 10,
            "options": {"excludeDnc": True},
        },
        live_context,
    )
    if (
        result.type == ResultType.ACTION_ERROR
        and "Lusha denied contact prospecting with excludeDnc enabled" in result.result.message
    ):
        pytest.skip("The test account denies excludeDnc; baseline prospect_contacts is tested separately")
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data.get("results"), list)
    assert len(result.result.data["results"]) <= 10

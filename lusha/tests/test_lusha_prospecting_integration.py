"""Live prospecting with bounded pages and an explicit company-domain criterion."""

import pytest
from autohive_integrations_sdk import ResultType

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("action", ["prospect_contacts", "prospect_companies"])
async def test_prospecting(live_context, company_domain, action):
    result = await lusha.execute_action(
        action,
        {"filters": {"companies": {"include": {"domains": [company_domain]}}}, "page": 0, "size": 10},
        live_context,
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data.get("results"), list)
    assert bool(data["results"]), "Use a public company domain with known prospecting results"
    assert len(data["results"]) <= 10
    assert data["pagination"]["page"] == 0
    assert data["pagination"]["size"] == 10
    assert all(isinstance(record.get("id"), str) for record in data["results"])


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

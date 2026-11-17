"""Live filter catalog and value lookups for both entity types."""

import pytest
from autohive_integrations_sdk import ResultType

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("entity", ["contacts", "companies"])
async def test_list_filter_types(live_context, entity):
    result = await lusha.execute_action("list_filter_types", {"entity": entity}, live_context)
    assert result.type == ResultType.ACTION
    filters = result.result.data["availableFilters"]
    assert isinstance(filters, list)
    assert bool(filters)
    assert all(
        isinstance(item.get("filterType"), str) and isinstance(item.get("requiresQuery"), bool) for item in filters
    )


@pytest.mark.parametrize("entity,filter_type", [("contacts", "departments"), ("companies", "sizes")])
async def test_get_filter_values(live_context, entity, filter_type):
    result = await lusha.execute_action(
        "get_filter_values", {"entity": entity, "filter_type": filter_type}, live_context
    )
    assert result.type == ResultType.ACTION
    assert "values" in result.result.data
    assert isinstance(result.result.data["values"], (list, dict))
    assert bool(result.result.data["values"])

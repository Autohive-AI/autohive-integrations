"""
End-to-end integration tests for the LINZ integration.

These call the real LINZ Data Service WFS API and require a valid LINZ Data
Service API key in the LINZ_API_KEY environment variable (via .env or export).

    Create a key at https://data.linz.govt.nz/my/api/

Ownership data (layer-50805) additionally requires that the key's LINZ account
has accepted the LINZ Licence for Personal Data. Tests that touch ownership data
SKIP automatically when the key lacks that access (LINZ reports the layer as an
"unknown" feature type), so the suite is meaningful on both licensed and
public-only keys.

Run (all tests here are read-only — no destructive marker needed):
    pytest linz/tests/test_linz_integration.py -m "integration and not destructive"

Never runs in CI — the default marker filter (-m unit) and the
test_*_integration.py naming both exclude it.
"""

import json as _json
import os

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from linz.linz import linz

pytestmark = pytest.mark.integration

# Optional pre-existing resources to exercise single-record reads without
# chaining. Each test that needs one skips gracefully when it is unset.
TEST_TITLE_NO = os.environ.get("LINZ_TEST_TITLE_NO", "")
TEST_LAND_DISTRICT = os.environ.get("LINZ_TEST_LAND_DISTRICT", "Otago")

# Phrases that indicate the key cannot see the licensed ownership layer.
_NO_OWNERSHIP_ACCESS = ("personal data", "unknown")


@pytest.fixture
def live_context(env_credentials):
    """Custom-auth context whose fetch makes real WFS calls via aiohttp."""
    api_key = env_credentials("LINZ_API_KEY")
    if not api_key:
        pytest.skip("LINZ_API_KEY not set — skipping integration tests")

    import aiohttp
    from unittest.mock import AsyncMock, MagicMock

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                text = await resp.text()
                # LDS returns JSON on success and XML on error; mirror the SDK's
                # fetch by parsing JSON when possible and passing the raw string
                # through otherwise (the integration handles both).
                try:
                    data = _json.loads(text)
                except Exception:
                    data = text
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    # Custom auth: the SDK passes context.auth straight through to the handler,
    # which reads api_key from it. Flat shape matches config.auth.fields.
    ctx.auth = {"api_key": api_key}
    return ctx


def _skip_if_no_ownership_access(result):
    """Skip a test when the key lacks the Personal Data Licence for layer-50805."""
    if result.type == ResultType.ACTION_ERROR:
        msg = (result.result.message or "").lower()
        if any(p in msg for p in _NO_OWNERSHIP_ACCESS):
            pytest.skip(f"API key lacks ownership-layer access: {result.result.message}")


# ---------------------------------------------------------------------------
# Public layers — always available with any valid key
# ---------------------------------------------------------------------------


class TestSearchParcels:
    async def test_returns_parcels_with_expected_fields(self, live_context):
        result = await linz.execute_action(
            "search_parcels", {"land_district": TEST_LAND_DISTRICT, "limit": 2}, live_context
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert "parcels" in data
        assert len(data["parcels"]) <= 2
        if data["parcels"]:
            parcel = data["parcels"][0]
            assert "appellation" in parcel
            assert "parcel_intent" in parcel
            # Geometry is stripped by default.
            assert "geometry" not in parcel

    async def test_include_geometry(self, live_context):
        result = await linz.execute_action(
            "search_parcels",
            {"land_district": TEST_LAND_DISTRICT, "limit": 1, "include_geometry": True},
            live_context,
        )
        assert result.type == ResultType.ACTION
        parcels = result.result.data["parcels"]
        if parcels:
            assert "geometry" in parcels[0]


class TestQueryLayer:
    async def test_public_titles_layer(self, live_context):
        # layer-50804 (titles without owners) is public; query_layer takes raw CQL.
        result = await linz.execute_action(
            "query_layer",
            {"layer": "50804", "cql_filter": f"land_district='{TEST_LAND_DISTRICT}'", "limit": 1},
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert "records" in data
        assert len(data["records"]) <= 1
        if data["records"]:
            assert "title_no" in data["records"][0]

    async def test_limit_respected(self, live_context):
        result = await linz.execute_action("query_layer", {"layer": "50772", "limit": 3}, live_context)
        assert result.type == ResultType.ACTION
        assert len(result.result.data["records"]) <= 3

    async def test_unknown_layer_errors(self, live_context):
        result = await linz.execute_action("query_layer", {"layer": "99999999", "limit": 1}, live_context)
        assert result.type == ResultType.ACTION_ERROR


# ---------------------------------------------------------------------------
# Ownership layer (layer-50805) — skips when the key lacks the licence
# ---------------------------------------------------------------------------


class TestSearchPropertyTitles:
    async def test_search_by_land_district(self, live_context):
        result = await linz.execute_action(
            "search_property_titles", {"land_district": TEST_LAND_DISTRICT, "limit": 2}, live_context
        )
        _skip_if_no_ownership_access(result)
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert "titles" in data
        assert len(data["titles"]) <= 2
        if data["titles"]:
            assert "title_no" in data["titles"][0]
            assert "owners" in data["titles"][0]


class TestGetTitleOwners:
    async def test_get_known_title(self, live_context):
        if not TEST_TITLE_NO:
            pytest.skip("LINZ_TEST_TITLE_NO not set")
        result = await linz.execute_action("get_title_owners", {"title_no": TEST_TITLE_NO}, live_context)
        _skip_if_no_ownership_access(result)
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert isinstance(data["owners"], list)
        assert data["title_no"]


class TestFindMultiPropertyOwners:
    async def test_scan_by_land_district(self, live_context):
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"land_district": TEST_LAND_DISTRICT, "min_properties": 2, "max_titles_scanned": 200},
            live_context,
        )
        _skip_if_no_ownership_access(result)
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert "owners" in data
        assert isinstance(data["owners"], list)
        assert data["titles_scanned"] <= 200
        # Every returned owner must genuinely hold >= min_properties titles.
        for owner in data["owners"]:
            assert owner["property_count"] >= 2
            assert len(owner["titles"]) == owner["property_count"]

    async def test_requires_scoping_filter(self, live_context):
        result = await linz.execute_action("find_multi_property_owners", {}, live_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "scoping filter" in result.result.message

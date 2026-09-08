"""
End-to-end integration tests for the Stats NZ Datafinder integration.

These call the real Datafinder API and WFS services and require a valid
Datafinder API key in STATS_NZ_DATAFINDER_API_KEY (via .env or export).

    Create a key at https://datafinder.stats.govt.nz/my/api/

Run (all tests here are read-only — no destructive marker needed):
    pytest stats-nz-datafinder/tests/test_stats_nz_datafinder_integration.py -m "integration and not destructive"

Never runs in CI — the default marker filter (-m unit) and the
test_*_integration.py naming both exclude it.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from stats_nz_datafinder import stats_nz_datafinder

pytestmark = pytest.mark.integration

TEST_LAYER_ID = os.environ.get("STATS_NZ_DATAFINDER_TEST_LAYER_ID", "")
WELLINGTON = {
    "type": "Polygon",
    "coordinates": [
        [
            [174.778, -41.279],
            [174.782, -41.279],
            [174.782, -41.276],
            [174.778, -41.276],
            [174.778, -41.279],
        ]
    ],
}


@pytest_asyncio.fixture
async def live_context(env_credentials):
    """Custom-auth context with real REST fetch and a shared WFS session.

    REST catalogue/metadata calls go through ``context.fetch``. WFS calls go
    through aiohttp on ``context._session`` so the key-in-path URL never
    reaches SDK request logs.
    """
    api_key = env_credentials("STATS_NZ_DATAFINDER_API_KEY")
    if not api_key:
        pytest.skip("STATS_NZ_DATAFINDER_API_KEY not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": api_key}}

    async with aiohttp.ClientSession() as session:
        ctx._session = session

        async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    raise RateLimitError(60, 429, str(data), data)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

        ctx.fetch = AsyncMock(side_effect=real_fetch)
        yield ctx


async def _layer_id(live_context) -> int:
    if TEST_LAYER_ID:
        return int(TEST_LAYER_ID)
    result = await stats_nz_datafinder.execute_action(
        "search_layers", {"keyword": "census", "page_size": 5}, live_context
    )
    assert result.type == ResultType.ACTION, result.result
    layers = result.result.data["layers"]
    if not layers:
        pytest.skip("No public vector layers returned for keyword 'census'")
    return layers[0]["id"]


class TestSearchLayers:
    async def test_returns_public_vector_layers(self, live_context):
        result = await stats_nz_datafinder.execute_action(
            "search_layers", {"keyword": "statistical area", "page_size": 5}, live_context
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert isinstance(data["layers"], list)
        assert len(data["layers"]) <= 5
        assert data["page"] == 1
        if data["layers"]:
            assert isinstance(data["layers"][0]["id"], int)
            assert "title" in data["layers"][0]


class TestGetLayerMetadata:
    async def test_returns_citation_fields(self, live_context):
        layer_id = await _layer_id(live_context)
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": layer_id}, live_context)
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["layer_id"] == layer_id
        assert data["source_url"].endswith(f"/layers/{layer_id}/")
        assert data["page_url"].startswith("https://datafinder.stats.govt.nz/")
        assert "title" in data
        assert "licence" in data
        assert "attribution" in data
        assert isinstance(data["fields"], list)
        assert isinstance(data["coded_field_count"], int)
        assert isinstance(data["attachments"], list)
        if data["description"]:
            assert len(data["description"]) <= 400

    async def test_unknown_layer_errors(self, live_context):
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 99999999}, live_context)
        assert result.type == ResultType.ACTION_ERROR


class TestQueryLayerByGeometry:
    async def test_returns_geojson_for_wellington_polygon(self, live_context):
        layer_id = await _layer_id(live_context)
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {"layer_id": layer_id, "geometry": WELLINGTON, "page_size": 5, "max_pages": 1},
            live_context,
        )
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Layer {layer_id} is not queryable over WFS: {result.result.message}")
        data = result.result.data
        assert data["layer_id"] == layer_id
        assert isinstance(data["records"], list)
        assert len(data["records"]) <= 5
        assert data["record_count"] == len(data["records"])
        assert data["retrieved_pages"] >= 1
        assert "truncated" in data
        if data["records"]:
            record = data["records"][0]
            assert "properties" in record
            assert "geometry" not in record
            assert "overlap_fraction" in record
            assert "coded_fields_omitted" in data
            frac = record["overlap_fraction"]
            if frac is not None:
                assert 0.0 <= frac <= 1.0
            area = record["feature_area_sq_km"]
            if area is not None:
                assert area >= 0

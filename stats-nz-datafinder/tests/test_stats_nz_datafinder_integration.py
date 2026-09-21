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

import base64
import json
import os
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from stats_nz_datafinder import stats_nz_datafinder

pytestmark = pytest.mark.integration

TEST_LAYER_ID = os.environ.get("STATS_NZ_DATAFINDER_TEST_LAYER_ID", "")
CENSUS_SA1_LAYER_ID = 120766
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


def _wellington_geojson_file() -> dict:
    payload = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": WELLINGTON, "properties": {}}],
    }
    return {
        "name": "catchments.geojson",
        "contentType": "application/geo+json",
        "content": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii"),
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
    queryable = [
        layer
        for layer in layers
        if isinstance(layer, dict) and layer.get("queryable") and isinstance(layer.get("id"), int)
    ]
    if not queryable:
        pytest.skip("No queryable public vector layers returned for keyword 'census'")
    return queryable[0]["id"]


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
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["layer_id"] == layer_id
        assert isinstance(data["records"], list)
        assert len(data["records"]) <= 5
        assert data["record_count"] == len(data["records"])
        assert data["retrieved_pages"] == (1 if data["records"] else 0)
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

    async def test_export_geojson_returns_feature_collection_file(self, live_context):
        layer_id = await _layer_id(live_context)
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {
                "layer_id": layer_id,
                "geometry": WELLINGTON,
                "page_size": 50,
                "max_pages": 20,
                "export_geojson": True,
            },
            live_context,
        )
        if result.type == ResultType.ACTION_ERROR and "incomplete_pagination" in str(result.result.message):
            pytest.skip("Wellington clip exceeds page cap on this layer")
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        exported_file = data["files"][0]
        assert exported_file["name"] == f"layer-{layer_id}-query.geojson"
        assert exported_file["contentType"] == "application/geo+json"
        exported = json.loads(base64.b64decode(exported_file["content"]))
        assert exported["type"] == "FeatureCollection"
        assert len(exported["features"]) == data["record_count"]
        if exported["features"]:
            feature = exported["features"][0]
            assert feature["type"] == "Feature"
            assert "overlap_fraction" in feature["properties"]
            assert "geometry" in feature
            assert "geometry" not in data["records"][0]

    async def test_scopes_query_from_geojson_file(self, live_context):
        layer_id = await _layer_id(live_context)
        geojson_file = _wellington_geojson_file()
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {"layer_id": layer_id, "file": geojson_file, "page_size": 5, "max_pages": 1},
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        source = data["geometry_source"]
        assert source["name"] == "catchments.geojson"
        assert source["feature_index"] == 0
        assert "coordinates" not in source
        if data["records"]:
            assert "geometry" not in data["records"][0]


async def _census_count_field(live_context) -> tuple[int, dict]:
    layer_id = CENSUS_SA1_LAYER_ID
    metadata = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": layer_id}, live_context)
    if metadata.type != ResultType.ACTION:
        pytest.skip(f"Census SA1 layer {layer_id} is not available")
    count_fields = [
        field
        for field in metadata.result.data.get("fields", [])
        if isinstance(field, dict)
        and field.get("coded")
        and isinstance(field.get("name"), str)
        and str(field.get("measure") or "").strip().lower() == "count"
    ]
    if not count_fields:
        pytest.skip(f"Layer {layer_id} has no codebook Count fields")
    count_field = next(
        (field for field in count_fields if field["name"] == "VAR_1_3"),
        count_fields[0],
    )
    return layer_id, count_field


def _population_measure(count_field: dict) -> dict:
    return {
        "key": "population",
        "label": count_field.get("title") or "Census count",
        "field": count_field["name"],
        "unit": "count",
        "aggregation": "additive_count",
    }


class TestQueryAreaStatistics:
    async def test_returns_compact_totals_for_wellington_polygon(self, live_context):
        layer_id, count_field = await _census_count_field(live_context)
        result = await stats_nz_datafinder.execute_action(
            "query_area_statistics",
            {
                "layer_id": layer_id,
                "geometry": WELLINGTON,
                "measures": [_population_measure(count_field)],
                "page_size": 50,
                "max_pages": 20,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["layer"]["layer_id"] == layer_id
        assert len(data["results"]) == 1
        row = data["results"][0]
        assert row["field"] == count_field["name"]
        assert row["status"] in {"ok", "partial", "unavailable"}
        assert data["validation_status"] == row["status"]
        if row["estimated_value"] is not None:
            assert row["estimated_value"] >= 0
        assert data["geography_summary"]["intersecting_feature_count"] >= 0

    async def test_returns_compact_totals_from_geojson_file(self, live_context):
        layer_id, count_field = await _census_count_field(live_context)
        geojson_file = _wellington_geojson_file()
        result = await stats_nz_datafinder.execute_action(
            "query_area_statistics",
            {
                "layer_id": layer_id,
                "file": geojson_file,
                "measures": [_population_measure(count_field)],
                "page_size": 50,
                "max_pages": 20,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        source = data["geometry_source"]
        assert source["name"] == "catchments.geojson"
        assert source["feature_index"] == 0
        assert "coordinates" not in source
        assert "geometry" not in data
        if data["results"][0]["estimated_value"] is not None:
            assert data["results"][0]["estimated_value"] >= 0

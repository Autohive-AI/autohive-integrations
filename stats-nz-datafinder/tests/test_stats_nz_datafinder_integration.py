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
import csv
import io
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


class TestQueryAreaStatistics:
    async def test_returns_compact_totals_for_wellington_polygon(self, live_context):
        search = await stats_nz_datafinder.execute_action(
            "search_layers", {"keyword": "census statistical area 1", "page_size": 10}, live_context
        )
        assert search.type == ResultType.ACTION, search.result
        layers = [
            layer
            for layer in search.result.data["layers"]
            if isinstance(layer, dict) and layer.get("queryable") and isinstance(layer.get("id"), int)
        ]
        if not layers:
            pytest.skip("No queryable Census SA1 layer returned")
        layer_id = layers[0]["id"]
        metadata = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": layer_id}, live_context)
        assert metadata.type == ResultType.ACTION, metadata.result
        coded = [
            field["name"]
            for field in metadata.result.data.get("fields", [])
            if isinstance(field, dict) and field.get("coded") and isinstance(field.get("name"), str)
        ]
        if not coded:
            pytest.skip(f"Layer {layer_id} has no VAR_* census fields")
        result = await stats_nz_datafinder.execute_action(
            "query_area_statistics",
            {
                "layer_id": layer_id,
                "geometry": WELLINGTON,
                "measures": [
                    {
                        "key": "population",
                        "label": "Census count",
                        "field": coded[0],
                        "unit": "count",
                        "aggregation": "additive_count",
                    }
                ],
                "page_size": 50,
                "max_pages": 20,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        assert data["validation_status"] == "ok"
        assert data["layer"]["layer_id"] == layer_id
        assert data["files"] == []
        assert "source_records" not in data
        assert len(data["results"]) == 1
        row = data["results"][0]
        assert row["field"] == coded[0]
        assert row["status"] in {"ok", "partial", "unavailable"}
        if row["estimated_value"] is not None:
            assert row["estimated_value"] >= 0
        assert data["geography_summary"]["intersecting_feature_count"] >= 0

    async def test_csv_export_is_a_platform_file_without_credentials(self, live_context):
        metadata = await stats_nz_datafinder.execute_action(
            "get_layer_metadata", {"layer_id": CENSUS_SA1_LAYER_ID}, live_context
        )
        if metadata.type != ResultType.ACTION:
            pytest.skip(f"Census SA1 layer {CENSUS_SA1_LAYER_ID} is not available")
        measure_field = None
        for field in metadata.result.data.get("fields") or []:
            if not isinstance(field, dict) or not field.get("coded"):
                continue
            codebook_measure = str(field.get("measure") or "").strip().lower()
            if codebook_measure and codebook_measure != "count":
                continue
            if field.get("name") == "VAR_1_3":
                measure_field = field
                break
            if measure_field is None and isinstance(field.get("name"), str):
                measure_field = field
        if measure_field is None:
            pytest.skip("No additive Census count field on layer 120766")
        result = await stats_nz_datafinder.execute_action(
            "query_area_statistics",
            {
                "layer_id": CENSUS_SA1_LAYER_ID,
                "geometry": WELLINGTON,
                "measures": [
                    {
                        "key": "population",
                        "label": measure_field.get("title") or "Census count",
                        "field": measure_field["name"],
                        "unit": "count",
                        "aggregation": "additive_count",
                    }
                ],
                "export_source_records": True,
                "export_format": "csv",
                "page_size": 50,
                "max_pages": 20,
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result
        data = result.result.data
        files = data["files"]
        assert len(files) == 1
        file_obj = files[0]
        assert file_obj["name"].endswith(".csv")
        assert file_obj["contentType"] == "text/csv"
        raw = base64.b64decode(file_obj["content"])
        api_key = live_context.auth["credentials"]["api_key"]
        assert api_key.encode("utf-8") not in raw
        assert b"Authorization" not in raw
        text = raw.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
        for required in (
            "source_feature_id",
            "geography_code",
            "overlap_fraction",
            "population_source_value",
            "population_contribution",
            "population_status",
        ):
            assert required in fieldnames
        rows = list(reader)
        assert len(rows) == data["geography_summary"]["intersecting_feature_count"]
        for row in rows:
            fraction = float(row["overlap_fraction"])
            assert 0.0 <= fraction <= 1.0
            assert row["population_status"] in {"included", "unavailable", "suppressed"}

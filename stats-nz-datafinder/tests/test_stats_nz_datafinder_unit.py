from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stats_nz_datafinder import (
    GetLayerMetadataAction,
    QueryLayerByGeometryAction,
    SearchLayersAction,
    _wfs_url,
)

pytestmark = pytest.mark.unit


class Response:
    def __init__(self, data, headers=None):
        self.data = data
        self.headers = headers or {}


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": "test-key"}}
    ctx.fetch = AsyncMock()
    return ctx


GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.3]]],
}
CAPABILITIES = """<?xml version="1.0"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0">
  <wfs:FeatureTypeList>
    <wfs:FeatureType><wfs:Name>layer-123</wfs:Name></wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>"""
METADATA = {
    "title": "Census SA2",
    "description": "Boundary data",
    "first_published_at": "2023-01-01T00:00:00Z",
    "license": "CC BY 4.0",
    "supplier_reference": "Stats NZ",
}


async def test_query_collects_paginated_features_and_metadata(context):
    context.fetch.return_value = Response(METADATA)
    wfs_request = AsyncMock(
        side_effect=[
            CAPABILITIES,
            {
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [{"type": "Feature", "id": "a", "geometry": None, "properties": {}}],
            },
            {
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [
                    {"type": "Feature", "id": "b", "geometry": None, "properties": {}},
                    {"type": "Feature", "id": "c", "geometry": None, "properties": {}},
                ],
            },
        ]
    )
    with patch("stats_nz_datafinder._wfs_request", wfs_request):
        result = await QueryLayerByGeometryAction().execute(
            {"layer_id": 123, "geometry": GEOMETRY, "page_size": 2, "max_pages": 5},
            context,
        )
    assert [feature["id"] for feature in result.data["feature_collection"]["features"]] == ["a", "b", "c"]
    assert result.data["data_vintage"] == "2023-01-01T00:00:00Z"
    assert result.data["licence"] == "CC BY 4.0"
    get_feature = wfs_request.await_args_list[1].args[1]
    assert get_feature["outputFormat"] == "json"
    assert "filter" not in get_feature
    assert get_feature["cql_filter"].startswith("INTERSECTS(Shape, SRID=4326;POLYGON((")
    assert "174.7 -41.3" in get_feature["cql_filter"]
    assert wfs_request.await_args_list[2].args[1]["startIndex"] == 2


async def test_query_rejects_unclosed_geometry(context):
    bad_geometry = {
        "type": "Polygon",
        "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.2]]],
    }
    result = await QueryLayerByGeometryAction().execute({"layer_id": 123, "geometry": bad_geometry}, context)
    assert result.message == "Each polygon ring must be closed."
    assert context.fetch.await_count == 0


async def test_query_falls_back_to_layer_id_when_site_wide_capabilities_omit_layer(context):
    context.fetch.return_value = Response(METADATA)
    wfs_request = AsyncMock(
        side_effect=[
            CAPABILITIES.replace("layer-123", "layer-999"),
            {
                "type": "FeatureCollection",
                "numberMatched": 1,
                "features": [{"type": "Feature", "id": "a", "geometry": None, "properties": {}}],
            },
        ]
    )
    with patch("stats_nz_datafinder._wfs_request", wfs_request):
        result = await QueryLayerByGeometryAction().execute(
            {"layer_id": 123, "geometry": GEOMETRY, "page_size": 1, "max_pages": 1},
            context,
        )
    assert result.data["feature_collection"]["features"][0]["id"] == "a"
    assert wfs_request.await_args_list[0].kwargs["layer_id"] == 123
    assert wfs_request.await_args_list[1].kwargs["layer_id"] == 123
    assert wfs_request.await_args_list[1].args[1]["typeNames"] == "layer-123"


async def test_query_uses_advertised_namespaced_feature_type(context):
    context.fetch.return_value = Response(METADATA)
    capabilities = CAPABILITIES.replace("layer-123", "kx:layer-123")
    wfs_request = AsyncMock(
        side_effect=[
            capabilities,
            {
                "type": "FeatureCollection",
                "numberMatched": 1,
                "features": [{"type": "Feature", "id": "a", "geometry": None, "properties": {}}],
            },
        ]
    )
    with patch("stats_nz_datafinder._wfs_request", wfs_request):
        result = await QueryLayerByGeometryAction().execute(
            {"layer_id": 123, "geometry": GEOMETRY, "page_size": 1, "max_pages": 1},
            context,
        )
    assert result.data["feature_collection"]["features"][0]["id"] == "a"
    assert wfs_request.await_args_list[1].args[1]["typeNames"] == "kx:layer-123"


async def test_query_uses_metadata_geometry_field_and_attribute_cql(context):
    context.fetch.return_value = Response({**METADATA, "data": {"geometry_field": "geom"}})
    wfs_request = AsyncMock(
        side_effect=[
            CAPABILITIES,
            {
                "type": "FeatureCollection",
                "numberMatched": 1,
                "features": [{"type": "Feature", "id": "a", "geometry": None, "properties": {}}],
            },
        ]
    )
    with patch("stats_nz_datafinder._wfs_request", wfs_request):
        result = await QueryLayerByGeometryAction().execute(
            {
                "layer_id": 123,
                "geometry": GEOMETRY,
                "attribute_filters": [{"property": "population", "operator": "gte", "value": 100}],
                "page_size": 1,
                "max_pages": 1,
            },
            context,
        )
    assert result.data["feature_collection"]["features"][0]["id"] == "a"
    cql = wfs_request.await_args_list[1].args[1]["cql_filter"]
    assert cql.startswith("INTERSECTS(geom, SRID=4326;POLYGON((")
    assert " AND (population >= 100)" in cql


def test_wfs_url_uses_layer_specific_key_in_path(context):
    context.auth["credentials"]["api_key"] = "key with/slash"
    assert _wfs_url(context, 120897).endswith("services;key=key%20with%2Fslash/wfs/layer-120897")


async def test_metadata_normalises_citation_fields(context):
    context.fetch.return_value = Response(METADATA)
    result = await GetLayerMetadataAction().execute({"layer_id": 123}, context)
    assert result.data["attribution"] == "Stats NZ"
    assert result.data["source_url"].endswith("/layers/123/")


async def test_search_extracts_layers_and_total(context):
    context.fetch.return_value = Response(
        [{"id": 123, "title": "Census SA2", "description": "test"}],
        {"X-Resource-Range": "0-20/44"},
    )
    result = await SearchLayersAction().execute({"keyword": "census"}, context)
    assert result.data == {
        "layers": [{"id": 123, "title": "Census SA2", "description": "test"}],
        "page": 1,
        "page_size": 20,
        "total": 44,
    }


async def test_missing_key_returns_action_error(context):
    context.auth = {"auth_type": "Custom", "credentials": {}}
    result = await GetLayerMetadataAction().execute({"layer_id": 123}, context)
    assert result.message == "A Stats NZ Datafinder API key is required."

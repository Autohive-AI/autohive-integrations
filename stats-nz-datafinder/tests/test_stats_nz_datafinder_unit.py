from unittest.mock import AsyncMock, MagicMock

import pytest
from stats_nz_datafinder import (
    GetLayerMetadataAction,
    QueryLayerByGeometryAction,
    SearchLayersAction,
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
METADATA = {
    "title": "Census SA2",
    "description": "Boundary data",
    "first_published_at": "2023-01-01T00:00:00Z",
    "license": "CC BY 4.0",
    "supplier_reference": "Stats NZ",
}


async def test_query_collects_paginated_features_and_metadata(context):
    context.fetch.side_effect = [
        Response(METADATA),
        Response(
            {
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [{"type": "Feature", "id": "a", "geometry": None, "properties": {}}],
            }
        ),
        Response(
            {
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [
                    {"type": "Feature", "id": "b", "geometry": None, "properties": {}},
                    {"type": "Feature", "id": "c", "geometry": None, "properties": {}},
                ],
            }
        ),
    ]
    result = await QueryLayerByGeometryAction().execute(
        {"layer_id": 123, "geometry": GEOMETRY, "page_size": 2, "max_pages": 5}, context
    )
    assert [feature["id"] for feature in result.data["feature_collection"]["features"]] == ["a", "b", "c"]
    assert result.data["data_vintage"] == "2023-01-01T00:00:00Z"
    assert result.data["licence"] == "CC BY 4.0"
    assert context.fetch.await_args_list[2].kwargs["params"]["startIndex"] == 2


async def test_query_rejects_unclosed_geometry(context):
    context.fetch.return_value = Response(METADATA)
    bad_geometry = {
        "type": "Polygon",
        "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.2]]],
    }
    result = await QueryLayerByGeometryAction().execute({"layer_id": 123, "geometry": bad_geometry}, context)
    assert result.message == "Each polygon ring must be closed."
    assert context.fetch.await_count == 1


async def test_metadata_normalises_citation_fields(context):
    context.fetch.return_value = Response(METADATA)
    result = await GetLayerMetadataAction().execute({"layer_id": 123}, context)
    assert result.data["attribution"] == "Stats NZ"
    assert result.data["source_url"].endswith("/layers/123/")


async def test_search_extracts_layers_and_total(context):
    context.fetch.return_value = Response(
        [{"id": 123, "title": "Census SA2", "description": "test"}], {"X-Resource-Range": "0-20/44"}
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

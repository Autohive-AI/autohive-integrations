"""Unit tests for the Stats NZ Datafinder integration using mocked HTTP seams."""

import asyncio
import json
from unittest.mock import MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType
from stats_nz_datafinder import (
    DatafinderError,
    _as_shapely,
    _attribution,
    _bbox_polygon,
    _build_cql_filter,
    _cql_literal,
    _fields,
    _geometry_field,
    _get_api_key,
    _licence,
    _overlap_stats,
    _parse_bbox,
    _redact,
    _requested_attribute_names,
    _coded_fields_omitted_count,
    _resolve_feature_type,
    _short_description,
    _stable_sort_field,
    _total_matched,
    _vintage,
    _wfs_request,
    _wfs_url,
    _WfsResponse,
    _wkt_geometry,
    stats_nz_datafinder,
)

pytestmark = pytest.mark.unit

SENTINEL_KEY = "SEKRET"  # nosec B105
SENTINEL_FILTER = "ZZFILTERSENTINELZZ"

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.3]]],
}
CAPABILITIES = """<?xml version="1.0" encoding="UTF-8"?>
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


def ok(data, status=200):
    return _WfsResponse(status=status, data=data)


def fetch_ok(data, headers=None):
    return FetchResponse(status=200, headers=headers or {}, data=data)


def square(west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


def collection(*feature_ids, number_matched=None, geometry=None, properties=None):
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {} if properties is None else properties,
            }
            for fid in feature_ids
        ],
    }
    if number_matched is not None:
        payload["numberMatched"] = number_matched
    return payload


async def _query(mock_context, inputs=None):
    payload = {"layer_id": 123, "geometry": GEOMETRY, "page_size": 2, "max_pages": 5}
    if inputs:
        payload.update(inputs)
    return await stats_nz_datafinder.execute_action("query_layer_by_geometry", payload, mock_context)


# =============================================================================
# Auth
# =============================================================================


class TestGetApiKey:
    def test_nested_credentials(self, mock_context):
        assert _get_api_key(mock_context) == "test_api_key"

    def test_missing_raises(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}
        with pytest.raises(DatafinderError, match="API key is required"):
            _get_api_key(mock_context)

    @pytest.mark.asyncio
    async def test_execute_action_with_platform_auth_envelope(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION
        mock_context.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_flat_auth_rejected_by_sdk(self, mock_context):
        mock_context.auth = {"api_key": "flat_key"}  # nosec B105
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_key_blocked_before_fetch(self, mock_context):
        # auth.fields.required includes api_key, so the SDK rejects an empty
        # credentials object before the handler runs.
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# =============================================================================
# Pure helpers
# =============================================================================


class TestHelpers:
    def test_wkt_point(self):
        assert _wkt_geometry({"type": "Point", "coordinates": [174.774, -41.338]}) == "POINT(174.774 -41.338)"

    def test_wkt_polygon(self):
        wkt = _wkt_geometry(GEOMETRY)
        assert wkt.startswith("POLYGON((")
        assert "174.7 -41.3" in wkt

    def test_wkt_multipolygon(self):
        geometry = {"type": "MultiPolygon", "coordinates": [GEOMETRY["coordinates"], GEOMETRY["coordinates"]]}
        wkt = _wkt_geometry(geometry)
        assert wkt.startswith("MULTIPOLYGON(")

    def test_wkt_rejects_unclosed_ring(self):
        with pytest.raises(DatafinderError, match="must be closed"):
            _wkt_geometry(
                {
                    "type": "Polygon",
                    "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.2]]],
                }
            )

    def test_wkt_rejects_out_of_range_coordinates(self):
        with pytest.raises(DatafinderError, match="WGS84"):
            _wkt_geometry(
                {
                    "type": "Polygon",
                    "coordinates": [[[200, -41.3], [174.8, -41.3], [174.8, -41.2], [200, -41.3]]],
                }
            )

    def test_bbox_unwraps_datafinder_national_extent(self):
        west, south, east, north = _parse_bbox([166.1, -47.8, 184.5, -34.0])
        assert west == pytest.approx(166.1)
        assert east == pytest.approx(-175.5)
        assert south == pytest.approx(-47.8)
        assert north == pytest.approx(-34.0)
        geometry = _bbox_polygon([166.1, -47.8, 184.5, -34.0])
        assert geometry["type"] == "MultiPolygon"
        assert _wkt_geometry(geometry).startswith("MULTIPOLYGON(")

    def test_bbox_antimeridian_west_greater_than_east(self):
        geometry = _bbox_polygon([170.0, -48.0, -170.0, -34.0])
        assert geometry["type"] == "MultiPolygon"
        west, _south, east, _north = _parse_bbox([170.0, -48.0, -170.0, -34.0])
        assert west == pytest.approx(170.0)
        assert east == pytest.approx(-170.0)

    def test_bbox_simple_window_stays_polygon(self):
        geometry = _bbox_polygon([174.7, -41.3, 174.8, -41.2])
        assert geometry["type"] == "Polygon"

    def test_bbox_rejects_zero_span_and_inverted_lat(self):
        with pytest.raises(DatafinderError, match="south < north"):
            _parse_bbox([174.7, -41.2, 174.8, -41.2])
        with pytest.raises(DatafinderError, match="non-zero longitude"):
            _parse_bbox([174.7, -41.3, 174.7, -41.2])

    def test_cql_literal_escapes_quotes(self):
        assert _cql_literal("O'Brien") == "'O''Brien'"

    def test_cql_literal_bool_is_not_int(self):
        assert _cql_literal(True) == "true"
        assert _cql_literal(False) == "false"

    def test_cql_filter_includes_attribute_clause(self):
        cql = _build_cql_filter(
            "POLYGON((0 0, 1 0, 1 1, 0 0))",
            [{"property": "population", "operator": "gte", "value": 100}],
            "geom",
        )
        assert cql.startswith("INTERSECTS(geom, SRID=4326;POLYGON((0 0")
        assert " AND (population >= 100)" in cql

    def test_cql_contains_uses_ilike(self):
        cql = _build_cql_filter(
            None,
            [{"property": "SA22023_V1_00_NAME", "operator": "contains", "value": "Island Bay"}],
            "Shape",
        )
        assert cql == "(SA22023_V1_00_NAME ILIKE '%Island Bay%')"
        assert "INTERSECTS" not in cql

    def test_cql_ieq_is_exact_case_insensitive(self):
        cql = _build_cql_filter(
            None,
            [{"property": "SA22023_V1_00_NAME", "operator": "ieq", "value": "Wellington Central"}],
            "Shape",
        )
        assert cql == "(SA22023_V1_00_NAME ILIKE 'Wellington Central')"
        assert "%" not in cql

    def test_cql_rejects_unscoped(self):
        with pytest.raises(DatafinderError, match="Unscoped national scans"):
            _build_cql_filter(None, None, "Shape")

    def test_cql_rejects_non_identifier_property(self):
        with pytest.raises(DatafinderError, match="valid property"):
            _build_cql_filter(
                "POLYGON((0 0, 1 0, 1 1, 0 0))",
                [{"property": "a);DROP", "operator": "eq", "value": 1}],
                "Shape",
            )

    def test_geometry_field_defaults_to_shape(self):
        assert _geometry_field({}) == "Shape"
        assert _geometry_field({"data": {"geometry_field": "geom"}}) == "geom"
        assert _geometry_field({"data": {"geometry_field": "1bad"}}) == "Shape"

    def test_stable_sort_field_prefers_primary_key(self):
        assert (
            _stable_sort_field(
                {
                    "data": {
                        "primary_key_fields": ["feature_key"],
                        "fields": [
                            {"name": "SA22023_V1_00", "type": "string"},
                            {"name": "feature_key", "type": "integer"},
                        ],
                    }
                }
            )
            == "feature_key"
        )

    def test_stable_sort_field_joins_composite_primary_key(self):
        assert (
            _stable_sort_field(
                {
                    "data": {
                        "geometry_field": "Shape",
                        "primary_key_fields": ["owner_id", "title_no", "Shape"],
                        "fields": [
                            {"name": "Shape", "type": "geometry"},
                            {"name": "owner_id", "type": "integer"},
                            {"name": "title_no", "type": "string"},
                        ],
                    }
                }
            )
            == "owner_id,title_no"
        )

    def test_stable_sort_field_uses_id_then_geography_code(self):
        assert _stable_sort_field({}) is None
        assert _stable_sort_field({"data": {"fields": [{"name": "VAR_1_1", "type": "integer"}]}}) is None
        assert (
            _stable_sort_field(
                {
                    "data": {
                        "fields": [
                            {"name": "Shape", "type": "geometry"},
                            {"name": "SA22023_V1_00", "type": "string"},
                            {"name": "VAR_1_1", "type": "integer"},
                        ]
                    }
                }
            )
            == "SA22023_V1_00"
        )
        assert (
            _stable_sort_field(
                {
                    "data": {
                        "fields": [
                            {"name": "id", "type": "integer"},
                            {"name": "SA22023_V1_00", "type": "string"},
                        ]
                    }
                }
            )
            == "id"
        )
        assert _stable_sort_field({"data": {"primary_key_fields": ["Shape"], "geometry_field": "Shape"}}) is None

    def test_licence_from_object_title(self):
        assert _licence({"license": {"title": "Creative Commons Attribution 4.0 International"}}) == (
            "Creative Commons Attribution 4.0 International"
        )

    def test_licence_from_string(self):
        assert _licence({"license": "CC BY 4.0"}) == "CC BY 4.0"

    def test_attribution_from_group_name(self):
        assert _attribution({"group": {"name": "GIS"}}) == "GIS"

    def test_vintage_prefers_collected_at(self):
        assert _vintage({"collected_at": "2024-01-01", "first_published_at": "2020-01-01"}) == "2024-01-01"

    def test_total_matched_ignores_unknown_and_bool(self):
        assert _total_matched({"numberMatched": "unknown"}) is None
        assert _total_matched({"numberMatched": True}) is None
        assert _total_matched({"numberMatched": "12"}) == 12
        assert _total_matched({"numberMatched": 3}) == 3

    def test_resolve_feature_type_namespaced(self):
        xml = CAPABILITIES.replace("layer-123", "kx:layer-123")
        assert _resolve_feature_type(123, xml) == "kx:layer-123"

    def test_resolve_feature_type_fallback(self):
        assert _resolve_feature_type(123, CAPABILITIES.replace("layer-123", "layer-999")) == "layer-123"

    def test_wfs_url_uses_layer_specific_key_in_path(self, mock_context):
        mock_context.auth["credentials"]["api_key"] = "key with/slash"  # nosec B105
        assert _wfs_url(mock_context, 120897).endswith("services;key=key%20with%2Fslash/wfs/layer-120897")

    def test_short_description_keeps_first_paragraph(self):
        long_blurb = "Dataset contains life-cycle age group counts by statistical area 2.\n\n" + ("Footnotes. " * 80)
        short = _short_description(long_blurb)
        assert short is not None
        assert "life-cycle age group" in short
        assert "Footnotes" not in short
        assert len(short) <= 400

    def test_fields_skip_geometry(self):
        fields = _fields(
            {
                "data": {
                    "geometry_field": "Shape",
                    "fields": [
                        {"name": "Shape", "type": "geometry"},
                        {"name": "VAR_1_1", "type": "integer"},
                        {"name": "SA22023_V1_00_NAME", "type": "string", "title": "SA2 name"},
                    ],
                }
            }
        )
        assert fields == [
            {"name": "VAR_1_1", "type": "integer", "coded": True},
            {"name": "SA22023_V1_00_NAME", "type": "string", "title": "SA2 name"},
        ]

    def test_overlap_identical_polygons_is_one(self):
        geom = square(174.7, -41.3, 174.8, -41.2)
        stats = _overlap_stats(_as_shapely(geom), geom)
        assert stats["overlap_fraction"] == 1.0
        assert stats["overlap_area_sq_km"] == stats["feature_area_sq_km"]
        assert stats["feature_area_sq_km"] > 0

    def test_overlap_half_coverage(self):
        query = square(174.7, -41.3, 174.75, -41.2)
        feature = square(174.7, -41.3, 174.8, -41.2)
        stats = _overlap_stats(_as_shapely(query), feature)
        assert stats["overlap_fraction"] == pytest.approx(0.5, abs=0.02)

    def test_point_overlap_is_one_not_zero(self):
        point = {"type": "Point", "coordinates": [174.75, -41.25]}
        feature = square(174.7, -41.3, 174.8, -41.2)
        stats = _overlap_stats(_as_shapely(point), feature)
        assert stats["overlap_fraction"] == 1.0
        assert stats["overlap_area_sq_km"] is None
        assert stats["feature_area_sq_km"] > 0

    def test_attribute_only_overlap_is_one(self):
        feature = square(174.7, -41.3, 174.8, -41.2)
        stats = _overlap_stats(None, feature)
        assert stats["overlap_fraction"] == 1.0

    def test_line_feature_under_polygon_clip_has_no_area_share(self):
        query = square(174.7, -41.3, 174.8, -41.2)
        line = {
            "type": "LineString",
            "coordinates": [[174.6, -41.25], [174.75, -41.25], [174.9, -41.25]],
        }
        stats = _overlap_stats(_as_shapely(query), line)
        assert stats["overlap_fraction"] is None
        assert stats["overlap_area_sq_km"] is None
        assert stats["feature_area_sq_km"] == 0.0


# =============================================================================
# query_layer_by_geometry
# =============================================================================


class TestQueryLayerByGeometry:
    @pytest.mark.asyncio
    async def test_collects_paginated_features_and_metadata(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", number_matched=3)),
            ok(collection("b", "c", number_matched=3)),
        ]
        result = await _query(mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert [record["id"] for record in data["records"]] == ["a", "b", "c"]
        assert data["record_count"] == 3
        assert "feature_collection" not in data
        assert "geometry" not in data["records"][0]
        assert data["data_vintage"] == "2023-01-01T00:00:00Z"
        assert data["licence"] == "CC BY 4.0"
        assert data["truncated"] is False
        assert data["total_matched"] == 3
        assert data["coded_fields_omitted"] == 0
        assert "note" not in data
        get_feature = mock_wfs.await_args_list[1].kwargs["params"]
        assert mock_wfs.await_args_list[0].kwargs.get("method") in (None, "GET")
        assert mock_wfs.await_args_list[1].kwargs["method"] == "POST"
        assert get_feature["outputFormat"] == "json"
        assert get_feature["srsName"] == "EPSG:4326"
        assert "filter" not in get_feature
        assert get_feature["cql_filter"].startswith("INTERSECTS(Shape, SRID=4326;POLYGON((")
        assert "sortBy" not in get_feature
        assert mock_wfs.await_args_list[2].kwargs["params"]["startIndex"] == 2
        assert mock_wfs.await_args_list[2].kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_rejects_unclosed_geometry(self, mock_context):
        result = await _query(
            mock_context,
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[174.7, -41.3], [174.8, -41.3], [174.8, -41.2], [174.7, -41.2]]],
                }
            },
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Each polygon ring must be closed."
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_layer_id_when_capabilities_omit_layer(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES.replace("layer-123", "layer-999")),
            ok(collection("a", number_matched=1)),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        assert mock_wfs.await_args_list[0].kwargs["layer_id"] == 123
        assert mock_wfs.await_args_list[1].kwargs["params"]["typeNames"] == "layer-123"

    @pytest.mark.asyncio
    async def test_uses_advertised_namespaced_feature_type(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES.replace("layer-123", "kx:layer-123")),
            ok(collection("a", number_matched=1)),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        assert mock_wfs.await_args_list[1].kwargs["params"]["typeNames"] == "kx:layer-123"

    @pytest.mark.asyncio
    async def test_uses_metadata_geometry_field_and_attribute_cql(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok({**METADATA, "data": {"geometry_field": "geom"}})
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await _query(
            mock_context,
            {
                "attribute_filters": [{"property": "population", "operator": "gte", "value": 100}],
                "page_size": 1,
                "max_pages": 1,
            },
        )
        assert result.type == ResultType.ACTION
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert cql.startswith("INTERSECTS(geom, SRID=4326;POLYGON((")
        assert " AND (population >= 100)" in cql

    @pytest.mark.asyncio
    async def test_named_area_ieq_is_not_a_substring(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {
                "layer_id": 123,
                "attribute_filters": [
                    {"property": "SA22023_V1_00_NAME", "operator": "ieq", "value": "Wellington Central"}
                ],
                "page_size": 1,
                "max_pages": 1,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert cql == "(SA22023_V1_00_NAME ILIKE 'Wellington Central')"

    @pytest.mark.asyncio
    async def test_returns_overlap_and_omits_geometry_by_default(self, mock_context, mock_wfs):
        query = square(174.7, -41.3, 174.8, -41.2)
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(
                collection(
                    "island-bay",
                    number_matched=1,
                    geometry=query,
                    properties={"SA22023_V1_00_NAME": "Island Bay East", "VAR_1_1": 1200},
                )
            ),
        ]
        result = await _query(mock_context, {"geometry": query, "page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        record = result.result.data["records"][0]
        assert record["properties"]["SA22023_V1_00_NAME"] == "Island Bay East"
        assert "VAR_1_1" not in record["properties"]
        assert result.result.data["coded_fields_omitted"] == 1
        assert record["overlap_fraction"] == 1.0
        assert "geometry" not in record

    @pytest.mark.asyncio
    async def test_fields_allowlist_keeps_coded_columns(self, mock_context, mock_wfs):
        census_meta = {
            **METADATA,
            "data": {
                "geometry_field": "Shape",
                "fields": [
                    {"name": "Shape", "type": "geometry"},
                    {"name": "SA22023_V1_00_NAME", "type": "string"},
                    {"name": "VAR_1_1", "type": "integer"},
                    {"name": "VAR_1_2", "type": "integer"},
                ],
            },
        }
        mock_context.fetch.return_value = fetch_ok(census_meta)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(
                collection(
                    "island-bay",
                    number_matched=1,
                    properties={"SA22023_V1_00_NAME": "Island Bay East", "VAR_1_1": 1200},
                )
            ),
        ]
        result = await _query(
            mock_context, {"page_size": 1, "max_pages": 1, "fields": ["SA22023_V1_00_NAME", "VAR_1_1"]}
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["records"][0]["properties"] == {
            "SA22023_V1_00_NAME": "Island Bay East",
            "VAR_1_1": 1200,
        }
        assert result.result.data["coded_fields_omitted"] == 1
        assert mock_wfs.await_args_list[1].kwargs["params"]["propertyName"] == "Shape,SA22023_V1_00_NAME,VAR_1_1"

    def test_coded_omitted_count_uses_schema_not_row_keys(self):
        metadata = {
            "data": {
                "fields": [
                    {"name": "SA22023_V1_00_NAME", "type": "string"},
                    {"name": "VAR_1_1", "type": "integer"},
                    {"name": "VAR_1_2", "type": "integer"},
                ]
            }
        }
        assert (
            _coded_fields_omitted_count(metadata, fields=["SA22023_V1_00_NAME", "VAR_1_1"], include_coded_fields=False)
            == 1
        )
        assert _coded_fields_omitted_count(metadata, fields=["NAME", "VAR_9_9"], include_coded_fields=False) == 2
        assert _coded_fields_omitted_count(metadata, fields=None, include_coded_fields=False) == 2
        assert _coded_fields_omitted_count(metadata, fields=None, include_coded_fields=True) == 0

    @pytest.mark.asyncio
    async def test_empty_fields_list_is_rejected(self, mock_context):
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {"layer_id": 123, "geometry": GEOMETRY, "fields": []},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()
        with pytest.raises(DatafinderError, match="at least one property name"):
            _requested_attribute_names({}, fields=[], include_coded_fields=False)

    @pytest.mark.asyncio
    async def test_default_query_asks_wfs_for_non_coded_fields(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(
            {
                **METADATA,
                "data": {
                    "geometry_field": "Shape",
                    "fields": [
                        {"name": "Shape", "type": "geometry"},
                        {"name": "SA22023_V1_00_NAME", "type": "string"},
                        {"name": "VAR_1_1", "type": "integer"},
                    ],
                },
            }
        )
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        assert result.result.data["coded_fields_omitted"] == 1
        assert mock_wfs.await_args_list[1].kwargs["params"]["propertyName"] == "Shape,SA22023_V1_00_NAME"

    @pytest.mark.asyncio
    async def test_include_geometry_adds_rings(self, mock_context, mock_wfs):
        query = square(174.7, -41.3, 174.8, -41.2)
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("island-bay", number_matched=1, geometry=query, properties={"VAR_1_1": 1200})),
        ]
        result = await _query(
            mock_context, {"geometry": query, "page_size": 1, "max_pages": 1, "include_geometry": True}
        )
        assert result.result.data["records"][0]["geometry"]["type"] == "Polygon"

    @pytest.mark.asyncio
    async def test_point_query_does_not_area_weight(self, mock_context, mock_wfs):
        feature = square(174.7, -41.3, 174.8, -41.2)
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("island-bay", number_matched=1, geometry=feature, properties={"VAR_1_1": 1200})),
        ]
        result = await _query(
            mock_context,
            {
                "geometry": {"type": "Point", "coordinates": [174.75, -41.25]},
                "page_size": 1,
                "max_pages": 1,
            },
        )
        assert result.type == ResultType.ACTION
        record = result.result.data["records"][0]
        assert record["overlap_fraction"] == 1.0
        assert record["overlap_area_sq_km"] is None
        assert record["feature_area_sq_km"] > 0
        assert "note" not in result.result.data
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert "POINT(174.75 -41.25)" in cql

    @pytest.mark.asyncio
    async def test_bbox_query(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {"layer_id": 123, "bbox": [174.7, -41.3, 174.8, -41.2], "page_size": 1, "max_pages": 1},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert cql.startswith("INTERSECTS(Shape, SRID=4326;POLYGON((")

    @pytest.mark.asyncio
    async def test_unwrapped_national_bbox_uses_multipolygon_cql(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {
                "layer_id": 123,
                "bbox": [166.1, -47.8, 184.5, -34.0],
                "page_size": 1,
                "max_pages": 1,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert "MULTIPOLYGON" in cql
        assert mock_wfs.await_args_list[1].kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_named_area_lookup_without_geometry(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("island-bay", number_matched=1, properties={"SA22023_V1_00_NAME": "Island Bay East"})),
        ]
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {
                "layer_id": 123,
                "attribute_filters": [
                    {"property": "SA22023_V1_00_NAME", "operator": "contains", "value": "Island Bay"}
                ],
                "page_size": 1,
                "max_pages": 1,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["records"][0]["overlap_fraction"] == 1.0
        assert "note" not in result.result.data
        cql = mock_wfs.await_args_list[1].kwargs["params"]["cql_filter"]
        assert "ILIKE" in cql
        assert "INTERSECTS" not in cql

    @pytest.mark.asyncio
    async def test_page_size_above_cap_is_validation_error(self, mock_context):
        result = await stats_nz_datafinder.execute_action(
            "query_layer_by_geometry",
            {"layer_id": 123, "geometry": GEOMETRY, "page_size": 1000},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_unscoped_query(self, mock_context):
        result = await stats_nz_datafinder.execute_action("query_layer_by_geometry", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Unscoped national scans" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_truncated_when_match_count_exceeds_page_cap(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=9))]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.result.data["truncated"] is True
        assert result.result.data["retrieved_pages"] == 1

    @pytest.mark.asyncio
    async def test_probes_when_match_count_unknown(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", number_matched="unknown")),
            ok(collection("b")),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.result.data["truncated"] is True
        probe = mock_wfs.await_args_list[2].kwargs["params"]
        assert probe["startIndex"] == 1
        assert probe["count"] == 1
        assert "sortBy" not in probe

    @pytest.mark.asyncio
    async def test_pages_and_probe_share_geography_code_sort(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(
            {
                **METADATA,
                "data": {
                    "fields": [
                        {"name": "Shape", "type": "geometry"},
                        {"name": "SA22023_V1_00", "type": "string"},
                        {"name": "VAR_1_1", "type": "integer"},
                    ]
                },
            }
        )
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", number_matched="unknown")),
            ok(collection("b")),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.result.data["truncated"] is True
        for call in mock_wfs.await_args_list[1:]:
            assert call.kwargs["params"]["sortBy"] == "SA22023_V1_00"

    @pytest.mark.asyncio
    async def test_pages_sort_by_composite_primary_key(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(
            {
                **METADATA,
                "data": {
                    "geometry_field": "Shape",
                    "primary_key_fields": ["owner_id", "title_no"],
                    "fields": [
                        {"name": "Shape", "type": "geometry"},
                        {"name": "owner_id", "type": "integer"},
                        {"name": "title_no", "type": "string"},
                    ],
                },
            }
        )
        mock_wfs.side_effect = [ok(CAPABILITIES), ok(collection("a", number_matched=1))]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        assert mock_wfs.await_args_list[1].kwargs["params"]["sortBy"] == "owner_id,title_no"

    @pytest.mark.asyncio
    async def test_drops_duplicate_feature_ids_across_pages(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", "b", number_matched=3)),
            ok(collection("b", "c", number_matched=3)),
        ]
        result = await _query(mock_context)
        assert result.type == ResultType.ACTION
        assert [record["id"] for record in result.result.data["records"]] == ["a", "b", "c"]
        assert result.result.data["record_count"] == 3

    @pytest.mark.asyncio
    async def test_later_page_failure_returns_partial_truncated(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", "b", number_matched=4)),
            DatafinderError("Datafinder WFS request timed out."),
        ]
        result = await _query(mock_context, {"page_size": 2, "max_pages": 5})
        assert result.type == ResultType.ACTION
        assert [record["id"] for record in result.result.data["records"]] == ["a", "b"]
        assert result.result.data["truncated"] is True
        assert result.result.data["retrieved_pages"] == 1

    @pytest.mark.asyncio
    async def test_first_page_failure_is_still_an_error(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            DatafinderError("Datafinder WFS request timed out."),
        ]
        result = await _query(mock_context, {"page_size": 2, "max_pages": 5})
        assert result.type == ResultType.ACTION_ERROR
        assert "timed out" in result.result.message

    @pytest.mark.asyncio
    async def test_probe_failure_keeps_page_and_marks_truncated(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok(collection("a", number_matched="unknown")),
            DatafinderError("Datafinder WFS request timed out."),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION
        assert [record["id"] for record in result.result.data["records"]] == ["a"]
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_http_error_on_metadata_is_mapped(self, mock_context, mock_wfs):
        mock_context.fetch.side_effect = HTTPError(404, "missing")
        result = await _query(mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Datafinder could not find layer 123."
        mock_wfs.assert_not_called()

    @pytest.mark.asyncio
    async def test_wfs_400_does_not_echo_provider_body(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [
            ok(CAPABILITIES),
            ok({"message": f"rejected {SENTINEL_FILTER} for key {SENTINEL_KEY}"}, status=400),
        ]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION_ERROR
        assert SENTINEL_KEY not in result.result.message
        assert SENTINEL_FILTER not in result.result.message
        assert "rejected the WFS request" in result.result.message

    @pytest.mark.asyncio
    async def test_unexpected_exception_text_is_not_echoed(self, mock_context, mock_wfs):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = Exception(
            f"aiohttp: GET https://datafinder.stats.govt.nz/services;key={SENTINEL_KEY}/wfs failed"
        )
        result = await _query(mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert SENTINEL_KEY not in result.result.message
        assert "datafinder.stats.govt.nz" not in result.result.message
        assert result.result.message.startswith("The Stats NZ Datafinder integration hit an unexpected error")


# =============================================================================
# get_layer_metadata / search_layers
# =============================================================================


class TestGetLayerMetadata:
    @pytest.mark.asyncio
    async def test_normalises_citation_fields(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["attribution"] == "Stats NZ"
        assert result.result.data["source_url"].endswith("/layers/123/")
        assert result.result.data["page_url"] == "https://datafinder.stats.govt.nz/layer/123/"
        assert result.result.data["coded_field_count"] == 0
        assert result.result.data["attachments"] == []
        url = mock_context.fetch.call_args.args[0]
        assert url == "https://datafinder.stats.govt.nz/services/api/v1/layers/123/"
        assert mock_context.fetch.call_args.kwargs["headers"]["Authorization"] == "Key test_api_key"
        assert result.result.data["fields"] == []

    @pytest.mark.asyncio
    async def test_truncates_description_and_returns_fields(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(
            {
                **METADATA,
                "description": "Age counts by SA2.\n\n" + ("Confidentiality footnotes. " * 60),
                "data": {
                    "geometry_field": "Shape",
                    "fields": [
                        {"name": "Shape", "type": "geometry"},
                        {"name": "VAR_1_1", "type": "integer"},
                    ],
                },
            }
        )
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.result.data["description"] == "Age counts by SA2."
        assert result.result.data["fields"] == [{"name": "VAR_1_1", "type": "integer", "coded": True}]
        assert result.result.data["coded_field_count"] == 1

    @pytest.mark.asyncio
    async def test_includes_page_url_and_attachments(self, mock_context):
        mock_context.fetch.side_effect = [
            fetch_ok(
                {
                    **METADATA,
                    "url_html": "https://datafinder.stats.govt.nz/layer/123-census/",
                    "attachments": "https://datafinder.stats.govt.nz/services/api/v1/layers/123/versions/1/attachments/",
                }
            ),
            fetch_ok([{"title": "Variable lookup", "url": "https://example.test/lookup.csv"}]),
        ]
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["page_url"] == "https://datafinder.stats.govt.nz/layer/123-census/"
        assert result.result.data["attachments"] == [
            {"name": "Variable lookup", "url": "https://example.test/lookup.csv"}
        ]
        assert mock_context.fetch.await_count == 2

    @pytest.mark.asyncio
    async def test_missing_attachments_leave_empty_list(self, mock_context):
        mock_context.fetch.side_effect = [
            fetch_ok({**METADATA, "attachments": "https://example.test/attachments/"}),
            HTTPError(404, "missing"),
        ]
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["attachments"] == []

    @pytest.mark.asyncio
    async def test_attachment_rate_limit_is_surfaced(self, mock_context):
        mock_context.fetch.side_effect = [
            fetch_ok({**METADATA, "attachments": "https://example.test/attachments/"}),
            RateLimitError(60, 429, "slow down", None),
        ]
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "rate-limited" in result.result.message

    @pytest.mark.asyncio
    async def test_licence_object_from_live_api_shape(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(
            {
                **METADATA,
                "license": {"title": "Creative Commons Attribution 4.0 International", "type": "cc-by"},
                "group": {"name": "GIS"},
            }
        )
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.result.data["licence"] == "Creative Commons Attribution 4.0 International"

    @pytest.mark.asyncio
    async def test_http_401(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "nope")
        result = await stats_nz_datafinder.execute_action("get_layer_metadata", {"layer_id": 123}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "rejected the API key" in result.result.message


class TestSearchLayers:
    @pytest.mark.asyncio
    async def test_extracts_layers_and_total(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(
            [
                {
                    "id": 123,
                    "title": "Census SA2",
                    "description": "test",
                    "published_at": "2024-12-18T00:00:00Z",
                    "user_capabilities": ["can-spatial-query", "can-export"],
                }
            ],
            headers={"X-Resource-Range": "0-20/44"},
        )
        result = await stats_nz_datafinder.execute_action("search_layers", {"keyword": "census"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "layers": [
                {
                    "id": 123,
                    "title": "Census SA2",
                    "description": "test",
                    "published_at": "2024-12-18T00:00:00Z",
                    "queryable": True,
                }
            ],
            "page": 1,
            "page_size": 20,
            "total": 44,
        }
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["q"] == "census"
        assert params["kind"] == "vector"
        assert params["public"] == "true"

    @pytest.mark.asyncio
    async def test_malformed_resource_range_leaves_total_none(self, mock_context):
        mock_context.fetch.return_value = fetch_ok(
            [{"id": 123, "title": "Census SA2"}],
            headers={"X-Resource-Range": "0-20/unknown"},
        )
        result = await stats_nz_datafinder.execute_action("search_layers", {"keyword": "census"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["total"] is None
        assert result.result.data["layers"][0]["id"] == 123

    @pytest.mark.asyncio
    async def test_rate_limit(self, mock_context):
        mock_context.fetch.side_effect = RateLimitError(60, 429, "slow down", None)
        result = await stats_nz_datafinder.execute_action("search_layers", {"keyword": "census"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "rate-limited" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_keyword_is_validation_error(self, mock_context):
        result = await stats_nz_datafinder.execute_action("search_layers", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# =============================================================================
# _wfs_request / _redact — the aiohttp seam that keeps the key out of logs
# =============================================================================


class _FakeResp:
    def __init__(self, status=200, text="{}", content_type="application/json"):
        self.status = status
        self._text = text
        self.headers = {"Content-Type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self):
        return self._text


class _RaisingCtx:
    def __init__(self, error):
        self._error = error

    async def __aenter__(self):
        raise self._error

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, resp=None, error=None):
        self._resp = resp
        self._error = error
        self.calls = []

    def get(self, url, params=None, **kwargs):
        self.calls.append(("GET", url, params, kwargs))
        return _RaisingCtx(self._error) if self._error is not None else self._resp

    def post(self, url, data=None, params=None, **kwargs):
        self.calls.append(("POST", url, data, kwargs))
        return _RaisingCtx(self._error) if self._error is not None else self._resp

    async def close(self):  # pragma: no cover - not exercised
        pass


def _key_context(session):
    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": SENTINEL_KEY}}  # nosec B105
    ctx._session = session
    return ctx


class TestRedact:
    def test_strips_key_from_url(self):
        url = "https://datafinder.stats.govt.nz/services;key=SEKRET/wfs/layer-1"
        out = _redact(url)
        assert "SEKRET" not in out
        assert "services;key=<redacted>/wfs" in out

    def test_passes_through_unrelated_text(self):
        assert _redact("Connection refused") == "Connection refused"
        assert _redact(None) == ""


class TestWfsRequestDirect:
    @pytest.mark.asyncio
    async def test_key_placed_in_url_path_not_params(self, monkeypatch):
        import stats_nz_datafinder as module

        session = _FakeSession(resp=_FakeResp(text=json.dumps({"features": []})))
        monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)
        ctx = _key_context(session)

        result = await _wfs_request(ctx, params={"service": "WFS", "cql_filter": "a = 'b'"}, layer_id=123)

        assert result.status == 200
        assert result.data == {"features": []}
        method, url, params, _ = session.calls[0]
        assert method == "GET"
        assert f"services;key={SENTINEL_KEY}/wfs/layer-123" in url
        assert SENTINEL_KEY not in json.dumps(params)
        assert params["cql_filter"] == "a = 'b'"

    @pytest.mark.asyncio
    async def test_get_feature_post_puts_cql_in_body_not_query(self, monkeypatch):
        import stats_nz_datafinder as module

        session = _FakeSession(resp=_FakeResp(text=json.dumps({"features": []})))
        monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)
        ctx = _key_context(session)
        cql = "INTERSECTS(Shape, SRID=4326;POLYGON((" + ", ".join(["174.7 -41.3"] * 80) + ")))"

        result = await _wfs_request(
            ctx,
            params={"service": "WFS", "request": "GetFeature", "cql_filter": cql},
            layer_id=123,
            method="POST",
        )

        assert result.status == 200
        method, url, data, _ = session.calls[0]
        assert method == "POST"
        assert f"services;key={SENTINEL_KEY}/wfs/layer-123" in url
        assert "cql_filter" not in url
        assert data["cql_filter"] == cql
        assert SENTINEL_KEY not in json.dumps(data)

    @pytest.mark.asyncio
    async def test_xml_body_returned_as_string(self, monkeypatch):
        import stats_nz_datafinder as module

        session = _FakeSession(resp=_FakeResp(status=400, text="<ExceptionReport/>", content_type="application/xml"))
        monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)
        result = await _wfs_request(_key_context(session), params={"service": "WFS"}, layer_id=123)
        assert result.status == 400
        assert result.data == "<ExceptionReport/>"

    @pytest.mark.asyncio
    async def test_client_error_text_is_discarded(self, monkeypatch):
        import stats_nz_datafinder as module

        leaky = (
            f"cannot connect to https://datafinder.stats.govt.nz/services;key={SENTINEL_KEY}/wfs"
            f"?cql_filter=INTERSECTS(Shape,'{SENTINEL_FILTER}')"
        )
        session = _FakeSession(error=aiohttp.ClientError(leaky))
        monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)

        with pytest.raises(DatafinderError) as excinfo:
            await _wfs_request(_key_context(session), params={"service": "WFS"}, layer_id=123)

        message = str(excinfo.value)
        assert SENTINEL_KEY not in message
        assert SENTINEL_FILTER not in message
        assert "datafinder.stats.govt.nz" not in message
        assert "could not reach the Stats NZ Datafinder service" in message

    @pytest.mark.asyncio
    async def test_timeout_message_has_no_url(self, monkeypatch):
        import stats_nz_datafinder as module

        session = _FakeSession(error=asyncio.TimeoutError())
        monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)

        with pytest.raises(DatafinderError) as excinfo:
            await _wfs_request(_key_context(session), params={"service": "WFS"}, layer_id=123)

        message = str(excinfo.value)
        assert SENTINEL_KEY not in message
        assert "timed out" in message


class TestErrorsDoNotLeakKey:
    LEAKY_XML = (
        '<?xml version="1.0"?><ows:ExceptionReport version="2.0.0">'
        '<ows:Exception exceptionCode="InvalidParameterValue" locator="filter">'
        f"<ows:ExceptionText>Unable to parse cql_filter: INTERSECTS(Shape, '{SENTINEL_FILTER}') "
        f"requested from https://datafinder.stats.govt.nz/services;key={SENTINEL_KEY}/wfs"
        "</ows:ExceptionText></ows:Exception></ows:ExceptionReport>"
    )

    @staticmethod
    def assert_clean(message):
        assert SENTINEL_KEY not in message
        assert SENTINEL_FILTER not in message
        assert "cql_filter" not in message.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [200, 400, 403, 500])
    async def test_xml_exception_report_is_not_echoed(self, mock_context, mock_wfs, status):
        mock_context.fetch.return_value = fetch_ok(METADATA)
        mock_wfs.side_effect = [ok(self.LEAKY_XML, status=status)]
        result = await _query(mock_context, {"page_size": 1, "max_pages": 1})
        assert result.type == ResultType.ACTION_ERROR
        self.assert_clean(result.result.message)

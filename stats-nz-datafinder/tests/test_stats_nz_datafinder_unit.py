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
    _attribution,
    _build_cql_filter,
    _cql_literal,
    _geometry_field,
    _get_api_key,
    _licence,
    _redact,
    _resolve_feature_type,
    _total_matched,
    _vintage,
    _wfs_request,
    _wkt_geometry,
    _WfsResponse,
    stats_nz_datafinder,
    _wfs_url,
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


def collection(*feature_ids, number_matched=None):
    payload = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "id": fid, "geometry": None, "properties": {}} for fid in feature_ids],
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
        assert [feature["id"] for feature in data["feature_collection"]["features"]] == ["a", "b", "c"]
        assert data["data_vintage"] == "2023-01-01T00:00:00Z"
        assert data["licence"] == "CC BY 4.0"
        assert data["truncated"] is False
        get_feature = mock_wfs.await_args_list[1].kwargs["params"]
        assert get_feature["outputFormat"] == "json"
        assert "filter" not in get_feature
        assert get_feature["cql_filter"].startswith("INTERSECTS(Shape, SRID=4326;POLYGON((")
        assert mock_wfs.await_args_list[2].kwargs["params"]["startIndex"] == 2

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
        url = mock_context.fetch.call_args.args[0]
        assert url == "https://datafinder.stats.govt.nz/services/api/v1/layers/123/"
        assert mock_context.fetch.call_args.kwargs["headers"]["Authorization"] == "Key test_api_key"

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
            [{"id": 123, "title": "Census SA2", "description": "test"}],
            headers={"X-Resource-Range": "0-20/44"},
        )
        result = await stats_nz_datafinder.execute_action("search_layers", {"keyword": "census"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "layers": [{"id": 123, "title": "Census SA2", "description": "test"}],
            "page": 1,
            "page_size": 20,
            "total": 44,
        }
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["q"] == "census"
        assert params["kind"] == "vector"
        assert params["public"] == "true"

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
        self.calls.append((url, params, kwargs))
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
        url, params, _ = session.calls[0]
        assert f"services;key={SENTINEL_KEY}/wfs/layer-123" in url
        assert SENTINEL_KEY not in json.dumps(params)
        assert params["cql_filter"] == "a = 'b'"

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

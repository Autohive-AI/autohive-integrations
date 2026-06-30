"""Unit tests for the LINZ integration using a mocked WFS fetch."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from linz.linz import (
    linz,
    _and,
    _cql_literal,
    _extract_exception_text,
    _extract_features,
    _get_api_key,
    _normalize_layer,
    _owner_key,
    _split_owners,
    _total_matched,
    LAYER_TITLES_OWNERS,
    LAYER_PRIMARY_PARCELS,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def feature(props, geometry=None, fid=None):
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": props}


def collection(features, **extra):
    return {"type": "FeatureCollection", "features": features, **extra}


# =============================================================================
# Auth
# =============================================================================


class TestGetApiKey:
    def test_flat_auth(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {"api_key": "abc"}  # nosec B105
        assert _get_api_key(ctx) == "abc"

    def test_nested_credentials(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {"credentials": {"api_key": "xyz"}}  # nosec B105
        assert _get_api_key(ctx) == "xyz"

    def test_missing_raises(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {}
        with pytest.raises(ValueError, match="API key is required"):
            _get_api_key(ctx)

    @pytest.mark.asyncio
    async def test_missing_key_blocked_before_fetch(self, mock_context):
        # The SDK validates the required api_key auth field before the handler
        # runs, so a missing key never reaches the network.
        mock_context.auth = {}
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# =============================================================================
# Pure helpers
# =============================================================================


class TestHelpers:
    def test_normalize_layer_digits(self):
        assert _normalize_layer("50805") == "layer-50805"

    def test_normalize_layer_prefixed(self):
        assert _normalize_layer("layer-50805") == "layer-50805"
        assert _normalize_layer("table-50806") == "table-50806"

    def test_normalize_layer_blank_raises(self):
        with pytest.raises(ValueError):
            _normalize_layer("  ")

    def test_cql_literal_escapes_quotes(self):
        assert _cql_literal("O'Brien") == "'O''Brien'"

    def test_and_combines(self):
        assert _and(["a = 1", "b = 2"]) == "(a = 1) AND (b = 2)"

    def test_and_drops_empty(self):
        assert _and(["a = 1", "", None]) == "(a = 1)"

    def test_and_all_empty_is_none(self):
        assert _and(["", None]) is None

    def test_split_owners_comma(self):
        assert _split_owners("JOHN SMITH, JANE SMITH") == ["JOHN SMITH", "JANE SMITH"]

    def test_split_owners_single(self):
        assert _split_owners("ACME PROPERTIES LIMITED") == ["ACME PROPERTIES LIMITED"]

    def test_split_owners_empty(self):
        assert _split_owners("") == []
        assert _split_owners(None) == []

    def test_split_owners_list(self):
        assert _split_owners(["A", " B "]) == ["A", "B"]

    def test_owner_key_normalises(self):
        assert _owner_key("  john   smith ") == "JOHN SMITH"

    def test_extract_features(self):
        assert _extract_features(collection([{"x": 1}])) == [{"x": 1}]
        assert _extract_features({}) == []
        assert _extract_features("not json") == []

    def test_total_matched_coerces(self):
        # LDS returns totalFeatures as the string "unknown" — must become None.
        assert _total_matched({"totalFeatures": "unknown", "numberReturned": 1}) is None
        assert _total_matched({"numberMatched": 42}) == 42
        assert _total_matched({"totalFeatures": "42"}) == 42
        assert _total_matched({}) is None

    def test_extract_exception_text(self):
        xml = (
            '<?xml version="1.0"?><ows:ExceptionReport><ows:Exception>'
            "<ows:ExceptionText>Feature type :layer-50805 unknown</ows:ExceptionText>"
            "</ows:Exception></ows:ExceptionReport>"
        )
        assert _extract_exception_text(xml) == "Feature type :layer-50805 unknown"


# =============================================================================
# WFS request construction & error handling
# =============================================================================


class TestWfsRequest:
    @pytest.mark.asyncio
    async def test_key_in_url_and_params(self, mock_context):
        mock_context.fetch.return_value = ok(collection([]))
        await linz.execute_action("search_property_titles", {"title_no": "NA1/1"}, mock_context)
        args, kwargs = mock_context.fetch.call_args
        url = args[0]
        assert "services;key=test_api_key/wfs" in url
        params = kwargs["params"]
        assert params["service"] == "WFS"
        assert params["version"] == "2.0.0"
        assert params["request"] == "GetFeature"
        assert params["typeNames"] == LAYER_TITLES_OWNERS
        assert params["outputFormat"] == "json"
        assert params["cql_filter"] == "(title_no = 'NA1/1')"

    @pytest.mark.asyncio
    async def test_403_gives_licence_hint(self, mock_context):
        mock_context.fetch.return_value = ok({"message": "forbidden"}, status=403)
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Personal Data" in result.result.message

    @pytest.mark.asyncio
    async def test_xml_exception_report(self, mock_context):
        mock_context.fetch.return_value = ok("<ExceptionReport>bad cql</ExceptionReport>")
        result = await linz.execute_action("search_property_titles", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "exception" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_unknown_layer_maps_to_licence_hint(self, mock_context):
        # Real LDS behaviour for an unlicensed ownership layer: 400 + unknown
        # feature type. Should surface the Personal Data Licence hint.
        xml = (
            '<?xml version="1.0"?><ows:ExceptionReport><ows:Exception exceptionCode="InvalidParameterValue">'
            "<ows:ExceptionText>Feature type :layer-50805 unknown</ows:ExceptionText>"
            "</ows:Exception></ows:ExceptionReport>"
        )
        mock_context.fetch.return_value = ok(xml, status=400)
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Personal Data" in result.result.message

    @pytest.mark.asyncio
    async def test_total_matched_unknown_is_null(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection([feature({"title_no": "NA1/1"})], totalFeatures="unknown", numberReturned=1)
        )
        result = await linz.execute_action("search_property_titles", {"title_no": "NA1/1"}, mock_context)
        assert result.result.data["total_matched"] is None

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_action_error(self, mock_context):
        # Every action wraps work in try/except — a transport failure must
        # surface as an ActionError, not propagate.
        mock_context.fetch.side_effect = Exception("Connection refused")
        result = await linz.execute_action("search_property_titles", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_500_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = ok({"message": "boom"}, status=500)
        result = await linz.execute_action("search_parcels", {"appellation": "Lot 1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "500" in result.result.message


# =============================================================================
# search_property_titles
# =============================================================================


class TestSearchPropertyTitles:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection(
                [feature({"title_no": "NA1/1", "owners": "JOHN SMITH", "land_district": "North Auckland"})],
                numberMatched=1,
            )
        )
        result = await linz.execute_action("search_property_titles", {"owner_name": "smith"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["count"] == 1
        assert data["titles"][0]["title_no"] == "NA1/1"
        assert "geometry" not in data["titles"][0]
        assert data["total_matched"] == 1

    @pytest.mark.asyncio
    async def test_owner_name_uses_ilike(self, mock_context):
        mock_context.fetch.return_value = ok(collection([]))
        await linz.execute_action("search_property_titles", {"owner_name": "smith"}, mock_context)
        cql = mock_context.fetch.call_args.kwargs["params"]["cql_filter"]
        assert "owners ILIKE '%smith%'" in cql

    @pytest.mark.asyncio
    async def test_requires_a_filter(self, mock_context):
        result = await linz.execute_action("search_property_titles", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one filter" in result.result.message
        mock_context.fetch.assert_not_called()


# =============================================================================
# get_title_owners
# =============================================================================


class TestGetTitleOwners:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection(
                [
                    feature(
                        {
                            "title_no": "NA1/1",
                            "owners": "JOHN SMITH, JANE SMITH",
                            "number_owners": 2,
                            "estate_description": "Fee Simple, 1/1",
                            "land_district": "North Auckland",
                            "status": "Live",
                        }
                    )
                ]
            )
        )
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["owners"] == ["JOHN SMITH", "JANE SMITH"]
        assert data["number_owners"] == 2
        assert data["estate_description"] == "Fee Simple, 1/1"

    @pytest.mark.asyncio
    async def test_missing_title_no(self, mock_context):
        # title_no is a required input — rejected by SDK validation pre-handler.
        result = await linz.execute_action("get_title_owners", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = ok(collection([]))
        result = await linz.execute_action("get_title_owners", {"title_no": "ZZ9/9"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "No title found" in result.result.message


# =============================================================================
# find_multi_property_owners (headline use case)
# =============================================================================


class TestFindMultiPropertyOwners:
    @pytest.mark.asyncio
    async def test_requires_scoping_filter(self, mock_context):
        result = await linz.execute_action("find_multi_property_owners", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "scoping filter is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_aggregates_distinct_titles(self, mock_context):
        # District-wide scan (no owner_name): both multi-title owners returned.
        # SMITH owns T1+T2; JONES owns T2+T3.
        mock_context.fetch.return_value = ok(
            collection(
                [
                    feature({"title_no": "T1", "owners": "JOHN SMITH", "land_district": "Otago"}),
                    feature({"title_no": "T2", "owners": "JOHN SMITH, JANE JONES", "land_district": "Otago"}),
                    feature({"title_no": "T3", "owners": "JANE JONES", "land_district": "Otago"}),
                ]
            )
        )
        result = await linz.execute_action("find_multi_property_owners", {"land_district": "Otago"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["titles_scanned"] == 3
        assert data["owner_count"] == 2
        by_name = {o["owner_name"]: o for o in data["owners"]}
        assert by_name["JOHN SMITH"]["property_count"] == 2
        assert {t["title_no"] for t in by_name["JOHN SMITH"]["titles"]} == {"T1", "T2"}
        assert {t["title_no"] for t in by_name["JANE JONES"]["titles"]} == {"T2", "T3"}

    @pytest.mark.asyncio
    async def test_owner_name_filters_co_owners(self, mock_context):
        # Scoped to SMITH: JANE JONES (a co-owner) must not be aggregated even
        # though she co-owns two titles with smiths.
        mock_context.fetch.return_value = ok(
            collection(
                [
                    feature({"title_no": "T1", "owners": "JOHN SMITH, JANE JONES"}),
                    feature({"title_no": "T2", "owners": "MARY SMITH, JANE JONES"}),
                ]
            )
        )
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "min_properties": 1},
            mock_context,
        )
        names = {o["owner_name"] for o in result.result.data["owners"]}
        assert "JANE JONES" not in names
        assert names == {"JOHN SMITH", "MARY SMITH"}

    @pytest.mark.asyncio
    async def test_min_properties_threshold(self, mock_context):
        mock_context.fetch.return_value = ok(collection([feature({"title_no": "T1", "owners": "SOLO OWNER"})]))
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"land_district": "Otago", "min_properties": 2},
            mock_context,
        )
        assert result.result.data["owner_count"] == 0

    @pytest.mark.asyncio
    async def test_duplicate_title_not_double_counted(self, mock_context):
        # Same title appearing twice (e.g. multiple estates) counts once.
        mock_context.fetch.return_value = ok(
            collection(
                [
                    feature({"title_no": "T1", "owners": "JOHN SMITH"}),
                    feature({"title_no": "T1", "owners": "JOHN SMITH"}),
                ]
            )
        )
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "min_properties": 1},
            mock_context,
        )
        owner = result.result.data["owners"][0]
        assert owner["property_count"] == 1

    @pytest.mark.asyncio
    async def test_truncation_flag_and_paging(self, mock_context):
        # Two full pages then exact stop at max_titles_scanned via truncation.
        page1 = collection([feature({"title_no": f"A{i}", "owners": "BULK OWNER"}) for i in range(1000)])
        page2 = collection([feature({"title_no": f"B{i}", "owners": "BULK OWNER"}) for i in range(1000)])
        mock_context.fetch.side_effect = [ok(page1), ok(page2)]
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "bulk", "max_titles_scanned": 2000, "min_properties": 1},
            mock_context,
        )
        data = result.result.data
        assert data["titles_scanned"] == 2000
        assert data["truncated"] is True
        assert mock_context.fetch.call_count == 2


# =============================================================================
# search_parcels
# =============================================================================


class TestSearchParcels:
    @pytest.mark.asyncio
    async def test_happy_path_strips_geometry(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection(
                [feature({"appellation": "Lot 1 DP 1", "parcel_intent": "Fee Simple"}, geometry={"big": "poly"})]
            )
        )
        result = await linz.execute_action("search_parcels", {"appellation": "Lot 1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["params"]["typeNames"] == LAYER_PRIMARY_PARCELS
        parcel = result.result.data["parcels"][0]
        assert parcel["appellation"] == "Lot 1 DP 1"
        assert "geometry" not in parcel

    @pytest.mark.asyncio
    async def test_include_geometry(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection([feature({"appellation": "Lot 1"}, geometry={"type": "Polygon"})])
        )
        result = await linz.execute_action(
            "search_parcels", {"appellation": "Lot 1", "include_geometry": True}, mock_context
        )
        assert result.result.data["parcels"][0]["geometry"] == {"type": "Polygon"}

    @pytest.mark.asyncio
    async def test_requires_filter(self, mock_context):
        result = await linz.execute_action("search_parcels", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


# =============================================================================
# query_layer
# =============================================================================


class TestQueryLayer:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(collection([feature({"id_field": 1})], numberMatched=1))
        result = await linz.execute_action(
            "query_layer",
            {"layer": "50805", "cql_filter": "land_district = 'Otago'", "limit": 5},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["typeNames"] == "layer-50805"
        assert params["cql_filter"] == "land_district = 'Otago'"
        assert params["count"] == 5
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_missing_layer(self, mock_context):
        # layer is a required input — rejected by SDK validation pre-handler.
        result = await linz.execute_action("query_layer", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

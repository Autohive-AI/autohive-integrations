"""Unit tests for the LINZ integration using a mocked WFS fetch."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from linz.linz import (
    linz,
    _and,
    _bounded_limit,
    _bounded_start_index,
    _cql_literal,
    _extract_exception_text,
    _extract_features,
    _get_api_key,
    _normalize_layer,
    _owner_display_name,
    _owner_key,
    _parse_capabilities_layers,
    _split_owners,
    _total_matched,
    LAYER_TITLES,
    LAYER_TITLES_OWNERS,
    LAYER_TITLE_OWNERS,
    LAYER_PRIMARY_PARCELS,
    MAX_QUERY_LIMIT,
    OWNER_SCAN_FIELDS,
    QueryLayerAction,
    TABLE_TITLE_OWNERS_LIST,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def feature(props, geometry=None, fid=None):
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": props}


def collection(features, **extra):
    return {"type": "FeatureCollection", "features": features, **extra}


def capabilities_xml(feature_types):
    """Build a WFS 2.0 GetCapabilities document, namespaced like real LDS output."""
    body = "".join(
        f"<FeatureType><Name>data.linz.govt.nz:{layer_id}</Name><Title>{title}</Title></FeatureType>"
        for layer_id, title in feature_types
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0" '
        'xmlns:wfs="http://www.opengis.net/wfs/2.0">'
        f"<FeatureTypeList>{body}</FeatureTypeList></wfs:WFS_Capabilities>"
    )


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
    async def test_execute_action_with_platform_auth_envelope(self, mock_context):
        # The platform passes {"auth_type": ..., "credentials": {...}} at
        # runtime; the full action path must work with that shape end-to-end.
        mock_context.auth = {"auth_type": "Custom", "credentials": {"api_key": "nested_key"}}  # nosec B105
        mock_context.fetch.return_value = ok({"type": "FeatureCollection", "features": []})
        result = await linz.execute_action("search_property_titles", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert "services;key=nested_key/wfs" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_flat_auth_rejected_by_sdk(self, mock_context):
        # SDK 2.0.1+ rejects non-envelope auth before the handler runs.
        mock_context.auth = {"api_key": "flat_key"}  # nosec B105
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_key_blocked_before_fetch(self, mock_context):
        # auth.fields has no "required" list, so an empty credentials object
        # passes SDK schema validation; the handler's own _get_api_key check
        # blocks the network call instead.
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "API key is required" in result.result.message
        mock_context.fetch.assert_not_called()


# =============================================================================
# Pure helpers
# =============================================================================


class TestHelpers:
    def test_normalize_layer_digits(self):
        assert _normalize_layer("50805") == "layer-50805"

    def test_normalize_layer_prefixed(self):
        assert _normalize_layer("layer-50805") == "layer-50805"
        assert _normalize_layer("table-51564") == "table-51564"

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

    def test_bounded_limit(self):
        assert _bounded_limit(None, 100, 1000) == 100  # default
        assert _bounded_limit(5, 100, 1000) == 5
        assert _bounded_limit(999999, 100, 1000) == 1000  # clamped to cap
        assert _bounded_limit(0, 100, 1000) == 1
        assert _bounded_limit(-3, 100, 1000) == 1

    def test_bounded_start_index(self):
        assert _bounded_start_index(None) is None
        assert _bounded_start_index(0) == 0
        assert _bounded_start_index(25) == 25
        assert _bounded_start_index(-5) == 0

    def test_owner_display_name_corporate(self):
        assert _owner_display_name({"corporate_name": "ACME LIMITED"}) == "ACME LIMITED"

    def test_owner_display_name_individual(self):
        # Mirrors LINZ's construction: prime_other_names + prime_surname.
        assert _owner_display_name({"prime_other_names": "John David", "prime_surname": "Smith"}) == "John David Smith"

    def test_owner_display_name_corporate_wins_and_empty_is_none(self):
        assert _owner_display_name({"corporate_name": "ACME", "prime_surname": "Smith"}) == "ACME"
        assert _owner_display_name({}) is None

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

    def test_parse_capabilities_layers(self):
        # Must handle the encoding declaration and strip the namespace prefix
        # from layer ids, exactly as real LDS capabilities documents need.
        xml = capabilities_xml(
            [("layer-50804", "NZ Property Titles"), ("table-51564", "NZ Property Titles Owners List")]
        )
        assert _parse_capabilities_layers(xml) == [
            {"id": "layer-50804", "title": "NZ Property Titles"},
            {"id": "table-51564", "title": "NZ Property Titles Owners List"},
        ]

    def test_parse_capabilities_layers_empty(self):
        # A key with no query scope returns capabilities with no FeatureTypeList.
        assert _parse_capabilities_layers(capabilities_xml([])) == []


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
    TITLE_50805 = collection(
        [
            feature(
                {
                    "title_no": "NA1/1",
                    "owners": "JANE SMITH, JOHN SMITH",
                    "estate_description": "Fee Simple, 1/1",
                    "land_district": "North Auckland",
                    "status": "Live",
                }
            )
        ]
    )

    @staticmethod
    def owner_row(**props):
        defaults = {
            "owner_type": "Individual",
            "estate_share": "1/2",
            "prime_surname": None,
            "prime_other_names": None,
            "corporate_name": None,
            "name_suffix": None,
        }
        return feature({**defaults, **props})

    @pytest.mark.asyncio
    async def test_happy_path_owners_from_normalised_table(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(self.TITLE_50805),
            ok(
                collection(
                    [
                        self.owner_row(prime_other_names="John", prime_surname="Smith"),
                        self.owner_row(prime_other_names="Jane", prime_surname="Smith"),
                    ]
                )
            ),
        ]
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["owners"] == ["John Smith", "Jane Smith"]
        assert data["owners_exact"] is True
        assert data["estate_description"] == "Fee Simple, 1/1"
        assert [d["owner_name"] for d in data["owner_details"]] == ["John Smith", "Jane Smith"]
        assert data["owner_details"][0]["estate_share"] == "1/2"
        # Second request must hit the normalised owners table.
        owners_params = mock_context.fetch.call_args.kwargs["params"]
        assert owners_params["typeNames"] == TABLE_TITLE_OWNERS_LIST
        assert owners_params["cql_filter"] == "title_no = 'NA1/1'"

    @pytest.mark.asyncio
    async def test_comma_in_corporate_name_is_one_owner(self, mock_context):
        # The regression the aggregated-string split could never get right: a
        # single owner whose real name contains a comma.
        mock_context.fetch.side_effect = [
            ok(self.TITLE_50805),
            ok(
                collection([self.owner_row(owner_type="Corporate", corporate_name="SMITH, JONES AND PARTNERS LIMITED")])
            ),
        ]
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        data = result.result.data
        assert data["owners"] == ["SMITH, JONES AND PARTNERS LIMITED"]
        assert data["owners_exact"] is True

    @pytest.mark.asyncio
    async def test_falls_back_to_display_string_when_table_empty(self, mock_context):
        mock_context.fetch.side_effect = [ok(self.TITLE_50805), ok(collection([]))]
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        data = result.result.data
        assert data["owners"] == ["JANE SMITH", "JOHN SMITH"]
        assert data["owners_exact"] is False
        assert data["owner_details"] == []

    @pytest.mark.asyncio
    async def test_falls_back_when_table_inaccessible(self, mock_context):
        # A key licensed for layer-50805 but not table-51564 must still work.
        unknown = (
            '<?xml version="1.0"?><ows:ExceptionReport><ows:Exception>'
            "<ows:ExceptionText>Feature type :table-51564 unknown</ows:ExceptionText>"
            "</ows:Exception></ows:ExceptionReport>"
        )
        mock_context.fetch.side_effect = [ok(self.TITLE_50805), ok(unknown, status=400)]
        result = await linz.execute_action("get_title_owners", {"title_no": "NA1/1"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["owners"] == ["JANE SMITH", "JOHN SMITH"]
        assert data["owners_exact"] is False

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
        # No owners-table lookup for a missing title.
        assert mock_context.fetch.call_count == 1


# =============================================================================
# find_multi_property_owners (headline use case)
# =============================================================================


class TestFindMultiPropertyOwners:
    @staticmethod
    def owner_row(owner, title_no, district="Otago", status="LIVE", part=False):
        """One layer-50806 feature: a distinct (owner, title) pair."""
        return feature(
            {
                "owner": owner,
                "title_no": title_no,
                "title_status": status,
                "land_district": district,
                "part_ownership": part,
            }
        )

    @staticmethod
    def detail_row(title_no, estate="Fee Simple, 1/1", type_="Freehold"):
        """One layer-50805 enrichment feature."""
        return feature({"title_no": title_no, "estate_description": estate, "type": type_})

    @pytest.mark.asyncio
    async def test_requires_scoping_filter(self, mock_context):
        result = await linz.execute_action("find_multi_property_owners", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "scoping filter is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_aggregates_distinct_titles_from_owner_rows(self, mock_context):
        # District-wide scan: SMITH owns T1+T2; JONES owns T2+T3. Each scanned
        # record is one (owner, title) row — no string splitting involved.
        mock_context.fetch.side_effect = [
            ok(
                collection(
                    [
                        self.owner_row("JOHN SMITH", "T1"),
                        self.owner_row("JOHN SMITH", "T2"),
                        self.owner_row("JANE JONES", "T2"),
                        self.owner_row("JANE JONES", "T3"),
                    ]
                )
            ),
            ok(collection([self.detail_row(t) for t in ("T1", "T2", "T3")])),
        ]
        result = await linz.execute_action("find_multi_property_owners", {"land_district": "Otago"}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["titles_scanned"] == 4  # owner-title rows, not titles
        assert data["owner_count"] == 2
        by_name = {o["owner_name"]: o for o in data["owners"]}
        assert by_name["JOHN SMITH"]["property_count"] == 2
        assert {t["title_no"] for t in by_name["JOHN SMITH"]["titles"]} == {"T1", "T2"}
        assert {t["title_no"] for t in by_name["JANE JONES"]["titles"]} == {"T2", "T3"}
        # The scan must hit the row-per-owner layer without geometry.
        scan_params = mock_context.fetch.call_args_list[0].kwargs["params"]
        assert scan_params["typeNames"] == LAYER_TITLE_OWNERS
        assert scan_params["propertyName"] == OWNER_SCAN_FIELDS

    @pytest.mark.asyncio
    async def test_comma_in_owner_name_is_single_owner(self, mock_context):
        # The regression comma-splitting used to get wrong: one corporate owner
        # whose real name contains ', ' must not become two owners.
        mock_context.fetch.return_value = ok(
            collection(
                [
                    self.owner_row("SMITH, JONES AND PARTNERS LIMITED", "T1"),
                    self.owner_row("SMITH, JONES AND PARTNERS LIMITED", "T2"),
                ]
            )
        )
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "include_title_details": False},
            mock_context,
        )
        data = result.result.data
        assert data["owner_count"] == 1
        owner = data["owners"][0]
        assert owner["owner_name"] == "SMITH, JONES AND PARTNERS LIMITED"
        assert owner["property_count"] == 2

    @pytest.mark.asyncio
    async def test_min_properties_threshold(self, mock_context):
        mock_context.fetch.return_value = ok(collection([self.owner_row("SOLO OWNER", "T1")]))
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"land_district": "Otago", "min_properties": 2},
            mock_context,
        )
        assert result.result.data["owner_count"] == 0
        # No results → no enrichment request.
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_row_not_double_counted(self, mock_context):
        # The same (owner, title) row appearing twice counts once.
        mock_context.fetch.return_value = ok(
            collection(
                [
                    self.owner_row("JOHN SMITH", "T1"),
                    self.owner_row("JOHN SMITH", "T1"),
                ]
            )
        )
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "min_properties": 1, "include_title_details": False},
            mock_context,
        )
        owner = result.result.data["owners"][0]
        assert owner["property_count"] == 1

    @pytest.mark.asyncio
    async def test_request_combines_filters(self, mock_context):
        mock_context.fetch.return_value = ok(collection([]))
        await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "land_district": "Otago", "status": "LIVE"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["typeNames"] == LAYER_TITLE_OWNERS
        assert (
            params["cql_filter"] == "(owner ILIKE '%smith%') AND (land_district = 'Otago') AND (title_status = 'LIVE')"
        )

    @pytest.mark.asyncio
    async def test_title_details_enriched_from_50805(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                collection(
                    [
                        self.owner_row("JOHN SMITH", "T1", part=True),
                        self.owner_row("JOHN SMITH", "T2"),
                    ]
                )
            ),
            ok(
                collection(
                    [
                        self.detail_row("T1", estate="Fee Simple, 1/2, Lot 1 DP 1", type_="Freehold"),
                        self.detail_row("T2", estate="Leasehold, 1/1", type_="Leasehold"),
                    ]
                )
            ),
        ]
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "min_properties": 2},
            mock_context,
        )
        titles = {t["title_no"]: t for t in result.result.data["owners"][0]["titles"]}
        assert titles["T1"]["estate_description"] == "Fee Simple, 1/2, Lot 1 DP 1"
        assert titles["T1"]["part_ownership"] is True
        assert titles["T2"]["type"] == "Leasehold"
        detail_params = mock_context.fetch.call_args.kwargs["params"]
        assert detail_params["typeNames"] == LAYER_TITLES_OWNERS
        assert detail_params["cql_filter"] == "title_no IN ('T1', 'T2')"
        assert detail_params["propertyName"] == "title_no,estate_description,type"

    @pytest.mark.asyncio
    async def test_include_title_details_false_skips_enrichment(self, mock_context):
        mock_context.fetch.return_value = ok(
            collection([self.owner_row("JOHN SMITH", "T1"), self.owner_row("JOHN SMITH", "T2")])
        )
        result = await linz.execute_action(
            "find_multi_property_owners",
            {"owner_name": "smith", "include_title_details": False},
            mock_context,
        )
        assert mock_context.fetch.call_count == 1
        title = result.result.data["owners"][0]["titles"][0]
        assert title["estate_description"] is None

    @staticmethod
    def bulk_page(prefix, size=1000, **extra):
        return collection(
            [TestFindMultiPropertyOwners.owner_row("BULK OWNER", f"{prefix}{i}") for i in range(size)], **extra
        )

    BULK_INPUTS = {
        "owner_name": "bulk",
        "max_titles_scanned": 2000,
        "min_properties": 1,
        "include_title_details": False,
    }

    @pytest.mark.asyncio
    async def test_truncated_when_numeric_total_exceeds_cap(self, mock_context):
        # numberMatched is numeric and > cap: truncated without a probe request.
        mock_context.fetch.side_effect = [
            ok(self.bulk_page("A", numberMatched=2500)),
            ok(self.bulk_page("B", numberMatched=2500)),
        ]
        result = await linz.execute_action("find_multi_property_owners", self.BULK_INPUTS, mock_context)
        data = result.result.data
        assert data["titles_scanned"] == 2000
        assert data["truncated"] is True
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_exact_cap_with_numeric_total_not_truncated(self, mock_context):
        # Exactly cap matches (numberMatched == cap): nothing was omitted, so
        # a full final page must NOT be reported as truncated.
        mock_context.fetch.side_effect = [
            ok(self.bulk_page("A", numberMatched=2000)),
            ok(self.bulk_page("B", numberMatched=2000)),
        ]
        result = await linz.execute_action("find_multi_property_owners", self.BULK_INPUTS, mock_context)
        data = result.result.data
        assert data["titles_scanned"] == 2000
        assert data["truncated"] is False
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_exact_cap_unknown_total_probes_and_not_truncated(self, mock_context):
        # LDS reports totalFeatures "unknown": a probe one past the cap comes
        # back empty, proving exactly cap matches — not truncated.
        mock_context.fetch.side_effect = [
            ok(self.bulk_page("A", totalFeatures="unknown")),
            ok(self.bulk_page("B", totalFeatures="unknown")),
            ok(collection([])),
        ]
        result = await linz.execute_action("find_multi_property_owners", self.BULK_INPUTS, mock_context)
        data = result.result.data
        assert data["titles_scanned"] == 2000
        assert data["truncated"] is False
        assert mock_context.fetch.call_count == 3
        probe_params = mock_context.fetch.call_args.kwargs["params"]
        assert probe_params["count"] == 1
        assert probe_params["startIndex"] == 2000

    @pytest.mark.asyncio
    async def test_cap_plus_one_unknown_total_truncated(self, mock_context):
        # The probe past the cap returns a record: data really was omitted.
        mock_context.fetch.side_effect = [
            ok(self.bulk_page("A", totalFeatures="unknown")),
            ok(self.bulk_page("B", totalFeatures="unknown")),
            ok(collection([self.owner_row("BULK OWNER", "C0")])),
        ]
        result = await linz.execute_action("find_multi_property_owners", self.BULK_INPUTS, mock_context)
        data = result.result.data
        assert data["titles_scanned"] == 2000
        assert data["truncated"] is True
        assert mock_context.fetch.call_count == 3


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

    @pytest.mark.asyncio
    async def test_limit_above_cap_rejected_by_schema(self, mock_context):
        result = await linz.execute_action("query_layer", {"layer": "50805", "limit": 5000}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_start_index_rejected_by_schema(self, mock_context):
        result = await linz.execute_action("query_layer", {"layer": "50805", "start_index": -1}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_clamp_defends_without_schema(self, mock_context):
        # Defense-in-depth: even calling the handler directly (bypassing SDK
        # schema validation) the limit and start_index are clamped before they
        # reach WFS.
        mock_context.fetch.return_value = ok(collection([]))
        await QueryLayerAction().execute({"layer": "50805", "limit": 999999, "start_index": -5}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["count"] == MAX_QUERY_LIMIT
        assert params["startIndex"] == 0

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection reset")
        result = await linz.execute_action("query_layer", {"layer": "50772"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection reset" in result.result.message


# =============================================================================
# list_available_layers
# =============================================================================


class TestListAvailableLayers:
    OWNERSHIP_LAYERS = [
        (LAYER_TITLES_OWNERS, "NZ Property Titles Including Owners"),
        (LAYER_TITLE_OWNERS, "NZ Property Title Owners"),
        (TABLE_TITLE_OWNERS_LIST, "NZ Property Titles Owners List"),
    ]
    PUBLIC_LAYERS = [
        (LAYER_TITLES, "NZ Property Titles"),
        (LAYER_PRIMARY_PARCELS, "NZ Primary Parcels"),
    ]
    ALL_LAYERS = OWNERSHIP_LAYERS + PUBLIC_LAYERS

    @pytest.mark.asyncio
    async def test_sends_getcapabilities_request(self, mock_context):
        mock_context.fetch.return_value = ok(capabilities_xml(self.ALL_LAYERS))
        await linz.execute_action("list_available_layers", {}, mock_context)
        args, kwargs = mock_context.fetch.call_args
        assert "services;key=test_api_key/wfs" in args[0]
        params = kwargs["params"]
        assert params["request"] == "GetCapabilities"
        assert "typeNames" not in params

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(capabilities_xml(self.ALL_LAYERS))
        result = await linz.execute_action("list_available_layers", {}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["count"] == 5
        assert data["total_available"] == 5
        assert data["truncated"] is False
        assert {"id": LAYER_TITLES, "title": "NZ Property Titles"} in data["layers"]
        assert data["integration_layers"] == {
            LAYER_TITLES_OWNERS: True,
            LAYER_TITLE_OWNERS: True,
            TABLE_TITLE_OWNERS_LIST: True,
            LAYER_TITLES: True,
            LAYER_PRIMARY_PARCELS: True,
        }
        assert "all layers used by this integration" in data["note"]

    @pytest.mark.asyncio
    async def test_empty_capabilities_gives_scope_hint(self, mock_context):
        # The real failure mode this action diagnoses: a valid key whose
        # capabilities expose zero layers (no query/WFS scope).
        mock_context.fetch.return_value = ok(capabilities_xml([]))
        result = await linz.execute_action("list_available_layers", {}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["count"] == 0
        assert data["total_available"] == 0
        assert data["integration_layers"][LAYER_TITLES_OWNERS] is False
        assert "cannot see any layers" in data["note"]
        assert "data.linz.govt.nz/my/api" in data["note"]

    @pytest.mark.asyncio
    async def test_missing_ownership_layers_note_licence(self, mock_context):
        # Key can query public layers but none of the licensed ownership datasets.
        mock_context.fetch.return_value = ok(capabilities_xml(self.PUBLIC_LAYERS))
        result = await linz.execute_action("list_available_layers", {}, mock_context)
        data = result.result.data
        assert data["integration_layers"] == {
            LAYER_TITLES_OWNERS: False,
            LAYER_TITLE_OWNERS: False,
            TABLE_TITLE_OWNERS_LIST: False,
            LAYER_TITLES: True,
            LAYER_PRIMARY_PARCELS: True,
        }
        assert LAYER_TITLES_OWNERS in data["note"]
        assert "Personal Data" in data["note"]

    @pytest.mark.asyncio
    async def test_name_contains_filters_but_not_diagnostics(self, mock_context):
        mock_context.fetch.return_value = ok(capabilities_xml(self.ALL_LAYERS))
        result = await linz.execute_action("list_available_layers", {"name_contains": "parcels"}, mock_context)
        data = result.result.data
        assert [layer["id"] for layer in data["layers"]] == [LAYER_PRIMARY_PARCELS]
        assert data["count"] == 1
        # Diagnostics still reflect the full capabilities, not the filter.
        assert data["total_available"] == 5
        assert data["integration_layers"][LAYER_TITLES_OWNERS] is True

    @pytest.mark.asyncio
    async def test_limit_truncates(self, mock_context):
        mock_context.fetch.return_value = ok(capabilities_xml(self.ALL_LAYERS))
        result = await linz.execute_action("list_available_layers", {"limit": 2}, mock_context)
        data = result.result.data
        assert data["count"] == 2
        assert data["truncated"] is True
        assert data["total_available"] == 5

    @pytest.mark.asyncio
    async def test_non_xml_response_is_action_error(self, mock_context):
        mock_context.fetch.return_value = ok({"unexpected": "json"})
        result = await linz.execute_action("list_available_layers", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "unexpected" in result.result.message.lower()

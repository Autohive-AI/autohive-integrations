import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from metabase.metabase import metabase

pytestmark = pytest.mark.unit

BASE = "https://metabase.test"


def _ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# ---- Account ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                "id": 7,
                "email": "api-key-user@metabase.test",
                "common_name": "Agent key",
                "is_superuser": False,
                "group_ids": [1, 4],
                "personal_collection_id": 9,
                "login_attributes": {"secret": "x"},  # nosec B105
            }
        )
        result = await metabase.execute_action("get_current_user", {}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "id": 7,
            "email": "api-key-user@metabase.test",
            "common_name": "Agent key",
            "is_superuser": False,
            "group_ids": [1, 4],
            "personal_collection_id": 9,
        }

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 1})
        await metabase.execute_action("get_current_user", {}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/user/current"
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["headers"]["x-api-key"] == "mb_test_api_key"

    @pytest.mark.asyncio
    async def test_bad_key(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "Unauthenticated", "Unauthenticated")
        result = await metabase.execute_action("get_current_user", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 401" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_credentials(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {"base_url": BASE}})
        result = await metabase.execute_action("get_current_user", {}, ctx)
        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_base_url_rejected(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {"base_url": "http://m.test", "api_key": "k"}})
        result = await metabase.execute_action("get_current_user", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "https://" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_sub_path_instance(self, make_context):
        ctx = make_context(
            auth={"auth_type": "Custom", "credentials": {"base_url": "https://ex.com/metabase/api", "api_key": "k"}}
        )
        ctx.fetch.return_value = _ok({"id": 1})
        await metabase.execute_action("get_current_user", {}, ctx)
        assert ctx.fetch.call_args.args[0] == "https://ex.com/metabase/api/user/current"


# ---- Data model ----


class TestListDatabases:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                "data": [
                    {"id": 1, "name": "Sample", "engine": "h2", "is_sample": True, "details": {"password": "x"}},  # nosec B105
                    {"id": 3, "name": "Warehouse", "engine": "postgres", "description": "Main"},
                ],
                "total": 2,
            }
        )
        result = await metabase.execute_action("list_databases", {}, mock_context)
        data = result.result.data
        assert data["count"] == 2
        assert data["databases"][1] == {
            "id": 3,
            "name": "Warehouse",
            "engine": "postgres",
            "description": "Main",
            "is_sample": False,
        }
        assert "details" not in data["databases"][0]

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": []})
        await metabase.execute_action("list_databases", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/database"
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_plain_list_response(self, mock_context):
        mock_context.fetch.return_value = _ok([{"id": 1, "name": "Old", "engine": "mysql"}])
        result = await metabase.execute_action("list_databases", {}, mock_context)
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")
        result = await metabase.execute_action("list_databases", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message


SAMPLE_METADATA = {
    "id": 3,
    "name": "Warehouse",
    "engine": "postgres",
    "tables": [
        {
            "id": 10,
            "schema": "core",
            "name": "fct_orders",
            "display_name": "Fct Orders",
            "fields": [
                {"id": 100, "name": "id", "base_type": "type/Integer", "semantic_type": "type/PK"},
                {"id": 101, "name": "user_id", "base_type": "type/Integer", "fk_target_field_id": 200},
            ],
        },
        {"id": 11, "schema": "core", "name": "dim_users", "fields": []},
        {"id": 12, "schema": "staging", "name": "stg_orders", "fields": []},
    ],
}


class TestGetDatabaseSchema:
    @pytest.mark.asyncio
    async def test_tables_without_fields(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_METADATA)
        result = await metabase.execute_action("get_database_schema", {"database_id": 3}, mock_context)
        data = result.result.data
        assert data["count"] == 3
        assert data["database_name"] == "Warehouse"
        assert "fields" not in data["tables"][0]

    @pytest.mark.asyncio
    async def test_request_skips_fields_by_default(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_METADATA)
        await metabase.execute_action("get_database_schema", {"database_id": 3}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/database/3/metadata"
        assert call.kwargs["params"] == {"skip_fields": "true"}

    @pytest.mark.asyncio
    async def test_include_fields(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_METADATA)
        result = await metabase.execute_action(
            "get_database_schema", {"database_id": 3, "include_fields": True}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["params"] == {"skip_fields": "false"}
        fields = result.result.data["tables"][0]["fields"]
        assert fields[1]["foreign_key_target_field_id"] == 200
        assert fields[0]["semantic_type"] == "type/PK"

    @pytest.mark.asyncio
    async def test_schema_filter_case_insensitive(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_METADATA)
        result = await metabase.execute_action(
            "get_database_schema", {"database_id": 3, "schema": "STAGING"}, mock_context
        )
        assert [t["name"] for t in result.result.data["tables"]] == ["stg_orders"]

    @pytest.mark.asyncio
    async def test_name_filter(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_METADATA)
        result = await metabase.execute_action(
            "get_database_schema", {"database_id": 3, "schema": "core", "table_name_contains": "Order"}, mock_context
        )
        assert [t["id"] for t in result.result.data["tables"]] == [10]

    @pytest.mark.asyncio
    async def test_missing_database_id(self, mock_context):
        result = await metabase.execute_action("get_database_schema", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("get_database_schema", {"database_id": 99}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestGetTable:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                "id": 10,
                "db_id": 3,
                "schema": "core",
                "name": "fct_orders",
                "fields": [{"id": 101, "name": "user_id", "target": {"id": 200}}],
            }
        )
        result = await metabase.execute_action("get_table", {"table_id": 10}, mock_context)
        data = result.result.data
        assert data["database_id"] == 3
        assert data["fields"][0]["foreign_key_target_field_id"] == 200

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 10, "name": "t", "fields": []})
        await metabase.execute_action("get_table", {"table_id": 10}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/table/10/query_metadata"
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "x", {"message": "You don't have permissions to do that."})
        result = await metabase.execute_action("get_table", {"table_id": 10}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "permissions" in result.result.message


# ---- Search and collections ----


class TestSearch:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                "data": [
                    {
                        "model": "dashboard",
                        "id": 5,
                        "name": "Revenue",
                        "collection": {"id": 2, "name": "Finance", "authority_level": None},
                        "updated_at": "2026-10-01T00:00:00Z",
                    }
                ],
                "total": 16,
                "limit": 50,
                "offset": 0,
            }
        )
        result = await metabase.execute_action("search", {"query": "revenue"}, mock_context)
        data = result.result.data
        assert data["total"] == 16
        assert data["results"][0]["collection"] == {"id": 2, "name": "Finance"}
        assert data["results"][0]["archived"] is False

    @pytest.mark.asyncio
    async def test_request_repeats_models(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": [], "total": 0})
        await metabase.execute_action(
            "search", {"query": "rev", "models": ["card", "dashboard"], "limit": 5, "offset": 10}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/search?q=rev&models=card&models=dashboard&limit=5&offset=10"
        assert call.kwargs["method"] == "GET"
        assert "params" not in call.kwargs

    @pytest.mark.asyncio
    async def test_empty_query_and_archived(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": [], "total": 0})
        await metabase.execute_action("search", {"archived": True}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/search?archived=true&limit=50&offset=0"

    @pytest.mark.asyncio
    async def test_limit_clamped(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": []})
        result = await metabase.execute_action("search", {"query": "x", "limit": 200}, mock_context)
        assert "limit=200" in mock_context.fetch.call_args.args[0]
        assert result.result.data["total"] is None

    @pytest.mark.asyncio
    async def test_invalid_model_rejected(self, mock_context):
        result = await metabase.execute_action("search", {"models": ["widget"]}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")
        result = await metabase.execute_action("search", {"query": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


SAMPLE_COLLECTIONS = [
    {"id": "root", "name": "Our analytics", "is_personal": False},
    {"id": 4, "name": "Finance", "location": "/", "effective_location": "/", "parent_id": None},
    {"id": 9, "name": "Jane's Personal Collection", "is_personal": True, "personal_owner_id": 2},
]


class TestListCollections:
    @pytest.mark.asyncio
    async def test_excludes_personal_by_default(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_COLLECTIONS)
        result = await metabase.execute_action("list_collections", {}, mock_context)
        assert [c["id"] for c in result.result.data["collections"]] == ["root", 4]
        assert result.result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_include_personal(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_COLLECTIONS)
        result = await metabase.execute_action("list_collections", {"include_personal": True}, mock_context)
        assert result.result.data["count"] == 3
        assert result.result.data["collections"][2]["is_personal"] is True

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_collections", {"archived": True}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/collection"
        assert call.kwargs["params"] == {"archived": "true"}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "boom", None)
        result = await metabase.execute_action("list_collections", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListCollectionItems:
    @pytest.mark.asyncio
    async def test_root_by_default(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {"data": [{"model": "card", "id": 1, "name": "Q", "display": "bar"}], "total": 24, "limit": 50, "offset": 0}
        )
        result = await metabase.execute_action("list_collection_items", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/collection/root/items?limit=50&offset=0"
        assert result.result.data["items"][0]["display"] == "bar"
        assert result.result.data["total"] == 24

    @pytest.mark.asyncio
    async def test_models_filter(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": []})
        await metabase.execute_action(
            "list_collection_items", {"collection_id": 4, "models": ["dashboard", "card"], "limit": 2}, mock_context
        )
        assert (
            mock_context.fetch.call_args.args[0]
            == f"{BASE}/api/collection/4/items?models=dashboard&models=card&limit=2&offset=0"
        )

    @pytest.mark.asyncio
    async def test_path_id_escaped(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": []})
        await metabase.execute_action("list_collection_items", {"collection_id": "a/b"}, mock_context)
        assert "/api/collection/a%2Fb/items" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("list_collection_items", {"collection_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateCollection:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 30, "name": "Agent work", "location": "/4/"})
        result = await metabase.execute_action(
            "create_collection",
            {"name": " Agent work ", "description": "Made by Autohive", "parent_collection_id": 4},
            mock_context,
        )
        assert result.result.data == {"id": 30, "name": "Agent work", "location": "/4/"}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/collection"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"name": "Agent work", "description": "Made by Autohive", "parent_id": 4}

    @pytest.mark.asyncio
    async def test_minimal_body(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 31, "name": "X"})
        await metabase.execute_action("create_collection", {"name": "X"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "X"}

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action("create_collection", {"name": "  "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({})
        result = await metabase.execute_action("create_collection", {"name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

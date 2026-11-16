"""
Live tests for the Metabase integration.

Requires METABASE_BASE_URL (https:// only) and METABASE_API_KEY (repo-root .env is loaded by
the root conftest). Read-only tests need a key that can see at least one database; the
question/dashboard tests also need at least one saved question and dashboard to exist.
Destructive tests create a collection, questions, dashboards, segments, alerts, subscriptions and timelines,
edit them, then move them to the trash. One also edits a table and column description and puts it back.

Read-only (default):
    pytest metabase/tests/test_metabase_integration.py -m "integration and not destructive"

Opt-in writes:
    pytest metabase/tests/test_metabase_integration.py -m "integration and destructive"
"""

import base64
import os
from urllib.parse import quote, urlparse
from uuid import uuid4
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType
from metabase.metabase import _api, _read_only_sql, metabase

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("METABASE_BASE_URL", "").strip().rstrip("/")
API_KEY = os.getenv("METABASE_API_KEY", "").strip()

skip_if_no_creds = pytest.mark.skipif(
    not BASE_URL or not API_KEY,
    reason="METABASE_BASE_URL and METABASE_API_KEY required",
)


@pytest.fixture
def live_context(make_context):
    if not BASE_URL or not API_KEY:
        pytest.skip("METABASE_BASE_URL and METABASE_API_KEY required")
    parsed = urlparse(BASE_URL)
    if parsed.scheme != "https" or not parsed.netloc:
        pytest.skip(f"METABASE_BASE_URL must be https:// (got {BASE_URL!r})")

    async def real_fetch(
        url, *, method="GET", json=None, data=None, content_type=None, headers=None, params=None, timeout=None, **kwargs
    ):
        client_timeout = aiohttp.ClientTimeout(total=timeout or 30)
        # Like the SDK, a form body (export actions) is sent with its own content type.
        if content_type and "Content-Type" not in (headers or {}):
            headers = {**(headers or {}), "Content-Type": content_type}
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(method, url, json=json, data=data, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "base_url": BASE_URL,
                "api_key": API_KEY,
                "gateway_header_name": os.getenv("METABASE_GATEWAY_HEADER_NAME", ""),
                "gateway_header_value": os.getenv("METABASE_GATEWAY_HEADER_VALUE", ""),
            },
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


def _assert_ok(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    return result.result.data


async def _first_database(live_context):
    data = _assert_ok(await metabase.execute_action("list_databases", {}, live_context))
    sql_dbs = [db for db in data["databases"] if db["engine"] not in ("mongo", "druid", "druid-jdbc")]
    if not sql_dbs:
        pytest.skip("No SQL database visible to this API key")
    return sql_dbs[0]


def _select(db, columns):
    """A SELECT without a table, which Oracle before 23ai only accepts with FROM DUAL."""
    return f"select {columns}" + (" from dual" if db["engine"] == "oracle" else "")


async def _first_search_hit(live_context, model):
    data = _assert_ok(await metabase.execute_action("search", {"models": [model], "limit": 1}, live_context))
    if not data["results"]:
        pytest.skip(f"No {model} visible to this API key")
    return data["results"][0]


async def _safe_to_run(live_context, question):
    """Query-builder questions can't write; saved SQL must pass the check run_sql_query uses."""
    if question["query_type"] != "native":
        return True
    try:
        await _read_only_sql(live_context, question["database_id"], question["native_sql"])
    except ValueError:
        return False
    return True


async def _raw(live_context, method, path, body=None):
    return await _api(live_context, method, path, json=body)


async def _is_archived(live_context, path):
    """Metabase 0.49 answers a read of an archived dashboard with a 404 saying so; later versions return it."""
    try:
        return (await _raw(live_context, "GET", path))["archived"] is True
    except HTTPError as e:
        if e.status == 404 and "archived" in str(e.response_data):
            return True
        raise


def _dashcard_state(dashcard):
    """What a user sees of a dashboard card: its question, position, combo series, filter links and settings."""
    return {
        "card_id": dashcard.get("card_id"),
        "dashboard_tab_id": dashcard.get("dashboard_tab_id"),
        "position": [dashcard.get(k) for k in ("row", "col", "size_x", "size_y")],
        "series": [s["id"] for s in dashcard.get("series") or []],
        "parameter_mappings": dashcard.get("parameter_mappings"),
        "visualization_settings": dashcard.get("visualization_settings"),
    }


async def _archive(live_context, path, item_id, failures):
    if item_id is None:
        return
    try:
        await _api(
            live_context,
            "PUT",
            f"/{path}/{quote(str(item_id), safe='')}",
            json={"archived": True},
        )
    except Exception as exc:
        failures.append(f"{path} {item_id}: {exc}")


@skip_if_no_creds
class TestReadOnly:
    @pytest.mark.asyncio
    async def test_get_current_user(self, live_context):
        data = _assert_ok(await metabase.execute_action("get_current_user", {}, live_context))
        assert isinstance(data["id"], int)
        assert isinstance(data["group_ids"], list)

    @pytest.mark.asyncio
    async def test_list_databases(self, live_context):
        data = _assert_ok(await metabase.execute_action("list_databases", {}, live_context))
        assert data["count"] == len(data["databases"])

    @pytest.mark.asyncio
    async def test_schema_and_table(self, live_context):
        db = await _first_database(live_context)
        schema = _assert_ok(
            await metabase.execute_action("get_database_schema", {"database_id": db["id"]}, live_context)
        )
        assert schema["database_id"] == db["id"]
        if not schema["tables"]:
            pytest.skip("Database has no synced tables")
        table = schema["tables"][0]
        filtered = _assert_ok(
            await metabase.execute_action(
                "get_database_schema",
                {"database_id": db["id"], "schema": table["schema"] or "", "table_name_contains": table["name"]},
                live_context,
            )
        )
        assert table["id"] in [t["id"] for t in filtered["tables"]]

        detail = _assert_ok(await metabase.execute_action("get_table", {"table_id": table["id"]}, live_context))
        assert detail["id"] == table["id"]
        assert isinstance(detail["fields"], list)

    @pytest.mark.asyncio
    async def test_run_sql_query(self, live_context):
        db = await _first_database(live_context)
        data = _assert_ok(
            await metabase.execute_action(
                "run_sql_query", {"database_id": db["id"], "sql": _select(db, "1 as one"), "max_rows": 5}, live_context
            )
        )
        assert data["row_count"] == 1
        assert list(data["rows"][0].values()) == [1]

    @pytest.mark.asyncio
    async def test_run_sql_query_error(self, live_context):
        db = await _first_database(live_context)
        result = await metabase.execute_action(
            "run_sql_query",
            {"database_id": db["id"], "sql": "select * from autohive_itest_missing_table"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        # Most databases name the missing table (Snowflake in upper case); Oracle only gives its error code.
        message = result.result.message.lower()
        assert "autohive_itest_missing_table" in message or "ora-00942" in message

    @pytest.mark.asyncio
    async def test_search_paging(self, live_context):
        data = _assert_ok(await metabase.execute_action("search", {"limit": 2}, live_context))
        assert data["limit"] == 2
        assert data["count"] <= 2

    @pytest.mark.asyncio
    async def test_collections(self, live_context):
        data = _assert_ok(await metabase.execute_action("list_collections", {}, live_context))
        assert all(not c["is_personal"] for c in data["collections"])
        items = _assert_ok(await metabase.execute_action("list_collection_items", {"limit": 5}, live_context))
        assert items["count"] <= 5

    @pytest.mark.asyncio
    async def test_get_and_run_question(self, live_context):
        question = None
        seen = 0
        for offset in range(0, 200, 50):
            page = _assert_ok(
                await metabase.execute_action(
                    "search", {"models": ["card"], "limit": 50, "offset": offset}, live_context
                )
            )
            for hit in page["results"]:
                seen += 1
                candidate = _assert_ok(
                    await metabase.execute_action("get_question", {"question_id": hit["id"]}, live_context)
                )
                assert candidate["id"] == hit["id"]
                # A saved SQL question could write data, so it runs only if it passes the SQL check.
                if not candidate["parameters"] and await _safe_to_run(live_context, candidate):
                    question = candidate
                    break
            if question or len(page["results"]) < 50:
                break
        if not seen:
            pytest.skip("No card visible to this API key")
        if question is None:
            pytest.skip(f"None of the {seen} questions checked runs without parameters and passes the SQL check")
        data = _assert_ok(
            await metabase.execute_action("run_question", {"question_id": question["id"], "max_rows": 5}, live_context)
        )
        assert data["row_count"] <= 5

    @pytest.mark.asyncio
    async def test_get_dashboard(self, live_context):
        hit = await _first_search_hit(live_context, "dashboard")
        data = _assert_ok(await metabase.execute_action("get_dashboard", {"dashboard_id": hit["id"]}, live_context))
        assert data["id"] == hit["id"]
        assert isinstance(data["cards"], list)


@skip_if_no_creds
@pytest.mark.destructive
class TestBuildLifecycle:
    @pytest.mark.asyncio
    async def test_collection_question_dashboard(self, live_context):
        run_id = uuid4().hex[:8]
        collection_id = question_id = dashboard_id = None
        try:
            db = await _first_database(live_context)
            sql = _select(db, "1 as one")
            collection = _assert_ok(
                await metabase.execute_action("create_collection", {"name": f"Autohive itest {run_id}"}, live_context)
            )
            collection_id = collection["id"]

            question = _assert_ok(
                await metabase.execute_action(
                    "create_question",
                    {
                        "name": f"Autohive itest question {run_id}",
                        "database_id": db["id"],
                        "sql": sql,
                        "display": "scalar",
                        "collection_id": collection_id,
                    },
                    live_context,
                )
            )
            question_id = question["id"]
            assert question["native_sql"] == sql

            run = _assert_ok(await metabase.execute_action("run_question", {"question_id": question_id}, live_context))
            assert run["row_count"] == 1

            dashboard = _assert_ok(
                await metabase.execute_action(
                    "create_dashboard",
                    {"name": f"Autohive itest dashboard {run_id}", "collection_id": collection_id},
                    live_context,
                )
            )
            dashboard_id = dashboard["id"]

            first = _assert_ok(
                await metabase.execute_action(
                    "add_question_to_dashboard",
                    {"dashboard_id": dashboard_id, "question_id": question_id},
                    live_context,
                )
            )
            second = _assert_ok(
                await metabase.execute_action(
                    "add_question_to_dashboard",
                    {"dashboard_id": dashboard_id, "question_id": question_id, "width": 6, "height": 3},
                    live_context,
                )
            )
            assert first["row"] == 0
            assert second["row"] == first["row"] + first["size_y"]
            assert second["dashcard_id"] and second["dashcard_id"] != first["dashcard_id"]

            fetched = _assert_ok(
                await metabase.execute_action("get_dashboard", {"dashboard_id": dashboard_id}, live_context)
            )
            assert [c["card_id"] for c in fetched["cards"]] == [question_id, question_id]

            items = _assert_ok(
                await metabase.execute_action("list_collection_items", {"collection_id": collection_id}, live_context)
            )
            assert {i["model"] for i in items["items"]} == {"card", "dashboard"}
        finally:
            failures: list = []
            await _archive(live_context, "dashboard", dashboard_id, failures)
            await _archive(live_context, "card", question_id, failures)
            await _archive(live_context, "collection", collection_id, failures)
            if failures:
                raise AssertionError("Metabase integration-test cleanup failed: " + "; ".join(failures))


@skip_if_no_creds
@pytest.mark.destructive
class TestAddToExistingDashboard:
    @pytest.mark.asyncio
    async def test_existing_cards_unchanged(self, live_context):
        """Adding a question sends every existing card back; a combo chart, link card, text card and filter
        connection must all survive that round trip."""
        run_id = uuid4().hex[:8]
        collection_id = dashboard_id = None
        question_ids: list = []
        try:
            db = await _first_database(live_context)
            collection = _assert_ok(
                await metabase.execute_action("create_collection", {"name": f"Autohive itest {run_id}"}, live_context)
            )
            collection_id = collection["id"]

            # A question with a filter, so a dashboard filter can be connected to it.
            tag_id = str(uuid4())
            filtered = await _raw(
                live_context,
                "POST",
                "/card",
                {
                    "name": f"Autohive itest filtered {run_id}",
                    "type": "question",
                    "display": "line",
                    "visualization_settings": {},
                    "collection_id": collection_id,
                    "dataset_query": {
                        "database": db["id"],
                        "type": "native",
                        "native": {
                            "query": _select(db, "1 as x, {{n}} as y"),
                            "template-tags": {
                                "n": {"id": tag_id, "name": "n", "display-name": "N", "type": "number", "default": "2"}
                            },
                        },
                    },
                    "parameters": [
                        {
                            "id": tag_id,
                            "name": "N",
                            "slug": "n",
                            "type": "number/=",
                            "target": ["variable", ["template-tag", "n"]],
                            "default": "2",
                        }
                    ],
                },
            )
            question_ids.append(filtered["id"])
            for name in ("series", "added"):
                question = _assert_ok(
                    await metabase.execute_action(
                        "create_question",
                        {
                            "name": f"Autohive itest {name} {run_id}",
                            "database_id": db["id"],
                            "sql": _select(db, "1 as x, 3 as y"),
                            "display": "line",
                            "collection_id": collection_id,
                        },
                        live_context,
                    )
                )
                question_ids.append(question["id"])
            filtered_id, series_id, added_id = question_ids

            dashboard = _assert_ok(
                await metabase.execute_action(
                    "create_dashboard",
                    {"name": f"Autohive itest existing {run_id}", "collection_id": collection_id},
                    live_context,
                )
            )
            dashboard_id = dashboard["id"]
            await _raw(
                live_context,
                "PUT",
                f"/dashboard/{dashboard_id}",
                {
                    "parameters": [{"id": "itest_n", "name": "N", "slug": "n", "type": "number/="}],
                    "dashcards": [
                        {
                            "id": -1,
                            "card_id": filtered_id,
                            "row": 0,
                            "col": 0,
                            "size_x": 12,
                            "size_y": 6,
                            "series": [{"id": series_id}],
                            "parameter_mappings": [
                                {
                                    "parameter_id": "itest_n",
                                    "card_id": filtered_id,
                                    "target": ["variable", ["template-tag", "n"]],
                                }
                            ],
                            "visualization_settings": {"card.title": "Combo"},
                        },
                        {
                            "id": -2,
                            "card_id": None,
                            "row": 0,
                            "col": 12,
                            "size_x": 6,
                            "size_y": 2,
                            "series": [],
                            "parameter_mappings": [],
                            "visualization_settings": {
                                "virtual_card": {
                                    "name": None,
                                    "display": "link",
                                    "visualization_settings": {},
                                    "dataset_query": {},
                                    "archived": False,
                                },
                                "link": {"entity": {"id": series_id, "model": "card"}},
                            },
                        },
                        {
                            "id": -3,
                            "card_id": None,
                            "row": 6,
                            "col": 0,
                            "size_x": 12,
                            "size_y": 2,
                            "series": [],
                            "parameter_mappings": [],
                            "visualization_settings": {
                                "virtual_card": {
                                    "name": None,
                                    "display": "text",
                                    "visualization_settings": {},
                                    "dataset_query": {},
                                    "archived": False,
                                },
                                "text": f"Autohive itest {run_id}",
                            },
                        },
                    ],
                },
            )
            before = {
                dc["id"]: _dashcard_state(dc)
                for dc in (await _raw(live_context, "GET", f"/dashboard/{dashboard_id}"))["dashcards"]
            }
            assert len(before) == 3
            combo = next(state for state in before.values() if state["card_id"] == filtered_id)
            assert combo["series"] == [series_id]
            assert combo["parameter_mappings"]

            added = _assert_ok(
                await metabase.execute_action(
                    "add_question_to_dashboard", {"dashboard_id": dashboard_id, "question_id": added_id}, live_context
                )
            )
            assert added["row"] == 8
            assert added["card_count"] == 4

            after_cards = (await _raw(live_context, "GET", f"/dashboard/{dashboard_id}"))["dashcards"]
            after = {dc["id"]: _dashcard_state(dc) for dc in after_cards}
            assert {k: v for k, v in after.items() if k in before} == before
            assert after[added["dashcard_id"]]["card_id"] == added_id
        finally:
            failures: list = []
            await _archive(live_context, "dashboard", dashboard_id, failures)
            for question_id in question_ids:
                await _archive(live_context, "card", question_id, failures)
            await _archive(live_context, "collection", collection_id, failures)
            if failures:
                raise AssertionError("Metabase integration-test cleanup failed: " + "; ".join(failures))


@skip_if_no_creds
@pytest.mark.destructive
class TestEditDashboard:
    @pytest.mark.asyncio
    async def test_layout_tabs_filters_run_and_history(self, live_context):
        run_id = uuid4().hex[:8]
        collection_id = dashboard_id = copy_id = None
        question_ids: list = []
        try:
            db = await _first_database(live_context)
            collection_id = _assert_ok(
                await metabase.execute_action("create_collection", {"name": f"Autohive itest {run_id}"}, live_context)
            )["id"]
            for name in ("a", "b"):
                question = _assert_ok(
                    await metabase.execute_action(
                        "create_question",
                        {
                            "name": f"Autohive itest {name} {run_id}",
                            "database_id": db["id"],
                            "sql": _select(db, "1 as x"),
                            "collection_id": collection_id,
                        },
                        live_context,
                    )
                )
                question_ids.append(question["id"])
            dashboard_id = _assert_ok(
                await metabase.execute_action(
                    "create_dashboard",
                    {"name": f"Autohive itest {run_id}", "collection_id": collection_id},
                    live_context,
                )
            )["id"]
            for question_id in question_ids:
                _assert_ok(
                    await metabase.execute_action(
                        "add_question_to_dashboard",
                        {"dashboard_id": dashboard_id, "question_id": question_id},
                        live_context,
                    )
                )
            heading = _assert_ok(
                await metabase.execute_action(
                    "add_text_to_dashboard",
                    {"dashboard_id": dashboard_id, "kind": "heading", "text": "Section", "row": 0},
                    live_context,
                )
            )
            assert heading["dashcard_id"]

            updated = _assert_ok(
                await metabase.execute_action(
                    "update_dashboard",
                    {"dashboard_id": dashboard_id, "name": f"Autohive itest edited {run_id}", "width": "full"},
                    live_context,
                )
            )
            assert updated["width"] == "full"

            cards = {c["card_id"]: c for c in updated["cards"]}
            first, second = (cards[q]["dashcard_id"] for q in question_ids)
            moved = _assert_ok(
                await metabase.execute_action(
                    "update_dashboard_cards",
                    {
                        "dashboard_id": dashboard_id,
                        "cards": [{"dashcard_id": first, "col": 12, "title": "Renamed"}],
                    },
                    live_context,
                )
            )
            assert next(c for c in moved["cards"] if c["dashcard_id"] == first)["col"] == 12
            saved = await _raw(live_context, "GET", f"/dashboard/{dashboard_id}")
            first_saved = next(dc for dc in saved["dashcards"] if dc["id"] == first)
            assert first_saved["visualization_settings"]["card.title"] == "Renamed"

            tabbed = _assert_ok(
                await metabase.execute_action(
                    "update_dashboard_tabs",
                    {"dashboard_id": dashboard_id, "tabs": [{"name": "Main"}, {"name": "More"}]},
                    live_context,
                )
            )
            main, more = (t["id"] for t in tabbed["tabs"])
            assert {c["dashboard_tab_id"] for c in tabbed["cards"]} == {main}
            _assert_ok(
                await metabase.execute_action(
                    "update_dashboard_cards",
                    {"dashboard_id": dashboard_id, "cards": [{"dashcard_id": second, "tab_id": more}]},
                    live_context,
                )
            )
            refused = await metabase.execute_action(
                "update_dashboard_tabs",
                {"dashboard_id": dashboard_id, "tabs": [{"id": main, "name": "Main"}]},
                live_context,
            )
            assert refused.type == ResultType.ACTION_ERROR

            filtered = _assert_ok(
                await metabase.execute_action(
                    "update_dashboard_filters",
                    {
                        "dashboard_id": dashboard_id,
                        "filters": [{"name": "Region", "type": "string/=", "default": ["NZ"]}],
                    },
                    live_context,
                )
            )
            assert [p["slug"] for p in filtered["parameters"]] == ["region"]

            ran = _assert_ok(
                await metabase.execute_action("run_dashboard", {"dashboard_id": dashboard_id}, live_context)
            )
            assert ran["card_count"] == 2
            assert all(c.get("row_count") == 1 for c in ran["cards"]), ran["cards"]

            copy_id = _assert_ok(
                await metabase.execute_action(
                    "copy_dashboard",
                    {
                        "dashboard_id": dashboard_id,
                        "name": f"Autohive itest copy {run_id}",
                        "collection_id": collection_id,
                    },
                    live_context,
                )
            )["id"]

            history = _assert_ok(
                await metabase.execute_action(
                    "get_revision_history", {"item_type": "dashboard", "item_id": dashboard_id}, live_context
                )
            )
            assert history["count"] >= 2
            reverted = _assert_ok(
                await metabase.execute_action(
                    "revert_to_revision",
                    {
                        "item_type": "dashboard",
                        "item_id": dashboard_id,
                        "revision_id": history["revisions"][-1]["revision_id"],
                    },
                    live_context,
                )
            )
            assert reverted["new_revision_id"]
        finally:
            failures: list = []
            for item in (copy_id, dashboard_id):
                await _archive(live_context, "dashboard", item, failures)
            for question_id in question_ids:
                await _archive(live_context, "card", question_id, failures)
            await _archive(live_context, "collection", collection_id, failures)
            if failures:
                raise AssertionError("Metabase integration-test cleanup failed: " + "; ".join(failures))


@skip_if_no_creds
@pytest.mark.destructive
class TestEditQuestions:
    @pytest.mark.asyncio
    async def test_update_copy_export_and_query_builder(self, live_context):
        run_id = uuid4().hex[:8]
        collection_id = None
        question_ids: list = []
        try:
            db = await _first_database(live_context)
            collection_id = _assert_ok(
                await metabase.execute_action("create_collection", {"name": f"Autohive itest {run_id}"}, live_context)
            )["id"]
            question = _assert_ok(
                await metabase.execute_action(
                    "create_question",
                    {
                        "name": f"Autohive itest {run_id}",
                        "database_id": db["id"],
                        "sql": _select(db, "1 as x"),
                        "collection_id": collection_id,
                    },
                    live_context,
                )
            )
            question_ids.append(question["id"])

            edited = _assert_ok(
                await metabase.execute_action(
                    "update_question",
                    {
                        "question_id": question["id"],
                        "sql": _select(db, "2 as x"),
                        "display": "scalar",
                        "visualization_settings": {"card.title": "Two"},
                    },
                    live_context,
                )
            )
            assert edited["display"] == "scalar"
            assert "2" in edited["native_sql"]
            refused = await metabase.execute_action(
                "update_question", {"question_id": question["id"], "sql": "delete from x"}, live_context
            )
            assert refused.type == ResultType.ACTION_ERROR

            copy = _assert_ok(
                await metabase.execute_action(
                    "copy_question",
                    {"question_id": question["id"], "name": f"Autohive itest copy {run_id}"},
                    live_context,
                )
            )
            question_ids.append(copy["id"])
            assert copy["name"] == f"Autohive itest copy {run_id}"

            exported = _assert_ok(
                await metabase.execute_action(
                    "export_question_results", {"question_id": question["id"], "format": "csv"}, live_context
                )
            )
            excel = _assert_ok(
                await metabase.execute_action(
                    "export_question_results", {"question_id": question["id"], "format": "xlsx"}, live_context
                )
            )
            assert base64.b64decode(excel["file"]["content"])[:2] == b"PK"

            filtered = _assert_ok(
                await metabase.execute_action(
                    "create_question",
                    {
                        "name": f"Autohive itest filtered {run_id}",
                        "database_id": db["id"],
                        "sql": _select(db, "{{n}} as x"),
                        "filters": [{"name": "n", "type": "number", "default": 5}],
                        "collection_id": collection_id,
                    },
                    live_context,
                )
            )
            question_ids.append(filtered["id"])
            assert [p["slug"] for p in filtered["parameters"]] == ["n"]
            ran = _assert_ok(
                await metabase.execute_action("run_question", {"question_id": filtered["id"]}, live_context)
            )
            assert list(ran["rows"][0].values()) == [5]
            assert exported["row_count"] == 1
            assert exported["content"].splitlines()[1].strip() == "2"

            schema = _assert_ok(
                await metabase.execute_action(
                    "get_database_schema", {"database_id": db["id"], "limit": 1}, live_context
                )
            )
            if schema["tables"]:
                table_id = schema["tables"][0]["id"]
                gui = _assert_ok(
                    await metabase.execute_action(
                        "create_query_builder_question",
                        {
                            "name": f"Autohive itest gui {run_id}",
                            "database_id": db["id"],
                            "query": {"source-table": table_id, "aggregation": [["count"]]},
                            "display": "scalar",
                            "collection_id": collection_id,
                        },
                        live_context,
                    )
                )
                question_ids.append(gui["id"])
                assert gui["query_type"] == "query"
                model = _assert_ok(
                    await metabase.execute_action(
                        "create_model",
                        {
                            "name": f"Autohive itest model {run_id}",
                            "database_id": db["id"],
                            "query": {"source-table": table_id},
                            "collection_id": collection_id,
                        },
                        live_context,
                    )
                )
                question_ids.append(model["id"])
                assert model["type"] == "model"

            history = _assert_ok(
                await metabase.execute_action(
                    "get_revision_history", {"item_type": "question", "item_id": question["id"]}, live_context
                )
            )
            assert history["count"] >= 2
        finally:
            failures: list = []
            for question_id in question_ids:
                await _archive(live_context, "card", question_id, failures)
            await _archive(live_context, "collection", collection_id, failures)
            if failures:
                raise AssertionError("Metabase integration-test cleanup failed: " + "; ".join(failures))


@skip_if_no_creds
@pytest.mark.destructive
class TestOrganiseAndMonitor:
    @pytest.mark.asyncio
    async def test_move_archive_alerts_subscriptions_timelines(self, live_context):
        run_id = uuid4().hex[:8]
        collection_id = child_id = question_id = dashboard_id = alert_id = None
        subscription_id = timeline_id = None
        try:
            db = await _first_database(live_context)
            collection_id = _assert_ok(
                await metabase.execute_action("create_collection", {"name": f"Autohive itest {run_id}"}, live_context)
            )["id"]
            child_id = _assert_ok(
                await metabase.execute_action(
                    "create_collection", {"name": f"Autohive itest child {run_id}"}, live_context
                )
            )["id"]
            moved = _assert_ok(
                await metabase.execute_action(
                    "update_collection",
                    {
                        "collection_id": child_id,
                        "name": f"Autohive itest moved {run_id}",
                        "parent_collection_id": collection_id,
                    },
                    live_context,
                )
            )
            assert moved["parent_id"] == collection_id

            question_id = _assert_ok(
                await metabase.execute_action(
                    "create_question",
                    {"name": f"Autohive itest {run_id}", "database_id": db["id"], "sql": _select(db, "1 as x")},
                    live_context,
                )
            )["id"]
            dashboard_id = _assert_ok(
                await metabase.execute_action("create_dashboard", {"name": f"Autohive itest {run_id}"}, live_context)
            )["id"]
            _assert_ok(
                await metabase.execute_action(
                    "add_question_to_dashboard",
                    {"dashboard_id": dashboard_id, "question_id": question_id},
                    live_context,
                )
            )
            result = _assert_ok(
                await metabase.execute_action(
                    "move_items",
                    {
                        "items": [
                            {"item_type": "question", "id": question_id},
                            {"item_type": "dashboard", "id": dashboard_id},
                        ],
                        "collection_id": child_id,
                    },
                    live_context,
                )
            )
            assert result["moved_count"] == 2

            _assert_ok(
                await metabase.execute_action(
                    "archive_item", {"item_type": "dashboard", "item_id": dashboard_id}, live_context
                )
            )
            assert await _is_archived(live_context, f"/dashboard/{dashboard_id}")
            _assert_ok(
                await metabase.execute_action(
                    "restore_item", {"item_type": "dashboard", "item_id": dashboard_id}, live_context
                )
            )
            assert not await _is_archived(live_context, f"/dashboard/{dashboard_id}")

            me = _assert_ok(await metabase.execute_action("get_current_user", {}, live_context))
            alert = _assert_ok(
                await metabase.execute_action(
                    "create_alert",
                    {"question_id": question_id, "frequency": "daily", "hour": 9, "recipient_user_ids": [me["id"]]},
                    live_context,
                )
            )
            alert_id = alert["id"]
            listed = _assert_ok(
                await metabase.execute_action("list_alerts", {"question_id": question_id}, live_context)
            )
            assert [a["id"] for a in listed["alerts"]] == [alert_id]

            subscription = _assert_ok(
                await metabase.execute_action(
                    "create_subscription",
                    {
                        "dashboard_id": dashboard_id,
                        "frequency": "weekly",
                        "day_of_week": "fri",
                        "recipient_user_ids": [me["id"]],
                    },
                    live_context,
                )
            )
            subscription_id = subscription["id"]
            changed = _assert_ok(
                await metabase.execute_action(
                    "update_subscription",
                    {"subscription_id": subscription_id, "frequency": "daily", "hour": 7},
                    live_context,
                )
            )
            assert (changed["frequency"], changed["hour"]) == ("daily", 7)

            timeline_id = _assert_ok(
                await metabase.execute_action(
                    "create_timeline",
                    {"name": f"Autohive itest {run_id}", "collection_id": collection_id},
                    live_context,
                )
            )["id"]
            event = _assert_ok(
                await metabase.execute_action(
                    "create_timeline_event",
                    {"timeline_id": timeline_id, "name": "Release", "timestamp": "2026-11-01"},
                    live_context,
                )
            )
            renamed = _assert_ok(
                await metabase.execute_action(
                    "update_timeline_event", {"event_id": event["id"], "name": "Release 2"}, live_context
                )
            )
            assert renamed["name"] == "Release 2"
            timelines = _assert_ok(
                await metabase.execute_action("list_timelines", {"collection_id": collection_id}, live_context)
            )
            assert [t["id"] for t in timelines["timelines"]] == [timeline_id]
        finally:
            failures: list = []
            if alert_id is not None:
                archived = await metabase.execute_action(
                    "archive_item", {"item_type": "alert", "item_id": alert_id}, live_context
                )
                if archived.type != ResultType.ACTION:
                    failures.append(f"alert {alert_id}: {archived.result.message}")
            await _archive(live_context, "pulse", subscription_id, failures)
            await _archive(live_context, "timeline", timeline_id, failures)
            await _archive(live_context, "dashboard", dashboard_id, failures)
            await _archive(live_context, "card", question_id, failures)
            await _archive(live_context, "collection", child_id, failures)
            await _archive(live_context, "collection", collection_id, failures)
            if failures:
                raise AssertionError("Metabase integration-test cleanup failed: " + "; ".join(failures))


@skip_if_no_creds
@pytest.mark.destructive
class TestDataDescriptions:
    @pytest.mark.asyncio
    async def test_update_table_and_field_then_restore(self, live_context):
        db = await _first_database(live_context)
        schema = _assert_ok(
            await metabase.execute_action("get_database_schema", {"database_id": db["id"], "limit": 1}, live_context)
        )
        if not schema["tables"]:
            pytest.skip("No table visible to this API key")
        table = _assert_ok(
            await metabase.execute_action("get_table", {"table_id": schema["tables"][0]["id"]}, live_context)
        )
        field = table["fields"][0]
        # Metabase 0.49 clears a column's date conversion when a PUT leaves it out, so the restore sends it back.
        coercion = (await _raw(live_context, "GET", f"/field/{field['id']}")).get("coercion_strategy")
        run_id = uuid4().hex[:8]
        try:
            updated = _assert_ok(
                await metabase.execute_action(
                    "update_table", {"table_id": table["id"], "description": f"Autohive itest {run_id}"}, live_context
                )
            )
            assert updated["description"] == f"Autohive itest {run_id}"
            changed = _assert_ok(
                await metabase.execute_action(
                    "update_field", {"field_id": field["id"], "description": f"Autohive itest {run_id}"}, live_context
                )
            )
            assert changed["description"] == f"Autohive itest {run_id}"
        finally:
            # Put the original descriptions back (an empty one is stored as null), trying both even if one fails.
            failures: list = []
            restores = (
                (f"/table/{table['id']}", {"description": table["description"]}),
                (
                    f"/field/{field['id']}",
                    {"description": field["description"], **({"coercion_strategy": coercion} if coercion else {})},
                ),
            )
            for path, body in restores:
                try:
                    await _raw(live_context, "PUT", path, body)
                except Exception as exc:
                    failures.append(f"{path}: {exc}")
            if failures:
                raise AssertionError("Restoring descriptions failed: " + "; ".join(failures))

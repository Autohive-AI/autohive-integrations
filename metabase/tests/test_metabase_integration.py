"""
Live tests for the Metabase integration.

Requires METABASE_BASE_URL (https:// only) and METABASE_API_KEY (repo-root .env is loaded by
the root conftest). Read-only tests need a key that can see at least one database; the
question/dashboard tests also need at least one saved question and dashboard to exist.
Destructive tests create a collection, questions and dashboards, then move them to the trash.

Read-only (default):
    pytest metabase/tests/test_metabase_integration.py -m "integration and not destructive"

Opt-in writes:
    pytest metabase/tests/test_metabase_integration.py -m "integration and destructive"
"""

import os
from urllib.parse import quote, urlparse
from uuid import uuid4
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType
from metabase.metabase import get_base_url, metabase

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

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, timeout=None, **kwargs):
        client_timeout = aiohttp.ClientTimeout(total=timeout or 30)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"auth_type": "Custom", "credentials": {"base_url": BASE_URL, "api_key": API_KEY}})
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


async def _first_search_hit(live_context, model):
    data = _assert_ok(await metabase.execute_action("search", {"models": [model], "limit": 1}, live_context))
    if not data["results"]:
        pytest.skip(f"No {model} visible to this API key")
    return data["results"][0]


async def _raw(live_context, method, path, body=None):
    response = await live_context.fetch(
        f"{get_base_url(live_context)}/api{path}",
        method=method,
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json=body,
    )
    return response.data


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
        await live_context.fetch(
            f"{get_base_url(live_context)}/api/{path}/{quote(str(item_id), safe='')}",
            method="PUT",
            headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
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
                "run_sql_query", {"database_id": db["id"], "sql": "select 1 as one", "max_rows": 5}, live_context
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
        assert "autohive_itest_missing_table" in result.result.message

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
                if not candidate["parameters"]:
                    question = candidate
                    break
            if question or len(page["results"]) < 50:
                break
        if not seen:
            pytest.skip("No card visible to this API key")
        if question is None:
            pytest.skip(f"All {seen} questions checked need parameters")
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
                        "sql": "select 1 as one",
                        "display": "scalar",
                        "collection_id": collection_id,
                    },
                    live_context,
                )
            )
            question_id = question["id"]
            assert question["native_sql"] == "select 1 as one"

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
                            "query": "select 1 as x, {{n}} as y",
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
                            "sql": "select 1 as x, 3 as y",
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

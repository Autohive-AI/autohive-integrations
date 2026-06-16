"""
End-to-end integration tests for the BigQuery integration.

These tests call the real BigQuery REST API and require:
    BIGQUERY_ACCESS_TOKEN  — an OAuth2 access token with the BigQuery scope
                             (https://www.googleapis.com/auth/bigquery)
    BIGQUERY_PROJECT_ID    — a Google Cloud project ID you can query/write to

Run all read-only (safe) tests:
    pytest bigquery/tests/test_bigquery_integration.py -m "integration and not destructive"

Run destructive tests (creates/deletes real datasets + tables in your project):
    pytest bigquery/tests/test_bigquery_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys
import uuid

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

# Make the integration importable as the ``bigquery`` package from the repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from bigquery.bigquery import bigquery as bigquery_integration  # noqa: E402

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("BIGQUERY_ACCESS_TOKEN", "")
PROJECT_ID = os.environ.get("BIGQUERY_PROJECT_ID", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("BIGQUERY_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        all_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", **(headers or {})}
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=all_headers) as resp:
                if resp.status == 204 or resp.content_length == 0:
                    data = None
                else:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = await resp.text()
                # Mirror the SDK: context.fetch() raises on non-2xx and only
                # returns a FetchResponse for successful responses. Without this,
                # error paths would never surface as ActionError in these tests.
                # Match production semantics — RateLimitError for 429, HTTPError
                # for any other non-2xx status — so live tests exercise the same
                # SDK behavior the actions see in production.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(data), data)
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


@pytest.fixture
def project_id():
    if not PROJECT_ID:
        pytest.skip("BIGQUERY_PROJECT_ID not set — skipping project-scoped tests")
    return PROJECT_ID


def _action_data(result):
    """Assert a successful ACTION result and return its data payload.

    Makes ACTION_ERROR / VALIDATION_ERROR failures explicit and surfaces the
    action's error message instead of an opaque AttributeError on ``.data``.
    """
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    return result.result.data


# =============================================================================
# PROJECTS
# =============================================================================


class TestListProjects:
    async def test_returns_projects(self, live_context):
        result = await bigquery_integration.execute_action("list_projects", {"max_results": 10}, live_context)
        data = _action_data(result)
        assert "projects" in data
        assert isinstance(data["projects"], list)

    async def test_project_item_shape(self, live_context):
        result = await bigquery_integration.execute_action("list_projects", {"max_results": 5}, live_context)
        projects = _action_data(result)["projects"]
        if not projects:
            pytest.skip("No projects accessible with this token")
        assert "project_id" in projects[0]


# =============================================================================
# DATASETS (read-only)
# =============================================================================


class TestListDatasets:
    async def test_returns_datasets(self, live_context, project_id):
        result = await bigquery_integration.execute_action("list_datasets", {"project_id": project_id}, live_context)
        data = _action_data(result)
        assert "datasets" in data
        assert isinstance(data["datasets"], list)

    async def test_get_dataset_if_any(self, live_context, project_id):
        list_result = await bigquery_integration.execute_action(
            "list_datasets", {"project_id": project_id}, live_context
        )
        datasets = _action_data(list_result)["datasets"]
        if not datasets:
            pytest.skip("No datasets in project")
        ds_id = datasets[0]["dataset_id"]
        result = await bigquery_integration.execute_action(
            "get_dataset", {"project_id": project_id, "dataset_id": ds_id}, live_context
        )
        assert _action_data(result)["dataset"]["dataset_id"] == ds_id


# =============================================================================
# TABLES (read-only)
# =============================================================================


class TestTables:
    async def test_list_tables_and_get_table(self, live_context, project_id):
        list_result = await bigquery_integration.execute_action(
            "list_datasets", {"project_id": project_id}, live_context
        )
        datasets = _action_data(list_result)["datasets"]
        if not datasets:
            pytest.skip("No datasets in project")

        # find a dataset that has at least one table
        for ds in datasets:
            tables_result = await bigquery_integration.execute_action(
                "list_tables", {"project_id": project_id, "dataset_id": ds["dataset_id"]}, live_context
            )
            tables = _action_data(tables_result)["tables"]
            if tables:
                table = tables[0]
                assert "table_id" in table
                get_result = await bigquery_integration.execute_action(
                    "get_table",
                    {"project_id": project_id, "dataset_id": ds["dataset_id"], "table_id": table["table_id"]},
                    live_context,
                )
                tbl = _action_data(get_result)["table"]
                assert tbl["table_id"] == table["table_id"]
                assert "schema" in tbl
                return

        pytest.skip("No tables found in any dataset")


# =============================================================================
# QUERIES (read-only — uses public datasets, no writes)
# =============================================================================


class TestRunQuery:
    async def test_simple_select(self, live_context, project_id):
        result = await bigquery_integration.execute_action(
            "run_query",
            {"project_id": project_id, "query": "SELECT 1 AS n, 'hello' AS s", "max_results": 10},
            live_context,
        )
        data = _action_data(result)
        assert data["job_complete"] is True
        assert len(data["rows"]) == 1
        assert data["rows"][0]["n"] == "1"
        assert data["rows"][0]["s"] == "hello"

    async def test_public_dataset_query(self, live_context, project_id):
        result = await bigquery_integration.execute_action(
            "run_query",
            {
                "project_id": project_id,
                "query": (
                    "SELECT name, SUM(number) AS total "
                    "FROM `bigquery-public-data.usa_names.usa_1910_current` "
                    "WHERE state = 'CA' GROUP BY name ORDER BY total DESC LIMIT 5"
                ),
                "max_results": 5,
            },
            live_context,
        )
        data = _action_data(result)
        assert data["job_complete"] is True
        assert len(data["rows"]) <= 5

    async def test_dry_run_returns_bytes_estimate(self, live_context, project_id):
        result = await bigquery_integration.execute_action(
            "run_query",
            {
                "project_id": project_id,
                "query": "SELECT * FROM `bigquery-public-data.usa_names.usa_1910_current` WHERE state = 'CA'",
                "dry_run": True,
            },
            live_context,
        )
        data = _action_data(result)
        assert data["dry_run"] is True
        assert isinstance(data["total_bytes_processed"], int)
        assert data["total_bytes_processed"] > 0

    async def test_get_query_results_by_job_id(self, live_context, project_id):
        run_result = await bigquery_integration.execute_action(
            "run_query",
            {"project_id": project_id, "query": "SELECT 1 AS n", "max_results": 10},
            live_context,
        )
        job_id = _action_data(run_result).get("job_id")
        if not job_id:
            pytest.skip("run_query did not return a job_id")
        result = await bigquery_integration.execute_action(
            "get_query_results", {"project_id": project_id, "job_id": job_id}, live_context
        )
        assert _action_data(result)["job_complete"] is True

    async def test_bad_query_returns_action_error(self, live_context, project_id):
        result = await bigquery_integration.execute_action(
            "run_query",
            {"project_id": project_id, "query": "SELECT FROM WHERE bad syntax"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# JOBS (read-only)
# =============================================================================


class TestJobs:
    async def test_list_jobs(self, live_context, project_id):
        result = await bigquery_integration.execute_action(
            "list_jobs", {"project_id": project_id, "max_results": 10}, live_context
        )
        assert isinstance(_action_data(result)["jobs"], list)

    async def test_get_job_from_list(self, live_context, project_id):
        list_result = await bigquery_integration.execute_action(
            "list_jobs", {"project_id": project_id, "max_results": 5}, live_context
        )
        jobs = _action_data(list_result)["jobs"]
        if not jobs:
            pytest.skip("No jobs in project history")
        job_id = jobs[0]["job_id"]
        location = jobs[0].get("location")
        inputs = {"project_id": project_id, "job_id": job_id}
        if location:
            inputs["location"] = location
        result = await bigquery_integration.execute_action("get_job", inputs, live_context)
        assert _action_data(result)["job"]["job_id"] == job_id


# =============================================================================
# DESTRUCTIVE — full dataset/table lifecycle (writes to your real project)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestDatasetTableLifecycle:
    """Create a dataset + table, stream a row, then tear everything down.

    Cleans up after itself even if an assertion fails midway.
    """

    async def test_full_lifecycle(self, live_context, project_id):
        # Unique per-run suffix so concurrent runs don't collide and a stale
        # leftover from a failed run can't make the next run fail. Keep the
        # autohive_it_ prefix for easy identification of test artifacts.
        suffix = uuid.uuid4().hex[:8]
        dataset_id = f"autohive_it_dataset_{suffix}"
        table_id = f"autohive_it_table_{suffix}"

        created = False
        try:
            # create dataset
            create_ds = await bigquery_integration.execute_action(
                "create_dataset",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "location": "US",
                    "description": "Autohive integration test — safe to delete",
                },
                live_context,
            )
            created = True
            assert _action_data(create_ds)["dataset"]["dataset_id"] == dataset_id

            # get dataset
            get_ds = await bigquery_integration.execute_action(
                "get_dataset", {"project_id": project_id, "dataset_id": dataset_id}, live_context
            )
            assert _action_data(get_ds)["dataset"]["dataset_id"] == dataset_id

            # create table
            create_tbl = await bigquery_integration.execute_action(
                "create_table",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                            {"name": "name", "type": "STRING", "mode": "NULLABLE"},
                        ]
                    },
                },
                live_context,
            )
            assert _action_data(create_tbl)["table"]["table_id"] == table_id

            # insert rows
            insert = await bigquery_integration.execute_action(
                "insert_rows",
                {
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "rows": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}],
                },
                live_context,
            )
            insert_data = _action_data(insert)
            assert insert_data["inserted_count"] == 2
            assert insert_data["insert_errors"] == []

            # delete table
            del_tbl = await bigquery_integration.execute_action(
                "delete_table",
                {"project_id": project_id, "dataset_id": dataset_id, "table_id": table_id},
                live_context,
            )
            assert _action_data(del_tbl)["deleted"] is True
        finally:
            # always tear down the dataset (delete_contents handles any leftover
            # table). Best-effort: never let cleanup mask the real test failure.
            if created:
                try:
                    await bigquery_integration.execute_action(
                        "delete_dataset",
                        {"project_id": project_id, "dataset_id": dataset_id, "delete_contents": True},
                        live_context,
                    )
                except Exception as exc:  # pragma: no cover - cleanup best-effort
                    print(f"WARNING: failed to clean up dataset {dataset_id}: {exc}")

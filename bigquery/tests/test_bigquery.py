"""
BigQuery Integration Tests

To run these tests:
1. Set up OAuth2 credentials with BigQuery scope
2. Update TEST_PROJECT_ID with your Google Cloud project ID
3. Run: python -m pytest tests/test_bigquery.py -v
   or: python tests/test_bigquery.py
"""

import asyncio
from context import *
from bigquery import bigquery
from autohive_integrations_sdk import ExecutionContext

# Test configuration - update these values
TEST_PROJECT_ID = "your-project-id"
TEST_ACCESS_TOKEN = "your-oauth-access-token"


def get_test_context():
    """Create a test execution context with OAuth credentials."""
    return ExecutionContext(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {
                "access_token": TEST_ACCESS_TOKEN
            }
        }
    )


# ---- Project Tests ----

async def test_list_projects():
    """Test listing all accessible projects."""
    print("\n=== Testing list_projects ===")
    async with get_test_context() as context:
        result = await bigquery.execute_action(
            "list_projects",
            {"max_results": 10},
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Projects found: {len(result.get('projects', []))}")
        for proj in result.get("projects", [])[:5]:
            print(f"  - {proj.get('project_id')}: {proj.get('friendly_name')}")
        assert result.get("result") == True
        return result


# ---- Dataset Tests ----

async def test_list_datasets():
    """Test listing datasets in a project."""
    print("\n=== Testing list_datasets ===")
    async with get_test_context() as context:
        result = await bigquery.execute_action(
            "list_datasets",
            {"project_id": TEST_PROJECT_ID},
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Datasets found: {len(result.get('datasets', []))}")
        for ds in result.get("datasets", [])[:5]:
            print(f"  - {ds.get('dataset_id')} ({ds.get('location')})")
        assert result.get("result") == True
        return result


async def test_create_and_delete_dataset():
    """Test creating and deleting a dataset."""
    print("\n=== Testing create_dataset ===")
    test_dataset_id = "test_integration_dataset"

    async with get_test_context() as context:
        # Create dataset
        result = await bigquery.execute_action(
            "create_dataset",
            {
                "project_id": TEST_PROJECT_ID,
                "dataset_id": test_dataset_id,
                "location": "US",
                "description": "Test dataset created by integration tests"
            },
            context
        )
        print(f"Create result: {result.get('result')}")
        if result.get("result"):
            print(f"Created dataset: {result.get('dataset', {}).get('dataset_id')}")

        # Get dataset details
        if result.get("result"):
            print("\n=== Testing get_dataset ===")
            get_result = await bigquery.execute_action(
                "get_dataset",
                {
                    "project_id": TEST_PROJECT_ID,
                    "dataset_id": test_dataset_id
                },
                context
            )
            print(f"Get result: {get_result.get('result')}")
            print(f"Location: {get_result.get('dataset', {}).get('location')}")

        # Delete dataset
        print("\n=== Testing delete_dataset ===")
        delete_result = await bigquery.execute_action(
            "delete_dataset",
            {
                "project_id": TEST_PROJECT_ID,
                "dataset_id": test_dataset_id
            },
            context
        )
        print(f"Delete result: {delete_result.get('result')}")
        print(f"Deleted: {delete_result.get('deleted')}")

        return result


# ---- Table Tests ----

async def test_list_tables():
    """Test listing tables in a dataset."""
    print("\n=== Testing list_tables ===")
    async with get_test_context() as context:
        # First get a dataset
        datasets_result = await bigquery.execute_action(
            "list_datasets",
            {"project_id": TEST_PROJECT_ID},
            context
        )

        if datasets_result.get("datasets"):
            dataset_id = datasets_result["datasets"][0]["dataset_id"]
            result = await bigquery.execute_action(
                "list_tables",
                {
                    "project_id": TEST_PROJECT_ID,
                    "dataset_id": dataset_id
                },
                context
            )
            print(f"Result: {result.get('result')}")
            print(f"Tables in {dataset_id}: {len(result.get('tables', []))}")
            for tbl in result.get("tables", [])[:5]:
                print(f"  - {tbl.get('table_id')} ({tbl.get('type')})")
            assert result.get("result") == True
            return result
        else:
            print("No datasets found to test tables")
            return {"result": True, "tables": []}


async def test_get_table():
    """Test getting table details."""
    print("\n=== Testing get_table ===")
    async with get_test_context() as context:
        # First find a table
        datasets_result = await bigquery.execute_action(
            "list_datasets",
            {"project_id": TEST_PROJECT_ID},
            context
        )

        for ds in datasets_result.get("datasets", []):
            tables_result = await bigquery.execute_action(
                "list_tables",
                {
                    "project_id": TEST_PROJECT_ID,
                    "dataset_id": ds["dataset_id"]
                },
                context
            )

            if tables_result.get("tables"):
                table = tables_result["tables"][0]
                result = await bigquery.execute_action(
                    "get_table",
                    {
                        "project_id": TEST_PROJECT_ID,
                        "dataset_id": ds["dataset_id"],
                        "table_id": table["table_id"]
                    },
                    context
                )
                print(f"Result: {result.get('result')}")
                tbl = result.get("table", {})
                print(f"Table: {tbl.get('table_id')}")
                print(f"Rows: {tbl.get('num_rows')}")
                print(f"Size: {tbl.get('num_bytes')} bytes")
                print(f"Schema fields: {len(tbl.get('schema', {}).get('fields', []))}")
                return result

        print("No tables found to test")
        return {"result": True, "table": {}}


# ---- Query Tests ----

async def test_run_query():
    """Test running a SQL query."""
    print("\n=== Testing run_query ===")
    async with get_test_context() as context:
        # Simple query against public dataset
        result = await bigquery.execute_action(
            "run_query",
            {
                "project_id": TEST_PROJECT_ID,
                "query": "SELECT 1 as test_value, 'hello' as test_string",
                "max_results": 10
            },
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Job complete: {result.get('job_complete')}")
        print(f"Rows returned: {len(result.get('rows', []))}")
        print(f"Bytes processed: {result.get('total_bytes_processed')}")
        print(f"Cache hit: {result.get('cache_hit')}")
        if result.get("rows"):
            print(f"First row: {result['rows'][0]}")
        assert result.get("result") == True
        return result


async def test_run_query_public_dataset():
    """Test running a query against a public BigQuery dataset."""
    print("\n=== Testing run_query (public dataset) ===")
    async with get_test_context() as context:
        result = await bigquery.execute_action(
            "run_query",
            {
                "project_id": TEST_PROJECT_ID,
                "query": """
                    SELECT name, gender, SUM(number) as total
                    FROM `bigquery-public-data.usa_names.usa_1910_current`
                    WHERE state = 'CA'
                    GROUP BY name, gender
                    ORDER BY total DESC
                    LIMIT 10
                """,
                "max_results": 10
            },
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Bytes processed: {result.get('total_bytes_processed')}")
        if result.get("rows"):
            print("Top 10 names in California:")
            for row in result["rows"]:
                print(f"  {row.get('name')} ({row.get('gender')}): {row.get('total')}")
        return result


async def test_dry_run_query():
    """Test dry run query to estimate bytes processed."""
    print("\n=== Testing run_query (dry run) ===")
    async with get_test_context() as context:
        result = await bigquery.execute_action(
            "run_query",
            {
                "project_id": TEST_PROJECT_ID,
                "query": """
                    SELECT *
                    FROM `bigquery-public-data.usa_names.usa_1910_current`
                    WHERE state = 'CA'
                """,
                "dry_run": True
            },
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Dry run: {result.get('dry_run')}")
        bytes_processed = result.get("total_bytes_processed", 0)
        print(f"Estimated bytes to process: {bytes_processed:,}")
        print(f"Estimated MB to process: {bytes_processed / (1024*1024):.2f}")
        return result


# ---- Job Tests ----

async def test_list_jobs():
    """Test listing recent jobs."""
    print("\n=== Testing list_jobs ===")
    async with get_test_context() as context:
        result = await bigquery.execute_action(
            "list_jobs",
            {
                "project_id": TEST_PROJECT_ID,
                "max_results": 10
            },
            context
        )
        print(f"Result: {result.get('result')}")
        print(f"Jobs found: {len(result.get('jobs', []))}")
        for job in result.get("jobs", [])[:5]:
            print(f"  - {job.get('job_id')}: {job.get('state')}")
        assert result.get("result") == True
        return result


# ---- Run All Tests ----

async def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("BigQuery Integration Tests")
    print("=" * 60)

    tests = [
        ("List Projects", test_list_projects),
        ("List Datasets", test_list_datasets),
        ("List Tables", test_list_tables),
        ("Get Table", test_get_table),
        ("Run Query", test_run_query),
        ("Run Query (Public Dataset)", test_run_query_public_dataset),
        ("Dry Run Query", test_dry_run_query),
        ("List Jobs", test_list_jobs),
        # ("Create/Delete Dataset", test_create_and_delete_dataset),  # Uncomment to test writes
    ]

    results = []
    for name, test_func in tests:
        try:
            await test_func()
            results.append((name, "PASSED"))
        except Exception as e:
            results.append((name, f"FAILED: {e}"))
            print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, status in results:
        emoji = "PASS" if status == "PASSED" else "FAIL"
        print(f"[{emoji}] {name}: {status}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())

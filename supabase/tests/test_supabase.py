# Test suite for Supabase integration
import asyncio
from context import supabase
from autohive_integrations_sdk import ExecutionContext


# Test credentials - replace with your actual values
TEST_AUTH = {
    "auth_type": "custom",
    "credentials": {
        "host": "https://your-project.supabase.co",
        "service_role_secret": "your_service_role_key_here"
    }
}


# ---- Database Tests ----

async def test_select_records():
    """Test selecting records from a table."""
    inputs = {"table": "your_table_name", "limit": 10}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("select_records", inputs, context)
            print(f"Select Records Result: {result}")
            assert result.data.get('result') == True
            assert 'records' in result.data
            return result
        except Exception as e:
            print(f"Error testing select_records: {e}")
            return None


async def test_select_records_with_filters():
    """Test selecting records with filters."""
    inputs = {
        "table": "your_table_name",
        "filters": {"status": "eq.active"},
        "order": "created_at.desc",
        "limit": 5
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("select_records", inputs, context)
            print(f"Select Records with Filters Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing select_records with filters: {e}")
            return None


async def test_insert_records():
    """Test inserting records."""
    inputs = {
        "table": "your_table_name",
        "records": [{"name": "Test Record", "status": "active"}]
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("insert_records", inputs, context)
            print(f"Insert Records Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing insert_records: {e}")
            return None


async def test_update_records():
    """Test updating records."""
    inputs = {
        "table": "your_table_name",
        "data": {"status": "updated"},
        "filters": {"id": "eq.1"}
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("update_records", inputs, context)
            print(f"Update Records Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing update_records: {e}")
            return None


async def test_delete_records():
    """Test deleting records."""
    inputs = {
        "table": "your_table_name",
        "filters": {"id": "eq.999"},
        "return_records": True
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("delete_records", inputs, context)
            print(f"Delete Records Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_records: {e}")
            return None


async def test_call_function():
    """Test calling a database function."""
    inputs = {
        "function_name": "your_function_name",
        "params": {"param1": "value1"}
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("call_function", inputs, context)
            print(f"Call Function Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing call_function: {e}")
            return None


# ---- Storage Tests ----

async def test_list_buckets():
    """Test listing storage buckets."""
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("list_buckets", {}, context)
            print(f"List Buckets Result: {result}")
            assert result.data.get('result') == True
            assert 'buckets' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_buckets: {e}")
            return None


async def test_get_bucket():
    """Test getting a bucket."""
    inputs = {"bucket_id": "your_bucket_id"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("get_bucket", inputs, context)
            print(f"Get Bucket Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing get_bucket: {e}")
            return None


async def test_create_bucket():
    """Test creating a bucket."""
    inputs = {"name": "test-bucket", "public": False}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("create_bucket", inputs, context)
            print(f"Create Bucket Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing create_bucket: {e}")
            return None


async def test_delete_bucket():
    """Test deleting a bucket."""
    inputs = {"bucket_id": "test-bucket"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("delete_bucket", inputs, context)
            print(f"Delete Bucket Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_bucket: {e}")
            return None


async def test_list_files():
    """Test listing files in a bucket."""
    inputs = {"bucket_id": "your_bucket_id", "limit": 10}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("list_files", inputs, context)
            print(f"List Files Result: {result}")
            assert result.data.get('result') == True
            assert 'files' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_files: {e}")
            return None


async def test_delete_files():
    """Test deleting files."""
    inputs = {"bucket_id": "your_bucket_id", "paths": ["test/file.txt"]}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("delete_files", inputs, context)
            print(f"Delete Files Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_files: {e}")
            return None


async def test_get_public_url():
    """Test getting a public URL."""
    inputs = {"bucket_id": "your_bucket_id", "path": "public/file.txt"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("get_public_url", inputs, context)
            print(f"Get Public URL Result: {result}")
            assert result.data.get('result') == True
            assert 'public_url' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_public_url: {e}")
            return None


# ---- Auth Tests ----

async def test_list_users():
    """Test listing users."""
    inputs = {"per_page": 10}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("list_users", inputs, context)
            print(f"List Users Result: {result}")
            assert result.data.get('result') == True
            assert 'users' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_users: {e}")
            return None


async def test_get_user():
    """Test getting a user."""
    inputs = {"user_id": "your_user_uuid"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("get_user", inputs, context)
            print(f"Get User Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


async def test_delete_user():
    """Test deleting a user."""
    inputs = {"user_id": "user_uuid_to_delete"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await supabase.execute_action("delete_user", inputs, context)
            print(f"Delete User Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_user: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Supabase Integration Test Suite")
    print("=" * 60)

    test_functions = [
        # Database
        ("Select Records", test_select_records),
        ("Select Records with Filters", test_select_records_with_filters),
        ("Insert Records", test_insert_records),
        ("Update Records", test_update_records),
        ("Delete Records", test_delete_records),
        ("Call Function", test_call_function),
        # Storage
        ("List Buckets", test_list_buckets),
        ("Get Bucket", test_get_bucket),
        ("Create Bucket", test_create_bucket),
        ("Delete Bucket", test_delete_bucket),
        ("List Files", test_list_files),
        ("Delete Files", test_delete_files),
        ("Get Public URL", test_get_public_url),
        # Auth
        ("List Users", test_list_users),
        ("Get User", test_get_user),
        ("Delete User", test_delete_user),
    ]

    results = []
    for test_name, test_func in test_functions:
        print(f"\n{'-' * 60}")
        print(f"Running: {test_name}")
        print(f"{'-' * 60}")
        result = await test_func()
        results.append((test_name, result is not None))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

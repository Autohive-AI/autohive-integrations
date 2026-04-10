# Test suite for Google Tasks integration
import asyncio
from context import google_tasks
from autohive_integrations_sdk import ExecutionContext

# Test configuration
# Note: For real testing, replace with actual OAuth tokens or use mock responses
TEST_AUTH = {
    "access_token": "test_token_here"
}

# Store created resource IDs for cleanup
created_task_ids = []
test_tasklist_id = None


async def test_list_tasklists():
    """Test listing all task lists."""
    print("\n[TEST] Listing task lists...")

    inputs = {
        "maxResults": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("list_tasklists", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "tasklists" in result, "Should return tasklists array"

            if result["tasklists"]:
                global test_tasklist_id
                test_tasklist_id = result["tasklists"][0]["id"]
                print(f"✓ Found {len(result['tasklists'])} task list(s)")
                print(f"  Using task list: {test_tasklist_id}")
            else:
                print("⚠ No task lists found (create one in Google Tasks first)")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_tasklist():
    """Test getting a specific task list."""
    if not test_tasklist_id:
        print("\n[TEST] Skipping get_tasklist - no task list ID available")
        return None

    print(f"\n[TEST] Getting task list {test_tasklist_id}...")

    inputs = {
        "tasklist": test_tasklist_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("get_tasklist", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "tasklist" in result, "Should return tasklist object"
            assert result["tasklist"]["id"] == test_tasklist_id, "Should return correct task list"

            print(f"✓ Retrieved task list: {result['tasklist'].get('title', 'Untitled')}")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_task():
    """Test creating a new task."""
    if not test_tasklist_id:
        print("\n[TEST] Skipping create_task - no task list ID available")
        return None

    print(f"\n[TEST] Creating a new task...")

    inputs = {
        "tasklist": test_tasklist_id,
        "title": "Test Task from Autohive",
        "notes": "This is a test task created by the integration test suite",
        "status": "needsAction"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("create_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"
            assert result["task"]["title"] == inputs["title"], "Task title should match"

            task_id = result["task"]["id"]
            created_task_ids.append(task_id)

            print(f"✓ Created task: {result['task']['title']} (ID: {task_id})")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_task_with_due_date():
    """Test creating a task with a due date."""
    if not test_tasklist_id:
        print("\n[TEST] Skipping create_task_with_due_date - no task list ID available")
        return None

    print(f"\n[TEST] Creating a task with due date...")

    inputs = {
        "tasklist": test_tasklist_id,
        "title": "Task with Due Date",
        "notes": "This task has a due date",
        "due": "2025-12-31T00:00:00.000Z",
        "status": "needsAction"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("create_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"
            assert "due" in result["task"], "Task should have due date"

            task_id = result["task"]["id"]
            created_task_ids.append(task_id)

            print(f"✓ Created task with due date: {result['task']['title']}")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_tasks():
    """Test listing all tasks in a task list."""
    if not test_tasklist_id:
        print("\n[TEST] Skipping list_tasks - no task list ID available")
        return None

    print(f"\n[TEST] Listing tasks...")

    inputs = {
        "tasklist": test_tasklist_id,
        "maxResults": 20,
        "showCompleted": True
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("list_tasks", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "tasks" in result, "Should return tasks array"

            print(f"✓ Found {len(result['tasks'])} task(s)")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_task():
    """Test getting a specific task."""
    if not test_tasklist_id or not created_task_ids:
        print("\n[TEST] Skipping get_task - no task available")
        return None

    task_id = created_task_ids[0]
    print(f"\n[TEST] Getting task {task_id}...")

    inputs = {
        "tasklist": test_tasklist_id,
        "task": task_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("get_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"
            assert result["task"]["id"] == task_id, "Should return correct task"

            print(f"✓ Retrieved task: {result['task']['title']}")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_update_task():
    """Test updating an existing task."""
    if not test_tasklist_id or not created_task_ids:
        print("\n[TEST] Skipping update_task - no task available")
        return None

    task_id = created_task_ids[0]
    print(f"\n[TEST] Updating task {task_id}...")

    inputs = {
        "tasklist": test_tasklist_id,
        "task": task_id,
        "title": "Updated Test Task",
        "notes": "This task has been updated by the test suite",
        "status": "completed"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("update_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"
            assert result["task"]["title"] == inputs["title"], "Task title should be updated"
            assert result["task"]["status"] == "completed", "Task status should be updated"

            print(f"✓ Updated task: {result['task']['title']} (Status: {result['task']['status']})")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_subtask():
    """Test creating a subtask under a parent task."""
    if not test_tasklist_id or not created_task_ids:
        print("\n[TEST] Skipping create_subtask - no parent task available")
        return None

    parent_task_id = created_task_ids[0]
    print(f"\n[TEST] Creating subtask under {parent_task_id}...")

    inputs = {
        "tasklist": test_tasklist_id,
        "title": "Subtask of Test Task",
        "parent": parent_task_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("create_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"
            assert result["task"]["parent"] == parent_task_id, "Task should have correct parent"

            task_id = result["task"]["id"]
            created_task_ids.append(task_id)

            print(f"✓ Created subtask: {result['task']['title']}")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_move_task():
    """Test moving a task to a different position."""
    if not test_tasklist_id or len(created_task_ids) < 2:
        print("\n[TEST] Skipping move_task - need at least 2 tasks")
        return None

    task_id = created_task_ids[1]
    print(f"\n[TEST] Moving task {task_id}...")

    inputs = {
        "tasklist": test_tasklist_id,
        "task": task_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("move_task", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "task" in result, "Should return task object"

            print(f"✓ Moved task: {result['task']['title']}")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_delete_task():
    """Test deleting a task."""
    if not test_tasklist_id or not created_task_ids:
        print("\n[TEST] Skipping delete_task - no task available")
        return None

    task_id = created_task_ids.pop()  # Remove from list as we delete
    print(f"\n[TEST] Deleting task {task_id}...")

    inputs = {
        "tasklist": test_tasklist_id,
        "task": task_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await google_tasks.execute_action("delete_task", inputs, context)

            assert result["result"] is True, "Action should succeed"

            print(f"✓ Deleted task successfully")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def cleanup_tasks():
    """Clean up any remaining test tasks."""
    if not test_tasklist_id or not created_task_ids:
        return

    print(f"\n[CLEANUP] Deleting {len(created_task_ids)} remaining test task(s)...")

    async with ExecutionContext(auth=TEST_AUTH) as context:
        for task_id in created_task_ids:
            try:
                inputs = {
                    "tasklist": test_tasklist_id,
                    "task": task_id
                }
                await google_tasks.execute_action("delete_task", inputs, context)
                print(f"  ✓ Deleted task {task_id}")
            except Exception as e:
                print(f"  ✗ Failed to delete task {task_id}: {e}")


async def main():
    print("=" * 60)
    print("Google Tasks Integration Test Suite")
    print("=" * 60)
    print("\nNote: These tests require valid OAuth credentials.")
    print("Update TEST_AUTH with a real access token to run live tests.")
    print("=" * 60)

    try:
        # Test task list operations
        await test_list_tasklists()
        await test_get_tasklist()

        # Test task operations
        await test_create_task()
        await test_create_task_with_due_date()
        await test_list_tasks()
        await test_get_task()
        await test_update_task()

        # Test advanced operations
        await test_create_subtask()
        await test_move_task()
        await test_delete_task()

        # Clean up
        await cleanup_tasks()

        print("\n" + "=" * 60)
        print("Test suite completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test suite failed: {e}")
        # Attempt cleanup even if tests fail
        await cleanup_tasks()


if __name__ == "__main__":
    asyncio.run(main())

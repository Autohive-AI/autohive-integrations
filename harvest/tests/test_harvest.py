"""
Test suite for Harvest Integration

This file provides test cases for all 10 Harvest integration actions.
Note: These tests require valid Harvest OAuth credentials to run.
"""

import asyncio
from context import harvest
from autohive_integrations_sdk import ExecutionContext


async def test_create_time_entry():
    """Test creating a time entry in Harvest"""
    print("\n--- Testing create_time_entry ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "project_id": 12345,  # Replace with actual project ID
        "task_id": 67890,     # Replace with actual task ID
        "spent_date": "2025-01-21",
        "hours": 2.5,
        "notes": "Test time entry from integration test"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("create_time_entry", inputs, context)
            if result.get("success"):
                entry = result.get("time_entry", {})
                print(f"✓ Successfully created time entry (ID: {entry.get('id')})")
                print(f"  Hours: {entry.get('hours')}")
                print(f"  Notes: {entry.get('notes')}")
                return entry.get('id')  # Return ID for other tests
            else:
                print(f"✗ Error: {result.get('error')}")
                return None
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            return None


async def test_stop_time_entry():
    """Test stopping a running time entry"""
    print("\n--- Testing stop_time_entry ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    # First create a running timer
    create_inputs = {
        "project_id": 12345,
        "task_id": 67890,
        "spent_date": "2025-01-21",
        "is_running": True,
        "notes": "Running timer test"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create running timer
            create_result = await harvest.execute_action("create_time_entry", create_inputs, context)
            if not create_result.get("success"):
                print(f"✗ Failed to create running timer: {create_result.get('error')}")
                return

            time_entry_id = create_result.get("time_entry", {}).get("id")
            print(f"  Created running timer (ID: {time_entry_id})")

            # Stop the timer
            stop_inputs = {"time_entry_id": time_entry_id}
            result = await harvest.execute_action("stop_time_entry", stop_inputs, context)

            if result.get("success"):
                entry = result.get("time_entry", {})
                print(f"✓ Successfully stopped time entry")
                print(f"  Final hours: {entry.get('hours')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_list_time_entries():
    """Test listing time entries from Harvest"""
    print("\n--- Testing list_time_entries ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "per_page": 10,
        "is_running": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("list_time_entries", inputs, context)
            if result.get("success"):
                entries = result.get('time_entries', [])
                print(f"✓ Successfully retrieved {len(entries)} time entries")
                print(f"  Total entries: {result.get('total_entries')}")
                print(f"  Current page: {result.get('page')}/{result.get('total_pages')}")
                for entry in entries[:3]:  # Show first 3
                    print(f"  - {entry.get('notes', 'No notes')} ({entry.get('hours')}h) - {entry.get('spent_date')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_update_time_entry():
    """Test updating an existing time entry"""
    print("\n--- Testing update_time_entry ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    # First create a time entry
    create_inputs = {
        "project_id": 12345,
        "task_id": 67890,
        "spent_date": "2025-01-21",
        "hours": 1.0,
        "notes": "Original notes"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create entry
            create_result = await harvest.execute_action("create_time_entry", create_inputs, context)
            if not create_result.get("success"):
                print(f"✗ Failed to create time entry: {create_result.get('error')}")
                return

            time_entry_id = create_result.get("time_entry", {}).get("id")
            print(f"  Created time entry (ID: {time_entry_id})")

            # Update the entry
            update_inputs = {
                "time_entry_id": time_entry_id,
                "hours": 2.5,
                "notes": "Updated notes from test"
            }
            result = await harvest.execute_action("update_time_entry", update_inputs, context)

            if result.get("success"):
                entry = result.get("time_entry", {})
                print(f"✓ Successfully updated time entry")
                print(f"  New hours: {entry.get('hours')}")
                print(f"  New notes: {entry.get('notes')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_delete_time_entry():
    """Test deleting a time entry"""
    print("\n--- Testing delete_time_entry ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    # First create a time entry to delete
    create_inputs = {
        "project_id": 12345,
        "task_id": 67890,
        "spent_date": "2025-01-21",
        "hours": 0.5,
        "notes": "Entry to be deleted"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create entry
            create_result = await harvest.execute_action("create_time_entry", create_inputs, context)
            if not create_result.get("success"):
                print(f"✗ Failed to create time entry: {create_result.get('error')}")
                return

            time_entry_id = create_result.get("time_entry", {}).get("id")
            print(f"  Created time entry (ID: {time_entry_id})")

            # Delete the entry
            delete_inputs = {"time_entry_id": time_entry_id}
            result = await harvest.execute_action("delete_time_entry", delete_inputs, context)

            if result.get("success"):
                print(f"✓ Successfully deleted time entry")
                print(f"  {result.get('message')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_list_projects():
    """Test listing projects from Harvest"""
    print("\n--- Testing list_projects ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "is_active": True,
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("list_projects", inputs, context)
            if result.get("success"):
                projects = result.get('projects', [])
                print(f"✓ Successfully retrieved {len(projects)} projects")
                print(f"  Total projects: {result.get('total_entries')}")
                for project in projects[:3]:  # Show first 3
                    client = project.get('client', {})
                    print(f"  - {project.get('name')} (ID: {project.get('id')}) - Client: {client.get('name', 'N/A')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_get_project():
    """Test getting a specific project by ID"""
    print("\n--- Testing get_project ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "project_id": 12345  # Replace with actual project ID
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("get_project", inputs, context)
            if result.get("success"):
                project = result.get('project', {})
                print(f"✓ Successfully retrieved project details")
                print(f"  Name: {project.get('name')}")
                print(f"  Code: {project.get('code')}")
                print(f"  Is active: {project.get('is_active')}")
                print(f"  Billable: {project.get('is_billable')}")
                print(f"  Budget: {project.get('budget')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_list_clients():
    """Test listing clients from Harvest"""
    print("\n--- Testing list_clients ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "is_active": True,
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("list_clients", inputs, context)
            if result.get("success"):
                clients = result.get('clients', [])
                print(f"✓ Successfully retrieved {len(clients)} clients")
                print(f"  Total clients: {result.get('total_entries')}")
                for client in clients[:3]:  # Show first 3
                    print(f"  - {client.get('name')} (ID: {client.get('id')})")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_list_tasks():
    """Test listing tasks from Harvest"""
    print("\n--- Testing list_tasks ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "is_active": True,
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("list_tasks", inputs, context)
            if result.get("success"):
                tasks = result.get('tasks', [])
                print(f"✓ Successfully retrieved {len(tasks)} tasks")
                print(f"  Total tasks: {result.get('total_entries')}")
                for task in tasks[:3]:  # Show first 3
                    print(f"  - {task.get('name')} (ID: {task.get('id')}) - Billable: {task.get('billable_by_default')}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def test_list_users():
    """Test listing users (team members) from Harvest"""
    print("\n--- Testing list_users ---")

    auth = {
        "access_token": "your_harvest_access_token_here",
        "account_id": "your_harvest_account_id_here"
    }

    inputs = {
        "is_active": True,
        "per_page": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await harvest.execute_action("list_users", inputs, context)
            if result.get("success"):
                users = result.get('users', [])
                print(f"✓ Successfully retrieved {len(users)} users")
                print(f"  Total users: {result.get('total_entries')}")
                for user in users[:3]:  # Show first 3
                    print(f"  - {user.get('first_name')} {user.get('last_name')} ({user.get('email')})")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")


async def main():
    """Run all test cases for all 10 Harvest actions"""
    print("=" * 60)
    print("Harvest Integration Test Suite - All 10 Actions")
    print("=" * 60)
    print("\nNote: Update the auth credentials before running tests!")
    print("Replace 'your_harvest_access_token_here' with actual OAuth token")
    print("Replace 'your_harvest_account_id_here' with actual account ID")
    print("Replace project_id and task_id with actual values from your account")

    # Test all 10 actions
    print("\n" + "=" * 60)
    print("TIME ENTRY ACTIONS (5 actions)")
    print("=" * 60)
    await test_create_time_entry()      # Action 1
    await test_stop_time_entry()        # Action 2
    await test_list_time_entries()      # Action 3
    await test_update_time_entry()      # Action 4
    await test_delete_time_entry()      # Action 5

    print("\n" + "=" * 60)
    print("RESOURCE MANAGEMENT ACTIONS (5 actions)")
    print("=" * 60)
    await test_list_projects()          # Action 6
    await test_get_project()            # Action 7
    await test_list_clients()           # Action 8
    await test_list_tasks()             # Action 9
    await test_list_users()             # Action 10

    print("\n" + "=" * 60)
    print("Test suite completed! All 10 actions tested.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

# Test suite for Float integration
import asyncio
import os
from context import float
from autohive_integrations_sdk import ExecutionContext, ActionResult

# Test configuration
# IMPORTANT: Set the following environment variables before running tests:
#   FLOAT_API_KEY, FLOAT_CONTACT_EMAIL, FLOAT_APPLICATION_NAME
TEST_AUTH = {
    "credentials": {
        "api_key": os.getenv("FLOAT_API_KEY", "your_api_key_here"),
        "contact_email": os.getenv("FLOAT_CONTACT_EMAIL", "your_email@example.com"),
        "application_name": os.getenv("FLOAT_APPLICATION_NAME", "Your Application Name")
    }
}

# Store IDs for dependent tests
test_person_id = None
test_project_id = None
test_task_id = None
test_client_id = None
test_time_off_id = None
test_logged_time_id = None
test_department_id = None
test_role_id = None
test_time_off_type_id = None
test_account_id = None
test_status_id = None


# ==================== PEOPLE RESOURCE TESTS ====================

async def test_list_people():
    """Test listing all people in the Float account"""
    print("\n[TEST] Listing people...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_people", inputs, context)

            # Handle ActionResult return type
            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} person(s)")

            if data:
                global test_person_id
                test_person_id = data[0].get("people_id")
                print(f"  Using person: {data[0].get('name', 'Unnamed')} (ID: {test_person_id})")

                # Show first few people
                for i, person in enumerate(data[:3]):
                    print(f"  - {person.get('name', 'Unnamed')} ({person.get('email', 'No email')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_person():
    """Test getting a specific person's details"""
    if not test_person_id:
        print("\n[TEST] Skipping get_person - no person ID available")
        return None

    print(f"\n[TEST] Getting person details for {test_person_id}...")

    inputs = {
        "people_id": test_person_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_person", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("people_id") == test_person_id, "Should return correct person"
            print(f"[OK] Retrieved person: {data.get('name', 'Unnamed')}")
            print(f"  Email: {data.get('email', 'N/A')}")
            print(f"  Job Title: {data.get('job_title', 'N/A')}")
            print(f"  Active: {data.get('active', 'N/A')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_create_person():
    """Test creating a new person. Commented out to avoid test data creation."""
    print("\n[TEST] Skipping create_person - commented out to avoid test data")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test
    # inputs = {
    #     "name": "Test User",
    #     "email": "testuser@example.com",
    #     "job_title": "Test Engineer",
    #     "active": 1
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await float.execute_action("create_person", inputs, context)
    #         print(f"[OK] Created person: {result.get('name')} (ID: {result.get('people_id')})")
    #         return result
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


# ==================== PROJECT RESOURCE TESTS ====================

async def test_list_projects():
    """Test listing all projects"""
    print("\n[TEST] Listing projects...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_projects", inputs, context)

            assert isinstance(result.data, list), "Should return an array"
            print(f"[OK] Found {len(result.data)} project(s)")

            if result.data:
                global test_project_id
                test_project_id = result.data[0].get("project_id")
                print(f"  Using project: {result.data[0].get('name', 'Unnamed')} (ID: {test_project_id})")

                # Show first few projects
                for i, project in enumerate(result.data[:3]):
                    print(f"  - {project.get('name', 'Unnamed')} (Active: {project.get('active', 'N/A')})")

            return result.data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_project():
    """Test getting a specific project's details"""
    if not test_project_id:
        print("\n[TEST] Skipping get_project - no project ID available")
        return None

    print(f"\n[TEST] Getting project details for {test_project_id}...")

    inputs = {
        "project_id": test_project_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_project", inputs, context)

            assert result.data.get("project_id") == test_project_id, "Should return correct project"
            print(f"[OK] Retrieved project: {result.data.get('name', 'Unnamed')}")
            print(f"  Client ID: {result.data.get('client_id', 'N/A')}")
            print(f"  Budget Type: {result.data.get('budget_type', 'N/A')}")
            print(f"  Active: {result.data.get('active', 'N/A')}")

            return result

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== TASK/ALLOCATION RESOURCE TESTS ====================

async def test_list_tasks():
    """Test listing all tasks/allocations"""
    print("\n[TEST] Listing tasks/allocations...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_tasks", inputs, context)

            assert isinstance(result.data, list), "Should return an array"
            print(f"[OK] Found {len(result.data)} task(s)")

            if result.data:
                global test_task_id
                test_task_id = result.data[0].get("task_id")
                print(f"  Using task ID: {test_task_id}")

                # Show first few tasks
                for i, task in enumerate(result.data[:3]):
                    print(f"  - Task {task.get('task_id')} (Person: {task.get('people_id')}, Project: {task.get('project_id')})")

            return result.data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_task():
    """Test getting a specific task's details"""
    if not test_task_id:
        print("\n[TEST] Skipping get_task - no task ID available")
        return None

    print(f"\n[TEST] Getting task details for {test_task_id}...")

    inputs = {
        "task_id": test_task_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_task", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("task_id") == test_task_id, "Should return correct task"
            print(f"[OK] Retrieved task: {data.get('task_id')}")
            print(f"  Person ID: {data.get('people_id', 'N/A')}")
            print(f"  Project ID: {data.get('project_id', 'N/A')}")
            print(f"  Hours: {data.get('hours', 'N/A')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== CLIENT RESOURCE TESTS ====================

async def test_list_clients():
    """Test listing all clients"""
    print("\n[TEST] Listing clients...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_clients", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} client(s)")

            if data:
                global test_client_id
                test_client_id = data[0].get("client_id")
                print(f"  Using client: {data[0].get('name', 'Unnamed')} (ID: {test_client_id})")

                # Show first few clients
                for i, client in enumerate(data[:3]):
                    print(f"  - {client.get('name', 'Unnamed')} (Active: {client.get('active', 'N/A')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_client():
    """Test getting a specific client's details"""
    if not test_client_id:
        print("\n[TEST] Skipping get_client - no client ID available")
        return None

    print(f"\n[TEST] Getting client details for {test_client_id}...")

    inputs = {
        "client_id": test_client_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_client", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("client_id") == test_client_id, "Should return correct client"
            print(f"[OK] Retrieved client: {data.get('name', 'Unnamed')}")
            print(f"  Active: {data.get('active', 'N/A')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== TIME OFF RESOURCE TESTS ====================

async def test_list_time_off():
    """Test listing all time off entries"""
    print("\n[TEST] Listing time off entries...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_time_off", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} time off entry(s)")

            if data:
                global test_time_off_id
                test_time_off_id = data[0].get("timeoff_id")
                print(f"  Using time off ID: {test_time_off_id}")

                # Show first few entries
                for i, entry in enumerate(data[:3]):
                    print(f"  - Time off {entry.get('timeoff_id')} (Person: {entry.get('people_id')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== LOGGED TIME RESOURCE TESTS ====================

async def test_list_logged_time():
    """Test listing all logged time entries"""
    print("\n[TEST] Listing logged time entries...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_logged_time", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} logged time entry(s)")

            if data:
                global test_logged_time_id
                test_logged_time_id = data[0].get("logged_time_id")
                print(f"  Using logged time ID: {test_logged_time_id}")

                # Show first few entries
                for i, entry in enumerate(data[:3]):
                    print(f"  - {entry.get('date', 'N/A')}: {entry.get('hours', 'N/A')} hours")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== DEPARTMENT RESOURCE TESTS ====================

async def test_list_departments():
    """Test listing all departments"""
    print("\n[TEST] Listing departments...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_departments", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} department(s)")

            if data:
                global test_department_id
                test_department_id = data[0].get("department_id")
                print(f"  Using department: {data[0].get('name', 'Unnamed')} (ID: {test_department_id})")

                # Show all departments
                for dept in data:
                    print(f"  - {dept.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_department():
    """Test getting a specific department's details"""
    if not test_department_id:
        print("\n[TEST] Skipping get_department - no department ID available")
        return None

    print(f"\n[TEST] Getting department details for {test_department_id}...")

    inputs = {
        "department_id": test_department_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_department", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("department_id") == test_department_id, "Should return correct department"
            print(f"[OK] Retrieved department: {data.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== ROLE RESOURCE TESTS ====================

async def test_list_roles():
    """Test listing all roles"""
    print("\n[TEST] Listing roles...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_roles", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} role(s)")

            if data:
                global test_role_id
                test_role_id = data[0].get("role_id")
                print(f"  Using role: {data[0].get('name', 'Unnamed')} (ID: {test_role_id})")

                # Show all roles
                for role in data:
                    print(f"  - {role.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_role():
    """Test getting a specific role's details"""
    if not test_role_id:
        print("\n[TEST] Skipping get_role - no role ID available")
        return None

    print(f"\n[TEST] Getting role details for {test_role_id}...")

    inputs = {
        "role_id": test_role_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_role", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("role_id") == test_role_id, "Should return correct role"
            print(f"[OK] Retrieved role: {data.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== TIME OFF TYPE RESOURCE TESTS ====================

async def test_list_time_off_types():
    """Test listing all time off types"""
    print("\n[TEST] Listing time off types...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_time_off_types", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} time off type(s)")

            if data:
                global test_time_off_type_id
                test_time_off_type_id = data[0].get("timeoff_type_id")
                print(f"  Using time off type: {data[0].get('name', 'Unnamed')} (ID: {test_time_off_type_id})")

                # Show all time off types
                for toff_type in data:
                    print(f"  - {toff_type.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_time_off_type():
    """Test getting a specific time off type's details"""
    if not test_time_off_type_id:
        print("\n[TEST] Skipping get_time_off_type - no time off type ID available")
        return None

    print(f"\n[TEST] Getting time off type details for {test_time_off_type_id}...")

    inputs = {
        "timeoff_type_id": test_time_off_type_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_time_off_type", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("timeoff_type_id") == test_time_off_type_id, "Should return correct time off type"
            print(f"[OK] Retrieved time off type: {data.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== ACCOUNT RESOURCE TESTS ====================

async def test_list_accounts():
    """Test listing all accounts"""
    print("\n[TEST] Listing accounts...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_accounts", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} account(s)")

            if data:
                global test_account_id
                test_account_id = data[0].get("account_id")
                print(f"  Using account ID: {test_account_id}")

                # Show account info
                for account in data[:3]:
                    print(f"  - Account {account.get('account_id')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_account():
    """Test getting a specific account's details"""
    if not test_account_id:
        print("\n[TEST] Skipping get_account - no account ID available")
        return None

    print(f"\n[TEST] Getting account details for {test_account_id}...")

    inputs = {
        "account_id": test_account_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_account", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("account_id") == test_account_id, "Should return correct account"
            print(f"[OK] Retrieved account: {data.get('account_id')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== STATUS RESOURCE TESTS ====================

async def test_list_statuses():
    """Test listing all statuses"""
    print("\n[TEST] Listing statuses...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_statuses", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} status(es)")

            if data:
                global test_status_id
                test_status_id = data[0].get("status_id")
                print(f"  Using status: {data[0].get('name', 'Unnamed')} (ID: {test_status_id})")

                # Show all statuses
                for status in data:
                    print(f"  - {status.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_status():
    """Test getting a specific status's details"""
    if not test_status_id:
        print("\n[TEST] Skipping get_status - no status ID available")
        return None

    print(f"\n[TEST] Getting status details for {test_status_id}...")

    inputs = {
        "status_id": test_status_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_status", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert data.get("status_id") == test_status_id, "Should return correct status"
            print(f"[OK] Retrieved status: {data.get('name', 'Unnamed')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== PUBLIC HOLIDAY RESOURCE TESTS ====================

async def test_list_public_holidays():
    """Test listing public holidays"""
    print("\n[TEST] Listing public holidays...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_public_holidays", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} public holiday(s)")

            # Show first few holidays
            for holiday in data[:5]:
                print(f"  - {holiday.get('name', 'Unnamed')} ({holiday.get('date', 'N/A')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== TEAM HOLIDAY RESOURCE TESTS ====================

async def test_list_team_holidays():
    """Test listing team holidays"""
    print("\n[TEST] Listing team holidays...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_team_holidays", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} team holiday(s)")

            # Show first few holidays
            for holiday in data[:5]:
                print(f"  - Team holiday {holiday.get('team_holiday_id', 'N/A')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== MILESTONE RESOURCE TESTS ====================

async def test_list_milestones():
    """Test listing milestones"""
    print("\n[TEST] Listing milestones...")

    inputs = {
        "per_page": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("list_milestones", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            data = result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} milestone(s)")

            # Show first few milestones
            for milestone in data[:5]:
                print(f"  - {milestone.get('name', 'Unnamed')} ({milestone.get('date', 'N/A')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== REPORTS RESOURCE TESTS ====================

async def test_get_people_report():
    """Test getting people utilization report"""
    print("\n[TEST] Getting people utilization report...")

    inputs = {
        "start_date": "2025-01-01",
        "end_date": "2025-01-31"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_people_report", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            print(f"[OK] Retrieved people report")
            print(f"  Date range: {inputs['start_date']} to {inputs['end_date']}")

            return result.data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_get_projects_report():
    """Test getting projects report"""
    print("\n[TEST] Getting projects report...")

    inputs = {
        "start_date": "2025-01-01",
        "end_date": "2025-01-31"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await float.execute_action("get_projects_report", inputs, context)

            assert isinstance(result, ActionResult), "Should return ActionResult"
            print(f"[OK] Retrieved projects report")
            print(f"  Date range: {inputs['start_date']} to {inputs['end_date']}")

            return result.data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== MAIN TEST RUNNER ====================

async def main():
    print("=" * 70)
    print("Float Integration Test Suite")
    print("=" * 70)
    print("\nSETUP:")
    print(f"  API Key: {TEST_AUTH['credentials']['api_key'][:20]}...")
    print(f"  Email: {TEST_AUTH['credentials']['contact_email']}")
    print(f"  Application: {TEST_AUTH['credentials']['application_name']}")
    print("\n" + "=" * 70)

    try:
        # Test People Resource
        print("\n" + "=" * 70)
        print("PEOPLE RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_people()
        await test_get_person()

        # Test Projects Resource
        print("\n" + "=" * 70)
        print("PROJECTS RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_projects()
        await test_get_project()

        # Test Tasks Resource
        print("\n" + "=" * 70)
        print("TASKS/ALLOCATIONS RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_tasks()
        await test_get_task()

        # Test Clients Resource
        print("\n" + "=" * 70)
        print("CLIENTS RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_clients()
        await test_get_client()

        # Test Time Off Resource
        print("\n" + "=" * 70)
        print("TIME OFF RESOURCE (1 action)")
        print("=" * 70)
        await test_list_time_off()

        # Test Logged Time Resource
        print("\n" + "=" * 70)
        print("LOGGED TIME RESOURCE (1 action)")
        print("=" * 70)
        await test_list_logged_time()

        # Test Departments Resource
        print("\n" + "=" * 70)
        print("DEPARTMENTS RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_departments()
        await test_get_department()

        # Test Roles Resource
        print("\n" + "=" * 70)
        print("ROLES RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_roles()
        await test_get_role()

        # Test Time Off Types Resource
        print("\n" + "=" * 70)
        print("TIME OFF TYPES RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_time_off_types()
        await test_get_time_off_type()

        # Test Accounts Resource
        print("\n" + "=" * 70)
        print("ACCOUNTS RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_accounts()
        await test_get_account()

        # Test Statuses Resource
        print("\n" + "=" * 70)
        print("STATUSES RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_statuses()
        await test_get_status()

        # Test Public Holidays Resource
        print("\n" + "=" * 70)
        print("PUBLIC HOLIDAYS RESOURCE (1 action)")
        print("=" * 70)
        await test_list_public_holidays()

        # Test Team Holidays Resource
        print("\n" + "=" * 70)
        print("TEAM HOLIDAYS RESOURCE (1 action)")
        print("=" * 70)
        await test_list_team_holidays()

        # Test Milestones Resource
        print("\n" + "=" * 70)
        print("MILESTONES RESOURCE (1 action)")
        print("=" * 70)
        await test_list_milestones()

        # Test Reports Resource
        print("\n" + "=" * 70)
        print("REPORTS RESOURCE (2 actions)")
        print("=" * 70)
        await test_get_people_report()
        await test_get_projects_report()

        print("\n" + "=" * 70)
        print("Test suite completed!")
        print("=" * 70)
        print("\nSummary: 25 actions tested")
        print("  - Tested core read operations for all resources")
        print("  - Create/Update/Delete operations commented out to avoid test data")
        print("=" * 70)

    except Exception as e:
        print(f"\nTest suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

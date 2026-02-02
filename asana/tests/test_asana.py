# Testbed for Asana integration
import asyncio
from context import asana
from autohive_integrations_sdk import ExecutionContext


async def test_list_projects():
    """Test listing projects in workspace."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workspace": "your_workspace_gid_here",
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("list_projects", inputs, context)
            print(f"List Projects Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'projects' in result, "Response missing 'projects' field"
            return result
        except Exception as e:
            print(f"Error testing list_projects: {e}")
            return None


async def test_get_project():
    """Test getting a specific project."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"project_gid": "project_gid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("get_project", inputs, context)
            print(f"Get Project Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'project' in result, "Response missing 'project' field"
            return result
        except Exception as e:
            print(f"Error testing get_project: {e}")
            return None


async def test_create_task():
    """Test creating a new task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "name": "Test Task via Integration",
        "workspace": "your_workspace_gid_here",
        "notes": "This is a test task created via Asana API integration",
        "assignee": "me"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("create_task", inputs, context)
            print(f"Create Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'task' in result, "Response missing 'task' field"
            return result
        except Exception as e:
            print(f"Error testing create_task: {e}")
            return None


async def test_get_task():
    """Test getting a specific task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "task_gid": "task_gid_here",
        "opt_fields": ["assignee", "due_on", "completed", "projects"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("get_task", inputs, context)
            print(f"Get Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'task' in result, "Response missing 'task' field"
            return result
        except Exception as e:
            print(f"Error testing get_task: {e}")
            return None


async def test_update_task():
    """Test updating a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "task_gid": "task_gid_here",
        "name": "Updated Task Name",
        "completed": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("update_task", inputs, context)
            print(f"Update Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'task' in result, "Response missing 'task' field"
            return result
        except Exception as e:
            print(f"Error testing update_task: {e}")
            return None


async def test_list_tasks():
    """Test listing tasks with filters."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    # Filter by assignee + workspace (required combination)
    inputs = {
        "assignee": "me",
        "workspace": "your_workspace_gid_here",
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("list_tasks", inputs, context)
            print(f"List Tasks Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'tasks' in result, "Response missing 'tasks' field"
            return result
        except Exception as e:
            print(f"Error testing list_tasks: {e}")
            return None


async def test_delete_task():
    """Test deleting a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"task_gid": "task_gid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("delete_task", inputs, context)
            print(f"Delete Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_task: {e}")
            return None


async def test_create_project():
    """Test creating a new project."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {
        "name": "Test Project via API",
        "workspace": "your_workspace_gid_here",
        "team": "your_team_gid_here"  # Required for organization workspaces
    }
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("create_project", inputs, context)
            print(f"Create Project Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'project' in result, "Response missing 'project' field"
            return result
        except Exception as e:
            print(f"Error testing create_project: {e}")
            return None


async def test_update_project():
    """Test updating a project."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"project_gid": "project_gid_here", "name": "Updated Project Name"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("update_project", inputs, context)
            print(f"Update Project Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'project' in result, "Response missing 'project' field"
            return result
        except Exception as e:
            print(f"Error testing update_project: {e}")
            return None


async def test_delete_project():
    """Test deleting a project."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"project_gid": "project_gid_here"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("delete_project", inputs, context)
            print(f"Delete Project Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_project: {e}")
            return None


async def test_get_project_by_name():
    """Test getting a project by name."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {
        "name": "Your Project Name Here",  # Replace with actual project name
        "workspace": "your_workspace_gid_here"  # Optional but recommended
    }
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("get_project_by_name", inputs, context)
            print(f"Get Project by Name Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('not_found'):
                print("  -> Project not found")
            else:
                print(f"  -> Found: {result.get('name')} (GID: {result.get('gid')})")
            return result
        except Exception as e:
            print(f"Error testing get_project_by_name: {e}")
            return None


async def test_list_sections():
    """Test listing sections in a project."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"project_gid": "project_gid_here"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("list_sections", inputs, context)
            print(f"List Sections Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'sections' in result, "Response missing 'sections' field"
            return result
        except Exception as e:
            print(f"Error testing list_sections: {e}")
            return None


async def test_create_section():
    """Test creating a section."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"project_gid": "project_gid_here", "name": "To Do"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("create_section", inputs, context)
            print(f"Create Section Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'section' in result, "Response missing 'section' field"
            return result
        except Exception as e:
            print(f"Error testing create_section: {e}")
            return None


async def test_update_section():
    """Test updating a section."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"section_gid": "section_gid_here", "name": "In Progress"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("update_section", inputs, context)
            print(f"Update Section Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'section' in result, "Response missing 'section' field"
            return result
        except Exception as e:
            print(f"Error testing update_section: {e}")
            return None


async def test_add_task_to_section():
    """Test adding task to section."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"section_gid": "section_gid_here", "task_gid": "task_gid_here"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("add_task_to_section", inputs, context)
            print(f"Add Task to Section Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing add_task_to_section: {e}")
            return None


async def test_create_story():
    """Test creating a comment."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"task_gid": "task_gid_here", "text": "This is a test comment"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("create_story", inputs, context)
            print(f"Create Story Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'story' in result, "Response missing 'story' field"
            return result
        except Exception as e:
            print(f"Error testing create_story: {e}")
            return None


async def test_list_stories():
    """Test listing stories/comments."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"task_gid": "task_gid_here"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("list_stories", inputs, context)
            print(f"List Stories Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'stories' in result, "Response missing 'stories' field"
            return result
        except Exception as e:
            print(f"Error testing list_stories: {e}")
            return None


async def test_create_subtask():
    """Test creating a subtask."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"parent_task_gid": "task_gid_here", "name": "Subtask 1"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("create_subtask", inputs, context)
            print(f"Create Subtask Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'subtask' in result, "Response missing 'subtask' field"
            return result
        except Exception as e:
            print(f"Error testing create_subtask: {e}")
            return None


async def test_list_workspaces():
    """Test listing all workspaces."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {}  # No inputs required
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("list_workspaces", inputs, context)
            print(f"List Workspaces Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'workspaces' in result, "Response missing 'workspaces' field"
            if result.get('workspaces'):
                print(f"  -> Found {len(result['workspaces'])} workspace(s)")
                for ws in result['workspaces']:
                    print(f"     - {ws.get('name')} (GID: {ws.get('gid')})")
            return result
        except Exception as e:
            print(f"Error testing list_workspaces: {e}")
            return None


async def test_get_workspace():
    """Test getting a specific workspace."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {"workspace_gid": "your_workspace_gid_here"}
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("get_workspace", inputs, context)
            print(f"Get Workspace Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'workspace' in result, "Response missing 'workspace' field"
            return result
        except Exception as e:
            print(f"Error testing get_workspace: {e}")
            return None


async def test_get_user():
    """Test getting current user info."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }
    inputs = {
        "user_gid": "me",  # Get current user
        "opt_fields": ["workspaces", "email", "name"]
    }
    async with ExecutionContext(auth=auth) as context:
        try:
            result = await asana.execute_action("get_user", inputs, context)
            print(f"Get User Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'user' in result, "Response missing 'user' field"
            if result.get('user'):
                print(f"  -> User: {result['user'].get('name')} ({result['user'].get('email')})")
                if 'workspaces' in result['user']:
                    print(f"  -> Workspaces: {len(result['user']['workspaces'])}")
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


async def main():
    print("Testing Asana Integration - 21 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your OAuth access token")
    print("  - your_workspace_gid_here: Your workspace GID")
    print("  - your_team_gid_here: Your team GID")
    print("  - project_gid_here, task_gid_here, section_gid_here")
    print()
    print("TIP: Run list_workspaces and get_user tests first to get workspace IDs!")
    print()
    print("=" * 60)
    print()

    # Test workspace and user actions (3) - RUN THESE FIRST!
    print("WORKSPACE & USER DISCOVERY ACTIONS")
    print("-" * 60)
    print("1. Testing list_workspaces (NEW - helps you discover workspace IDs)...")
    await test_list_workspaces()
    print()

    print("2. Testing get_workspace (NEW)...")
    await test_get_workspace()
    print()

    print("3. Testing get_user (NEW - use 'me' to get your info & workspaces)...")
    await test_get_user()
    print()

    print("=" * 60)
    print()
    print("PROJECT ACTIONS")
    print("-" * 60)

    # Test project actions (6)
    print("4. Testing list_projects...")
    await test_list_projects()
    print()

    print("5. Testing get_project...")
    await test_get_project()
    print()

    print("6. Testing get_project_by_name...")
    await test_get_project_by_name()
    print()

    print("7. Testing create_project...")
    await test_create_project()
    print()

    print("8. Testing update_project...")
    await test_update_project()
    print()

    print("9. Testing delete_project...")
    await test_delete_project()
    print()

    print("=" * 60)
    print()
    print("TASK ACTIONS")
    print("-" * 60)

    # Test task actions (5)
    print("10. Testing create_task...")
    await test_create_task()
    print()

    print("11. Testing get_task...")
    await test_get_task()
    print()

    print("12. Testing update_task...")
    await test_update_task()
    print()

    print("13. Testing list_tasks...")
    await test_list_tasks()
    print()

    print("14. Testing delete_task...")
    await test_delete_task()
    print()

    print("=" * 60)
    print()
    print("SECTION ACTIONS")
    print("-" * 60)

    # Test section actions (4)
    print("15. Testing list_sections...")
    await test_list_sections()
    print()

    print("16. Testing create_section...")
    await test_create_section()
    print()

    print("17. Testing update_section...")
    await test_update_section()
    print()

    print("18. Testing add_task_to_section...")
    await test_add_task_to_section()
    print()

    print("=" * 60)
    print()
    print("COMMENT ACTIONS")
    print("-" * 60)

    # Test comment actions (2)
    print("19. Testing create_story...")
    await test_create_story()
    print()

    print("20. Testing list_stories...")
    await test_list_stories()
    print()

    print("=" * 60)
    print()
    print("SUBTASK ACTIONS")
    print("-" * 60)

    # Test subtask action (1)
    print("21. Testing create_subtask...")
    await test_create_subtask()
    print()

    print("=" * 60)
    print("Testing completed - 21 actions total!")
    print("  - 3 NEW workspace/user discovery actions")
    print("  - 18 existing actions")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

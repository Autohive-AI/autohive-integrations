# Testbed for ClickUp integration
import asyncio
from context import clickup
from autohive_integrations_sdk import ExecutionContext


async def test_get_authorized_teams():
    """Test getting authorized teams/workspaces."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_authorized_teams", inputs, context)
            print(f"Get Authorized Teams Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'teams' in result, "Response missing 'teams' field"
            return result
        except Exception as e:
            print(f"Error testing get_authorized_teams: {e}")
            return None


async def test_get_spaces():
    """Test getting spaces in a team."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "team_id": "your_team_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_spaces", inputs, context)
            print(f"Get Spaces Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'spaces' in result, "Response missing 'spaces' field"
            return result
        except Exception as e:
            print(f"Error testing get_spaces: {e}")
            return None


async def test_get_space():
    """Test getting a specific space."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "space_id": "your_space_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_space", inputs, context)
            print(f"Get Space Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'space' in result, "Response missing 'space' field"
            return result
        except Exception as e:
            print(f"Error testing get_space: {e}")
            return None


async def test_create_folder():
    """Test creating a folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "space_id": "your_space_id_here",
        "name": "Test Folder via API"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("create_folder", inputs, context)
            print(f"Create Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'folder' in result, "Response missing 'folder' field"
            return result
        except Exception as e:
            print(f"Error testing create_folder: {e}")
            return None


async def test_get_folder():
    """Test getting a specific folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "folder_id": "your_folder_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_folder", inputs, context)
            print(f"Get Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'folder' in result, "Response missing 'folder' field"
            return result
        except Exception as e:
            print(f"Error testing get_folder: {e}")
            return None


async def test_update_folder():
    """Test updating a folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "folder_id": "your_folder_id_here",
        "name": "Updated Folder Name"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("update_folder", inputs, context)
            print(f"Update Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'folder' in result, "Response missing 'folder' field"
            return result
        except Exception as e:
            print(f"Error testing update_folder: {e}")
            return None


async def test_get_folders():
    """Test getting folders in a space."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "space_id": "your_space_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_folders", inputs, context)
            print(f"Get Folders Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'folders' in result, "Response missing 'folders' field"
            return result
        except Exception as e:
            print(f"Error testing get_folders: {e}")
            return None


async def test_delete_folder():
    """Test deleting a folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "folder_id": "your_folder_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("delete_folder", inputs, context)
            print(f"Delete Folder Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_folder: {e}")
            return None


async def test_create_list():
    """Test creating a list."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "folder_id": "your_folder_id_here",
        "name": "Test List via API"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("create_list", inputs, context)
            print(f"Create List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing create_list: {e}")
            return None


async def test_get_list():
    """Test getting a specific list."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_list", inputs, context)
            print(f"Get List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing get_list: {e}")
            return None


async def test_update_list():
    """Test updating a list."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "name": "Updated List Name"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("update_list", inputs, context)
            print(f"Update List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing update_list: {e}")
            return None


async def test_get_lists():
    """Test getting lists in a folder."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "folder_id": "your_folder_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_lists", inputs, context)
            print(f"Get Lists Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'lists' in result, "Response missing 'lists' field"
            return result
        except Exception as e:
            print(f"Error testing get_lists: {e}")
            return None


async def test_delete_list():
    """Test deleting a list."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("delete_list", inputs, context)
            print(f"Delete List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_list: {e}")
            return None


async def test_create_task():
    """Test creating a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "name": "Test Task via API",
        "description": "This is a test task created via ClickUp API integration",
        "priority": 3
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("create_task", inputs, context)
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
        "task_id": "your_task_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_task", inputs, context)
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
        "task_id": "your_task_id_here",
        "name": "Updated Task Name",
        "status": "Complete"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("update_task", inputs, context)
            print(f"Update Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'task' in result, "Response missing 'task' field"
            return result
        except Exception as e:
            print(f"Error testing update_task: {e}")
            return None


async def test_get_tasks():
    """Test getting tasks from a list."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_tasks", inputs, context)
            print(f"Get Tasks Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'tasks' in result, "Response missing 'tasks' field"
            return result
        except Exception as e:
            print(f"Error testing get_tasks: {e}")
            return None


async def test_delete_task():
    """Test deleting a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "task_id": "your_task_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("delete_task", inputs, context)
            print(f"Delete Task Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_task: {e}")
            return None


async def test_create_task_comment():
    """Test creating a comment on a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "task_id": "your_task_id_here",
        "comment_text": "This is a test comment via API"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("create_task_comment", inputs, context)
            print(f"Create Task Comment Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'comment' in result, "Response missing 'comment' field"
            return result
        except Exception as e:
            print(f"Error testing create_task_comment: {e}")
            return None


async def test_get_task_comments():
    """Test getting comments from a task."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "task_id": "your_task_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("get_task_comments", inputs, context)
            print(f"Get Task Comments Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'comments' in result, "Response missing 'comments' field"
            return result
        except Exception as e:
            print(f"Error testing get_task_comments: {e}")
            return None


async def test_update_comment():
    """Test updating a comment."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "comment_id": "your_comment_id_here",
        "comment_text": "Updated comment text"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("update_comment", inputs, context)
            print(f"Update Comment Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'comment' in result, "Response missing 'comment' field"
            return result
        except Exception as e:
            print(f"Error testing update_comment: {e}")
            return None


async def test_delete_comment():
    """Test deleting a comment."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "comment_id": "your_comment_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await clickup.execute_action("delete_comment", inputs, context)
            print(f"Delete Comment Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_comment: {e}")
            return None


async def main():
    print("Testing ClickUp Integration - 22 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your OAuth access token")
    print("  - your_team_id_here: Your team/workspace ID")
    print("  - your_space_id_here: Your space ID")
    print("  - your_folder_id_here: Your folder ID")
    print("  - your_list_id_here: Your list ID")
    print("  - your_task_id_here: Your task ID")
    print("  - your_comment_id_here: Your comment ID")
    print()
    print("To get IDs:")
    print("  Teams: Use get_authorized_teams action")
    print("  Spaces: Use get_spaces action with team_id")
    print("  Folders: Use get_folders action with space_id")
    print("  Lists: Use get_lists action with folder_id or space_id")
    print("  Tasks: Use get_tasks action with list_id")
    print()
    print("=" * 60)
    print()

    # Test team/workspace actions (1)
    print("1. Testing get_authorized_teams...")
    await test_get_authorized_teams()
    print()

    # Test space actions (2)
    print("2. Testing get_spaces...")
    await test_get_spaces()
    print()

    print("3. Testing get_space...")
    await test_get_space()
    print()

    # Test folder actions (5)
    print("4. Testing create_folder...")
    await test_create_folder()
    print()

    print("5. Testing get_folder...")
    await test_get_folder()
    print()

    print("6. Testing update_folder...")
    await test_update_folder()
    print()

    print("7. Testing get_folders...")
    await test_get_folders()
    print()

    print("8. Testing delete_folder...")
    await test_delete_folder()
    print()

    # Test list actions (5)
    print("9. Testing create_list...")
    await test_create_list()
    print()

    print("10. Testing get_list...")
    await test_get_list()
    print()

    print("11. Testing update_list...")
    await test_update_list()
    print()

    print("12. Testing get_lists...")
    await test_get_lists()
    print()

    print("13. Testing delete_list...")
    await test_delete_list()
    print()

    # Test task actions (5)
    print("14. Testing create_task...")
    await test_create_task()
    print()

    print("15. Testing get_task...")
    await test_get_task()
    print()

    print("16. Testing update_task...")
    await test_update_task()
    print()

    print("17. Testing get_tasks...")
    await test_get_tasks()
    print()

    print("18. Testing delete_task...")
    await test_delete_task()
    print()

    # Test comment actions (4)
    print("19. Testing create_task_comment...")
    await test_create_task_comment()
    print()

    print("20. Testing get_task_comments...")
    await test_get_task_comments()
    print()

    print("21. Testing update_comment...")
    await test_update_comment()
    print()

    print("22. Testing delete_comment...")
    await test_delete_comment()
    print()

    print("=" * 60)
    print("Testing completed - 22 actions total!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

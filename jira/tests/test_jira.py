"""
Manual testbed for the Jira integration.

Usage:
    1. Set the credentials below.
    2. Run: python tests/test_jira.py
    3. Review printed output.

DO NOT commit real credentials.
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jira import jira
from autohive_integrations_sdk import ExecutionContext

# ------------------------------------------------------------
# CREDENTIALS — Replace with your OAuth access token to run tests.
# Obtain via the platform OAuth flow or Atlassian developer console.
# NEVER commit real values here.
# ------------------------------------------------------------
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"  # nosec B105

# Test data — replace with real values from your Jira instance
TEST_PROJECT_KEY = "PROJ"
TEST_ISSUE_KEY = "PROJ-1"
TEST_BOARD_ID = 1
TEST_SPRINT_ID = 1
TEST_USER_ACCOUNT_ID = "YOUR_ACCOUNT_ID_HERE"

AUTH = {"auth_type": "oauth", "credentials": {"access_token": ACCESS_TOKEN}}


def make_context():
    """Create an ExecutionContext with test credentials."""
    return ExecutionContext(auth=AUTH)


async def test_missing_credentials():
    """Test that missing credentials fail fast with a clear error."""
    async with ExecutionContext(auth={"auth_type": "oauth", "credentials": {}}) as context:
        result = await jira.execute_action("get_current_user", {}, context)
    assert result.data.get("result") is False, "Expected failure on missing credentials"
    assert (
        "access_token" in (result.data.get("error") or "").lower()
        or "access_token" in (result.data.get("message") or "").lower()
    )
    print("test_missing_credentials: PASS")
    return result.data


async def test_get_current_user():
    """Test retrieving the currently authenticated user."""
    async with make_context() as context:
        result = await jira.execute_action("get_current_user", {}, context)
    print("test_get_current_user:", result.data)
    return result.data


async def test_search_users():
    """Test searching for users."""
    async with make_context() as context:
        result = await jira.execute_action("search_users", {"query": "admin"}, context)
    print("test_search_users:", result.data)
    return result.data


async def test_get_user():
    """Test retrieving a specific user by account ID."""
    async with make_context() as context:
        result = await jira.execute_action("get_user", {"accountId": TEST_USER_ACCOUNT_ID}, context)
    print("test_get_user:", result.data)
    return result.data


async def test_list_projects():
    """Test listing all accessible projects."""
    async with make_context() as context:
        result = await jira.execute_action("list_projects", {"maxResults": 10}, context)
    print("test_list_projects:", result.data)
    return result.data


async def test_get_project():
    """Test getting project details."""
    async with make_context() as context:
        result = await jira.execute_action("get_project", {"projectKey": TEST_PROJECT_KEY}, context)
    print("test_get_project:", result.data)
    return result.data


async def test_get_project_components():
    """Test listing project components."""
    async with make_context() as context:
        result = await jira.execute_action("get_project_components", {"projectKey": TEST_PROJECT_KEY}, context)
    print("test_get_project_components:", result.data)
    return result.data


async def test_get_project_versions():
    """Test listing project versions."""
    async with make_context() as context:
        result = await jira.execute_action("get_project_versions", {"projectKey": TEST_PROJECT_KEY}, context)
    print("test_get_project_versions:", result.data)
    return result.data


async def test_create_issue():
    """Test creating a new issue."""
    async with make_context() as context:
        result = await jira.execute_action(
            "create_issue",
            {
                "projectKey": TEST_PROJECT_KEY,
                "summary": "Test issue created by autohive integration",
                "issueType": "Task",
                "description": "This is a test issue. Safe to delete.",
                "priority": "Medium",
                "labels": ["test", "autohive"],
            },
            context,
        )
    print("test_create_issue:", result.data)
    return result.data


async def test_get_issue():
    """Test retrieving issue details."""
    async with make_context() as context:
        result = await jira.execute_action("get_issue", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_issue:", result.data)
    return result.data


async def test_update_issue():
    """Test updating an issue."""
    async with make_context() as context:
        result = await jira.execute_action(
            "update_issue",
            {
                "issueKey": TEST_ISSUE_KEY,
                "summary": "Updated summary from autohive integration test",
                "labels": ["autohive-updated"],
            },
            context,
        )
    print("test_update_issue:", result.data)
    return result.data


async def test_search_issues():
    """Test searching issues with JQL."""
    async with make_context() as context:
        result = await jira.execute_action(
            "search_issues",
            {
                "jql": f"project = {TEST_PROJECT_KEY} ORDER BY created DESC",
                "maxResults": 5,
            },
            context,
        )
    print("test_search_issues:", result.data)
    return result.data


async def test_get_issue_transitions():
    """Test retrieving available transitions for an issue."""
    async with make_context() as context:
        result = await jira.execute_action("get_issue_transitions", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_issue_transitions:", result.data)
    return result.data


async def test_add_comment():
    """Test adding a comment to an issue."""
    async with make_context() as context:
        result = await jira.execute_action(
            "add_comment",
            {
                "issueKey": TEST_ISSUE_KEY,
                "body": "Test comment from autohive integration.",
            },
            context,
        )
    print("test_add_comment:", result.data)
    return result.data


async def test_get_comments():
    """Test retrieving comments on an issue."""
    async with make_context() as context:
        result = await jira.execute_action("get_comments", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_comments:", result.data)
    return result.data


async def test_add_worklog():
    """Test logging time on an issue."""
    async with make_context() as context:
        result = await jira.execute_action(
            "add_worklog",
            {
                "issueKey": TEST_ISSUE_KEY,
                "timeSpent": "1h",
                "comment": "Test worklog from autohive integration.",
            },
            context,
        )
    print("test_add_worklog:", result.data)
    return result.data


async def test_get_worklogs():
    """Test retrieving worklogs for an issue."""
    async with make_context() as context:
        result = await jira.execute_action("get_worklogs", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_worklogs:", result.data)
    return result.data


async def test_get_watchers():
    """Test retrieving watchers on an issue."""
    async with make_context() as context:
        result = await jira.execute_action("get_watchers", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_watchers:", result.data)
    return result.data


async def test_get_issue_link_types():
    """Test retrieving available issue link types."""
    async with make_context() as context:
        result = await jira.execute_action("get_issue_link_types", {}, context)
    print("test_get_issue_link_types:", result.data)
    return result.data


async def test_get_issue_types():
    """Test retrieving issue types."""
    async with make_context() as context:
        result = await jira.execute_action("get_issue_types", {}, context)
    print("test_get_issue_types:", result.data)
    return result.data


async def test_get_priorities():
    """Test retrieving priority values."""
    async with make_context() as context:
        result = await jira.execute_action("get_priorities", {}, context)
    print("test_get_priorities:", result.data)
    return result.data


async def test_get_fields():
    """Test retrieving all fields."""
    async with make_context() as context:
        result = await jira.execute_action("get_fields", {"customOnly": False}, context)
    print("test_get_fields:", result.data)
    return result.data


async def test_get_issue_changelog():
    """Test retrieving issue changelog."""
    async with make_context() as context:
        result = await jira.execute_action("get_issue_changelog", {"issueKey": TEST_ISSUE_KEY}, context)
    print("test_get_issue_changelog:", result.data)
    return result.data


async def test_list_boards():
    """Test listing Jira boards."""
    async with make_context() as context:
        result = await jira.execute_action("list_boards", {"maxResults": 10}, context)
    print("test_list_boards:", result.data)
    return result.data


async def test_get_sprints():
    """Test getting sprints for a board."""
    async with make_context() as context:
        result = await jira.execute_action("get_sprints", {"boardId": TEST_BOARD_ID, "state": "active"}, context)
    print("test_get_sprints:", result.data)
    return result.data


async def test_get_sprint_issues():
    """Test getting issues in a sprint."""
    async with make_context() as context:
        result = await jira.execute_action("get_sprint_issues", {"sprintId": TEST_SPRINT_ID, "maxResults": 10}, context)
    print("test_get_sprint_issues:", result.data)
    return result.data


async def test_get_status_categories():
    """Test retrieving status categories."""
    async with make_context() as context:
        result = await jira.execute_action("get_status_categories", {}, context)
    print("test_get_status_categories:", result.data)
    return result.data


async def test_get_project_roles():
    """Test retrieving project roles."""
    async with make_context() as context:
        result = await jira.execute_action("get_project_roles", {"projectKey": TEST_PROJECT_KEY}, context)
    print("test_get_project_roles:", result.data)
    return result.data


if __name__ == "__main__":
    print("--- Testing Missing Credentials ---")
    asyncio.run(test_missing_credentials())

    print("\n--- Testing Get Current User ---")
    asyncio.run(test_get_current_user())

    print("\n--- Testing Search Users ---")
    asyncio.run(test_search_users())

    print("\n--- Testing List Projects ---")
    asyncio.run(test_list_projects())

    print("\n--- Testing Get Project ---")
    asyncio.run(test_get_project())

    print("\n--- Testing Get Project Components ---")
    asyncio.run(test_get_project_components())

    print("\n--- Testing Get Project Versions ---")
    asyncio.run(test_get_project_versions())

    print("\n--- Testing Create Issue ---")
    asyncio.run(test_create_issue())

    print("\n--- Testing Get Issue ---")
    asyncio.run(test_get_issue())

    print("\n--- Testing Update Issue ---")
    asyncio.run(test_update_issue())

    print("\n--- Testing Search Issues ---")
    asyncio.run(test_search_issues())

    print("\n--- Testing Get Issue Transitions ---")
    asyncio.run(test_get_issue_transitions())

    print("\n--- Testing Add Comment ---")
    asyncio.run(test_add_comment())

    print("\n--- Testing Get Comments ---")
    asyncio.run(test_get_comments())

    print("\n--- Testing Add Worklog ---")
    asyncio.run(test_add_worklog())

    print("\n--- Testing Get Worklogs ---")
    asyncio.run(test_get_worklogs())

    print("\n--- Testing Get Watchers ---")
    asyncio.run(test_get_watchers())

    print("\n--- Testing Get Issue Link Types ---")
    asyncio.run(test_get_issue_link_types())

    print("\n--- Testing Get Issue Types ---")
    asyncio.run(test_get_issue_types())

    print("\n--- Testing Get Priorities ---")
    asyncio.run(test_get_priorities())

    print("\n--- Testing Get Fields ---")
    asyncio.run(test_get_fields())

    print("\n--- Testing Get Issue Changelog ---")
    asyncio.run(test_get_issue_changelog())

    print("\n--- Testing List Boards ---")
    asyncio.run(test_list_boards())

    print("\n--- Testing Get Sprints ---")
    asyncio.run(test_get_sprints())

    print("\n--- Testing Get Sprint Issues ---")
    asyncio.run(test_get_sprint_issues())

    print("\n--- Testing Get Status Categories ---")
    asyncio.run(test_get_status_categories())

    print("\n--- Testing Get Project Roles ---")
    asyncio.run(test_get_project_roles())

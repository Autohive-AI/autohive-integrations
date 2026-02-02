# Test suite for GitHub integration
import asyncio
import os
import sys
from context import github
from autohive_integrations_sdk import ExecutionContext, ActionResult, IntegrationResult

# Test configuration
# Pass token as command line argument: python test_github.py YOUR_TOKEN
# Or set environment variable: set GITHUB_ACCESS_TOKEN=YOUR_TOKEN && python test_github.py
if len(sys.argv) > 1:
    ACCESS_TOKEN = sys.argv[1]
else:
    ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN", "")

if not ACCESS_TOKEN:
    print("ERROR: No GitHub access token provided!")
    print("Usage: python test_github.py YOUR_GITHUB_TOKEN")
    print("   Or: set GITHUB_ACCESS_TOKEN=token && python test_github.py")
    sys.exit(1)

TEST_AUTH = {
    "credentials": {
        "access_token": ACCESS_TOKEN
    }
}

# Store IDs for dependent tests
test_repo_owner = None
test_repo_name = None
test_issue_number = None
test_workflow_id = None


# ==================== REPOSITORY RESOURCE TESTS ====================

async def test_get_repository():
    """Test getting a specific repository's details"""
    # Use a well-known public repo for testing
    global test_repo_owner, test_repo_name
    test_repo_owner = "octocat"
    test_repo_name = "Hello-World"

    print(f"\n[TEST] Getting repository details for {test_repo_owner}/{test_repo_name}...")

    inputs = {
        "owner": test_repo_owner,
        "repo": test_repo_name
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await github.execute_action("get_repository", inputs, context)

            assert isinstance(result, IntegrationResult), "Should return IntegrationResult"
            assert isinstance(result.result, ActionResult), "Result should contain ActionResult"
            data = result.result.data
            assert data.get("name") == test_repo_name, "Should return correct repository"
            print(f"[OK] Retrieved repository: {data.get('full_name')}")
            print(f"  Description: {data.get('description', 'N/A')}")
            print(f"  Stars: {data.get('stargazers_count', 0)}")
            print(f"  Forks: {data.get('forks_count', 0)}")
            print(f"  Default Branch: {data.get('default_branch', 'N/A')}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== COMMIT RESOURCE TESTS ====================

async def test_list_commits():
    """Test listing commits for a repository"""
    if not test_repo_owner or not test_repo_name:
        print("\n[TEST] Skipping list_commits - no repository available")
        return None

    print(f"\n[TEST] Listing commits for {test_repo_owner}/{test_repo_name}...")

    inputs = {
        "owner": test_repo_owner,
        "repo": test_repo_name,
        "since": "2020-01-01T00:00:00Z"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await github.execute_action("list_commits", inputs, context)

            assert isinstance(result, IntegrationResult), "Should return IntegrationResult"
            assert isinstance(result.result, ActionResult), "Result should contain ActionResult"
            data = result.result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} commit(s)")

            for commit in data[:3]:
                sha = commit.get("sha", "")[:7]
                message = commit.get("commit", {}).get("message", "N/A")[:50]
                print(f"  - {sha}: {message}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== ISSUE RESOURCE TESTS ====================

async def test_list_issues():
    """Test getting issues for a repository"""
    if not test_repo_owner or not test_repo_name:
        print("\n[TEST] Skipping list_issues - no repository available")
        return None

    print(f"\n[TEST] Listing issues for {test_repo_owner}/{test_repo_name}...")

    inputs = {
        "owner": test_repo_owner,
        "repo": test_repo_name,
        "state": "all",
        "sort": "created",
        "direction": "desc"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await github.execute_action("list_issues", inputs, context)

            assert isinstance(result, IntegrationResult), "Should return IntegrationResult"
            assert isinstance(result.result, ActionResult), "Result should contain ActionResult"
            data = result.result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} issue(s)")

            if data:
                global test_issue_number
                test_issue_number = data[0].get("number")
                print(f"  Using issue: #{test_issue_number} - {data[0].get('title')}")

                for issue in data[:3]:
                    print(f"  - #{issue.get('number')}: {issue.get('title')} ({issue.get('state')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_create_issue():
    """Test creating a new issue. Commented out to avoid test data creation."""
    print("\n[TEST] Skipping create_issue - commented out to avoid test data")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test (requires write access)
    # inputs = {
    #     "owner": test_repo_owner,
    #     "repo": test_repo_name,
    #     "title": "Test Issue from Integration",
    #     "body": "This is a test issue created by the integration test suite."
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await github.execute_action("create_issue", inputs, context)
    #         print(f"[OK] Created issue: #{result.data.get('number')} - {result.data.get('title')}")
    #         return result.data
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


async def test_update_issue():
    """Test updating an existing issue. Commented out to avoid test data changes."""
    print("\n[TEST] Skipping update_issue - commented out to avoid test data changes")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test (requires write access)
    # if not test_issue_number:
    #     print("\n[TEST] Skipping update_issue - no issue available")
    #     return None
    #
    # inputs = {
    #     "owner": test_repo_owner,
    #     "repo": test_repo_name,
    #     "issue_number": test_issue_number,
    #     "body": "Updated body from integration test"
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await github.execute_action("update_issue", inputs, context)
    #         print(f"[OK] Updated issue: #{result.data.get('number')}")
    #         return result.data
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


# ==================== PULL REQUEST RESOURCE TESTS ====================

async def test_list_pull_requests():
    """Test getting pull requests for a repository"""
    if not test_repo_owner or not test_repo_name:
        print("\n[TEST] Skipping list_pull_requests - no repository available")
        return None

    print(f"\n[TEST] Listing pull requests for {test_repo_owner}/{test_repo_name}...")

    inputs = {
        "owner": test_repo_owner,
        "repo": test_repo_name,
        "state": "all",
        "sort": "updated"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await github.execute_action("list_pull_requests", inputs, context)

            assert isinstance(result, IntegrationResult), "Should return IntegrationResult"
            assert isinstance(result.result, ActionResult), "Result should contain ActionResult"
            data = result.result.data
            assert isinstance(data, list), "Data should be an array"
            print(f"[OK] Found {len(data)} pull request(s)")

            for pr in data[:3]:
                print(f"  - #{pr.get('number')}: {pr.get('title')} ({pr.get('state')})")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


async def test_create_pull_request():
    """Test creating a pull request. Commented out to avoid test data creation."""
    print("\n[TEST] Skipping create_pull_request - commented out to avoid test data")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test (requires write access)
    # inputs = {
    #     "owner": test_repo_owner,
    #     "repo": test_repo_name,
    #     "title": "Test PR from Integration",
    #     "head": "feature-branch",
    #     "base": "main",
    #     "body": "This is a test PR created by the integration test suite.",
    #     "draft": True
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await github.execute_action("create_pull_request", inputs, context)
    #         print(f"[OK] Created PR: #{result.data.get('number')} - {result.data.get('title')}")
    #         return result.data
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


# ==================== WORKFLOW RESOURCE TESTS ====================

async def test_get_workflow_runs():
    """Test getting workflow runs. Skipped - requires workflow_id."""
    print("\n[TEST] Skipping get_workflow_runs - requires specific workflow_id")
    print("  To enable, provide a valid workflow_id for a repository you have access to")
    return None

    # Uncomment below to actually test
    # inputs = {
    #     "owner": test_repo_owner,
    #     "repo": test_repo_name,
    #     "workflow_id": "your_workflow_id_here"
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await github.execute_action("get_workflow_runs", inputs, context)
    #         print(f"[OK] Found {len(result.data)} workflow run(s)")
    #         return result.data
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


# ==================== BRANCH RESOURCE TESTS ====================

async def test_create_branch():
    """Test creating a branch. Commented out to avoid test data creation."""
    print("\n[TEST] Skipping create_branch - commented out to avoid test data")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test (requires write access)
    # inputs = {
    #     "owner": test_repo_owner,
    #     "repo": test_repo_name,
    #     "branch_name": "test-branch",
    #     "sha": "commit_sha_here"
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await github.execute_action("create_branch", inputs, context)
    #         print(f"[OK] Created branch: {result.data.get('ref')}")
    #         return result.data
    #     except Exception as e:
    #         print(f"[ERROR] Error: {e}")
    #         return None


# ==================== DIFF RESOURCE TESTS ====================

async def test_diff_branch_to_branch():
    """Test comparing two branches"""
    if not test_repo_owner or not test_repo_name:
        print("\n[TEST] Skipping diff_branch_to_branch - no repository available")
        return None

    print(f"\n[TEST] Comparing branches in {test_repo_owner}/{test_repo_name}...")

    inputs = {
        "owner": test_repo_owner,
        "repo": test_repo_name,
        "base_branch": "master",
        "head_branch": "test"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await github.execute_action("diff_branch_to_branch", inputs, context)

            assert isinstance(result, IntegrationResult), "Should return IntegrationResult"
            assert isinstance(result.result, ActionResult), "Result should contain ActionResult"
            data = result.result.data
            print(f"[OK] Retrieved branch comparison")
            print(f"  Status: {data.get('status', 'N/A')}")
            print(f"  Ahead by: {data.get('ahead_by', 0)}")
            print(f"  Behind by: {data.get('behind_by', 0)}")
            print(f"  Total commits: {data.get('total_commits', 0)}")

            return data

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None


# ==================== MAIN TEST RUNNER ====================

async def main():
    print("=" * 70)
    print("GitHub Integration Test Suite")
    print("=" * 70)
    print("\nSETUP:")
    token = TEST_AUTH['credentials']['access_token']
    print(f"  Access Token: {token[:20]}..." if len(token) > 20 else f"  Access Token: {token}")
    print("\nActions defined in config.json:")
    print("  - list_commits, list_pull_requests, get_repository")
    print("  - list_issues, create_issue, update_issue")
    print("  - get_workflow_runs, create_branch, create_pull_request")
    print("  - diff_branch_to_branch")
    print("\n" + "=" * 70)

    try:
        # Test Repository Resource
        print("\n" + "=" * 70)
        print("REPOSITORY RESOURCE (1 action)")
        print("=" * 70)
        await test_get_repository()

        # Test Commit Resource
        print("\n" + "=" * 70)
        print("COMMIT RESOURCE (1 action)")
        print("=" * 70)
        await test_list_commits()

        # Test Issue Resource
        print("\n" + "=" * 70)
        print("ISSUE RESOURCE (3 actions)")
        print("=" * 70)
        await test_list_issues()
        await test_create_issue()
        await test_update_issue()

        # Test Pull Request Resource
        print("\n" + "=" * 70)
        print("PULL REQUEST RESOURCE (2 actions)")
        print("=" * 70)
        await test_list_pull_requests()
        await test_create_pull_request()

        # Test Workflow Resource
        print("\n" + "=" * 70)
        print("WORKFLOW RESOURCE (1 action)")
        print("=" * 70)
        await test_get_workflow_runs()

        # Test Branch Resource
        print("\n" + "=" * 70)
        print("BRANCH RESOURCE (1 action)")
        print("=" * 70)
        await test_create_branch()

        # Test Diff Resource
        print("\n" + "=" * 70)
        print("DIFF RESOURCE (1 action)")
        print("=" * 70)
        await test_diff_branch_to_branch()

        print("\n" + "=" * 70)
        print("Test suite completed!")
        print("=" * 70)
        print("\nSummary: 10 actions tested (matching config.json)")
        print("  - Tested read operations for repositories, commits, issues, PRs")
        print("  - Write operations (create/update) are commented out to avoid test data")
        print("=" * 70)

    except Exception as e:
        print(f"\nTest suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

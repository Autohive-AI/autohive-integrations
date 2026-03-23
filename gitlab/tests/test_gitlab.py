# Test suite for GitLab integration (Read-Only)
import asyncio
from context import gitlab
from autohive_integrations_sdk import ExecutionContext


# ---- User Tests ----

async def test_get_current_user():
    """Test getting current user info."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_current_user", {}, context)
            print(f"Get Current User Result: {result}")
            assert result.data.get('result') == True
            assert 'user' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_current_user: {e}")
            return None


# ---- Project Tests ----

async def test_list_projects():
    """Test listing projects."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"owned": True, "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_projects", inputs, context)
            print(f"List Projects Result: {result}")
            assert result.data.get('result') == True
            assert 'projects' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_projects: {e}")
            return None


async def test_get_project():
    """Test getting project details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id_or_path", "statistics": True}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_project", inputs, context)
            print(f"Get Project Result: {result}")
            assert result.data.get('result') == True
            assert 'project' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_project: {e}")
            return None


# ---- Issue Tests ----

async def test_list_issues():
    """Test listing issues."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "state": "opened", "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_issues", inputs, context)
            print(f"List Issues Result: {result}")
            assert result.data.get('result') == True
            assert 'issues' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_issues: {e}")
            return None


async def test_get_issue():
    """Test getting issue details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "issue_iid": 1}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_issue", inputs, context)
            print(f"Get Issue Result: {result}")
            assert result.data.get('result') == True
            assert 'issue' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_issue: {e}")
            return None


# ---- Merge Request Tests ----

async def test_list_merge_requests():
    """Test listing merge requests."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "state": "opened", "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_merge_requests", inputs, context)
            print(f"List Merge Requests Result: {result}")
            assert result.data.get('result') == True
            assert 'merge_requests' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_merge_requests: {e}")
            return None


async def test_get_merge_request():
    """Test getting merge request details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "merge_request_iid": 1}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_merge_request", inputs, context)
            print(f"Get Merge Request Result: {result}")
            assert result.data.get('result') == True
            assert 'merge_request' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_merge_request: {e}")
            return None


async def test_get_merge_request_changes():
    """Test getting merge request changes/diff."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "merge_request_iid": 1}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_merge_request_changes", inputs, context)
            print(f"Get Merge Request Changes Result: {result}")
            assert result.data.get('result') == True
            assert 'changes' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_merge_request_changes: {e}")
            return None


async def test_list_merge_request_commits():
    """Test listing merge request commits."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "merge_request_iid": 1, "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_merge_request_commits", inputs, context)
            print(f"List Merge Request Commits Result: {result}")
            assert result.data.get('result') == True
            assert 'commits' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_merge_request_commits: {e}")
            return None


# ---- Branch Tests ----

async def test_list_branches():
    """Test listing branches."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "per_page": 20}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_branches", inputs, context)
            print(f"List Branches Result: {result}")
            assert result.data.get('result') == True
            assert 'branches' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_branches: {e}")
            return None


async def test_get_branch():
    """Test getting branch details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "branch": "main"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_branch", inputs, context)
            print(f"Get Branch Result: {result}")
            assert result.data.get('result') == True
            assert 'branch' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_branch: {e}")
            return None


# ---- Commit Tests ----

async def test_list_commits():
    """Test listing commits."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "ref_name": "main", "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_commits", inputs, context)
            print(f"List Commits Result: {result}")
            assert result.data.get('result') == True
            assert 'commits' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_commits: {e}")
            return None


async def test_get_commit():
    """Test getting commit details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "sha": "your_commit_sha", "stats": True}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_commit", inputs, context)
            print(f"Get Commit Result: {result}")
            assert result.data.get('result') == True
            assert 'commit' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_commit: {e}")
            return None


async def test_get_commit_diff():
    """Test getting commit diff."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "sha": "your_commit_sha"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_commit_diff", inputs, context)
            print(f"Get Commit Diff Result: {result}")
            assert result.data.get('result') == True
            assert 'diffs' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_commit_diff: {e}")
            return None


# ---- Pipeline Tests ----

async def test_list_pipelines():
    """Test listing pipelines."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_pipelines", inputs, context)
            print(f"List Pipelines Result: {result}")
            assert result.data.get('result') == True
            assert 'pipelines' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_pipelines: {e}")
            return None


async def test_get_pipeline():
    """Test getting pipeline details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "pipeline_id": 12345}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_pipeline", inputs, context)
            print(f"Get Pipeline Result: {result}")
            assert result.data.get('result') == True
            assert 'pipeline' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_pipeline: {e}")
            return None


async def test_list_pipeline_jobs():
    """Test listing pipeline jobs."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "pipeline_id": 12345, "per_page": 20}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_pipeline_jobs", inputs, context)
            print(f"List Pipeline Jobs Result: {result}")
            assert result.data.get('result') == True
            assert 'jobs' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_pipeline_jobs: {e}")
            return None


# ---- Repository Tests ----

async def test_list_repository_tree():
    """Test listing repository tree."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "ref": "main", "recursive": False}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_repository_tree", inputs, context)
            print(f"List Repository Tree Result: {result}")
            assert result.data.get('result') == True
            assert 'tree' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_repository_tree: {e}")
            return None


async def test_get_file():
    """Test getting file content (base64)."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "project_id": "your_project_id",
        "file_path": "README.md",
        "ref": "main"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_file", inputs, context)
            print(f"Get File Result: {result}")
            assert result.data.get('result') == True
            assert 'file' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_file: {e}")
            return None


async def test_get_file_raw():
    """Test getting raw file content."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "project_id": "your_project_id",
        "file_path": "README.md",
        "ref": "main"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_file_raw", inputs, context)
            print(f"Get File Raw Result: {result}")
            assert result.data.get('result') == True
            assert 'content' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_file_raw: {e}")
            return None


async def test_compare_branches():
    """Test comparing branches."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "project_id": "your_project_id",
        "from": "main",
        "to": "feature-branch"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("compare_branches", inputs, context)
            print(f"Compare Branches Result: {result}")
            assert result.data.get('result') == True
            assert 'comparison' in result.data
            return result
        except Exception as e:
            print(f"Error testing compare_branches: {e}")
            return None


# ---- Container Registry Tests ----

async def test_list_container_registry_repositories():
    """Test listing container registry repositories."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "tags_count": True}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_container_registry_repositories", inputs, context)
            print(f"List Container Registry Repositories Result: {result}")
            assert result.data.get('result') == True
            assert 'repositories' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_container_registry_repositories: {e}")
            return None


async def test_get_container_registry_repository():
    """Test getting container registry repository details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "repository_id": 12345, "tags": True}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_container_registry_repository", inputs, context)
            print(f"Get Container Registry Repository Result: {result}")
            assert result.data.get('result') == True
            assert 'repository' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_container_registry_repository: {e}")
            return None


async def test_list_container_registry_tags():
    """Test listing container registry tags."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"project_id": "your_project_id", "repository_id": 12345, "per_page": 20}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("list_container_registry_tags", inputs, context)
            print(f"List Container Registry Tags Result: {result}")
            assert result.data.get('result') == True
            assert 'tags' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_container_registry_tags: {e}")
            return None


async def test_get_container_registry_tag():
    """Test getting container registry tag details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "project_id": "your_project_id",
        "repository_id": 12345,
        "tag_name": "latest"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await gitlab.execute_action("get_container_registry_tag", inputs, context)
            print(f"Get Container Registry Tag Result: {result}")
            assert result.data.get('result') == True
            assert 'tag' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_container_registry_tag: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("GitLab Integration Test Suite (Read-Only)")
    print("=" * 60)

    test_functions = [
        # User
        ("Get Current User", test_get_current_user),
        # Projects
        ("List Projects", test_list_projects),
        ("Get Project", test_get_project),
        # Issues
        ("List Issues", test_list_issues),
        ("Get Issue", test_get_issue),
        # Merge Requests
        ("List Merge Requests", test_list_merge_requests),
        ("Get Merge Request", test_get_merge_request),
        ("Get Merge Request Changes", test_get_merge_request_changes),
        ("List Merge Request Commits", test_list_merge_request_commits),
        # Branches
        ("List Branches", test_list_branches),
        ("Get Branch", test_get_branch),
        # Commits
        ("List Commits", test_list_commits),
        ("Get Commit", test_get_commit),
        ("Get Commit Diff", test_get_commit_diff),
        # Pipelines
        ("List Pipelines", test_list_pipelines),
        ("Get Pipeline", test_get_pipeline),
        ("List Pipeline Jobs", test_list_pipeline_jobs),
        # Repository
        ("List Repository Tree", test_list_repository_tree),
        ("Get File", test_get_file),
        ("Get File Raw", test_get_file_raw),
        ("Compare Branches", test_compare_branches),
        # Container Registry
        ("List Container Registry Repositories", test_list_container_registry_repositories),
        ("Get Container Registry Repository", test_get_container_registry_repository),
        ("List Container Registry Tags", test_list_container_registry_tags),
        ("Get Container Registry Tag", test_get_container_registry_tag),
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

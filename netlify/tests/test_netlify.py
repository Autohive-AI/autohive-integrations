# Test suite for Netlify integration
import asyncio
from context import netlify
from autohive_integrations_sdk import ExecutionContext


async def test_list_sites():
    """Test listing all sites."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("list_sites", {}, context)
            print(f"List Sites Result: {result}")
            assert result.data.get('result') == True
            assert 'sites' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_sites: {e}")
            return None


async def test_create_site():
    """Test creating a new site."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"name": "test-site-autohive"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("create_site", inputs, context)
            print(f"Create Site Result: {result}")
            assert result.data.get('result') == True
            assert 'site' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_site: {e}")
            return None


async def test_get_site():
    """Test getting site details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"site_id": "your_site_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("get_site", inputs, context)
            print(f"Get Site Result: {result}")
            assert result.data.get('result') == True
            assert 'site' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_site: {e}")
            return None


async def test_list_deploys():
    """Test listing deploys for a site."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"site_id": "your_site_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("list_deploys", inputs, context)
            print(f"List Deploys Result: {result}")
            assert result.data.get('result') == True
            assert 'deploys' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_deploys: {e}")
            return None


async def test_create_deploy():
    """Test creating a deploy with files."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "site_id": "your_site_id_here",
        "files": {
            "/index.html": "<html><body><h1>Hello from Autohive!</h1></body></html>"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("create_deploy", inputs, context)
            print(f"Create Deploy Result: {result}")
            assert result.data.get('result') == True
            assert 'deploy' in result.data
            assert 'deploy_url' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_deploy: {e}")
            return None


async def test_get_deploy():
    """Test getting deploy details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"deploy_id": "your_deploy_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await netlify.execute_action("get_deploy", inputs, context)
            print(f"Get Deploy Result: {result}")
            assert result.data.get('result') == True
            assert 'deploy' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_deploy: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Netlify Integration Test Suite")
    print("=" * 60)

    test_functions = [
        ("List Sites", test_list_sites),
        ("Create Site", test_create_site),
        ("Get Site", test_get_site),
        ("List Deploys", test_list_deploys),
        ("Create Deploy", test_create_deploy),
        ("Get Deploy", test_get_deploy),
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

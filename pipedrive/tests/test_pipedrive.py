"""
Pipedrive Integration Tests

To run these tests:
1. Set up your Pipedrive API token
2. Update the test configuration below with your actual credentials
3. Run: python tests/test_pipedrive.py
"""

import asyncio
import sys
import os

# Add parent directory to path to import the integration
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipedrive import pipedrive
from autohive_integrations_sdk import ExecutionContext


# ==========================================
# TEST CONFIGURATION
# ==========================================
# Replace these with your actual test credentials
TEST_API_TOKEN = "YOUR_PIPEDRIVE_API_TOKEN"

# Test data - will be created and cleaned up during tests
TEST_DEAL_TITLE = "Test Deal - Integration Test"
TEST_PERSON_NAME = "Test Person - Integration Test"
TEST_ORG_NAME = "Test Organization - Integration Test"
TEST_ACTIVITY_SUBJECT = "Test Activity - Integration Test"


def create_mock_context():
    """Create a mock ExecutionContext with Pipedrive credentials."""

    class MockFetch:
        def __init__(self, token):
            self.token = token

        async def __call__(self, url, method="GET", json=None, params=None):
            """Mock fetch implementation for testing."""
            import aiohttp

            # Add API token to params
            if params is None:
                params = {}
            params['api_token'] = self.token

            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url, params=params) as response:
                        return await response.json()
                elif method == "POST":
                    async with session.post(url, json=json, params=params) as response:
                        return await response.json()
                elif method == "PUT":
                    async with session.put(url, json=json, params=params) as response:
                        return await response.json()
                elif method == "DELETE":
                    async with session.delete(url, params=params) as response:
                        return await response.json()
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
    context = ExecutionContext(
        auth={
            "type": "api_token",
            "credentials": {
                "api_token": TEST_API_TOKEN
            }
        },
        fetch=MockFetch(TEST_API_TOKEN)
    )

    return context


async def test_deal_lifecycle():
    """Test creating, retrieving, updating, and deleting a deal."""
    print("\n" + "="*60)
    print("Testing Deal Lifecycle")
    print("="*60)

    context = create_mock_context()
    deal_id = None

    try:
        # 1. Create a deal
        print("\n1. Creating deal...")
        create_action = pipedrive.get_action("create_deal")
        result = await create_action.execute({
            "title": TEST_DEAL_TITLE,
            "value": 10000,
            "currency": "USD",
            "status": "open"
        }, context)

        assert result.data['result'], f"Failed to create deal: {result.data.get('error')}"
        deal_id = result.data['deal']['id']
        print(f"✓ Deal created with ID: {deal_id}")
        print(f"  Title: {result.data['deal']['title']}")

        # 2. Get the deal
        print("\n2. Retrieving deal...")
        get_action = pipedrive.get_action("get_deal")
        result = await get_action.execute({"deal_id": deal_id}, context)

        assert result.data['result'], f"Failed to get deal: {result.data.get('error')}"
        print(f"✓ Deal retrieved successfully")
        print(f"  Value: {result.data['deal']['value']} {result.data['deal']['currency']}")

        # 3. Update the deal
        print("\n3. Updating deal...")
        update_action = pipedrive.get_action("update_deal")
        result = await update_action.execute({
            "deal_id": deal_id,
            "value": 15000,
            "title": TEST_DEAL_TITLE + " (Updated)"
        }, context)

        assert result.data['result'], f"Failed to update deal: {result.data.get('error')}"
        print(f"✓ Deal updated successfully")
        print(f"  New value: {result.data['deal']['value']}")

        # 4. List deals
        print("\n4. Listing deals...")
        list_action = pipedrive.get_action("list_deals")
        result = await list_action.execute({"limit": 5}, context)

        assert result.data['result'], f"Failed to list deals: {result.data.get('error')}"
        print(f"✓ Listed {len(result.data['deals'])} deals")

        # 5. Delete the deal
        print("\n5. Deleting deal...")
        delete_action = pipedrive.get_action("delete_deal")
        result = await delete_action.execute({"deal_id": deal_id}, context)

        assert result.data['result'], f"Failed to delete deal: {result.data.get('error')}"
        print(f"✓ Deal deleted successfully")

        print("\n✓ Deal lifecycle test completed successfully!")

    except Exception as e:
        print(f"\n✗ Error during deal lifecycle test: {str(e)}")
        raise
    finally:
        # Cleanup: ensure deal is deleted
        if deal_id:
            try:
                delete_action = pipedrive.get_action("delete_deal")
                await delete_action.execute({"deal_id": deal_id}, context)
            except Exception:
                pass  # Cleanup errors can be ignored


async def test_person_operations():
    """Test person (contact) operations."""
    print("\n" + "="*60)
    print("Testing Person Operations")
    print("="*60)

    context = create_mock_context()
    person_id = None

    try:
        # Create a person
        print("\n1. Creating person...")
        create_action = pipedrive.get_action("create_person")
        result = await create_action.execute({
            "name": TEST_PERSON_NAME,
            "email": "test@example.com",
            "phone": "+1234567890"
        }, context)

        assert result.data['result'], f"Failed to create person: {result.data.get('error')}"
        person_id = result.data['person']['id']
        print(f"✓ Person created with ID: {person_id}")

        # Get the person
        print("\n2. Retrieving person...")
        get_action = pipedrive.get_action("get_person")
        result = await get_action.execute({"person_id": person_id}, context)

        assert result.data['result'], f"Failed to get person: {result.data.get('error')}"
        print(f"✓ Person retrieved: {result.data['person']['name']}")

        # Delete the person
        print("\n3. Deleting person...")
        delete_action = pipedrive.get_action("delete_person")
        result = await delete_action.execute({"person_id": person_id}, context)

        assert result.data['result'], f"Failed to delete person: {result.data.get('error')}"
        print(f"✓ Person deleted successfully")

        print("\n✓ Person operations test completed successfully!")

    except Exception as e:
        print(f"\n✗ Error during person operations test: {str(e)}")
        raise
    finally:
        # Cleanup
        if person_id:
            try:
                delete_action = pipedrive.get_action("delete_person")
                await delete_action.execute({"person_id": person_id}, context)
            except Exception:
                pass  # Cleanup errors can be ignored


async def test_activity_operations():
    """Test activity operations."""
    print("\n" + "="*60)
    print("Testing Activity Operations")
    print("="*60)

    context = create_mock_context()
    activity_id = None

    try:
        # Create an activity
        print("\n1. Creating activity...")
        create_action = pipedrive.get_action("create_activity")
        result = await create_action.execute({
            "subject": TEST_ACTIVITY_SUBJECT,
            "type": "task",
            "due_date": "2025-12-31"
        }, context)

        assert result.data['result'], f"Failed to create activity: {result.data.get('error')}"
        activity_id = result.data['activity']['id']
        print(f"✓ Activity created with ID: {activity_id}")

        # Update activity to mark as done
        print("\n2. Marking activity as done...")
        update_action = pipedrive.get_action("update_activity")
        result = await update_action.execute({
            "activity_id": activity_id,
            "done": 1
        }, context)

        assert result.data['result'], f"Failed to update activity: {result.data.get('error')}"
        print(f"✓ Activity marked as done")

        # Delete the activity
        print("\n3. Deleting activity...")
        delete_action = pipedrive.get_action("delete_activity")
        result = await delete_action.execute({"activity_id": activity_id}, context)

        assert result.data['result'], f"Failed to delete activity: {result.data.get('error')}"
        print(f"✓ Activity deleted successfully")

        print("\n✓ Activity operations test completed successfully!")

    except Exception as e:
        print(f"\n✗ Error during activity operations test: {str(e)}")
        raise
    finally:
        # Cleanup
        if activity_id:
            try:
                delete_action = pipedrive.get_action("delete_activity")
                await delete_action.execute({"activity_id": activity_id}, context)
            except Exception:
                pass  # Cleanup errors can be ignored


async def test_pipeline_operations():
    """Test pipeline and stage operations."""
    print("\n" + "="*60)
    print("Testing Pipeline Operations")
    print("="*60)

    context = create_mock_context()

    try:
        # List pipelines
        print("\n1. Listing pipelines...")
        list_action = pipedrive.get_action("list_pipelines")
        result = await list_action.execute({}, context)

        assert result.data['result'], f"Failed to list pipelines: {result.data.get('error')}"
        print(f"✓ Found {len(result.data['pipelines'])} pipelines")

        if result.data['pipelines']:
            pipeline_id = result.data['pipelines'][0]['id']
            print(f"  First pipeline: {result.data['pipelines'][0]['name']} (ID: {pipeline_id})")

            # Get pipeline details
            print("\n2. Getting pipeline details...")
            get_action = pipedrive.get_action("get_pipeline")
            result = await get_action.execute({"pipeline_id": pipeline_id}, context)

            assert result.data['result'], f"Failed to get pipeline: {result.data.get('error')}"
            print(f"✓ Pipeline details retrieved")

            # List stages for this pipeline
            print("\n3. Listing stages...")
            stages_action = pipedrive.get_action("list_stages")
            result = await stages_action.execute({"pipeline_id": pipeline_id}, context)

            assert result.data['result'], f"Failed to list stages: {result.data.get('error')}"
            print(f"✓ Found {len(result.data['stages'])} stages")

        print("\n✓ Pipeline operations test completed successfully!")

    except Exception as e:
        print(f"\n✗ Error during pipeline operations test: {str(e)}")
        raise


async def test_search():
    """Test search functionality."""
    print("\n" + "="*60)
    print("Testing Search")
    print("="*60)

    context = create_mock_context()

    try:
        print("\n1. Searching for items...")
        search_action = pipedrive.get_action("search")
        result = await search_action.execute({
            "term": "test",
            "limit": 5
        }, context)

        assert result.data['result'], f"Failed to search: {result.data.get('error')}"
        print(f"✓ Search completed, found {len(result.data['items'])} items")

        print("\n✓ Search test completed successfully!")

    except Exception as e:
        print(f"\n✗ Error during search test: {str(e)}")
        raise


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("PIPEDRIVE INTEGRATION TEST SUITE")
    print("="*60)

    if TEST_API_TOKEN == "YOUR_PIPEDRIVE_API_TOKEN":
        print("\n✗ ERROR: Please update TEST_API_TOKEN with your actual Pipedrive API token")
        return

    try:
        await test_deal_lifecycle()
        await test_person_operations()
        await test_activity_operations()
        await test_pipeline_operations()
        await test_search()

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)

    except Exception as e:
        print("\n" + "="*60)
        print(f"✗ TEST SUITE FAILED: {str(e)}")
        print("="*60)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())

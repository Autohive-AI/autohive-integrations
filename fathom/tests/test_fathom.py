# Test suite for Fathom integration
import asyncio
from context import fathom
from autohive_integrations_sdk import ExecutionContext

async def test_list_meetings():
    """Test listing meetings"""
    print("\n--- Testing list_meetings ---")

    # Setup mock auth object
    auth = {
        "api_key": "test_api_key"
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await fathom.execute_action("list_meetings", inputs, context)
            print(f"✓ list_meetings returned {len(result.get('items', []))} meetings")
            print(f"  Limit: {result.get('limit', 0)}")
            if result.get("next_cursor"):
                print(f"  Next cursor: {result['next_cursor']}")
        except Exception as e:
            print(f"✗ Error testing list_meetings: {str(e)}")

async def test_get_transcript():
    """Test getting recording transcript"""
    print("\n--- Testing get_transcript ---")

    auth = {
        "api_key": "test_api_key"
    }

    inputs = {
        "recording_id": "test_recording_id_123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await fathom.execute_action("get_transcript", inputs, context)
            print(f"✓ get_transcript returned {len(result.get('transcript', []))} segments")
        except Exception as e:
            print(f"✗ Error testing get_transcript: {str(e)}")

async def test_list_teams():
    """Test listing teams"""
    print("\n--- Testing list_teams ---")

    auth = {
        "api_key": "test_api_key"
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await fathom.execute_action("list_teams", inputs, context)
            print(f"✓ list_teams returned {len(result.get('teams', []))} teams")
        except Exception as e:
            print(f"✗ Error testing list_teams: {str(e)}")

async def test_list_team_members():
    """Test listing team members"""
    print("\n--- Testing list_team_members ---")

    auth = {
        "api_key": "test_api_key"
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await fathom.execute_action("list_team_members", inputs, context)
            print(f"✓ list_team_members returned {len(result.get('team_members', []))} members")
        except Exception as e:
            print(f"✗ Error testing list_team_members: {str(e)}")

async def main():
    print("========================================")
    print("Testing Fathom Integration")
    print("========================================")

    await test_list_meetings()
    await test_get_transcript()
    await test_list_teams()
    await test_list_team_members()

    print("\n========================================")
    print("Tests completed!")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(main())

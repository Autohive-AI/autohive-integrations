# Quick test script for Zoom integration
import asyncio
import sys
import os

# Get the zoom directory path
ZOOM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(ZOOM_DIR, "config.json")

sys.path.insert(0, ZOOM_DIR)
sys.path.insert(0, os.path.join(ZOOM_DIR, "dependencies"))

from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ConnectedAccountHandler, ConnectedAccountInfo
from typing import Dict, Any, Optional
from urllib.parse import quote

# Load integration from config.json with explicit path
zoom = Integration.load(CONFIG_PATH)

# ---- Constants ----
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"

def get_headers() -> Dict[str, str]:
    return {"Content-Type": "application/json"}

def encode_meeting_id(meeting_id: str) -> str:
    if meeting_id.startswith('/') or '//' in meeting_id:
        return quote(quote(meeting_id, safe=''), safe='')
    return meeting_id

# ---- API Client Class ----
class ZoomAPIClient:
    def __init__(self, context: ExecutionContext):
        self.context = context
        self.base_url = ZOOM_API_BASE_URL

    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        headers = get_headers()
        if method == "GET":
            return await self.context.fetch(url, params=params, headers=headers)
        elif method == "POST":
            return await self.context.fetch(url, method="POST", json=data, headers=headers)
        elif method == "PATCH":
            return await self.context.fetch(url, method="PATCH", json=data, headers=headers)
        elif method == "DELETE":
            response = await self.context.fetch(url, method="DELETE", params=params, headers=headers)
            return response if response else {"success": True}
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

# ---- Register Action Handlers ----

@zoom.connected_account()
class ZoomConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        client = ZoomAPIClient(context)
        user_data = await client._make_request("users/me")
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")
        return ConnectedAccountInfo(
            email=user_data.get("email"),
            username=user_data.get("display_name") or f"{first_name} {last_name}".strip(),
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            avatar_url=user_data.get("pic_url"),
            organization=user_data.get("company") or user_data.get("dept"),
            user_id=user_data.get("id")
        )

@zoom.action("get_user")
class GetUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")
            response = await client._make_request(f"users/{user_id}")
            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "first_name": response.get("first_name", ""),
                    "last_name": response.get("last_name", ""),
                    "email": response.get("email", ""),
                    "type": response.get("type"),
                    "timezone": response.get("timezone", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)

@zoom.action("list_meetings")
class ListMeetingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")
            params = {"type": inputs.get("type", "scheduled"), "page_size": min(inputs.get("page_size", 30), 300)}
            if inputs.get("next_page_token"):
                params["next_page_token"] = inputs["next_page_token"]
            response = await client._make_request(f"users/{user_id}/meetings", params=params)
            meetings = [{"id": m.get("id"), "topic": m.get("topic", ""), "start_time": m.get("start_time", ""), "join_url": m.get("join_url", "")} for m in response.get("meetings", [])]
            return ActionResult(data={"meetings": meetings, "total_records": response.get("total_records", len(meetings)), "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"meetings": [], "total_records": 0, "result": False, "error": str(e)}, cost_usd=0.0)

@zoom.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            params = {"page_size": min(inputs.get("page_size", 50), 1000)}
            if inputs.get("next_page_token"):
                params["next_page_token"] = inputs["next_page_token"]
            if inputs.get("type"):
                params["type"] = inputs["type"]
            if inputs.get("search_key"):
                params["search_key"] = inputs["search_key"]
            response = await client._make_request("contacts", params=params)
            contacts = [{"id": c.get("id", ""), "email": c.get("email", ""), "first_name": c.get("first_name", ""), "last_name": c.get("last_name", "")} for c in response.get("contacts", [])]
            return ActionResult(data={"contacts": contacts, "total_records": response.get("total_records", len(contacts)), "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contacts": [], "total_records": 0, "result": False, "error": str(e)}, cost_usd=0.0)

@zoom.action("get_user_permissions")
class GetUserPermissionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")
            response = await client._make_request(f"users/{user_id}/permissions")
            return ActionResult(data={"permissions": response.get("permissions", []), "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"permissions": [], "result": False, "error": str(e)}, cost_usd=0.0)

# ---- Test Token ----
ACCESS_TOKEN = os.environ.get("ZOOM_ACCESS_TOKEN", "")

def get_data(result):
    """Extract data from IntegrationResult or ActionResult."""
    if hasattr(result, 'result') and hasattr(result.result, 'data'):
        return result.result.data
    elif hasattr(result, 'data'):
        return result.data
    elif hasattr(result, 'output'):
        return result.output
    return result

async def test_get_user():
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    inputs = {"user_id": "me"}
    async with ExecutionContext(auth=auth) as context:
        result = await zoom.execute_action("get_user", inputs, context)
        data = get_data(result)
        print("\n=== Get User Result ===")
        print(f"Success: {data.get('result')}")
        if data.get('result'):
            print(f"Name: {data.get('first_name')} {data.get('last_name')}")
            print(f"Email: {data.get('email')}")
            print(f"Timezone: {data.get('timezone')}")
        else:
            print(f"Error: {data.get('error')}")
        return result


async def test_list_meetings():
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    inputs = {"user_id": "me", "type": "scheduled", "page_size": 10}
    async with ExecutionContext(auth=auth) as context:
        result = await zoom.execute_action("list_meetings", inputs, context)
        data = get_data(result)
        print("\n=== List Meetings Result ===")
        print(f"Success: {data.get('result')}")
        print(f"Total Records: {data.get('total_records')}")
        if data.get('meetings'):
            for meeting in data['meetings'][:5]:
                print(f"  - {meeting.get('topic')} (ID: {meeting.get('id')})")
        else:
            print("  No meetings found")
        if data.get('error'):
            print(f"Error: {data.get('error')}")
        return result


async def test_list_contacts():
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    inputs = {"page_size": 50}
    async with ExecutionContext(auth=auth) as context:
        result = await zoom.execute_action("list_contacts", inputs, context)
        data = get_data(result)
        print("\n=== List Contacts Result ===")
        print(f"Success: {data.get('result')}")
        print(f"Total Records: {data.get('total_records')}")
        if data.get('contacts'):
            for contact in data['contacts'][:5]:
                print(f"  - {contact.get('first_name')} {contact.get('last_name')} ({contact.get('email')})")
        else:
            print("  No contacts found")
        if data.get('error'):
            print(f"Error: {data.get('error')}")
        return result


async def test_get_user_permissions():
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    inputs = {"user_id": "me"}
    async with ExecutionContext(auth=auth) as context:
        result = await zoom.execute_action("get_user_permissions", inputs, context)
        data = get_data(result)
        print("\n=== Get User Permissions Result ===")
        print(f"Success: {data.get('result')}")
        if data.get('permissions'):
            print(f"Permissions ({len(data['permissions'])} total):")
            for perm in data['permissions'][:10]:
                print(f"  - {perm}")
            if len(data['permissions']) > 10:
                print(f"  ... and {len(data['permissions']) - 10} more")
        if data.get('error'):
            print(f"Error: {data.get('error')}")
        return result


async def test_connected_account():
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    async with ExecutionContext(auth=auth) as context:
        result = await zoom.get_connected_account(context)
        # Handle both ConnectedAccountInfo and IntegrationResult
        if hasattr(result, 'email'):
            account_info = result
        elif hasattr(result, 'output'):
            account_info = result.output
        else:
            account_info = result
        print("\n=== Connected Account Info ===")
        if hasattr(account_info, 'email'):
            print(f"Email: {account_info.email}")
            print(f"Username: {account_info.username}")
            print(f"First Name: {account_info.first_name}")
            print(f"Last Name: {account_info.last_name}")
            print(f"Organization: {account_info.organization}")
            print(f"User ID: {account_info.user_id}")
        else:
            print(f"Result: {account_info}")
        return result


async def main():
    print("=" * 60)
    print("Testing Zoom Integration")
    print("=" * 60)

    try:
        await test_connected_account()
    except Exception as e:
        print(f"\nConnected Account Error: {e}")

    try:
        await test_get_user()
    except Exception as e:
        print(f"\nGet User Error: {e}")

    try:
        await test_list_meetings()
    except Exception as e:
        print(f"\nList Meetings Error: {e}")

    try:
        await test_list_contacts()
    except Exception as e:
        print(f"\nList Contacts Error: {e}")

    try:
        await test_get_user_permissions()
    except Exception as e:
        print(f"\nGet User Permissions Error: {e}")

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

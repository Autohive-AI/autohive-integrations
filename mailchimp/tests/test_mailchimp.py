# Manual testing/demo script for Mailchimp integration
import asyncio
from context import mailchimp
from autohive_integrations_sdk import ExecutionContext


async def test_get_lists():
    """Test retrieving all mailing lists."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"count": 10, "offset": 0}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_lists", inputs, context)
            print(f"Get Lists Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_lists: {e}")
            return None


async def test_get_list():
    """Test getting a specific mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"list_id": "your_list_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_list", inputs, context)
            print(f"Get List Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_list: {e}")
            return None


async def test_create_list():
    """Test creating a new mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "name": "Test List via Integration",
        "permission_reminder": "You signed up for updates on our website.",
        "contact": {
            "company": "Test Company",
            "address1": "123 Test Street",
            "city": "Test City",
            "state": "CA",
            "zip": "90210",
            "country": "US"
        },
        "campaign_defaults": {
            "from_name": "Test Sender",
            "from_email": "test@example.com",
            "subject": "Default Subject",
            "language": "en"
        },
        "email_type_option": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("create_list", inputs, context)
            print(f"Create List Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_list: {e}")
            return None


async def test_add_member():
    """Test adding a new member to a mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "email_address": "test@example.com",
        "status": "subscribed",
        "merge_fields": {
            "FNAME": "John",
            "LNAME": "Doe"
        },
        "tags": ["api-test"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("add_member", inputs, context)
            print(f"Add Member Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing add_member: {e}")
            return None


async def test_get_member():
    """Test getting a specific member from a mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "email_address": "test@example.com"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_member", inputs, context)
            print(f"Get Member Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_member: {e}")
            return None


async def test_update_member():
    """Test updating an existing member in a mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "email_address": "test@example.com",
        "merge_fields": {
            "FNAME": "Jane",
            "LNAME": "Smith"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("update_member", inputs, context)
            print(f"Update Member Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_member: {e}")
            return None


async def test_get_list_members():
    """Test getting all members from a mailing list."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "list_id": "your_list_id_here",
        "count": 10,
        "offset": 0,
        "status": "subscribed"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_list_members", inputs, context)
            print(f"Get List Members Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_list_members: {e}")
            return None


async def test_get_campaigns():
    """Test retrieving all campaigns."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"count": 10, "offset": 0}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_campaigns", inputs, context)
            print(f"Get Campaigns Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_campaigns: {e}")
            return None


async def test_create_campaign():
    """Test creating a new campaign."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "type": "regular",
        "list_id": "your_list_id_here",
        "subject_line": "Test Campaign Subject",
        "from_name": "Test Sender",
        "reply_to": "reply@example.com",
        "title": "Test Campaign Title"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("create_campaign", inputs, context)
            print(f"Create Campaign Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_campaign: {e}")
            return None


async def test_get_campaign():
    """Test getting a specific campaign."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"campaign_id": "your_campaign_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await mailchimp.execute_action("get_campaign", inputs, context)
            print(f"Get Campaign Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_campaign: {e}")
            return None


async def main():
    print("Testing Mailchimp Integration")
    print("=" * 60)
    print()
    print("NOTE: Replace 'your_access_token_here' and IDs with actual")
    print("      credentials before running tests.")
    print()
    print("=" * 60)
    print()

    # Test list management actions
    print("1. Testing get_lists...")
    await test_get_lists()
    print()

    print("2. Testing get_list...")
    await test_get_list()
    print()

    print("3. Testing create_list...")
    await test_create_list()
    print()

    # Test member management actions
    print("4. Testing add_member...")
    await test_add_member()
    print()

    print("5. Testing get_member...")
    await test_get_member()
    print()

    print("6. Testing update_member...")
    await test_update_member()
    print()

    print("7. Testing get_list_members...")
    await test_get_list_members()
    print()

    # Test campaign management actions
    print("8. Testing get_campaigns...")
    await test_get_campaigns()
    print()

    print("9. Testing create_campaign...")
    await test_create_campaign()
    print()

    print("10. Testing get_campaign...")
    await test_get_campaign()
    print()

    print("=" * 60)
    print("Testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

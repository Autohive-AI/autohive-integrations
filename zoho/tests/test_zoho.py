"""
Zoho CRM Integration Testbed
============================

Real API integration testing against Zoho CRM with placeholder credentials.

Prerequisites:
1. Zoho CRM account with API access enabled
2. OAuth 2.0 credentials from Zoho API Console
3. Access token obtained through OAuth flow
4. Existing records in CRM (for get/list operations)

Credential Setup:
- Access Token: Zoho API Console -> Client Credentials -> Authorization
- API Domain: Region-specific (www.zohoapis.com, www.zohoapis.eu, www.zohoapis.com.au)

Running Tests:
    python test_zoho.py

Notes:
- Makes real API calls - review Zoho rate limits
- Some tests require existing data in your CRM
- Create operations add records to your Zoho CRM
"""

import asyncio
import time
from context import zoho
from autohive_integrations_sdk import ExecutionContext


# =============================================================================
# CONFIGURATION - Update these values with your Zoho credentials
# =============================================================================
AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {
        "access_token": "<placeholder>",
        "api_domain": "www.zohoapis.com.au"  # Options: www.zohoapis.com (US), www.zohoapis.eu (EU), www.zohoapis.com.au (AU)
    }
}

# Replace with an actual CONTACT ID from your Zoho CRM (use list_contacts to find one)
# Note: This should be a Contact ID (e.g., 102732000000388354), NOT an Account ID
TEST_CONTACT_ID = "102732000000388354"  # Kris Marrier (Sample) from list_contacts
# =============================================================================


async def test_list_contacts():
    """Test listing contacts with pagination."""
    inputs = {
        "page": 1,
        "per_page": 10
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("list_contacts", inputs, context)
            # Access data from IntegrationResult.result.data
            result_data = result.result.data
            print(f"List Contacts Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'contacts' in result_data, "Response missing 'contacts' field"
            assert 'info' in result_data, "Response missing pagination 'info' field"
            print("✓ test_list_contacts passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing list_contacts: {e}")
            return None


async def test_create_contact():
    """Test creating a new contact."""
    # Use timestamp to ensure unique email each run
    timestamp = int(time.time())
    inputs = {
        "Last_Name": "Smith",
        "First_Name": "John",
        "Email": f"john.smith.{timestamp}@example.com",
        "Phone": "+1-555-0100"
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("create_contact", inputs, context)
            result_data = result.result.data
            print(f"Create Contact Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'contact' in result_data, "Response missing 'contact' field"
            assert result_data['contact'].get('id'), "Contact ID not returned"
            print("✓ test_create_contact passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing create_contact: {e}")
            return None


async def test_get_contact():
    """Test getting a specific contact by ID."""
    inputs = {
        "contact_id": TEST_CONTACT_ID
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("get_contact", inputs, context)
            result_data = result.result.data
            print(f"Get Contact Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'contact' in result_data, "Response missing 'contact' field"
            print("✓ test_get_contact passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing get_contact: {e}")
            return None


async def test_create_deal():
    """Test creating a new deal."""
    inputs = {
        "Deal_Name": "Enterprise Software Deal",
        "Amount": 50000,
        "Stage": "Proposal"
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("create_deal", inputs, context)
            result_data = result.result.data
            print(f"Create Deal Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'deal' in result_data, "Response missing 'deal' field"
            assert result_data['deal'].get('id'), "Deal ID not returned"
            print("✓ test_create_deal passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing create_deal: {e}")
            return None


async def test_list_deals():
    """Test listing deals with pagination."""
    inputs = {
        "page": 1,
        "per_page": 10
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("list_deals", inputs, context)
            result_data = result.result.data
            print(f"List Deals Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'deals' in result_data, "Response missing 'deals' field"
            assert 'info' in result_data, "Response missing pagination 'info' field"
            print("✓ test_list_deals passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing list_deals: {e}")
            return None


async def test_create_note():
    """Test creating a note on a contact record."""
    inputs = {
        "module": "Contacts",
        "record_id": TEST_CONTACT_ID,
        "Note_Title": "Discussion Notes",
        "Note_Content": "Q4 requirements discussed"
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("create_note", inputs, context)
            result_data = result.result.data
            print(f"Create Note Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'note' in result_data, "Response missing 'note' field"
            assert result_data['note'].get('id'), "Note ID not returned"
            print("✓ test_create_note passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing create_note: {e}")
            return None


async def test_get_contact_notes():
    """Test getting notes from a contact record."""
    inputs = {
        "module": "Contacts",
        "record_id": TEST_CONTACT_ID,
        "page": 1,
        "per_page": 10,
        "fields": ["Note_Title", "Note_Content", "Owner", "Created_Time"]
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("get_contact_notes", inputs, context)
            result_data = result.result.data
            print(f"Get Contact Notes Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'notes' in result_data, "Response missing 'notes' field"
            assert 'info' in result_data, "Response missing pagination 'info' field"
            print("✓ test_get_contact_notes passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing get_contact_notes: {e}")
            return None


async def test_execute_coql_query():
    """Test executing a COQL query."""
    inputs = {
        "select_query": "SELECT First_Name, Last_Name, Email FROM Contacts WHERE Last_Name is not null LIMIT 10"
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("execute_coql_query", inputs, context)
            result_data = result.result.data
            print(f"Execute COQL Query Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'data' in result_data, "Response missing 'data' field"
            assert 'info' in result_data, "Response missing 'info' field"
            print("✓ test_execute_coql_query passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing execute_coql_query: {e}")
            return None


async def test_list_leads():
    """Test listing leads with pagination."""
    inputs = {
        "page": 1,
        "per_page": 10
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await zoho.execute_action("list_leads", inputs, context)
            result_data = result.result.data
            print(f"List Leads Result: {result_data}")

            assert result_data.get('result') == True, f"Action failed: {result_data.get('error', 'Unknown error')}"
            assert 'leads' in result_data, "Response missing 'leads' field"
            assert 'info' in result_data, "Response missing pagination 'info' field"
            print("✓ test_list_leads passed")
            return result_data
        except Exception as e:
            print(f"✗ Error testing list_leads: {e}")
            return None


async def main():
    """Run all test functions sequentially."""
    print("=" * 70)
    print("Testing Zoho CRM Integration - 9 Actions")
    print("=" * 70)
    print()
    print("NOTE: Replace placeholders before running:")
    print("  - your_zoho_oauth_token_here: Your OAuth 2.0 access token")
    print("  - your_contact_id_here: An existing contact ID from your Zoho CRM")
    print("  - api_domain: Your datacenter (com, com.au, eu, etc.)")
    print()
    print("To obtain OAuth credentials:")
    print("  1. Go to Zoho API Console (https://api-console.zoho.com/)")
    print("  2. Create Server-based Application")
    print("  3. Generate access token with required scopes")
    print("  4. Note your datacenter domain (e.g., www.zohoapis.com.au)")
    print()
    print("=" * 70)
    print()

    # Contacts Module (3 tests)
    print("1. Testing list_contacts...")
    await test_list_contacts()
    print()

    print("2. Testing create_contact...")
    await test_create_contact()
    print()

    print("3. Testing get_contact...")
    await test_get_contact()
    print()

    # Deals Module (2 tests)
    print("4. Testing create_deal...")
    await test_create_deal()
    print()

    print("5. Testing list_deals...")
    await test_list_deals()
    print()

    # Notes Module (2 tests)
    print("6. Testing create_note...")
    await test_create_note()
    print()

    print("7. Testing get_contact_notes...")
    await test_get_contact_notes()
    print()

    # Query Module (1 test)
    print("8. Testing execute_coql_query...")
    await test_execute_coql_query()
    print()

    # Leads (1 test)
    print("9. Testing list_leads...")
    await test_list_leads()
    print()

    print("=" * 70)
    print("Testing completed - 9 actions tested!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

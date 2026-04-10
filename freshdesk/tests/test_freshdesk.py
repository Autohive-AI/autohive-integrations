# Testbed for Freshdesk integration
import asyncio
from context import freshdesk
from autohive_integrations_sdk import ExecutionContext


async def test_list_companies():
    """Test listing all companies."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("list_companies", inputs, context)
            print(f"List Companies Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_companies: {e}")
            return None


async def test_search_companies():
    """Test searching for companies by name."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"name": "Acme"}  # Replace with a company name that exists in your account

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("search_companies", inputs, context)
            print(f"Search Companies Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing search_companies: {e}")
            return None


async def test_create_company():
    """Test creating a new company."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {
        "name": "Test Company via Integration",
        "description": "A test company created via API",
        "domains": ["testcompany.com"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("create_company", inputs, context)
            print(f"Create Company Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_company: {e}")
            return None


async def test_get_company():
    """Test getting a specific company."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"company_id": 123456}  # Replace with actual company ID

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("get_company", inputs, context)
            print(f"Get Company Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_company: {e}")
            return None


async def test_create_ticket():
    """Test creating a new ticket."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {
        "subject": "Test Ticket",
        "description": "<p>This is a test ticket created via API integration.</p>",
        "email": "customer@example.com",
        "priority": 2,
        "status": 2,
        "tags": ["api-test"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("create_ticket", inputs, context)
            print(f"Create Ticket Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_ticket: {e}")
            return None


async def test_list_tickets():
    """Test listing all tickets."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("list_tickets", inputs, context)
            print(f"List Tickets Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_tickets: {e}")
            return None


async def test_get_ticket():
    """Test getting a specific ticket."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"ticket_id": 1}  # Replace with actual ticket ID

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("get_ticket", inputs, context)
            print(f"Get Ticket Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_ticket: {e}")
            return None


async def test_create_contact():
    """Test creating a new contact."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-0123",
        "job_title": "Software Engineer"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("create_contact", inputs, context)
            print(f"Create Contact Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_contact: {e}")
            return None


async def test_list_contacts():
    """Test listing all contacts."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"per_page": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("list_contacts", inputs, context)
            print(f"List Contacts Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_contacts: {e}")
            return None


async def test_search_contacts():
    """Test searching for contacts by name."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"term": "John"}  # Replace with a contact name that exists in your account

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("search_contacts", inputs, context)
            print(f"Search Contacts Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing search_contacts: {e}")
            return None


async def test_list_conversations():
    """Test listing conversations for a ticket."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {"ticket_id": 1}  # Replace with actual ticket ID

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("list_conversations", inputs, context)
            print(f"List Conversations Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_conversations: {e}")
            return None


async def test_create_note():
    """Test creating a private note on a ticket."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {
        "ticket_id": 1,  # Replace with actual ticket ID
        "body": "<p>This is a private note for internal use.</p>"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("create_note", inputs, context)
            print(f"Create Note Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_note: {e}")
            return None


async def test_create_reply():
    """Test creating a public reply on a ticket."""
    auth = {
        "credentials": {
            "api_key": "your_api_key_here",
            "domain": "your_domain_here"
        }
    }

    inputs = {
        "ticket_id": 1,  # Replace with actual ticket ID
        "body": "<p>This is a public reply to the customer.</p>"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await freshdesk.execute_action("create_reply", inputs, context)
            print(f"Create Reply Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_reply: {e}")
            return None


async def main():
    print("Testing Freshdesk Integration")
    print("=" * 60)
    print()
    print("NOTE: Replace 'your_api_key_here' and 'your_domain_here'")
    print("      with actual credentials before running tests.")
    print()
    print("=" * 60)
    print()

    # Test company actions
    print("1. Testing list_companies...")
    await test_list_companies()
    print()

    print("2. Testing search_companies...")
    await test_search_companies()
    print()

    print("3. Testing create_company...")
    created_company = await test_create_company()
    print()

    print("4. Testing get_company...")
    await test_get_company()
    print()

    # Test ticket actions
    print("5. Testing create_ticket...")
    created_ticket = await test_create_ticket()
    print()

    print("6. Testing list_tickets...")
    await test_list_tickets()
    print()

    print("7. Testing get_ticket...")
    await test_get_ticket()
    print()

    # Test contact actions
    print("8. Testing create_contact...")
    created_contact = await test_create_contact()
    print()

    print("9. Testing list_contacts...")
    await test_list_contacts()
    print()

    print("10. Testing search_contacts...")
    await test_search_contacts()
    print()

    # Test conversation actions
    print("11. Testing list_conversations...")
    await test_list_conversations()
    print()

    print("12. Testing create_note...")
    await test_create_note()
    print()

    print("13. Testing create_reply...")
    await test_create_reply()
    print()

    print("=" * 60)
    print("Testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

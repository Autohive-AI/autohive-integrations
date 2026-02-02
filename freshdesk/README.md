# Freshdesk Integration for Autohive

Connects Autohive to the Freshdesk API to enable comprehensive customer support operations including ticket management, contact management, company management, and conversation tracking.

## Description

This integration provides a complete connection to Freshdesk's help desk platform. It allows users to automate customer support workflows by managing tickets, contacts, companies, and conversations directly from Autohive.

The integration uses Freshdesk API v2 and implements 15 core actions covering all essential help desk operations.

## Setup & Authentication

This integration uses **Custom Authentication** with Freshdesk API key credentials.

### Authentication Method

Freshdesk uses Basic Authentication with your API key. The integration handles the authentication automatically by encoding your API key in the required format (`api_key:X` base64-encoded) and adding it to all API requests.

### Required Authentication Fields

- **`api_key`**: Your Freshdesk API key
  - Find it by logging into Freshdesk → Profile Settings → View API key
  - Complete the CAPTCHA verification to reveal your key
  - **Note**: API keys are only available on Blossom plan or higher (not available on free Sprout plan)
  - Keep this key secure

- **`domain`**: Your Freshdesk subdomain
  - Enter only the subdomain part (e.g., `yourcompany` from `yourcompany.freshdesk.com`)
  - Do not include `.freshdesk.com` suffix

### Setup Steps

1. **Get your API key:**
   - Log into your Freshdesk account
   - Click on your profile picture in the top right
   - Select "Profile Settings"
   - Click "View API key" on the right side
   - Complete the CAPTCHA verification
   - Copy your API key immediately

2. **Configure in Autohive:**
   - Add the Freshdesk integration in Autohive
   - Paste your API key in the `api_key` field
   - Enter your Freshdesk subdomain in the `domain` field
   - Save the configuration

## Actions

### Companies (6 actions)

#### `list_companies`
Lists all companies in your Freshdesk account with pagination support.

**Inputs:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Companies per page (default: 30, max: 100)

**Outputs:**
- `companies`: Array of company objects
- `total`: Number of companies returned
- `result`: Success status

---

#### `search_companies`
Search for companies by name using autocomplete. The search is case insensitive but requires complete words (no substring matching).

**Inputs:**
- `name` (required): Company name or keyword to search for

**Outputs:**
- `companies`: Array of matching company objects (id and name only)
- `total`: Number of companies found
- `result`: Success status

**Search Behavior:**
- Case insensitive (e.g., "acme" matches "Acme Corporation")
- Requires word prefix matching (not substrings)
- Examples:
  - ✅ "Acme Corporation" matches: "acme", "Ac", "Corporation", "Co"
  - ❌ "Acme Corporation" does NOT match: "cme", "orporation"

---

#### `create_company`
Creates a new company in Freshdesk.

**Inputs:**
- `name` (required): Company name
- `description` (optional): Company description
- `domains` (optional): Array of email domains
- `note` (optional): Additional notes
- `custom_fields` (optional): Custom field values

**Outputs:**
- `company`: Created company object
- `result`: Success status

---

#### `get_company`
Retrieves details of a specific company by ID.

**Inputs:**
- `company_id` (required): Unique company ID

**Outputs:**
- `company`: Company object with all details
- `result`: Success status

---

#### `update_company`
Updates an existing company's information.

**Inputs:**
- `company_id` (required): Unique company ID
- `name` (optional): Updated company name
- `description` (optional): Updated description
- `domains` (optional): Updated email domains
- `note` (optional): Updated notes
- `custom_fields` (optional): Updated custom fields

**Outputs:**
- `company`: Updated company object
- `result`: Success status

---

#### `delete_company`
Deletes a company from Freshdesk (cannot be undone).

**Inputs:**
- `company_id` (required): Unique company ID

**Outputs:**
- `result`: Success status

---

### Tickets (5 actions)

#### `create_ticket`
Creates a new support ticket.

**Inputs:**
- `subject` (required): Ticket subject
- `email` (required): Requester email address
- `description` (optional): HTML ticket content
- `priority` (optional): 1-Low, 2-Medium, 3-High, 4-Urgent
- `status` (optional): 2-Open, 3-Pending, 4-Resolved, 5-Closed
- `source` (optional): 1-Email, 2-Portal, 3-Phone, 7-Chat, 9-Feedback, 10-Outbound Email
- `name` (optional): Requester name
- `company_id` (optional): Associated company ID
- `tags` (optional): Array of tags

**Outputs:**
- `ticket`: Created ticket object
- `result`: Success status

---

#### `list_tickets`
Lists all tickets with pagination.

**Inputs:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Tickets per page (default: 30, max: 100)

**Outputs:**
- `tickets`: Array of ticket objects
- `total`: Number of tickets returned
- `result`: Success status

---

#### `get_ticket`
Retrieves details of a specific ticket.

**Inputs:**
- `ticket_id` (required): Unique ticket ID

**Outputs:**
- `ticket`: Ticket object with all details
- `result`: Success status

---

#### `update_ticket`
Updates an existing ticket.

**Inputs:**
- `ticket_id` (required): Unique ticket ID
- `subject` (optional): Updated subject
- `description` (optional): Updated description
- `priority` (optional): Updated priority (1-4)
- `status` (optional): Updated status (2-5)
- `tags` (optional): Updated tags

**Outputs:**
- `ticket`: Updated ticket object
- `result`: Success status

---

#### `delete_ticket`
Deletes a ticket (can be restored within 30 days).

**Inputs:**
- `ticket_id` (required): Unique ticket ID

**Outputs:**
- `result`: Success status

---

### Contacts (6 actions)

#### `create_contact`
Creates a new contact in Freshdesk.

**Inputs:**
- `name` (required): Full name
- `email` (required): Email address
- `phone` (optional): Phone number
- `mobile` (optional): Mobile number
- `company_id` (optional): Associated company ID
- `job_title` (optional): Job title
- `description` (optional): Description
- `tags` (optional): Array of tags

**Outputs:**
- `contact`: Created contact object
- `result`: Success status

---

#### `search_contacts`
Search for contacts by name using autocomplete. The search is case insensitive but requires complete words (no substring matching).

**Inputs:**
- `term` (required): Contact name or keyword to search for

**Outputs:**
- `contacts`: Array of matching contact objects (id and name only)
- `total`: Number of contacts found
- `result`: Success status

**Search Behavior:**
- Case insensitive (e.g., "john" matches "John Jonz")
- Requires word prefix matching (not substrings)
- Examples:
  - ✅ "John Jonz" matches: "john", "Joh", "Jonz", "jon"
  - ❌ "John Jonz" does NOT match: "hn", "nz"

---

#### `list_contacts`
Lists all contacts with pagination.

**Inputs:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Contacts per page (default: 30, max: 100)

**Outputs:**
- `contacts`: Array of contact objects
- `total`: Number of contacts returned
- `result`: Success status

---

#### `get_contact`
Retrieves details of a specific contact.

**Inputs:**
- `contact_id` (required): Unique contact ID

**Outputs:**
- `contact`: Contact object with all details
- `result`: Success status

---

#### `update_contact`
Updates an existing contact's information.

**Inputs:**
- `contact_id` (required): Unique contact ID
- `name` (optional): Updated name
- `email` (optional): Updated email
- `phone` (optional): Updated phone
- `mobile` (optional): Updated mobile
- `job_title` (optional): Updated job title
- `description` (optional): Updated description

**Outputs:**
- `contact`: Updated contact object
- `result`: Success status

---

#### `delete_contact`
Soft deletes a contact (can be restored).

**Inputs:**
- `contact_id` (required): Unique contact ID

**Outputs:**
- `result`: Success status

---

### Conversations (3 actions)

#### `list_conversations`
Retrieves all conversations (notes and replies) for a ticket.

**Inputs:**
- `ticket_id` (required): Unique ticket ID

**Outputs:**
- `conversations`: Array of conversation objects
- `result`: Success status

---

#### `create_note`
Adds a private note to a ticket (visible only to agents).

**Inputs:**
- `ticket_id` (required): Unique ticket ID
- `body` (required): Note content (HTML supported)
- `notify_emails` (optional): Array of emails to notify

**Outputs:**
- `conversation`: Created note object
- `result`: Success status

---

#### `create_reply`
Adds a public reply to a ticket (visible to customer).

**Inputs:**
- `ticket_id` (required): Unique ticket ID
- `body` (required): Reply content (HTML supported)
- `from_email` (optional): Send from specific email

**Outputs:**
- `conversation`: Created reply object
- `result`: Success status

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URL Format**: `https://{domain}.freshdesk.com/api/v2`
- **Authentication**: Basic Auth (API Key)
- **Documentation**: https://developers.freshdesk.com/api/
- **Rate Limits**: Based on your Freshdesk plan (typically 1000 requests/hour for paid plans)

## Important Notes

- API access requires a Freshdesk Blossom plan or higher (not available on free Sprout plan)
- All API requests must use HTTPS
- Username/password authentication was deprecated on August 31, 2021 (only API key auth is supported)
- Deleted tickets can be restored within 30 days
- Deleted contacts are soft-deleted and can be restored
- Deleted companies cannot be restored

## Testing

To test the integration:

1. Navigate to the integration directory: `cd freshdesk`
2. Install dependencies: `pip install -r requirements.txt`
3. Update test credentials in `tests/test_freshdesk.py`
4. Run tests: `python tests/test_freshdesk.py`

## Common Use Cases

**Customer Support Workflow:**
1. Create contacts for new customers
2. Create tickets when issues are reported
3. Add notes for internal tracking
4. Add replies to communicate with customers
5. Update ticket status as issues progress
6. Close tickets when resolved

**Organization Management:**
1. Create companies for business customers
2. Associate contacts with companies
3. Track all support tickets by company

## Version History

- **1.1.0** - Added search functionality
  - Companies: Added `search_companies` (autocomplete search by name)
  - Contacts: Added `search_contacts` (autocomplete search by name)

- **1.0.0** - Initial release with 13 core actions
  - Companies: list, create, get, update, delete
  - Tickets: list, create, get, update, delete
  - Contacts: list, create, get, update, delete
  - Conversations: list, create_note, create_reply

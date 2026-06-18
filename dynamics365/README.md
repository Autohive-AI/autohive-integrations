# Microsoft Dynamics 365 Integration for Autohive

Connects Autohive to Microsoft Dynamics 365 CRM for managing Accounts, Contacts, Leads, Opportunities, and Tasks through the OData v4 REST API.

## Description

This integration provides comprehensive access to Microsoft Dynamics 365 CRM, enabling agents to manage the full sales lifecycle — from lead capture through opportunity close. It interacts with the Dynamics 365 Web API (`/api/data/v9.2/`) using platform OAuth2 authentication.

Key capabilities include listing, retrieving, creating, and updating Accounts and Contacts, managing Leads with qualification support (creating downstream Account/Contact/Opportunity records), Opportunity pipeline management with estimated value and close date tracking, and Task/activity creation linked to any CRM entity.

## Setup & Authentication

**Authentication Method:** Platform OAuth2 (Microsoft Dynamics 365)

Users connect their Dynamics 365 account through the Autohive platform. The `org_url` (e.g. `https://yourorg.crm.dynamics.com`) is collected alongside the OAuth credentials during setup.

Required OAuth scopes:
- `offline_access` — refresh token support
- `https://org.crm.dynamics.com/user_impersonation` — access Dynamics 365 data

## Actions

### `list_accounts`

List CRM accounts with optional filtering by name or industry.

**Inputs:**
- `name` (optional): Filter by account name (contains match)
- `industry` (optional): Filter by industry code
- `limit` (optional): Maximum records to return (default: 20)
- `select` (optional): Comma-separated list of fields to return

**Outputs:**
- `accounts`: List of account records
- `count`: Number of accounts returned

---

### `get_account`

Get a single CRM account by ID.

**Inputs:**
- `account_id` (required): The account GUID

**Outputs:**
- `account`: The account record

---

### `create_account`

Create a new CRM account.

**Inputs:**
- `name` (required): Account name
- `email` (optional): Primary email address
- `phone` (optional): Primary phone number
- `website` (optional): Website URL
- `industry` (optional): Industry code
- `city` (optional): City
- `country` (optional): Country
- `description` (optional): Account description

**Outputs:**
- `account`: The created account record

---

### `update_account`

Update an existing CRM account.

**Inputs:**
- `account_id` (required): The account GUID
- `name` (optional): Account name
- `email` (optional): Primary email address
- `phone` (optional): Primary phone number
- `website` (optional): Website URL
- `description` (optional): Account description

**Outputs:**
- `updated`: Whether the update succeeded
- `account_id`: The updated account GUID

---

### `list_contacts`

List CRM contacts with optional filtering.

**Inputs:**
- `first_name` (optional): Filter by first name (contains)
- `last_name` (optional): Filter by last name (contains)
- `email` (optional): Filter by email address
- `account_id` (optional): Filter by parent account GUID
- `limit` (optional): Maximum records to return (default: 20)
- `select` (optional): Comma-separated list of fields to return

**Outputs:**
- `contacts`: List of contact records
- `count`: Number of contacts returned

---

### `get_contact`

Get a single CRM contact by ID.

**Inputs:**
- `contact_id` (required): The contact GUID

**Outputs:**
- `contact`: The contact record

---

### `create_contact`

Create a new CRM contact.

**Inputs:**
- `last_name` (required): Last name
- `first_name` (optional): First name
- `email` (optional): Email address
- `phone` (optional): Phone number
- `job_title` (optional): Job title
- `account_id` (optional): Parent account GUID
- `city` (optional): City
- `country` (optional): Country

**Outputs:**
- `contact`: The created contact record

---

### `update_contact`

Update an existing CRM contact.

**Inputs:**
- `contact_id` (required): The contact GUID
- `first_name` (optional): First name
- `last_name` (optional): Last name
- `email` (optional): Email address
- `phone` (optional): Phone number
- `job_title` (optional): Job title

**Outputs:**
- `updated`: Whether the update succeeded
- `contact_id`: The updated contact GUID

---

### `list_leads`

List CRM leads with optional filtering.

**Inputs:**
- `first_name` (optional): Filter by first name (contains)
- `last_name` (optional): Filter by last name (contains)
- `email` (optional): Filter by email address
- `status` (optional): Filter by status code
- `limit` (optional): Maximum records to return (default: 20)

**Outputs:**
- `leads`: List of lead records
- `count`: Number of leads returned

---

### `get_lead`

Get a single CRM lead by ID.

**Inputs:**
- `lead_id` (required): The lead GUID

**Outputs:**
- `lead`: The lead record

---

### `create_lead`

Create a new CRM lead.

**Inputs:**
- `last_name` (required): Last name
- `company` (required): Company name
- `first_name` (optional): First name
- `email` (optional): Email address
- `phone` (optional): Phone number
- `topic` (optional): Lead topic / subject
- `source` (optional): Lead source code
- `description` (optional): Lead description / notes

**Outputs:**
- `lead`: The created lead record

---

### `qualify_lead`

Qualify a lead, optionally creating downstream Account, Contact, and/or Opportunity records.

**Inputs:**
- `lead_id` (required): The lead GUID to qualify
- `create_account` (optional): Create an account from the lead (default: `true`)
- `create_contact` (optional): Create a contact from the lead (default: `true`)
- `create_opportunity` (optional): Create an opportunity from the lead (default: `false`)

**Outputs:**
- `qualified`: Whether the lead was qualified successfully
- `created_entities`: List of entities created during qualification

---

### `list_opportunities`

List CRM opportunities with optional filtering.

**Inputs:**
- `name` (optional): Filter by opportunity name (contains)
- `account_id` (optional): Filter by parent account GUID
- `status` (optional): Filter by status (`Open`, `Won`, `Lost`)
- `limit` (optional): Maximum records to return (default: 20)

**Outputs:**
- `opportunities`: List of opportunity records
- `count`: Number of opportunities returned

---

### `get_opportunity`

Get a single CRM opportunity by ID.

**Inputs:**
- `opportunity_id` (required): The opportunity GUID

**Outputs:**
- `opportunity`: The opportunity record

---

### `create_opportunity`

Create a new CRM opportunity.

**Inputs:**
- `name` (required): Opportunity name
- `account_id` (optional): Parent account GUID
- `estimated_value` (optional): Estimated revenue value
- `close_date` (optional): Estimated close date (ISO 8601)
- `description` (optional): Opportunity description
- `probability` (optional): Win probability percentage (0–100)

**Outputs:**
- `opportunity`: The created opportunity record

---

### `list_tasks`

List CRM tasks/activities with optional filtering.

**Inputs:**
- `regarding_id` (optional): Filter by regarding entity GUID
- `status` (optional): Filter by status (`Open`, `Completed`, `Cancelled`)
- `limit` (optional): Maximum records to return (default: 20)

**Outputs:**
- `tasks`: List of task records
- `count`: Number of tasks returned

---

### `create_task`

Create a new CRM task/activity.

**Inputs:**
- `subject` (required): Task subject
- `description` (optional): Task description
- `due_date` (optional): Due date (ISO 8601)
- `priority` (optional): Priority — `Low`, `Normal`, or `High` (default: `Normal`)
- `regarding_id` (optional): GUID of the entity this task is regarding
- `regarding_type` (optional): Entity type — `account`, `contact`, `opportunity`, or `lead`

**Outputs:**
- `task`: The created task record

---

## Requirements

- `autohive-integrations-sdk~=2.0.0`
- `aiohttp>=3.9.0`

## Testing

Install dependencies:
```bash
pip install -r requirements.txt
```

Run unit tests (no credentials needed):
```bash
python -m pytest dynamics365/tests/test_dynamics365_unit.py -v
```

Run live integration tests (requires credentials):
```bash
export D365_ORG_URL="https://yourorg.crm.dynamics.com"
export D365_ACCESS_TOKEN="<your-access-token>"
python -m pytest dynamics365/tests/test_dynamics365_integration.py -v -m "integration and not destructive"
```

Run all integration tests including destructive ones (creates/updates real CRM records):
```bash
export D365_ORG_URL="https://yourorg.crm.dynamics.com"
export D365_ACCESS_TOKEN="<your-access-token>"
python -m pytest dynamics365/tests/test_dynamics365_integration.py -v -m "integration"
```

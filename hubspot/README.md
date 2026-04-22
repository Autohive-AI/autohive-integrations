# HubSpot CRM Integration for Autohive

Comprehensive HubSpot CRM integration for managing contacts, companies, deals, support tickets, marketing emails, and campaigns with advanced pipeline analytics and UTC date handling.

## Description

This integration provides complete access to HubSpot CRM and Marketing functionality through Autohive, enabling users to manage their entire customer relationship lifecycle and marketing operations. It supports comprehensive CRUD operations across all major CRM objects including contacts, companies, deals, tickets, and conversations, plus read access to marketing emails and campaigns. The integration features UTC date handling, pagination support, specialized rate limiting for high-volume operations, and powerful v4 Associations API support.

Key features include:
- Complete contact management with email conversation history
- Company management with comprehensive property support
- Advanced deal pipeline management with UTC date handling
- Support ticket management with conversation threading
- Call and meeting transcript access - Retrieve transcripts and notes from calls and meetings (including Google Meet recordings saved to HubSpot)
- Marketing emails - List and retrieve marketing emails
- Campaigns - Browse marketing campaigns and their associated content
- v4 Associations API - Retrieve all related objects (companies, deals, tickets, etc.) for any contact, company, or deal
- Intelligent pagination and rate limiting for large datasets
- Comprehensive search and filtering capabilities
- Real-time conversation management for customer support
- Lists/segments management with member exports

This integration interacts with HubSpot's CRM v3 API, v4 Associations API, Marketing v3 API (emails and campaigns), and Conversations API, providing robust error handling, UTC date formatting, and optimized performance for large-scale operations.

## Setup & Authentication

The integration uses HubSpot's OAuth 2.0 platform authentication. No manual API key configuration is required - authentication is handled automatically through Autohive's platform integration system.

**Required Scopes:**
The integration automatically requests the following HubSpot permissions:
- `conversations.read` - Read access to conversation threads
- `conversations.write` - Write access to conversation threads
- `crm.objects.companies.read` - Read access to company records
- `crm.objects.companies.write` - Write access to company records
- `crm.objects.contacts.read` - Read access to contact records
- `crm.objects.contacts.write` - Write access to contact records
- `crm.objects.deals.read` - Read access to deal records
- `crm.objects.deals.write` - Write access to deal records
- `crm.objects.owners.read` - Read access to owner information
- `crm.lists.read` - Read access to lists/segments and their memberships
- `tickets` - Full access to support tickets
- `sales-email-read` - Read access to sales email data
- `oauth` - OAuth authentication
- `content` - Read access to marketing emails and content
- `marketing.campaigns.read` - Read access to marketing campaigns and performance data
- `crm.extensions_calling_transcripts.read` - Read access to call and meeting transcripts (required for Google Meet transcript retrieval)

**Setup Steps:**
1. Configure the HubSpot integration in your Autohive platform
2. Authorize the integration through HubSpot's OAuth flow
3. Grant the required permissions when prompted
4. The integration will automatically handle token management and refresh

## Actions

This integration provides comprehensive actions covering complete CRUD operations for all major HubSpot CRM modules including note management, lists/segments management, v4 Associations API, custom properties discovery, and marketing functionality (emails and campaigns with performance analytics):

### Contact Management

#### Action: `get_contact`
- **Description:** Retrieve a HubSpot contact by email address with optional recent email conversations
- **Inputs:**
  - `email` (required): Email address of the contact to retrieve
  - `include_recent_emails` (optional): Include recent email conversations (default: false)
  - `email_limit` (optional): Maximum number of recent emails to retrieve (default: 5, max: 20)
- **Outputs:** Contact object with profile information and optional email history with UTC timestamps

#### Action: `create_contact`
- **Description:** Creates a new contact in HubSpot CRM
- **Inputs:**
  - `properties` (required): Contact properties object containing:
    - `email`: Contact email address (recommended)
    - `firstname`: Contact first name
    - `lastname`: Contact last name
    - `phone`: Phone number
    - `company`: Company name
    - `jobtitle`: Job title
- **Outputs:** Created contact object with `id` and contact details

#### Action: `update_contact`
- **Description:** Updates an existing contact's information
- **Inputs:**
  - `contact_id` (required): Internal object ID of the contact
  - `properties` (required): Contact properties to update
- **Outputs:** Updated contact object

#### Action: `search_contacts`
- **Description:** Search contacts using text queries across contact properties
- **Inputs:**
  - `query` (required): Search query string
  - `limit` (optional): Maximum number of results (default: 100, max: 100)
- **Outputs:** Array of matching contact objects

#### Action: `add_contact_to_list`
- **Description:** Add a contact to a specific HubSpot marketing list
- **Inputs:**
  - `list_id` (required): HubSpot list ID
  - `contact_id` (required): Contact ID to add to the list
- **Outputs:** Operation result with success status

#### Action: `get_recent_contacts`
- **Description:** Retrieve recently created contacts sorted by creation date
- **Inputs:**
  - `limit` (optional): Number of contacts to retrieve (default: 100, max: 100)
- **Outputs:** Array of recent contacts with pagination metadata

### Note Management (Engagements)

#### Action: `create_note`
- **Description:** Create a new note and associate it with contacts, companies, or deals
- **Inputs:**
  - `note_body` (required): The content/body of the note
  - `contact_id` (optional): Contact ID to associate the note with
  - `company_id` (optional): Company ID to associate the note with
  - `deal_id` (optional): Deal ID to associate the note with
  - `timestamp` (optional): Custom timestamp in milliseconds (defaults to current time)
- **Outputs:**
  - `note`: The created note object with HubSpot properties
  - `success`: Boolean indicating creation status
  - `message`: Success or error message
- **Note:** You can associate a single note with multiple objects (contact, company, and deal) simultaneously

#### Action: `update_note`
- **Description:** Update an existing note's content or properties
- **Inputs:**
  - `note_id` (required): The ID of the note to update
  - `note_body` (optional): New content for the note
  - `timestamp` (optional): New timestamp in milliseconds
  - `additional_properties` (optional): Other note properties to update
- **Outputs:**
  - `note`: The updated note object
  - `success`: Boolean indicating update status
  - `updated_properties`: Properties that were modified
  - `message`: Success or error message

#### Action: `delete_note`
- **Description:** Permanently delete a note from HubSpot
- **Inputs:**
  - `note_id` (required): The ID of the note to delete
- **Outputs:**
  - `success`: Boolean indicating deletion status
  - `note_id`: The ID of the deleted note
  - `message`: Success or error message

#### Action: `get_contact_notes`
- **Description:** Retrieve all notes associated with a specific contact
- **Inputs:**
  - `contact_id` (required): The contact ID to retrieve notes for
  - `limit` (optional): Maximum number of notes to retrieve (default: 100, max: 200)
  - `properties` (optional): Array of note properties to retrieve
- **Outputs:**
  - `notes`: Array of note objects with timestamps converted to UTC strings
  - `total`: Total number of notes retrieved
  - `contact_id`: The contact ID that was queried

#### Action: `get_company_notes`
- **Description:** Retrieve all notes associated with a specific company
- **Inputs:**
  - `company_id` (required): The company ID to retrieve notes for
  - `limit` (optional): Maximum number of notes to retrieve (default: 100, max: 200)
- **Outputs:** Array of note objects with UTC timestamps

#### Action: `get_deal_notes`
- **Description:** Retrieve all notes associated with a specific deal
- **Inputs:**
  - `deal_id` (required): The deal ID to retrieve notes for
  - `limit` (optional): Maximum number of notes to retrieve (default: 100, max: 200)
- **Outputs:** Array of note objects with UTC timestamps

### Calls and Meetings (Transcripts)

#### Action: `get_contact_calls_and_meetings`
- **Description:** Retrieve calls (with transcripts) and meetings (metadata) associated with a contact. Google Meet transcripts are stored on call records via HubSpot's Calling Transcripts API — not on meeting records.
- **Inputs:**
  - `contact_id` (required): The internal object ID of the contact
  - `limit` (optional): Maximum number of calls/meetings to retrieve each (default: 50, max: 100)
- **Outputs:**
  - `calls`: Array of call objects, each containing:
    - `hs_call_title`: Call title
    - `hs_call_duration`: Duration in milliseconds
    - `hs_call_status`: Call status
    - `hs_call_direction`: INBOUND or OUTBOUND
    - `hs_call_has_transcript`: Whether a transcript exists
    - `hs_call_transcription_id`: Transcript ID (may be null due to a known HubSpot bug even when a transcript exists)
    - `hs_timestamp`: Call time (UTC)
    - `transcript`: Array of utterances from the Calling Transcripts API, each with `speakerId`, `text`, and `timestamp`
  - `meetings`: Array of meeting metadata objects (title, start/end time, location — no transcript content)
  - `total_calls`: Number of calls returned
  - `total_meetings`: Number of meetings returned
- **Note:** Requires Sales Hub or Service Hub Professional/Enterprise for Google Meet transcript sync (Conversational Intelligence feature)
- **Transcript fallback:** When `hs_call_transcription_id` is null but `hs_call_has_transcript` is true (known HubSpot bug), the integration automatically falls back to using the call's own ID as the transcript ID to attempt recovery

#### Action: `get_deal_calls_and_meetings`
- **Description:** Retrieve calls (with transcripts) and meetings (metadata) associated with a deal. Same transcript behaviour as `get_contact_calls_and_meetings`.
- **Inputs:**
  - `deal_id` (required): The internal object ID of the deal
  - `limit` (optional): Maximum number of calls/meetings to retrieve each (default: 50, max: 100)
- **Outputs:**
  - `calls`: Array of call objects with transcript utterances (same structure as `get_contact_calls_and_meetings`)
  - `meetings`: Array of meeting metadata objects
  - `total_calls`: Number of calls returned
  - `total_meetings`: Number of meetings returned

#### Action: `get_call_transcript`
- **Description:** Retrieve structured transcript utterances (with speaker IDs and timestamps) for a specific HubSpot call. Use this when you need the full speaker/timestamp breakdown of a transcript rather than the plain-text `hs_call_body` property. Calls the HubSpot Calling Transcripts API directly.
- **Inputs:**
  - `transcript_id` (required): The transcript ID — use `hs_call_transcription_id` from the call record, or the call record ID itself as a fallback when `hs_call_has_transcript` is true but `hs_call_transcription_id` is null (known HubSpot bug)
- **Outputs:**
  - `transcript_id`: The transcript ID queried
  - `utterances`: Array of utterance objects, each with:
    - `speaker`: Object with `id`, `name`, and `email` of the speaker
    - `text`: Spoken text
    - `startTimeMillis`: Start time in milliseconds from start of call
    - `endTimeMillis`: End time in milliseconds from start of call
    - `languageCode`: Language code (e.g. `en-US`)
  - `total_utterances`: Number of utterances returned
- **Note:** Requires `crm.extensions_calling_transcripts.read` scope (already included). Requires Sales Hub or Service Hub Professional/Enterprise for Google Meet transcript sync.
- **When to use vs `get_contact_calls_and_meetings`:** The contact/deal call actions already inline transcripts — use `get_call_transcript` when you have a specific `transcript_id` and want utterances without fetching the entire call list.

### Company Management

#### Action: `get_company`
- **Description:** Retrieve a specific company by its ID with comprehensive properties
- **Inputs:**
  - `company_id` (required): Internal object ID of the company
- **Outputs:** Complete company record with all standard and custom properties

#### Action: `create_company`
- **Description:** Creates a new company in HubSpot CRM
- **Inputs:**
  - `properties` (required): Company properties object containing:
    - `name`: Company name (recommended)
    - `domain`: Company website domain
    - `phone`: Phone number
    - `city`, `state`, `country`: Location information
    - `industry`: Industry classification
    - `numberofemployees`: Number of employees
    - `annualrevenue`: Annual revenue
- **Outputs:** Created company object with `id` and company details

#### Action: `update_company`
- **Description:** Updates an existing company's information
- **Inputs:**
  - `company_id` (required): Company ID to update
  - `properties` (required): Company properties to update
- **Outputs:** Updated company object

#### Action: `search_companies`
- **Description:** Search companies using text queries
- **Inputs:**
  - `query` (required): Search query string
  - `limit` (optional): Maximum results (default: 100)
- **Outputs:** Array of matching company objects

#### Action: `get_company_properties`
- **Description:** Retrieve all available company properties (including custom) from HubSpot with detailed metadata
- **Inputs:**
  - `include_details` (optional): Include full property details (label, type, fieldType, options) instead of just names (default: false)
- **Outputs:**
  - `properties`: Array of company properties (names or detailed objects)
  - `total_properties`: Total count
  - `custom_properties_count`: Number of custom properties
- **Use Case:** Discover what custom properties exist before requesting them

#### Action: `get_deal_properties`
- **Description:** Retrieve all available deal properties (including custom) from HubSpot with detailed metadata
- **Inputs:**
  - `include_details` (optional): Include full property details (default: false)
- **Outputs:** Same as get_company_properties
- **Use Case:** Discover custom deal properties like "Custom Property Example" to use in other actions

#### Action: `get_contact_properties`
- **Description:** Retrieve all available contact properties (including custom) from HubSpot with detailed metadata
- **Inputs:**
  - `include_details` (optional): Include full property details (default: false)
- **Outputs:** Same as get_company_properties
- **Use Case:** Discover custom contact properties for retrieval

### Deal Management

#### Action: `get_deal`
- **Description:** Retrieve a specific deal by its ID with comprehensive properties and timezone conversion
- **Inputs:**
  - `deal_id` (required): Internal object ID of the deal
- **Outputs:** Complete deal record with UTC formatted dates and last contacted information

#### Action: `get_deals`
- **Description:** Retrieve deals with comprehensive pagination support and optional rate limiting - ideal for accessing ALL deals from a pipeline
- **Inputs:**
  - `limit` (optional): Deals per page (default: 50, max: 100)
  - `sort_property` (optional): Property to sort by (default: hs_lastmodifieddate)
  - `sort_direction` (optional): Sort direction ASC/DESC (default: DESC)
  - `fetch_all` (optional): Fetch all available pages (default: false)
  - `pipeline_id` (optional): Filter by specific pipeline ID
  - `year` (optional): Filter by close date year for performance
  - `max_total` (optional): Maximum total deals across all pages (default: 100, max: 5000)
  - `delay_between_requests` (optional): Delay in seconds between requests for rate limiting (default: 0, no delay)
- **Outputs:** Array of deals with comprehensive pagination metadata and UTC formatted dates

#### Action: `search_deals`
- **Description:** Search deals using advanced filters and text queries with intelligent post-processing
- **Inputs:**
  - `query` (optional): Text search across deal names
  - `pipeline_id` (optional): Filter by pipeline
  - `deal_stage` (optional): Filter by specific deal stage
  - `close_date_start/close_date_end` (optional): Date range filtering with flexible format support
  - `min_amount/max_amount` (optional): Amount range filtering
  - `sort_property` (optional): Sorting options
  - `limit` (optional): Results per page (default: 100)
- **Outputs:** Filtered deals with pagination guidance and timezone conversion

#### Action: `create_deal`
- **Description:** Creates a new deal with optional associations
- **Inputs:**
  - `properties` (required): Deal properties including dealname, amount, closedate, dealstage, pipeline
  - `associations` (optional): Array of associations to contacts/companies
- **Outputs:** Created deal object with `id` and deal details

#### Action: `update_deal`
- **Description:** Updates an existing deal's properties
- **Inputs:**
  - `deal_id` (required): Deal ID to update
  - `properties` (required): Deal properties to update
- **Outputs:** Updated deal object

#### Action: `get_recent_deals`
- **Description:** Retrieve recently created or modified deals
- **Inputs:**
  - `limit` (optional): Number of deals (default: 100)
  - `sort_property` (optional): Sort property (default: createdate)
  - `sort_direction` (optional): Sort direction (default: DESC)
- **Outputs:** Array of recent deals with UTC formatting

#### Action: `get_deal_pipelines`
- **Description:** Retrieve all deal pipelines and their stages
- **Inputs:** None required
- **Outputs:** Array of all pipelines with their stages and metadata

### Associations Management

#### Action: `get_contact_associations`
- **Description:** Retrieve all associated objects for a contact (companies, deals, tickets, tasks, notes, emails, etc.) using v4 Associations API
- **Inputs:**
  - `contact_id` (required): Internal object ID of the contact
  - `association_types` (optional): Array of association types to retrieve - ["companies", "deals", "tickets", "tasks", "notes", "emails", "meetings", "calls"] (default: ["companies", "deals", "meetings"])
  - `limit` (optional): Maximum associations per type (default: 100, max: 500)
- **Outputs:** Object containing:
  - `contact_id`: The contact ID queried
  - `associations`: Object with arrays for each association type (e.g., companies, deals)
  - `total_associations`: Total count across all types
  - `summary`: Count breakdown by type (e.g., companies_count, deals_count)
- **Use Case:** Get everything connected to a contact - "Show me all companies, deals, and tickets for this contact"

#### Action: `get_company_associations`
- **Description:** Retrieve all associated objects for a company (contacts, deals, tickets, etc.) using v4 Associations API
- **Inputs:**
  - `company_id` (required): Internal object ID of the company
  - `association_types` (optional): Array of association types - ["contacts", "deals", "tickets", "tasks", "notes", "emails"] (default: ["contacts", "deals", "tickets"])
  - `limit` (optional): Maximum associations per type (default: 100, max: 500)
- **Outputs:** Similar structure to get_contact_associations with company_id
- **Use Case:** Get all contacts and deals associated with a company

#### Action: `get_deal_associations`
- **Description:** Retrieve all associated objects for a deal (contacts, companies, tickets, line items, quotes) using v4 Associations API
- **Inputs:**
  - `deal_id` (required): Internal object ID of the deal
  - `association_types` (optional): Array of association types - ["contacts", "companies", "tickets", "line_items", "quotes"] (default: ["contacts", "companies"])
  - `limit` (optional): Maximum associations per type (default: 100, max: 500)
- **Outputs:** Similar structure to get_contact_associations with deal_id
- **Use Case:** Get all contacts and companies involved in a deal

### Lists/Segments Management

#### Action: `get_lists`
- **Description:** Retrieve all available lists/segments from HubSpot with filtering options
- **Inputs:**
  - `list_ids` (optional): Array of specific list IDs to retrieve
  - `include_filters` (optional): Include filter definitions for dynamic lists (default: false)
  - `processing_types` (optional): Filter by list types - ["MANUAL", "DYNAMIC", "SNAPSHOT"]
- **Outputs:** Array of list objects with metadata including size, processing type, and creation dates

#### Action: `get_list`
- **Description:** Retrieve detailed information about a specific list by ID
- **Inputs:**
  - `list_id` (required): The ILS list ID to retrieve
  - `include_filters` (optional): Include filter branch definitions (default: true)
- **Outputs:** Complete list object with metadata and optional filter definitions

#### Action: `search_lists`
- **Description:** Search for lists by name and other criteria with pagination
- **Inputs:**
  - `query` (optional): Search query for list names
  - `count` (optional): Number of results to return (default: 20, max: 500)
  - `offset` (optional): Pagination offset (default: 0)
  - `processing_types` (optional): Filter by processing types
- **Outputs:** Paginated search results with total count and more results indicator

#### Action: `get_list_members`
- **Description:** Retrieve list members with complete contact information including names, emails, and custom properties
- **Inputs:**
  - `list_id` (required): The ILS list ID to get members from
  - `limit` (optional): Maximum number of members to return (default: 1000, max: 10000)
  - `contact_properties` (optional): Contact properties to include (default: ["email", "firstname", "lastname", "phone", "company", "jobtitle"])
  - `include_membership_timestamps` (optional): Include when contacts were added to list (default: true)
- **Outputs:** List metadata, array of members with contact details, performance statistics, and pagination info

#### Action: `get_list_memberships`
- **Description:** Get raw list member IDs and timestamps without contact details (for advanced use cases)
- **Inputs:**
  - `list_id` (required): The ILS list ID
  - `limit` (optional): Maximum number of memberships to return (default: 1000, max: 10000)
  - `batch_size` (optional): Records per API request (default: 250, max: 250)
- **Outputs:** Array of membership records with contact IDs and timestamps only

### Lead Management

#### Action: `create_lead`
- **Description:** Creates a new lead for potential customers
- **Inputs:**
  - `Last_Name` (required): Lead's last name
  - `First_Name`: Lead's first name
  - `Email`: Email address
  - `Phone`, `Mobile`: Contact numbers
  - `Company`: Lead's company
  - `Title`: Job title
  - `Industry`: Lead's industry
  - `Lead_Status`: Current status (e.g., New, Contacted, Qualified)
  - `Lead_Source`: How the lead was acquired
  - `Rating`: Lead quality rating (Hot, Warm, Cold)
  - Address fields and description
- **Outputs:** Lead object with `id` and lead details

#### Action: `convert_lead`
- **Description:** Converts a qualified lead into contact, account, and/or deal records
- **Inputs:** `lead_id` and conversion options
- **Outputs:** IDs of created records (contact, account, deal)

#### Action: `get_lead`, `update_lead`, `delete_lead`, `list_leads`, `search_leads`
- **Description:** Standard CRUD operations for leads

### Task Management

#### Action: `create_task`
- **Description:** Creates a new task/to-do item
- **Inputs:**
  - `Subject` (required): Task description
  - `Status`: Task status (Not Started, In Progress, Completed)
  - `Priority`: Priority level (High, Normal, Low)
  - `Due_Date`: When the task is due
  - `What_Id`: Related record ID (contact, account, deal, etc.)
  - `Who_Id`: Assigned user ID
  - `Description`: Detailed task description
- **Outputs:** Task object with `id` and task details

#### Action: `get_task`, `update_task`, `delete_task`, `list_tasks`, `search_tasks`
- **Description:** Standard CRUD operations for tasks

### Event Management

#### Action: `create_event`
- **Description:** Creates a new calendar event/meeting
- **Inputs:**
  - `Event_Title` (required): Event name
  - `Start_DateTime` (required): Event start time
  - `End_DateTime` (required): Event end time
  - `Venue`: Event location
  - `What_Id`: Related record ID
  - `Participants`: List of participants
  - `Description`: Event description
- **Outputs:** Event object with `id` and event details

#### Action: `get_event`, `update_event`, `delete_event`, `list_events`, `search_events`
- **Description:** Standard CRUD operations for events

### Call Management

#### Action: `create_call`
- **Description:** Logs a call activity
- **Inputs:**
  - `Subject` (required): Call subject
  - `Call_Type`: Type of call (Inbound, Outbound)
  - `Call_Start_Time`: When the call started
  - `Call_Duration`: Duration in minutes
  - `What_Id`: Related record ID
  - `Who_Id`: Contact/lead called
  - `Description`: Call notes
- **Outputs:** Call object with `id` and call details

#### Action: `get_call`, `update_call`, `delete_call`, `list_calls`, `search_calls`
- **Description:** Standard CRUD operations for calls

### Advanced Operations

### Ticket Management

#### Action: `get_recent_tickets`
- **Description:** Retrieve recent support tickets with filtering and sorting capabilities
- **Inputs:**
  - `limit` (optional): Number of tickets to retrieve (default: 20, max: 100)
  - `status` (optional): Filter by pipeline stage/status (1, 2, 3, 4)
  - `sort_property` (optional): Property to sort by (default: hs_lastmodifieddate)
  - `sort_direction` (optional): Sort direction ASC/DESC (default: DESC)
- **Outputs:** Array of ticket records with subject, content, priority, and status information

#### Action: `get_ticket_conversation`
- **Description:** Retrieve the complete conversation thread associated with a support ticket
- **Inputs:**
  - `ticket_id` (required): ID of the ticket to retrieve conversation for
- **Outputs:** Sorted conversation messages with sender information, timestamps, and message types

#### Action: `add_ticket_comment`
- **Description:** Add a comment to an existing ticket's conversation thread
- **Inputs:**
  - `ticket_id` (required): Ticket ID to add comment to
  - `comment` (required): Comment text to add
  - `is_public` (optional): Whether comment is visible to customer (default: false)
- **Outputs:** Operation result with success status and thread message details

### Marketing Emails

#### Action: `get_marketing_emails`
- **Description:** Retrieve a list of marketing emails with optional filtering by archived status
- **Inputs:**
  - `limit` (optional): Maximum number of emails to return (default: 50, max: 100)
  - `after` (optional): Pagination cursor for fetching next page of results
  - `archived` (optional): Filter by archived status (default: false)
- **Outputs:**
  - `emails`: Array of marketing email objects with id, name, subject, type, state, created_at, updated_at
  - `total`: Total number of emails returned
  - `paging`: Pagination information for fetching additional results

### Campaigns

#### Action: `get_campaigns`
- **Description:** Retrieve a list of marketing campaigns with optional filtering by name. Uses HubSpot v3 Campaigns API.
- **Inputs:**
  - `limit` (optional): Maximum number of campaigns to return (default: 50, max: 100)
  - `after` (optional): Pagination cursor for fetching next page of results
  - `name` (optional): Filter campaigns by name (substring matching)
  - `sort` (optional): Field to sort by: hs_name, createdAt, updatedAt (prefix with - for descending). Default: -updatedAt
- **Outputs:**
  - `campaigns`: Array of campaign objects with id, name, start_date, end_date, status, notes, owner, created_at, updated_at
  - `total`: Total number of campaigns
  - `paging`: Pagination information

#### Action: `get_campaign`
- **Description:** Retrieve a specific marketing campaign by ID with full details including associated assets. Optionally provide date range to include asset metrics.
- **Inputs:**
  - `campaign_id` (required): The GUID of the campaign to retrieve
  - `start_date` (optional): Start date for metrics period (YYYY-MM-DD format)
  - `end_date` (optional): End date for metrics period (YYYY-MM-DD format)
- **Outputs:**
  - `campaign`: Campaign object with id, name, start_date, end_date, status, notes, owner, audience, currency_code, utm, color_hex, budget_total, spend_total, created_at, updated_at, assets

#### Action: `get_campaign_assets`
- **Description:** Retrieve specific asset types (landing pages, emails, forms, etc.) for a campaign with performance metrics.
- **Inputs:**
  - `campaign_id` (required): The GUID of the campaign
  - `asset_type` (required): Type of assets to retrieve (LANDING_PAGE, MARKETING_EMAIL, FORM, BLOG_POST, SOCIAL_POST, CTA, WORKFLOW, SMS)
  - `start_date` (optional): Start date for metrics period (YYYY-MM-DD format)
  - `end_date` (optional): End date for metrics period (YYYY-MM-DD format)
  - `limit` (optional): Maximum number of assets to return (default: 50, max: 100)
  - `after` (optional): Pagination cursor
- **Outputs:**
  - `campaign_id`: The campaign GUID
  - `asset_type`: The type of assets returned
  - `assets`: Array of assets with id, name, and metrics (VIEWS, SUBMISSIONS, CLICKS, SENT, OPEN, etc.)
  - `total`: Total number of assets returned
  - `paging`: Pagination information

#### Action: `get_campaign_performance`
- **Description:** Retrieve comprehensive campaign performance metrics across all asset types (landing pages, emails, forms, blog posts). Returns aggregated totals for views, submissions, contacts, email opens/clicks, etc.
- **Inputs:**
  - `campaign_id` (required): The GUID of the campaign
  - `start_date` (optional): Start date for metrics period (YYYY-MM-DD format)
  - `end_date` (optional): End date for metrics period (YYYY-MM-DD format)
- **Outputs:**
  - `campaign_id`: The campaign GUID
  - `date_range`: Object with start_date and end_date
  - `landing_pages`: Assets array with totals (views, submissions, contacts_first_touch, contacts_last_touch, customers)
  - `marketing_emails`: Assets array with totals (sent, open, clicks)
  - `forms`: Assets array with totals (views, submissions, conversion_rate)
  - `blog_posts`: Assets array with totals (views, submissions, contacts)
  - `summary`: High-level aggregated metrics across all asset types

## Requirements

The integration has the following dependencies:

* `autohive-integrations-sdk` - Core SDK for Autohive integrations

## Usage Examples

**Example 1: Getting a contact with recent emails**
```json
{
  "email": "john.smith@company.com",
  "include_recent_emails": true,
  "email_limit": 10
}
```

**Example 2: Creating a new contact**
```json
{
  "properties": {
    "email": "john.smith@company.com",
    "firstname": "John",
    "lastname": "Smith",
    "phone": "+1-555-0123",
    "company": "Acme Corporation",
    "jobtitle": "Sales Manager"
  }
}
```

**Example 3: Creating a new deal with associations**
```json
{
  "properties": {
    "dealname": "Q4 Enterprise Software Deal",
    "amount": "50000",
    "closedate": "2025-12-31",
    "dealstage": "appointmentscheduled",
    "pipeline": "default"
  },
  "associations": [{
    "types": [{
      "associationCategory": "HUBSPOT_DEFINED",
      "associationTypeId": 3
    }],
    "to": {
      "id": "123456789"
    }
  }]
}
```

**Example 4: Searching deals with date range**
```json
{
  "query": "Enterprise",
  "close_date_start": "2025-01-01",
  "close_date_end": "2025-12-31",
  "min_amount": 10000,
  "pipeline_id": "default"
}
```

**Supported Date Formats:**
- `YYYY-MM-DD` (ISO format, recommended): `2025-01-01`
- `DD MMM YYYY H:MM PM`: `22 Aug 2025 3:46 PM`
- `DD MMM YYYY`: `22 Aug 2025`
- `MM/DD/YYYY`: `08/22/2025`
- `DD/MM/YYYY`: `22/08/2025`

**Note:** Relative date formats like "Today at 3:00 PM" are not supported. Use explicit dates to avoid timezone ambiguity.

**Example 5: Getting all deals from a pipeline with pagination**
```json
{
  "pipeline_id": "default",
  "fetch_all": true,
  "max_total": 1000,
  "sort_property": "closedate",
  "sort_direction": "DESC"
}
```

**Example 6: Adding a comment to a support ticket**
```json
{
  "ticket_id": "123456789",
  "comment": "Following up on the customer's request. The issue has been resolved and we've updated the system accordingly.",
  "is_public": false
}
```

**Example 7: Getting all lists/segments**
```json
{
  "processing_types": ["DYNAMIC", "MANUAL"],
  "include_filters": false
}
```

**Example 8: Getting list members with contact details**
```json
{
  "list_id": "1084",
  "limit": 500,
  "contact_properties": ["email", "firstname", "lastname", "company", "jobtitle"],
  "include_membership_timestamps": true
}
```

**Example 9: Searching for specific lists**
```json
{
  "query": "Customer",
  "count": 50,
  "processing_types": ["DYNAMIC"]
}
```

**Example 10: Get all associations for a contact**
```json
{
  "contact_id": "123456",
  "association_types": ["companies", "deals", "meetings", "tasks"],
  "limit": 200
}
```

**Response:**
```json
{
  "contact_id": "123456",
  "associations": {
    "companies": [
      {
        "toObjectId": "789012",
        "associationTypes": [
          {
            "category": "HUBSPOT_DEFINED",
            "typeId": 1,
            "label": "Primary"
          }
        ]
      }
    ],
    "deals": [
      {
        "toObjectId": "345678",
        "associationTypes": [
          {
            "category": "HUBSPOT_DEFINED",
            "typeId": 3,
            "label": null
          }
        ]
      }
    ],
    "tickets": [],
    "tasks": []
  },
  "total_associations": 2,
  "summary": {
    "companies_count": 1,
    "deals_count": 1,
    "tickets_count": 0,
    "tasks_count": 0
  }
}
```

**Example 11: Get all contacts and deals for a company**
```json
{
  "company_id": "789012",
  "association_types": ["contacts", "deals"]
}
```

**Example 12: Get all associated objects for a deal**
```json
{
  "deal_id": "345678",
  "association_types": ["contacts", "companies", "line_items"]
}
```

**Example 13: Discover all deal properties (including custom)**
```json
{
  "include_details": true
}
```

**Response:**
```json
{
  "properties": [
    {
      "name": "dealname",
      "label": "Deal Name",
      "type": "string",
      "fieldType": "text",
      "groupName": "dealinformation",
      "hubspotDefined": true
    },
    {
      "name": "custom_property_example",
      "label": "Custom Property Example",
      "type": "enumeration",
      "fieldType": "select",
      "groupName": "dealinformation",
      "hubspotDefined": false,
      "options": [
        {"label": "German Shepherd", "value": "german_shepherd"}
      ]
    }
  ],
  "total_properties": 45,
  "custom_properties_count": 3
}
```

**Example 14: Get deal with custom properties**
```json
{
  "deal_id": "123456",
  "properties": ["dealname", "amount", "closedate", "custom_property_example", "my_custom_field"]
}
```

**Response includes custom property values:**
```json
{
  "deal": {
    "id": "123456",
    "properties": {
      "dealname": "Q4 Enterprise Deal",
      "amount": "50000",
      "closedate": "31 Dec 2025 11:59 PM UTC",
      "custom_property_example": "german_shepherd",
      "my_custom_field": "Custom value here"
    }
  }
}
```

**Example 15: Get marketing emails**
```json
{
  "limit": 25,
  "archived": false
}
```

**Response:**
```json
{
  "emails": [
    {
      "id": "12345678",
      "name": "Q4 Newsletter",
      "subject": "Your Monthly Update",
      "type": "REGULAR",
      "state": "PUBLISHED",
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-10-15T14:30:00Z"
    }
  ],
  "total": 1,
  "paging": {
    "next": {
      "after": "abc123"
    }
  }
}
```

**Example 16: Get marketing email statistics**
```json
{
  "email_id": "12345678"
}
```

**Response:**
```json
{
  "email_id": "12345678",
  "statistics": {
    "sent": 5000,
    "delivered": 4850,
    "open": 1200,
    "click": 350,
    "bounce": 150,
    "unsubscribed": 25,
    "spam_report": 5,
    "open_rate": 0.247,
    "click_rate": 0.072,
    "bounce_rate": 0.03
  }
}
```

**Example 17: Get marketing campaigns**
```json
{
  "limit": 50
}
```

**Response:**
```json
{
  "campaigns": [
    {
      "id": "98765432",
      "name": "Product Launch 2025",
      "app_id": 113,
      "app_name": "MarketingEmail"
    }
  ],
  "total": 1
}
```

## Common Workflows

### Contact Management Workflow
1. Search for existing contact using `get_contact` by email
2. If contact doesn't exist, create new contact with `create_contact`
3. Update contact information as needed with `update_contact`
4. Add contact to marketing lists using `add_contact_to_list`
5. Track recent email conversations with `get_contact` (include_recent_emails: true)

### Note Management Workflow
1. Add notes to contacts after interactions using `create_note`
2. Associate notes with multiple objects (contact, company, deal) for complete context
3. Retrieve all notes for a contact using `get_contact_notes`
4. Update existing notes with new information using `update_note`
5. Delete outdated or incorrect notes using `delete_note`
6. Review notes across companies and deals using `get_company_notes` and `get_deal_notes`

### Sales Pipeline Management
1. Retrieve pipeline structure using `get_deal_pipelines`
2. Create deals using `create_deal` with proper stage and pipeline assignment
3. Search and filter deals using `search_deals` for specific criteria
4. Use `get_deals` with fetch_all for complete pipeline analysis
5. Update deal stages and properties as they progress with `update_deal`
6. For large pipelines, use `get_deals` with `delay_between_requests` to avoid rate limits

### Lists/Segments Management Workflow
1. Discover available lists using `get_lists` with optional filtering by processing types
2. Search for specific lists using `search_lists` with name queries
3. Get detailed list information with `get_list` including filter definitions for dynamic lists
4. Export list members with complete contact details using `get_list_members`
5. For performance-critical operations, use `get_list_memberships` to get raw member IDs first
6. Use pagination with appropriate limits to manage large lists (10K+ members)

### Associations Discovery Workflow
1. Get a contact by email using `get_contact`
2. Use `get_contact_associations` to retrieve all related objects (companies, deals, meetings)
3. For each associated company ID, use `get_company` to fetch company details
4. For each associated deal ID, use `get_deal` to fetch deal details with stage information
5. Cross-reference relationships using `get_company_associations` or `get_deal_associations`
6. Build a complete relationship map of the contact's CRM network

### Custom Properties Workflow
1. Use `get_deal_properties` with `include_details: true` to discover all available deal properties
2. Identify custom properties by checking `hubspotDefined: false`
3. Note the internal property `name` (e.g., "custom_property_example")
4. Use `get_deal` or `get_deals` with the `properties` parameter including your custom property names
5. Custom property values will be included in the response
6. For dropdown/select fields, the response contains the internal value (e.g., "german_shepherd" not "German Shepherd")

### Customer Support Workflow
1. Retrieve recent tickets using `get_recent_tickets` with status filtering
2. Get complete conversation history with `get_ticket_conversation`
3. Add internal notes or customer responses with `add_ticket_comment`
4. Update ticket properties as issues are resolved

### Company Account Management
1. Search for existing companies using `search_companies`
2. Create new company records with `create_company`
3. Retrieve complete company profiles with `get_company`
4. Update company information with `update_company`
5. Discover available properties with `get_company_properties`

### Marketing Analytics Workflow
1. List all marketing emails using `get_marketing_emails` to see email campaigns
2. Browse marketing campaigns using `get_campaigns` to see all campaign initiatives (filter by name if needed)
3. Get campaign details with `get_campaign` to see associated content and basic info
4. Get comprehensive performance metrics with `get_campaign_performance` for landing page views, email opens/clicks, form submissions
5. Drill down into specific asset types with `get_campaign_assets` (e.g., just landing pages or just emails)

### Advanced Deal Analytics
1. Use `get_deals` with specific pipeline_id for comprehensive pipeline analysis
2. Filter by year or date ranges for performance optimization
3. All dates are provided in UTC format for consistency
4. Implement pagination for large datasets to manage chat context
5. Use rate limiting actions for high-volume data processing

## Testing

To run the tests included with the integration:

1. Navigate to the integration's directory: `cd hubspot`
2. Install dependencies: `pip install -r requirements.txt`
3. Set up test environment with valid HubSpot test credentials
4. Run the tests: `python tests/test_hubspot.py`

The test suite includes:
- Authentication and token management tests
- Contact, company, and deal CRUD operation tests
- Ticket management and conversation threading tests
- Marketing emails and campaigns retrieval tests
- Pagination and rate limiting functionality tests
- Timezone conversion accuracy tests
- Error handling and validation tests

## API Limitations and Best Practices

- HubSpot API has rate limits (100 requests per 10 seconds for most endpoints)
- The integration includes built-in rate limiting and retry logic
- Large deal retrievals should use `get_deals` with `delay_between_requests` to avoid rate limits
- Date filtering works best with the integration's client-side post-processing
- All dates are returned in UTC format for consistency
- Pagination is essential for pipelines with 100+ deals
- Some properties may be read-only depending on your HubSpot subscription level

## Performance Optimization

- Use `fetch_all: false` (default) for initial exploration to avoid context overflow
- Enable `fetch_all: true` only when you need complete datasets
- Apply `year` or `date_range_months` filters to reduce response sizes
- Use `get_deals` with `delay_between_requests`: 1.0 for pipelines with 2000+ deals
- Implement `max_total` limits to prevent runaway queries
- Leverage pipeline_id filtering for focused analysis

## Support

For issues specific to this integration, check:
1. HubSpot API documentation and status
2. OAuth token validity and refresh requirements
3. Required permissions and scopes are granted
4. Rate limiting and pagination parameters
5. UTC date format consistency

For Autohive platform support, contact your Autohive administrator.

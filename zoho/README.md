# Zoho CRM Integration for Autohive

Connects Autohive to the Zoho CRM API to provide comprehensive customer relationship management capabilities, including contact management, sales pipeline tracking, lead conversion, and activity management.

## Description

This integration provides full access to Zoho CRM functionality through Autohive, enabling users to manage their entire customer lifecycle. It supports complete CRUD operations across all major CRM modules including contacts, accounts, deals, leads, tasks, events, and calls. The integration also provides advanced relationship mapping and custom query capabilities through Zoho's COQL query language.

Key features include:
- Complete contact and account management with detailed profile information
- Sales pipeline management with deal tracking and conversion
- Lead management with automated conversion workflows  
- Task and activity management for CRM productivity
- Event scheduling and call logging for communication tracking
- Advanced relationship queries and hierarchical data access
- Custom COQL queries for complex data operations

This integration interacts with Zoho CRM API v8 and supports all standard CRM operations with proper error handling and data validation.

## Setup & Authentication

The integration uses Zoho's OAuth 2.0 platform authentication. No manual API key configuration is required - authentication is handled automatically through Autohive's platform integration system.

**Required Scopes:**
The integration automatically requests the following Zoho CRM permissions:
- `ZohoCRM.modules.contacts.ALL` - Full access to contacts module
- `ZohoCRM.modules.accounts.ALL` - Full access to accounts module  
- `ZohoCRM.modules.deals.ALL` - Full access to deals module
- `ZohoCRM.modules.leads.ALL` - Full access to leads module
- `ZohoCRM.modules.tasks.ALL` - Full access to tasks module
- `ZohoCRM.modules.events.ALL` - Full access to events module
- `ZohoCRM.modules.calls.ALL` - Full access to calls module
- `ZohoCRM.coql.READ` - Access to execute COQL queries

**Setup Steps:**
1. Configure the Zoho integration in your Autohive platform
2. Authorize the integration through Zoho's OAuth flow
3. Grant the required permissions when prompted
4. The integration will automatically handle token management and refresh

## Actions

This integration provides 54 actions covering complete CRUD operations for all major Zoho CRM modules:

### Contact Management

#### Action: `create_contact`
- **Description:** Creates a new contact in Zoho CRM with detailed profile information
- **Inputs:**
  - `Last_Name` (required): Contact's last name
  - `First_Name`: Contact's first name
  - `Email`: Email address
  - `Phone`: Phone number
  - `Mobile`: Mobile number
  - `Account_Name`: Associated company/account name
  - `Title`: Job title
  - `Department`: Department
  - `Mailing_Street`, `Mailing_City`, `Mailing_State`, `Mailing_Zip`, `Mailing_Country`: Mailing address components
  - `Description`: Notes about the contact
- **Outputs:** Contact object with `id` and created contact details

#### Action: `get_contact`
- **Description:** Retrieves detailed information for a specific contact
- **Inputs:** `contact_id` (required): Unique identifier of the contact
- **Outputs:** Complete contact record with all fields

#### Action: `update_contact`
- **Description:** Updates an existing contact's information
- **Inputs:** `contact_id` (required) + any contact fields to update
- **Outputs:** Updated contact object

#### Action: `delete_contact`
- **Description:** Permanently deletes a contact from Zoho CRM
- **Inputs:** `contact_id` (required): Contact to delete
- **Outputs:** Confirmation of deletion

#### Action: `list_contacts`
- **Description:** Retrieves a paginated list of all contacts with filtering and sorting
- **Inputs:** `page`, `per_page`, `sort_by`, `sort_order` for pagination and sorting
- **Outputs:** Array of contact objects with pagination metadata

#### Action: `search_contacts`
- **Description:** Search contacts using various criteria
- **Inputs:** Search parameters and filters
- **Outputs:** Array of matching contact objects

### Notes Management

#### Action: `create_note`
- **Description:** Creates a note attached to any record (Lead, Contact, Account, Deal, etc.)
- **Inputs:**
  - `module` (required): Module name - one of: Contacts, Accounts, Deals, Leads, Tasks, Events, Calls
  - `record_id` (required): ID of the record to attach the note to
  - `Note_Content` (required): Content of the note
  - `Note_Title`: Title of the note (optional)
- **Outputs:** Note object with `id` and note details

#### Action: `get_contact_notes`
- **Description:** Retrieves all notes for a specific record with pagination
- **Inputs:**
  - `module` (required): Module name - one of: Contacts, Accounts, Deals, Leads, Tasks, Events, Calls
  - `record_id` (required): ID of the record
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of records per page, max 200 (optional)
  - `fields`: Array of specific fields to retrieve (optional)
- **Outputs:** Array of note objects with pagination info

#### Action: `get_note`
- **Description:** Retrieves a specific note by ID
- **Inputs:** `note_id` (required): Note to retrieve
- **Outputs:** Complete note record

#### Action: `update_note`
- **Description:** Updates a note's title or content
- **Inputs:** `note_id` (required), `Note_Title`, `Note_Content` (at least one required)
- **Outputs:** Updated note object

#### Action: `delete_note`
- **Description:** Permanently deletes a note
- **Inputs:** `note_id` (required): Note to delete
- **Outputs:** Confirmation of deletion

### Account Management

#### Action: `create_account`
- **Description:** Creates a new account/company in Zoho CRM
- **Inputs:**
  - `Account_Name` (required): Company name
  - `Account_Type`: Type of account (e.g., Customer, Partner)
  - `Industry`: Industry classification
  - `Annual_Revenue`: Company's annual revenue
  - `No_of_Employees`: Number of employees
  - `Phone`, `Fax`, `Website`: Company contact information
  - `Billing_Street`, `Billing_City`, `Billing_State`, `Billing_Code`, `Billing_Country`: Billing address
  - `Shipping_Street`, `Shipping_City`, `Shipping_State`, `Shipping_Code`, `Shipping_Country`: Shipping address
  - `Description`: Account description
- **Outputs:** Account object with `id` and account details

#### Action: `get_account`, `update_account`, `delete_account`, `list_accounts`, `search_accounts`
- **Description:** Standard CRUD operations for accounts (similar patterns to contacts)

### Deal Management

#### Action: `create_deal`
- **Description:** Creates a new sales deal/opportunity
- **Inputs:**
  - `Deal_Name` (required): Name of the deal
  - `Amount`: Deal value
  - `Stage`: Current sales stage
  - `Account_Name`: Associated account
  - `Contact_Name`: Primary contact
  - `Closing_Date`: Expected close date
  - `Type`: Deal type
  - `Lead_Source`: Source of the lead
  - `Next_Step`: Next action to take
  - `Probability`: Probability of closing (%)
  - `Description`: Deal description
- **Outputs:** Deal object with `id` and deal details

#### Action: `get_deal`, `update_deal`, `delete_deal`, `list_deals`, `search_deals`
- **Description:** Standard CRUD operations for deals

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

#### Action: `get_related_records`
- **Description:** Retrieves related records for a given record (e.g., contacts for an account)
- **Inputs:** `module_api_name`, `record_id`, `related_list_api_name`
- **Outputs:** Array of related records

#### Action: `get_account_hierarchy`
- **Description:** Gets the hierarchical relationship structure for an account
- **Inputs:** `account_id`
- **Outputs:** Account hierarchy tree structure

#### Action: `get_contact_activities`
- **Description:** Retrieves all activities (tasks, events, calls) for a specific contact
- **Inputs:** `contact_id`, optional filtering parameters
- **Outputs:** Array of activity records

#### Action: `get_deal_relationships`
- **Description:** Gets all related records and relationships for a deal
- **Inputs:** `deal_id`
- **Outputs:** Deal with all related contacts, accounts, activities

#### Action: `execute_coql_query`
- **Description:** Executes custom COQL (Zoho Creator Query Language) queries for complex data operations
- **Inputs:** `query` (required): COQL query string
- **Outputs:** Query results based on the query structure

#### Action: `update_related_records`
- **Description:** Updates multiple related records in a single operation
- **Inputs:** Parent record details and array of related records to update
- **Outputs:** Results of bulk update operation

## Requirements

The integration has the following dependencies:

* `autohive-integrations-sdk` - Core SDK for Autohive integrations

## Usage Examples

**Example 1: Creating a new contact**
```json
{
  "Last_Name": "Smith",
  "First_Name": "John", 
  "Email": "john.smith@company.com",
  "Phone": "+1-555-0123",
  "Account_Name": "Acme Corporation",
  "Title": "Sales Manager",
  "Department": "Sales"
}
```

**Example 2: Creating a sales deal**
```json
{
  "Deal_Name": "Q4 Enterprise Software Deal",
  "Amount": 50000,
  "Stage": "Proposal/Price Quote", 
  "Account_Name": "Acme Corporation",
  "Contact_Name": "John Smith",
  "Closing_Date": "2024-12-31",
  "Probability": 75,
  "Description": "Enterprise software license for 100 users"
}
```

**Example 3: Converting a qualified lead**
```json
{
  "lead_id": "123456789",
  "convert_to_contact": true,
  "convert_to_account": true,
  "convert_to_deal": true
}
```

**Example 4: Executing a custom COQL query**
```json
{
  "query": "SELECT First_Name, Last_Name, Email, Account_Name FROM Contacts WHERE Lead_Source = 'Website' AND Created_Time > '2024-01-01T00:00:00+00:00'"
}
```

**Example 5: Getting related records**
```json
{
  "module_api_name": "Accounts",
  "record_id": "123456789",
  "related_list_api_name": "Contacts"
}
```

**Example 6: Creating a note for a contact**
```json
{
  "module": "Contacts",
  "record_id": "123456789",
  "Note_Title": "Q4 Planning Discussion",
  "Note_Content": "Discussed Q4 requirements and timeline. Follow up needed on budget approval."
}
```

**Example 7: Creating a note for a deal**
```json
{
  "module": "Deals",
  "record_id": "987654321",
  "Note_Title": "Contract Negotiation",
  "Note_Content": "Client requested 15% discount. Approved by sales manager. Updated proposal sent."
}
```

## Common Workflows

### Lead-to-Deal Conversion Process
1. Create a lead using `create_lead`
2. Qualify the lead and update status with `update_lead`
3. Convert qualified lead to contact/account/deal using `convert_lead`
4. Manage the resulting deal through the sales pipeline with deal actions

### Customer Onboarding Workflow  
1. Create account using `create_account`
2. Add primary contact with `create_contact`
3. Create onboarding tasks with `create_task`
4. Schedule kickoff meeting with `create_event`
5. Track activities and follow-ups

### Sales Pipeline Management
1. Create deals from converted leads or new opportunities
2. Update deal stages and probability as they progress
3. Associate tasks and events for deal activities
4. Use `get_deal_relationships` to view complete deal context
5. Generate reports using COQL queries

## Testing

To run the tests included with the integration:

1. Navigate to the integration's directory: `cd Zoho`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Set up test environment with valid Zoho CRM test credentials
4. Run the tests: `python tests/test_integration.py`

The test suite includes:
- Authentication and token management tests
- CRUD operation tests for all major modules
- Error handling and validation tests  
- Advanced operations and COQL query tests

## API Limitations

- Zoho CRM API has rate limits (typically 100 calls per minute per organization)
- Some fields may be read-only depending on your Zoho CRM edition and configuration
- COQL queries have syntax limitations and performance considerations
- Related record operations depend on proper CRM module relationships being configured

## Support

For issues specific to this integration, check:
1. Zoho CRM API documentation and status
2. OAuth token validity and refresh requirements
3. Required permissions and scopes are granted
4. Field mappings align with your Zoho CRM configuration

For Autohive platform support, contact your Autohive administrator.

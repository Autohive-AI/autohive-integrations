# Pipedrive Integration

Pipedrive CRM integration for managing deals, contacts, organizations, activities, and sales pipelines.

## Features

### Deal Management
- Create, read, update, and delete deals (sales opportunities)
- List deals with filtering by status, stage, user, or custom filters
- Track deal values, currencies, and expected close dates
- Associate deals with persons and organizations

### Contact Management (Persons)
- Create, read, update, and delete persons (contacts)
- Store contact information including email and phone
- Link contacts to organizations
- Filter contacts by owner or custom filters

### Organization Management
- Create, read, update, and delete organizations (companies)
- Manage company information and addresses
- Associate organizations with deals and persons
- Filter organizations by owner or custom filters

### Activity Tracking
- Create and manage activities (tasks, calls, meetings, deadlines, emails, lunch)
- Schedule activities with due dates and times
- Set activity duration and completion status
- Link activities to deals, persons, and organizations
- Filter activities by type, status, and associations

### Notes
- Add notes to deals, persons, or organizations
- Support for HTML formatting in notes
- List notes with filtering options

### Pipeline & Stage Management
- View all sales pipelines
- Get pipeline details
- List stages for pipeline configuration

### Universal Search
- Search across all items (deals, persons, organizations, products)
- Filter search by item types
- Perform exact match searches
- Search in custom fields, notes, and emails

## Authentication

This integration uses Pipedrive API token authentication. You'll need:

- **API Token**: A valid Pipedrive API token (OAuth 2.0 or personal API token)

## Actions

### Deal Actions

#### create_deal
Create a new deal (sales opportunity) in Pipedrive.

**Inputs:**
- `title` (string, required): Deal title
- `value` (number, optional): Deal value
- `currency` (string, optional): Currency code (e.g., "USD", "EUR")
- `person_id` (integer, optional): ID of associated person
- `org_id` (integer, optional): ID of associated organization
- `pipeline_id` (integer, optional): Pipeline ID
- `stage_id` (integer, optional): Stage ID in the pipeline
- `status` (string, optional): Deal status (open, won, lost, deleted)
- `expected_close_date` (string, optional): Expected close date (YYYY-MM-DD)
- `user_id` (integer, optional): Owner user ID

**Output:**
- `deal` (object): Created deal details
- `result` (boolean): Success status

#### get_deal
Retrieve details of a specific deal.

**Inputs:**
- `deal_id` (integer, required): Deal ID

**Output:**
- `deal` (object): Deal details
- `result` (boolean): Success status

#### update_deal
Update an existing deal.

**Inputs:**
- `deal_id` (integer, required): Deal ID
- `title` (string, optional): Updated title
- `value` (number, optional): Updated value
- `currency` (string, optional): Updated currency
- `person_id` (integer, optional): Updated person ID
- `org_id` (integer, optional): Updated organization ID
- `stage_id` (integer, optional): Updated stage ID
- `status` (string, optional): Updated status
- `expected_close_date` (string, optional): Updated close date
- `user_id` (integer, optional): Updated owner ID

**Output:**
- `deal` (object): Updated deal details
- `result` (boolean): Success status

#### list_deals
List deals with optional filtering.

**Inputs:**
- `user_id` (integer, optional): Filter by owner user ID
- `stage_id` (integer, optional): Filter by stage ID
- `status` (string, optional): Filter by status
- `filter_id` (integer, optional): Saved filter ID
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)
- `sort` (string, optional): Sort field

**Output:**
- `deals` (array): List of deals
- `result` (boolean): Success status

#### delete_deal
Delete a deal permanently.

**Inputs:**
- `deal_id` (integer, required): Deal ID

**Output:**
- `result` (boolean): Success status

### Person Actions

#### create_person
Create a new person (contact).

**Inputs:**
- `name` (string, required): Person's name
- `email` (string, optional): Email address
- `phone` (string, optional): Phone number
- `org_id` (integer, optional): Organization ID
- `owner_id` (integer, optional): Owner user ID
- `visible_to` (string, optional): Visibility (1 = owner & followers, 3 = entire company)

**Output:**
- `person` (object): Created person details
- `result` (boolean): Success status

#### get_person
Retrieve details of a specific person.

**Inputs:**
- `person_id` (integer, required): Person ID

**Output:**
- `person` (object): Person details
- `result` (boolean): Success status

#### update_person
Update an existing person.

**Inputs:**
- `person_id` (integer, required): Person ID
- `name` (string, optional): Updated name
- `email` (string, optional): Updated email
- `phone` (string, optional): Updated phone
- `org_id` (integer, optional): Updated organization ID
- `owner_id` (integer, optional): Updated owner ID

**Output:**
- `person` (object): Updated person details
- `result` (boolean): Success status

#### list_persons
List persons with optional filtering.

**Inputs:**
- `user_id` (integer, optional): Filter by owner user ID
- `filter_id` (integer, optional): Saved filter ID
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)
- `sort` (string, optional): Sort field

**Output:**
- `persons` (array): List of persons
- `result` (boolean): Success status

#### delete_person
Delete a person permanently.

**Inputs:**
- `person_id` (integer, required): Person ID

**Output:**
- `result` (boolean): Success status

### Organization Actions

#### create_organization
Create a new organization (company).

**Inputs:**
- `name` (string, required): Organization name
- `owner_id` (integer, optional): Owner user ID
- `visible_to` (string, optional): Visibility setting
- `address` (string, optional): Organization address

**Output:**
- `organization` (object): Created organization details
- `result` (boolean): Success status

#### get_organization
Retrieve details of a specific organization.

**Inputs:**
- `org_id` (integer, required): Organization ID

**Output:**
- `organization` (object): Organization details
- `result` (boolean): Success status

#### update_organization
Update an existing organization.

**Inputs:**
- `org_id` (integer, required): Organization ID
- `name` (string, optional): Updated name
- `owner_id` (integer, optional): Updated owner ID
- `address` (string, optional): Updated address

**Output:**
- `organization` (object): Updated organization details
- `result` (boolean): Success status

#### list_organizations
List organizations with optional filtering.

**Inputs:**
- `user_id` (integer, optional): Filter by owner user ID
- `filter_id` (integer, optional): Saved filter ID
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)
- `sort` (string, optional): Sort field

**Output:**
- `organizations` (array): List of organizations
- `result` (boolean): Success status

#### delete_organization
Delete an organization permanently.

**Inputs:**
- `org_id` (integer, required): Organization ID

**Output:**
- `result` (boolean): Success status

### Activity Actions

#### create_activity
Create a new activity (task, call, meeting, etc.).

**Inputs:**
- `subject` (string, required): Activity subject/title
- `type` (string, required): Activity type (call, meeting, task, deadline, email, lunch)
- `due_date` (string, optional): Due date (YYYY-MM-DD)
- `due_time` (string, optional): Due time (HH:MM)
- `duration` (string, optional): Duration (HH:MM)
- `deal_id` (integer, optional): Associated deal ID
- `person_id` (integer, optional): Associated person ID
- `org_id` (integer, optional): Associated organization ID
- `user_id` (integer, optional): Assigned user ID
- `note` (string, optional): Activity note/description
- `done` (integer, optional): Completion status (0 = not done, 1 = done)

**Output:**
- `activity` (object): Created activity details
- `result` (boolean): Success status

#### get_activity
Retrieve details of a specific activity.

**Inputs:**
- `activity_id` (integer, required): Activity ID

**Output:**
- `activity` (object): Activity details
- `result` (boolean): Success status

#### update_activity
Update an existing activity.

**Inputs:**
- `activity_id` (integer, required): Activity ID
- `subject` (string, optional): Updated subject
- `type` (string, optional): Updated type
- `due_date` (string, optional): Updated due date
- `due_time` (string, optional): Updated due time
- `duration` (string, optional): Updated duration
- `done` (integer, optional): Updated completion status
- `note` (string, optional): Updated note

**Output:**
- `activity` (object): Updated activity details
- `result` (boolean): Success status

#### list_activities
List activities with optional filtering.

**Inputs:**
- `user_id` (integer, optional): Filter by user ID
- `deal_id` (integer, optional): Filter by deal ID
- `person_id` (integer, optional): Filter by person ID
- `org_id` (integer, optional): Filter by organization ID
- `type` (string, optional): Filter by activity type
- `done` (boolean, optional): Filter by completion status
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)

**Output:**
- `activities` (array): List of activities
- `result` (boolean): Success status

#### delete_activity
Delete an activity permanently.

**Inputs:**
- `activity_id` (integer, required): Activity ID

**Output:**
- `result` (boolean): Success status

### Note Actions

#### create_note
Add a note to a deal, person, or organization.

**Inputs:**
- `content` (string, required): Note content (supports HTML)
- `deal_id` (integer, optional): Deal ID to attach to
- `person_id` (integer, optional): Person ID to attach to
- `org_id` (integer, optional): Organization ID to attach to

**Output:**
- `note` (object): Created note details
- `result` (boolean): Success status

#### list_notes
List notes with optional filtering.

**Inputs:**
- `deal_id` (integer, optional): Filter by deal ID
- `person_id` (integer, optional): Filter by person ID
- `org_id` (integer, optional): Filter by organization ID
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)

**Output:**
- `notes` (array): List of notes
- `result` (boolean): Success status

### Pipeline & Stage Actions

#### list_pipelines
List all pipelines.

**Inputs:** None

**Output:**
- `pipelines` (array): List of pipelines
- `result` (boolean): Success status

#### get_pipeline
Get details of a specific pipeline.

**Inputs:**
- `pipeline_id` (integer, required): Pipeline ID

**Output:**
- `pipeline` (object): Pipeline details
- `result` (boolean): Success status

#### list_stages
List stages, optionally filtered by pipeline.

**Inputs:**
- `pipeline_id` (integer, optional): Filter by pipeline ID

**Output:**
- `stages` (array): List of stages
- `result` (boolean): Success status

### Search Action

#### search
Search across all items.

**Inputs:**
- `term` (string, required): Search term
- `item_types` (array, optional): Item types to search (deal, person, organization, product)
- `fields` (array, optional): Fields to search (custom_fields, notes, emails)
- `exact_match` (boolean, optional): Perform exact match
- `start` (integer, optional): Pagination start (default: 0)
- `limit` (integer, optional): Items per page (default: 100, max: 500)

**Output:**
- `items` (array): Search results
- `result` (boolean): Success status

## Technical Details

### API Endpoints

- Base URL: `https://api.pipedrive.com/v1`
- Authentication: API token (OAuth 2.0 or personal token)

### Activity Types

Pipedrive supports the following activity types:
- `call` - Phone call
- `meeting` - Meeting
- `task` - General task
- `deadline` - Deadline
- `email` - Email
- `lunch` - Lunch meeting

### Deal Statuses

- `open` - Deal is active
- `won` - Deal is won
- `lost` - Deal is lost
- `deleted` - Deal is deleted

### Rate Limits

Pipedrive API has the following rate limits:
- Standard plan: 100 requests per 10 seconds
- Professional plan: 200 requests per 10 seconds
- Enterprise plan: Custom limits

### Best Practices

1. Use filters to reduce API calls when listing items
2. Implement pagination for large datasets (max 500 items per request)
3. Cache pipeline and stage data as they change infrequently
4. Use the search endpoint for cross-entity queries
5. Store Pipedrive IDs in your system for future reference
6. Handle rate limit errors with exponential backoff

## Example Usage

### Create a Deal with Contact
```python
# First, create a person
person_inputs = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890"
}

# Then create a deal associated with the person
deal_inputs = {
    "title": "Enterprise License Deal",
    "value": 50000,
    "currency": "USD",
    "person_id": person_response['person']['id'],
    "stage_id": 1,
    "status": "open",
    "expected_close_date": "2025-03-31"
}
```

### Schedule a Follow-up Activity
```python
activity_inputs = {
    "subject": "Follow-up call with John",
    "type": "call",
    "due_date": "2025-01-15",
    "due_time": "14:00",
    "duration": "00:30",
    "deal_id": deal_id,
    "person_id": person_id,
    "note": "Discuss contract terms and pricing"
}
```

### Search for Contacts
```python
search_inputs = {
    "term": "john@example.com",
    "item_types": ["person"],
    "exact_match": True
}
```

### List Open Deals
```python
list_inputs = {
    "status": "open",
    "sort": "update_time DESC",
    "limit": 50
}
```

## Resources

- [Pipedrive API Documentation](https://developers.pipedrive.com/docs/api/v1)
- [Pipedrive API Reference](https://developers.pipedrive.com/docs/api/v1)
- [Pipedrive OAuth Guide](https://pipedrive.readme.io/docs/marketplace-oauth-authorization)
- [API Rate Limits](https://pipedrive.readme.io/docs/core-api-concepts-rate-limiting)

## Version

1.0.0

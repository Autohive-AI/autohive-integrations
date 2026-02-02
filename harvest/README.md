# Harvest Integration for Autohive

Connects Autohive to the Harvest API to enable time tracking, project management, client management, and team collaboration directly from Autohive workflows.

## Description

This integration provides comprehensive Harvest time tracking functionality, allowing users to log time entries, manage projects and clients, track team members, and organize billable work. It supports both manual time entry logging and running timers, with flexible filtering and pagination for all resources.

Key features:
- Create, update, and delete time entries
- Start and stop running timers
- List and filter time entries by project, client, user, date range, and billing status
- Manage projects, clients, tasks, and users
- Full pagination support for large datasets
- OAuth2 authentication for secure access

## Setup & Authentication

The integration uses Harvest's OAuth2 platform authentication. Users need to authenticate through Harvest's OAuth flow within Autohive to grant access permissions.

**Authentication Type:** Platform (Harvest)

**Required OAuth Configuration:**
- Authorization URL: `https://id.getharvest.com/oauth2/authorize`
- Token URL: `https://id.getharvest.com/api/v2/oauth2/token`
- Scopes: None required (handled automatically by Harvest)

**To Set Up OAuth App:**
1. Go to https://id.getharvest.com/developers
2. Click "Create new OAuth Application"
3. Enter your application name and redirect URL
4. Select "Harvest" product access
5. Copy the Client ID and Client Secret for Autohive configuration

No additional configuration fields are required as authentication is handled through Harvest's OAuth2 flow.

## Actions

### Action: `create_time_entry`

- **Description:** Create a new time entry to log work hours for a project and task
- **Inputs:**
  - `project_id`: The ID of the project (required)
  - `task_id`: The ID of the task (required)
  - `spent_date`: The date the work was performed (YYYY-MM-DD format, required)
  - `notes`: Description of work performed (optional)
  - `hours`: Number of hours to log (optional, use this OR started_time/ended_time)
  - `started_time`: Start time in HH:MM format (optional, e.g., '08:00')
  - `ended_time`: End time in HH:MM format (optional, e.g., '17:00')
  - `is_running`: Start a running timer (optional, boolean)
  - `user_id`: User ID for the entry (optional, defaults to authenticated user)
  - `external_reference`: External reference metadata (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `time_entry`: Created time entry object with ID, hours, notes, project, task details
  - `error`: Error message if operation failed

### Action: `stop_time_entry`

- **Description:** Stop a currently running time entry timer
- **Inputs:**
  - `time_entry_id`: The ID of the running time entry to stop (required)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `time_entry`: Updated time entry object with final hours calculated
  - `error`: Error message if operation failed

### Action: `list_time_entries`

- **Description:** Retrieve a list of time entries with comprehensive filtering options
- **Inputs:**
  - `user_id`: Filter by user ID (optional)
  - `client_id`: Filter by client ID (optional)
  - `project_id`: Filter by project ID (optional)
  - `task_id`: Filter by task ID (optional)
  - `is_billed`: Filter by billed status (optional, boolean)
  - `is_running`: Filter for running timers only (optional, boolean)
  - `updated_since`: Filter entries updated after this date (optional, ISO 8601)
  - `from`: Start date for date range (optional, YYYY-MM-DD)
  - `to`: End date for date range (optional, YYYY-MM-DD)
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of results per page, max 2000 (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `time_entries`: Array of time entry objects
  - `per_page`: Results per page
  - `total_pages`: Total number of pages
  - `total_entries`: Total number of entries
  - `next_page`: Next page number (null if no more pages)
  - `previous_page`: Previous page number (null if on first page)
  - `page`: Current page number
  - `links`: Pagination links
  - `error`: Error message if operation failed

### Action: `update_time_entry`

- **Description:** Update an existing time entry's details
- **Inputs:**
  - `time_entry_id`: The ID of the time entry to update (required)
  - `project_id`: New project ID (optional)
  - `task_id`: New task ID (optional)
  - `spent_date`: New spent date (optional, YYYY-MM-DD)
  - `notes`: Updated notes (optional)
  - `hours`: Updated hours (optional)
  - `started_time`: Updated start time (optional, HH:MM)
  - `ended_time`: Updated end time (optional, HH:MM)
  - `external_reference`: Updated external reference (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `time_entry`: Updated time entry object
  - `error`: Error message if operation failed

### Action: `delete_time_entry`

- **Description:** Permanently delete a time entry from Harvest
- **Inputs:**
  - `time_entry_id`: The ID of the time entry to delete (required)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `message`: Success message with deleted entry ID
  - `error`: Error message if operation failed

### Action: `list_projects`

- **Description:** Retrieve a list of all projects in Harvest with optional filtering
- **Inputs:**
  - `is_active`: Filter by active status (optional, boolean - true for active, false for archived)
  - `client_id`: Filter by client ID (optional)
  - `updated_since`: Filter projects updated after this date (optional, ISO 8601)
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of results per page, max 2000 (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `projects`: Array of project objects with name, code, client, budget, billing details
  - `per_page`: Results per page
  - `total_pages`: Total number of pages
  - `total_entries`: Total number of projects
  - `next_page`: Next page number (null if no more pages)
  - `previous_page`: Previous page number (null if on first page)
  - `page`: Current page number
  - `links`: Pagination links
  - `error`: Error message if operation failed

### Action: `get_project`

- **Description:** Retrieve detailed information about a specific project by ID
- **Inputs:**
  - `project_id`: The ID of the project to retrieve (required)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `project`: Complete project object with all details, task assignments, user assignments
  - `error`: Error message if operation failed

### Action: `list_clients`

- **Description:** Retrieve a list of all clients in Harvest with optional filtering
- **Inputs:**
  - `is_active`: Filter by active status (optional, boolean - true for active, false for archived)
  - `updated_since`: Filter clients updated after this date (optional, ISO 8601)
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of results per page, max 2000 (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `clients`: Array of client objects with name, address, currency
  - `per_page`: Results per page
  - `total_pages`: Total number of pages
  - `total_entries`: Total number of clients
  - `next_page`: Next page number (null if no more pages)
  - `previous_page`: Previous page number (null if on first page)
  - `page`: Current page number
  - `links`: Pagination links
  - `error`: Error message if operation failed

### Action: `list_tasks`

- **Description:** Retrieve a list of all tasks in Harvest with optional filtering
- **Inputs:**
  - `is_active`: Filter by active status (optional, boolean - true for active, false for archived)
  - `updated_since`: Filter tasks updated after this date (optional, ISO 8601)
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of results per page, max 2000 (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `tasks`: Array of task objects with name, billable status, default hourly rate
  - `per_page`: Results per page
  - `total_pages`: Total number of pages
  - `total_entries`: Total number of tasks
  - `next_page`: Next page number (null if no more pages)
  - `previous_page`: Previous page number (null if on first page)
  - `page`: Current page number
  - `links`: Pagination links
  - `error`: Error message if operation failed

### Action: `list_users`

- **Description:** Retrieve a list of all users (team members) in Harvest with optional filtering
- **Inputs:**
  - `is_active`: Filter by active status (optional, boolean - true for active, false for archived)
  - `updated_since`: Filter users updated after this date (optional, ISO 8601)
  - `page`: Page number for pagination (optional)
  - `per_page`: Number of results per page, max 2000 (optional)
- **Outputs:**
  - `success`: Boolean indicating if operation succeeded
  - `users`: Array of user objects with name, email, role, capacity, rates
  - `per_page`: Results per page
  - `total_pages`: Total number of pages
  - `total_entries`: Total number of users
  - `next_page`: Next page number (null if no more pages)
  - `previous_page`: Previous page number (null if on first page)
  - `page`: Current page number
  - `links`: Pagination links
  - `error`: Error message if operation failed

## Requirements

- Python dependencies are handled by the Autohive platform
- Harvest account with API access (free trial accounts supported)
- OAuth2 application registered at https://id.getharvest.com/developers

## Usage Examples

**Example 1: Log 3 hours of work to a project**

```json
{
  "project_id": 23456789,
  "task_id": 12345678,
  "spent_date": "2025-01-21",
  "hours": 3.0,
  "notes": "Implemented user authentication feature"
}
```

**Example 2: Start a running timer**

```json
{
  "project_id": 23456789,
  "task_id": 12345678,
  "spent_date": "2025-01-21",
  "is_running": true,
  "notes": "Working on API integration"
}
```

**Example 3: Get time entries for last week**

```json
{
  "from": "2025-01-14",
  "to": "2025-01-21",
  "is_billed": false,
  "per_page": 50
}
```

**Example 4: List all active projects for a specific client**

```json
{
  "client_id": 5678901,
  "is_active": true,
  "per_page": 100
}
```

**Example 5: Update time entry hours and notes**

```json
{
  "time_entry_id": 987654321,
  "hours": 4.5,
  "notes": "Updated: Completed feature implementation and code review"
}
```

## Common Workflows

**Workflow 1: Log Time to a Project**
1. Use `list_projects` to get available projects
2. Use `list_tasks` to get available task types
3. Use `create_time_entry` with the project_id, task_id, date, and hours

**Workflow 2: Track Time with Running Timer**
1. Use `create_time_entry` with `is_running: true` to start timer
2. Work on your task
3. Use `stop_time_entry` when done - hours are calculated automatically

**Workflow 3: View Team's Time This Week**
1. Use `list_time_entries` with date range filters (`from` and `to` dates)
2. Optionally filter by `user_id` to see specific team member's time
3. Check `is_billed` status to see what's been invoiced

**Workflow 4: Get Unbilled Time for Invoicing**
1. Use `list_time_entries` with `is_billed: false`
2. Filter by `client_id` or `project_id` as needed
3. Review entries before generating invoices

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd harvest`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Update test credentials in `tests/test_harvest.py` with your Harvest OAuth token and account ID
4. Update `project_id` and `task_id` with actual values from your Harvest account
5. Run the tests: `python tests/test_harvest.py`

The test suite includes tests for all 10 actions:
- Time Entry Actions: create, stop, list, update, delete
- Resource Actions: list projects, get project, list clients, list tasks, list users

## API Rate Limits

Harvest API has the following rate limits:
- General API endpoints: 100 requests per 15 seconds
- Reports API endpoints: 100 requests per 15 minutes

The integration handles rate limit responses (HTTP 429) automatically through the Autohive SDK.

## Version History

- **0.1.0** - Initial release with 10 core actions for time tracking and resource management

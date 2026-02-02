# Float Integration for Autohive

Comprehensive Float API integration for resource management, project scheduling, time tracking, and team management. This integration provides full access to Float's core resources including people, projects, tasks/allocations, time off, logged time, clients, departments, and roles.

## Description

Float is a resource management and project scheduling platform designed to help teams plan their work, track time, and manage resources effectively. This integration enables Autohive workflows to:

- Manage team members and their information
- Create and organize projects with clients
- Schedule tasks and allocations across team members
- Track time off and manage leave types
- Log actual time worked on projects
- Manage client relationships
- Organize teams by departments and roles
- Track project expenses and milestones
- Generate utilization and project reports
- Manage holidays and team-specific non-working days
- Configure project stages and phases

The integration follows Float's REST API v3 specifications and implements proper authentication, rate limiting awareness, and comprehensive error handling.

## Setup & Authentication

### Getting Your API Key

1. Log in to your Float account
2. Navigate to **Account Settings** > **Integrations**
3. Find the API section at `https://{your-company-name}.float.com/admin/api`
4. Generate or copy your API key
5. Store the API key securely

### Authentication Configuration

The integration requires the following configuration fields:

#### Required Fields

1. **API Key** (required)
   - Your Float API key from Account Settings > Integrations
   - Format: Password field (hidden)

2. **Contact Email** (required)
   - Your contact email address for Float API support
   - Float requires this to identify API users and contact them if needed
   - Format: Valid email address
   - Example: `john.doe@yourcompany.com`

3. **Application Name** (optional)
   - The name of your application or integration
   - Defaults to: "Autohive Float Integration"
   - Example: "Acme Corp Float Integration"
   - Used in User-Agent header as: `{Application Name} ({Contact Email})`

#### Technical Details

- **Authentication Method**: Bearer token (passed in `Authorization` header)
- **Required Header**: `User-Agent` with format: `Application Name (contact@email.com)`
- **API Base URL**: `https://api.float.com/v3`
- **Content Type**: `application/json`

The User-Agent header is automatically constructed from your Application Name and Contact Email to comply with Float's API identification requirements.

## Rate Limiting

The Float API implements the following rate limits to ensure optimal performance for all users:

### Primary Data Endpoints
- **GET requests**: 200 requests per minute per company
- **Burst limit**: 10 GET requests per second
- **Non-GET requests** (POST, PATCH, DELETE): 100 requests per minute
- **Burst limit**: 4 non-GET requests per second

### Reports Endpoints
- **GET requests**: 30 requests per minute

### Rate Limit Response
- When rate limits are exceeded, the API returns a **429 Error** with message: "too many requests by this user"
- Wait briefly before retrying requests

## Actions

The integration provides 60 actions organized by resource type:

### People Management

Manage team members and their information including roles, departments, rates, and availability.

#### `list_people`
- **Description**: List all people/team members with filtering and pagination
- **Key Inputs**:
  - `active` (boolean): Filter by active status
  - `department_id` (integer): Filter by department
  - `modified_since` (string): Get people modified since date (YYYY-MM-DD)
  - `page`, `per_page`: Pagination parameters
  - `fields`: Comma-separated fields to return
  - `sort`: Sort field (prefix with '-' for descending)
- **Outputs**: List of people with pagination info

#### `get_person`
- **Description**: Get details of a specific person
- **Inputs**:
  - `people_id` (integer, required): Person ID
  - `expand` (string): Related resources to expand (e.g., 'contracts')
- **Outputs**: Person details

#### `create_person`
- **Description**: Create a new team member
- **Required Inputs**:
  - `name` (string): Full name
- **Optional Inputs**:
  - `email`: Email address
  - `job_title`: Job title
  - `department_id`, `role_id`: Department and role assignment
  - `active`: Active status (default: true)
  - `employee_type`: 1=Full-time, 2=Part-time, 3=Contractor
  - `start_date`, `end_date`: Employment dates
  - `cost_rate`, `bill_rate`: Hourly rates
  - `tags`: Array of tags
  - `notes`: Additional notes
- **Outputs**: Created person details with ID

#### `update_person`
- **Description**: Update existing person information
- **Required Inputs**:
  - `people_id` (integer): Person to update
- **Optional Inputs**: Same as create_person plus:
  - `effective_date`: Date for rate changes to take effect
  - `expand`: Related resources to include in response
- **Outputs**: Updated person details

#### `delete_person`
- **Description**: Delete a person from Float
- **Inputs**: `people_id` (integer, required)
- **Outputs**: Success confirmation

### Project Management

Create and manage projects, including client associations, budgets, teams, and timelines.

#### `list_projects`
- **Description**: List all projects with filtering
- **Key Inputs**:
  - `active` (boolean): Filter by active status
  - `client_id` (integer): Filter by client
  - `project_manager` (integer): Filter by PM
  - `start_date`, `end_date`: Date range filters
  - `modified_since`: Get projects modified since date
  - Pagination: `page`, `per_page`
- **Outputs**: List of projects

#### `get_project`
- **Description**: Get project details
- **Inputs**: `project_id` (integer, required)
- **Outputs**: Project details

#### `create_project`
- **Description**: Create a new project
- **Required Inputs**:
  - `name` (string): Project name
- **Optional Inputs**:
  - `client_id`: Associate with client
  - `color`: Hex color code (e.g., 'FF2D00')
  - `project_code`: External system identifier (max 32 chars)
  - `tags`: Array of tags
  - `project_team`: Array of people IDs
  - `project_manager`: PM's account ID
  - `budget_type`: 0=none, 1=total, 2=per phase
  - `budget_total`: Total budget amount
  - `non_billable`: Non-billable flag
  - `start_date`, `end_date`: Project timeline
  - `active`: Active status
  - `notes`: Project notes
- **Outputs**: Created project with ID

#### `update_project`
- **Description**: Update existing project
- **Required Inputs**: `project_id`
- **Optional Inputs**: Any project fields to update
- **Outputs**: Updated project details

#### `delete_project`
- **Description**: Delete a project
- **Inputs**: `project_id` (integer, required)
- **Outputs**: Success confirmation

### Tasks/Allocations Management

Schedule and manage task allocations across team members and projects.

#### `list_tasks`
- **Description**: List all tasks/allocations with filtering
- **Key Inputs**:
  - `people_id`, `project_id`: Filter by person or project
  - `start_date`, `end_date`: Date range
  - `modified_since`: Tasks modified since date
  - Pagination parameters
- **Outputs**: List of tasks/allocations

#### `get_task`
- **Description**: Get task details
- **Inputs**: `task_id` (integer, required)
- **Outputs**: Task details

#### `create_task`
- **Description**: Create a new task/allocation
- **Required Inputs**:
  - `people_id` (integer): Person assigned
  - `project_id` (integer): Project
  - `start_date`, `end_date` (string): Date range (YYYY-MM-DD)
  - `hours` (number): Hours per day
- **Optional Inputs**:
  - `name`: Task name
  - `notes`: Task notes
  - `status`: Task status
  - `billable`: Billable flag
  - `repeat_state`: 0=none, 1=weekly, 2=monthly, 3=bi-weekly
  - `repeat_end_date`: End date for repeating tasks
- **Outputs**: Created task with ID

#### `update_task`
- **Description**: Update existing task/allocation
- **Required Inputs**: `task_id`
- **Optional Inputs**: Any task fields to update
- **Outputs**: Updated task details

#### `delete_task`
- **Description**: Delete a task/allocation
- **Inputs**: `task_id` (integer, required)
- **Outputs**: Success confirmation

### Time Off Management

Schedule and track team member time off, vacations, and leave.

#### `list_time_off`
- **Description**: List all time off entries
- **Key Inputs**:
  - `people_id`: Filter by person
  - `timeoff_type_id`: Filter by time off type
  - `start_date`, `end_date`: Date range
  - Pagination parameters
- **Outputs**: List of time off entries

#### `get_time_off`
- **Description**: Get time off details
- **Inputs**: `timeoff_id` (integer, required)
- **Outputs**: Time off details

#### `create_time_off`
- **Description**: Create a new time off entry
- **Required Inputs**:
  - `people_id` (integer): Person
  - `timeoff_type_id` (integer): Type of time off
  - `start_date`, `end_date` (string): Date range
  - `hours` (number): Hours per day
- **Optional Inputs**:
  - `full_day` (boolean): Full day flag
  - `notes`: Additional notes
- **Outputs**: Created time off entry

#### `update_time_off`
- **Description**: Update time off entry
- **Required Inputs**: `timeoff_id`
- **Optional Inputs**: Any time off fields to update
- **Outputs**: Updated time off details

#### `delete_time_off`
- **Description**: Delete time off entry
- **Inputs**: `timeoff_id` (integer, required)
- **Outputs**: Success confirmation

### Logged Time Management

Track actual time worked on projects and tasks.

#### `list_logged_time`
- **Description**: List all logged time entries
- **Key Inputs**:
  - `people_id`, `project_id`: Filter by person or project
  - `start_date`, `end_date`: Date range
  - Pagination parameters
- **Outputs**: List of logged time entries

#### `get_logged_time`
- **Description**: Get logged time details
- **Inputs**: `logged_time_id` (string, required): Hexadecimal ID
- **Outputs**: Logged time details

#### `create_logged_time`
- **Description**: Log time worked
- **Required Inputs**:
  - `people_id` (integer): Person
  - `project_id` (integer): Project
  - `date` (string): Date (YYYY-MM-DD)
  - `hours` (number): Hours logged
- **Optional Inputs**:
  - `task_id` (integer): Associated task
  - `notes`: Description of work
  - `billable` (boolean): Billable flag
- **Outputs**: Created logged time entry

#### `update_logged_time`
- **Description**: Update logged time entry
- **Required Inputs**: `logged_time_id` (string)
- **Optional Inputs**: `hours`, `notes`, `billable`
- **Outputs**: Updated logged time details

#### `delete_logged_time`
- **Description**: Delete logged time entry
- **Inputs**: `logged_time_id` (string, required)
- **Outputs**: Success confirmation

### Client Management

Manage client organizations and relationships.

#### `list_clients`
- **Description**: List all clients
- **Key Inputs**:
  - `active` (boolean): Filter by active status
  - `modified_since`: Clients modified since date
  - Pagination parameters
- **Outputs**: List of clients

#### `get_client`
- **Description**: Get client details
- **Inputs**: `client_id` (integer, required)
- **Outputs**: Client details

#### `create_client`
- **Description**: Create a new client
- **Required Inputs**: `name` (string)
- **Optional Inputs**:
  - `active` (boolean): Active status
  - `notes`: Client notes
- **Outputs**: Created client with ID

#### `update_client`
- **Description**: Update existing client
- **Required Inputs**: `client_id`
- **Optional Inputs**: `name`, `active`, `notes`
- **Outputs**: Updated client details

#### `delete_client`
- **Description**: Delete a client
- **Inputs**: `client_id` (integer, required)
- **Outputs**: Success confirmation

### Department Management

View and manage organizational departments.

#### `list_departments`
- **Description**: List all departments
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of departments

#### `get_department`
- **Description**: Get department details
- **Inputs**: `department_id` (integer, required)
- **Outputs**: Department details

### Role Management

View and manage team roles.

#### `list_roles`
- **Description**: List all roles
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of roles

#### `get_role`
- **Description**: Get role details
- **Inputs**: `role_id` (integer, required)
- **Outputs**: Role details

### Time Off Type Management

View available time off types (vacation, sick leave, etc.).

#### `list_time_off_types`
- **Description**: List all time off types
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of time off types

#### `get_time_off_type`
- **Description**: Get time off type details
- **Inputs**: `timeoff_type_id` (integer, required)
- **Outputs**: Time off type details

### Account Management

View account information and settings.

#### `list_accounts`
- **Description**: List all accounts in the organization
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of accounts

#### `get_account`
- **Description**: Get account details
- **Inputs**: `account_id` (integer, required)
- **Outputs**: Account details including settings and preferences

### Status Management

Manage task and project statuses.

#### `list_statuses`
- **Description**: List all available statuses
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of statuses

#### `get_status`
- **Description**: Get status details
- **Inputs**: `status_id` (integer, required)
- **Outputs**: Status details including name and color

### Public Holiday Management

View and manage public holidays for your organization.

#### `list_public_holidays`
- **Description**: List all public holidays
- **Key Inputs**:
  - `country_id` (integer): Filter by country
  - `year` (integer): Filter by year
  - Pagination parameters
- **Outputs**: List of public holidays

#### `get_public_holiday`
- **Description**: Get public holiday details
- **Inputs**: `public_holiday_id` (integer, required)
- **Outputs**: Public holiday details

### Team Holiday Management

Manage team-specific holidays and non-working days.

#### `list_team_holidays`
- **Description**: List all team holidays
- **Key Inputs**:
  - `start_date`, `end_date`: Date range filters
  - Pagination parameters
- **Outputs**: List of team holidays

#### `get_team_holiday`
- **Description**: Get team holiday details
- **Inputs**: `team_holiday_id` (integer, required)
- **Outputs**: Team holiday details

### Project Stage Management

Manage project stages and workflow steps.

#### `list_project_stages`
- **Description**: List all project stages
- **Inputs**: Pagination parameters (optional)
- **Outputs**: List of project stages

#### `get_project_stage`
- **Description**: Get project stage details
- **Inputs**: `project_stage_id` (integer, required)
- **Outputs**: Project stage details

### Project Expense Management

Track and manage project-related expenses.

#### `list_project_expenses`
- **Description**: List all project expenses
- **Key Inputs**:
  - `project_id` (integer): Filter by project
  - `start_date`, `end_date`: Date range
  - Pagination parameters
- **Outputs**: List of project expenses

#### `get_project_expense`
- **Description**: Get project expense details
- **Inputs**: `project_expense_id` (integer, required)
- **Outputs**: Project expense details

### Phase Management

Manage project phases for complex project structures.

#### `list_phases`
- **Description**: List all project phases
- **Key Inputs**:
  - `project_id` (integer): Filter by project
  - Pagination parameters
- **Outputs**: List of phases

#### `get_phase`
- **Description**: Get phase details
- **Inputs**: `phase_id` (integer, required)
- **Outputs**: Phase details

### Project Task Management

Manage default task names and templates for projects.

#### `list_project_tasks`
- **Description**: List all project task templates
- **Key Inputs**:
  - `project_id` (integer): Filter by project
  - Pagination parameters
- **Outputs**: List of project task templates

#### `get_project_task`
- **Description**: Get project task template details
- **Inputs**: `project_task_id` (integer, required)
- **Outputs**: Project task template details

#### `merge_project_tasks`
- **Description**: Merge project task templates
- **Required Inputs**:
  - `source_project_task_id` (integer): Source task template
  - `target_project_task_id` (integer): Target task template
- **Outputs**: Merged task template details

### Milestone Management

Track and manage project milestones.

#### `list_milestones`
- **Description**: List all project milestones
- **Key Inputs**:
  - `project_id` (integer): Filter by project
  - `start_date`, `end_date`: Date range
  - Pagination parameters
- **Outputs**: List of milestones

#### `get_milestone`
- **Description**: Get milestone details
- **Inputs**: `milestone_id` (integer, required)
- **Outputs**: Milestone details

### Reports

Generate analytical reports for people and projects.

#### `get_people_report`
- **Description**: Get comprehensive people utilization report
- **Key Inputs**:
  - `start_date` (string, required): Report start date (YYYY-MM-DD)
  - `end_date` (string, required): Report end date (YYYY-MM-DD)
  - `people_ids` (array): Filter specific people
  - `department_ids` (array): Filter by departments
  - `include_placeholders` (boolean): Include placeholder resources
- **Outputs**: Detailed people utilization report with hours and availability

#### `get_projects_report`
- **Description**: Get comprehensive projects report
- **Key Inputs**:
  - `start_date` (string, required): Report start date (YYYY-MM-DD)
  - `end_date` (string, required): Report end date (YYYY-MM-DD)
  - `project_ids` (array): Filter specific projects
  - `client_ids` (array): Filter by clients
  - `include_archived` (boolean): Include archived projects
- **Outputs**: Detailed projects report with allocations and budgets

## Requirements

The integration requires the following dependencies:

- `autohive_integrations_sdk` - Autohive integration framework

These are automatically installed by the Autohive platform when the integration is loaded.

## Usage Examples

### Example 1: List Active Team Members

List all active people in your Float account:

```json
{
  "active": true,
  "per_page": 50
}
```

### Example 2: Create a New Project

Create a project with client association and team:

```json
{
  "name": "Website Redesign",
  "client_id": 123,
  "color": "FF5733",
  "project_team": [45, 67, 89],
  "project_manager": 45,
  "start_date": "2025-01-15",
  "end_date": "2025-03-31",
  "budget_type": 1,
  "budget_total": 50000,
  "active": true
}
```

### Example 3: Schedule a Task/Allocation

Assign a team member to a project:

```json
{
  "people_id": 67,
  "project_id": 456,
  "start_date": "2025-01-20",
  "end_date": "2025-02-10",
  "hours": 6,
  "name": "Frontend Development",
  "billable": true,
  "notes": "Focus on React components"
}
```

### Example 4: Create Time Off

Schedule vacation time:

```json
{
  "people_id": 45,
  "timeoff_type_id": 1,
  "start_date": "2025-03-10",
  "end_date": "2025-03-14",
  "hours": 8,
  "full_day": true,
  "notes": "Annual vacation"
}
```

### Example 5: Log Time Worked

Record time worked on a project:

```json
{
  "people_id": 67,
  "project_id": 456,
  "date": "2025-01-20",
  "hours": 7.5,
  "task_id": 789,
  "billable": true,
  "notes": "Completed user authentication module"
}
```

### Example 6: Update Person's Rate

Update cost and bill rates with effective date:

```json
{
  "people_id": 45,
  "cost_rate": 75,
  "bill_rate": 150,
  "effective_date": "2025-02-01",
  "expand": "contracts"
}
```

### Example 7: Generate People Utilization Report

Get a report of team utilization for a date range:

```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "department_ids": [5, 12],
  "include_placeholders": false
}
```

### Example 8: Get Project Report

Generate a comprehensive projects report:

```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-03-31",
  "client_ids": [123, 456],
  "include_archived": false
}
```

### Example 9: List Project Milestones

View all milestones for a specific project:

```json
{
  "project_id": 456,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31"
}
```

## Error Handling

The integration implements comprehensive error handling:

- **Authentication Errors**: Clear messages when API key is invalid or missing
- **Rate Limiting**: Automatic detection of 429 errors with descriptive messages
- **Validation Errors**: Detailed error messages for invalid input parameters
- **Network Errors**: Proper handling of connectivity issues
- **Resource Not Found**: Clear messages when requested resources don't exist

All errors are caught and returned with descriptive error messages to help diagnose issues.

## API Features & Limitations

### Supported Features

- Full CRUD operations for core resources
- Pagination support (up to 200 items per page)
- Field filtering to optimize response size
- Sorting capabilities
- Date range filtering
- Modified-since filtering for efficient sync
- Relationship expansion (e.g., contracts with people)
- Repeating task support

### Important Notes

1. **Date Format**: All dates use `YYYY-MM-DD` format
2. **ID Types**: Most IDs are integers, except `logged_time_id` which is hexadecimal
3. **Pagination**: Default page size is 50, maximum is 200
4. **Boolean Filters**: Active filters use `1` for true and `0` for false in API calls
5. **Rate Limits**: Automatic handling in headers, but best practice is to batch operations
6. **Employee Types**: 1 = Full-time, 2 = Part-time, 3 = Contractor
7. **Budget Types**: 0 = none, 1 = total, 2 = per phase
8. **Repeat States**: 0 = none, 1 = weekly, 2 = monthly, 3 = bi-weekly

### Read-Only Resources

The following resources are available for viewing but do not support create/update/delete operations:

- Accounts (list, get)
- Statuses (list, get)
- Departments (list, get)
- Roles (list, get)
- Time Off Types (list, get)
- Public Holidays (list, get)
- Team Holidays (list, get)
- Project Stages (list, get)
- Project Expenses (list, get)
- Phases (list, get)
- Project Tasks (list, get, merge)
- Milestones (list, get)
- Reports (people, projects)

## Testing

To test the integration:

1. Navigate to the integration directory: `cd float`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run tests: `python tests/test_float.py`

Ensure you have a valid Float API key configured in your test environment.

## Best Practices

1. **Rate Limiting**: Batch operations when possible to stay within rate limits
2. **Pagination**: Use appropriate `per_page` values based on your needs (max 200)
3. **Field Filtering**: Use `fields` parameter to request only needed data
4. **Modified Since**: Use `modified_since` filters for efficient data synchronization
5. **Error Handling**: Always check for errors in responses and handle 429 rate limit errors
6. **Date Validation**: Ensure dates are in correct YYYY-MM-DD format before submitting
7. **Unique Identifiers**: Store returned IDs for future reference and updates

## Support & Documentation

- **Float API Documentation**: [https://developer.float.com/](https://developer.float.com/)
- **Float Help Center**: [https://support.float.com/](https://support.float.com/)
- **Rate Limiting Details**: [https://developer.float.com/overview_authentication.html](https://developer.float.com/overview_authentication.html)
- **Autohive Support**: Contact your Autohive account representative

## SDK Features

### ActionResult Return Type

All action handlers now return `ActionResult` objects instead of plain dictionaries. This enables:

- **Cost Tracking**: Each action can report API costs (currently set to $0.00 for Float since it doesn't charge per-API-call)
- **Structured Responses**: Consistent response format across all integrations
- **Future Extensibility**: Easy to add metadata without breaking existing code

Example response structure:
```python
ActionResult(
    data={
        "people_id": 123,
        "name": "John Doe",
        "email": "john@example.com"
    },
    cost_usd=0.0
)
```

### Connected Account Information

The integration now supports displaying which Float account was used to authorize the integration. When a user connects their Float account, the platform will:

1. Automatically fetch account information
2. Cache it in the database
3. Display "Connected to **account@email.com** for everyone in **Company Name**"

This provides transparency about which credentials are being used and which workspace the integration is connected to.

The connected account handler fetches:
- Email address of the account owner
- Account owner's name
- Organization/company name
- Unique account identifier

## Version History

### Version 1.2.0 (Latest)
- Updated to new SDK ActionResult return type for cost tracking support
- Added connected account information display
- All actions now return structured ActionResult objects
- Enhanced transparency with account information caching
- Improved SDK compatibility

### Version 1.1.0
- Added 23 new actions covering all remaining Float API endpoints
- Implemented Accounts, Statuses, Public Holidays, Team Holidays, Project Stages, Project Expenses, Phases, Project Tasks, Milestones, and Reports resources
- Total of 60 actions covering complete Float API v3
- Enhanced documentation with additional usage examples

### Version 1.0.0
- Initial release
- Complete implementation of People, Projects, Tasks, Time Off, Logged Time, Clients, Departments, Roles, and Time Off Types resources
- 37 actions covering all major Float API operations
- Full rate limiting awareness
- Comprehensive error handling
- Complete documentation

## License

This integration is provided as part of the Autohive platform. Refer to your Autohive license agreement for terms and conditions.

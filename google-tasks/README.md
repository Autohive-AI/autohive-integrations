# Google Tasks Integration for Autohive

Connects Autohive to the Google Tasks API to enable comprehensive task management capabilities including listing task lists and performing full CRUD operations on tasks.

## Description

This integration provides comprehensive access to Google Tasks, allowing you to automate task management workflows. You can list and access existing task lists, then create, read, update, and delete tasks with due dates and notes, manage subtasks, and track completion status.

Key features:
- List and access existing task lists (read-only)
- Full CRUD operations on tasks (create, read, update, delete)
- Create and organize tasks with due dates, notes, and status
- Support for subtasks and task positioning
- Filter and search tasks by completion status and due dates
- Pagination support for large task lists (up to 2,000 lists and 20,000 tasks per list)

This integration uses the Google Tasks API v1.

## Setup & Authentication

This integration uses OAuth 2.0 authentication through the Autohive platform. When you configure this integration in Autohive, you'll be prompted to authenticate with your Google account.

**Required OAuth Scope:**
- `https://www.googleapis.com/auth/tasks` - Full access to Google Tasks

**Authentication Process:**
1. Add the Google Tasks integration in Autohive
2. Click "Connect" to initiate OAuth flow
3. Sign in with your Google account
4. Grant access to manage your Google Tasks
5. The integration will handle authentication automatically for all API calls

## Actions

### Action: `list_tasklists`

- **Description:** Returns all task lists for the authenticated user (maximum 2,000 task lists)
- **Inputs:**
  - `maxResults` (integer, optional): Maximum number of task lists to return (default: 100)
  - `pageToken` (string, optional): Token for retrieving a specific results page
- **Outputs:**
  - `tasklists` (array): List of task list objects
  - `nextPageToken` (string, optional): Token for the next page if more results exist
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `get_tasklist`

- **Description:** Retrieves details of a specific task list
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
- **Outputs:**
  - `tasklist` (object): Task list details including id, title, and updated timestamp
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `create_task`

- **Description:** Creates a new task in the specified task list
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `title` (string, required): Task title (max 1,024 characters)
  - `notes` (string, optional): Task notes/description (max 8,192 characters)
  - `due` (string, optional): Due date in RFC 3339 format (date only, time is discarded)
  - `status` (string, optional): Task status - either "needsAction" or "completed"
  - `parent` (string, optional): Parent task identifier to create a subtask
  - `previous` (string, optional): Previous sibling task identifier for positioning
- **Outputs:**
  - `task` (object): Created task details with id, title, status, etc.
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `list_tasks`

- **Description:** Returns all tasks in the specified task list (maximum 20,000 non-hidden tasks)
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `maxResults` (integer, optional): Maximum number of tasks to return (default: 100)
  - `pageToken` (string, optional): Token for retrieving a specific results page
  - `showCompleted` (boolean, optional): Include completed tasks (default: true)
  - `showHidden` (boolean, optional): Include hidden/cleared tasks (default: false)
  - `dueMin` (string, optional): Lower bound for task due date (RFC 3339 timestamp)
  - `dueMax` (string, optional): Upper bound for task due date (RFC 3339 timestamp)
- **Outputs:**
  - `tasks` (array): List of task objects
  - `nextPageToken` (string, optional): Token for the next page if more results exist
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `get_task`

- **Description:** Retrieves details of a specific task
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `task` (string, required): Task identifier
- **Outputs:**
  - `task` (object): Task details including id, title, notes, due date, status, etc.
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `update_task`

- **Description:** Updates an existing task with new information
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `task` (string, required): Task identifier
  - `title` (string, optional): Updated task title
  - `notes` (string, optional): Updated task notes
  - `due` (string, optional): Updated due date (RFC 3339 format)
  - `status` (string, optional): Updated status - "needsAction" or "completed"
- **Outputs:**
  - `task` (object): Updated task details
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `delete_task`

- **Description:** Permanently deletes a task from the task list
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `task` (string, required): Task identifier
- **Outputs:**
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

### Action: `move_task`

- **Description:** Moves a task to a different position in the list or converts it to a subtask
- **Inputs:**
  - `tasklist` (string, required): Task list identifier
  - `task` (string, required): Task identifier to move
  - `parent` (string, optional): New parent task identifier to create a subtask (omit to move to top level)
  - `previous` (string, optional): Previous sibling task identifier for positioning (omit to move to first position)
- **Outputs:**
  - `task` (object): Moved task details with updated position
  - `result` (boolean): Whether the operation succeeded
  - `error` (string, optional): Error message if the operation failed

## Requirements

- `autohive-integrations-sdk` - Autohive platform SDK for building integrations

## Usage Examples

**Example 1: Creating a Task with Due Date**

Create a new task in your default task list with a due date:

```json
{
  "tasklist": "MTk3NjQwNzE5NTc4MDk5MTQ0MDk6MDow",
  "title": "Complete project report",
  "notes": "Include Q4 metrics and analysis",
  "due": "2024-12-31T00:00:00.000Z",
  "status": "needsAction"
}
```

**Example 2: Listing Incomplete Tasks**

Get all incomplete tasks from a specific task list:

```json
{
  "tasklist": "MTk3NjQwNzE5NTc4MDk5MTQ0MDk6MDow",
  "showCompleted": false,
  "maxResults": 50
}
```

**Example 3: Creating a Subtask**

Create a subtask under an existing parent task:

```json
{
  "tasklist": "MTk3NjQwNzE5NTc4MDk5MTQ0MDk6MDow",
  "title": "Review first draft",
  "parent": "parent_task_id_here"
}
```

**Example 4: Marking a Task Complete**

Update a task's status to completed:

```json
{
  "tasklist": "MTk3NjQwNzE5NTc4MDk5MTQ0MDk6MDow",
  "task": "task_id_here",
  "status": "completed"
}
```

**Example 5: Filtering Tasks by Date Range**

Find tasks due within a specific date range:

```json
{
  "tasklist": "MTk3NjQwNzE5NTc4MDk5MTQ0MDk6MDow",
  "dueMin": "2024-01-01T00:00:00.000Z",
  "dueMax": "2024-01-31T23:59:59.000Z"
}
```

## Testing

To run the tests included with this integration:

1. Navigate to the integration's directory: `cd google-tasks`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Set up test credentials (OAuth token or mock authentication)
4. Run the tests: `python tests/test_google-tasks.py`

The test suite covers:
- Listing task lists
- Creating, reading, updating, and deleting tasks
- Task positioning and subtask creation
- Error handling scenarios

## Notes

- Task list and task IDs are opaque strings provided by Google Tasks API
- Due dates use RFC 3339 format, but only the date portion is used (time is discarded)
- Maximum limits: 2,000 task lists per user, 20,000 non-hidden tasks per list
- Pagination is supported via `pageToken` for large result sets
- All operations require valid OAuth authentication with the appropriate scope

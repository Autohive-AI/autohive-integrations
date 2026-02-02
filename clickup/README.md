# ClickUp Integration for Autohive

Connects Autohive to the ClickUp API to enable task management, list organization, folder and space management, and team collaboration automation.

## Description

This integration provides a comprehensive connection to ClickUp's project management platform. It allows users to automate task creation, list management, folder and space organization, team collaboration, and workflow automation directly from Autohive.

The integration uses ClickUp API v2 with OAuth 2.0 authentication and implements 22 comprehensive actions covering tasks, lists, folders, spaces, teams, and comments.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your ClickUp account.

### Authentication Method

 **OAuth 2.0** (Used by this integration)
   - Provides secure, token-based authentication
   - Users authorize access to their workspace(s)
   - Tokens are managed automatically by the platform
   - Recommended for multi-user integrations



### Setup Steps in Autohive

1. Add ClickUp integration in Autohive
2. Click "Connect to ClickUp" to authorize the integration
3. Sign in to your ClickUp account when prompted
4. Authorize the requested permissions for your workspace(s)
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh, so you don't need to manually manage access tokens.

## ClickUp Hierarchy

Understanding ClickUp's organizational structure:

```
Team (Workspace)
  └─ Space
      ├─ Folder
      │   └─ List
      │       └─ Task
      └─ List (Folderless)
          └─ Task
```

- **Team/Workspace**: The top-level organizational unit
- **Space**: Contains folders and lists
- **Folder**: Optional container for lists
- **List**: Contains tasks
- **Task**: Individual work items

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains an error message if the action failed
- Additional action-specific data fields (e.g., `task`, `list`, `folder`)

Example successful response:
```json
{
  "result": true,
  "task": { "id": "abc123", "name": "My Task" }
}
```

Example error response:
```json
{
  "result": false,
  "error": "Task not found",
  "task": {}
}
```

## Actions

### Tasks (5 actions)

#### `create_task`
Creates a new task in a list.

**Inputs:**
- `list_id` (required): The ID of the list to create the task in
- `name` (required): Task name/title
- `description` (optional): Task description (supports markdown)
- `assignees` (optional): Array of user IDs to assign to the task
- `status` (optional): Status name (e.g., 'Open', 'In Progress', 'Complete')
- `priority` (optional): Priority level: 1 (Urgent), 2 (High), 3 (Normal), 4 (Low)
- `due_date` (optional): Due date in Unix timestamp milliseconds
- `due_date_time` (optional): Whether the due date includes time (boolean)
- `start_date` (optional): Start date in Unix timestamp milliseconds
- `tags` (optional): Array of tag names

**Outputs:**
- `task`: Created task object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_task`
Retrieves details of a specific task by ID.

**Inputs:**
- `task_id` (required): The ID of the task
- `include_subtasks` (optional): Include subtasks in the response (boolean)

**Outputs:**
- `task`: Task object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `update_task`
Updates an existing task.

**Inputs:**
- `task_id` (required): The ID of the task to update
- `name` (optional): Updated task name
- `description` (optional): Updated task description
- `status` (optional): Updated status name
- `priority` (optional): Updated priority level (1-4)
- `assignees` (optional): Assignee operations with `add` and `rem` arrays
- `due_date` (optional): Updated due date (Unix timestamp ms)

**Outputs:**
- `task`: Updated task object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_task`
Deletes a task permanently.

**Inputs:**
- `task_id` (required): The ID of the task to delete

**Outputs:**
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_tasks`
Get tasks from a list with optional filtering.

**Inputs:**
- `list_id` (required): The ID of the list to get tasks from
- `archived` (optional): Include archived tasks (boolean)
- `page` (optional): Page number for pagination
- `order_by` (optional): Order by field (e.g., 'created', 'updated', 'due_date')
- `reverse` (optional): Reverse the order (boolean)
- `subtasks` (optional): Include subtasks (boolean)
- `statuses` (optional): Filter by status names (array)
- `assignees` (optional): Filter by assignee user IDs (array)

**Outputs:**
- `tasks`: Array of task objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Lists (5 actions)

#### `create_list`
Creates a new list in a folder or space.

**Inputs:**
- `name` (required): List name
- `folder_id` (optional): The ID of the folder (required if space_id not provided)
- `space_id` (optional): The ID of the space (required if folder_id not provided)
- `content` (optional): List description
- `due_date` (optional): Due date in Unix timestamp milliseconds
- `priority` (optional): Priority level (1-4)
- `status` (optional): Status for the list

**Outputs:**
- `list`: Created list object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_list`
Retrieves details of a specific list.

**Inputs:**
- `list_id` (required): The ID of the list

**Outputs:**
- `list`: List object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `update_list`
Updates an existing list.

**Inputs:**
- `list_id` (required): The ID of the list to update
- `name` (optional): Updated list name
- `content` (optional): Updated list description
- `due_date` (optional): Updated due date
- `priority` (optional): Updated priority

**Outputs:**
- `list`: Updated list object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_list`
Deletes a list permanently.

**Inputs:**
- `list_id` (required): The ID of the list to delete

**Outputs:**
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_lists`
Get all lists in a folder or space.

**Inputs:**
- `folder_id` (optional): The ID of the folder (required if space_id not provided)
- `space_id` (optional): The ID of the space (required if folder_id not provided)
- `archived` (optional): Include archived lists (boolean)

**Outputs:**
- `lists`: Array of list objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Folders (5 actions)

#### `create_folder`
Creates a new folder in a space.

**Inputs:**
- `space_id` (required): The ID of the space
- `name` (required): Folder name

**Outputs:**
- `folder`: Created folder object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_folder`
Retrieves details of a specific folder.

**Inputs:**
- `folder_id` (required): The ID of the folder

**Outputs:**
- `folder`: Folder object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `update_folder`
Updates an existing folder.

**Inputs:**
- `folder_id` (required): The ID of the folder to update
- `name` (required): Updated folder name

**Outputs:**
- `folder`: Updated folder object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_folder`
Deletes a folder permanently.

**Inputs:**
- `folder_id` (required): The ID of the folder to delete

**Outputs:**
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_folders`
Get all folders in a space.

**Inputs:**
- `space_id` (required): The ID of the space
- `archived` (optional): Include archived folders (boolean)

**Outputs:**
- `folders`: Array of folder objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Spaces (2 actions)

#### `get_space`
Retrieves details of a specific space.

**Inputs:**
- `space_id` (required): The ID of the space

**Outputs:**
- `space`: Space object with details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_spaces`
Get all spaces in a team/workspace.

**Inputs:**
- `team_id` (required): The ID of the team/workspace
- `archived` (optional): Include archived spaces (boolean)

**Outputs:**
- `spaces`: Array of space objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Teams/Workspaces (1 action)

#### `get_authorized_teams`
Get all teams/workspaces the authenticated user has access to.

**Inputs:** None

**Outputs:**
- `teams`: Array of authorized teams/workspaces
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Comments (4 actions)

#### `create_task_comment`
Adds a comment to a task.

**Inputs:**
- `task_id` (required): The ID of the task
- `comment_text` (required): The comment text (supports markdown)
- `assignee` (optional): User ID to assign the comment to
- `notify_all` (optional): Notify all task assignees (boolean)

**Outputs:**
- `comment`: Created comment object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_task_comments`
Gets all comments for a task.

**Inputs:**
- `task_id` (required): The ID of the task

**Outputs:**
- `comments`: Array of comment objects
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `update_comment`
Updates an existing comment.

**Inputs:**
- `comment_id` (required): The ID of the comment to update
- `comment_text` (required): Updated comment text

**Outputs:**
- `comment`: Updated comment object
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_comment`
Deletes a comment permanently.

**Inputs:**
- `comment_id` (required): The ID of the comment to delete

**Outputs:**
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URL**: `https://api.clickup.com/api/v2`
- **Authentication**: OAuth 2.0
- **Documentation**: https://developer.clickup.com/
- **Rate Limits**:
  - 100 requests per minute per user
  - Varies by plan tier

## Important Notes

- OAuth tokens are automatically managed by the platform
- Tokens are automatically refreshed when needed
- You can revoke access at any time from your ClickUp account settings
- All task responses return up to 100 tasks per page (use pagination for more)
- IDs in ClickUp are strings, not integers
- Unix timestamps should be in milliseconds (not seconds)
- Priority levels: 1 = Urgent, 2 = High, 3 = Normal, 4 = Low

## Testing

To test the integration:

1. Navigate to the integration directory: `cd clickup`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OAuth credentials through the Autohive platform
4. Run tests: `python tests/test_clickup.py`

## Common Use Cases

**Task Automation:**
1. Create tasks from external triggers (emails, forms, webhooks)
2. Update task status as work progresses
3. Assign tasks to team members
4. Set priorities and due dates
5. Add tags for categorization
6. Delete obsolete tasks

**List Management:**
1. Create lists in folders or spaces
2. Update list properties
3. Get all lists in a folder or space
4. Delete completed or obsolete lists

**Folder & Space Organization:**
1. Create folders to organize lists
2. Get folder and space details
3. Update folder names
4. List all folders in a space
5. Get all spaces in a workspace

**Team Collaboration:**
1. Add comments to tasks for updates
2. View all comments on a task
3. Update existing comments
4. Get all authorized teams/workspaces

**Workflow Automation:**
1. Create project templates with spaces, folders, and lists
2. Auto-assign tasks based on rules
3. Update task statuses through workflow stages
4. Add status updates as comments
5. Organize tasks with tags and priorities

## Version History

- **1.0.0** - Initial release with 22 comprehensive actions
  - Tasks: create, get, update, delete, get_tasks (5 actions)
  - Lists: create, get, update, delete, get_lists (5 actions)
  - Folders: create, get, update, delete, get_folders (5 actions)
  - Spaces: get, get_spaces (2 actions)
  - Teams: get_authorized_teams (1 action)
  - Comments: create, get_task_comments, update, delete (4 actions)

## Additional Resources

- [ClickUp API Documentation](https://developer.clickup.com/)
- [ClickUp API Authentication](https://developer.clickup.com/docs/authentication)
- [ClickUp API Reference](https://developer.clickup.com/reference)
- [ClickUp Help Center](https://help.clickup.com/)

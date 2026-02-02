# Microsoft Planner Integration for Autohive

Connects Autohive to the Microsoft Planner API (via Microsoft Graph API v1.0) to allow users to manage plans, tasks, buckets, and checklists within Microsoft 365 groups.

## Description

This integration provides comprehensive access to Microsoft Planner functionality through the Microsoft Graph API. It enables users to:

- **Manage Plans**: Create, update, delete, and list plans within Microsoft 365 groups
- **Organize Tasks**: Create and manage buckets to organize tasks
- **Task Management**: Full CRUD operations on tasks with support for assignments, due dates, priorities, categories, and progress tracking
- **Checklist Operations**: Add, update, and remove checklist items within tasks
- **User Management**: Search for users, get user details, and list user-specific tasks and plans
- **Task Details**: Manage task descriptions, references, and preview types
- **Board Views**: Control task ordering in different board views (assigned-to, bucket, progress)

The integration handles Microsoft API complexities including ETag management for optimistic concurrency, proper assignment formatting, and data cleaning for read-only fields.

## Setup & Authentication

This integration uses **OAuth 2.0 Platform Authentication** through Microsoft's identity platform. Users authenticate via Microsoft's OAuth flow to grant the integration access to their Planner data.

**Required Scopes:**
- `Tasks.ReadWrite` - Read and write access to Planner tasks
- `Group.ReadWrite.All` - Access to Microsoft 365 groups
- `User.Read` - Read user profile information
- `offline_access` - Maintain access via refresh tokens

**Setup Steps:**

1. In Autohive, add the Microsoft Planner integration to your workspace
2. Click "Connect" to initiate the OAuth flow
3. Sign in with your Microsoft account
4. Grant the requested permissions
5. You'll be redirected back to Autohive with the integration connected

## Actions

### Group Management

#### `list_groups`
- **Description:** List all Microsoft 365 groups the authenticated user is a member of
- **Inputs:**
  - `limit` (optional): Maximum number of groups to return (default: 100)
- **Outputs:**
  - `groups`: Array of group objects
  - `result`: Boolean indicating success

### User Operations

#### `get_current_user`
- **Description:** Get the currently authenticated user's information including their user_id
- **Inputs:** None
- **Outputs:**
  - `user`: Full user object
  - `user_id`: User's unique identifier (GUID)
  - `display_name`: User's display name
  - `email`: User's email address
  - `result`: Boolean indicating success

#### `get_user_by_email`
- **Description:** Get user information by email address to retrieve their user ID
- **Inputs:**
  - `email`: Email address to look up
- **Outputs:**
  - `user`: Full user object
  - `user_id`: User's unique identifier
  - `display_name`: User's display name
  - `email`: User's email address
  - `result`: Boolean indicating success

#### `search_users`
- **Description:** Search for users by display name or email
- **Inputs:**
  - `query`: Search query (name or email)
  - `limit` (optional): Maximum results (default: 10)
- **Outputs:**
  - `users`: Array of matching users with IDs, names, and emails
  - `result`: Boolean indicating success

#### `list_user_tasks`
- **Description:** List all tasks assigned to a user (defaults to current user)
- **Inputs:**
  - `user_id` (optional): Specific user ID or 'me' for current user
- **Outputs:**
  - `tasks`: Array of task objects
  - `result`: Boolean indicating success

#### `list_user_plans`
- **Description:** List all plans shared with a user (defaults to current user)
- **Inputs:**
  - `user_id` (optional): Specific user ID or 'me' for current user
- **Outputs:**
  - `plans`: Array of plan objects
  - `result`: Boolean indicating success

### Plan Management

#### `list_plans`
- **Description:** List all plans owned by a specific group
- **Inputs:**
  - `group_id`: The ID of the group
- **Outputs:**
  - `plans`: Array of plan objects
  - `result`: Boolean indicating success

#### `get_plan`
- **Description:** Get details of a specific plan by its ID
- **Inputs:**
  - `plan_id`: The plan ID
- **Outputs:**
  - `plan`: Plan object with details
  - `result`: Boolean indicating success

#### `create_plan`
- **Description:** Create a new plan in a Microsoft 365 group
- **Inputs:**
  - `title`: Plan title
  - `group_id`: Group ID to create the plan in
  - `container` (optional): Custom container object
- **Outputs:**
  - `plan`: Created plan object
  - `result`: Boolean indicating success

#### `update_plan`
- **Description:** Update a plan's title
- **Inputs:**
  - `plan_id`: Plan ID to update
  - `title`: New title
- **Outputs:**
  - `plan`: Updated plan object
  - `result`: Boolean indicating success

#### `delete_plan`
- **Description:** Delete a plan
- **Inputs:**
  - `plan_id`: Plan ID to delete
- **Outputs:**
  - `result`: Boolean indicating success

#### `get_plan_details`
- **Description:** Get plan details including category descriptions
- **Inputs:**
  - `plan_id`: The plan ID
- **Outputs:**
  - `plan_details`: Plan details object
  - `result`: Boolean indicating success

#### `update_plan_details`
- **Description:** Update plan details including category descriptions
- **Inputs:**
  - `plan_id`: Plan ID
  - `category_descriptions` (optional): Object mapping category names to descriptions
  - `shared_with` (optional): Object mapping user IDs to sharing details
- **Outputs:**
  - `plan_details`: Updated plan details
  - `result`: Boolean indicating success

### Bucket Management

#### `list_buckets`
- **Description:** List all buckets in a specific plan
- **Inputs:**
  - `plan_id`: The plan ID
- **Outputs:**
  - `buckets`: Array of bucket objects
  - `result`: Boolean indicating success

#### `get_bucket`
- **Description:** Get details of a specific bucket
- **Inputs:**
  - `bucket_id`: The bucket ID
- **Outputs:**
  - `bucket`: Bucket object
  - `result`: Boolean indicating success

#### `create_bucket`
- **Description:** Create a new bucket in a plan
- **Inputs:**
  - `name`: Bucket name
  - `plan_id`: Plan ID
  - `order_hint` (optional): Ordering hint
- **Outputs:**
  - `bucket`: Created bucket object
  - `result`: Boolean indicating success

#### `update_bucket`
- **Description:** Update a bucket's name
- **Inputs:**
  - `bucket_id`: Bucket ID
  - `name`: New name
- **Outputs:**
  - `bucket`: Updated bucket object
  - `result`: Boolean indicating success

#### `delete_bucket`
- **Description:** Delete a bucket from a plan
- **Inputs:**
  - `bucket_id`: Bucket ID to delete
- **Outputs:**
  - `result`: Boolean indicating success

#### `list_bucket_tasks`
- **Description:** List all tasks in a specific bucket
- **Inputs:**
  - `bucket_id`: The bucket ID
- **Outputs:**
  - `tasks`: Array of task objects
  - `result`: Boolean indicating success

### Task Management

#### `list_tasks`
- **Description:** List all tasks in a specific plan
- **Inputs:**
  - `plan_id`: The plan ID
- **Outputs:**
  - `tasks`: Array of task objects
  - `result`: Boolean indicating success

#### `get_task`
- **Description:** Get details of a specific task
- **Inputs:**
  - `task_id`: The task ID
- **Outputs:**
  - `task`: Task object
  - `result`: Boolean indicating success

#### `create_task`
- **Description:** Create a new task in a plan
- **Inputs:**
  - `plan_id`: Plan ID
  - `bucket_id`: Bucket ID
  - `title`: Task title
  - `assignments` (optional): Object mapping user IDs to assignment objects
  - `due_date_time` (optional): Due date in ISO 8601 format
  - `start_date_time` (optional): Start date in ISO 8601 format
  - `percent_complete` (optional): Completion percentage (0-100)
  - `priority` (optional): Priority (0-10, where 0 is urgent)
  - `applied_categories` (optional): Object mapping category names to boolean values
- **Outputs:**
  - `task`: Created task object
  - `result`: Boolean indicating success

**Important:** For assignments, you must use actual Microsoft user IDs (GUIDs). First call `get_current_user`, `get_user_by_email`, or `search_users` to get user IDs.

#### `update_task`
- **Description:** Update an existing task
- **Inputs:**
  - `task_id`: Task ID to update
  - `title` (optional): New title
  - `bucket_id` (optional): Move to different bucket
  - `assignments` (optional): Updated assignments (use user GUIDs)
  - `due_date_time` (optional): Updated due date
  - `start_date_time` (optional): Updated start date
  - `percent_complete` (optional): Updated completion (0-100)
  - `priority` (optional): Updated priority (0-10)
  - `applied_categories` (optional): Updated categories
  - `assignee_priority` (optional): Order hint for assignee view
  - `conversation_thread_id` (optional): Thread ID
  - `order_hint` (optional): Order hint for list views
- **Outputs:**
  - `task`: Updated task object
  - `result`: Boolean indicating success

#### `delete_task`
- **Description:** Delete a task
- **Inputs:**
  - `task_id`: Task ID to delete
- **Outputs:**
  - `result`: Boolean indicating success

### Task Details

#### `get_task_details`
- **Description:** Get task details including description, checklist, and references
- **Inputs:**
  - `task_id`: The task ID
- **Outputs:**
  - `task_details`: Task details object
  - `result`: Boolean indicating success

#### `update_task_details`
- **Description:** Update task details including description, checklist, references
- **Inputs:**
  - `task_id`: Task ID
  - `description` (optional): Task description
  - `preview_type` (optional): Preview type (automatic, noPreview, checklist, description, reference)
  - `checklist` (optional): Complete checklist object
  - `references` (optional): References object
- **Outputs:**
  - `task_details`: Updated task details
  - `result`: Boolean indicating success

### Checklist Operations

#### `add_checklist_item`
- **Description:** Add a new item to a task's checklist
- **Inputs:**
  - `task_id`: Task ID
  - `title`: Checklist item title
  - `is_checked` (optional): Checked status (default: false)
  - `order_hint` (optional): Order hint (default: ' !')
- **Outputs:**
  - `task_details`: Updated task details
  - `item_id`: ID of the newly created item
  - `result`: Boolean indicating success

#### `update_checklist_item`
- **Description:** Update an existing checklist item
- **Inputs:**
  - `task_id`: Task ID
  - `item_id`: Checklist item ID
  - `title` (optional): New title
  - `is_checked` (optional): New checked status
  - `order_hint` (optional): New order hint
- **Outputs:**
  - `task_details`: Updated task details
  - `result`: Boolean indicating success

#### `remove_checklist_item`
- **Description:** Remove an item from a task's checklist
- **Inputs:**
  - `task_id`: Task ID
  - `item_id`: Checklist item ID to remove
- **Outputs:**
  - `task_details`: Updated task details
  - `result`: Boolean indicating success

### Task Board Formats

#### `get_task_assigned_to_board_format`
- **Description:** Get the assigned-to task board format (ordering by assignee)
- **Inputs:**
  - `task_id`: Task ID
- **Outputs:**
  - `board_format`: Board format object
  - `result`: Boolean indicating success

#### `update_task_assigned_to_board_format`
- **Description:** Update the assigned-to task board format
- **Inputs:**
  - `task_id`: Task ID
  - `unassigned_order_hint` (optional): Order hint for unassigned tasks
  - `order_hints_by_assignee` (optional): Object mapping user IDs to order hints
- **Outputs:**
  - `board_format`: Updated board format
  - `result`: Boolean indicating success

#### `get_task_bucket_board_format`
- **Description:** Get the bucket task board format (ordering within buckets)
- **Inputs:**
  - `task_id`: Task ID
- **Outputs:**
  - `board_format`: Board format object
  - `result`: Boolean indicating success

#### `update_task_bucket_board_format`
- **Description:** Update the bucket task board format
- **Inputs:**
  - `task_id`: Task ID
  - `order_hint` (optional): Order hint for bucket view
- **Outputs:**
  - `board_format`: Updated board format
  - `result`: Boolean indicating success

#### `get_task_progress_board_format`
- **Description:** Get the progress task board format (ordering by progress state)
- **Inputs:**
  - `task_id`: Task ID
- **Outputs:**
  - `board_format`: Board format object
  - `result`: Boolean indicating success

#### `update_task_progress_board_format`
- **Description:** Update the progress task board format
- **Inputs:**
  - `task_id`: Task ID
  - `order_hint` (optional): Order hint for progress view
- **Outputs:**
  - `board_format`: Updated board format
  - `result`: Boolean indicating success

## Requirements

No additional Python dependencies beyond the Autohive SDK are required. The integration uses the standard `autohive_integrations_sdk` and Python's built-in libraries.

## Usage Examples

**Example 1: Assign a task to yourself**

```python
# Step 1: Get your user ID
current_user_result = await get_current_user()
user_id = current_user_result['user_id']

# Step 2: Update the task with your user ID
await update_task({
  "task_id": "task-guid-here",
  "assignments": {
    user_id: {}
  }
})
```

**Example 2: Create a task with a checklist**

```python
# Step 1: Create the task
task_result = await create_task({
  "plan_id": "plan-guid",
  "bucket_id": "bucket-guid",
  "title": "New Feature Implementation",
  "due_date_time": "2025-12-31T17:00:00Z",
  "priority": 3
})
task_id = task_result['task']['id']

# Step 2: Add checklist items
await add_checklist_item({
  "task_id": task_id,
  "title": "Write unit tests",
  "is_checked": false
})

await add_checklist_item({
  "task_id": task_id,
  "title": "Code review",
  "is_checked": false
})
```

**Example 3: Assign a task to another user by email**

```python
# Step 1: Find the user by email
user_result = await get_user_by_email({
  "email": "colleague@company.com"
})
colleague_id = user_result['user_id']

# Step 2: Assign the task
await update_task({
  "task_id": "task-guid-here",
  "assignments": {
    colleague_id: {}
  }
})
```

## Important Notes

### User ID Requirements
Microsoft Planner requires actual user IDs (GUIDs) for task assignments, not email addresses or the string "me". Always use `get_current_user`, `get_user_by_email`, or `search_users` actions first to retrieve the proper user IDs before assigning tasks.

### ETag Management
The integration automatically handles ETag retrieval for all update and delete operations. ETags are required by Microsoft's API for optimistic concurrency control.

### Checklist Operations
The checklist helper actions (`add_checklist_item`, `update_checklist_item`, `remove_checklist_item`) automatically clean existing checklist items by removing read-only fields (`lastModifiedBy`, `lastModifiedDateTime`) and preserving only writable fields to prevent API validation errors.

### Order Hints
Order hints control the positioning of items in lists. The integration handles the complexity of Microsoft's order hint format:
- For new items, use the default `" !"` or provide a custom hint
- For existing items, the integration preserves ordering without resubmitting potentially invalid hints
- Only include order hints when explicitly reordering items

## Testing

To test the integration:

1. Ensure you have a Microsoft 365 account with access to Planner
2. Configure the integration in your Autohive workspace
3. Test basic operations:
   - List your groups and plans
   - Create a test plan and bucket
   - Create tasks with various properties
   - Add checklist items to tasks
   - Assign tasks to users
   - Update and delete test data

Refer to the test plan in the pull request for comprehensive testing scenarios.

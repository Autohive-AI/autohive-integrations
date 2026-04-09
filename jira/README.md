# Jira

Integration for Jira Cloud using the REST API v3 and Agile API v1. Covers the full breadth of the Jira API: issues, comments, projects, users, boards, sprints, worklogs, issue links, watchers, and field/metadata lookup.

## Authentication

Authentication is handled via **OAuth 2.0** through the platform. Connect your Atlassian account using the platform's OAuth flow — no manual credentials required.

The integration automatically discovers your Jira Cloud ID from the OAuth token. If your account has access to multiple Jira sites, set the `JIRA_CLOUD_ID` environment variable to pin to a specific site.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JIRA_CLOUD_ID` | Pin to a specific Atlassian Cloud ID (useful when the OAuth account has access to multiple Jira sites) | Auto-discovered |

## Actions

### Create Issue (`create_issue`)

Create a new Jira issue with all standard fields.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `projectKey` | string | Yes | Project key (e.g. `PROJ`) |
| `summary` | string | Yes | Issue title |
| `issueType` | string | No | Issue type name. Default: `Task` |
| `description` | string | No | Plain text description |
| `assigneeAccountId` | string | No | Assignee's Atlassian account ID |
| `priority` | string | No | Priority name (e.g. `High`, `Medium`) |
| `labels` | array | No | List of label strings |
| `parentKey` | string | No | Parent issue key (for subtasks) |
| `customFields` | object | No | Map of custom field IDs to values |

**Output**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | True on success |
| `issueId` | string\|null | Internal numeric issue ID |
| `issueKey` | string\|null | Issue key (e.g. `PROJ-42`) |
| `issueUrl` | string\|null | REST URL of the issue |
| `message` | string\|null | Success message |
| `error` | string\|null | Error detail on failure |

---

### Get Issue (`get_issue`)

Retrieve full details of an issue by key or ID.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key or ID (e.g. `PROJ-123`) |
| `fields` | string | No | Comma-separated field list |
| `expand` | string | No | Expand options (e.g. `changelog`) |

**Output**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | True on success |
| `issueKey` | string\|null | Issue key |
| `summary` | string\|null | Issue summary |
| `status` | string\|null | Current status name |
| `statusCategory` | string\|null | Status category (To Do / In Progress / Done) |
| `priority` | string\|null | Priority name |
| `issueType` | string\|null | Issue type name |
| `projectKey` | string\|null | Project key |
| `assigneeDisplayName` | string\|null | Assignee's display name |
| `assigneeAccountId` | string\|null | Assignee's account ID |
| `reporterDisplayName` | string\|null | Reporter's display name |
| `created` | string\|null | Creation timestamp |
| `updated` | string\|null | Last update timestamp |
| `dueDate` | string\|null | Due date |
| `labels` | array | Labels |
| `components` | array | Component names |
| `fixVersions` | array | Fix version names |
| `subtasks` | array | Subtask objects |
| `parent` | object\|null | Parent issue (if subtask) |
| `rawFields` | object\|null | Full unprocessed fields object |

---

### Update Issue (`update_issue`)

Update one or more fields on an existing issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `summary` | string | No | New summary |
| `description` | string | No | New plain text description |
| `assigneeAccountId` | string\|null | No | New assignee. Null to unassign |
| `priority` | string | No | New priority name |
| `labels` | array | No | Replacement label list |
| `dueDate` | string | No | Due date (YYYY-MM-DD) |
| `fixVersions` | array | No | Replacement fix version names |
| `components` | array | No | Replacement component names |
| `notifyUsers` | boolean | No | Notify watchers. Default: true |
| `customFields` | object | No | Custom fields map |

---

### Delete Issue (`delete_issue`)

Permanently delete an issue. **Cannot be undone.**

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key to delete |
| `deleteSubtasks` | boolean | No | Also delete subtasks. Default: false |

---

### Search Issues (`search_issues`)

Search using JQL with pagination.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `jql` | string | Yes | JQL query (e.g. `project = PROJ AND status = "In Progress"`) |
| `maxResults` | integer | No | Max results (1-100). Default: 50 |
| `nextPageToken` | string | No | Token from a previous response to fetch the next page |
| `fields` | array | No | Fields to include. Custom field IDs (e.g. `customfield_10014`) are returned in `rawFields` |
| `expand` | array | No | Expand options (e.g. `changelog`) |

**Output**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | True on success |
| `issues` | array | List of issues with key fields. Each issue includes `rawFields` for custom/extra fields |
| `total` | integer\|null | Total matching issues |
| `nextPageToken` | string\|null | Pass to next request to paginate |

---

### Get Issue Transitions (`get_issue_transitions`)

List available workflow transitions for an issue. Use before `transition_issue`.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |

**Output**

| Field | Type | Description |
|-------|------|-------------|
| `transitions` | array | List with `id`, `name`, `toStatusName` |

---

### Transition Issue (`transition_issue`)

Move an issue to a new status.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `transitionId` | string | Yes | Transition ID from `get_issue_transitions` |
| `comment` | string | No | Comment to add with the transition |
| `resolution` | string | No | Resolution name (e.g. `Fixed`, `Won't Do`) |

---

### Assign Issue (`assign_issue`)

Assign or unassign an issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `accountId` | string\|null | No | Account ID. Null to unassign. `-1` for project default |

---

### Add Comment (`add_comment`)

Add a comment to an issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `body` | string | Yes | Comment text |
| `visibilityType` | string | No | `role` or `group` |
| `visibilityValue` | string | No | Role or group name |

---

### Get Comments (`get_comments`)

List comments on an issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `startAt` | integer | No | Offset. Default: 0 |
| `maxResults` | integer | No | Max results. Default: 50 |

---

### Update Comment (`update_comment`)

Update an existing comment.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `commentId` | string | Yes | Comment ID from `get_comments` |
| `body` | string | Yes | New comment text |

---

### Delete Comment (`delete_comment`)

Delete a comment permanently.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `commentId` | string | Yes | Comment ID |

---

### List Projects (`list_projects`)

List all accessible projects. Supports filtering by type and name.

---

### Get Project (`get_project`)

Get full project details including issue types, components, and versions.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `projectKey` | string | Yes | Project key or ID |
| `expand` | string | No | Expand options |

---

### Get Project Components (`get_project_components`)

List all components for a project.

---

### Get Project Versions (`get_project_versions`)

List all versions (releases) for a project.

---

### Create Project Version (`create_project_version`)

Create a new version/release for a project.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `projectKey` | string | Yes | Project key |
| `name` | string | Yes | Version name |
| `description` | string | No | Version description |
| `releaseDate` | string | No | Release date (YYYY-MM-DD) |
| `startDate` | string | No | Start date (YYYY-MM-DD) |
| `released` | boolean | No | Mark as already released |

---

### Get Current User (`get_current_user`)

Get the profile of the authenticated user.

---

### Get User (`get_user`)

Get a user's profile by account ID.

---

### Search Users (`search_users`)

Search users by name or email. Returns account IDs for use with assignee and watcher actions.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Name or email fragment |
| `maxResults` | integer | No | Max results. Default: 50 |

---

### List Boards (`list_boards`)

List all boards. Filter by type (`scrum`/`kanban`) or project.

---

### Get Sprints (`get_sprints`)

List sprints for a board. Filter by state: `active`, `future`, `closed`.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `boardId` | integer | Yes | Board ID from `list_boards` |
| `state` | string | No | `active`, `future`, or `closed` |

---

### Get Sprint Issues (`get_sprint_issues`)

Get issues assigned to a sprint.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sprintId` | integer | Yes | Sprint ID from `get_sprints` |
| `maxResults` | integer | No | Default: 50 |
| `jql` | string | No | Additional JQL filter |

---

### Create Sprint (`create_sprint`)

Create a new sprint on a Scrum board.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `boardId` | integer | Yes | Board ID |
| `name` | string | Yes | Sprint name |
| `startDate` | string | No | ISO 8601 start date |
| `endDate` | string | No | ISO 8601 end date |
| `goal` | string | No | Sprint goal |

---

### Update Sprint (`update_sprint`)

Update a sprint. Set `state` to `active` to start it, or `closed` to complete it.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sprintId` | integer | Yes | Sprint ID |
| `name` | string | No | New name |
| `state` | string | No | `future`, `active`, or `closed` |
| `startDate` | string | No | New start date |
| `endDate` | string | No | New end date |
| `goal` | string | No | New sprint goal |

---

### Get Board Issues (`get_board_issues`)

Get all issues on a board across all sprints.

---

### Get Backlog Issues (`get_backlog_issues`)

Get all issues in the backlog (not assigned to any sprint).

---

### Move Issues to Sprint (`move_issues_to_sprint`)

Move one or more issues into a specific sprint.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sprintId` | integer | Yes | Target sprint ID |
| `issueKeys` | array | Yes | List of issue keys to move |

---

### Add Worklog (`add_worklog`)

Log time spent on an issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `timeSpent` | string | Yes | Duration (e.g. `3h`, `1d 2h`, `30m`) |
| `comment` | string | No | Work description |
| `started` | string | No | When work started (ISO 8601). Defaults to now |
| `adjustEstimate` | string | No | `auto` (default), `new`, `manual`, or `leave` |
| `newEstimate` | string | No | Required when `adjustEstimate` is `new` |
| `reduceBy` | string | No | Required when `adjustEstimate` is `manual` |

---

### Get Worklogs (`get_worklogs`)

Retrieve all work log entries for an issue.

---

### Link Issues (`link_issues`)

Create a directional link between two issues.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `linkType` | string | Yes | Link type name (e.g. `Blocks`, `Relates`). Use `get_issue_link_types` to list all |
| `inwardIssueKey` | string | Yes | Inward issue key |
| `outwardIssueKey` | string | Yes | Outward issue key |
| `comment` | string | No | Optional comment |

---

### Get Issue Link Types (`get_issue_link_types`)

List all available link type names, inward/outward directions.

---

### Add Watcher (`add_watcher`)

Add a user as a watcher on an issue.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issueKey` | string | Yes | Issue key |
| `accountId` | string | Yes | Account ID to add as watcher |

---

### Get Watchers (`get_watchers`)

List all watchers on an issue.

---

### Get Issue Types (`get_issue_types`)

List all issue types. When `projectKey` is provided, returns types with their available statuses.

---

### Get Priorities (`get_priorities`)

List all priority values (e.g. Highest, High, Medium, Low, Lowest).

---

### Get Fields (`get_fields`)

List all available fields. Pass `customOnly: true` to see only custom fields and their IDs.

---

### Get Issue Changelog (`get_issue_changelog`)

Get full change history for an issue — every field change with who made it and when.

---

### Bulk Create Issues (`bulk_create_issues`)

Create up to 50 issues in a single request.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issues` | array | Yes | List of issue definitions (max 50) |

Each item in `issues`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `projectKey` | string | Yes | Project key |
| `summary` | string | Yes | Issue summary |
| `issueType` | string | No | Issue type. Default: `Task` |
| `description` | string | No | Description |
| `assigneeAccountId` | string | No | Assignee account ID |
| `priority` | string | No | Priority name |
| `labels` | array | No | Labels |

---

### Get Project Roles (`get_project_roles`)

List all role names for a project (e.g. Developer, Administrator).

---

### Get Status Categories (`get_status_categories`)

List all status categories: To Do, In Progress, Done.

---

### List Dashboards (`list_dashboards`)

List all dashboards accessible to the authenticated user.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filter` | string | No | Filter: `my` (owned) or `favourite` |
| `startAt` | integer | No | Pagination offset. Default: 0 |
| `maxResults` | integer | No | Max results (1-100). Default: 50 |

---

### Get Dashboard (`get_dashboard`)

Get full details of a specific dashboard by ID.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboardId` | string | Yes | Dashboard ID |

---

### Search Dashboards (`search_dashboards`)

Search for dashboards by name, owner, or group.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboardName` | string | No | Name filter |
| `accountId` | string | No | Filter by owner account ID |
| `owner` | string | No | Filter by owner display name |
| `groupId` | string | No | Filter by group |
| `orderBy` | string | No | Sort order |
| `startAt` | integer | No | Pagination offset. Default: 0 |
| `maxResults` | integer | No | Max results (1-100). Default: 50 |

---

### Get Dashboard Gadgets (`get_dashboard_gadgets`)

List all gadgets on a specific dashboard.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboardId` | string | Yes | Dashboard ID |

---

## Common Workflows

### Create and Transition an Issue

1. Call `create_issue` with `projectKey`, `summary`, `issueType`
2. Store the returned `issueKey`
3. Call `get_issue_transitions` with that `issueKey` to see available transitions
4. Call `transition_issue` with the chosen `transitionId`

### Find and Assign a User

1. Call `search_users` with the user's name or email
2. Copy the `accountId` from the results
3. Call `assign_issue` with `issueKey` and `accountId`

### Sprint Planning Workflow

1. Call `list_boards` to find the Scrum board ID
2. Call `create_sprint` with `boardId` and `name`
3. Call `search_issues` with JQL to find backlog items
4. Call `move_issues_to_sprint` with `sprintId` and the `issueKeys`
5. Call `update_sprint` with `state: "active"` to start the sprint

### Log Work on an Issue

1. Call `add_worklog` with `issueKey`, `timeSpent` (e.g. `2h 30m`), and optional `comment`
2. Call `get_worklogs` to verify the entry was recorded

### Find Custom Field IDs

1. Call `get_fields` with `customOnly: true`
2. Note the `fieldId` values (e.g. `customfield_10014`)
3. Use these as keys in `customFields` when calling `create_issue` or `update_issue`

## Testing

1. Open `tests/test_jira.py`
2. Set `EMAIL`, `API_TOKEN`, `DOMAIN`, `TEST_PROJECT_KEY`, and `TEST_ISSUE_KEY` at the top
3. Run: `python tests/test_jira.py`
4. Expected output: each test prints its result dict. All should show `result: True`


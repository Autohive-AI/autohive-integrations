# Toggl Track Integration for Autohive

Creates time entries in Toggl Track using the official API.

## Setup & Authentication

- Auth type: API token via HTTP Basic Auth.
- Field required in connection:
  - `api_token` (password): Find it at https://track.toggl.com/profile

The request uses Basic auth with username = your API token and password = `api_token`.

## Action: create_time_entry

Creates a time entry in a workspace.

Inputs:
- `workspace_id` (integer, required)
- `start` (string, required) — UTC time, e.g. `2006-01-02T15:04:05Z`
- `stop` (string, optional)
- `duration` (integer, optional) — in seconds; for running entries use `-1`
- `description` (string, optional)
- `project_id` (integer, optional)
- `task_id` (integer, optional)
- `billable` (boolean, optional)
- `tags` (array[string], optional)
- `tag_ids` (array[integer], optional)
- `user_id` (integer, optional)

Notes:
- The integration automatically sets `created_with` to `autohive-integrations` as required by Toggl.
- Provide either `stop` or `duration` unless you're creating a running entry with `duration = -1`.

## Requirements

- `autohive_integrations_sdk`

## Example

```json
{
  "workspace_id": 1234567,
  "start": "2025-08-14T10:00:00Z",
  "stop": "2025-08-14T11:00:00Z",
  "description": "Planning meeting",
  "project_id": 7654321,
  "billable": true,
  "tags": ["meeting", "planning"]
}
```


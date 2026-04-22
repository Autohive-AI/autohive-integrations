# Toggl Track Integration for Autohive

Creates time entries in Toggl Track using the official v9 API. Ideal for automating time tracking workflows, logging billable hours, and syncing work sessions into Toggl from external systems.

## Key Features

- Create time entries in any Toggl workspace
- Supports start/stop times, duration, project and task assignment
- Billable flag and tag support (by name or ID)
- API token authentication via HTTP Basic Auth

## Setup & Authentication

**Auth type:** Custom (API token)

**Required field:**
- `api_token` — Your Toggl API token. Find it at https://track.toggl.com/profile under "Profile settings" → "API Token".

The integration uses HTTP Basic Auth with `api_token` as both the username and the literal string `api_token` as the password, as required by Toggl's API.

## Actions

#### create_time_entry

Creates a new time entry in the specified Toggl workspace.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workspace_id` | integer | ✅ | Numeric Toggl workspace ID |
| `start` | string | ✅ | Start time in UTC, format `2006-01-02T15:04:05Z` |
| `stop` | string | optional | Stop time in UTC; omit if the entry is still running or using `duration` |
| `duration` | integer | optional | Duration in seconds. Use `-1` for a running (in-progress) entry |
| `description` | string | optional | Human-readable label for the time entry |
| `project_id` | integer | optional | ID of the project to assign the entry to |
| `task_id` | integer | optional | ID of the task within the project |
| `billable` | boolean | optional | Whether the entry is billable (default: `false`) |
| `tags` | array[string] | optional | Tag names to apply to the entry |
| `tag_ids` | array[integer] | optional | Tag IDs to apply to the entry |
| `user_id` | integer | optional | ID of the user creating the entry; defaults to the authenticated user |

**Notes:**
- Provide either `stop` or `duration` (not both) unless creating a running entry with `duration = -1`.
- The integration automatically sets `created_with: autohive-integrations` as required by Toggl.

**Outputs:**

The response mirrors the Toggl API time entry object, including fields such as `id`, `workspace_id`, `project_id`, `start`, `stop`, `duration`, `description`, `billable`, `tags`, and `at` (last updated timestamp).

## Requirements

- `autohive-integrations-sdk~=1.1.1`

## API Info

- **Base URL:** `https://api.track.toggl.com/api/v9`
- **Official docs:** https://developers.track.toggl.com/docs/
- **API version:** v9

## Rate Limiting

Toggl's API enforces per-user rate limits. Standard limits allow up to 1 request per second. Exceeding this returns HTTP 429. No automatic retry is built into this integration.

## Error Handling

| Error | Cause |
|-------|-------|
| `Missing API token` | `api_token` field not present in auth credentials |
| HTTP 403 | Invalid or expired API token |
| HTTP 400 | Missing required fields or malformed body (e.g. `workspace_id` mismatch) |
| HTTP 429 | Rate limit exceeded |

## Troubleshooting

- **403 Forbidden:** Double-check your API token at https://track.toggl.com/profile. Tokens can be regenerated there.
- **400 Bad Request:** Ensure `workspace_id` matches the workspace the project/task belong to. Toggl rejects mismatches.
- **Entry not appearing:** Confirm `start` is in UTC ISO 8601 format (`2006-01-02T15:04:05Z`). Local timezone offsets cause silent failures.
- **Running entry not stopping:** For running entries use `duration: -1` and omit `stop`. To stop it later, use the Toggl UI or a separate API call.
- **Tags not applying:** Tag names are case-sensitive and must already exist in the workspace. Use `tag_ids` for reliability.

## Version History

| Version | Notes |
|---------|-------|
| v1.0.0 | Initial release — `create_time_entry` action with full Toggl v9 API support |

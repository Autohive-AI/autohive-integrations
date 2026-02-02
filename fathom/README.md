# Fathom Integration for Autohive

Connects Autohive to the Fathom AI API to access meeting recordings, transcripts, teams, and team members.

## Description

This integration provides access to Fathom's conversation intelligence platform, enabling automated retrieval of meeting data, transcripts, and team information. Fathom records, transcribes, and summarizes video meetings, and this integration allows you to programmatically access that data for analysis, reporting, and workflow automation.

**Key Features:**
- List and filter meeting recordings with advanced search capabilities
- Retrieve full meeting transcripts with speaker attribution and timestamps
- Access team and team member information
- Support for pagination across all endpoints
- Filter meetings by date range, participants, domains, and more

## Setup & Authentication

This integration uses OAuth 2.0 authentication through the Autohive platform.

**Authentication Method:** Platform OAuth (Fathom provider)

**Required Scopes:**
- `public_api` - Access to Fathom's public API endpoints

**Setup Steps:**
1. Connect your Fathom account through the Autohive platform
2. Authorize the integration with the `public_api` scope
3. The integration will handle OAuth token management automatically

## Actions

### Action: `list_meetings`

Lists recent meetings recorded by you or shared with your team, with comprehensive filtering options.

**Inputs:**
- `cursor` (string, optional): Cursor for pagination
- `include_transcript` (boolean, optional): Include transcript for each meeting (unavailable for OAuth apps)
- `include_summary` (boolean, optional): Include summary for each meeting (unavailable for OAuth apps)
- `include_action_items` (boolean, optional): Include action items for each meeting
- `include_crm_matches` (boolean, optional): Include CRM matches for each meeting
- `recorded_by` (array of strings, optional): Email addresses of users who recorded meetings
- `calendar_invitees_domains` (array of strings, optional): Filter by company domains appearing in meetings
- `calendar_invitees_domains_type` (string, optional): Filter by attendee type - `all`, `only_internal`, or `one_or_more_external`
- `teams` (array of strings, optional): Team names to filter by
- `created_after` (string, optional): Filter to meetings created after this timestamp (ISO 8601 format)
- `created_before` (string, optional): Filter to meetings created before this timestamp (ISO 8601 format)
- `meeting_type` (string, optional): Filter by meeting type - `all`, `internal`, or `external`

**Outputs:**
- `limit` (integer): Number of items per page
- `next_cursor` (string|null): Cursor for retrieving the next page of results
- `items` (array): Array of meeting objects containing:
  - `recording_id` (integer): The recording ID
  - `title` (string): The meeting title
  - `meeting_title` (string|null): The scheduled meeting title
  - `url` (string): The Fathom video URL
  - `share_url` (string): The shareable meeting URL
  - `created_at` (string): Recording creation time in ISO format
  - `scheduled_start_time` (string): Scheduled meeting start time
  - `scheduled_end_time` (string): Scheduled meeting end time
  - `recording_start_time` (string): Actual recording start time
  - `recording_end_time` (string): Actual recording end time
  - `calendar_invitees_domains_type` (string): Type of attendees
  - `transcript_language` (string): Language of the transcript
  - `calendar_invitees` (array): List of calendar invitees with name, email, domain, and speaker matching
  - `recorded_by` (object): Information about who recorded the meeting

### Action: `get_transcript`

Retrieves the full transcript for a specific recording with speaker attribution and timestamps.

**Inputs:**
- `recording_id` (integer, required): The ID of the recording to get transcript for

**Outputs:**
- `recording_id` (integer): The recording ID
- `transcript` (array): Array of transcript segments containing:
  - `speaker_name` (string): Name of the speaker
  - `timestamp` (string): Timestamp in format HH:MM:SS
  - `text` (string): The spoken text

### Action: `list_teams`

Lists all teams the authenticated user has access to.

**Inputs:**
- `cursor` (string, optional): Cursor for pagination

**Outputs:**
- `limit` (integer|null): Number of items per page
- `next_cursor` (string|null): Cursor for retrieving the next page of results
- `teams` (array): Array of team objects containing:
  - `name` (string): The team name
  - `created_at` (string): Team creation timestamp in ISO format

### Action: `list_team_members`

Lists all team members the authenticated user has access to, with optional filtering by team.

**Inputs:**
- `cursor` (string, optional): Cursor for pagination
- `team` (string, optional): Team name to filter by

**Outputs:**
- `limit` (integer|null): Number of items per page
- `next_cursor` (string|null): Cursor for retrieving the next page of results
- `team_members` (array): Array of team member objects containing:
  - `name` (string): The member name
  - `email` (string): The member email
  - `created_at` (string): Member creation timestamp in ISO format

## Requirements

The integration requires the following Python dependencies:

- `autohive-integrations-sdk>=1.0.2`

All dependencies are automatically included when packaging the integration using the `hiveup` CLI tool.

## Usage Examples

**Example 1: List recent meetings from the last week**

```json
{
  "created_after": "2024-12-10T00:00:00Z",
  "meeting_type": "external"
}
```

**Example 2: Get transcript for a specific meeting**

```json
{
  "recording_id": 107505581
}
```

**Example 3: Filter meetings by specific team and participant**

```json
{
  "teams": ["Sales"],
  "recorded_by": ["john.doe@company.com"]
}
```

**Example 4: List team members for a specific team**

```json
{
  "team": "Engineering"
}
```

## Testing

To run the integration tests:

1. Navigate to the integration's directory:
   ```bash
   cd fathom
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the tests:
   ```bash
   python tests/test_fathom.py
   ```

The test suite includes tests for all four actions: `list_meetings`, `get_transcript`, `list_teams`, and `list_team_members`.

## Notes

- **OAuth Limitations**: The `include_summary` and `include_transcript` parameters in `list_meetings` are unavailable for OAuth-connected apps. Use the dedicated `get_transcript` endpoint instead.
- **Pagination**: All list endpoints support pagination using the `cursor` parameter and return a `next_cursor` for retrieving additional pages.
- **Date Filtering**: Timestamps should be provided in ISO 8601 format (e.g., `2024-12-10T00:00:00Z`).
- **Array Parameters**: Array parameters like `recorded_by`, `calendar_invitees_domains`, and `teams` are automatically formatted correctly for the Fathom API.

## Support

For issues or questions about the Fathom API, refer to the [Fathom API Documentation](https://api.fathom.ai/external/v1/docs).

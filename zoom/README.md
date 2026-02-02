# Zoom Integration for Autohive

Connects Autohive to the Zoom API to enable meeting management, access to cloud recordings and transcripts, and user management capabilities for AI-powered automation workflows.

## Description

This integration provides comprehensive access to Zoom's meeting and recording functionality, allowing Autohive agents to:

- **Meeting Management**: Create, update, delete, and list Zoom meetings with full control over settings
- **Cloud Recordings**: Access and manage cloud recordings including video, audio, and transcript files
- **Meeting Transcripts**: Retrieve and parse meeting transcripts for post-meeting analysis
- **User Management**: List and view user details within the Zoom account
- **Meeting Participants**: Track attendance and participant data from completed meetings
- **Meeting Registration**: Programmatically register participants for meetings

This integration is ideal for automating meeting workflows, building meeting assistants, and extracting insights from recorded meetings.

## Setup & Authentication

### Authentication Method

This integration uses **OAuth 2.0** platform authentication managed by Autohive. The OAuth flow handles token acquisition and refresh automatically.

### Required Scopes

The following OAuth scopes are required for full functionality:

- `meeting:read:meeting:admin` - Read meeting details
- `meeting:read:list_meetings:admin` - List meetings
- `meeting:write:meeting:admin` - Create meetings
- `meeting:update:meeting:admin` - Update meetings
- `meeting:delete:meeting:admin` - Delete meetings
- `user:read:user:admin` - Read user details
- `user:read:list_users:admin` - List users
- `cloud_recording:read:list_recording_files:admin` - List recording files
- `cloud_recording:read:list_user_recordings:admin` - List user recordings
- `cloud_recording:read:recording_file:admin` - Access recording files

### Prerequisites

1. A Zoom account (Pro, Business, or Enterprise plan recommended for cloud recording features)
2. Cloud recording and audio transcription enabled in Zoom settings (for transcript features)

### Setup Steps in Autohive

1. Navigate to Integrations in your Autohive dashboard
2. Find and select the Zoom integration
3. Click "Connect" to initiate the OAuth flow
4. Log in to your Zoom account and authorize the requested permissions
5. Once connected, you can use Zoom actions in your workflows

## Actions

### `list_meetings`

- **Display Name**: List Meetings
- **Description**: List all scheduled meetings for a user with optional filtering
- **Inputs**:
  - `user_id` (string, optional): User ID or email. Default: "me"
  - `type` (string, optional): Meeting type filter. Options: "scheduled", "live", "upcoming", "upcoming_meetings", "previous_meetings". Default: "scheduled"
  - `page_size` (integer, optional): Results per page (max 300). Default: 30
  - `next_page_token` (string, optional): Pagination token
- **Outputs**:
  - `meetings` (array): List of meeting objects with id, uuid, topic, type, start_time, duration, timezone, join_url, created_at
  - `next_page_token` (string): Token for next page
  - `total_records` (integer): Total number of meetings
  - `result` (boolean): Operation success status

---

### `get_meeting`

- **Display Name**: Get Meeting Details
- **Description**: Retrieve detailed information about a specific meeting
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID or UUID
- **Outputs**:
  - `id` (integer): Meeting ID
  - `uuid` (string): Meeting UUID
  - `topic` (string): Meeting topic
  - `status` (string): Meeting status
  - `start_time` (string): Start time in ISO format
  - `duration` (integer): Duration in minutes
  - `start_url` (string): URL for host to start meeting
  - `join_url` (string): URL for participants to join
  - `password` (string): Meeting password
  - `host_id` (string): Host user ID
  - `host_email` (string): Host email
  - `settings` (object): Meeting settings
  - `result` (boolean): Operation success status

---

### `create_meeting`

- **Display Name**: Create Meeting
- **Description**: Create a new Zoom meeting with customizable settings
- **Inputs**:
  - `user_id` (string, optional): Host user ID. Default: "me"
  - `topic` (string, required): Meeting topic/title
  - `type` (integer, optional): Meeting type (1=instant, 2=scheduled, 3=recurring no fixed time, 8=recurring fixed time). Default: 2
  - `start_time` (string, optional): Start time in ISO 8601 format
  - `duration` (integer, optional): Duration in minutes. Default: 60
  - `timezone` (string, optional): Timezone (e.g., "America/New_York")
  - `password` (string, optional): Meeting password (max 10 chars)
  - `agenda` (string, optional): Meeting agenda/description
  - `waiting_room` (boolean, optional): Enable waiting room. Default: true
  - `join_before_host` (boolean, optional): Allow join before host. Default: false
  - `mute_upon_entry` (boolean, optional): Mute on entry. Default: false
  - `auto_recording` (string, optional): Auto-recording option ("local", "cloud", "none"). Default: "none"
- **Outputs**:
  - `id` (integer): Created meeting ID
  - `uuid` (string): Meeting UUID
  - `topic` (string): Meeting topic
  - `start_time` (string): Start time
  - `duration` (integer): Duration
  - `start_url` (string): Host start URL
  - `join_url` (string): Participant join URL
  - `password` (string): Meeting password
  - `result` (boolean): Operation success status

---

### `update_meeting`

- **Display Name**: Update Meeting
- **Description**: Update an existing meeting's details
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID to update
  - `topic` (string, optional): New topic
  - `start_time` (string, optional): New start time
  - `duration` (integer, optional): New duration
  - `timezone` (string, optional): New timezone
  - `password` (string, optional): New password
  - `agenda` (string, optional): New agenda
  - `waiting_room` (boolean, optional): Enable/disable waiting room
  - `join_before_host` (boolean, optional): Allow/disallow join before host
  - `mute_upon_entry` (boolean, optional): Enable/disable mute on entry
  - `auto_recording` (string, optional): Auto-recording option
- **Outputs**:
  - `meeting_id` (string): Updated meeting ID
  - `result` (boolean): Operation success status

---

### `delete_meeting`

- **Display Name**: Delete Meeting
- **Description**: Delete a scheduled meeting
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID to delete
  - `occurrence_id` (string, optional): For recurring meetings, delete specific occurrence
  - `schedule_for_reminder` (boolean, optional): Send cancellation email. Default: true
- **Outputs**:
  - `meeting_id` (string): Deleted meeting ID
  - `result` (boolean): Operation success status

---

### `list_recordings`

- **Display Name**: List Cloud Recordings
- **Description**: List all cloud recordings for a user within a date range
- **Inputs**:
  - `user_id` (string, optional): User ID. Default: "me"
  - `from_date` (string, optional): Start date (YYYY-MM-DD). Default: 30 days ago
  - `to_date` (string, optional): End date (YYYY-MM-DD). Default: today
  - `page_size` (integer, optional): Results per page (max 300). Default: 30
  - `next_page_token` (string, optional): Pagination token
- **Outputs**:
  - `meetings` (array): Meetings with recordings, each containing:
    - `uuid`, `id`, `topic`, `start_time`, `duration`, `total_size`, `recording_count`
    - `recording_files` (array): Recording files with id, recording_type, file_type, file_size, download_url, play_url, status
  - `next_page_token` (string): Token for next page
  - `total_records` (integer): Total recordings
  - `result` (boolean): Operation success status

---

### `get_meeting_recordings`

- **Display Name**: Get Meeting Recordings
- **Description**: Get all recording files for a specific meeting
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID or UUID
- **Outputs**:
  - `uuid` (string): Meeting UUID
  - `id` (integer): Meeting ID
  - `topic` (string): Meeting topic
  - `start_time` (string): Start time
  - `duration` (integer): Duration
  - `total_size` (integer): Total file size in bytes
  - `recording_files` (array): Recording files with detailed info
  - `password` (string): Recording access password
  - `share_url` (string): Share URL
  - `result` (boolean): Operation success status

---

### `get_meeting_transcript`

- **Display Name**: Get Meeting Transcript
- **Description**: Retrieve the transcript for a recorded meeting
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID or UUID
- **Outputs**:
  - `meeting_id` (string): Meeting ID
  - `topic` (string): Meeting topic
  - `transcript_url` (string): URL to download VTT transcript
  - `transcript_content` (string): Raw transcript content if available
  - `transcript_segments` (array): Parsed segments with:
    - `speaker` (string): Speaker name
    - `start_time` (string): Start timestamp
    - `end_time` (string): End timestamp
    - `text` (string): Spoken text
  - `result` (boolean): Operation success status

---

### `list_users`

- **Display Name**: List Users
- **Description**: List all users in the Zoom account
- **Inputs**:
  - `status` (string, optional): User status filter ("active", "inactive", "pending"). Default: "active"
  - `page_size` (integer, optional): Results per page (max 300). Default: 30
  - `next_page_token` (string, optional): Pagination token
  - `role_id` (string, optional): Filter by role ID
- **Outputs**:
  - `users` (array): User objects with id, first_name, last_name, email, type, status, department, created_at, last_login_time
  - `next_page_token` (string): Token for next page
  - `total_records` (integer): Total users
  - `result` (boolean): Operation success status

---

### `get_user`

- **Display Name**: Get User Details
- **Description**: Get detailed information about a specific user
- **Inputs**:
  - `user_id` (string, optional): User ID or email. Default: "me"
- **Outputs**:
  - `id` (string): User ID
  - `first_name` (string): First name
  - `last_name` (string): Last name
  - `email` (string): Email
  - `type` (integer): User type (1=basic, 2=licensed, 3=on-prem)
  - `role_name` (string): Role name
  - `pmi` (integer): Personal Meeting ID
  - `use_pmi` (boolean): Use PMI for instant meetings
  - `timezone` (string): User timezone
  - `dept` (string): Department
  - `created_at` (string): Account creation time
  - `last_login_time` (string): Last login time
  - `pic_url` (string): Profile picture URL
  - `result` (boolean): Operation success status

---

### `get_meeting_participants`

- **Display Name**: Get Meeting Participants
- **Description**: Get participants who attended a past meeting
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID or UUID
  - `page_size` (integer, optional): Results per page (max 300). Default: 30
  - `next_page_token` (string, optional): Pagination token
- **Outputs**:
  - `participants` (array): Participant objects with id, user_id, name, user_email, join_time, leave_time, duration, attentiveness_score
  - `next_page_token` (string): Token for next page
  - `total_records` (integer): Total participants
  - `result` (boolean): Operation success status

---

### `add_meeting_registrant`

- **Display Name**: Add Meeting Registrant
- **Description**: Register a participant for a meeting that requires registration
- **Inputs**:
  - `meeting_id` (string, required): Meeting ID
  - `email` (string, required): Registrant's email
  - `first_name` (string, required): Registrant's first name
  - `last_name` (string, optional): Registrant's last name
  - `auto_approve` (boolean, optional): Auto-approve registrant. Default: true
- **Outputs**:
  - `registrant_id` (string): Registrant ID
  - `id` (integer): Meeting ID
  - `topic` (string): Meeting topic
  - `start_time` (string): Meeting start time
  - `join_url` (string): Unique join URL for registrant
  - `result` (boolean): Operation success status

## Requirements

- `autohive-integrations-sdk`

## Rate Limits

Zoom API enforces rate limits based on account type:

| Category | Free | Pro | Business+ |
|----------|------|-----|-----------|
| Light APIs | 4/sec, 6,000/day | 30/sec | 80/sec |
| Medium APIs | 2/sec, 2,000/day | 20/sec | 60/sec |
| Heavy APIs | 1/sec, 1,000/day | 10/sec* | 40/sec* |

*Pro and Business+ have combined daily limits of 30,000 and 60,000 requests respectively.

**Special limits:**
- Meeting creation: 100 per user per day
- Registration updates: 3 per registrant per meeting per day

When limits are exceeded, API returns HTTP 429. The integration handles this gracefully and returns an error message.

## Usage Examples

**Example 1: Create a scheduled meeting**

```json
Input:
{
  "topic": "Weekly Team Standup",
  "type": 2,
  "start_time": "2025-01-20T09:00:00Z",
  "duration": 30,
  "timezone": "America/New_York",
  "waiting_room": true,
  "mute_upon_entry": true
}

Output:
{
  "id": 85746352890,
  "uuid": "abc123def456",
  "topic": "Weekly Team Standup",
  "start_time": "2025-01-20T09:00:00Z",
  "duration": 30,
  "start_url": "https://zoom.us/s/85746352890?zak=...",
  "join_url": "https://zoom.us/j/85746352890",
  "password": "abc123",
  "result": true
}
```

**Example 2: Get meeting transcript**

```json
Input:
{
  "meeting_id": "85746352890"
}

Output:
{
  "meeting_id": "85746352890",
  "topic": "Weekly Team Standup",
  "transcript_url": "https://zoom.us/rec/download/...",
  "transcript_segments": [
    {
      "speaker": "John Smith",
      "start_time": "00:00:05.000",
      "end_time": "00:00:12.000",
      "text": "Good morning everyone, let's get started with our standup."
    }
  ],
  "result": true
}
```

**Example 3: List upcoming meetings**

```json
Input:
{
  "user_id": "me",
  "type": "upcoming",
  "page_size": 10
}

Output:
{
  "meetings": [
    {
      "id": 85746352890,
      "topic": "Weekly Team Standup",
      "start_time": "2025-01-20T09:00:00Z",
      "duration": 30,
      "join_url": "https://zoom.us/j/85746352890"
    }
  ],
  "total_records": 1,
  "result": true
}
```

## Meeting Automation Capabilities

This integration enables powerful meeting automation use cases:

1. **Automated Meeting Scheduling**: Create meetings programmatically based on calendar availability or workflow triggers

2. **Meeting Notes & Summaries**: Retrieve transcripts and recordings for AI-powered meeting summarization

3. **Attendance Tracking**: Monitor participant attendance and duration for reporting

4. **Meeting Management**: Update or cancel meetings based on changing schedules

5. **Registration Workflows**: Automatically register participants for webinars or registration-required meetings

## Troubleshooting

### Common Issues

1. **"Invalid access token" error**: Token may have expired. Reconnect the integration in Autohive.

2. **"Recording not found" error**: Ensure the meeting has ended and cloud recording was enabled. Recordings may take time to process.

3. **"Transcript not available"**: Audio transcription must be enabled in Zoom account settings before the meeting.

4. **Rate limit errors (HTTP 429)**: Reduce request frequency or upgrade Zoom account tier.

5. **"Insufficient permissions"**: Ensure all required scopes were authorized during OAuth setup.

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd zoom`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Update test credentials in `tests/test_zoom.py`
4. Run the tests: `python tests/test_zoom.py`

## Additional Resources

- [Zoom API Documentation](https://developers.zoom.us/docs/api/)
- [Zoom OAuth Documentation](https://developers.zoom.us/docs/integrations/oauth/)
- [Zoom Rate Limits](https://developers.zoom.us/docs/api/rate-limits/)
- [Zoom Developer Forum](https://devforum.zoom.us/)

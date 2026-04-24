# Salesforce

Salesforce is the world's leading CRM platform, used to manage sales pipelines, customer relationships, tasks, events, and more. This integration provides 7 focused actions for searching and updating records, and for retrieving summaries of task and event activity.

## Auth Setup

This integration uses **OAuth 2.0** via a Salesforce Connected App.

1. Log in to Salesforce and go to **Setup → App Manager → New Connected App**.
2. Enable **OAuth Settings** and set a callback URL.
3. Add the **`api`** scope under Selected OAuth Scopes.
4. Save and copy the **Consumer Key** (Client ID) and **Consumer Secret**.
5. Use those credentials to connect via the Autohive platform OAuth flow.

## Actions

| Action | Description | Key Inputs | Key Outputs |
|--------|-------------|------------|-------------|
| `search_records` | Run a SOQL query against any object | `soql` | `records`, `total_size` |
| `get_record` | Fetch a single record by ID | `object_type`, `record_id` | `record` |
| `update_record` | Update fields on a record | `object_type`, `record_id`, `fields` | `result`, `record_id` |
| `list_tasks` | List Task records with optional filters | `status`, `due_date_from`, `due_date_to`, `limit` | `tasks`, `total_size` |
| `list_events` | List Event records with optional date filters | `start_date_from`, `start_date_to`, `limit` | `events`, `total_size` |
| `get_task_summary` | Get a readable summary of a Task | `task_id` | `summary`, `task` |
| `get_event_summary` | Get a readable summary of an Event | `event_id` | `summary`, `event` |

## API Info

- **Base URL:** `https://{instance_url}/services/data/v62.0/`
- **Docs:** https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
- **Rate limits:** Typically 15,000 API calls per 24 hours (varies by Salesforce edition)
- **Query endpoint:** `GET /query?q={SOQL}`
- **Record endpoint:** `GET /sobjects/{ObjectType}/{Id}`

## Running Tests

```bash
cd salesforce/tests
export SALESFORCE_TOKEN=your_access_token
export SALESFORCE_INSTANCE_URL=https://yourinstance.salesforce.com
# Optional: set record IDs to test get/update actions
export SALESFORCE_RECORD_ID=003XXXXXXXXXXXXXXX
export SALESFORCE_TASK_ID=00TXXXXXXXXXXXXXXX
export SALESFORCE_EVENT_ID=00UXXXXXXXXXXXXXXX
python test_salesforce.py
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Expired or invalid access token | Re-authenticate via Autohive OAuth flow |
| `400 MALFORMED_QUERY` | Invalid SOQL syntax | Check field names, quote strings with single quotes |
| `404 NOT_FOUND` | Record ID doesn't exist or wrong object type | Verify ID and object type match |
| `REQUEST_LIMIT_EXCEEDED` | Daily API call limit hit | Wait until the 24-hour window resets |

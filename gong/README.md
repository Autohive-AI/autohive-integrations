# Gong Integration

A comprehensive integration for accessing Gong call recordings, transcripts, and CRM data through the Gong API.

## Features

### Actions
- **List Calls** - Retrieve calls with filtering by date, users, and other criteria
- **Get Call Transcript** - Fetch detailed transcripts with speaker segments
- **Get Call Details** - Access comprehensive call information including CRM data
- **Search Calls** - Search through calls using keywords and topics
- **List Users** - Retrieve workspace users with roles and status

## Setup

### 1. Authentication
The integration uses platform-managed Gong OAuth authentication:

1. **Configure Integration**:
   - Set authentication provider to "gong"
   - Complete the OAuth flow through the platform's auth system
   - Supply the customer-specific API base URL from the OAuth token response as `context.metadata["api_base_url"]`

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Required Scopes
The integration requires these API scopes:
- `api:calls:read:basic` - Access basic call data
- `api:calls:read:extensive` - Access extensive call data
- `api:calls:read:transcript` - Access call transcripts
- `api:users:read` - Access user information

## Usage Examples

Run these fragments inside an async function. `integration` must be the registered `gong` instance from `gong.py`; import `ResultType` from `autohive_integrations_sdk`. Your caller must supply an open `ExecutionContext` named `context`, managed with `async with`, using `{"auth_type": "PlatformOauth2", "credentials": {"access_token": supplied_token}}` and `metadata={"api_base_url": supplied_api_base_url}`. Use the `api_base_url_for_customer` value from Gong's OAuth response when present. Supply credentials securely rather than embedding them in source.

`execute_action` returns an `IntegrationResult`. Check `ResultType.ACTION` before reading `result.result.data`; handle other result types as failures. See the [SDK calling patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md). These examples don't change the SDK pin in [requirements.txt](requirements.txt).

### List Recent Calls
```python
# Get calls in a specified date range
result = await integration.execute_action("list_calls", {
    "from_date": "2025-01-01",
    "to_date": "2025-01-31",
    "limit": 50
}, context)

assert result.type == ResultType.ACTION, result.result
for call in result.result.data["calls"]:
    print(f"Call: {call['title']} - {call['started']}")
```

### Get Call Transcript
```python
# Get detailed transcript for a specific call
result = await integration.execute_action("get_call_transcript", {
    "call_id": "call_123456"
}, context)

assert result.type == ResultType.ACTION, result.result
for segment in result.result.data["transcript"]:
    print(f"{segment['speaker_name']}: {segment['text']}")
```

### Search Calls
```python
# Search for calls containing specific keywords
result = await integration.execute_action("search_calls", {
    "query": "product demo pricing",
    "from_date": "2025-01-01",
    "limit": 25
}, context)

assert result.type == ResultType.ACTION, result.result
for call in result.result.data["results"]:
    print(f"Match: {call['title']} (Score: {call['relevance_score']})")
```

### Monitor New Calls

Schedule a workflow to call `list_calls` with the desired date range and user IDs. This integration doesn't register a polling trigger in `config.json` or `gong.py`; there is no `setup_polling_trigger` SDK method to call.

## Testing

### Offline unit tests

Install HiveUp 2.5.4 from a Tooling local build as described in the root [contribution guide](../CONTRIBUTING.md). HiveUp isn't published to PyPI and isolates this integration's existing requirements. From the repository root, run:

```bash
hiveup test gong
```

### Live API Testing

Prepare a separate local environment with `gong/requirements.txt` and the repository's test dependencies. Copy the root [.env.example](../.env.example) to an uncommitted `.env` and set `GONG_ACCESS_TOKEN`. Set `GONG_API_BASE_URL` to the `api_base_url_for_customer` value when Gong's OAuth response includes it; the test fixture otherwise defaults to `https://api.gong.io`. These tests use an OAuth access token, not the access-key variables also listed in `.env.example`. Don't put credentials in tracked test files.

From the repository root in that prepared environment, run the read-only live tests against a dedicated test workspace:

```bash
python -m pytest gong/tests/test_gong_integration.py -m "integration and not destructive"
```

## API Reference

### Actions

#### `list_calls`
List calls with optional filtering.

**Input:**
- `from_date` (optional): Start date (YYYY-MM-DD)
- `to_date` (optional): End date (YYYY-MM-DD)
- `user_ids` (optional): Array of user IDs to filter by
- `limit` (optional): Maximum number of calls (default: 100)
- `cursor` (optional): Pagination cursor

**Output:**
- `calls`: Array of call objects
- `has_more`: Boolean indicating more results available
- `next_cursor`: Pagination cursor for next page

#### `get_call_transcript`
Retrieve transcript for a specific call.

**Input:**
- `call_id` (required): The call ID

**Output:**
- `call_id`: The call ID
- `transcript`: Array of segments containing `speaker_id`, `speaker_name`, `start_time`, `end_time`, and `text`

#### `get_call_details`
Get comprehensive call information.

**Input:**
- `call_id` (required): The call ID

**Output:**
- Complete call object with participants, outcome, CRM data, etc.

#### `search_calls`
Search calls by keywords or topics.

**Input:**
- `query` (required): Search query string
- `from_date` (optional): Start date for search
- `to_date` (optional): End date for search
- `limit` (optional): Maximum results (default: 50)

**Output:**
- `results`: Array of matching calls with relevance scores
- `total_count`: Total number of matching calls

#### `list_users`
List workspace users.

**Input:**
- `limit` (optional): Maximum number of users (default: 100)
- `cursor` (optional): Pagination cursor

**Output:**
- `users`: Array of user objects
- `has_more`: Boolean indicating more results available
- `next_cursor`: Pagination cursor for next page

## Error Handling

Check `IntegrationResult.type` before reading an action payload. The handlers return `ActionError` for provider and network failures; `execute_action` wraps these errors rather than returning empty successful data. SDK schema validation failures also produce a non-action result. `ExecutionContext.fetch` raises exceptions for HTTP errors rather than returning an error-status `FetchResponse` as a success.

## Development

### Project Structure
```
gong/
├── config.json          # Integration configuration
├── requirements.txt     # Python dependencies
├── gong.py             # Main integration code
├── README.md           # This file
└── tests/
    ├── __init__.py
    ├── conftest.py              # Test import setup
    ├── test_gong_unit.py        # Offline unit tests
    └── test_gong_integration.py # Live API tests
```

### Adding New Features
1. Update `config.json` with new action definitions
2. Add implementation in `gong.py`
3. Add offline tests in `tests/test_gong_unit.py` and optional live tests in `tests/test_gong_integration.py`
4. Update documentation

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify the OAuth access token is valid and the customer-specific API base URL is supplied
   - Ensure you have admin access to Gong
   - Check that required scopes are enabled

2. **No Data Returned**
   - Verify date ranges are correct
   - Check user permissions for call access
   - Ensure calls exist in the specified timeframe

3. **Rate Limiting**
   - Gong API has rate limits
   - Reduce request frequency
   - Implement exponential backoff

### Debug Mode
Enable detailed logging by setting environment variables:
```bash
export GONG_DEBUG=1
python gong.py
```

## Support

For issues related to:
- **Integration bugs**: Check the test suite and error logs
- **Gong API**: Consult Gong's official API documentation
- **Authentication**: Verify admin access, OAuth configuration, and granted scopes

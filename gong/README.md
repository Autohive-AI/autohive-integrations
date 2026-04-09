# Gong Integration

A comprehensive integration for accessing Gong call recordings, transcripts, and CRM data through the Gong API.

## Features

### Actions
- **List Calls** - Retrieve calls with filtering by date, users, and other criteria
- **Get Call Transcript** - Fetch detailed transcripts with speaker segments
- **Get Call Details** - Access comprehensive call information including CRM data
- **Search Calls** - Search through calls using keywords and topics
- **List Users** - Retrieve workspace users with roles and status

### Triggers
- **New Calls Polling** - Monitor for new calls in the workspace (5-minute intervals)

## Setup

### 1. Authentication
The integration uses Gong's API key authentication:

1. **Get API Credentials** (requires Gong admin access):
   - Go to Company Settings > Ecosystem > API
   - Click "Get API Key" to receive your access key and secret
   - Copy both values for configuration

2. **Configure Integration**:
   - Set authentication provider to "gong"
   - Provide your API key and secret through the platform's auth system

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Required Scopes
The integration requires these API scopes:
- `api:calls:read` - Access call data
- `api:calls:transcript:read` - Access call transcripts
- `api:crm:read` - Access CRM integration data
- `api:users:read` - Access user information
- `api:call-user-access:read` - Access user call permissions

## Usage Examples

### List Recent Calls
```python
# Get calls from the last 30 days
result = await integration.execute_action("list_calls", {
    "from_date": "2025-01-01",
    "to_date": "2025-01-31",
    "limit": 50
})

for call in result["calls"]:
    print(f"Call: {call['title']} - {call['started']}")
```

### Get Call Transcript
```python
# Get detailed transcript for a specific call
result = await integration.execute_action("get_call_transcript", {
    "call_id": "call_123456"
})

for segment in result["transcript"]:
    print(f"{segment['speaker']}: {segment['text']}")
```

### Search Calls
```python
# Search for calls containing specific keywords
result = await integration.execute_action("search_calls", {
    "query": "product demo pricing",
    "from_date": "2025-01-01",
    "limit": 25
})

for call in result["results"]:
    print(f"Match: {call['title']} (Score: {call['relevance_score']})")
```

### Monitor New Calls
```python
# Set up polling for new calls
await integration.setup_polling_trigger("new_calls", {
    "user_ids": ["user_123", "user_456"],
    "limit": 100
})
```

## Testing

### Quick Test (Mock Data)
```bash
# Run tests with mock responses (safe, no API calls)
python test/run_tests.py --type mock --verbose
```

### Live API Testing
1. **Configure credentials** in `test/test_config.py`:
   ```python
   GONG_API_KEY = "your_access_key"
   GONG_API_SECRET = "your_access_key_secret"
   ENABLE_LIVE_TESTS = True
   MOCK_RESPONSES = False
   ```

2. **Run live tests**:
   ```bash
   python test/run_tests.py --type integration --verbose
   ```

### Check Configuration
```bash
python test/run_tests.py --check-config
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
- `transcript`: Array of transcript segments with speaker, timing, and text

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

### Triggers

#### `new_calls`
Polls for new calls every 5 minutes.

**Input:**
- `user_ids` (optional): Array of user IDs to monitor
- `limit` (optional): Maximum calls to check (default: 50)

**Output:**
- Array of new call objects

## Error Handling

The integration includes comprehensive error handling:
- Network errors return empty results with error messages
- Invalid API responses are handled gracefully
- Rate limiting and authentication errors are properly reported
- All actions include error fields in responses

## Development

### Project Structure
```
gong/
├── config.json          # Integration configuration
├── requirements.txt     # Python dependencies
├── gong.py             # Main integration code
├── README.md           # This file
└── test/
    ├── test_config.py           # Test configuration
    ├── test_gong_integration.py # Test suite
    ├── run_tests.py            # Test runner
    └── README.md               # Test documentation
```

### Adding New Features
1. Update `config.json` with new action/trigger definitions
2. Add implementation in `gong.py`
3. Add tests in `test/test_gong_integration.py`
4. Update documentation

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify API key and secret are correct
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
- **Authentication**: Verify admin access and API key configuration

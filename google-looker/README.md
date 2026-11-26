# Google Looker Integration

A comprehensive integration for accessing Google Looker dashboards, models, queries, and data through the Looker API.

## Features

### Actions
- **List Dashboards** - Retrieve all available dashboards with metadata
- **Get Dashboard** - Fetch detailed dashboard information including elements
- **Execute LookML Query** - Run queries against Looker models and explores
- **List Models** - Retrieve all LookML models with their explores
- **Get Model** - Access detailed model information and structure
- **Execute SQL Query** - Run raw SQL queries against connected data sources
- **List Connections** - Retrieve all database connections configured in Looker

## Setup

### 1. Authentication
The integration uses Looker's API key authentication:

1. **Get API Credentials** (requires Looker admin access):
   - Go to Admin > Users > API Keys
   - Create a new API key pair (Client ID and Client Secret)
   - Ensure the API user has appropriate permissions for data access

2. **Configure Integration**:
   - Set authentication provider to "custom"
   - Provide your Looker instance base URL (e.g., https://your-company.looker.com)
   - Provide your API Client ID and Client Secret

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Required Permissions
The integration requires these API permissions:
- `see_lookml_dashboards` - Access dashboard data
- `see_lookml` - Access models and explores
- `see_sql` - Access SQL query functionality
- `access_data` - Execute queries and retrieve data

## Usage Examples

Run these fragments inside an async function. `integration` must be the registered `google_looker` instance from `google_looker.py`; import `ResultType` from `autohive_integrations_sdk`. Your caller must supply an open `ExecutionContext` named `context`, managed with `async with`, using `{"auth_type": "Custom", "credentials": {"base_url": supplied_base_url, "client_id": supplied_client_id, "client_secret": supplied_client_secret}}`. The handler exchanges these credentials for a Looker token. Use a test instance and supply secrets securely rather than embedding them in source.

`execute_action` returns an `IntegrationResult`. Check `ResultType.ACTION` before reading `result.result.data`; handle other result types as failures. See the [SDK calling patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md). These examples don't change the SDK pin in [requirements.txt](requirements.txt).

### List All Dashboards
```python
# Get all available dashboards
result = await integration.execute_action(
    "list_dashboards", {"fields": "id,title,description,created_at", "per_page": 50}, context
)

assert result.type == ResultType.ACTION, result.result
for dashboard in result.result.data["dashboards"]:
    print(f"Dashboard: {dashboard['title']} (ID: {dashboard['id']})")
```

### Get Dashboard Details
```python
# Get detailed information about a specific dashboard
result = await integration.execute_action(
    "get_dashboard", {"dashboard_id": "123", "fields": "id,title,description,dashboard_elements"}, context
)

assert result.type == ResultType.ACTION, result.result
dashboard = result.result.data["dashboard"]
print(f"Dashboard: {dashboard['title']}")
print(f"Elements: {len(dashboard['dashboard_elements'])}")
```

### Execute LookML Query
```python
# Run a query against a Looker model
result = await integration.execute_action(
    "execute_lookml_query",
    {
        "model": "sales_analytics",
        "explore": "orders",
        "dimensions": ["orders.status", "orders.created_date"],
        "measures": ["orders.count", "orders.total_amount"],
        "filters": {"orders.created_date": "30 days ago for 30 days"},
        "sorts": ["orders.created_date desc"],
        "limit": 1000,
        "result_format": "json",
    },
    context,
)

import json

assert result.type == ResultType.ACTION, result.result
query_data = json.loads(result.result.data["query_results"])
for row in query_data:
    print(f"Status: {row['orders.status']}, Count: {row['orders.count']}")
```

### Execute SQL Query
```python
# Run raw SQL against a connected database
result = await integration.execute_action(
    "execute_sql_query",
    {
        "sql": """
        SELECT 
            status,
            COUNT(*) as order_count,
            SUM(total_amount) as total_revenue
        FROM orders 
        WHERE created_date >= '2025-01-01'
        GROUP BY status
        ORDER BY total_revenue DESC
    """,
        "connection_name": "production_warehouse",
        "result_format": "json",
    },
    context,
)

import json

assert result.type == ResultType.ACTION, result.result
sql_data = json.loads(result.result.data["query_results"])
for row in sql_data:
    print(f"{row['status']}: {row['order_count']} orders, ${row['total_revenue']}")
```

### List Models and Explores
```python
# Get all available models
models_result = await integration.execute_action("list_models", {"fields": "name,label,explores"}, context)

assert models_result.type == ResultType.ACTION, models_result.result
for model in models_result.result.data["models"]:
    print(f"Model: {model['name']} ({model['label']})")

    # Get detailed model information
    model_detail = await integration.execute_action(
        "get_model", {"model_name": model["name"], "fields": "name,explores.name,explores.label"}, context
    )

    assert model_detail.type == ResultType.ACTION, model_detail.result
    for explore in model_detail.result.data["model"]["explores"]:
        print(f"  - Explore: {explore['name']} ({explore['label']})")
```

## Testing

### Offline unit tests

Install HiveUp 2.5.4 from a Tooling local build as described in the root [contribution guide](../CONTRIBUTING.md). HiveUp isn't published to PyPI and isolates this integration's existing requirements. From the repository root, run:

```bash
hiveup test google-looker
```

### Live API Testing

Prepare a separate local environment with `google-looker/requirements.txt` and the repository's test dependencies. Copy the root [.env.example](../.env.example) to an uncommitted `.env` and set `LOOKER_BASE_URL`, `LOOKER_CLIENT_ID`, and `LOOKER_CLIENT_SECRET`. Set `LOOKER_TEST_DASHBOARD_ID` and `LOOKER_TEST_MODEL_NAME` to existing resources to exercise the resource-specific tests; those tests skip when the IDs aren't supplied. Don't put credentials in tracked test files.

From the repository root in that prepared environment, run the read-only live tests against a test instance:

```bash
python -m pytest google-looker/tests/test_google_looker_integration.py -m "integration and not destructive"
```

### Test Coverage
The test suite covers:
- All action handlers with mock responses
- Authentication flow and token management
- Error handling for missing credentials
- Input validation for required parameters
- API response parsing and data transformation

## API Reference

### Actions

#### `list_dashboards`
Retrieve all available dashboards.

**Input:**
- `fields` (optional): Comma-separated list of fields to include
- `page` (optional): Page number for pagination
- `per_page` (optional): Number of dashboards per page

**Output:**
- `dashboards`: Array of dashboard objects

#### `get_dashboard`
Get detailed information about a specific dashboard.

**Input:**
- `dashboard_id` (required): The dashboard ID
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `dashboard`: Complete dashboard object with elements and metadata

#### `execute_lookml_query`
Execute a query against Looker models.

**Input:**
- `model` (required): The LookML model name
- `explore` (required): The explore name within the model
- `dimensions` (optional): Array of dimension names
- `measures` (optional): Array of measure names
- `filters` (optional): Object with filter conditions
- `sorts` (optional): Array of sort specifications
- `limit` (optional): Maximum number of results
- `result_format` (optional): Output format (json, csv, etc.)

**Output:**
- `query_results`: String containing query results in the requested format; parse with `json.loads` only for JSON output

#### `execute_sql_query`
Execute raw SQL queries against connected databases.

**Input:**
- `sql` (required): The SQL query string
- `connection_name` OR `model_name` (required): Database connection or model to use
- `result_format` (optional): Output format (default: json)
- `download` (optional): Whether to format for download

**Output:**
- `slug`: Query identifier for reference
- `query_results`: String containing SQL results in the requested format; parse with `json.loads` only for JSON output

#### `list_models`
Retrieve all available LookML models.

**Input:**
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `models`: Array of model objects with explores

#### `get_model`
Get detailed information about a specific model.

**Input:**
- `model_name` (required): The model name
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `model`: Complete model object with explores and dimensions

#### `list_connections`
Retrieve all database connections.

**Input:**
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `connections`: Array of connection objects

## Error Handling

Check `IntegrationResult.type` before reading an action payload. The handlers return `ActionError` for authentication, network, and provider failures; `execute_action` wraps those errors rather than returning empty successful data. SDK schema validation failures also produce a non-action result. `ExecutionContext.fetch` raises exceptions for HTTP errors rather than returning an error-status `FetchResponse` as a success. Successful action payloads have no shared `result` or `error` field.

## Development

### Project Structure
```
google-looker/
├── config.json              # Integration configuration
├── requirements.txt         # Python dependencies
├── google_looker.py        # Main integration code
├── README.md               # This file
└── tests/
    ├── __init__.py
    ├── conftest.py                       # Test import setup
    ├── test_google_looker_unit.py        # Offline unit tests
    └── test_google_looker_integration.py # Live API tests
```

### Adding New Features
1. Update `config.json` with new action definitions
2. Add implementation in `google_looker.py`
3. Add offline tests in `tests/test_google_looker_unit.py` and optional live tests in `tests/test_google_looker_integration.py`
4. Update documentation

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify Client ID and Client Secret are correct
   - Ensure the API user has required permissions
   - Check that the base URL is correct and accessible

2. **No Data Returned**
   - Verify the user has access to the requested dashboards/models
   - Check that the model and explore names are correct
   - Ensure proper permissions are granted for data access

3. **Query Execution Errors**
   - Validate LookML syntax for dimensions and measures
   - Check that the connection exists and is accessible
   - Ensure SQL syntax is compatible with the target database

4. **Rate Limiting**
   - Looker API has rate limits per user/hour
   - Implement appropriate delays between requests
   - Consider caching frequently accessed data

### Debug Mode
Enable detailed logging by setting environment variables:
```bash
export LOOKER_DEBUG=1
python google_looker.py
```

## Support

For issues related to:
- **Integration bugs**: Check the test suite and error logs
- **Looker API**: Consult Looker's official API documentation
- **Authentication**: Verify admin access and API key configuration
- **Data access**: Check user permissions and model/explore availability

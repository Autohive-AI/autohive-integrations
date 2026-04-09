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

### List All Dashboards
```python
# Get all available dashboards
result = await integration.execute_action("list_dashboards", {
    "fields": "id,title,description,created_at",
    "per_page": 50
})

for dashboard in result["dashboards"]:
    print(f"Dashboard: {dashboard['title']} (ID: {dashboard['id']})")
```

### Get Dashboard Details
```python
# Get detailed information about a specific dashboard
result = await integration.execute_action("get_dashboard", {
    "dashboard_id": "123",
    "fields": "id,title,description,dashboard_elements"
})

dashboard = result["dashboard"]
print(f"Dashboard: {dashboard['title']}")
print(f"Elements: {len(dashboard['dashboard_elements'])}")
```

### Execute LookML Query
```python
# Run a query against a Looker model
result = await integration.execute_action("execute_lookml_query", {
    "model": "sales_analytics",
    "explore": "orders",
    "dimensions": ["orders.status", "orders.created_date"],
    "measures": ["orders.count", "orders.total_amount"],
    "filters": {
        "orders.created_date": "30 days ago for 30 days"
    },
    "sorts": ["orders.created_date desc"],
    "limit": 1000,
    "result_format": "json"
})

import json
query_data = json.loads(result["query_results"])
for row in query_data:
    print(f"Status: {row['orders.status']}, Count: {row['orders.count']}")
```

### Execute SQL Query
```python
# Run raw SQL against a connected database
result = await integration.execute_action("execute_sql_query", {
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
    "result_format": "json"
})

import json
sql_data = json.loads(result["query_results"])
for row in sql_data:
    print(f"{row['status']}: {row['order_count']} orders, ${row['total_revenue']}")
```

### List Models and Explores
```python
# Get all available models
models_result = await integration.execute_action("list_models", {
    "fields": "name,label,explores"
})

for model in models_result["models"]:
    print(f"Model: {model['name']} ({model['label']})")
    
    # Get detailed model information
    model_detail = await integration.execute_action("get_model", {
        "model_name": model['name'],
        "fields": "name,explores.name,explores.label"
    })
    
    for explore in model_detail["model"]["explores"]:
        print(f"  - Explore: {explore['name']} ({explore['label']})")
```

## Testing

### Quick Test (Mock Data)
```bash
# Run tests with mock responses (safe, no API calls)
python test/test_google_looker_integration.py
```

### Live API Testing
1. **Configure credentials** in your test environment:
   ```python
   LOOKER_BASE_URL = "https://your-company.looker.com"
   LOOKER_CLIENT_ID = "your_client_id"
   LOOKER_CLIENT_SECRET = "your_client_secret"
   ```

2. **Run live tests** (ensure you have test dashboards and models):
   ```bash
   python -m pytest test/ -v
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
- `result`: Boolean indicating success

#### `get_dashboard`
Get detailed information about a specific dashboard.

**Input:**
- `dashboard_id` (required): The dashboard ID
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `dashboard`: Complete dashboard object with elements and metadata
- `result`: Boolean indicating success

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
- `query_results`: JSON string containing query results
- `result`: Boolean indicating success

#### `execute_sql_query`
Execute raw SQL queries against connected databases.

**Input:**
- `sql` (required): The SQL query string
- `connection_name` OR `model_name` (required): Database connection or model to use
- `result_format` (optional): Output format (default: json)
- `download` (optional): Whether to format for download

**Output:**
- `slug`: Query identifier for reference
- `query_results`: JSON string containing SQL results
- `result`: Boolean indicating success

#### `list_models`
Retrieve all available LookML models.

**Input:**
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `models`: Array of model objects with explores
- `result`: Boolean indicating success

#### `get_model`
Get detailed information about a specific model.

**Input:**
- `model_name` (required): The model name
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `model`: Complete model object with explores and dimensions
- `result`: Boolean indicating success

#### `list_connections`
Retrieve all database connections.

**Input:**
- `fields` (optional): Comma-separated list of fields to include

**Output:**
- `connections`: Array of connection objects
- `result`: Boolean indicating success

## Error Handling

The integration includes comprehensive error handling:
- Authentication failures return appropriate error messages
- Invalid API responses are handled gracefully
- Missing required parameters are validated
- Network errors return empty results with error details
- All actions include error fields in responses

## Development

### Project Structure
```
google-looker/
├── config.json              # Integration configuration
├── requirements.txt         # Python dependencies
├── google_looker.py        # Main integration code
├── README.md               # This file
└── test/
    ├── __init__.py
    ├── context.py                    # Test configuration
    └── test_google_looker_integration.py # Test suite
```

### Adding New Features
1. Update `config.json` with new action definitions
2. Add implementation in `google_looker.py`
3. Add tests in `test/test_google_looker_integration.py`
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

# Google Analytics Integration

Google Analytics 4 (GA4) integration for accessing analytics data, reports, and metrics.

## Features

### Standard Reports
- Run customized reports with dimensions and metrics
- Filter by date ranges
- Support for pagination with limit and offset
- Access to all GA4 event data

### Realtime Reports
- Get real-time analytics data for the last 30 minutes
- Monitor active users and current activity
- Track real-time engagement metrics

### Metadata Discovery
- Retrieve all available dimensions and metrics for your property
- Get detailed descriptions and API names
- Explore available data points before building reports

### Batch Processing
- Run multiple reports in a single API call
- Efficient data retrieval for complex analytics needs
- Reduced API calls and improved performance

## Authentication

This integration uses Google OAuth2 authentication. You'll need:

- **Access Token**: A valid Google OAuth2 access token with Analytics Data API access

Required OAuth2 scopes:
- `https://www.googleapis.com/auth/analytics.readonly` - Read-only access to Google Analytics data

## Actions

### run_report
Generate a customized report of Google Analytics event data.

**Inputs:**
- `property_id` (string, required): GA4 Property ID (e.g., "123456789")
- `date_ranges` (array, required): Array of date range objects
  - `start_date` (string): Start date (YYYY-MM-DD or relative like "7daysAgo")
  - `end_date` (string): End date (YYYY-MM-DD or relative like "today")
- `dimensions` (array, optional): Array of dimension objects
  - `name` (string): Dimension API name (e.g., "country", "city", "deviceCategory")
- `metrics` (array, required): Array of metric objects
  - `name` (string): Metric API name (e.g., "activeUsers", "sessions", "screenPageViews")
- `limit` (integer, optional): Maximum number of rows to return (default: 10000)
- `offset` (integer, optional): Number of rows to skip (default: 0)

**Output:**
- `rows` (array): Array of data rows with dimension and metric values
- `row_count` (integer): Number of rows returned
- `result` (boolean): Success status

### run_realtime_report
Get real-time Google Analytics data for the last 30 minutes.

**Inputs:**
- `property_id` (string, required): GA4 Property ID
- `dimensions` (array, optional): Array of dimension objects
  - `name` (string): Dimension API name
- `metrics` (array, required): Array of metric objects
  - `name` (string): Metric API name
- `limit` (integer, optional): Maximum number of rows to return (default: 10000)

**Output:**
- `rows` (array): Array of real-time data rows
- `row_count` (integer): Number of rows returned
- `result` (boolean): Success status

### get_metadata
Retrieve available dimensions and metrics for a Google Analytics property.

**Inputs:**
- `property_id` (string, required): GA4 Property ID

**Output:**
- `dimensions` (array): Array of available dimensions with API names, UI names, and descriptions
- `metrics` (array): Array of available metrics with API names, UI names, and descriptions
- `dimension_count` (integer): Total number of dimensions
- `metric_count` (integer): Total number of metrics
- `result` (boolean): Success status

### batch_run_reports
Run multiple reports in a single API call for efficiency.

**Inputs:**
- `property_id` (string, required): GA4 Property ID
- `report_requests` (array, required): Array of report request objects, each containing:
  - `date_ranges` (array, required): Array of date range objects
  - `dimensions` (array, optional): Array of dimension objects
  - `metrics` (array, required): Array of metric objects
  - `limit` (integer, optional): Maximum rows per report (default: 10000)
  - `offset` (integer, optional): Rows to skip per report (default: 0)

**Output:**
- `reports` (array): Array of report results, each containing:
  - `rows` (array): Data rows for the report
  - `row_count` (integer): Number of rows in the report
- `report_count` (integer): Total number of reports returned
- `result` (boolean): Success status

## Common Dimensions

- `country` - User's country
- `city` - User's city
- `region` - User's region
- `deviceCategory` - Device type (mobile, desktop, tablet)
- `browser` - Browser used
- `operatingSystem` - Operating system
- `pagePath` - Page URL path
- `pageTitle` - Page title
- `eventName` - Event name
- `date` - Date in YYYYMMDD format

## Common Metrics

- `activeUsers` - Number of active users
- `sessions` - Number of sessions
- `screenPageViews` - Number of page/screen views
- `bounceRate` - Bounce rate
- `averageSessionDuration` - Average session duration
- `conversions` - Number of conversions
- `eventCount` - Total number of events
- `engagementRate` - Engagement rate

## Technical Details

### API Endpoints

- Google Analytics Data API v1 (Beta): Uses `BetaAnalyticsDataClient`
- Token URL: `https://oauth2.googleapis.com/token`

### Date Formats

The API supports both absolute and relative date formats:
- Absolute: `YYYY-MM-DD` (e.g., "2024-01-01")
- Relative: `today`, `yesterday`, `NdaysAgo` (e.g., "7daysAgo", "30daysAgo")

### Rate Limits

Google Analytics Data API has the following quotas:
- 25,000 API requests per day per project
- 10 concurrent requests per property

### Best Practices

1. Use `batch_run_reports` when you need multiple reports to reduce API calls
2. Use appropriate `limit` values to avoid retrieving unnecessary data
3. Cache metadata results as they don't change frequently
4. Use relative date ranges (e.g., "7daysAgo") for recurring reports
5. Consider using real-time reports only when necessary as they have stricter limits

## Testing

To test the integration:

1. Obtain a Google OAuth2 access token with Analytics Data API access
2. Find your GA4 Property ID from Google Analytics Admin
3. Update the credentials in `tests/test_google_analytics.py`
4. Replace `PROPERTY_ID` and `access_token` with your values
5. Run the tests: `python tests/test_google_analytics.py`

## Example Usage

### Basic Report
```python
inputs = {
    "property_id": "123456789",
    "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
    "dimensions": [{"name": "country"}],
    "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
    "limit": 10
}
```

### Realtime Data
```python
inputs = {
    "property_id": "123456789",
    "dimensions": [{"name": "country"}],
    "metrics": [{"name": "activeUsers"}]
}
```

### Multiple Reports
```python
inputs = {
    "property_id": "123456789",
    "report_requests": [
        {
            "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}],
            "dimensions": [{"name": "country"}],
            "metrics": [{"name": "activeUsers"}]
        },
        {
            "date_ranges": [{"start_date": "30daysAgo", "end_date": "today"}],
            "dimensions": [{"name": "deviceCategory"}],
            "metrics": [{"name": "sessions"}]
        }
    ]
}
```

## Resources

- [Google Analytics Data API Documentation](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [GA4 Dimensions & Metrics Explorer](https://ga-dev-tools.google/ga4/dimensions-metrics-explorer/)
- [OAuth 2.0 for Google APIs](https://developers.google.com/identity/protocols/oauth2)
- [Google Analytics Property ID](https://support.google.com/analytics/answer/9539598)

## Version

1.0.0

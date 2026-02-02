# Google Search Console Integration

Google Search Console integration for accessing search analytics, URL inspection, sitemap management, and site verification data.

## Features

### Search Analytics
- Query search performance data with dimensions and metrics
- Filter by date ranges, queries, pages, countries, devices
- Access clicks, impressions, CTR, and position data
- Support for dimension filters and grouping
- Pagination support for large datasets

### Site Management
- List all verified sites in your Search Console account
- View permission levels for each site
- Support for both URL-prefix and Domain properties

### URL Inspection
- Inspect individual URLs for index status
- Check mobile usability
- View AMP validation results
- Get rich results information
- Check crawl status and last crawl date

### Sitemap Management
- List all sitemaps for a site
- Get detailed sitemap information
- View submission status and errors
- Check sitemap index status

## Authentication

This integration uses Google OAuth2 authentication. You'll need:

- **Access Token**: A valid Google OAuth2 access token with Search Console API access

Required OAuth2 scopes:
- `https://www.googleapis.com/auth/webmasters` - Full access to Google Search Console data (required for URL Inspection API)

## Actions

### query_analytics
Retrieve search analytics data including queries, pages, countries, and devices.

**Inputs:**
- `site_url` (string, required): The site URL (e.g., "https://example.com" or "sc-domain:example.com")
- `start_date` (string, required): Start date in YYYY-MM-DD format
- `end_date` (string, required): End date in YYYY-MM-DD format
- `dimensions` (array, optional): Dimensions to group by (e.g., ["query", "page", "country", "device", "date"])
- `dimension_filter_groups` (array, optional): Filters to apply to the data
  - `filters` (array): Array of filter objects
    - `dimension` (string): Dimension to filter
    - `operator` (string): Filter operator (equals, notEquals, contains, notContains)
    - `expression` (string): Filter value
- `row_limit` (integer, optional): Maximum number of rows to return (default: 25000, max: 25000)
- `start_row` (integer, optional): Starting row for pagination (default: 0)

**Output:**
- `rows` (array): Array of analytics data rows with dimensions and metrics
- `row_count` (integer): Number of rows returned
- `result` (boolean): Success status

**Metrics included in each row:**
- `clicks` (integer): Number of clicks
- `impressions` (integer): Number of impressions
- `ctr` (float): Click-through rate
- `position` (float): Average position in search results

### list_sites
List all sites in the user's Search Console account.

**Inputs:**
None

**Output:**
- `sites` (array): Array of site objects
  - `site_url` (string): The site URL
  - `permission_level` (string): User's permission level (owner, full, restricted)
- `site_count` (integer): Number of sites
- `result` (boolean): Success status

### inspect_url
Get URL inspection data including index status, mobile usability, and more.

**Inputs:**
- `site_url` (string, required): The site URL (e.g., "https://example.com")
- `inspection_url` (string, required): The URL to inspect

**Output:**
- `inspection_result` (object): URL inspection data including:
  - Index status
  - Mobile usability
  - AMP validation
  - Rich results
  - Crawl information
- `result` (boolean): Success status

### list_sitemaps
List all sitemaps for a site.

**Inputs:**
- `site_url` (string, required): The site URL (e.g., "https://example.com")

**Output:**
- `sitemaps` (array): Array of sitemap objects
  - `path` (string): Sitemap URL
  - `last_submitted` (string): Last submission timestamp
  - `is_pending` (boolean): Whether sitemap is pending
  - `is_sitemap_index` (boolean): Whether it's a sitemap index
- `sitemap_count` (integer): Number of sitemaps
- `result` (boolean): Success status

### get_sitemap
Get detailed information about a specific sitemap.

**Inputs:**
- `site_url` (string, required): The site URL (e.g., "https://example.com")
- `sitemap_url` (string, required): The sitemap URL

**Output:**
- `sitemap` (object): Detailed sitemap information including:
  - Path
  - Last submitted date
  - Status
  - Errors and warnings
  - Contents (for sitemap indexes)
- `result` (boolean): Success status

## Common Dimensions

- `query` - Search query
- `page` - Page URL
- `country` - Country code (e.g., "USA", "GBR")
- `device` - Device type (MOBILE, DESKTOP, TABLET)
- `date` - Date in YYYY-MM-DD format
- `searchAppearance` - Search appearance type (e.g., AMP_BLUE_LINK, RICH_RESULT)

## Available Metrics

All analytics queries return the following metrics:
- `clicks` - Number of clicks from search results
- `impressions` - Number of times the URL appeared in search results
- `ctr` - Click-through rate (clicks / impressions)
- `position` - Average position in search results (1 = top)

## Technical Details

### API Endpoints

- Google Search Console API v1: Uses `searchconsole` service
- Token URL: `https://oauth2.googleapis.com/token`

### Date Formats

The API requires absolute date formats:
- Format: `YYYY-MM-DD` (e.g., "2024-01-01")
- Maximum date range: 16 months
- Data available from: Past 16 months

### Rate Limits

Google Search Console API has the following quotas:
- 1,200 API requests per minute per project
- Maximum 25,000 rows per analytics query

### Site URL Formats

Two types of properties are supported:
1. **URL-prefix property**: `https://example.com` or `http://example.com`
2. **Domain property**: `sc-domain:example.com` (requires DNS verification)

### Best Practices

1. Use appropriate date ranges to avoid hitting the 16-month limit
2. Apply dimension filters to reduce data volume when possible
3. Use pagination for large result sets (max 25,000 rows per request)
4. Cache site list results as they don't change frequently
5. Group by relevant dimensions to get actionable insights
6. Use URL inspection sparingly as it counts against quotas

## Filter Examples

### Filter by country
```python
"dimension_filter_groups": [
    {
        "filters": [
            {
                "dimension": "country",
                "operator": "equals",
                "expression": "USA"
            }
        ]
    }
]
```

### Filter by device
```python
"dimension_filter_groups": [
    {
        "filters": [
            {
                "dimension": "device",
                "operator": "equals",
                "expression": "MOBILE"
            }
        ]
    }
]
```

### Filter by query containing keyword
```python
"dimension_filter_groups": [
    {
        "filters": [
            {
                "dimension": "query",
                "operator": "contains",
                "expression": "python"
            }
        ]
    }
]
```

### Multiple filters (AND logic)
```python
"dimension_filter_groups": [
    {
        "filters": [
            {
                "dimension": "country",
                "operator": "equals",
                "expression": "USA"
            },
            {
                "dimension": "device",
                "operator": "equals",
                "expression": "MOBILE"
            }
        ]
    }
]
```

## Testing

To test the integration:

1. Obtain a Google OAuth2 access token with Search Console API access
2. Verify you have a property set up in Google Search Console
3. Update the credentials in `tests/test_google_search_console.py`
4. Replace `SITE_URL` and `access_token` with your values
5. Run the tests: `python tests/test_google_search_console.py`

## Example Usage

### Query Top Search Queries
```python
inputs = {
    "site_url": "https://example.com",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "dimensions": ["query"],
    "row_limit": 100
}
```

### Query by Country and Device
```python
inputs = {
    "site_url": "https://example.com",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "dimensions": ["country", "device"],
    "row_limit": 50
}
```

### Query with Filters
```python
inputs = {
    "site_url": "https://example.com",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "dimensions": ["query", "page"],
    "dimension_filter_groups": [
        {
            "filters": [
                {
                    "dimension": "country",
                    "operator": "equals",
                    "expression": "USA"
                }
            ]
        }
    ],
    "row_limit": 100
}
```

### Inspect a URL
```python
inputs = {
    "site_url": "https://example.com",
    "inspection_url": "https://example.com/page-to-inspect"
}
```

### List All Sites
```python
inputs = {}
```

### List Sitemaps
```python
inputs = {
    "site_url": "https://example.com"
}
```

## Resources

- [Google Search Console API Documentation](https://developers.google.com/webmaster-tools/search-console-api-original)
- [Search Analytics API Reference](https://developers.google.com/webmaster-tools/search-console-api-original/v3/searchanalytics)
- [URL Inspection API Documentation](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [OAuth 2.0 for Google APIs](https://developers.google.com/identity/protocols/oauth2)
- [Search Console Help](https://support.google.com/webmasters)

## Version

1.0.0

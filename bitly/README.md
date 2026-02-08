# Bitly Integration for Autohive

URL shortening and link management integration with Bitly for creating, managing, and tracking shortened links.

## Description

This integration provides access to Bitly's link management platform for shortening URLs, creating custom bitlinks, tracking click analytics, and managing groups and organizations. It allows you to automate link creation and monitor link performance.

The integration uses Bitly API v4 with OAuth 2.0 authentication and implements 12 actions covering link management, click analytics, and organization management.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication with Bitly.

### Setup Steps

1. Connect your Bitly account through Autohive's OAuth flow
2. Authorize the requested permissions
3. Start using the integration actions

### Account Limits

API limits depend on your Bitly subscription:
- **Free**: 5 links/month, 1,000 API calls/month
- **Core ($10/mo)**: Higher limits, 30-day click data
- **Growth ($29/mo)**: Branded links, 4-month click data
- **Premium ($199/mo)**: Extended features and limits

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

## Actions (12 Total)

### User & Account (1 action)

#### `get_user`
Get information about the currently authenticated user.

**Inputs:** None

**Outputs:**
- `user`: User information including name, email, default_group_guid
- `result`: Success status

---

### Link Management (6 actions)

#### `shorten_url`
Shorten a long URL to a Bitly link (simple, quick shortening).

**Inputs:**
- `long_url` (required): The URL to shorten
- `domain` (optional): Custom domain to use (default: bit.ly)
- `group_guid` (optional): Group GUID to associate the link with

**Outputs:**
- `bitlink`: Created bitlink details including link, id, long_url
- `result`: Success status

---

#### `create_bitlink`
Create a bitlink with advanced options like custom back-half, title, and tags.

**Inputs:**
- `long_url` (required): The URL to shorten
- `domain` (optional): Custom domain to use (default: bit.ly)
- `group_guid` (optional): Group GUID to associate the link with
- `title` (optional): Title for the bitlink
- `tags` (optional): Array of tags to categorize the bitlink
- `custom_back_half` (optional): Custom back-half for the short URL (e.g., 'my-link' for bit.ly/my-link)

**Outputs:**
- `bitlink`: Created bitlink details
- `result`: Success status

---

#### `get_bitlink`
Get information about a specific bitlink.

**Inputs:**
- `bitlink` (required): The bitlink to retrieve (e.g., 'bit.ly/abc123' or just 'abc123')

**Outputs:**
- `bitlink`: Bitlink details including long_url, title, tags, created_at
- `result`: Success status

---

#### `update_bitlink`
Update an existing bitlink's title, tags, or archived status.

**Inputs:**
- `bitlink` (required): The bitlink to update
- `title` (optional): New title for the bitlink
- `tags` (optional): New tags for the bitlink
- `archived` (optional): Whether to archive the bitlink

**Outputs:**
- `bitlink`: Updated bitlink details
- `result`: Success status

---

#### `expand_bitlink`
Get the original long URL from a bitlink.

**Inputs:**
- `bitlink` (required): The bitlink to expand

**Outputs:**
- `long_url`: The original long URL
- `result`: Success status

---

#### `list_bitlinks`
List bitlinks for a group.

**Inputs:**
- `group_guid` (optional): Group GUID (uses default group if not specified)
- `size` (optional): Number of results to return (default: 50, max: 100)
- `page` (optional): Page number for pagination
- `keyword` (optional): Search keyword to filter bitlinks
- `archived` (optional): Filter by archived status: 'on', 'off', or 'both'

**Outputs:**
- `bitlinks`: List of bitlinks
- `total`: Total number of bitlinks
- `page`: Current page number
- `size`: Number of results per page
- `next`: URL for next page of results
- `prev`: URL for previous page of results
- `result`: Success status

---

### Click Analytics (2 actions)

#### `get_clicks`
Get click counts for a bitlink by time unit.

**Inputs:**
- `bitlink` (required): The bitlink to get clicks for
- `unit` (optional): Time unit for grouping (minute, hour, day, week, month)
- `units` (optional): Number of time units to query (default: -1 for all)

**Outputs:**
- `clicks`: Array of click data by time unit
- `result`: Success status

---

#### `get_clicks_summary`
Get a summary of total clicks for a bitlink.

**Inputs:**
- `bitlink` (required): The bitlink to get clicks summary for
- `unit` (optional): Time unit for the summary period
- `units` (optional): Number of time units to include

**Outputs:**
- `total_clicks`: Total number of clicks
- `unit`: Time unit used
- `units`: Number of units queried
- `result`: Success status

---

### Groups & Organizations (3 actions)

#### `list_groups`
List all groups the user belongs to.

**Inputs:** None

**Outputs:**
- `groups`: List of groups
- `result`: Success status

---

#### `get_group`
Get information about a specific group.

**Inputs:**
- `group_guid` (required): The group GUID to retrieve

**Outputs:**
- `group`: Group details
- `result`: Success status

---

#### `list_organizations`
List all organizations the user belongs to.

**Inputs:** None

**Outputs:**
- `organizations`: List of organizations
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v4
- **Base URL**: `https://api-ssl.bitly.com/v4`
- **Authentication**: OAuth 2.0
- **Documentation**: https://dev.bitly.com/api-reference

## Important Notes

- **Bitlink Format**: Bitlinks can be provided as full URLs (https://bit.ly/abc123), domain/path (bit.ly/abc123), or just the path (abc123)
- **Custom Back-Half**: Creating custom back-halves may require a paid plan
- **Click Data Retention**: Data retention depends on your subscription level
- **Rate Limits**: 5 concurrent connections max; hourly limits vary by endpoint and plan

## Common Use Cases

**Marketing Automation:**
- Shorten URLs for social media campaigns
- Track link performance with click analytics
- Create branded links with custom back-halves

**Link Management:**
- Organize links with tags and titles
- Archive old links
- Expand shortened URLs to view original destinations

**Analytics & Reporting:**
- Monitor click trends over time
- Get click summaries for reporting
- Track link performance by time period

## Version History

- **1.0.0** - Initial release with 12 actions
  - User: get_user (1 action)
  - Links: shorten_url, create_bitlink, get_bitlink, update_bitlink, expand_bitlink, list_bitlinks (6 actions)
  - Analytics: get_clicks, get_clicks_summary (2 actions)
  - Groups/Orgs: list_groups, get_group, list_organizations (3 actions)

## Sources

- [Bitly API Reference](https://dev.bitly.com/api-reference)
- [Bitly Authentication](https://dev.bitly.com/docs/getting-started/authentication/)
- [Bitly Rate Limits](https://dev.bitly.com/docs/getting-started/rate-limits/)

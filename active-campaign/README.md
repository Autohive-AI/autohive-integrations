# ActiveCampaign Integration for Autohive

ActiveCampaign email marketing integration for tracking EDM campaign performance. Pull email campaign metrics, analyse open rates, click rates, and bounce rates, and explore contact-level engagement data to track and improve marketing performance over time.

## Key Features

- Pull all email campaigns with derived open rate, click rate, and bounce rate
- Drill into individual campaign performance and tracked link click counts
- List and search contacts with filtering by list, status, and creation date
- Retrieve per-contact activity history (opens, clicks, engagement events)
- List all contact lists and audience segments

## Setup & Authentication

ActiveCampaign uses API key authentication. Two values are required:

| Field | Description |
|-------|-------------|
| `api_key` | Your ActiveCampaign API key |
| `api_url` | Your full ActiveCampaign API URL (e.g. `https://mycompany.api-us1.com`) |

**Steps:**
1. Log in to your ActiveCampaign account
2. Go to **Settings → Developer**
3. Copy your **API Key**
4. Copy your **API URL** (shown on the same page, e.g. `https://mycompany.api-us1.com`)
5. Enter both values when connecting the integration in Autohive

## Actions

---

#### `list_campaigns`

List all email campaigns with performance metrics. Returns derived open rate, click rate, and bounce rate calculated from raw campaign data.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number of results per page (default: 20) |
| `offset` | integer | No | Pagination offset (default: 0) |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `campaigns` | array | List of campaign objects, each including `open_rate`, `click_rate`, `bounce_rate`, `sends`, `unsubscribes` |
| `total` | integer | Total number of campaigns matching the filter |

---

#### `get_campaign`

Retrieve full details and performance metrics for a single email campaign by ID.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | integer | Yes | The campaign ID to retrieve |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `campaign` | object | Full campaign object with all fields including `open_rate`, `click_rate`, `bounce_rate` |

---

#### `get_campaign_links`

Retrieve all tracked links in a campaign with click counts. Useful for understanding which content drove the most clicks.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | integer | Yes | The campaign ID to get tracked links for |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `links` | array | List of tracked link objects with URL and click counts |

---

#### `list_contacts`

List and search contacts with optional filters by email, list membership, status, and creation date.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | No | Filter by exact email address |
| `search` | string | No | Search by name, organisation, phone, or email |
| `listid` | string | No | Filter contacts by list ID |
| `status` | integer | No | Filter by contact status: 1=active, 2=unsubscribed, 3=bounced |
| `created_after` | string | No | Filter contacts created after this date (YYYY-MM-DD) |
| `created_before` | string | No | Filter contacts created before this date (YYYY-MM-DD) |
| `limit` | integer | No | Number of results (default: 20) |
| `offset` | integer | No | Pagination offset (default: 0) |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `contacts` | array | List of contact objects with id, email, name, and status fields |
| `total` | integer | Total number of contacts matching the filter |

---

#### `get_contact`

Retrieve a single contact by their ID including full profile and subscription data.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `contact_id` | integer | Yes | The contact ID to retrieve |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `contact` | object | Full contact object with profile, list memberships, and custom fields |

---

#### `list_contact_activities`

Get the activity history for a contact including email opens, link clicks, and other engagement events.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `contact_id` | integer | Yes | The contact ID to get activities for |
| `after` | string | No | Filter activities after this date (YYYY-MM-DD) |
| `include_emails` | boolean | No | Include full email data fields in the response (default: false) |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `activities` | array | List of activity records with timestamp, action type, and reference data |
| `total` | integer | Total number of activity records |

---

#### `list_lists`

Retrieve all contact lists in the ActiveCampaign account. Use list IDs to filter contacts by segment.

**Inputs**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number of results (default: 20) |
| `offset` | integer | No | Pagination offset (default: 0) |

**Outputs**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `lists` | array | List of contact list objects with id, name, and subscriber counts |
| `total` | integer | Total number of lists |

---

## Derived Metrics

`list_campaigns` and `get_campaign` calculate performance rates client-side from raw campaign data:

| Metric | Formula |
|--------|---------|
| `open_rate` | `unique_opens / sends × 100` |
| `click_rate` | `unique_link_clicks / sends × 100` |
| `bounce_rate` | `(hard_bounces + soft_bounces) / sends × 100` |

## EDM Performance Use Case

### Track overall EDM performance
Use `list_campaigns` with `status: 5` (completed) to pull all sent campaigns and compare `open_rate`, `click_rate`, and `bounce_rate` across sends over time.

### Drill into a specific campaign
Use `get_campaign` for full metrics on a send, then `get_campaign_links` to see which URLs were clicked and how many times.

### Identify disengaged contacts
Use `list_contacts` with `status: 2` (unsubscribed) or `status: 3` (bounced) to understand list churn, then `list_contact_activities` on specific contacts to review their engagement history.

### Segment-level analysis
Use `list_lists` to enumerate all audience segments, then `list_contacts` filtered by `listid` to understand how different audiences respond to different sends.

## Requirements

- `autohive-integrations-sdk~=2.0.0`
- `aiohttp~=3.9` (integration tests only)

## API Info

- **Base URL**: `https://{your-api-url}/api/3` (derived from your `api_url` field)
- **Auth**: Custom HTTP header `Api-Token: <your_key>`
- **API Docs**: [developers.activecampaign.com](https://developers.activecampaign.com/reference/overview)
- **API Version**: v3

## Rate Limiting

ActiveCampaign does not publicly document rate limits. Monitor for `429 Too Many Requests` responses and implement backoff if needed.

## Error Handling

| Error | Meaning |
|-------|---------|
| `HTTP 401` | Invalid or missing API key |
| `HTTP 403` | API key does not have permission for this resource |
| `HTTP 404` | Resource not found — check the ID or account name |
| `HTTP 422` | Invalid input — check required fields and data types |
| `HTTP 429` | Rate limit exceeded — back off and retry |

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `HTTP 401` on all requests | Invalid API key | Re-copy from Settings → Developer |
| `HTTP 404` on all requests | Wrong account name | Check your subdomain in the browser URL |
| Empty `campaigns[]` | No campaigns in the account yet | Check that campaigns have been created in ActiveCampaign |
| `open_rate` is 0 | Campaign has 0 sends | Expected for draft or scheduled campaigns |
| Activities return empty | No activity recorded yet | Normal for new contacts or accounts |

## Version History

| Version | Description |
|---------|-------------|
| `1.0.0` | Initial release — 7 actions covering email campaigns, contacts, and lists |

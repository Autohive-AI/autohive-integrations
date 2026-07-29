# LinkedIn Ads Integration

Integration with the LinkedIn Marketing API for managing ad accounts, campaigns, creatives, and analytics.

## Features

- **Ad Account Management**: Retrieve accessible ad accounts and users
- **Campaign Operations**: Create, read, update, pause, and activate campaigns
- **Campaign Groups**: Manage campaign groups
- **Creatives**: Retrieve ad creatives for campaigns
- **Analytics**: Pull performance metrics for campaigns

## Authentication

This integration uses OAuth 2.0 with the following scopes:
- `r_ads` - Read ad accounts and campaigns
- `r_ads_reporting` - Read campaign analytics
- `rw_ads` - Read/write access to ads

## Setup

1. Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps
2. Apply for Advertising API access under the Products tab
3. Configure OAuth redirect URLs
4. Use the Client ID and Client Secret for OAuth flow

## Actions

| Action | Description |
|--------|-------------|
| `get_ad_accounts` | List all accessible ad accounts |
| `get_campaigns` | List campaigns for an ad account |
| `get_campaign` | Get details of a specific campaign (requires `account_id`) |
| `create_campaign` | Create a new campaign |
| `update_campaign` | Update campaign settings (requires `account_id`) |
| `pause_campaign` | Pause an active campaign (requires `account_id`) |
| `activate_campaign` | Activate a paused campaign (requires `account_id`) |
| `get_campaign_groups` | List campaign groups |
| `get_creatives` | List creatives for an ad account (requires `account_id`, optional `campaign_id` filter) |
| `get_ad_analytics` | Get performance analytics |
| `get_ad_account_users` | List users with account access |

## API Version

This integration uses LinkedIn Marketing API version `202607`.

`202605` or newer is required: `appointmentsScheduled` (bookings) was added in
`202605` and older versions reject it with
`400 Projected field "appointmentsScheduled" not present in schema`.

### Account-scoped endpoints

LinkedIn's versioned Marketing API scopes campaign, campaign group, and creative
requests to an ad account — the account ID is part of the URL path
(`/rest/adAccounts/{accountId}/adCampaigns`, `.../adCampaignGroups`,
`.../creatives`). As a result, every action that targets a specific campaign or
creative requires an `account_id` input in addition to the entity identifier:
`get_campaign`, `update_campaign`, `pause_campaign`, `activate_campaign`, and
`get_creatives`. (`create_campaign` already required `account_id`.)

Reads that use finders (search, analytics, account-user lookups) rely on the
compact Rest.li query syntax (e.g. `accounts=List(urn:li:sponsoredAccount:1)` and
`dateRange=(start:(year:2026,month:1,day:1),...)`). The `( ) , :` characters in
these values are sent literally rather than percent-encoded, which the API
requires.

### Pagination

The list actions `get_campaigns`, `get_campaign_groups`, and `get_creatives`
use LinkedIn's cursor-based pagination (required from API version 202401). Pass
an optional `page_size` (default 25, max 100). To fetch the next page, pass the
`next_page_token` returned by the previous response as `page_token`. When
`next_page_token` is `null`, there are no more results.

### Analytics fields

Analytics requests only project fields that exist in the `AdAnalytics` v8 schema.
The always-requested base set is `impressions`, `clicks`, `costInLocalCurrency`,
`externalWebsiteConversions`. Derived metrics such as cost-per-click and
click-through-rate are not stored fields and must be computed by consumers from
these values.

**Lead Gen form metrics** (`include_leadgen_metrics`, default `true`) add
`oneClickLeadFormOpens`, `oneClickLeads`, `qualifiedLeads`,
`costPerQualifiedLead`, `appointmentsScheduled`, `viralOneClickLeadFormOpens`,
and `viralOneClickLeads`. `appointmentsScheduled` is what Campaign Manager
labels "bookings". The `viral*` variants count leads from organic reshares of a
sponsored post.

These are ordinary reporting fields — they need no scope beyond
`r_ads_reporting`, which is the only permission the
[reporting docs](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/ads-reporting)
list for `adAnalytics`. The separate `r_ads_leadgen_automation` scope is only
required for the Lead Sync API (`/leadFormResponses`), which returns the
submitted lead records themselves, and is not used by this integration.

**Reach and frequency** (`include_reach`, default `false`) add
`approximateMemberReach` and `audiencePenetration`, plus a derived `frequency`
(`impressions / reach`, rounded to 4dp; `null` when LinkedIn omits reach for a
row). LinkedIn only serves these when the field is named explicitly, the pivot
is non-demographic (this integration always pivots on `CAMPAIGN`), and the date
range is 92 days or less. Past 92 days it returns `200` with the fields
**silently absent** rather than an error, so the range is validated up front and
a longer range returns an action error instead. Off by default so longer
reporting windows keep working.

**Absent versus zero.** LinkedIn omits metrics it has no data for rather than
returning `0` — `qualifiedLeads`, `costPerQualifiedLead`, and the reach fields
are all routinely missing from rows. Consumers must treat every analytics key as
optional. `frequency` is `null` when reach is absent for that row.

LinkedIn caps the `fields` parameter at 20 metrics per request; the action
rejects anything over that before calling the API.

## Testing

Unit tests are mocked and run in CI:

```bash
pytest linkedin-ads/
```

Integration tests call the real LinkedIn Marketing API and are excluded from CI.
They require an OAuth2 access token (scopes `r_ads`, `r_ads_reporting`, `rw_ads`)
in `LINKEDIN_ADS_ACCESS_TOKEN`; set `LINKEDIN_ADS_TEST_ACCOUNT_ID` to pin a
specific account (otherwise the first accessible account is used). See the root
`.env.example`.

Read-only tests (safe — use this by default):

```bash
pytest linkedin-ads/tests/test_linkedin_ads_integration.py -m "integration and not destructive"
```

Destructive tests **create and mutate real campaigns** on the connected account
(create → update → pause → activate → archive; there is no delete-campaign
action). Run these deliberately, never in CI:

```bash
pytest linkedin-ads/tests/test_linkedin_ads_integration.py -m "integration and destructive"
```

## Resources

- [LinkedIn Marketing API Documentation](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Advertising API Quick Start](https://learn.microsoft.com/en-us/linkedin/marketing/quick-start)
- [Campaign Management](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaigns)

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

This integration uses LinkedIn Marketing API version `202601`.

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

### Analytics fields

Analytics requests only project fields that exist in the `AdAnalytics` v8 schema:
`impressions`, `clicks`, `costInLocalCurrency`, `externalWebsiteConversions`.
Derived metrics such as cost-per-click and click-through-rate are not stored
fields and must be computed by consumers from these values.

## Resources

- [LinkedIn Marketing API Documentation](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Advertising API Quick Start](https://learn.microsoft.com/en-us/linkedin/marketing/quick-start)
- [Campaign Management](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaigns)

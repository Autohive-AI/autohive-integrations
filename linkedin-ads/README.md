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
| `get_campaign` | Get details of a specific campaign |
| `create_campaign` | Create a new campaign |
| `update_campaign` | Update campaign settings |
| `pause_campaign` | Pause an active campaign |
| `activate_campaign` | Activate a paused campaign |
| `get_campaign_groups` | List campaign groups |
| `get_creatives` | List creatives for a campaign |
| `get_ad_analytics` | Get performance analytics |
| `get_ad_account_users` | List users with account access |

## API Version

This integration uses LinkedIn Marketing API version `202601`.

## Resources

- [LinkedIn Marketing API Documentation](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Advertising API Quick Start](https://learn.microsoft.com/en-us/linkedin/marketing/quick-start)
- [Campaign Management](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaigns)

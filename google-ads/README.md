# Google Ads Integration for Autohive

Google Ads is Google's online advertising platform. This integration provides comprehensive campaign, ad group, keyword, and reporting management via the Google Ads API.

## Setup & Authentication

- **Auth type**: OAuth2 platform (`google`)
- **Scopes**: `https://www.googleapis.com/auth/adwords`
- Authenticate via Autohive → Integrations → Google Ads → Connect.

## Actions

### Account
- `get_accessible_accounts` — List all Google Ads accounts accessible to the authenticated user

### Campaigns
- `create_campaign` — Create a new campaign with budget and bidding strategy
- `update_campaign` — Update campaign settings
- `remove_campaign` — Remove a campaign

### Ad Groups
- `create_ad_group` — Create a new ad group within a campaign
- `update_ad_group` — Update ad group settings
- `remove_ad_group` — Remove an ad group

### Ads
- `create_responsive_search_ad` — Create a responsive search ad with headlines and descriptions
- `update_ad` — Update an existing ad
- `remove_ad` — Remove an ad
- `get_active_ad_urls` — Retrieve URLs from active ads

### Keywords
- `add_keywords` — Add keywords to an ad group
- `update_keyword` — Update a keyword's match type or bid
- `remove_keyword` — Remove a keyword
- `add_negative_keywords_to_campaign` — Add negative keywords at campaign level
- `add_negative_keywords_to_ad_group` — Add negative keywords at ad group level

### Reporting & Metrics
- `retrieve_campaign_metrics` — Get campaign performance metrics
- `retrieve_ad_group_metrics` — Get ad group performance metrics
- `retrieve_ad_metrics` — Get ad-level performance metrics
- `retrieve_keyword_metrics` — Get keyword performance metrics
- `retrieve_search_terms` — Get search terms report

### Keyword Planner
- `generate_keyword_ideas` — Generate keyword ideas from seed keywords or URLs
- `generate_keyword_historical_metrics` — Get historical search volume and metrics
- `generate_keyword_forecast` — Forecast keyword performance with budget projections

## Requirements

- `autohive-integrations-sdk~=1.0.2`
- `google-ads`
- `grpcio`
- `grpcio-status`
- `protobuf`

## API Info

- **API**: Google Ads API
- **Docs**: [https://developers.google.com/google-ads/api/docs](https://developers.google.com/google-ads/api/docs)

## Rate Limiting

Google Ads API uses token-based rate limits per developer token tier. See [rate limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas).

## Error Handling

| Error | Cause |
|-------|-------|
| AuthenticationError | Invalid OAuth token — re-authenticate |
| QuotaError | Rate limit exceeded |
| RequestError | Invalid input parameters |

## Troubleshooting

**No accounts returned**: Ensure the authenticated user has access to at least one Google Ads account.

**QuotaError**: Reduce request frequency or upgrade your developer token.

## Version History

- **v1.0.0** — Initial release. 24 actions covering accounts, campaigns, ad groups, ads, keywords, reporting, and keyword planning.

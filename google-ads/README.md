# Google Ads Integration for Autohive

Connects Autohive to the Google Ads API to enable full campaign management, performance reporting, keyword planning, and ad automation.

## Description

This integration provides comprehensive access to the Google Ads API. It allows users to create and manage campaigns, ad groups, ads, and keywords, retrieve detailed performance metrics, and use Keyword Planner to research and forecast keyword opportunities — all directly from Autohive.

The integration uses the Google Ads API v18 with OAuth 2.0 authentication and implements 24 actions covering campaign management, ad group management, ad management, keyword management, performance reporting, and keyword planning.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication via the Google Ads platform provider.

### Authentication Method

The integration uses OAuth 2.0 with the following scope:
- `https://www.googleapis.com/auth/adwords` - Full access to Google Ads account data

### Setup Steps in Autohive

1. Add the Google Ads integration in Autohive
2. Click "Connect to Google Ads" to authorize the integration
3. Sign in to your Google account when prompted
4. Review and authorize the requested permissions
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh, so you don't need to manually manage access tokens.

### Account IDs

Most actions require two IDs:
- `login_customer_id`: Your Google Ads **Manager Account (MCC) ID** — the top-level account you log in with, without dashes (e.g., `1234567890`)
- `customer_id`: The **specific client account ID** you want to manage or query data from

## Actions

### Account (1 action)

#### `get_accessible_accounts`
Lists all Google Ads accounts accessible to the authenticated user via OAuth.

**Inputs:** None

**Outputs:**
- `accounts`: Array of accessible account objects (resource_name, customer_id, descriptive_name, currency_code)

---

### Campaigns (3 actions)

#### `create_campaign`
Creates a new Google Ads Search campaign with a budget. The campaign is created in PAUSED status by default.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `campaign_name` (required): Name for the new campaign
- `budget_amount_micros` (required): Daily budget in micros (e.g., 1000000 = $1.00)
- `budget_name` (optional): Name for the campaign budget
- `start_date` (optional): Campaign start date in YYYYMMDD format. Defaults to tomorrow
- `end_date` (optional): Campaign end date in YYYYMMDD format. Defaults to 1 year from now
- `bidding_strategy` (optional): Bidding strategy. Defaults to MANUAL_CPC
- `enhanced_cpc_enabled` (optional): For MANUAL_CPC — enable enhanced CPC. Defaults to false
- `target_spend_micros` (optional): For TARGET_SPEND — optional target spend in micros
- `target_cpa_micros` (optional): For MAXIMIZE_CONVERSIONS — optional target CPA in micros
- `cpc_bid_ceiling_micros` (optional): For MAXIMIZE_CLICKS — optional max CPC bid ceiling in micros
- `contains_eu_political_advertising` (optional): Whether the campaign contains EU political advertising content

---

#### `update_campaign`
Updates an existing campaign's status (ENABLED, PAUSED) or name.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `campaign_id` (required): The ID of the campaign to update
- `status` (optional): New status for the campaign (ENABLED or PAUSED)
- `name` (optional): New name for the campaign

---

#### `remove_campaign`
Removes (deletes) a campaign by setting its status to REMOVED.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `campaign_id` (required): The ID of the campaign to remove

---

### Ad Groups (4 actions)

#### `create_ad_group`
Creates a new ad group within an existing campaign.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `campaign_id` (required): The ID of the campaign to add the ad group to
- `ad_group_name` (required): Name for the new ad group
- `cpc_bid_micros` (optional): CPC bid in micros. Defaults to 1000000 ($1.00)
- `status` (optional): Status for the ad group. Defaults to PAUSED

---

#### `update_ad_group`
Updates an existing ad group's status, name, or CPC bid.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group to update
- `status` (optional): New status for the ad group
- `name` (optional): New name for the ad group
- `cpc_bid_micros` (optional): New CPC bid in micros

---

#### `remove_ad_group`
Removes (deletes) an ad group by setting its status to REMOVED.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group to remove

---

#### `add_negative_keywords_to_ad_group`
Adds negative keywords to an ad group to prevent ads from showing for specific search terms at the ad group level.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group to add negative keywords to
- `keywords` (required): List of negative keywords with their match types

---

### Ads (3 actions)

#### `create_responsive_search_ad`
Creates a new Responsive Search Ad (RSA) in an existing ad group with multiple headlines and descriptions.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group to add the ad to
- `headlines` (required): List of headlines (3–15 required, each max 30 characters)
- `descriptions` (required): List of descriptions (2–4 required, each max 90 characters)
- `final_url` (required): The landing page URL for the ad
- `path1` (optional): First path text in display URL (max 15 characters)
- `path2` (optional): Second path text in display URL (max 15 characters)
- `status` (optional): Status for the ad. Defaults to PAUSED

---

#### `update_ad`
Updates an ad's status (ENABLED or PAUSED).

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group containing the ad
- `ad_id` (required): The ID of the ad to update
- `status` (optional): New status for the ad (ENABLED or PAUSED)

---

#### `remove_ad`
Removes (deletes) an ad from an ad group.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group containing the ad
- `ad_id` (required): The ID of the ad to remove

---

### Keywords (5 actions)

#### `add_keywords`
Adds keywords to an existing ad group with specified match types.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group to add keywords to
- `keywords` (required): List of keywords with their match types

---

#### `update_keyword`
Updates a keyword's status or CPC bid.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group containing the keyword
- `criterion_id` (required): The criterion ID of the keyword to update
- `status` (optional): New status for the keyword
- `cpc_bid_micros` (optional): New CPC bid in micros

---

#### `remove_keyword`
Removes (deletes) a keyword from an ad group.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_id` (required): The ID of the ad group containing the keyword
- `criterion_id` (required): The criterion ID of the keyword to remove

---

#### `add_negative_keywords_to_campaign`
Adds negative keywords to a campaign to prevent ads from showing for specific search terms.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `campaign_id` (required): The ID of the campaign to add negative keywords to
- `keywords` (required): List of negative keywords with their match types

---

#### `get_active_ad_urls`
Retrieves all currently active (ENABLED) ads with their destination URLs.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `url_filter` (optional): Filter to only return ads containing this URL substring

---

### Performance Reporting (4 actions)

#### `retrieve_campaign_metrics`
Retrieves overall performance metrics for campaigns (clicks, cost, conversions per campaign).

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `date_ranges` (optional): List of date ranges. Formats: `YYYY-MM-DD_YYYY-MM-DD`, `last 7 days`, or `DD/MM/YYYY`
- `campaign_type` (optional): Filter by campaign type: SEARCH, VIDEO, DISPLAY, PERFORMANCE_MAX, or ALL (default)

---

#### `retrieve_ad_group_metrics`
Retrieves performance metrics for ad groups including impressions, clicks, cost, conversions, and CTR.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `date_ranges` (required): List of date ranges
- `campaign_ids` (optional): Filter by specific campaign IDs

---

#### `retrieve_ad_metrics`
Retrieves performance metrics for individual ads including impressions, clicks, cost, conversions, final URLs, and ad copy.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `date_ranges` (required): List of date ranges
- `campaign_ids` (optional): Filter by specific campaign IDs
- `ad_group_ids` (optional): Filter by specific ad group IDs

---

#### `retrieve_search_terms`
Retrieves the search terms that triggered your ads, including matched keyword, impressions, clicks, cost, and conversions.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `date_ranges` (required): List of date ranges
- `campaign_ids` (optional): Filter by specific campaign IDs
- `ad_group_ids` (optional): Filter by specific ad group IDs

---

### Keyword Planning (4 actions)

#### `retrieve_keyword_metrics`
Retrieves detailed performance metrics for keywords including match type, impressions, clicks, cost, conversions, and interaction rate.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `ad_group_ids` (required): List of ad group IDs to filter by
- `campaign_ids` (required): List of campaign IDs to filter by
- `date_ranges` (optional): List of date ranges

---

#### `generate_keyword_ideas`
Uses Keyword Planner to generate keyword ideas based on seed keywords and/or a URL. Returns search volume and competition data.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `seed_keywords` (optional): List of seed keywords to generate ideas from
- `page_url` (optional): URL to analyze for keyword ideas
- `language_id` (optional): Language ID (e.g., `1000` for English). Defaults to English
- `location_ids` (optional): List of geo target location IDs (e.g., `['2840']` for USA). Defaults to USA
- `include_adult_keywords` (optional): Whether to include adult keywords. Defaults to false

---

#### `generate_keyword_historical_metrics`
Retrieves historical metrics (search volume, competition, bid estimates) for specific keywords using the Keyword Planner.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `keywords` (required): List of keywords to get historical metrics for
- `language_id` (optional): Language ID. Defaults to English
- `location_ids` (optional): List of geo target location IDs. Defaults to USA

---

#### `generate_keyword_forecast`
Generates forecast metrics (impressions, clicks, cost) for keywords with specified budget and targeting settings.

**Inputs:**
- `login_customer_id` (required): Manager Account ID (MCC) without dashes
- `customer_id` (required): The Google Ads Customer ID
- `keywords` (required): List of keywords to forecast
- `daily_budget_micros` (optional): Daily budget in micros for Target Spend bidding strategy
- `max_cpc_bid_micros` (optional): Max CPC bid in micros for Manual CPC. Defaults to 1000000 ($1.00)
- `language_id` (optional): Language ID. Defaults to English
- `location_ids` (optional): List of geo target location IDs. Defaults to USA (`['2840']`)
- `forecast_days` (optional): Number of days to forecast. Defaults to 30

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK
- `google-ads==28.4.1` - Google Ads Python client library
- `grpcio>=1.56.2,<2.0.0dev` - gRPC runtime
- `grpcio-status>=1.56.2,<2.0.0dev` - gRPC status extensions
- `protobuf>=4.25.0,<7.0.0` - Protocol Buffers

## API Information

- **API Version**: Google Ads API v18
- **Base URL**: `https://googleads.googleapis.com`
- **Authentication**: OAuth 2.0 (platform-managed)
- **Documentation**: https://developers.google.com/google-ads/api/docs/start
- **Rate Limits**: Subject to Google Ads API quotas; see https://developers.google.com/google-ads/api/docs/best-practices/quotas

## Important Notes

- OAuth tokens are automatically managed by the Autohive platform
- Most actions require both a `login_customer_id` (MCC manager account) and a `customer_id` (target client account)
- Budget and bid amounts are in **micros** — divide by 1,000,000 to get the dollar value (e.g., 1000000 micros = $1.00)
- New campaigns, ad groups, and ads are created in **PAUSED** status by default for safety
- Use `remove_*` actions to delete resources — they set the status to REMOVED, which is permanent

## Testing

To test the integration:

1. Navigate to the integration directory: `cd google-ads`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OAuth credentials through the Autohive platform
4. Run tests: `python tests/test_google_ads.py`

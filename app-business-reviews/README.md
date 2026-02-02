# App and Business Reviews Integration

Unified Autohive integration for accessing reviews from Apple App Store, Google Play Store, and Google Maps using SerpAPI.

## Overview

This integration consolidates three separate review sources into a single, unified integration:
- **Apple App Store** - iOS app reviews
- **Google Play Store** - Android app reviews
- **Google Maps** - Business reviews

All sources are powered by [SerpAPI](https://serpapi.com/), requiring only a single API key.

## Features

### Apple App Store
- Search for iOS apps by name or developer
- Fetch app reviews with sorting options (most recent, helpful, favorable, critical)
- Automatic app ID resolution from app names
- Pagination support

### Google Play Store
- Search for Android apps by name
- Fetch app reviews with platform and rating filters
- Sort by relevance, newest, or rating
- Automatic app ID resolution from app names
- Pagination support

### Google Maps
- Search for businesses by name and location
- Fetch business reviews with sorting options
- Automatic place ID resolution from business names
- Pagination support

## Authentication

This integration uses custom authentication with a SerpAPI API key.

**Required Credentials:**
- `api_key`: Your SerpAPI API key (get one at https://serpapi.com/manage-api-key)

## Actions

### Apple App Store Actions

#### `search_apps_ios`
Search for iOS apps on Apple App Store.

**Inputs:**
- `term` (required): App name or search term
- `country` (optional): Country code (default: "us")
- `num` (optional): Number of results (1-200, default: 10)
- `property` (optional): Search by "developer" or leave empty for app names

**Outputs:**
- `apps`: Array of app objects with id, title, bundle_id, developer, rating, price, link
- `total_results`: Number of apps found

#### `get_reviews_app_store`
Fetch reviews for an iOS app.

**Inputs:**
- `product_id` (optional): App Store app ID (e.g., "534220544")
- `app_name` (optional): App name to auto-resolve ID
- `country` (optional): Country code (default: "us")
- `sort` (optional): Sort order - mostrecent, mosthelpful, mostfavorable, mostcritical (default: "mostrecent")
- `max_pages` (optional): Maximum pages to fetch (1-10, default: 3)

**Note:** Either `product_id` or `app_name` must be provided.

**Outputs:**
- `reviews`: Array of review objects
- `total_reviews`: Number of reviews fetched
- `app_name`: Name of the app
- `product_id`: App Store app ID

### Google Play Store Actions

#### `search_apps_android`
Search for Android apps on Google Play Store.

**Inputs:**
- `query` (required): App name or search term
- `limit` (optional): Maximum results (1-50, default: 10)

**Outputs:**
- `apps`: Array of app objects with product_id, title, developer, rating, price, thumbnail, link
- `total_results`: Number of apps found

#### `get_reviews_google_play`
Fetch reviews for an Android app.

**Inputs:**
- `product_id` (optional): Play Store app ID (e.g., "com.whatsapp")
- `app_name` (optional): App name to auto-resolve ID
- `rating` (optional): Filter by star rating (1-5)
- `platform` (optional): Filter by platform - phone, tablet, watch, chromebook, tv
- `sort_by` (optional): Sort order - 1 (Most relevant), 2 (Newest), 3 (Rating) (default: 1)
- `num_reviews` (optional): Reviews per page (1-199, default: 40)
- `max_pages` (optional): Maximum pages to fetch (1-10, default: 3)

**Note:** Either `product_id` or `app_name` must be provided.

**Outputs:**
- `reviews`: Array of review objects
- `total_reviews`: Number of reviews fetched
- `app_name`: Name of the app
- `app_rating`: Overall app rating
- `product_id`: Play Store app ID

### Google Maps Actions

#### `search_places_google_maps`
Search for businesses on Google Maps.

**Inputs:**
- `query` (required): Business name or search query
- `location` (optional): Location to search in (e.g., "New York, NY")
- `num_results` (optional): Number of results (1-20, default: 5)

**Outputs:**
- `places`: Array of place objects with place_id, data_id, title, address, rating, reviews, type, phone
- `total_results`: Number of places found

#### `get_reviews_google_maps`
Fetch reviews for a business from Google Maps.

**Inputs:**
- `place_id` (optional): Google Maps Place ID
- `data_id` (optional): Google Maps Data ID
- `query` (optional): Business name to auto-resolve IDs
- `location` (optional): Location to narrow search results
- `sort_by` (optional): Sort order - qualityScore, newestFirst, ratingHigh, ratingLow (default: "qualityScore")
- `num_reviews` (optional): Reviews per page (1-20, default: 10)
- `max_pages` (optional): Maximum pages to fetch (1-10, default: 5)

**Note:** Either `place_id`, `data_id`, or `query` must be provided.

**Outputs:**
- `reviews`: Array of review objects
- `total_reviews`: Number of reviews fetched
- `average_rating`: Average business rating
- `business_name`: Name of the business
- `place_id`: Google Maps Place ID

## Migration Guide

If you're migrating from the standalone integrations (`appstore_reviews`, `google_play_reviews`, `google_map_reviews`), here's the action mapping:

### From `appstore_reviews` → `serpapi`
- `search_apps` → `search_apps_ios`
- `get_app_reviews` → `get_reviews_app_store`

### From `google_play_reviews` → `serpapi`
- `search_apps` → `search_apps_android`
- `get_app_reviews` → `get_reviews_google_play`

### From `google_map_reviews` → `serpapi`
- `search_places` → `search_places_google_maps`
- `get_google_maps_reviews` → `get_reviews_google_maps`

**Key Changes:**
1. **Single API key**: Use the same SerpAPI key for all three sources
2. **Action names**: Updated to include platform identifiers (ios, android, google_maps)
3. **Identical functionality**: All parameters and outputs remain the same

## Usage Examples

### Example 1: Get iOS App Reviews
```python
# Search for the app
search_result = await serpapi.execute_action("search_apps_ios", {
    "term": "WhatsApp",
    "country": "us"
}, context)

# Get reviews using app ID
reviews_result = await serpapi.execute_action("get_reviews_app_store", {
    "product_id": "310633997",
    "country": "us",
    "sort": "mostrecent",
    "max_pages": 5
}, context)
```

### Example 2: Get Android App Reviews by Name
```python
# Automatically resolves app ID from name
reviews_result = await serpapi.execute_action("get_reviews_google_play", {
    "app_name": "WhatsApp",
    "rating": 5,
    "sort_by": 2,  # Newest first
    "max_pages": 3
}, context)
```

### Example 3: Get Google Maps Reviews by Business Name
```python
# Automatically resolves place ID from query
# IMPORTANT: Use simple business name only, not full address
reviews_result = await serpapi.execute_action("get_reviews_google_maps", {
    "query": "Starbucks Reserve Roastery",  # Just business name
    "location": "Seattle, WA",  # City and state/country
    "sort_by": "newestFirst",
    "num_reviews": 20,
    "max_pages": 5
}, context)
```

### Example 4: Get Google Maps Reviews by Place ID (Recommended)
```python
# Most reliable method - use place_id directly
reviews_result = await serpapi.execute_action("get_reviews_google_maps", {
    "place_id": "ChIJdwFEqNmvOG0RDdhA0UWZgiw",
    "sort_by": "newestFirst",
    "num_reviews": 10,
    "max_pages": 3
}, context)
```

## Best Practices

### Google Maps Reviews - Tips for Success

**✅ DO:**
- Use `place_id` directly when you have it (most reliable method)
- Keep business names simple: "Starbucks" not "Starbucks on Main Street"
- Separate business name and location into different parameters
- Use city and country format for location: "Wellington, New Zealand"
- Search for the place first using `search_places_google_maps` if you don't have the place_id

**❌ DON'T:**
- Don't include full street addresses in the query parameter
- Don't combine business name with location in a single string
- Don't use overly specific queries like "Restaurant on Cuba Street at Te Aro"

**Example of GOOD vs BAD queries:**

❌ BAD:
```python
{
    "query": "Yor Yak Thai Eatery on Cuba Street at Te Aro, Wellington"
}
```

✅ GOOD:
```python
{
    "query": "Yor Yak Thai Eatery",
    "location": "Wellington, New Zealand"
}
```

✅ BEST:
```python
{
    "place_id": "ChIJdwFEqNmvOG0RDdhA0UWZgiw"
}
```

## Error Handling

All actions include comprehensive error handling:
- Invalid API keys return authentication errors
- Missing required parameters raise `ValueError`
- App/business not found scenarios provide clear error messages with suggestions
- API rate limits are handled by SerpAPI

## Rate Limits

Rate limits are determined by your SerpAPI subscription plan. See [SerpAPI Pricing](https://serpapi.com/pricing) for details.

## Dependencies

- `autohive-integrations-sdk`: Core integration framework

## Support

For issues or questions:
- SerpAPI Documentation: https://serpapi.com/
- Autohive Integration Support: [Your support channel]

## Version History

### 1.0.0 (Initial Release)
- Unified integration for App Store, Play Store, and Google Maps
- Support for 6 actions across 3 platforms
- Automatic ID resolution from names
- Pagination support for all review actions
- Comprehensive filtering and sorting options

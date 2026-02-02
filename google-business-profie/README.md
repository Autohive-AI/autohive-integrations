# Google Business Profile Integration for Autohive

Connects Autohive to the Google My Business API to allow users to manage their Google Business Profile reviews and business information directly from their Autohive workflows.

## Description

This integration provides comprehensive Google Business Profile functionality, enabling users to access their business accounts, locations, and customer reviews. It supports reading reviews, replying to customers, and managing business profile interactions. The integration uses Google's platform authentication to securely access business profile data with appropriate permissions.

Key features:
- List all accessible Google Business Profile accounts
- View business locations with contact details
- Read customer reviews and ratings
- Reply to customer reviews professionally
- Delete review replies when needed

## Setup & Authentication

The integration uses Google's OAuth2 platform authentication. Users need to authenticate through Google's OAuth flow within Autohive to grant business profile access permissions.

**Authentication Type:** Platform (Google Maps Reviews)

**Required Scopes:**
- `https://www.googleapis.com/auth/business.manage` - Full access to Google Business Profile

No additional configuration fields are required as authentication is handled through Google's OAuth2 flow.

## Actions

### Action: `list_accounts`

- **Description:** Retrieve all Google Business Profile accounts accessible to the authenticated user
- **Inputs:** None required
- **Outputs:**
  - `accounts`: Array of account objects with name, account name, and type
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `list_locations`

- **Description:** List all business locations for a specific account
- **Inputs:**
  - `account_name`: Account resource name from list_accounts (e.g., 'accounts/12345')
- **Outputs:**
  - `locations`: Array of location objects with name, title, address, and phone number
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `list_reviews`

- **Description:** List all reviews for a specific business location
- **Inputs:**
  - `location_name`: Location resource name from list_locations (e.g., 'accounts/12345/locations/67890')
- **Outputs:**
  - `reviews`: Array of review objects with reviewer info, ratings, comments, and existing replies
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `reply_to_review`

- **Description:** Reply to a customer review on behalf of the business owner
- **Inputs:**
  - `review_name`: Full review resource name (e.g., 'accounts/12345/locations/67890/reviews/abc123')
  - `reply_comment`: The reply message to post
- **Outputs:**
  - `reviewReply`: Object containing the posted comment and timestamp
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `delete_review_reply`

- **Description:** Delete a previously posted reply to a review
- **Inputs:**
  - `review_name`: Full review resource name (e.g., 'accounts/12345/locations/67890/reviews/abc123')
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

## Requirements

- Python dependencies are handled by the Autohive platform
- Google My Business API access
- Valid Google Business Profile with business locations
- Business owner or manager permissions

## Usage Examples

**Example 1: Reply to a customer review**

```json
{
  "review_name": "accounts/12345/locations/67890/reviews/abc123",
  "reply_comment": "Thank you for your feedback! We're glad you had a great experience with our service."
}
```

**Example 2: List all reviews for a location**

```json
{
  "location_name": "accounts/12345/locations/67890"
}
```

**Example 3: Get business locations**

```json
{
  "account_name": "accounts/12345"
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd google_mpas_official_reviews`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run the tests: `python tests/test_integration.py`

## Notes

- Reviews are returned in pages with Google's default pagination limits (typically 20-50 reviews per request)
- This integration does not implement pagination, so it returns the most recent reviews only
- Star ratings are returned as enum values: ONE, TWO, THREE, FOUR, FIVE
- Review replies can be updated or deleted after posting
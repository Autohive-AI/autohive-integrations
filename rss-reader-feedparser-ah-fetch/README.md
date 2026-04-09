# RSS Reader Integration for Autohive using feedparser and autohive-integration-sdk's .fetch()

This integration allows Autohive to connect with RSS feeds, enabling users to fetch and process feed entries from any RSS-compatible source.

## Description

The RSS Reader integration provides a simple way to access and process RSS feed content within Autohive workflows. It uses autohive-integration-sdk to manage HTTP calls to RSS feed URLs and  the feedparser library to parse RSS feeds and extract relevant information such as titles, links, descriptions, and publication dates. This integration is particularly useful for monitoring news sources, blogs, or any other RSS-enabled content.

## Setup & Authentication

While most public RSS feeds don't require authentication, some private or protected feeds may need username and password credentials.

The integration supports HTTP Basic Authentication (if `user_name` and `password` are provided), authentication via a token/API key as Bearer token (if `api_token` is provided) or can simply be used without any authentication. 

**Authentication Fields:**

*   `user_name`: Username for the RSS feed (if authentication is required)
*   `password`: Password for the RSS feed (if authentication is required)
*   `api_token`: Bearer token for RSS feed (if authentication is required)

## Actions

### Action: `get_feed`

*   **Description:** Retrieves entries from a specified RSS feed URL
*   **Inputs:**
    *   `feed_url`: The URL of the RSS feed to read (required)
    *   `limit`: Maximum number of entries to return (optional, defaults to 10)
*   **Outputs:**
    *   `feed_title`: Title of the RSS feed
    *   `feed_link`: Link to the RSS feed
    *   `entries`: Array of feed entries, each containing:
        *   `title`: Entry title
        *   `link`: Link to entry
        *   `description`: The description of the entry
        *   `published`: Published date
        *   `author`: Author

## Requirements

*   `feedparser`
*   `autohive_integrations_sdk`

## Usage Examples

**Example 1: Fetch latest news from a blog**

Inputs:

```json
{
  "feed_url": "https://example.com/blog/feed.xml",
  "limit": 5
}
```

**Example 2: Fetch data from a news source with authentication**

Inputs:

```json
{
  "feed_url": "https://private-news.com/feed",
  "limit": 20
}
```
Auth:

```json
{
  "auth": {
    "user_name": "your_username",
    "password": "your_password"
  }
}
```

## Testing

To run the tests:

1.  Navigate to the integration's directory: `cd rss-reader-feedparser-ah-fetch`
2.  Install dependencies: `pip install -r requirements.txt -t dependencies`
3.  Run the tests: `python tests/test_rss_reader.py` 

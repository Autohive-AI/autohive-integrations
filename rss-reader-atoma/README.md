# RSS Reader Integration for Autohive using Atoma

> ⚠️ **Status: Unsupported**
>
> This integration is **no longer supported or maintained** by the Autohive team. It is kept in the repository for reference only and is not covered by routine bug-fix updates. Use [`rss-reader-atoma-ah-fetch`](../rss-reader-atoma-ah-fetch) for maintained RSS/Atom feed workflows that route HTTP requests through the Autohive SDK `context.fetch` layer.

This integration allows Autohive to connect with RSS and Atom feeds, enabling users to fetch and process feed entries from compatible sources.

## Description

The RSS Reader integration uses the [`atoma`](https://pypi.org/project/atoma/) library to parse RSS/Atom feed payloads and extract common information such as titles, links, descriptions, publication dates, and authors. It fetches feed URLs directly with Python's standard library, which is why the maintained SDK-fetch variant is preferred for production workflows.

Using `atoma` avoids the `feedparser` → `sgmllib3k` dependency chain that cannot be installed by `hiveup package` under its binary-only dependency policy.

## Setup & Authentication

Most public RSS and Atom feeds do not require authentication. This legacy integration supports optional HTTP Basic Authentication when `user_name` and `password` are provided.

**Authentication Fields:**

- `user_name`: Username for the feed, if required
- `password`: Password for the feed, if required

## Actions

### Action: `get_feed`

- **Description:** Retrieves entries from a specified RSS or Atom feed URL
- **Inputs:**
  - `feed_url`: The URL of the feed to read (required)
  - `limit`: Maximum number of entries to return (optional, defaults to 10)
- **Outputs:**
  - `feed_title`: Title of the feed
  - `feed_link`: Link to the feed
  - `entries`: Array of feed entries, each containing:
    - `title`: Entry title
    - `link`: Link to entry
    - `description`: Entry description or summary
    - `published`: Parsed publication/update date as an ISO string when available
    - `author`: Entry author when available

## Requirements

- `atoma`
- `autohive-integrations-sdk`

## Usage Examples

**Example 1: Fetch latest posts from a public blog**

```json
{
  "feed_url": "https://example.com/blog/feed.xml",
  "limit": 5
}
```

**Example 2: Fetch a feed with HTTP Basic Authentication**

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
  "auth_type": "Custom",
  "credentials": {
    "user_name": "your_username",
    "password": "your_password"
  }
}
```

## Testing

Run unit tests:

```bash
pytest rss-reader-atoma/tests/test_rss_reader_unit.py -m unit
```

Run read-only end-to-end integration tests against a real public feed:

```bash
pytest rss-reader-atoma/tests/test_rss_reader_integration.py -m "integration and not destructive"
```

The integration tests default to `https://xkcd.com/rss.xml`. Set `RSS_READER_TEST_FEED_URL` in the root `.env` file to test a different public feed.

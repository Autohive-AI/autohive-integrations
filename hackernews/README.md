# Hacker News Integration for Autohive

Read-only integration with the official Hacker News API for fetching tech news, discussions, and community content. Optimized for LLM agents to create curated daily reports.

## Description

This integration provides read-only access to Hacker News content through the official Firebase-hosted API. It enables agents to:

- Fetch top, best, and new stories from the front page
- Access Ask HN discussions and Show HN project showcases
- Retrieve job postings from YC companies
- Get story details with threaded comment discussions
- Look up user profiles and karma

Designed specifically for LLM agents that need to monitor tech news, create curated digests, or analyze community discussions. All responses include ISO timestamps and pre-computed HN URLs for easy reference.

## Setup & Authentication

**No authentication required.** The Hacker News API is public with no rate limits.

**Authentication Fields:**

*   None - this is a public API

## Actions

### Action: `get_top_stories`

*   **Description:** Fetches the current top stories from the Hacker News front page, sorted by ranking.
*   **Inputs:**
    *   `limit` (optional): Maximum number of stories to return (1-100, default: 30)
*   **Outputs:**
    *   `stories`: Array of story objects with id, title, url, hn_url, score, by, time, descendants, type
    *   `fetched_at`: ISO timestamp when data was fetched
    *   `count`: Number of stories returned

### Action: `get_best_stories`

*   **Description:** Fetches the highest-voted stories over time (evergreen high-quality content).
*   **Inputs:**
    *   `limit` (optional): Maximum number of stories to return (1-100, default: 30)
*   **Outputs:**
    *   `stories`: Array of story objects
    *   `fetched_at`: ISO timestamp
    *   `count`: Number of stories returned

### Action: `get_new_stories`

*   **Description:** Fetches the newest submissions to Hacker News, sorted by submission time.
*   **Inputs:**
    *   `limit` (optional): Maximum number of stories to return (1-100, default: 30)
*   **Outputs:**
    *   `stories`: Array of story objects
    *   `fetched_at`: ISO timestamp
    *   `count`: Number of stories returned

### Action: `get_ask_hn_stories`

*   **Description:** Fetches "Ask HN" posts where users ask the community questions.
*   **Inputs:**
    *   `limit` (optional): Maximum number of stories to return (1-100, default: 30)
*   **Outputs:**
    *   `stories`: Array of Ask HN posts with question text content
    *   `fetched_at`: ISO timestamp
    *   `count`: Number of stories returned

### Action: `get_show_hn_stories`

*   **Description:** Fetches "Show HN" posts showcasing user projects and creations.
*   **Inputs:**
    *   `limit` (optional): Maximum number of stories to return (1-100, default: 30)
*   **Outputs:**
    *   `stories`: Array of Show HN posts with project URLs
    *   `fetched_at`: ISO timestamp
    *   `count`: Number of stories returned

### Action: `get_job_stories`

*   **Description:** Fetches job postings, typically from YC companies and tech startups.
*   **Inputs:**
    *   `limit` (optional): Maximum number of jobs to return (1-100, default: 30)
*   **Outputs:**
    *   `jobs`: Array of job postings with title, url, text, by, time
    *   `fetched_at`: ISO timestamp
    *   `count`: Number of jobs returned

### Action: `get_story_with_comments`

*   **Description:** Fetches a single story with its threaded comment discussion.
*   **Inputs:**
    *   `story_id` (required): The Hacker News story ID
    *   `comment_limit` (optional): Maximum top-level comments to fetch (1-50, default: 20)
    *   `comment_depth` (optional): How many levels deep to fetch replies (1-5, default: 2)
*   **Outputs:**
    *   `story`: Full story details (id, title, url, score, by, time, descendants)
    *   `comments`: Threaded comment tree with nested replies
    *   `fetched_at`: ISO timestamp

### Action: `get_user_profile`

*   **Description:** Fetches a Hacker News user's public profile.
*   **Inputs:**
    *   `username` (required): Hacker News username (case-sensitive)
*   **Outputs:**
    *   `id`: Username
    *   `karma`: User's karma score
    *   `created`: Account creation date (ISO timestamp)
    *   `about`: User's self-description (HTML, if set)
    *   `profile_url`: Link to HN profile

## Requirements

*   `autohive-integrations-sdk`
*   `aiohttp>=3.9.0`

## Usage Examples

**Example 1: Get today's top 10 stories for a daily digest**

```json
{
  "limit": 10
}
```

**Example 2: Fetch a trending story with community discussion**

```json
{
  "story_id": 12345678,
  "comment_limit": 30,
  "comment_depth": 3
}
```

**Example 3: Discover new projects from Show HN**

```json
{
  "limit": 20
}
```

## Testing

To run the tests:

1.  Navigate to the integration's directory: `cd hackernews`
2.  Install dependencies: `pip install -r requirements.txt -t dependencies`
3.  Run the tests: `python tests/test_hackernews.py`

## License

The Hacker News API is public and provided under the MIT license with no rate limits. See the [official API documentation](https://github.com/HackerNews/API) for details.

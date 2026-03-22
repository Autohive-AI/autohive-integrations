# Substack

Search Substack publications, read posts and comments. No authentication required.

> **Note:** Substack has no official public API. This integration uses internal endpoints that are widely used but undocumented and subject to change.

## Authentication

None required. All actions use Substack's public APIs.

## Actions

| Action | Description |
|---|---|
| `get_publication_posts` | List posts from a publication archive |
| `get_post` | Get full post content by slug |
| `search_publications` | Search publications across Substack |
| `search_posts` | Search posts within a publication by keyword |
| `get_post_comments` | Get comments on a post |

## Notes

- `get_post_comments` requires the numeric `post_id` (from `get_publication_posts`), not the slug
- Paywalled post `body_html` is truncated for non-subscribers

# Substack

Read Substack publications, posts, comments, and your personal subscriptions and reader feed.

> **Note:** Substack has no official public API. This integration uses internal endpoints that are widely used but undocumented and subject to change. Personal/automation use is low risk; commercial use should review Substack's ToS.

## Authentication

Authentication is optional — public actions work without credentials. To access your subscriptions and reader feed, provide session cookies from your browser:

1. Log in to [substack.com](https://substack.com) in your browser
2. Open DevTools → Application → Cookies → `substack.com`
3. Copy the values of `connect.sid` and `substack.sid`

> Cookies are invalidated when you log out. Consider using a dedicated account for automation.

## Actions

| Action | Auth Required | Description |
|---|---|---|
| `get_publication_posts` | No | List posts from a publication archive |
| `get_post` | No | Get full post content by slug |
| `get_publication_info` | No | Get publication metadata |
| `search_publications` | No | Search publications across Substack |
| `search_posts` | No | Search posts within a publication |
| `get_post_comments` | No | Get comments on a post |
| `get_subscriptions` | Yes | List your subscriptions |
| `get_reader_feed` | Yes | Get your reader activity feed |

## Notes

- Paywalled post `body_html` is truncated without a paid subscriber session
- `get_post_comments` requires the numeric `post_id` (from `get_publication_posts`), not the slug
- `get_subscriptions` and `get_reader_feed` make two HTTP requests per invocation to resolve your user ID

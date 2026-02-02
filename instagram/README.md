# Instagram Integration

Instagram Business/Creator integration for Autohive, providing comprehensive management of posts, comments, and insights via the Instagram Graph API.

## Features

- **Connected Account**: Displays authorized user's profile info (username, name, avatar)
- **Post Publishing**: Create images, videos, reels, carousels, and stories
- **Comment Moderation**: Read, reply, hide/unhide, and delete comments
- **Insights & Analytics**: Account and post performance metrics

## Requirements

- Instagram Business or Creator account

## Permissions

This integration uses **Business Login for Instagram** (users log in with Instagram credentials):

| Permission | Purpose |
|------------|---------|
| `instagram_business_basic` | Read account profile and posts |
| `instagram_business_content_publish` | Publish posts, reels, stories |
| `instagram_business_manage_comments` | Read/reply/hide/delete comments |
| `instagram_business_manage_insights` | Access analytics and metrics |

## Actions

| Action | Description |
|--------|-------------|
| `get_account` | Get Instagram Business/Creator account details |
| `get_posts` | Retrieve posts (images, videos, reels, carousels) |
| `create_post` | Publish images, videos, reels, or carousels |
| `create_story` | Publish a story (24hr lifespan) |
| `get_comments` | Get comments on a post |
| `manage_comment` | Reply, hide, or unhide comments |
| `delete_comment` | Delete a comment |
| `get_insights` | Get account or post analytics |

## Pagination

The `get_posts` and `get_comments` actions support cursor-based pagination for accessing large datasets:

1. Make an initial request with a `limit` (default 25, max 100)
2. If more results exist, the response includes a `next_cursor`
3. Pass `after_cursor` in subsequent requests to fetch the next page

```
# First request
{ "limit": 25 }
# Response includes: { "media": [...], "next_cursor": "abc123" }

# Next page
{ "limit": 25, "after_cursor": "abc123" }
```

## Rate Limits

- **Content Publishing**: 100 posts per 24 hours (carousels count as 1)
- **API Calls**: Scales with account reach — `4800 × impressions in last 24hrs`. For example, an account with 1,000 impressions gets 4.8M API calls/day. Minimum floor of 48,000 calls/day for small accounts.

## Limitations

- Media must be hosted on a publicly accessible URL for publishing
- Stories are only available for 24 hours; insights expire after 24hrs
- Carousel posts require 2-10 items
- Video processing may take time before publishing completes

## API Version

This integration uses Instagram Graph API **v24.0**.

## Links

- [Instagram Platform Documentation](https://developers.facebook.com/docs/instagram-platform/)
- [Instagram API Reference](https://developers.facebook.com/docs/instagram-platform/reference)
- [Content Publishing Guide](https://developers.facebook.com/docs/instagram-platform/content-publishing/)

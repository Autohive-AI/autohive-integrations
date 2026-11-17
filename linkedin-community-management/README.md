# LinkedIn Community Management

Autohive integration for LinkedIn's **Community Management API product**. It manages member and organization content, conversations, follower discovery, and organic analytics. It does not use LinkedIn Ads, Lead Sync, Events, OpenID Connect, or other LinkedIn API products.

The integration sends `LinkedIn-Version: 202610` and `X-Restli-Protocol-Version: 2.0.0` on versioned requests.

## Capabilities

- Retrieve the authenticated member's basic profile and first-degree connection count.
- Discover organization pages managed by the authenticated member.
- Retrieve, create, update, delete, and reshare member or organization posts.
- Retrieve, create, update, and delete comments and replies.
- Retrieve, add, and remove reactions.
- Retrieve social metadata and open or close a post's comments.
- Find organization followers for `@mention` workflows.
- Retrieve organization follower and organic post statistics.
- Retrieve member post and follower analytics.

## Authentication and access

Authentication uses Autohive platform OAuth with the dedicated provider `linkedin-community-management`. The LinkedIn developer application must be approved for the Community Management product. Some capabilities, including People Typeahead, are restricted by LinkedIn and may require Standard tier or additional approval even when the scope is present.

The configured scopes are exactly:

- `r_member_postAnalytics`
- `r_organization_followers`
- `r_organization_social`
- `rw_organization_admin`
- `r_organization_social_feed`
- `w_member_social`
- `r_member_profileAnalytics`
- `w_organization_social`
- `r_basicprofile`
- `w_organization_social_feed`
- `w_member_social_feed`
- `r_1st_connections_size`

LinkedIn restricts organization operations to pages where the authenticated member has an eligible role. Member-feed write operations act only as the authenticated member.

## Actions

### Identity and page access

- `get_profile` — retrieve the authenticated member's basic profile.
- `get_connection_count` — retrieve the authenticated member's first-degree connection count.
- `list_managed_organizations` — list the member's organization roles, optionally filtered by role and state.

### Posts

- `get_post` — retrieve a share or UGC post by URN.
- `list_posts` — list posts for an organization or member author.
- `create_post` — publish a text post as a member or organization.
- `share_article` — publish an article post as a member or organization.
- `reshare_post` — reshare an existing post.
- `update_post` — replace a post's commentary.
- `delete_post` — delete a post.

For member actions, omit `author`/`actor` to use the authenticated member. For an organization, pass either its full URN or its bare ID with `actor_type: "ORGANIZATION"`.

### Community conversations

- `list_comments`, `create_comment`, `update_comment`, `delete_comment`
- `list_reactions`, `create_reaction`, `delete_reaction`
- `get_social_metadata` — retrieve comments state and comment/reaction totals.
- `set_comments_state` — set comments to `OPEN` or `CLOSED`.

**LinkedIn permanently deletes existing comments when a thread is changed to `CLOSED`.** Reopening the thread does not restore them.

### Followers and analytics

- `search_organization_followers` — find page followers for mention workflows.
- `get_organization_follower_statistics` — retrieve lifetime demographic or time-bound follower statistics.
- `get_organization_post_statistics` — retrieve organic aggregate or per-post page statistics. LinkedIn limits this endpoint to a rolling 12-month window.
- `get_member_post_analytics` — retrieve a selected metric for a post or all authenticated-member posts.
- `get_member_follower_statistics` — retrieve lifetime or daily authenticated-member follower counts.

Member analytics are best-effort reporting data and should not be used for billing. Organization post statistics are organic only; sponsored reporting belongs to the Ads API and is intentionally outside this integration.

## Tests and validation

Run mocked tests and repository checks from the repository root:

```bash
.venv/bin/pytest linkedin-community-management/ -v
.venv/bin/python ../autohive-integrations-tooling/scripts/validate_integration.py linkedin-community-management
.venv/bin/python ../autohive-integrations-tooling/scripts/check_code.py linkedin-community-management
```

Optional read-only live tests use `LINKEDIN_COMMUNITY_ACCESS_TOKEN`:

```bash
.venv/bin/pytest linkedin-community-management/tests/test_linkedin_community_management_integration.py -m integration
```

## Official LinkedIn documentation

- [Community Management overview](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview)
- [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
- [Comments API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api)
- [Reactions API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/reactions-api)
- [Social Metadata API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/social-metadata-api)
- [Organization follower statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/follower-statistics)
- [Organization share statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/share-statistics)
- [Member post statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/post-statistics)
- [Member follower statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/follower-statistics)
- [Connections Size API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/connections-size)

# LinkedIn Integration

LinkedIn integration for Autohive. Share content, manage posts, and access user profile information through a unified interface.

## Features

| Category | Capabilities |
|----------|-------------|
| **Profile** | Retrieve authenticated user profile via OpenID Connect |
| **Posts** | Create text, article, image, multi-image, and reshare posts |
| **Post Management** | Update and delete existing LinkedIn posts |

## Actions

### Profile

#### `get_user_info`
Retrieve profile information for the authenticated LinkedIn user using OpenID Connect.

**Outputs:**

| Field | Description |
|-------|-------------|
| `sub` | Subject identifier - unique LinkedIn user ID |
| `name` | Full name of the user |
| `given_name` | First name |
| `family_name` | Last name |
| `picture` | Profile picture URL |
| `locale` | User's locale object with `country` and `language` |
| `email` | Email address (if email scope granted) |
| `email_verified` | Whether email has been verified |

---

### Posts

#### `create_post`
Create a LinkedIn post as the authenticated user.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `text` | No | The text content/commentary to share. Optional when images are provided |
| `file` | No | Single image file object |
| `files` | No | Image file objects for multi-image posts, up to 20 |
| `visibility` | No | `PUBLIC` (default) or `CONNECTIONS` |
| `author_id` | No | LinkedIn user ID (sub). If omitted, uses authenticated user |
| `disable_reshare` | No | Prevent others from resharing this post |

**Outputs:**

| Field | Description |
|-------|-------------|
| `result` | Status message |
| `post_id` | URN of created post (e.g., `urn:li:share:123456`) |
| `post_url` | Browser permalink using LinkedIn's feed activity URN format |
| `images_uploaded` | Number of images uploaded |

#### `share_article`
Create a LinkedIn article/link post with commentary, title, description, and URL.

#### `reshare_post`
Reshare an existing LinkedIn post with optional commentary.

LinkedIn can return `403 FORBIDDEN` for reshares even when create/update/delete work. This indicates the connected LinkedIn Developer App, product approval, member token, or source post permissions do not allow the reshare/repost operation. Re-authorize the connection after any Developer App permission changes so the token includes the new access.

#### `update_post`
Update the commentary/text of an existing post. The post URN is sent as a pre-encoded Rest.li path segment, e.g. `urn%3Ali%3Ashare%3A123456`.

#### `delete_post`
Delete an existing post. The post URN is sent as a pre-encoded Rest.li path segment, e.g. `urn%3Ali%3Ashare%3A123456`.

#### `reshare_post`
Reshare an existing public LinkedIn post with optional commentary.

LinkedIn returns `403 FORBIDDEN` when the source post is not publicly accessible, including connections-only posts. Create the source post with `PUBLIC` visibility before resharing it.

---

## Required Permissions

This integration requires the following LinkedIn OAuth scopes:

| Scope | Purpose |
|-------|---------|
| `openid` | OpenID Connect authentication |
| `profile` | Access user profile information |
| `email` | Access user email address |
| `w_member_social` | Post content on behalf of user |

---

## Project Structure

```
linkedin/
├── linkedin.py          # Entry point with action handlers
├── config.json          # Integration configuration & schemas
├── icon.png             # LinkedIn logo
├── requirements.txt     # SDK dependency
└── tests/
    ├── __init__.py
    ├── test_linkedin_unit.py
    └── test_linkedin_integration.py
```

## Running Tests

```bash
pytest linkedin/tests/test_linkedin_unit.py -v
```

Integration tests call the real LinkedIn API and require `LINKEDIN_ACCESS_TOKEN`.

```bash
pytest linkedin/tests/test_linkedin_integration.py -m "integration and not destructive"
```

Destructive integration tests create, update, and delete real LinkedIn posts:

```bash
pytest linkedin/tests/test_linkedin_integration.py -m "integration and destructive"
```

The live reshare integration test is opt-in because LinkedIn commonly returns `403 FORBIDDEN` unless the connected Developer App/member token has approved reshare access:

```bash
LINKEDIN_RUN_RESHARE_INTEGRATION=1 pytest linkedin/tests/test_linkedin_integration.py -m "integration and destructive"
```

**Test Coverage:**
- `get_user_info` - Success, without email, error handling
- `create_post` - Text posts, image posts, visibility, explicit author, validation
- `share_article` and `reshare_post` - Payload shape and provider error handling
- `update_post` and `delete_post` - Rest.li method headers and pre-encoded post URN paths

---

## API Documentation

This integration uses:
- **Posts API**: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- **OpenID Connect**: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2

### API Headers

All Posts API requests include:
```
LinkedIn-Version: 202601
X-Restli-Protocol-Version: 2.0.0
Content-Type: application/json
```

---

## API Version

This integration uses:
- LinkedIn Posts API (REST) with versioned headers `202601`
- LinkedIn OpenID Connect userinfo endpoint

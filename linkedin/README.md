# LinkedIn Integration

LinkedIn integration for Autohive. Share content and access user profile information through a unified interface.

## Features

| Category | Capabilities |
|----------|-------------|
| **Profile** | Retrieve authenticated user profile via OpenID Connect |
| **Posts** | Share text content to LinkedIn feed |

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

#### `share_content`
Share a text post on LinkedIn as the authenticated user.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `content` | Yes | The text content/commentary to share |
| `visibility` | No | `PUBLIC` (default) or `CONNECTIONS` |
| `author_id` | No | LinkedIn user ID (sub). If omitted, uses authenticated user |

**Outputs:**

| Field | Description |
|-------|-------------|
| `result` | Status message |
| `post_id` | URN of created post (e.g., `urn:li:share:123456`) |
| `post_data` | Full post data from LinkedIn API |

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
    ├── context.py       # Test import configuration
    └── test_linkedin.py # Comprehensive test suite (11 tests)
```

## Running Tests

```bash
cd linkedin/tests
pytest test_linkedin.py -v
```

**Test Coverage:**
- `get_user_info` - Success, without email, error handling
- `share_content` - Success, explicit author, visibility options, headers validation, payload structure, input validation

---

## API Documentation

This integration uses:
- **Posts API**: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- **OpenID Connect**: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2

### API Headers

All Posts API requests include:
```
LinkedIn-Version: 202501
X-Restli-Protocol-Version: 2.0.0
Content-Type: application/json
```

---

## API Version

This integration uses:
- LinkedIn Posts API (REST) with versioned headers
- LinkedIn OpenID Connect userinfo endpoint

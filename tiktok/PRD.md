# TikTok Integration PRD

## Product Requirements Document

**Integration Name:** TikTok
**Version:** 1.0.0
**Author:** Autohive Team
**Date:** 2025-01-23
**Status:** Draft

---

## 1. Overview

TikTok integration for Autohive, enabling video content posting, user profile management, and analytics via the official TikTok Content Posting API and User Info API.

### 1.1 Objective

Enable Autohive users to:
- Post videos directly to TikTok or as drafts
- Manage video content with captions, hashtags, and privacy settings
- Access user profile information and statistics
- Monitor post status and performance

### 1.2 Target Users

- Social media managers
- Content creators
- Marketing teams
- Businesses with TikTok presence

---

## 2. TikTok API Overview

### 2.1 API Products Required

| API Product | Purpose |
|-------------|---------|
| **Login Kit** | OAuth 2.0 user authentication |
| **Content Posting API** | Video upload and publishing |
| **User Info API** | Profile data and statistics |

### 2.2 Base URLs

| Environment | URL |
|-------------|-----|
| API Base | `https://open.tiktokapis.com` |
| OAuth | `https://www.tiktok.com/v2/auth/authorize/` |
| Token | `https://open.tiktokapis.com/v2/oauth/token/` |

---

## 3. Authentication

### 3.1 OAuth 2.0 Flow

```
1. User clicks "Connect TikTok"
2. Redirect to TikTok authorization URL
3. User grants permissions
4. TikTok redirects back with authorization code
5. Exchange code for access_token + refresh_token
6. Store tokens securely
```

### 3.2 Token Management

| Token Type | Expiry | Action |
|------------|--------|--------|
| Access Token | 24 hours | Auto-refresh before expiry |
| Refresh Token | 1 year | Prompt re-authentication before expiry |

### 3.3 Token Endpoints

```
POST /v2/oauth/token/
- grant_type: authorization_code | refresh_token
- client_key: <app_client_key>
- client_secret: <app_client_secret>
- code: <authorization_code>  (for initial auth)
- refresh_token: <token>  (for refresh)
- redirect_uri: <callback_url>

POST /v2/oauth/revoke/
- client_key: <app_client_key>
- client_secret: <app_client_secret>
- token: <access_token>
```

---

## 4. Required Scopes

| Scope | Purpose | Required For |
|-------|---------|--------------|
| `user.info.basic` | Basic profile (open_id, avatar, display_name) | Connected Account |
| `user.info.profile` | Extended profile (bio, username, verification) | Profile Display |
| `user.info.stats` | Statistics (followers, likes, video count) | Analytics |
| `video.publish` | Post videos to TikTok | Video Publishing |
| `video.upload` | Upload videos as drafts | Draft Upload |
| `video.list` | List user's videos | Video Management |

---

## 5. Actions (All Possible Endpoints)

### 5.1 User & Account Actions

| Action | API Endpoint | Method | Description |
|--------|--------------|--------|-------------|
| `get_user_info` | `/v2/user/info/` | GET | Get user profile information |
| `get_creator_info` | `/v2/post/publish/creator_info/query/` | POST | Get creator posting capabilities |

### 5.2 Video Posting Actions (Primary Focus)

| Action | API Endpoint | Method | Description |
|--------|--------------|--------|-------------|
| `create_video_post` | `/v2/post/publish/video/init/` | POST | Direct post video to TikTok profile |
| `upload_video_draft` | `/v2/post/publish/inbox/video/init/` | POST | Upload video as draft to TikTok inbox |
| `upload_video_chunk` | `<upload_url>` | PUT | Upload video file chunks |
| `get_post_status` | `/v2/post/publish/status/fetch/` | POST | Check video processing/posting status |

### 5.3 Photo Posting Actions

| Action | API Endpoint | Method | Description |
|--------|--------------|--------|-------------|
| `create_photo_post` | `/v2/post/publish/content/init/` | POST | Post photos to TikTok |

### 5.4 Video List Actions

| Action | API Endpoint | Method | Description |
|--------|--------------|--------|-------------|
| `get_videos` | `/v2/video/list/` | POST | List user's posted videos |
| `get_video` | `/v2/video/query/` | POST | Get specific video details |

---

## 6. Detailed Action Specifications

### 6.1 Get User Info

**Endpoint:** `GET /v2/user/info/`

**Input:**
```json
{
  "fields": ["open_id", "union_id", "avatar_url", "display_name", "bio_description",
             "profile_deep_link", "is_verified", "username", "follower_count",
             "following_count", "likes_count", "video_count"]
}
```

**Output:**
```json
{
  "open_id": "string",
  "union_id": "string",
  "avatar_url": "string",
  "avatar_url_100": "string",
  "avatar_large_url": "string",
  "display_name": "string",
  "bio_description": "string",
  "profile_deep_link": "string",
  "is_verified": "boolean",
  "username": "string",
  "follower_count": "integer",
  "following_count": "integer",
  "likes_count": "integer",
  "video_count": "integer"
}
```

---

### 6.2 Get Creator Info

**Endpoint:** `POST /v2/post/publish/creator_info/query/`

**Purpose:** Query creator's posting capabilities and limits before posting.

**Output:**
```json
{
  "creator_avatar_url": "string",
  "creator_username": "string",
  "creator_nickname": "string",
  "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
  "comment_disabled": "boolean",
  "duet_disabled": "boolean",
  "stitch_disabled": "boolean",
  "max_video_post_duration_sec": "integer"
}
```

---

### 6.3 Create Video Post (Direct Post)

**Endpoint:** `POST /v2/post/publish/video/init/`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "enum": ["FILE_UPLOAD", "PULL_FROM_URL"],
      "description": "Video source type"
    },
    "video_url": {
      "type": "string",
      "description": "Required if source=PULL_FROM_URL: Public URL of video"
    },
    "video_size": {
      "type": "integer",
      "description": "Required if source=FILE_UPLOAD: Video file size in bytes"
    },
    "chunk_size": {
      "type": "integer",
      "description": "Required if source=FILE_UPLOAD: Upload chunk size (5MB-64MB)"
    },
    "total_chunk_count": {
      "type": "integer",
      "description": "Required if source=FILE_UPLOAD: Number of chunks"
    },
    "post_info": {
      "type": "object",
      "properties": {
        "title": {
          "type": "string",
          "maxLength": 2200,
          "description": "Video caption with hashtags"
        },
        "privacy_level": {
          "type": "string",
          "enum": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
          "description": "Who can view the video"
        },
        "disable_comment": {
          "type": "boolean",
          "description": "Disable comments on video"
        },
        "disable_duet": {
          "type": "boolean",
          "description": "Disable duet feature"
        },
        "disable_stitch": {
          "type": "boolean",
          "description": "Disable stitch feature"
        },
        "video_cover_timestamp_ms": {
          "type": "integer",
          "description": "Timestamp for cover image in milliseconds"
        },
        "brand_content_toggle": {
          "type": "boolean",
          "description": "Mark as branded content"
        },
        "brand_organic_toggle": {
          "type": "boolean",
          "description": "Mark as organic branded content"
        }
      }
    }
  },
  "required": ["source"]
}
```

**Output:**
```json
{
  "publish_id": "string",
  "upload_url": "string (if FILE_UPLOAD)"
}
```

---

### 6.4 Upload Video Draft (Inbox)

**Endpoint:** `POST /v2/post/publish/inbox/video/init/`

**Purpose:** Upload video to user's TikTok inbox for later editing and posting.

**Input:** Same as Direct Post but without `post_info`

**Output:**
```json
{
  "publish_id": "string",
  "upload_url": "string"
}
```

---

### 6.5 Upload Video Chunk

**Endpoint:** `PUT <upload_url>`

**Headers:**
```
Content-Range: bytes <start>-<end>/<total>
Content-Type: video/mp4
```

**Body:** Binary video chunk data

---

### 6.6 Get Post Status

**Endpoint:** `POST /v2/post/publish/status/fetch/`

**Input:**
```json
{
  "publish_id": "string"
}
```

**Output:**
```json
{
  "status": "PROCESSING_UPLOAD | PROCESSING_DOWNLOAD | SEND_TO_USER_INBOX | PUBLISH_COMPLETE | FAILED",
  "fail_reason": "string (if FAILED)",
  "publicaly_available_post_id": ["string"],
  "uploaded_bytes": "integer",
  "error_code": "string"
}
```

---

### 6.7 Get Videos List

**Endpoint:** `POST /v2/video/list/`

**Input:**
```json
{
  "max_count": 20,
  "cursor": "integer (pagination)"
}
```

**Output:**
```json
{
  "videos": [
    {
      "id": "string",
      "title": "string",
      "cover_image_url": "string",
      "share_url": "string",
      "create_time": "integer (unix timestamp)",
      "duration": "integer (seconds)",
      "width": "integer",
      "height": "integer",
      "like_count": "integer",
      "comment_count": "integer",
      "share_count": "integer",
      "view_count": "integer"
    }
  ],
  "cursor": "integer",
  "has_more": "boolean"
}
```

---

## 7. Video Requirements & Specifications

### 7.1 Format Requirements

| Attribute | Requirement |
|-----------|-------------|
| **Format** | MP4 (H.264 codec), MOV |
| **Audio** | AAC codec |
| **Resolution** | 1080x1920 recommended (9:16) |
| **Aspect Ratio** | 9:16 (vertical), 16:9, 1:1 supported |
| **Frame Rate** | 30fps or 60fps |
| **Bitrate** | 6-8 Mbps for 1080p |

### 7.2 Size & Duration Limits

| Attribute | Limit |
|-----------|-------|
| **Min Duration** | 3 seconds |
| **Max Duration** | 10 minutes (API), 60 minutes (upload) |
| **Max File Size** | 287 MB (API), 500 MB (web) |
| **Chunk Size** | 5 MB - 64 MB (final chunk up to 128 MB) |

### 7.3 Upload Chunking Rules

```
- Videos < 5 MB: Upload as single chunk (chunk_size = video_size)
- Videos >= 5 MB: Split into 5-64 MB chunks
- Final chunk can be up to 128 MB for trailing bytes
```

---

## 8. Rate Limits & Quotas

| Limit Type | Value |
|------------|-------|
| API Requests | 6 requests/minute per user |
| Daily Posts (Unaudited) | 5 users/day, private only |
| Daily Posts (Audited) | ~15 posts/day per creator (shared across apps) |
| Caption Length | 2,200 characters |

### 8.1 Unaudited vs Audited Clients

| Feature | Unaudited | Audited |
|---------|-----------|---------|
| Users per 24h | 5 | Unlimited |
| Privacy Level | SELF_ONLY only | All levels |
| Account Type | Private only | Any |

---

## 9. Error Handling

### 9.1 Common Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `ok` | Success | - |
| `access_token_invalid` | Token expired | Refresh token |
| `rate_limit_exceeded` | Too many requests | Implement backoff |
| `scope_not_authorized` | Missing scope | Request authorization |
| `video_file_invalid` | Bad video format | Check format specs |
| `spam_risk_too_many_posts` | Post limit reached | Wait 24 hours |
| `unaudited_client_can_only_post_to_private_accounts` | Audit required | Request audit |

---

## 10. Webhook Events (Optional)

TikTok provides webhooks for post status updates:

| Event | Description |
|-------|-------------|
| `post.publish.complete` | Video successfully published |
| `post.publish.failed` | Video publishing failed |

---

## 11. Implementation Priority

### Phase 1 (MVP)
1. OAuth Authentication (Login Kit)
2. Get User Info
3. Create Video Post (Direct Post)
4. Get Post Status

### Phase 2
5. Upload Video Draft (Inbox)
6. Get Creator Info
7. Get Videos List

### Phase 3
8. Photo Posting
9. Webhook Integration
10. Analytics/Insights (if available)

---

## 12. Proposed Actions Summary

| Action | Display Name | Description | Priority |
|--------|--------------|-------------|----------|
| `get_user_info` | Get User Info | Get TikTok account profile and statistics | P1 |
| `get_creator_info` | Get Creator Info | Get posting capabilities and limits | P2 |
| `create_video_post` | Create Video Post | Post video directly to TikTok profile | P1 |
| `upload_video_draft` | Upload Draft | Upload video to inbox for later editing | P2 |
| `get_post_status` | Get Post Status | Check video processing/publishing status | P1 |
| `get_videos` | Get Videos | List user's published videos | P2 |
| `create_photo_post` | Create Photo Post | Post photos to TikTok | P3 |

---

## 13. Connected Account Display

Display in Autohive UI:
- Avatar (avatar_url)
- Display Name (display_name)
- Username (@username)
- Verification Badge (is_verified)
- Follower Count (follower_count)
- Total Likes (likes_count)

---

## 14. Security Considerations

1. **Token Storage:** Encrypt access/refresh tokens at rest
2. **HTTPS Only:** All API calls over HTTPS
3. **Scope Minimization:** Request only needed scopes
4. **Audit Compliance:** Follow TikTok's content policies
5. **Rate Limiting:** Implement client-side rate limiting

---

## 15. References

- [TikTok for Developers Portal](https://developers.tiktok.com/)
- [Content Posting API Documentation](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [Login Kit Documentation](https://developers.tiktok.com/doc/login-kit-overview)
- [User Info API](https://developers.tiktok.com/doc/tiktok-api-v2-get-user-info)
- [OAuth Token Management](https://developers.tiktok.com/doc/oauth-user-access-token-management)
- [Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)
- [Media Transfer Guide](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide)

---

## 16. Appendix: Full API Endpoints Reference

### Content Posting API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/post/publish/video/init/` | POST | Initialize direct video post |
| `/v2/post/publish/inbox/video/init/` | POST | Initialize draft upload |
| `/v2/post/publish/content/init/` | POST | Initialize photo post |
| `/v2/post/publish/creator_info/query/` | POST | Query creator capabilities |
| `/v2/post/publish/status/fetch/` | POST | Fetch post status |

### User Info API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/user/info/` | GET | Get user profile info |

### Video List API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/video/list/` | POST | List user videos |
| `/v2/video/query/` | POST | Query video details |

### OAuth API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/oauth/token/` | POST | Get/refresh tokens |
| `/v2/oauth/revoke/` | POST | Revoke tokens |

# TikTok Integration

TikTok integration for Autohive, enabling video posting and user profile management via the official TikTok Content Posting API.

## Features

- **Connected Account**: Displays authorized user's profile (username, avatar, follower count)
- **Video Posting**: Post videos directly to TikTok or upload as drafts
- **Post Management**: Set captions, hashtags, privacy levels, and engagement settings
- **Photo Posting**: Post photo slideshows with optional auto-music
- **Video List**: Retrieve user's published videos with engagement metrics

## Requirements

- TikTok account
- App registered on [TikTok for Developers](https://developers.tiktok.com/)

## Permissions

| Scope | Purpose |
|-------|---------|
| `user.info.basic` | Basic profile (avatar, display name) |
| `user.info.profile` | Extended profile (bio, username, verification) |
| `user.info.stats` | Statistics (followers, likes, video count) |
| `video.publish` | Post videos directly |
| `video.upload` | Upload videos as drafts |
| `video.list` | List published videos |

## Actions

| Action | Description |
|--------|-------------|
| `get_user_info` | Get account profile and statistics |
| `get_creator_info` | Get posting capabilities and limits |
| `create_video_post` | Post video directly to TikTok |
| `upload_video_draft` | Upload video to inbox as draft |
| `get_post_status` | Check video processing status |
| `get_videos` | List published videos |
| `create_photo_post` | Post photos to TikTok |

## Video Upload Flow

Videos are uploaded using base64-encoded content. The integration handles chunked uploading automatically.

### Input Format

```json
{
  "video_content_base64": "<base64-encoded-video>",
  "title": "My video caption #tiktok #viral",
  "privacy_level": "PUBLIC_TO_EVERYONE"
}
```

### Upload Process

1. **Decode**: Video content is decoded from base64
2. **Validate**: Size and format are validated (max 287 MB)
3. **Initialize**: Upload session is created with TikTok API
4. **Chunk Upload**: Video is split into chunks (5-64 MB each) and uploaded
5. **Process**: TikTok processes the video asynchronously
6. **Status**: Use `get_post_status` to track processing completion

### Response

```json
{
  "publish_id": "v_pub_123456789",
  "status": "PROCESSING_UPLOAD"
}
```

## Video Requirements

| Attribute | Requirement |
|-----------|-------------|
| Format | MP4 (H.264), MOV |
| Resolution | 1080x1920 (9:16 recommended) |
| Duration | 3 seconds - 10 minutes |
| Max Size | 287 MB |

## Privacy Levels

| Level | Description |
|-------|-------------|
| `PUBLIC_TO_EVERYONE` | Anyone can view |
| `MUTUAL_FOLLOW_FRIENDS` | Only mutual followers |
| `SELF_ONLY` | Private (only you) |

## Post Status Values

| Status | Description |
|--------|-------------|
| `PROCESSING_UPLOAD` | Video is being uploaded |
| `PROCESSING_DOWNLOAD` | TikTok is processing the video |
| `SEND_TO_USER_INBOX` | Draft sent to user's inbox |
| `PUBLISH_COMPLETE` | Video published successfully |
| `FAILED` | Publishing failed (check `fail_reason`) |

## Rate Limits

- **API Requests**: 6 requests/minute per user
- **Daily Posts**: ~15 posts/day per creator
- **Caption Length**: 2,200 characters max

## Error Handling

The integration handles common TikTok API errors:

| Error Code | Description |
|------------|-------------|
| `access_token_invalid` | Token expired, re-authenticate |
| `rate_limit_exceeded` | Too many requests, wait and retry |
| `scope_not_authorized` | Missing required OAuth scope |
| `spam_risk_too_many_posts` | Daily post limit reached |
| `video_format_invalid` | Unsupported video format |

## API Version

TikTok API **v2**

## Links

- [TikTok for Developers](https://developers.tiktok.com/)
- [Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [User Info API](https://developers.tiktok.com/doc/tiktok-api-v2-get-user-info)

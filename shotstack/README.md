# Shotstack Integration

Video editing and rendering integration using the [Shotstack](https://shotstack.io) API.

## Authentication

Requires a Shotstack API key and environment selection (`stage` or `v1`).

## Actions

| Action | Description |
|--------|-------------|
| `upload_media` | Upload a media file from a URL to Shotstack Ingest |
| `get_source` | Get the status and details of an ingested source |
| `list_sources` | List all ingested media sources |
| `delete_source` | Delete an ingested media source |
| `create_video` | Render a video from a list of clips with optional effects/transitions |
| `create_video_advanced` | Render a video using a full Shotstack Edit API timeline payload |
| `add_text_overlay` | Add a text overlay to an existing video |
| `add_logo_overlay` | Add an image/logo overlay to an existing video |
| `add_audio_track` | Add a background audio track to a video |
| `get_render` | Get the status and result URL of a render job |
| `list_renders` | List recent render jobs |
| `get_media_info` | Probe a media URL for metadata (duration, dimensions, codec, etc.) |
| `download_media` | Download a rendered video as base64 |

## Notes

- Use `environment: stage` for testing (free tier, watermarked output).
- Use `environment: v1` for production.
- `create_video` and `create_video_advanced` support `wait_for_completion: true` to poll until done (up to 5 minutes).

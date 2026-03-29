# Shotstack Integration

Video editing and rendering integration using the [Shotstack](https://shotstack.io) API.

## Authentication

Requires a Shotstack API key and environment selection (`stage` or `v1`).

## Actions

| Action | Description |
|--------|-------------|
| `upload_file` | Upload a file (video/image/audio) from conversation context to Shotstack Ingest |
| `check_source_status` | Poll the status of an uploaded file until ready or failed |
| `get_upload_url` | Get a presigned URL for direct file upload (advanced use) |
| `download_render` | Download a rendered video/image as base64 by render ID or URL |
| `submit_render` | Submit a render job and return immediately with a render_id (no waiting) |
| `check_render_status` | Check the status of a previously submitted render job |
| `render_and_wait` | Submit a render job and poll until complete (up to 5 minutes) |
| `custom_edit` | Full timeline-based video edit with optional wait for completion |
| `compose_video` | Combine multiple video/image clips sequentially with transitions |
| `add_text_overlay` | Add a text/title overlay to a video at a specified time and position |
| `add_logo_overlay` | Add a logo or watermark image to a video |
| `add_audio_track` | Add background music or voiceover to a video |
| `trim_video` | Extract a segment from a video by start time and end time or duration |
| `concatenate_videos` | Join multiple videos sequentially into one |
| `add_captions` | Add auto-generated or manual subtitles/captions to a video |

## Notes

- Use `environment: stage` for testing (free tier, watermarked output).
- Use `environment: v1` for production.
- `create_video` and `create_video_advanced` support `wait_for_completion: true` to poll until done (up to 5 minutes).

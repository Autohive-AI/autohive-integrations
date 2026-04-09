# Supadata Transcribe Integration for Autohive

Connects Autohive to the Supadata API to extract transcripts from popular social media video platforms including YouTube, TikTok, Instagram, and X (Twitter).

## Description

This integration provides automatic video transcription capabilities by leveraging the Supadata API. It solves the problem of extracting readable text content from social media videos, enabling users to analyze, search, and process video content in text format.

Key features:
- Extract transcripts from YouTube, TikTok, Instagram, and X (Twitter) videos
- Support for multiple languages with automatic detection
- Native transcript extraction when available, with AI-generated fallback
- Plain text output for easy processing and analysis

## Setup & Authentication

This integration uses API key authentication to connect with the Supadata service. You'll need to obtain a Supadata API key from their platform to use this integration.

To set up the integration:

1. Sign up for a Supadata account at [supadata.ai](https://supadata.ai)
2. Navigate to your API settings and generate an API key
3. Configure the integration in Autohive with your API key

**Authentication Fields:**

*   `api_key`: Your Supadata API key for video transcript extraction

## Actions

This integration provides one main action for extracting video transcripts.

### Action: `get_transcript`

*   **Description:** Fetches the transcript for a video from YouTube, TikTok, Instagram, or X (Twitter) URLs using the Supadata API
*   **Inputs:**
    *   `video_url`: Video URL from supported platforms (YouTube, TikTok, Instagram, X/Twitter) or public file URL
*   **Outputs:**
    *   `transcript`: The video transcript text in plain text format
    *   `language`: Detected language of the transcript (ISO 639-1 code)
    *   `available_languages`: List of available language codes for the transcript

## Requirements

The following Python packages are required for this integration:

*   `autohive-integrations-sdk` - Core SDK for Autohive integrations
*   `supadata` - Official Supadata Python SDK for API interactions

## Usage Examples

**Example 1: Extract YouTube video transcript**

```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

Expected output:
```json
{
  "transcript": "Never gonna give you up, never gonna let you down...",
  "language": "en",
  "available_languages": ["en", "es", "fr"]
}
```

**Example 2: Extract TikTok video transcript**

```json
{
  "video_url": "https://www.tiktok.com/@user/video/1234567890"
}
```

This integration is particularly useful for:
- Content analysis and sentiment analysis of social media videos
- Creating searchable text archives of video content
- Generating subtitles or captions for accessibility
- Building content moderation workflows

## Testing

To run the tests for this integration:

1.  Navigate to the integration's directory: `cd supadata`
2.  Install dependencies: `pip install -r requirements.txt`
3.  Set up your test environment with a valid Supadata API key
4.  Run the tests: `python tests/test_supadata_transcribe.py`

Note: Tests require a valid Supadata API key to interact with the actual service. Consider setting up environment variables for testing credentials.


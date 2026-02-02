# ElevenLabs Integration for Autohive

Connects Autohive to the ElevenLabs API to enable text-to-speech conversion, voice discovery, subscription management, and audio generation history management.

## Description

This integration provides access to ElevenLabs' AI text-to-speech platform. It allows users to convert text to lifelike speech, browse and discover available voices, manage voice settings, check subscription status and usage, and track audio generation history directly from Autohive.

The integration uses ElevenLabs API v1 with API Key authentication and implements 7 actions (6 free, 1 paid).

## Setup & Authentication

This integration uses **Custom Authentication** with ElevenLabs API Key.

### Authentication Method

ElevenLabs uses a custom header `xi-api-key` for authentication. The integration handles the authentication automatically by adding your API key to this header in all API requests.

### Required Authentication Fields

- **`api_key`**: Your ElevenLabs API Key
  - Created in ElevenLabs Settings > Developers > API Keys
  - Long-lived key that doesn't expire automatically
  - Must be kept secure (treat like a password)

### How to Get Your API Key

1. **Sign up/Login**: Go to https://elevenlabs.io
2. **Navigate to API Keys**: Click "Developers" in left sidebar
3. **Access API Keys**: Click "API Keys" tab
4. **Create Key**: Click "Create API Key" button
5. **Name and Create**: Enter name (e.g., "Autohive Integration"), click "Create"
6. **Copy Immediately**: Copy the key right away (shown only once!)

**Direct Link:** https://elevenlabs.io/app/settings/api-keys

### Setup Steps in Autohive

1. Get your API Key (follow steps above)
2. Add ElevenLabs integration in Autohive
3. Paste your API key in the `api_key` field
4. Save configuration

## Actions

### Text-to-Speech (1 action - COSTS CREDITS)

#### `text_to_speech`
Converts text to speech using a selected voice.

**Inputs:**
- `text` (required): Text to convert (max 2,500 characters on free tier)
- `voice_id` (required): Voice ID to use
- `model_id` (optional): AI model (e.g., 'eleven_multilingual_v2', 'eleven_turbo_v2_5')
- `output_format` (optional): Audio format (mp3_44100_128, pcm_16000, etc.)
- `voice_settings` (optional): Override voice settings
  - `stability`: 0.0-1.0
  - `similarity_boost`: 0.0-1.0
  - `style`: 0.0-1.0
  - `use_speaker_boost`: boolean

**Outputs:**
- `file`: Generated audio file object with base64-encoded content
  - `content`: Base64-encoded audio data
  - `name`: File name
  - `contentType`: MIME type (e.g., "audio/mpeg")
- `result`: Success status

**Cost:**
- Standard models: 1 credit per character
- Turbo models: 0.5 credits per character

---

### Voice Management (3 actions - FREE)

#### `list_voices`
Returns a list of all available voices with filtering and pagination.

**Inputs:**
- `page_size` (optional): Number of voices to return (default: 30, max: 100)
- `category` (optional): Filter by category (premade, cloned, generated, professional)
- `use_cases` (optional): Filter by use cases
- `search` (optional): Search by name or description

**Outputs:**
- `voices`: Array of voice objects
- `result`: Success status

**Cost:** FREE (0 credits)

---

#### `get_voice`
Returns metadata about a specific voice.

**Inputs:**
- `voice_id` (required): The ID of the voice
- `with_settings` (optional): Include voice settings in response

**Outputs:**
- `voice`: Voice object with metadata, labels, and samples
- `result`: Success status

**Cost:** FREE (0 credits)

---

#### `get_voice_settings`
Returns voice settings for a specific voice.

**Inputs:**
- `voice_id` (required): The ID of the voice

**Outputs:**
- `settings`: Voice settings (stability, similarity_boost, style, use_speaker_boost)
- `result`: Success status

**Cost:** FREE (0 credits)

---

### History Management (2 actions - FREE)

#### `list_history`
Returns a list of all generated audio items.

**Inputs:**
- `page_size` (optional): Number of items to return (max: 1,000)
- `voice_id` (optional): Filter by voice ID

**Outputs:**
- `history`: Array of history items (includes text, voice, timestamps, IDs)
- `result`: Success status

**Cost:** FREE (0 credits)

---

#### `download_history_audio`
Downloads the audio file from a history item.

**Inputs:**
- `history_item_id` (required): The ID of the history item

**Outputs:**
- `file`: Audio file object with base64-encoded content
  - `content`: Base64-encoded audio data
  - `name`: File name
  - `contentType`: MIME type (e.g., "audio/mpeg")
- `result`: Success status

**Cost:** FREE (0 credits - no new generation)

---

### User Account (1 action - FREE)

#### `get_user_subscription`
Returns subscription information including character quota and usage.

**Inputs:** None required

**Outputs:**
- `subscription`: Subscription object with tier, character_count, character_limit, voice_limit, etc.
- `result`: Success status

**Cost:** FREE (0 credits)

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v1
- **Base URL**: `https://api.elevenlabs.io/v1`
- **Authentication**: Custom header `xi-api-key`
- **Documentation**: https://elevenlabs.io/docs
- **Free Tier Limits**:
  - 10,000 credits/month
  - 1 credit = 1 character (standard models)
  - 1 credit = 2 characters (Turbo models - 0.5 credits per char)
  - Max 2,500 characters per generation
  - 3 custom voice slots
  - 20 premade professional voices
  - Non-commercial use only

## Important Notes

- API key must be kept secure and never shared publicly
- Free tier is for non-commercial use only
- Credits = characters of text generated
- Only `text_to_speech` action costs credits
- All other actions (list, get, download) are FREE
- Free tier includes 20 premade professional voices (American, British, Australian accents)
- Audio returned as base64-encoded file objects (supports mp3, wav, pcm formats)
- Generated audio is saved in history and can be re-downloaded without additional credits
- All actions include comprehensive error handling with result status and error messages

## Testing

To test the integration:

1. Navigate to the integration directory: `cd elevenlabs`
2. Install dependencies: `pip install -r requirements.txt`
3. Update test credentials in `tests/test_elevenlabs.py`
4. Run tests: `python tests/test_elevenlabs.py`

## Common Use Cases

**Content Creation:**
1. Convert blog posts to audio versions
2. Generate podcast intros/outros
3. Create audiobook narration
4. Produce video voiceovers

**Automation:**
1. Auto-generate audio from text triggers
2. Create voice notifications
3. Generate multilingual audio content
4. Batch convert documents to speech

**Voice Discovery:**
1. Browse 20 available premade voices
2. Test different voice characteristics (gender, age, accent)
3. Compare voice settings
4. Find the perfect voice for your content

**History Management:**
1. Track all generated audio
2. Re-download previous generations (free!)
3. Monitor credit usage
4. Manage audio assets

## Version History

- **1.0.0** - Initial release with 7 actions
  - Text-to-Speech: text_to_speech (1 action - PAID)
  - Voice Management: list_voices, get_voice, get_voice_settings (3 actions - FREE)
  - History Management: list_history, download_history_audio (2 actions - FREE)
  - User Account: get_user_subscription (1 action - FREE)

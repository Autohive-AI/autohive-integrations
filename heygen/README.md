# HeyGen Integration for Autohive

Connects Autohive to the HeyGen API to enable AI avatar generation, video creation, and photo avatar management for creating professional avatar videos at scale.

## Description

This integration provides comprehensive access to HeyGen's AI avatar platform. It allows users to generate AI photo avatars with customizable attributes, train custom avatar groups, create multi-scene videos with avatars, manage avatar looks and appearances, add motion and sound effects, and access existing avatar libraries directly from Autohive.

The integration uses HeyGen API v2 and implements actions covering the complete avatar-to-video workflow. It uses **OAuth 2.0** authentication with PKCE for secure access.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication with PKCE (Proof Key for Code Exchange) for enhanced security.

### OAuth 2.0 Flow

1. **User Authorization**: User is redirected to HeyGen to grant access
2. **Authorization Code**: HeyGen returns a code to your redirect URL
3. **Token Exchange**: Code is exchanged for access/refresh tokens
4. **API Access**: Access token is used as Bearer token in API requests

### OAuth 2.0 Endpoints

| Endpoint | URL |
|----------|-----|
| Authorization | `https://app.heygen.com/oauth/authorize` |
| Token | `https://api2.heygen.com/v1/oauth/token` |
| Refresh | `https://api2.heygen.com/v1/oauth/refresh_token` |

### Setup in Autohive

1. Add HeyGen integration in Autohive
2. Click "Connect with HeyGen"
3. Authorize the application in HeyGen
4. You're connected! Token refresh is handled automatically

### Request Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
User-Agent: AutoHive/1.0
```

## Actions

### Avatar Generation (2 actions)

#### `generate_photo_avatar`
Generate AI photos for photo avatar development with customizable attributes.

**Inputs:**
- `name` (required): Name to assign to the generated avatar
- `age` (required): Age group (Young Adult, Early Middle Age, Late Middle Age, Senior, Unspecified)
- `gender` (required): Gender identity (Woman, Man, Unspecified)
- `ethnicity` (required): Ethnic background (White, Black, Asian American, East Asian, South East Asian, South Asian, Middle Eastern, Latino, Native American, Pacific Islander, Mixed, Unspecified)
- `orientation` (required): Image orientation (square, horizontal, vertical)
- `pose` (required): Body framing (half_body, close_up, full_body)
- `style` (required): Visual style (Realistic, Pixar, Cinematic, Vintage, Noir, Cyberpunk, Unspecified)
- `appearance` (required): Text description of appearance, clothing, mood, lighting (max 1000 chars)
- `callback_url` (optional): URL to notify when generation is complete
- `callback_id` (optional): Custom ID for callback tracking

**Outputs:**
- `generation_id`: ID for tracking generation status

---

#### `check_generation_status`
Check the status of a photo or look generation request.

**Inputs:**
- `generation_id` (required): The generation ID from generate_photo_avatar or generate_avatar_look

**Outputs:**
- `photo_avatar_list`: Array of generated avatars with IDs, URLs, status, and metadata

---

### Avatar Group Management (4 actions)

#### `create_avatar_group`
Create an avatar group by grouping photos of the same subject.

**Inputs:**
- `name` (required): Name of the avatar group
- `image_key` (required): Image key from generation status or upload asset endpoint
- `generation_id` (optional): For AI-generated avatars only

**Outputs:**
- Avatar details including `id`, `group_id`, `image_url`, `status`

---

#### `add_looks_to_group`
Add additional looks to an existing avatar group (max 4 per request).

**Inputs:**
- `group_id` (required): Avatar group ID
- `image_keys` (required): Array of image keys (max 4)
- `name` (required): Name of the look
- `generation_id` (optional): For AI-generated avatars only

**Outputs:**
- Success confirmation

---

#### `train_avatar_group`
Train an avatar group to recognize the subject's unique features using machine learning.

**Inputs:**
- `group_id` (required): Avatar group ID to train

**Outputs:**
- Training job details with `flow_id` and avatar counts

---

#### `check_training_status`
Check the status of an avatar group training job.

**Inputs:**
- `group_id` (required): Avatar group ID being trained

**Outputs:**
- `status`: Training status (pending, processing, completed, failed)
- `progress`: Progress percentage (0-100)

---

### Avatar Enhancement (3 actions)

#### `generate_avatar_look`
Generate new appearance variations for a trained avatar group.

**Inputs:**
- `group_id` (required): Trained avatar group ID
- `prompt` (required): Description of desired look (max 1000 chars)
- `orientation` (required): Image orientation (square, horizontal, vertical)
- `pose` (required): Body framing (half_body, close_up, full_body)
- `style` (required): Visual style (Realistic, Pixar, Cinematic, Vintage, Noir, Cyberpunk, Unspecified)

**Outputs:**
- `generation_id`: ID for tracking generation status

---

#### `add_motion_to_avatar`
Add animated effects to a static photo avatar.

**Inputs:**
- `id` (required): Avatar/look ID
- `prompt` (optional): Text describing desired animation
- `motion_type` (optional): Motion engine (expressive, consistent, consistent_gen_3, hailuo_2, veo2, seedance_lite, kling)

**Outputs:**
- `id`: Motion-enhanced avatar ID

---

#### `add_sound_effect_to_avatar`
Attach audio enhancements to a motion avatar.

**Inputs:**
- `id` (required): Motion avatar/look ID from add_motion_to_avatar

**Outputs:**
- `sound_effect_id`: Unique identifier of the sound effect

---

### Avatar Discovery (2 actions)

#### `get_avatar_details`
Retrieve comprehensive information about a specific avatar.

**Inputs:**
- `id` (required): Avatar/look ID

**Outputs:**
- Complete avatar details including metadata, status, motion settings, sound effects, voice settings

---

#### `list_avatars`
List all available avatars in the account with pagination support.

**Inputs:**
- `page` (optional): Page number for pagination
- `limit` (optional): Number of results per page

**Outputs:**
- `avatars`: Array of avatar objects with IDs, names, preview URLs, tags
- `talking_photos`: Array of talking photo objects

---

### Video Creation (2 actions)

#### `create_avatar_video`
Create a video using an avatar with text-to-speech or audio input. Supports multiple scenes with customizable character, voice, background, and text elements.

**Inputs:**
- `video_inputs` (required): Array of scenes (1-50 items), each containing:
  - `character`: Avatar or talking photo configuration
  - `voice`: Text, audio, or silence settings
  - `background`: Color, image, or video background
  - `text`: Optional text overlay
- `title` (optional): Video title
- `caption` (optional): Enable captions (text-based input only)
- `dimension` (optional): Custom dimensions (default: 1280x720)
- `folder_id` (optional): Folder to store video
- `callback_id` (optional): Custom callback ID
- `callback_url` (optional): Webhook URL for completion notification

**Outputs:**
- `video_id`: ID for tracking video generation status

**Important Notes:**
- For backgrounds: Use hex colors (#RRGGBB format) or provide either `url` OR `asset_id`
- For audio voices: Provide either `audio_url` OR `audio_asset_id`
- See USAGE_EXAMPLE.md for detailed video_inputs structure

---

#### `get_video_status`
Check the status of a video generation request and get the video URL when complete.

**Inputs:**
- `video_id` (required): Video generation request ID

**Outputs:**
- `status`: Video status (pending, processing, completed, failed)
- `video_url`: URL to download video (when completed)

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URL**: `https://api.heygen.com/v2`
- **Authentication**: OAuth 2.0 Bearer Token (`Authorization: Bearer <token>`)
- **User-Agent**: `AutoHive/1.0` (Required for HeyGen partnership)
- **Documentation**: https://docs.heygen.com
- **OAuth Documentation**: https://docs.heygen.com/docs/heygen-oauth
- **Rate Limits**: Check your plan limits in HeyGen dashboard

## Plan Tiers & Video Quality

HeyGen offers different subscription tiers that affect video quality and available features:

### Video Resolution by Plan:
- **Free/Basic Plans**: Lower resolution (720p or below) - Still produces good quality videos suitable for most use cases
- **Pro Plans**: Higher resolution (1080p+) - Premium quality for professional productions
- **Enterprise Plans**: Custom resolutions including 4K

### Important Notes:
- **All plans work with this integration** - The integration supports all plan tiers
- **Free plan is capable** - Creates good quality videos for social media, demos, and standard content
- **Resolution errors**: If you get `RESOLUTION_NOT_ALLOWED` error, use lower dimensions or omit the `dimension` parameter
- **Features available**: Both public avatars and custom photo avatars work on free/basic plans
- **Training works**: Avatar training and enhancement features are available across all tiers

### Recommended Dimensions by Plan:
```javascript
// Free/Basic Plan (Safe)
{ "width": 1280, "height": 720 }   // 720p HD
{ "width": 854, "height": 480 }    // 480p SD
{ "width": 720, "height": 720 }    // Square (social media)

// Pro Plan and Above
{ "width": 1920, "height": 1080 }  // 1080p Full HD
{ "width": 3840, "height": 2160 }  // 4K (Enterprise)

// Or omit dimension entirely to use plan default
```

## Important Notes

- **API key must be kept secure** and never shared publicly
- **Avatar Training** takes 5-15 minutes - use polling with check_training_status
- **Video Generation** is asynchronous - poll get_video_status until complete
- **Error Format**: All errors return object with `code` and `message` properties
- **Validation**: Color backgrounds must use hex format (#RRGGBB), not shorthand
- **Resource Selection**: For images/videos/audio, provide EITHER url OR asset_id, not both
- **Scene Limits**: Videos support 1-50 scenes in video_inputs array
- **Motion Requirement**: Some features require motion-enhanced avatars

## Workflow Overview

HeyGen offers **two approaches** for creating avatar videos, each with different complexity and quality levels:

### Path 1: Quick Video with Public Avatars (Basic)
**Best for:** Fast video creation, testing, standard avatars
**Time:** Minutes
**Quality:** Good - uses HeyGen's pre-made avatars

```
1. list_voices → Choose a voice
2. list_avatars → Choose a public avatar (e.g., Santa, Angela)
3. create_avatar_video → Create video with avatar + voice + script
4. get_video_status → Poll until video is ready
```

**Example Use Cases:**
- Quick product demos
- Standard explainer videos
- Testing and prototyping
- Generic content with pre-made avatars

---

### Path 2: Custom Photo Avatar (Advanced)
**Best for:** Personalized avatars, brand consistency, unique characters
**Time:** 30-60 minutes (includes training)
**Quality:** Excellent - custom-trained on your specific photos

```
1. generate_photo_avatar → Generate AI photo from description
2. check_generation_status → Wait for generation
3. create_avatar_group → Group photos of same subject
4. train_avatar_group → ML training for facial features
5. check_training_status → Wait 5-15 mins for training
6. (Optional) generate_avatar_look → Generate different outfits/styles
7. (Optional) add_looks_to_group → Add multiple looks
8. add_motion_to_avatar → Add lifelike movements
9. add_sound_effect_to_avatar → Enhance with audio
10. create_photo_avatar_video → Create video with trained avatar
11. get_video_status → Poll until video is ready
```

**Why Train Your Avatar?**
- **Better lip-sync** - More accurate mouth movements
- **Natural expressions** - Improved facial animations
- **Multiple looks** - Same person, different outfits/backgrounds
- **Brand consistency** - Use your brand ambassador or team member
- **Personalization** - Create unique, recognizable characters

**Example Use Cases:**
- CEO announcements with actual CEO's photo
- Brand ambassador videos
- Personalized customer messages
- Company training with real employee avatars
- Character-based content series

---

### Comparison: Public vs Custom Avatars

| Feature | Public Avatars | Custom Photo Avatars |
|---------|---------------|---------------------|
| **Setup Time** | Instant | 30-60 minutes |
| **Customization** | Limited to existing avatars | Fully customizable appearance |
| **Quality** | Good | Excellent (after training) |
| **Cost** | Lower | Higher (training + generation) |
| **Use When** | Generic content, testing | Brand content, personalization |
| **Actions Needed** | 4 steps | 10+ steps |

---

### Hybrid Approach: Best of Both Worlds

You can also **combine both approaches**:
1. Start with public avatars for immediate needs
2. Generate custom avatars in parallel
3. Switch to trained avatars once ready
4. Use public avatars for generic scenes, custom for important ones

## Common Use Cases

**Marketing & Sales:**
- Product introduction videos
- Sales pitch videos
- Explainer videos
- Social media content
- Customer testimonials

**Training & Education:**
- Course content creation
- Tutorial videos
- Onboarding materials
- Educational content
- Training modules

**Automation:**
- Personalized video messages
- Automated video responses
- Content localization
- Batch video generation
- Dynamic video creation

**Content Creation:**
- YouTube videos
- LinkedIn content
- Instagram reels
- TikTok videos
- Podcast video versions

## Testing

To test the integration:

1. Navigate to the integration directory: `cd heygen`
2. Install dependencies: `pip install -r requirements.txt`
3. Update `access_token` in `tests/test_heygen.py` with your OAuth token
4. Run tests: `python tests/test_heygen.py`

## Usage Examples

### Example 1: Quick Marketing Video with Public Avatar

```python
# Step 1: List available voices
voices = heygen.list_voices()
# Choose: voice_id = "1bd001e7ffe04520adf63141a163d1f8" (Monica - Friendly)

# Step 2: List available avatars
avatars = heygen.list_avatars()
# Choose: avatar_id = "Angela-inblackskirt-20220820"

# Step 3: Create video
video = heygen.create_avatar_video({
  "video_inputs": [{
    "character": {
      "type": "avatar",
      "avatar_id": "Angela-inblackskirt-20220820"
    },
    "voice": {
      "type": "text",
      "voice_id": "1bd001e7ffe04520adf63141a163d1f8",
      "input_text": "Welcome to our new product! Today I'm excited to show you how our solution can transform your business."
    },
    "background": {
      "type": "color",
      "value": "#0066CC"
    }
  }],
  "title": "Product Introduction"
})

# Step 4: Poll for completion
status = heygen.get_video_status({"video_id": video["data"]["video_id"]})
# When status is "complete", download from video_url
```

---

### Example 2: Custom CEO Avatar Video (Advanced)

```python
# Step 1: Generate custom avatar from description
generation = heygen.generate_photo_avatar({
  "name": "CEO Avatar",
  "age": "Early Middle Age",
  "gender": "Man",
  "ethnicity": "Asian American",
  "orientation": "horizontal",
  "pose": "half_body",
  "style": "Realistic",
  "appearance": "Professional business executive in navy suit, confident expression, modern office background"
})

# Step 2: Check generation status
status = heygen.check_generation_status({
  "generation_id": generation["data"]["generation_id"]
})
# Wait until status is "completed", get image_key

# Step 3: Create avatar group
group = heygen.create_avatar_group({
  "name": "CEO Avatar Group",
  "image_key": status["data"]["photo_avatar_list"][0]["image_key"],
  "generation_id": generation["data"]["generation_id"]
})

# Step 4: Train the avatar (takes 5-15 minutes)
training = heygen.train_avatar_group({
  "group_id": group["data"]["group_id"]
})

# Step 5: Check training status
train_status = heygen.check_training_status({
  "group_id": group["data"]["group_id"]
})
# Poll until training is complete

# Step 6: Add motion and sound
motion = heygen.add_motion_to_avatar({
  "id": group["data"]["id"],
  "motion_type": "consistent"
})

sound = heygen.add_sound_effect_to_avatar({
  "id": motion["data"]["id"]
})

# Step 7: Create high-quality video
video = heygen.create_photo_avatar_video({
  "image_key": status["data"]["photo_avatar_list"][0]["image_key"],
  "video_title": "CEO Quarterly Update",
  "script": "Team, I'm pleased to share our Q4 results and vision for next year...",
  "voice_id": "e540ff9778d04108a8a7190bb4a77072"
})

# Step 8: Get final video
final = heygen.get_video_status({"video_id": video["data"]["video_id"]})
```

## Troubleshooting

**Common Error Messages:**

1. `"String should match pattern '^#[0-9a-fA-F]{6}$'"`
   - Use hex color format: `#FFFFFF` not `#FFF`

2. `"either url or image_asset_id needs to be provided"`
   - Provide exactly ONE of url or asset_id for images/videos/audio

3. `"Training status: pending"`
   - Training takes 5-15 minutes, continue polling

4. Video generation fails
   - Verify avatar is fully trained
   - Check all required video_inputs fields
   - Ensure motion/sound effects are added if needed

## Version History

- **1.2.0** - OAuth 2.0 Authentication (HeyGen Partnership)
  - Implemented OAuth 2.0 authentication with PKCE flow
  - Added `User-Agent: AutoHive/1.0` header for HeyGen partnership tracking
  - Updated to 17 actions

- **1.1.0** - Expanded Actions
  - Added list_avatar_groups, list_avatars_in_group actions
  - Added get_photo_avatar_details action
  - Added create_photo_avatar_video action (Avatar IV endpoint)
  - Added list_voice_locales action

- **1.0.0** - Initial release with 14 actions
  - Avatar Generation: generate_photo_avatar, check_generation_status
  - Avatar Groups: create_avatar_group, add_looks_to_group, train_avatar_group, check_training_status
  - Avatar Enhancement: generate_avatar_look, add_motion_to_avatar, add_sound_effect_to_avatar
  - Avatar Discovery: get_avatar_details, list_avatars
  - Video Creation: create_avatar_video, get_video_status

## Support

- **HeyGen Support**: https://help.heygen.com
- **API Documentation**: https://docs.heygen.com
- **Autohive Support**: Contact your Autohive team

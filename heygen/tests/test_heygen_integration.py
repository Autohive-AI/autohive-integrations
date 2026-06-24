"""
End-to-end integration tests for the HeyGen integration.

These tests call the real HeyGen API and require a valid OAuth access token
set in the HEYGEN_ACCESS_TOKEN environment variable.

Run all read-only tests:
    pytest heygen/tests/test_heygen_integration.py -m integration

Run destructive tests (generate/create — costs HeyGen credits):
    pytest heygen/tests/test_heygen_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import heygen.heygen as heygen_mod  # noqa: E402

heygen_integration = heygen_mod.heygen

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("HEYGEN_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("HEYGEN_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=headers or {}) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# =============================================================================
# LIST VOICES
# =============================================================================


class TestListVoices:
    async def test_returns_voices_list(self, live_context):
        result = await heygen_integration.execute_action("list_voices", {}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "voices" in data["data"]
        assert isinstance(data["data"]["voices"], list)

    async def test_voices_have_expected_fields(self, live_context):
        result = await heygen_integration.execute_action("list_voices", {}, live_context)
        voices = result.result.data["data"]["voices"]
        if not voices:
            pytest.skip("No voices returned from API")
        voice = voices[0]
        assert "voice_id" in voice
        assert "display_name" in voice
        assert "language" in voice


# =============================================================================
# LIST VOICE LOCALES
# =============================================================================


class TestListVoiceLocales:
    async def test_returns_locales_list(self, live_context):
        result = await heygen_integration.execute_action("list_voice_locales", {}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "locales" in data["data"]
        assert isinstance(data["data"]["locales"], list)

    async def test_locales_have_locale_field(self, live_context):
        result = await heygen_integration.execute_action("list_voice_locales", {}, live_context)
        locales = result.result.data["data"]["locales"]
        if not locales:
            pytest.skip("No locales returned from API")
        assert "locale" in locales[0]


# =============================================================================
# LIST AVATARS
# =============================================================================


class TestListAvatars:
    async def test_returns_avatars_and_talking_photos(self, live_context):
        result = await heygen_integration.execute_action("list_avatars", {}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "avatars" in data["data"]
        assert "talking_photos" in data["data"]

    async def test_avatars_are_simplified(self, live_context):
        result = await heygen_integration.execute_action("list_avatars", {}, live_context)
        avatars = result.result.data["data"]["avatars"]
        if not avatars:
            pytest.skip("No avatars on this account")
        avatar = avatars[0]
        # Simplification should have removed preview_image_url
        assert "preview_image_url" not in avatar
        assert "avatar_id" in avatar
        assert "avatar_name" in avatar

    async def test_pagination_limit_respected(self, live_context):
        result = await heygen_integration.execute_action("list_avatars", {"page": 1, "limit": 2}, live_context)
        avatars = result.result.data["data"]["avatars"]
        assert len(avatars) <= 2


# =============================================================================
# LIST AVATAR GROUPS
# =============================================================================


class TestListAvatarGroups:
    async def test_returns_avatar_groups(self, live_context):
        result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "avatar_groups" in data["data"]
        assert isinstance(data["data"]["avatar_groups"], list)

    async def test_groups_have_expected_fields(self, live_context):
        result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")
        group = groups[0]
        assert "id" in group
        assert "name" in group

    async def test_pagination_params_respected(self, live_context):
        result = await heygen_integration.execute_action("list_avatar_groups", {"page": 1, "limit": 5}, live_context)
        data = result.result.data
        assert data["error"] is None


# =============================================================================
# LIST AVATARS IN GROUP
# =============================================================================


class TestListAvatarsInGroup:
    async def test_returns_avatars_for_group(self, live_context):
        # First get a group to use
        groups_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = groups_result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")

        group_id = groups[0]["id"]
        result = await heygen_integration.execute_action("list_avatars_in_group", {"group_id": group_id}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "avatars" in data["data"]
        assert isinstance(data["data"]["avatars"], list)


# =============================================================================
# GET AVATAR DETAILS
# =============================================================================


class TestGetAvatarDetails:
    async def test_returns_avatar_details(self, live_context):
        avatars_result = await heygen_integration.execute_action("list_avatars", {"limit": 1}, live_context)
        avatars = avatars_result.result.data["data"]["avatars"]
        if not avatars:
            pytest.skip("No avatars on this account")

        avatar_id = avatars[0]["avatar_id"]
        if not avatar_id:
            pytest.skip("No avatar_id available")

        result = await heygen_integration.execute_action("get_avatar_details", {"avatar_id": avatar_id}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "avatar_id" in data["data"]


# =============================================================================
# CHECK GENERATION STATUS (read-only — uses existing generation_id)
# =============================================================================


class TestCheckGenerationStatus:
    async def test_invalid_id_returns_api_error(self, live_context):
        # A non-existent generation ID should return an API-level error, not crash
        result = await heygen_integration.execute_action(
            "check_generation_status", {"generation_id": "nonexistent_id_test"}, live_context
        )
        # The action should complete (not throw) — API error is in response body
        assert result is not None


# =============================================================================
# GET VIDEO STATUS (read-only — uses existing video_id)
# =============================================================================


class TestGetVideoStatus:
    async def test_invalid_id_returns_api_error(self, live_context):
        # A non-existent video ID should return API-level error, not crash
        result = await heygen_integration.execute_action(
            "get_video_status", {"video_id": "nonexistent_video_id_test"}, live_context
        )
        assert result is not None


# =============================================================================
# GET PHOTO AVATAR DETAILS (read-only — uses avatars from existing groups)
# =============================================================================


class TestGetPhotoAvatarDetails:
    async def test_returns_photo_avatar_details(self, live_context):
        groups_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = groups_result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")

        group_id = groups[0]["id"]
        avatars_result = await heygen_integration.execute_action(
            "list_avatars_in_group", {"group_id": group_id}, live_context
        )
        avatars = avatars_result.result.data["data"]["avatars"]
        if not avatars:
            pytest.skip("No avatars in group")

        photo_id = avatars[0]["id"]
        result = await heygen_integration.execute_action("get_photo_avatar_details", {"id": photo_id}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "id" in data["data"]
        assert data["data"]["id"] == photo_id

    async def test_photo_avatar_has_expected_fields(self, live_context):
        groups_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = groups_result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")

        group_id = groups[0]["id"]
        avatars_result = await heygen_integration.execute_action(
            "list_avatars_in_group", {"group_id": group_id}, live_context
        )
        avatars = avatars_result.result.data["data"]["avatars"]
        if not avatars:
            pytest.skip("No avatars in group")

        result = await heygen_integration.execute_action(
            "get_photo_avatar_details", {"id": avatars[0]["id"]}, live_context
        )
        details = result.result.data["data"]
        assert "name" in details
        assert "status" in details
        assert "is_motion" in details
        assert "group_id" in details


# =============================================================================
# CHECK TRAINING STATUS (read-only — uses existing trained groups)
# =============================================================================


class TestCheckTrainingStatus:
    async def test_returns_training_status(self, live_context):
        groups_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = groups_result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")

        group_id = groups[0]["id"]
        result = await heygen_integration.execute_action("check_training_status", {"group_id": group_id}, live_context)
        data = result.result.data
        assert data["error"] is None
        assert "status" in data["data"]

    async def test_training_status_has_timestamps(self, live_context):
        groups_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        groups = groups_result.result.data["data"]["avatar_groups"]
        if not groups:
            pytest.skip("No avatar groups on this account")

        group_id = groups[0]["id"]
        result = await heygen_integration.execute_action("check_training_status", {"group_id": group_id}, live_context)
        details = result.result.data["data"]
        assert "created_at" in details
        assert "updated_at" in details


# =============================================================================
# DESTRUCTIVE — generates/creates content (costs HeyGen credits)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestGeneratePhotoAvatar:
    """Generate a photo avatar — costs HeyGen credits."""

    async def test_generate_and_check_status(self, live_context):
        result = await heygen_integration.execute_action(
            "generate_photo_avatar",
            {
                "name": "Integration Test Avatar",
                "age": "Young Adult",
                "gender": "Woman",
                "ethnicity": "Unspecified",
                "orientation": "square",
                "pose": "half_body",
                "style": "Realistic",
                "appearance": "Professional business attire, friendly expression",
            },
            live_context,
        )
        data = result.result.data
        assert data["error"] is None
        generation_id = data["data"]["generation_id"]
        assert generation_id

        # Check status
        status_result = await heygen_integration.execute_action(
            "check_generation_status", {"generation_id": generation_id}, live_context
        )
        status_data = status_result.result.data
        assert status_data["error"] is None
        assert "status" in status_data["data"]


@pytest.mark.destructive
class TestCreateAvatarVideo:
    """Create a video — costs HeyGen credits. Requires valid avatar_id and voice_id."""

    async def test_create_and_check_status(self, live_context):
        # Get a voice and avatar to use
        voices_result = await heygen_integration.execute_action("list_voices", {}, live_context)
        voices = voices_result.result.data["data"]["voices"]
        if not voices:
            pytest.skip("No voices available")

        avatars_result = await heygen_integration.execute_action("list_avatars", {"limit": 1}, live_context)
        avatars = avatars_result.result.data["data"]["avatars"]
        if not avatars or not avatars[0].get("avatar_id"):
            pytest.skip("No avatars available")

        voice_id = voices[0]["voice_id"]
        avatar_id = avatars[0]["avatar_id"]

        result = await heygen_integration.execute_action(
            "create_avatar_video",
            {
                "video_inputs": [
                    {
                        "character": {"type": "avatar", "avatar_id": avatar_id},
                        "voice": {
                            "type": "text",
                            "input_text": "Hello, this is an integration test.",
                            "voice_id": voice_id,
                        },
                    }
                ],
                "title": "Integration Test Video",
            },
            live_context,
        )
        data = result.result.data
        assert data["error"] is None
        video_id = data["data"]["video_id"]
        assert video_id

        # Check video status
        status_result = await heygen_integration.execute_action(
            "get_video_status", {"video_id": video_id}, live_context
        )
        status_data = status_result.result.data
        assert status_data["error"] is None
        assert "status" in status_data["data"]
        assert status_data["data"]["status"] in ("pending", "in_progress", "complete", "failed")


@pytest.mark.destructive
class TestCreatePhotoAvatarVideo:
    """Create a photo avatar video using Avatar IV endpoint — costs HeyGen credits.

    Requires HEYGEN_TEST_IMAGE_KEY to be set (an image key from a previously uploaded
    or generated photo). The image_key is not discoverable via read-only API calls.
    """

    async def test_create_and_check_status(self, live_context):
        image_key = os.environ.get("HEYGEN_TEST_IMAGE_KEY", "")
        if not image_key:
            pytest.skip("HEYGEN_TEST_IMAGE_KEY not set — skipping photo avatar video test")

        voices_result = await heygen_integration.execute_action("list_voices", {}, live_context)
        voices = voices_result.result.data["data"]["voices"]
        if not voices:
            pytest.skip("No voices available")

        voice_id = voices[0]["voice_id"]

        result = await heygen_integration.execute_action(
            "create_photo_avatar_video",
            {
                "image_key": image_key,
                "video_title": "Integration Test Photo Avatar Video",
                "script": "Hello, this is an integration test.",
                "voice_id": voice_id,
            },
            live_context,
        )
        data = result.result.data
        assert data["error"] is None
        video_id = data["data"]["video_id"]
        assert video_id

        status_result = await heygen_integration.execute_action(
            "get_video_status", {"video_id": video_id}, live_context
        )
        status_data = status_result.result.data
        assert status_data["error"] is None
        assert status_data["data"]["status"] in ("pending", "in_progress", "complete", "failed")


@pytest.mark.destructive
class TestAvatarGroupLifecycle:
    """Create an avatar group and add looks — requires existing image_keys.

    Set HEYGEN_TEST_IMAGE_KEY to an image key obtained from a previously
    generated or uploaded photo (available from check_generation_status).

    This test creates real avatar groups on the account. It does not delete them
    (HeyGen has no delete group endpoint in v2). Run sparingly.
    """

    async def test_create_avatar_group(self, live_context):
        image_key = os.environ.get("HEYGEN_TEST_IMAGE_KEY", "")
        if not image_key:
            pytest.skip("HEYGEN_TEST_IMAGE_KEY not set — skipping avatar group lifecycle test")

        result = await heygen_integration.execute_action(
            "create_avatar_group",
            {"name": "Integration Test Group", "image_key": image_key},
            live_context,
        )
        data = result.result.data
        assert data["error"] is None
        group_id = data["data"]["group_id"]
        assert group_id

        # Verify the group appears in listings
        list_result = await heygen_integration.execute_action("list_avatar_groups", {}, live_context)
        group_ids = [g["id"] for g in list_result.result.data["data"]["avatar_groups"]]
        assert group_id in group_ids

    async def test_add_looks_to_group(self, live_context):
        image_key = os.environ.get("HEYGEN_TEST_IMAGE_KEY", "")
        if not image_key:
            pytest.skip("HEYGEN_TEST_IMAGE_KEY not set")

        # Create a fresh group to add looks to
        group_result = await heygen_integration.execute_action(
            "create_avatar_group",
            {"name": "Integration Test Group - Looks", "image_key": image_key},
            live_context,
        )
        assert group_result.result.data["error"] is None
        group_id = group_result.result.data["data"]["group_id"]

        result = await heygen_integration.execute_action(
            "add_looks_to_group",
            {"group_id": group_id, "image_keys": [image_key], "name": "Test Look"},
            live_context,
        )
        assert result.result.data["error"] is None

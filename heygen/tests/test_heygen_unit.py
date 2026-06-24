"""
Unit tests for the HeyGen integration using mocked fetch.
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, _parent)

import heygen.heygen as heygen_mod  # noqa: E402

heygen_integration = heygen_mod.heygen

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {"credentials": {"access_token": "test-token"}}  # nosec B105
    return ctx


def make_ctx_multi(responses: list):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {"credentials": {"access_token": "test-token"}}  # nosec B105
    return ctx


def make_ctx_error(exc: Exception):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc)
    ctx.auth = {"credentials": {"access_token": "test-token"}}  # nosec B105
    return ctx


# =============================================================================
# AUTH HEADERS
# =============================================================================


@pytest.mark.asyncio
async def test_auth_header_sent_with_bearer_token():
    ctx = make_ctx({"error": None, "data": {"voices": []}})
    await heygen_integration.execute_action("list_voices", {}, ctx)
    headers = ctx.fetch.call_args.kwargs.get("headers", {})
    assert headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_auth_header_empty_when_no_token():
    ctx = make_ctx({"error": None, "data": {"voices": []}})
    ctx.auth = {}
    await heygen_integration.execute_action("list_voices", {}, ctx)
    headers = ctx.fetch.call_args.kwargs.get("headers", {})
    assert headers["Authorization"] == "Bearer "


# =============================================================================
# GENERATE PHOTO AVATAR
# =============================================================================


@pytest.mark.asyncio
async def test_generate_photo_avatar_success():
    ctx = make_ctx({"error": None, "data": {"generation_id": "gen_abc123"}})
    inputs = {
        "name": "Test Avatar",
        "age": "Young Adult",
        "gender": "Woman",
        "ethnicity": "Asian American",
        "orientation": "square",
        "pose": "half_body",
        "style": "Realistic",
        "appearance": "Professional attire",
    }
    result = await heygen_integration.execute_action("generate_photo_avatar", inputs, ctx)
    assert result.result.data["data"]["generation_id"] == "gen_abc123"
    assert result.result.data["error"] is None


@pytest.mark.asyncio
async def test_generate_photo_avatar_optional_callback():
    ctx = make_ctx({"error": None, "data": {"generation_id": "gen_123"}})
    inputs = {
        "name": "Avatar",
        "age": "Young Adult",
        "gender": "Man",
        "ethnicity": "White",
        "orientation": "square",
        "pose": "close_up",
        "style": "Cinematic",
        "appearance": "Casual",
        "callback_url": "https://example.com/callback",
        "callback_id": "cb_001",
    }
    await heygen_integration.execute_action("generate_photo_avatar", inputs, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["callback_url"] == "https://example.com/callback"
    assert body["callback_id"] == "cb_001"


@pytest.mark.asyncio
async def test_generate_photo_avatar_no_optional_callback():
    ctx = make_ctx({"error": None, "data": {"generation_id": "gen_123"}})
    inputs = {
        "name": "Avatar",
        "age": "Young Adult",
        "gender": "Man",
        "ethnicity": "White",
        "orientation": "square",
        "pose": "close_up",
        "style": "Cinematic",
        "appearance": "Casual",
    }
    await heygen_integration.execute_action("generate_photo_avatar", inputs, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert "callback_url" not in body
    assert "callback_id" not in body


@pytest.mark.asyncio
async def test_generate_photo_avatar_fetch_error():
    ctx = make_ctx_error(RuntimeError("Network error"))
    inputs = {
        "name": "Avatar",
        "age": "Young Adult",
        "gender": "Man",
        "ethnicity": "White",
        "orientation": "square",
        "pose": "close_up",
        "style": "Cinematic",
        "appearance": "Casual",
    }
    result = await heygen_integration.execute_action("generate_photo_avatar", inputs, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Network error" in result.result.message


@pytest.mark.asyncio
async def test_generate_photo_avatar_missing_required_field():
    ctx = make_ctx({})
    result = await heygen_integration.execute_action("generate_photo_avatar", {"name": "Only Name"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# CHECK GENERATION STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_check_generation_status_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "id": "avatar_001",
                "status": "completed",
                "image_url_list": ["https://example.com/img.jpg"],
                "image_key_list": ["key_001"],
            },
        }
    )
    result = await heygen_integration.execute_action("check_generation_status", {"generation_id": "gen_abc"}, ctx)
    data = result.result.data["data"]
    assert data["status"] == "completed"
    assert data["id"] == "avatar_001"


@pytest.mark.asyncio
async def test_check_generation_status_uses_generation_id_in_url():
    ctx = make_ctx({"error": None, "data": {"id": "x", "status": "in_progress"}})
    await heygen_integration.execute_action("check_generation_status", {"generation_id": "gen_xyz"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "gen_xyz" in url


@pytest.mark.asyncio
async def test_check_generation_status_error():
    ctx = make_ctx_error(RuntimeError("Timeout"))
    result = await heygen_integration.execute_action("check_generation_status", {"generation_id": "gen_abc"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Timeout" in result.result.message


# =============================================================================
# CREATE AVATAR GROUP
# =============================================================================


@pytest.mark.asyncio
async def test_create_avatar_group_success():
    ctx = make_ctx({"error": None, "data": {"group_id": "group_001", "name": "My Group", "status": "active"}})
    result = await heygen_integration.execute_action(
        "create_avatar_group", {"name": "My Group", "image_key": "img_key_001"}, ctx
    )
    assert result.result.data["data"]["group_id"] == "group_001"


@pytest.mark.asyncio
async def test_create_avatar_group_optional_generation_id():
    ctx = make_ctx({"error": None, "data": {"group_id": "group_001"}})
    await heygen_integration.execute_action(
        "create_avatar_group",
        {"name": "Group", "image_key": "img_key", "generation_id": "gen_001"},
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["generation_id"] == "gen_001"


@pytest.mark.asyncio
async def test_create_avatar_group_without_generation_id():
    ctx = make_ctx({"error": None, "data": {"group_id": "group_001"}})
    await heygen_integration.execute_action("create_avatar_group", {"name": "Group", "image_key": "img_key"}, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert "generation_id" not in body


@pytest.mark.asyncio
async def test_create_avatar_group_error():
    ctx = make_ctx_error(RuntimeError("API error"))
    result = await heygen_integration.execute_action("create_avatar_group", {"name": "Group", "image_key": "key"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# ADD LOOKS TO GROUP
# =============================================================================


@pytest.mark.asyncio
async def test_add_looks_to_group_success():
    ctx = make_ctx({"error": None, "data": {"id": "look_001"}})
    result = await heygen_integration.execute_action(
        "add_looks_to_group",
        {"group_id": "grp_001", "image_keys": ["key1", "key2"], "name": "Look 1"},
        ctx,
    )
    assert result.result.data["error"] is None


@pytest.mark.asyncio
async def test_add_looks_to_group_sends_correct_body():
    ctx = make_ctx({"error": None, "data": {}})
    await heygen_integration.execute_action(
        "add_looks_to_group",
        {"group_id": "grp_001", "image_keys": ["key1", "key2"], "name": "New Look"},
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["group_id"] == "grp_001"
    assert body["image_keys"] == ["key1", "key2"]
    assert body["name"] == "New Look"


@pytest.mark.asyncio
async def test_add_looks_to_group_error():
    ctx = make_ctx_error(RuntimeError("Bad request"))
    result = await heygen_integration.execute_action(
        "add_looks_to_group",
        {"group_id": "grp_001", "image_keys": ["key1"], "name": "Look"},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Bad request" in result.result.message


# =============================================================================
# TRAIN AVATAR GROUP
# =============================================================================


@pytest.mark.asyncio
async def test_train_avatar_group_success():
    ctx = make_ctx({"error": None, "data": {"flow_id": "flow_001"}})
    result = await heygen_integration.execute_action("train_avatar_group", {"group_id": "grp_001"}, ctx)
    assert result.result.data["error"] is None


@pytest.mark.asyncio
async def test_train_avatar_group_sends_group_id():
    ctx = make_ctx({"error": None, "data": {}})
    await heygen_integration.execute_action("train_avatar_group", {"group_id": "grp_abc"}, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["group_id"] == "grp_abc"


@pytest.mark.asyncio
async def test_train_avatar_group_error():
    ctx = make_ctx_error(RuntimeError("Server error"))
    result = await heygen_integration.execute_action("train_avatar_group", {"group_id": "grp_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CHECK TRAINING STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_check_training_status_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {"status": "ready", "error_msg": None, "created_at": 1700000000, "updated_at": 1700001000},
        }
    )
    result = await heygen_integration.execute_action("check_training_status", {"group_id": "grp_001"}, ctx)
    assert result.result.data["data"]["status"] == "ready"


@pytest.mark.asyncio
async def test_check_training_status_uses_group_id_in_url():
    ctx = make_ctx({"error": None, "data": {"status": "pending"}})
    await heygen_integration.execute_action("check_training_status", {"group_id": "grp_xyz"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "grp_xyz" in url


@pytest.mark.asyncio
async def test_check_training_status_error():
    ctx = make_ctx_error(RuntimeError("Timeout"))
    result = await heygen_integration.execute_action("check_training_status", {"group_id": "grp_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GENERATE AVATAR LOOK
# =============================================================================


@pytest.mark.asyncio
async def test_generate_avatar_look_success():
    ctx = make_ctx({"error": None, "data": {"generation_id": "look_gen_001"}})
    result = await heygen_integration.execute_action(
        "generate_avatar_look",
        {
            "group_id": "grp_001",
            "prompt": "Professional business attire",
            "orientation": "vertical",
            "pose": "half_body",
            "style": "Realistic",
        },
        ctx,
    )
    assert result.result.data["data"]["generation_id"] == "look_gen_001"


@pytest.mark.asyncio
async def test_generate_avatar_look_sends_correct_body():
    ctx = make_ctx({"error": None, "data": {"generation_id": "x"}})
    await heygen_integration.execute_action(
        "generate_avatar_look",
        {
            "group_id": "grp_001",
            "prompt": "Casual outfit",
            "orientation": "square",
            "pose": "close_up",
            "style": "Cinematic",
        },
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["group_id"] == "grp_001"
    assert body["prompt"] == "Casual outfit"
    assert body["style"] == "Cinematic"


@pytest.mark.asyncio
async def test_generate_avatar_look_error():
    ctx = make_ctx_error(RuntimeError("Rate limited"))
    result = await heygen_integration.execute_action(
        "generate_avatar_look",
        {"group_id": "grp_001", "prompt": "x", "orientation": "square", "pose": "close_up", "style": "Realistic"},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Rate limited" in result.result.message


# =============================================================================
# ADD MOTION TO AVATAR
# =============================================================================


@pytest.mark.asyncio
async def test_add_motion_to_avatar_success():
    ctx = make_ctx({"error": None, "data": {"id": "motion_avatar_001"}})
    result = await heygen_integration.execute_action("add_motion_to_avatar", {"id": "avatar_001"}, ctx)
    assert result.result.data["data"]["id"] == "motion_avatar_001"


@pytest.mark.asyncio
async def test_add_motion_to_avatar_with_optional_fields():
    ctx = make_ctx({"error": None, "data": {"id": "motion_001"}})
    await heygen_integration.execute_action(
        "add_motion_to_avatar",
        {"id": "avatar_001", "prompt": "Wave hand", "motion_type": "expressive"},
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["prompt"] == "Wave hand"
    assert body["motion_type"] == "expressive"


@pytest.mark.asyncio
async def test_add_motion_to_avatar_without_optional_fields():
    ctx = make_ctx({"error": None, "data": {"id": "motion_001"}})
    await heygen_integration.execute_action("add_motion_to_avatar", {"id": "avatar_001"}, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert "prompt" not in body
    assert "motion_type" not in body


@pytest.mark.asyncio
async def test_add_motion_to_avatar_error():
    ctx = make_ctx_error(RuntimeError("Internal error"))
    result = await heygen_integration.execute_action("add_motion_to_avatar", {"id": "avatar_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# ADD SOUND EFFECT TO AVATAR
# =============================================================================


@pytest.mark.asyncio
async def test_add_sound_effect_success():
    ctx = make_ctx({"error": None, "data": {"code": 100, "data": {"sound_effect_id": "se_001"}}})
    result = await heygen_integration.execute_action("add_sound_effect_to_avatar", {"id": "avatar_001"}, ctx)
    assert result.result.data["data"]["data"]["sound_effect_id"] == "se_001"


@pytest.mark.asyncio
async def test_add_sound_effect_sends_id():
    ctx = make_ctx({"error": None, "data": {}})
    await heygen_integration.execute_action("add_sound_effect_to_avatar", {"id": "motion_avatar_xyz"}, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["id"] == "motion_avatar_xyz"


@pytest.mark.asyncio
async def test_add_sound_effect_error():
    ctx = make_ctx_error(RuntimeError("Not found"))
    result = await heygen_integration.execute_action("add_sound_effect_to_avatar", {"id": "avatar_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST AVATAR GROUPS
# =============================================================================


@pytest.mark.asyncio
async def test_list_avatar_groups_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "avatar_groups": [
                    {"id": "grp_001", "name": "Group 1", "created_at": 1700000000, "training_status": "ready"},
                    {"id": "grp_002", "name": "Group 2", "created_at": 1700001000, "training_status": "pending"},
                ],
                "total": 2,
                "page": 1,
                "limit": 10,
            },
        }
    )
    result = await heygen_integration.execute_action("list_avatar_groups", {}, ctx)
    groups = result.result.data["data"]["avatar_groups"]
    assert len(groups) == 2
    assert groups[0]["id"] == "grp_001"


@pytest.mark.asyncio
async def test_list_avatar_groups_pagination_params():
    ctx = make_ctx({"error": None, "data": {"avatar_groups": [], "total": 0}})
    await heygen_integration.execute_action("list_avatar_groups", {"page": 2, "limit": 5}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["page"] == 2
    assert params["limit"] == 5


@pytest.mark.asyncio
async def test_list_avatar_groups_include_public():
    ctx = make_ctx({"error": None, "data": {"avatar_groups": [], "total": 0}})
    await heygen_integration.execute_action("list_avatar_groups", {"include_public": True}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["include_public"] is True


@pytest.mark.asyncio
async def test_list_avatar_groups_error():
    ctx = make_ctx_error(RuntimeError("Unauthorized"))
    result = await heygen_integration.execute_action("list_avatar_groups", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST AVATARS IN GROUP
# =============================================================================


@pytest.mark.asyncio
async def test_list_avatars_in_group_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "group_id": "grp_001",
                "group_name": "My Group",
                "avatars": [
                    {
                        "id": "av_001",
                        "name": "Avatar 1",
                        "status": "active",
                        "is_motion": False,
                        "created_at": 1700000000,
                    }
                ],
            },
        }
    )
    result = await heygen_integration.execute_action("list_avatars_in_group", {"group_id": "grp_001"}, ctx)
    data = result.result.data["data"]
    assert data["group_id"] == "grp_001"
    assert len(data["avatars"]) == 1


@pytest.mark.asyncio
async def test_list_avatars_in_group_uses_group_id_in_url():
    ctx = make_ctx({"error": None, "data": {"group_id": "grp_abc", "avatars": []}})
    await heygen_integration.execute_action("list_avatars_in_group", {"group_id": "grp_abc"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "grp_abc" in url


@pytest.mark.asyncio
async def test_list_avatars_in_group_error():
    ctx = make_ctx_error(RuntimeError("Not found"))
    result = await heygen_integration.execute_action("list_avatars_in_group", {"group_id": "grp_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET AVATAR DETAILS
# =============================================================================


@pytest.mark.asyncio
async def test_get_avatar_details_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "avatar_id": "av_001",
                "avatar_name": "Studio Avatar",
                "gender": "female",
                "preview_image_url": "https://example.com/preview.jpg",
                "preview_video_url": None,
                "default_voice_id": "voice_001",
            },
        }
    )
    result = await heygen_integration.execute_action("get_avatar_details", {"avatar_id": "av_001"}, ctx)
    assert result.result.data["data"]["avatar_id"] == "av_001"
    assert result.result.data["data"]["avatar_name"] == "Studio Avatar"


@pytest.mark.asyncio
async def test_get_avatar_details_uses_avatar_id_in_url():
    ctx = make_ctx({"error": None, "data": {"avatar_id": "av_xyz"}})
    await heygen_integration.execute_action("get_avatar_details", {"avatar_id": "av_xyz"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "av_xyz" in url


@pytest.mark.asyncio
async def test_get_avatar_details_error():
    ctx = make_ctx_error(RuntimeError("Not found"))
    result = await heygen_integration.execute_action("get_avatar_details", {"avatar_id": "av_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET PHOTO AVATAR DETAILS
# =============================================================================


@pytest.mark.asyncio
async def test_get_photo_avatar_details_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "id": "photo_av_001",
                "name": "Photo Avatar 1",
                "status": "active",
                "is_motion": True,
                "group_id": "grp_001",
            },
        }
    )
    result = await heygen_integration.execute_action("get_photo_avatar_details", {"id": "photo_av_001"}, ctx)
    assert result.result.data["data"]["id"] == "photo_av_001"
    assert result.result.data["data"]["is_motion"] is True


@pytest.mark.asyncio
async def test_get_photo_avatar_details_uses_id_in_url():
    ctx = make_ctx({"error": None, "data": {"id": "photo_xyz"}})
    await heygen_integration.execute_action("get_photo_avatar_details", {"id": "photo_xyz"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "photo_xyz" in url


@pytest.mark.asyncio
async def test_get_photo_avatar_details_error():
    ctx = make_ctx_error(RuntimeError("Forbidden"))
    result = await heygen_integration.execute_action("get_photo_avatar_details", {"id": "photo_av_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST VOICES
# =============================================================================


@pytest.mark.asyncio
async def test_list_voices_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "voices": [
                    {
                        "voice_id": "v_001",
                        "display_name": "Alice",
                        "language": "en-US",
                        "gender": "female",
                        "age": "young",
                        "emotion_support": True,
                        "multilingual": False,
                    }
                ]
            },
        }
    )
    result = await heygen_integration.execute_action("list_voices", {}, ctx)
    voices = result.result.data["data"]["voices"]
    assert len(voices) == 1
    assert voices[0]["voice_id"] == "v_001"


@pytest.mark.asyncio
async def test_list_voices_empty():
    ctx = make_ctx({"error": None, "data": {"voices": []}})
    result = await heygen_integration.execute_action("list_voices", {}, ctx)
    assert result.result.data["data"]["voices"] == []


@pytest.mark.asyncio
async def test_list_voices_error():
    ctx = make_ctx_error(RuntimeError("Service unavailable"))
    result = await heygen_integration.execute_action("list_voices", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Service unavailable" in result.result.message


# =============================================================================
# LIST VOICE LOCALES
# =============================================================================


@pytest.mark.asyncio
async def test_list_voice_locales_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "locales": [
                    {"locale": "en-US", "language": "English", "region": "United States"},
                    {"locale": "en-GB", "language": "English", "region": "United Kingdom"},
                    {"locale": "fr", "language": "French", "region": None},
                ]
            },
        }
    )
    result = await heygen_integration.execute_action("list_voice_locales", {}, ctx)
    locales = result.result.data["data"]["locales"]
    assert len(locales) == 3
    assert locales[0]["locale"] == "en-US"
    assert locales[2]["region"] is None


@pytest.mark.asyncio
async def test_list_voice_locales_with_voice_id():
    ctx = make_ctx({"error": None, "data": {"locales": []}})
    await heygen_integration.execute_action("list_voice_locales", {"voice_id": "v_001"}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["voice_id"] == "v_001"


@pytest.mark.asyncio
async def test_list_voice_locales_without_voice_id():
    ctx = make_ctx({"error": None, "data": {"locales": []}})
    await heygen_integration.execute_action("list_voice_locales", {}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert "voice_id" not in params


@pytest.mark.asyncio
async def test_list_voice_locales_error():
    ctx = make_ctx_error(RuntimeError("Timeout"))
    result = await heygen_integration.execute_action("list_voice_locales", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST AVATARS (with simplification logic)
# =============================================================================


@pytest.mark.asyncio
async def test_list_avatars_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "avatars": [
                    {
                        "avatar_id": "av_001",
                        "avatar_name": "Alice",
                        "gender": "female",
                        "type": "studio",
                        "premium": False,
                        "default_voice_id": "v_001",
                        "preview_image_url": "https://cdn.example.com/very/long/url/preview.jpg",
                    }
                ],
                "talking_photos": [
                    {
                        "talking_photo_id": "tp_001",
                        "talking_photo_name": "Photo 1",
                        "preview_image_url": "https://cdn.example.com/another/long/url.jpg",
                    }
                ],
            },
        }
    )
    result = await heygen_integration.execute_action("list_avatars", {}, ctx)
    data = result.result.data["data"]
    avatar = data["avatars"][0]
    # Verify simplification removed the long URL
    assert "preview_image_url" not in avatar
    assert avatar["avatar_id"] == "av_001"
    assert avatar["avatar_name"] == "Alice"
    assert avatar["gender"] == "female"
    assert avatar["type"] == "studio"
    assert avatar["premium"] is False
    assert avatar["default_voice_id"] == "v_001"


@pytest.mark.asyncio
async def test_list_avatars_talking_photos_simplified():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "avatars": [],
                "talking_photos": [
                    {"talking_photo_id": "tp_001", "talking_photo_name": "Photo 1", "preview_image_url": "https://..."},
                    {"talking_photo_id": "tp_002", "talking_photo_name": "Photo 2", "preview_image_url": "https://..."},
                ],
            },
        }
    )
    result = await heygen_integration.execute_action("list_avatars", {}, ctx)
    photos = result.result.data["data"]["talking_photos"]
    assert len(photos) == 2
    for photo in photos:
        assert "preview_image_url" not in photo
        assert "talking_photo_id" in photo
        assert "talking_photo_name" in photo


@pytest.mark.asyncio
async def test_list_avatars_empty_lists():
    ctx = make_ctx({"error": None, "data": {"avatars": [], "talking_photos": []}})
    result = await heygen_integration.execute_action("list_avatars", {}, ctx)
    data = result.result.data["data"]
    assert data["avatars"] == []
    assert data["talking_photos"] == []


@pytest.mark.asyncio
async def test_list_avatars_pagination_params():
    ctx = make_ctx({"error": None, "data": {"avatars": [], "talking_photos": []}})
    await heygen_integration.execute_action("list_avatars", {"page": 2, "limit": 20}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["page"] == 2
    assert params["limit"] == 20


@pytest.mark.asyncio
async def test_list_avatars_error():
    ctx = make_ctx_error(RuntimeError("Auth failed"))
    result = await heygen_integration.execute_action("list_avatars", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE AVATAR VIDEO
# =============================================================================


@pytest.mark.asyncio
async def test_create_avatar_video_success():
    ctx = make_ctx({"error": None, "data": {"video_id": "vid_001"}})
    video_inputs = [
        {
            "character": {"type": "avatar", "avatar_id": "av_001"},
            "voice": {"type": "text", "input_text": "Hello world", "voice_id": "v_001"},
        }
    ]
    result = await heygen_integration.execute_action("create_avatar_video", {"video_inputs": video_inputs}, ctx)
    assert result.result.data["data"]["video_id"] == "vid_001"


@pytest.mark.asyncio
async def test_create_avatar_video_optional_fields():
    ctx = make_ctx({"error": None, "data": {"video_id": "vid_002"}})
    video_inputs = [{"character": {"type": "avatar", "avatar_id": "av_001"}, "voice": {"type": "silence"}}]
    await heygen_integration.execute_action(
        "create_avatar_video",
        {
            "video_inputs": video_inputs,
            "title": "My Video",
            "caption": True,
            "dimension": {"width": 1920, "height": 1080},
            "folder_id": "folder_001",
            "callback_id": "cb_001",
            "callback_url": "https://example.com/cb",
        },
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["title"] == "My Video"
    assert body["caption"] is True
    assert body["dimension"] == {"width": 1920, "height": 1080}
    assert body["folder_id"] == "folder_001"


@pytest.mark.asyncio
async def test_create_avatar_video_minimal_body():
    ctx = make_ctx({"error": None, "data": {"video_id": "vid_003"}})
    video_inputs = [{"character": {"type": "avatar", "avatar_id": "av_001"}, "voice": {"type": "silence"}}]
    await heygen_integration.execute_action("create_avatar_video", {"video_inputs": video_inputs}, ctx)
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert set(body.keys()) == {"video_inputs"}


@pytest.mark.asyncio
async def test_create_avatar_video_error():
    ctx = make_ctx_error(RuntimeError("Quota exceeded"))
    video_inputs = [{"character": {"type": "avatar", "avatar_id": "av_001"}, "voice": {"type": "silence"}}]
    result = await heygen_integration.execute_action("create_avatar_video", {"video_inputs": video_inputs}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Quota exceeded" in result.result.message


# =============================================================================
# CREATE PHOTO AVATAR VIDEO
# =============================================================================


@pytest.mark.asyncio
async def test_create_photo_avatar_video_with_script():
    ctx = make_ctx({"error": None, "data": {"video_id": "pav_vid_001"}})
    result = await heygen_integration.execute_action(
        "create_photo_avatar_video",
        {
            "image_key": "img_key_001",
            "video_title": "My Photo Video",
            "script": "Hello, this is a test.",
            "voice_id": "v_001",
        },
        ctx,
    )
    assert result.result.data["data"]["video_id"] == "pav_vid_001"
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["script"] == "Hello, this is a test."
    assert body["voice_id"] == "v_001"


@pytest.mark.asyncio
async def test_create_photo_avatar_video_with_audio_url():
    ctx = make_ctx({"error": None, "data": {"video_id": "pav_vid_002"}})
    await heygen_integration.execute_action(
        "create_photo_avatar_video",
        {"image_key": "img_key_001", "video_title": "Audio Video", "audio_url": "https://example.com/audio.mp3"},
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["audio_url"] == "https://example.com/audio.mp3"
    assert "script" not in body


@pytest.mark.asyncio
async def test_create_photo_avatar_video_optional_orientation():
    ctx = make_ctx({"error": None, "data": {"video_id": "pav_vid_003"}})
    await heygen_integration.execute_action(
        "create_photo_avatar_video",
        {
            "image_key": "key",
            "video_title": "Test",
            "video_orientation": "landscape",
            "fit": "cover",
            "custom_motion_prompt": "Nod head",
            "enhance_custom_motion_prompt": True,
        },
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["video_orientation"] == "landscape"
    assert body["fit"] == "cover"
    assert body["custom_motion_prompt"] == "Nod head"
    assert body["enhance_custom_motion_prompt"] is True


@pytest.mark.asyncio
async def test_create_photo_avatar_video_error():
    ctx = make_ctx_error(RuntimeError("Invalid image key"))
    result = await heygen_integration.execute_action(
        "create_photo_avatar_video",
        {"image_key": "bad_key", "video_title": "Test"},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Invalid image key" in result.result.message


# =============================================================================
# GET VIDEO STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_get_video_status_success():
    ctx = make_ctx(
        {
            "error": None,
            "data": {
                "video_id": "vid_001",
                "status": "complete",
                "video_url": "https://cdn.heygen.com/vid_001.mp4",
                "thumbnail_url": "https://cdn.heygen.com/vid_001_thumb.jpg",
                "duration": 12.5,
                "created_at": 1700000000,
            },
        }
    )
    result = await heygen_integration.execute_action("get_video_status", {"video_id": "vid_001"}, ctx)
    data = result.result.data["data"]
    assert data["video_id"] == "vid_001"
    assert data["status"] == "complete"
    assert data["video_url"] is not None


@pytest.mark.asyncio
async def test_get_video_status_pending():
    ctx = make_ctx({"error": None, "data": {"video_id": "vid_002", "status": "pending", "video_url": None}})
    result = await heygen_integration.execute_action("get_video_status", {"video_id": "vid_002"}, ctx)
    assert result.result.data["data"]["status"] == "pending"
    assert result.result.data["data"]["video_url"] is None


@pytest.mark.asyncio
async def test_get_video_status_uses_v1_endpoint():
    ctx = make_ctx({"error": None, "data": {"video_id": "vid_001", "status": "pending"}})
    await heygen_integration.execute_action("get_video_status", {"video_id": "vid_001"}, ctx)
    url = ctx.fetch.call_args.kwargs.get("url", "")
    assert "v1/video_status.get" in url
    assert "vid_001" in url


@pytest.mark.asyncio
async def test_get_video_status_error():
    ctx = make_ctx_error(RuntimeError("Connection refused"))
    result = await heygen_integration.execute_action("get_video_status", {"video_id": "vid_001"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Connection refused" in result.result.message

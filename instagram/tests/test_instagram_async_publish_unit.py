import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import instagram as instagram_mod  # noqa: E402

instagram_integration = instagram_mod.instagram

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def make_ctx_multi(responses):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(response) for response in responses])
    ctx.auth = {}
    return ctx


def publish_state(**overrides):
    state = {
        "media_type": "REELS",
        "phase": "MEDIA",
        "container_id": "container_123",
        "child_container_ids": [],
        "caption": "A test post",
        "attempt": 0,
    }
    state.update(overrides)
    return state


def test_async_action_descriptions_explain_automatic_completion():
    config_path = os.path.join(_parent, "config.json")
    with open(config_path, encoding="utf-8") as config_file:
        actions = json.load(config_file)["actions"]

    assert "Recommended for large media uploads" in actions["start_post"]["description"]
    assert "continues checking automatically" in actions["start_post"]["description"]
    assert "continues checking automatically" in actions["complete_post"]["description"]


def test_start_post_file_inputs_are_public_url_annotated():
    config_path = os.path.join(_parent, "config.json")
    with open(config_path, encoding="utf-8") as config_file:
        properties = json.load(config_file)["actions"]["start_post"]["input_schema"]["properties"]

    assert properties["media_url"]["x-autohive-input"] == "file-public-url"
    assert properties["children"]["items"]["properties"]["media_url"]["x-autohive-input"] == "file-public-url"


@pytest.mark.asyncio
async def test_start_post_reel_returns_processing_state_without_polling():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "reel_container"},
        ]
    )

    result = await instagram_integration.execute_action(
        "start_post",
        {
            "media_type": "VIDEO",
            "media_url": "https://example.com/video.mp4",
            "caption": "Video",
        },
        ctx,
    )

    data = result.result.data
    create_data = ctx.fetch.call_args_list[1].kwargs["data"]
    assert data["status"] == "PROCESSING"
    assert data["next_action"] == "complete_post"
    assert data["publish_state"] == {
        "media_type": "REELS",
        "phase": "MEDIA",
        "container_id": "reel_container",
        "child_container_ids": [],
        "caption": "Video",
        "attempt": 0,
    }
    assert create_data["media_type"] == "REELS"
    assert ctx.fetch.call_count == 2


@pytest.mark.asyncio
async def test_start_post_mixed_carousel_preserves_child_order():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "image_child"},
            {"id": "video_child"},
        ]
    )

    result = await instagram_integration.execute_action(
        "start_post",
        {
            "media_type": "CAROUSEL",
            "caption": "Mixed",
            "children": [
                {"media_type": "IMAGE", "media_url": "https://example.com/image.jpg"},
                {"media_type": "VIDEO", "media_url": "https://example.com/video.mp4"},
            ],
        },
        ctx,
    )

    data = result.result.data
    assert data["publish_state"]["phase"] == "CHILDREN"
    assert data["publish_state"]["child_container_ids"] == ["image_child", "video_child"]
    assert ctx.fetch.call_args_list[1].kwargs["data"] == {
        "is_carousel_item": "true",
        "image_url": "https://example.com/image.jpg",
    }
    assert ctx.fetch.call_args_list[2].kwargs["data"] == {
        "is_carousel_item": "true",
        "media_type": "VIDEO",
        "video_url": "https://example.com/video.mp4",
    }


@pytest.mark.asyncio
async def test_complete_post_publishes_ready_single_media():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {"id": "published_456"},
            {"permalink": "https://www.instagram.com/reel/ABC/"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert data["status"] == "PUBLISHED"
    assert data["media_id"] == "published_456"
    assert data["permalink"] == "https://www.instagram.com/reel/ABC/"
    assert data["next_action"] == ""
    assert ctx.fetch.call_args_list[2].kwargs["data"] == {"creation_id": "container_123"}


@pytest.mark.asyncio
async def test_complete_post_creates_parent_after_carousel_children_finish():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {"status_code": "FINISHED"},
            {"id": "parent_container"},
        ]
    )
    state = publish_state(
        media_type="CAROUSEL",
        phase="CHILDREN",
        container_id="",
        child_container_ids=["image_child", "video_child"],
        caption="Mixed",
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": state},
        ctx,
    )

    data = result.result.data
    assert data["status"] == "PROCESSING"
    assert data["publish_state"]["phase"] == "PARENT"
    assert data["publish_state"]["container_id"] == "parent_container"
    assert ctx.fetch.call_args_list[3].kwargs["data"] == {
        "media_type": "CAROUSEL",
        "caption": "Mixed",
        "children": "image_child,video_child",
    }


@pytest.mark.asyncio
@patch("actions.media.asyncio.sleep", new_callable=AsyncMock)
async def test_complete_post_returns_processing_and_updated_state_when_not_ready(mock_sleep):
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            *[{"status_code": "IN_PROGRESS"} for _ in range(6)],
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert data["status"] == "PROCESSING"
    assert data["next_action"] == "complete_post"
    assert data["publish_state"]["attempt"] == 1
    assert mock_sleep.await_count == 5
    assert ctx.fetch.call_count == 7


@pytest.mark.asyncio
async def test_complete_post_returns_failed_for_terminal_meta_status():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "ERROR", "status": "Video could not be processed"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert data["status"] == "FAILED"
    assert "Video could not be processed" in data["error"]
    assert data["next_action"] == ""


@pytest.mark.asyncio
async def test_complete_post_stops_after_maximum_automatic_attempts():
    ctx = make_ctx_multi([])

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state(attempt=12)},
        ctx,
    )

    data = result.result.data
    assert data["status"] == "FAILED"
    assert data["error"] == "Maximum automatic completion attempts exceeded"
    ctx.fetch.assert_not_called()

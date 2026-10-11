import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from autohive_integrations_sdk import ExecutionContext, FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import instagram as instagram_mod  # noqa: E402

instagram_integration = instagram_mod.instagram

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def make_ctx_multi(responses):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(
        side_effect=[response if isinstance(response, Exception) else ok(response) for response in responses]
    )
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
async def test_start_post_carousel_requires_children_before_fetching_account():
    ctx = make_ctx_multi([])

    result = await instagram_integration.execute_action(
        "start_post",
        {"media_type": "CAROUSEL"},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert "at least 2" in result.result.message
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("child_count", [1, 11])
async def test_start_post_carousel_rejects_out_of_range_child_counts(child_count):
    ctx = make_ctx_multi([])
    children = [
        {"media_type": "IMAGE", "media_url": f"https://example.com/image-{index}.jpg"} for index in range(child_count)
    ]

    result = await instagram_integration.execute_action(
        "start_post",
        {"media_type": "CAROUSEL", "children": children},
        ctx,
    )

    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_start_post_returns_action_error_when_media_url_is_missing():
    ctx = make_ctx_multi([])

    result = await instagram_integration.execute_action(
        "start_post",
        {"media_type": "REELS"},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "media_url is required for REELS"
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_start_post_returns_action_error_when_carousel_child_has_no_container_id():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {},
            {"id": "video_child"},
        ]
    )

    result = await instagram_integration.execute_action(
        "start_post",
        {
            "media_type": "CAROUSEL",
            "children": [
                {"media_type": "IMAGE", "media_url": "https://example.com/image.jpg"},
                {"media_type": "VIDEO", "media_url": "https://example.com/video.mp4"},
            ],
        },
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Instagram did not return a carousel child container ID"


@pytest.mark.asyncio
async def test_start_post_returns_action_error_when_media_container_id_is_missing():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {},
        ]
    )

    result = await instagram_integration.execute_action(
        "start_post",
        {"media_type": "IMAGE", "media_url": "https://example.com/image.jpg"},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Instagram did not return a media container ID"


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
async def test_complete_post_recovers_when_container_was_already_published():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "PUBLISHED"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert result.type == ResultType.ACTION
    assert data["status"] == "PUBLISHED"
    assert data["media_id"] == ""
    assert data["permalink"] == ""
    assert data["next_action"] == ""
    assert "already published" in data["message"]
    assert ctx.fetch.call_count == 2


@pytest.mark.asyncio
async def test_complete_post_preserves_success_when_permalink_lookup_fails():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(
        side_effect=[
            ok({"id": "17841400000000000"}),
            ok({"status_code": "FINISHED"}),
            ok({"id": "published_456"}),
            Exception("details lookup failed"),
        ]
    )
    ctx.auth = {}

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert result.type == ResultType.ACTION
    assert data["status"] == "PUBLISHED"
    assert data["media_id"] == "published_456"
    assert data["permalink"] == ""
    assert data["next_action"] == ""
    assert "permalink could not be retrieved" in data["message"]
    assert ctx.fetch.call_count == 4


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
async def test_complete_post_publishes_carousel_across_continuation_calls():
    children_ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {"status_code": "FINISHED"},
            {"id": "parent_container"},
        ]
    )
    initial_state = publish_state(
        media_type="CAROUSEL",
        phase="CHILDREN",
        container_id="",
        child_container_ids=["image_child", "video_child"],
        caption="Mixed",
        attempt=11,
    )

    parent_result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": initial_state},
        children_ctx,
    )

    parent_state = parent_result.result.data["publish_state"]
    assert parent_result.result.data["status"] == "PROCESSING"
    assert parent_state["phase"] == "PARENT"
    assert parent_state["attempt"] == 0

    parent_ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {"id": "published_carousel"},
            {"permalink": "https://www.instagram.com/p/CAROUSEL/"},
        ]
    )

    published_result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": parent_state},
        parent_ctx,
    )

    published_data = published_result.result.data
    assert published_data["status"] == "PUBLISHED"
    assert published_data["media_id"] == "published_carousel"
    assert published_data["permalink"] == "https://www.instagram.com/p/CAROUSEL/"
    assert published_data["publish_state"]["attempt"] == 1
    assert parent_ctx.fetch.call_args_list[2].kwargs["data"] == {"creation_id": "parent_container"}


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
async def test_complete_post_returns_action_error_for_terminal_meta_status():
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

    assert result.type == ResultType.ACTION_ERROR
    assert "Video could not be processed" in result.result.message


@pytest.mark.asyncio
async def test_complete_post_returns_action_error_when_carousel_parent_is_not_created():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {"status_code": "FINISHED"},
            {},
        ]
    )
    state = publish_state(
        media_type="CAROUSEL",
        phase="CHILDREN",
        container_id="",
        child_container_ids=["image_child", "video_child"],
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": state},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Instagram did not return a carousel container ID"


@pytest.mark.asyncio
async def test_complete_post_returns_action_error_for_invalid_state():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state(container_id="")},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "publish_state must identify a media or parent container"


@pytest.mark.asyncio
async def test_complete_post_reconciles_when_publish_has_no_media_id():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {},
            {"status_code": "FINISHED"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["status"] == "PROCESSING"
    assert data["publish_state"]["phase"] == "PUBLISHING"
    assert data["publish_state"]["container_id"] == "container_123"
    assert data["next_action"] == "complete_post"
    assert "do not start a new post" in data["message"]


@pytest.mark.asyncio
async def test_complete_post_preserves_success_when_publish_response_has_no_media_id():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            {},
            {"status_code": "PUBLISHED"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert result.type == ResultType.ACTION
    assert data["status"] == "PUBLISHED"
    assert data["media_id"] == ""
    assert data["permalink"] == ""
    assert data["next_action"] == ""
    assert "did not return its media ID" in data["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "publish_error",
    [TimeoutError("publish response timed out"), HTTPError(400, "retry rejected"), HTTPError(500, "server error")],
)
async def test_complete_post_reconciles_accepted_publish_after_request_error(publish_error):
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            publish_error,
            {"status_code": "PUBLISHED"},
        ]
    )

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state()},
        ctx,
    )

    data = result.result.data
    assert result.type == ResultType.ACTION
    assert data["status"] == "PUBLISHED"
    assert data["next_action"] == ""
    assert data["media_id"] == ""
    assert data["permalink"] == ""


@pytest.mark.asyncio
async def test_complete_post_reconciles_real_sdk_timeout_then_retry_rejection(unused_tcp_port, monkeypatch):
    """Local repro: accept publication, lose the response, then reject the SDK retry."""
    publish_requests = []
    publications = []
    release_publish_response = asyncio.Event()

    async def account(request):
        return web.json_response({"id": "account_123"})

    async def container_status(request):
        return web.json_response({"status_code": "PUBLISHED" if publications else "FINISHED"})

    async def publish(request):
        creation_id = (await request.post())["creation_id"]
        publish_requests.append(creation_id)
        if publications:
            return web.json_response({"error": {"message": "Already published"}}, status=400)
        publications.append(creation_id)
        await release_publish_response.wait()
        return web.json_response({"id": "published_123"})

    server = web.Application()
    server.router.add_get("/me", account)
    server.router.add_get("/container_123", container_status)
    server.router.add_post("/account_123/media_publish", publish)
    runner = web.AppRunner(server)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
        base_url = f"http://127.0.0.1:{unused_tcp_port}"
        monkeypatch.setattr("helpers.INSTAGRAM_GRAPH_API_BASE", base_url)
        monkeypatch.setattr("actions.media.INSTAGRAM_GRAPH_API_BASE", base_url)

        async with ExecutionContext(request_config={"timeout": 1, "max_retries": 1}) as ctx:
            result = await instagram_integration.execute_action(
                "complete_post", {"publish_state": publish_state()}, ctx
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["status"] == "PUBLISHED"
        assert data["media_id"] == ""
        assert data["permalink"] == ""
        assert data["next_action"] == ""
        assert publish_requests == ["container_123", "container_123"]
        assert publications == ["container_123"]
    finally:
        release_publish_response.set()
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["MEDIA", "PUBLISHING"])
@pytest.mark.parametrize("terminal_status", ["ERROR", "EXPIRED", "FAILED"])
async def test_complete_post_reports_confirmed_failure_during_reconciliation(phase, terminal_status):
    responses = [{"id": "17841400000000000"}]
    if phase == "MEDIA":
        responses.extend([{"status_code": "FINISHED"}, TimeoutError("publish response timed out")])
    responses.append({"status_code": terminal_status, "status": "Container cannot be published"})
    ctx = make_ctx_multi(responses)

    result = await instagram_integration.execute_action(
        "complete_post", {"publish_state": publish_state(phase=phase)}, ctx
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == f"Media container {terminal_status.lower()}: Container cannot be published"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", ["FINISHED", "IN_PROGRESS"])
@patch("actions.media.asyncio.sleep", new_callable=AsyncMock)
async def test_complete_post_does_not_republish_an_uncertain_container(mock_sleep, status_code):
    ctx = make_ctx_multi([{"id": "17841400000000000"}, *[{"status_code": status_code} for _ in range(6)]])
    state = publish_state(phase="PUBLISHING", attempt=5)

    result = await instagram_integration.execute_action("complete_post", {"publish_state": state}, ctx)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["status"] == "PROCESSING"
    assert data["publish_state"] == {**state, "attempt": 6}
    assert data["next_action"] == "complete_post"
    assert all(call.kwargs["method"] == "GET" for call in ctx.fetch.call_args_list)

    recovered_ctx = make_ctx_multi([{"id": "17841400000000000"}, {"status_code": "PUBLISHED"}])
    recovered = await instagram_integration.execute_action(
        "complete_post", {"publish_state": data["publish_state"]}, recovered_ctx
    )

    assert recovered.type == ResultType.ACTION
    assert recovered.result.data["status"] == "PUBLISHED"
    assert recovered.result.data["next_action"] == ""
    assert all(call.kwargs["method"] == "GET" for call in recovered_ctx.fetch.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("publish_error", [TimeoutError("publish response timed out"), HTTPError(500, "server error")])
async def test_complete_post_returns_resumable_state_when_publish_outcome_is_uncertain(publish_error):
    initial_ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "FINISHED"},
            publish_error,
            TimeoutError("status check timed out"),
        ]
    )

    uncertain_result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state(attempt=11)},
        initial_ctx,
    )

    uncertain_data = uncertain_result.result.data
    uncertain_state = uncertain_data["publish_state"]
    assert uncertain_result.type == ResultType.ACTION
    assert uncertain_data["status"] == "PROCESSING"
    assert uncertain_data["next_action"] == "complete_post"
    assert uncertain_state["phase"] == "PUBLISHING"
    assert uncertain_state["attempt"] == 0
    assert "do not start a new post" in uncertain_data["message"]

    reconciliation_ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"status_code": "PUBLISHED"},
        ]
    )
    published_result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": uncertain_state},
        reconciliation_ctx,
    )

    assert published_result.result.data["status"] == "PUBLISHED"
    assert reconciliation_ctx.fetch.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", ["account", "container"])
async def test_complete_post_resumes_after_a_later_reconciliation_error(failure_at):
    responses = [TimeoutError("account check timed out")]
    if failure_at == "container":
        responses = [{"id": "17841400000000000"}, TimeoutError("status check timed out")]
    failed_ctx = make_ctx_multi(responses)
    state = publish_state(phase="PUBLISHING", attempt=3)

    result = await instagram_integration.execute_action("complete_post", {"publish_state": state}, failed_ctx)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["status"] == "PROCESSING"
    assert data["publish_state"] == {**state, "attempt": 4}
    assert data["next_action"] == "complete_post"
    assert "do not start a new post" in data["message"]
    assert state["attempt"] == 3

    recovered_ctx = make_ctx_multi([{"id": "17841400000000000"}, {"status_code": "PUBLISHED"}])
    recovered = await instagram_integration.execute_action(
        "complete_post", {"publish_state": data["publish_state"]}, recovered_ctx
    )

    assert recovered.type == ResultType.ACTION
    assert recovered.result.data["status"] == "PUBLISHED"
    assert recovered.result.data["next_action"] == ""


@pytest.mark.asyncio
async def test_complete_post_stops_reconciliation_with_an_unknown_outcome():
    failed_ctx = make_ctx_multi([{"id": "17841400000000000"}, TimeoutError("status check timed out")])
    state = publish_state(phase="PUBLISHING", attempt=11)

    last_check = await instagram_integration.execute_action("complete_post", {"publish_state": state}, failed_ctx)

    assert last_check.type == ResultType.ACTION
    assert last_check.result.data["status"] == "PROCESSING"
    assert last_check.result.data["publish_state"]["attempt"] == 12

    exhausted_ctx = make_ctx_multi([])
    result = await instagram_integration.execute_action(
        "complete_post", {"publish_state": last_check.result.data["publish_state"]}, exhausted_ctx
    )

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["status"] == "UNKNOWN"
    assert data["publish_state"] == {**state, "attempt": 13}
    assert data["next_action"] == ""
    assert data["retry_after_seconds"] == 0
    assert data["media_id"] == ""
    assert "do not start a new post" in data["message"]

    from jsonschema import validate

    with open(os.path.join(_parent, "config.json"), encoding="utf-8") as config_file:
        output_schema = json.load(config_file)["actions"]["complete_post"]["output_schema"]
    validate(data, output_schema)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses,state,error_message",
    [
        (
            [Exception("account lookup failed")],
            publish_state(),
            "account lookup failed",
        ),
        (
            [
                {"id": "17841400000000000"},
                Exception("status polling failed"),
            ],
            publish_state(),
            "status polling failed",
        ),
        (
            [
                {"id": "17841400000000000"},
                {"status_code": "FINISHED"},
                {"status_code": "FINISHED"},
                Exception("parent creation failed"),
            ],
            publish_state(
                media_type="CAROUSEL",
                phase="CHILDREN",
                container_id="",
                child_container_ids=["image_child", "video_child"],
            ),
            "parent creation failed",
        ),
        (
            [
                {"id": "17841400000000000"},
                {"status_code": "FINISHED"},
                HTTPError(400, "publishing rejected"),
                {"status_code": "ERROR", "status": "Video could not be processed"},
            ],
            publish_state(),
            "Media container error: Video could not be processed",
        ),
    ],
)
async def test_complete_post_returns_action_error_for_provider_failures(responses, state, error_message):
    ctx = make_ctx_multi(responses)

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": state},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == error_message


@pytest.mark.asyncio
async def test_complete_post_stops_after_maximum_automatic_attempts():
    ctx = make_ctx_multi([])

    result = await instagram_integration.execute_action(
        "complete_post",
        {"publish_state": publish_state(attempt=12)},
        ctx,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert "maximum automatic completion attempts" in result.result.message
    ctx.fetch.assert_not_called()

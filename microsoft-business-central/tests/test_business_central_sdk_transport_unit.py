"""Exercise direct HTTP transport without contacting Business Central."""

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientError
from autohive_integrations_sdk import ExecutionContext, ResultType

from businesscentral import BusinessCentralError, businesscentral, request as direct_request

pytestmark = pytest.mark.unit
INPUTS = {
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "environment": "Sandbox",
    "company_id": "22222222-2222-2222-2222-222222222222",
}
ORDER = "44444444-4444-4444-4444-444444444444"
AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {"access_token": "fake-transport-test-token"},  # nosec B105
}


def response_manager(status, body, headers=None):
    """Substitute HTTP I/O; integration transport and action execution remain real."""
    response = MagicMock(status=status, ok=status < 400)
    response.headers = {"Content-Type": "application/json", **(headers or {})}
    response.json = AsyncMock(return_value=body)
    response.text = AsyncMock(return_value=json.dumps(body))
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=response)
    manager.__aexit__ = AsyncMock(return_value=False)
    return manager


def transport_context(*responses):
    context = ExecutionContext(auth=AUTH)
    context.fetch = AsyncMock(side_effect=AssertionError("SDK fetch must not be used"))
    context._session = MagicMock(closed=False)
    context._session.request.side_effect = list(responses)
    return context


@pytest.mark.parametrize("content_type", ["application/json", "text/plain"])
async def test_provider_data_is_absent_from_action_errors_and_all_log_channels(capsys, caplog, content_type):
    body_sentinel = "PRIVATE_BUSINESS_DATA_SENTINEL"
    path_sentinel = "PRIVATE_PATH_SENTINEL"
    query_sentinel = "PRIVATE_QUERY_SENTINEL"
    header_sentinel = "PRIVATE_HEADER_SENTINEL"
    manager = response_manager(
        400,
        {"error": {"message": body_sentinel}},
        {"Content-Type": content_type, "X-Private-Value": header_sentinel},
    )
    context = transport_context(manager)
    with patch("businesscentral.base_url", return_value=f"https://example.invalid/{path_sentinel}"):
        result = await businesscentral.execute_action("list_items", dict(INPUTS, item_number=query_sentinel), context)

    assert result.type == ResultType.ACTION_ERROR
    captured = capsys.readouterr()
    for sentinel in (body_sentinel, path_sentinel, query_sentinel, header_sentinel):
        for channel in (captured.out, captured.err, caplog.text, result.result.message):
            assert sentinel not in channel
    context._session.request.assert_called_once()
    context.fetch.assert_not_awaited()


async def test_direct_503_short_retry_after_header_controls_integration_backoff():
    context = transport_context(
        response_manager(503, {"error": "temporarily unavailable"}, {"rEtRy-AfTeR": "2"}),
        response_manager(200, {"value": []}),
    )
    with patch("businesscentral.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await businesscentral.execute_action("list_items", INPUTS, context)
    assert result.type == ResultType.ACTION
    assert result.result.data["records"] == []
    sleep.assert_awaited_once_with(2)
    assert context._session.request.call_count == 2


async def test_direct_503_over_limit_retry_after_returns_without_sleep_or_retry():
    context = transport_context(response_manager(503, {"error": "temporarily unavailable"}, {"retry-after": "60"}))
    with patch("businesscentral.asyncio.sleep", new_callable=AsyncMock) as sleep:
        result = await businesscentral.execute_action("list_items", INPUTS, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "503" in result.result.message
    sleep.assert_not_awaited()
    context._session.request.assert_called_once()


@asynccontextmanager
async def lost_write_server(write_method):
    """Accept one write, then drop its response to detect automatic replay."""
    state = {"writes": 0, "primed_writer": None, "pooled_write": False}
    writers = set()
    handlers = set()

    async def handle(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        writers.add(writer)
        try:
            while True:
                request = await reader.readuntil(b"\r\n\r\n")
                method, path, _ = request.split(b"\r\n", 1)[0].split(b" ")
                for header in request.split(b"\r\n")[1:]:
                    if header.lower().startswith(b"content-length:"):
                        await reader.readexactly(int(header.split(b":", 1)[1]))
                if method == write_method.encode():
                    state["writes"] += 1
                    if state["writes"] == 1:
                        state["pooled_write"] = writer is state["primed_writer"]
                        return
                    status, body = b"404 Not Found", b'{"error":"already removed"}'
                else:
                    assert method == b"GET" and path == b"/prime"
                    state["primed_writer"] = writer
                    status, body = b"200 OK", b"{}"
                writer.write(
                    b"HTTP/1.1 "
                    + status
                    + b"\r\nContent-Type: application/json\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\n\r\n"
                    + body
                )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            writers.discard(writer)
            handlers.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        server.close()
        await server.wait_closed()
        for writer in tuple(writers):
            writer.close()
        if handlers:
            await asyncio.wait_for(asyncio.gather(*tuple(handlers)), timeout=5)


@pytest.mark.parametrize(
    "method,action,extra",
    [
        ("DELETE", "remove_purchase_order", {"purchase_order_id": ORDER, "etag": 'W/"current"'}),
        ("POST", "create_purchase_order", {"vendor_number": "V1"}),
    ],
)
async def test_accepted_write_with_lost_response_is_not_replayed_and_returns_uncertain_outcome(method, action, extra):
    async with lost_write_server(method) as (origin, state):
        async with ExecutionContext(auth=AUTH, request_config={"max_retries": 3, "timeout": 5}) as context:
            await direct_request(context, f"{origin}/prime")
            with patch("businesscentral.base_url", return_value=origin):
                result = await asyncio.wait_for(
                    businesscentral.execute_action(action, dict(INPUTS, **extra), context),
                    timeout=5,
                )
    assert state["pooled_write"], "The write must use the primed connection to exercise aiohttp's replay path."
    assert state["writes"] == 1
    assert result.type == ResultType.ACTION_ERROR
    assert "outcome is unknown" in result.result.message
    assert "not found" not in result.result.message


@pytest.mark.parametrize(
    "action,extra",
    [
        ("list_items", {}),
        ("create_purchase_order", {"vendor_number": "V1"}),
        ("remove_purchase_order", {"purchase_order_id": ORDER, "etag": 'W/"current"'}),
    ],
)
@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 412, 429, 500])
async def test_error_bodies_are_never_read_or_logged(action, extra, status, capsys, caplog):
    manager = response_manager(status, {"error": "PERSON_NAME_SENTINEL person@example.invalid"}, {"Retry-After": "60"})
    context = transport_context(manager)
    result = await businesscentral.execute_action(action, dict(INPUTS, **extra), context)
    assert result.type == ResultType.ACTION_ERROR
    resp = manager.__aenter__.return_value
    resp.json.assert_not_awaited()
    resp.text.assert_not_awaited()
    captured = capsys.readouterr()
    for channel in [captured.out, captured.err, caplog.text, result.result.message]:
        assert "PERSON_NAME_SENTINEL" not in channel
        assert "person@example.invalid" not in channel
        assert AUTH["credentials"]["access_token"] not in channel
    context.fetch.assert_not_awaited()


async def test_direct_request_sends_auth_timeout_and_disables_redirects_and_replay():
    context = transport_context(response_manager(201, {"id": ORDER}))
    result = await businesscentral.execute_action("create_purchase_order", dict(INPUTS, vendor_number="V1"), context)
    assert result.type == ResultType.ACTION
    args = context._session.request.call_args.kwargs
    assert args["method"] == "POST"
    assert args["json"] == {"vendorNumber": "V1"}
    assert args["headers"]["Authorization"] == "Bearer " + AUTH["credentials"]["access_token"]
    assert args["timeout"].total == context.config["timeout"]
    assert args["allow_redirects"] is False
    assert args["raise_for_status"] is False
    assert args["ssl"] is True
    assert context._session._retry_connection is False
    context.fetch.assert_not_awaited()


async def test_redirect_is_not_followed_or_parsed():
    manager = response_manager(302, {}, {"Location": "https://example.invalid/private"})
    context = transport_context(manager)
    result = await businesscentral.execute_action("list_items", INPUTS, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "302" in result.result.message
    context._session.request.assert_called_once()
    manager.__aenter__.return_value.json.assert_not_awaited()


@pytest.mark.parametrize("status,method", [(200, "GET"), (201, "POST")])
async def test_malformed_success_body_is_sanitized(status, method, capsys, caplog):
    manager = response_manager(status, {})
    manager.__aenter__.return_value.json.side_effect = ValueError("PERSON_NAME_SENTINEL person@example.invalid")
    context = transport_context(manager)
    action = "list_items" if method == "GET" else "create_purchase_order"
    inputs = INPUTS if method == "GET" else dict(INPUTS, vendor_number="V1")
    result = await businesscentral.execute_action(action, inputs, context)
    assert result.type == ResultType.ACTION_ERROR
    if method == "POST":
        assert "before retrying" in result.result.message
    captured = capsys.readouterr()
    for channel in [captured.out, captured.err, caplog.text, result.result.message]:
        assert "PERSON_NAME_SENTINEL" not in channel
        assert "person@example.invalid" not in channel


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
async def test_transport_exception_is_replaced_without_exposing_its_traceback(method):
    context = transport_context()
    context._session.request.side_effect = ClientConnectionError("PRIVATE_URL_SENTINEL person@example.invalid")
    with pytest.raises(ClientError) as excinfo:
        await direct_request(context, "https://example.invalid/private", method=method)
    rendered = "".join(traceback.format_exception(excinfo.value))
    assert "PRIVATE_URL_SENTINEL" not in rendered
    assert "person@example.invalid" not in rendered
    assert excinfo.value.__suppress_context__ is True
    context._session.request.assert_called_once()


async def test_empty_delete_response_is_not_parsed():
    manager = response_manager(204, None)
    context = transport_context(manager)
    result = await businesscentral.execute_action(
        "remove_purchase_order", dict(INPUTS, purchase_order_id=ORDER, etag='W/"current"'), context
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == {"purchase_order_id": ORDER, "deleted": True}
    manager.__aenter__.return_value.json.assert_not_awaited()
    manager.__aenter__.return_value.text.assert_not_awaited()


async def test_unknown_replay_control_fails_before_request():
    context = transport_context()
    del context._session._retry_connection
    with pytest.raises(BusinessCentralError, match="replay cannot be disabled"):
        await direct_request(context, "https://example.invalid/private", method="DELETE")
    context._session.request.assert_not_called()

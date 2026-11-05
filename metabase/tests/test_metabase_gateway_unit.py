"""Gateway tests use dummy credentials and a local HTTP server; production requires HTTPS."""

import asyncio
import importlib
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
import pytest

from metabase.metabase import _api, _gateway_request, get_auth_headers, metabase
from autohive_integrations_sdk import HTTPError, ResultType

pytestmark = pytest.mark.unit

GATEWAY_SECRET = "dummy-gateway-secret"  # nosec B105


def configure(context, name="X-Gateway-Secret", value=GATEWAY_SECRET):
    context.auth["credentials"].update(gateway_header_name=name, gateway_header_value=value)
    return context


@asynccontextmanager
async def server(handler):
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("X-Gateway", ""),
        ("", GATEWAY_SECRET),
        (None, GATEWAY_SECRET),
        (123, GATEWAY_SECRET),
        ("X-Gateway", 123),
        ("Bad Header", GATEWAY_SECRET),
        ("X-Gateway\r\nInjected", GATEWAY_SECRET),
        ("X-API-KEY", GATEWAY_SECRET),
        ("hOsT", GATEWAY_SECRET),
        ("Content-Length", GATEWAY_SECRET),
        ("Transfer-Encoding", GATEWAY_SECRET),
        ("Connection", GATEWAY_SECRET),
        ("X-Gateway", "a\r\nb"),
        ("X-Gateway", "a\x00b"),
        ("X-Gateway", "a\x7fb"),
        ("X-Gateway", "é"),
        ("X-Gateway", "   "),
    ],
)
def test_invalid_gateway_credentials(mock_context, name, value):
    configure(mock_context, name, value)
    with pytest.raises(ValueError) as error:
        get_auth_headers(mock_context)
    assert GATEWAY_SECRET not in str(error.value)


@pytest.mark.parametrize("name,value", [(None, None), ("", "")])
def test_empty_gateway_fields_preserve_existing_auth(mock_context, name, value):
    configure(mock_context, name, value)
    assert get_auth_headers(mock_context) == {
        "x-api-key": "mb_test_api_key",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])
async def test_gateway_receives_both_headers_and_request_body(mock_context, monkeypatch, method):
    configure(mock_context)
    received = []

    async def handler(request):
        received.append((request.method, dict(request.headers), await request.json(), request.query["q"]))
        return web.json_response({"id": 7})

    original = _gateway_request
    async with server(handler) as base:

        async def local_request(url, method, headers, **kwargs):
            assert url == "https://metabase.test/api/example?q=test"
            return await original(base + "/api/example?q=test", method, headers, **kwargs)

        monkeypatch.setattr(importlib.import_module("metabase.metabase"), "_gateway_request", local_request)
        assert await _api(mock_context, method, "/example?q=test", json={"name": "example"}) == {"id": 7}

    assert received == [(method, received[0][1], {"name": "example"}, "test")]
    assert received[0][1]["X-Gateway-Secret"] == GATEWAY_SECRET
    assert received[0][1]["x-api-key"] == "mb_test_api_key"
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_redirects_never_receive_credentials(mock_context, status):
    hits = []

    async def target(request):
        hits.append(request.path)
        return web.json_response({"id": 1})

    async with server(target) as destination:

        async def redirect(request):
            return web.Response(status=status, headers={"Location": destination + "/capture"})

        async with server(redirect) as source:
            with pytest.raises(ValueError, match="redirected"):
                await _gateway_request(source, "POST", get_auth_headers(configure(mock_context)), json={})
    assert hits == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 500])
async def test_error_bodies_do_not_expose_secrets(mock_context, caplog, capsys, status):
    async def handler(request):
        return web.Response(status=status, text=f"{GATEWAY_SECRET} mb_test_api_key")

    async with server(handler) as base:
        with pytest.raises(HTTPError) as error:
            await _gateway_request(base, "GET", get_auth_headers(configure(mock_context)))
    assert error.value.status == status
    output = str(error.value) + repr(error.value.response_data) + caplog.text + str(capsys.readouterr())
    assert GATEWAY_SECRET not in output
    assert "mb_test_api_key" not in output


@pytest.mark.asyncio
async def test_transport_errors_are_safe(mock_context, monkeypatch):
    def fail(*args, **kwargs):
        raise aiohttp.ClientConnectionError(f"reflected {GATEWAY_SECRET}")

    monkeypatch.setattr(aiohttp.ClientSession, "request", fail)
    with pytest.raises(ValueError, match="Could not connect") as error:
        await _gateway_request("https://metabase.test", "GET", get_auth_headers(configure(mock_context)))
    assert GATEWAY_SECRET not in str(error.value)


@pytest.mark.asyncio
async def test_timeout_does_not_repeat_writes(mock_context):
    calls = []

    async def handler(request):
        calls.append(request.method)
        await asyncio.sleep(0.05)
        return web.json_response({"id": 1})

    async with server(handler) as base:
        with pytest.raises(asyncio.TimeoutError):
            await _gateway_request(base, "POST", get_auth_headers(configure(mock_context)), timeout=0.01, json={})
    assert calls == ["POST"]


@pytest.mark.asyncio
async def test_html_login_page_is_safe(mock_context):
    async def handler(request):
        return web.Response(text=f"<html>{GATEWAY_SECRET}</html>")

    async with server(handler) as base:
        with pytest.raises(ValueError, match="isn't JSON") as error:
            await _gateway_request(base, "GET", get_auth_headers(configure(mock_context)))
    assert GATEWAY_SECRET not in str(error.value)


@pytest.mark.asyncio
async def test_invalid_configuration_fails_action_before_network(mock_context):
    configure(mock_context, "Host")
    result = await metabase.execute_action("get_current_user", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


def test_action_error_redacts_credentials_before_truncating(mock_context):
    from metabase.metabase import _error_message

    secret = "mb_test_api_key" + "long-secret-" * 60
    configure(mock_context, value=secret)
    message = _error_message(ValueError(f"{secret} mb_test_api_key"), context=mock_context)
    assert message == "[REDACTED] [REDACTED]"


@pytest.mark.asyncio
async def test_gateway_still_requires_https(mock_context):
    configure(mock_context)
    mock_context.auth["credentials"]["base_url"] = "http://metabase.test"
    with pytest.raises(ValueError, match="https"):
        await _api(mock_context, "GET", "/user/current")
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_committed_put_is_not_replayed_after_disconnect(mock_context):
    committed = []

    async def handler(request):
        committed.append(await request.json())
        # Simulate a committed dashboard update whose response is lost.
        request.transport.close()
        return web.Response()

    body = {"dashcards": [{"id": -1, "card_id": 7}]}
    async with server(handler) as base:
        with pytest.raises(ValueError, match="Could not connect"):
            await _gateway_request(base, "PUT", get_auth_headers(configure(mock_context)), json=body)
    assert committed == [body]

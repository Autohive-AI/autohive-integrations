import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from shopify_admin import (
    ListCustomersHandler,
    build_headers,
    execute_graphql,
    get_access_token,
    get_shop_url,
    shopify_admin,
)

pytestmark = pytest.mark.unit


CLIENT_SECRET = uuid4().hex
ACCESS_TOKEN = uuid4().hex
FIRST_TOKEN = uuid4().hex
REFRESHED_TOKEN = uuid4().hex
SECOND_TOKEN = uuid4().hex
MISSING_CREDENTIAL = str()


@pytest.fixture
def custom_auth_context():
    context = MagicMock()
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "shop_url": "example-store.myshopify.com",
            "client_id": "test-client-id",
            "client_secret": CLIENT_SECRET,
        },
    }
    context.fetch = AsyncMock()
    return context


def test_config_uses_custom_auth_fields():
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text())

    assert config["auth"]["type"] == "custom"
    assert set(config["auth"]["fields"]["properties"]) == {"shop_url", "client_id", "client_secret"}
    # Keep fields optional in the connection schema because the deployed custom-auth
    # form mishandles non-empty required arrays. Runtime helpers validate all fields.
    assert config["auth"]["fields"]["required"] == []
    assert config["auth"]["fields"]["properties"]["client_secret"]["format"] == "password"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("example-store.myshopify.com", "example-store.myshopify.com"),
        ("HTTPS://EXAMPLE-STORE.MYSHOPIFY.COM/", "example-store.myshopify.com"),
    ],
)
def test_get_shop_url_normalizes_valid_domains(custom_auth_context, value, expected):
    custom_auth_context.auth["credentials"]["shop_url"] = value

    assert get_shop_url(custom_auth_context) == expected


@pytest.mark.parametrize(
    "value",
    ["example.com", "example-store.myshopify.com.evil.test", "example-store.myshopify.com/admin"],
)
def test_get_shop_url_rejects_invalid_domains(custom_auth_context, value):
    custom_auth_context.auth["credentials"]["shop_url"] = value

    with pytest.raises(ValueError, match="your-store.myshopify.com"):
        get_shop_url(custom_auth_context)


async def test_get_access_token_uses_client_credentials_grant(custom_auth_context):
    custom_auth_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "access_token": ACCESS_TOKEN,
            "expires_in": 86399,
        },
    )

    token = await get_access_token(custom_auth_context)

    assert token == ACCESS_TOKEN
    custom_auth_context.fetch.assert_awaited_once_with(
        "https://example-store.myshopify.com/admin/oauth/access_token",
        method="POST",
        data={
            "grant_type": "client_credentials",
            "client_id": "test-client-id",
            "client_secret": CLIENT_SECRET,
        },
        content_type="application/x-www-form-urlencoded",
    )


async def test_get_access_token_reuses_cached_token(custom_auth_context):
    custom_auth_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"access_token": ACCESS_TOKEN, "expires_in": 86399},
    )

    first_token = await get_access_token(custom_auth_context)
    second_token = await get_access_token(custom_auth_context)

    assert first_token == second_token == ACCESS_TOKEN
    custom_auth_context.fetch.assert_awaited_once()


async def test_get_access_token_refreshes_near_expiry(custom_auth_context, monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr("shopify_admin.monotonic", lambda: current_time)
    custom_auth_context.fetch.side_effect = [
        FetchResponse(
            status=200,
            headers={},
            data={"access_token": FIRST_TOKEN, "expires_in": 120},
        ),
        FetchResponse(
            status=200,
            headers={},
            data={"access_token": REFRESHED_TOKEN, "expires_in": 120},
        ),
    ]

    assert await get_access_token(custom_auth_context) == FIRST_TOKEN
    current_time += 59
    assert await get_access_token(custom_auth_context) == FIRST_TOKEN
    current_time += 1
    assert await get_access_token(custom_auth_context) == REFRESHED_TOKEN
    assert custom_auth_context.fetch.await_count == 2


async def test_get_access_token_does_not_reuse_cache_after_credentials_change(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        FetchResponse(
            status=200,
            headers={},
            data={"access_token": FIRST_TOKEN, "expires_in": 86399},
        ),
        FetchResponse(
            status=200,
            headers={},
            data={"access_token": SECOND_TOKEN, "expires_in": 86399},
        ),
    ]

    assert await get_access_token(custom_auth_context) == FIRST_TOKEN
    custom_auth_context.auth["credentials"]["client_id"] = "different-client-id"
    assert await get_access_token(custom_auth_context) == SECOND_TOKEN
    assert custom_auth_context.fetch.await_count == 2


async def test_multiple_graphql_requests_exchange_credentials_once(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        FetchResponse(
            status=200,
            headers={},
            data={"access_token": ACCESS_TOKEN, "expires_in": 86399},
        ),
        FetchResponse(status=200, headers={}, data={"data": {"shop": {"id": "gid://shopify/Shop/1"}}}),
        FetchResponse(status=200, headers={}, data={"data": {"shop": {"id": "gid://shopify/Shop/1"}}}),
    ]

    await execute_graphql(custom_auth_context, "query { shop { id } }")
    await execute_graphql(custom_auth_context, "query { shop { id } }")

    assert custom_auth_context.fetch.await_count == 3
    token_calls = [
        call for call in custom_auth_context.fetch.await_args_list if call.args[0].endswith("/admin/oauth/access_token")
    ]
    assert len(token_calls) == 1


async def test_get_access_token_rejects_missing_credentials(custom_auth_context):
    custom_auth_context.auth["credentials"]["client_secret"] = MISSING_CREDENTIAL

    with pytest.raises(ValueError, match="client_secret"):
        await get_access_token(custom_auth_context)

    custom_auth_context.fetch.assert_not_awaited()


async def test_build_headers_uses_exchanged_token(custom_auth_context):
    custom_auth_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"access_token": ACCESS_TOKEN},
    )

    headers = await build_headers(custom_auth_context)

    assert headers == {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


async def test_action_exchanges_credentials_before_admin_api_call(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": ACCESS_TOKEN}),
        FetchResponse(
            status=200,
            headers={},
            data={"data": {"customers": {"nodes": [{"id": "gid://shopify/Customer/123"}]}}},
        ),
    ]

    result = await ListCustomersHandler().execute({"limit": 1}, custom_auth_context)

    assert result.data["success"] is True
    assert result.data["count"] == 1
    assert custom_auth_context.fetch.await_count == 2
    admin_call = custom_auth_context.fetch.await_args_list[1]
    assert admin_call.args[0] == "https://example-store.myshopify.com/admin/api/2026-07/graphql.json"
    assert admin_call.kwargs["method"] == "POST"
    assert admin_call.kwargs["json"]["variables"] == {"first": 1, "query": None}
    assert admin_call.kwargs["headers"]["X-Shopify-Access-Token"] == ACCESS_TOKEN


async def test_create_customer_error_returns_action_error(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": ACCESS_TOKEN}),
        Exception("Shopify rejected the customer"),
    ]

    result = await shopify_admin.execute_action(
        "create_customer",
        {"email": "customer@example.com"},
        custom_auth_context,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Shopify rejected the customer"

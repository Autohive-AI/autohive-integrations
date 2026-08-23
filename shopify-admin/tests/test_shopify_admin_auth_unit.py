import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shopify_admin import ListCustomersHandler, build_headers, get_access_token, get_shop_url, shopify_admin

pytestmark = pytest.mark.unit


@pytest.fixture
def custom_auth_context():
    context = MagicMock()
    context.auth = {
        "shop_url": "example-store.myshopify.com",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",  # nosec B105
    }
    context.fetch = AsyncMock()
    return context


def test_config_uses_custom_auth_fields():
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text())

    assert config["auth"]["type"] == "custom"
    assert set(config["auth"]["fields"]["properties"]) == {"shop_url", "client_id", "client_secret"}
    assert set(config["auth"]["fields"]["required"]) == {"shop_url", "client_id", "client_secret"}
    assert config["auth"]["fields"]["properties"]["client_secret"]["format"] == "password"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("example-store.myshopify.com", "example-store.myshopify.com"),
        ("HTTPS://EXAMPLE-STORE.MYSHOPIFY.COM/", "example-store.myshopify.com"),
    ],
)
def test_get_shop_url_normalizes_valid_domains(custom_auth_context, value, expected):
    custom_auth_context.auth["shop_url"] = value

    assert get_shop_url(custom_auth_context) == expected


@pytest.mark.parametrize(
    "value",
    ["example.com", "example-store.myshopify.com.evil.test", "example-store.myshopify.com/admin"],
)
def test_get_shop_url_rejects_invalid_domains(custom_auth_context, value):
    custom_auth_context.auth["shop_url"] = value

    with pytest.raises(ValueError, match="your-store.myshopify.com"):
        get_shop_url(custom_auth_context)


async def test_get_access_token_uses_client_credentials_grant(custom_auth_context):
    custom_auth_context.fetch.return_value = {
        "access_token": "test-access-token",  # nosec B105
        "expires_in": 86399,
    }

    token = await get_access_token(custom_auth_context)

    assert token == "test-access-token"  # nosec B105
    custom_auth_context.fetch.assert_awaited_once_with(
        "https://example-store.myshopify.com/admin/oauth/access_token",
        method="POST",
        data={
            "grant_type": "client_credentials",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
        },
        content_type="application/x-www-form-urlencoded",
    )


async def test_get_access_token_rejects_missing_credentials(custom_auth_context):
    custom_auth_context.auth["client_secret"] = ""  # nosec B105

    with pytest.raises(ValueError, match="client_secret"):
        await get_access_token(custom_auth_context)

    custom_auth_context.fetch.assert_not_awaited()


async def test_build_headers_uses_exchanged_token(custom_auth_context):
    custom_auth_context.fetch.return_value = {"access_token": "test-access-token"}  # nosec B105

    headers = await build_headers(custom_auth_context)

    assert headers == {
        "X-Shopify-Access-Token": "test-access-token",
        "Content-Type": "application/json",
    }


async def test_action_exchanges_credentials_before_admin_api_call(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        {"access_token": "test-access-token"},  # nosec B105
        {"customers": [{"id": 123}]},
    ]

    result = await ListCustomersHandler().execute({"limit": 1}, custom_auth_context)

    assert result.data["success"] is True
    assert result.data["count"] == 1
    assert custom_auth_context.fetch.await_count == 2
    admin_call = custom_auth_context.fetch.await_args_list[1]
    assert admin_call.args[0] == "https://example-store.myshopify.com/admin/api/2026-07/customers.json"
    assert admin_call.kwargs["headers"]["X-Shopify-Access-Token"] == "test-access-token"


async def test_create_customer_error_response_matches_object_schema(custom_auth_context):
    custom_auth_context.fetch.side_effect = [
        {"access_token": "test-access-token"},  # nosec B105
        Exception("Shopify rejected the customer"),
    ]

    result = await shopify_admin.execute_action(
        "create_customer",
        {"email": "customer@example.com"},
        custom_auth_context,
    )

    assert result.result.data == {
        "success": False,
        "message": "Shopify rejected the customer",
        "customer": {},
    }

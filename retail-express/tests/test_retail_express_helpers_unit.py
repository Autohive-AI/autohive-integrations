from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse

from retail_express import build_pagination_params, get_access_token, get_auth_headers


pytestmark = pytest.mark.unit


class TestBuildPaginationParams:
    @pytest.mark.parametrize(
        "inputs, expected",
        [
            ({}, {}),
            ({"page_number": 3}, {"page_number": 3}),
            ({"page_size": 100}, {"page_size": 100}),
            ({"page_number": 2, "page_size": 300}, {"page_number": 2, "page_size": 250}),
        ],
    )
    def test_builds_and_caps_pagination(self, inputs, expected):
        assert build_pagination_params(inputs) == expected


class TestAuthenticationHelpers:
    @pytest.fixture
    def auth_context(self):
        context = MagicMock(name="ExecutionContext")
        context.auth = {
            "auth_type": "Custom",
            "credentials": {"api_key": "test-api-key"},  # nosec B105
        }
        context.fetch = AsyncMock(
            return_value=FetchResponse(
                status=200,
                headers={},
                data={"access_token": "test-access-token"},  # nosec B105
            )
        )
        return context

    async def test_get_access_token_uses_api_key_header(self, auth_context):
        token = await get_access_token(auth_context)

        assert token == "test-access-token"  # nosec B105
        auth_context.fetch.assert_awaited_once_with(
            "https://api.retailexpress.com.au/v2.1/auth/token",
            method="GET",
            headers={"x-api-key": "test-api-key", "Accept": "application/json"},
        )

    async def test_get_auth_headers_includes_bearer_token_and_api_key(self, auth_context):
        headers = await get_auth_headers(auth_context)

        assert headers == {
            "Authorization": "Bearer test-access-token",
            "x-api-key": "test-api-key",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

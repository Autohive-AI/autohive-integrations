import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _get_env(var: str) -> str | None:
    val = os.environ.get(var)
    return val if val else None


@pytest.fixture
def mock_context(mocker):
    from unittest.mock import AsyncMock, MagicMock
    from autohive_integrations_sdk.integration import FetchResponse

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data={}))
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "sk_test_fake"},  # nosec B105
    }
    return ctx


@pytest.fixture
def stripe_context():
    import aiohttp
    import json as _json
    from unittest.mock import AsyncMock, MagicMock
    from autohive_integrations_sdk.integration import FetchResponse

    api_key = _get_env("STRIPE_TEST_API_KEY")
    if not api_key:
        pytest.skip("STRIPE_TEST_API_KEY not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, data=None, **kwargs):
        merged = dict(headers or {})
        merged["Authorization"] = f"Bearer {api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=merged, params=params, data=data, json=json) as resp:
                text = await resp.text()
                body = _json.loads(text) if text.strip() else {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": api_key},
    }
    return ctx

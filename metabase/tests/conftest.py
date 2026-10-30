import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ExecutionContext, FetchResponse

BASE = "https://metabase.test"


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": BASE,
            "api_key": "mb_test_api_key",  # nosec B105
        },
    }
    return ctx

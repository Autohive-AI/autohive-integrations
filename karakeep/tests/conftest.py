import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": "https://karakeep.test",
            "api_key": "test_api_key",  # nosec B105
        },
    }
    return ctx

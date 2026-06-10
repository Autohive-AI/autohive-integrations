import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",  # nosec B105
    }
    return ctx

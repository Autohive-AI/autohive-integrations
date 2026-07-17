import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "site_url": "https://test.imis.com",
        "username": "testuser",
        "password": "testpassword",  # nosec B105
        "client_id": "iMIS",
    }
    return ctx

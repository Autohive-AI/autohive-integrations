import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "host": "https://test.supabase.co",
        "service_role_secret": "test-service-role-secret",  # nosec B105
    }
    return ctx

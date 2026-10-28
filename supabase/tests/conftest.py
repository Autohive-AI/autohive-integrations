import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    dummy_value = "test-service-role-secret"
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "host": "https://test.supabase.co",
            "service_role_secret": dummy_value,
        },
    }
    return ctx

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import ExecutionContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.fetch = AsyncMock()
    ctx.auth = {"api_key": "test_api_key"}  # nosec B105
    return ctx

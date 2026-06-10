from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    return ctx

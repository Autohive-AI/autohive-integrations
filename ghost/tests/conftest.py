from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "api_url": "https://demo.ghost.io",
        "content_api_key": "test_content_key",  # nosec B105
        "admin_api_key": "testid00000000000000000a:aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",  # nosec B105
    }
    return ctx

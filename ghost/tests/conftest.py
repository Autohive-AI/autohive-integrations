from unittest.mock import AsyncMock, MagicMock
import pytest

# 32-byte hex secret keeps the line length and PyJWT's HS256 key-length warning in check.
_ADMIN_API_KEY = "testid00000000000000000a:" + "aabbccddeeff0011" * 4  # nosec B105


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_url": "https://demo.ghost.io",
            "content_api_key": "test_content_key",  # nosec B105
            "admin_api_key": _ADMIN_API_KEY,
        },
    }
    return ctx

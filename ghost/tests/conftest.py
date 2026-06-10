from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "api_url": "https://demo.ghost.io",
        "content_api_key": "test_content_key",  # nosec B105
        "admin_api_key": "6747844835dbba000136a9b3:f9e9e900c9e04cde3cc42d387c8757490a0d81db5a44e49e46af0dbd0ef64ec1",  # nosec B105
    }
    return ctx

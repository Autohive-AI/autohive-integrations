import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def mock_context(monkeypatch):
    context = MagicMock()
    context.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test-token"}}  # nosec B105
    context.fetch = AsyncMock()
    context.request = AsyncMock()

    async def mock_request(ctx, *args, **kwargs):
        assert ctx is context
        return await context.request(*args, **kwargs)

    monkeypatch.setattr("businesscentral.request", mock_request)
    context.config = {"max_retries": 3, "timeout": 30}
    return context

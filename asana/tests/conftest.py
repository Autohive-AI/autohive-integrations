import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx

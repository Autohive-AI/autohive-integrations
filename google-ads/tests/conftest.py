import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Allow imports to work when pytest runs from repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock context with Google Ads platform OAuth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_access_token"},  # nosec B105
    }
    return ctx

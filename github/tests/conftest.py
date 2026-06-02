import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make github.py importable as a top-level module in tests.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with GitHub platform OAuth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx

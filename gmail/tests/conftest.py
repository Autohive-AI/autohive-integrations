import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make gmail.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with the platform-OAuth shape Gmail expects.

    Gmail uses platform OAuth (config.auth.type == "platform") so the SDK wraps
    the access token in {"auth_type": "PlatformOauth2", "credentials": {...}}.
    """
    ctx = MagicMock(name="ExecutionContext")
    # gmail uses googleapiclient directly (not context.fetch), but unit tests
    # still receive an AsyncMock for fetch so the standard fixture contract holds.
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_access_token"},  # nosec B105
    }
    return ctx

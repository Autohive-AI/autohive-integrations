import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make freshdesk.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the wrapped Custom auth envelope Freshdesk expects.

    MagicMock attributes don't share state, so setting ``ctx.auth`` alone does
    not make the real ``credentials`` property available; set it explicitly to
    the unwrapped credentials dict.
    """
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    credentials = {"api_key": "test_api_key", "domain": "testcompany"}  # nosec B105
    ctx.auth = {"auth_type": "Custom", "credentials": credentials}
    return ctx

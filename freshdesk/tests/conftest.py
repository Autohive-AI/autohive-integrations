import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make freshdesk.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the custom auth shape Freshdesk expects."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"api_key": "test_api_key", "domain": "testcompany"}  # nosec B105
    return ctx

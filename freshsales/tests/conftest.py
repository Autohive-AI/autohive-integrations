import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make freshsales.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the wrapped Custom auth envelope Freshsales expects."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    credentials = {"api_key": "test_api_key", "bundle_alias": "testcompany"}  # nosec B105
    ctx.auth = {"auth_type": "Custom", "credentials": credentials}
    return ctx

import os
import sys

# Make windcave.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with Windcave's flat custom-auth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "username": "test_user",
        "api_key": "test_api_key",  # nosec B105
        "use_test_environment": False,
    }
    return ctx

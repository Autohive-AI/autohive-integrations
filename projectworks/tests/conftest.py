import os
import sys

from unittest.mock import AsyncMock, MagicMock

import pytest

# Make projectworks.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    dummy_value = "test_consumer_secret"
    """Mock ExecutionContext pre-loaded with Projectworks custom-auth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "consumer_key": "test_consumer_key",
            "consumer_secret": dummy_value,
        },
    }
    return ctx

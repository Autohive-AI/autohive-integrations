import os
import sys

from unittest.mock import AsyncMock, MagicMock

import pytest

# Make projectworks.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with ProjectWorks custom-auth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "consumer_key": "test_consumer_key",  # nosec B105
        "consumer_secret": "test_consumer_secret",  # nosec B105
    }
    return ctx

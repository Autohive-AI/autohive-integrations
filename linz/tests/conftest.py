import os
import sys

from unittest.mock import AsyncMock, MagicMock

import pytest

# Make the linz package importable (as `from linz.linz import ...`) even when
# tests run from outside the repo root. Adding the repo root — not the linz/
# directory itself — keeps linz.py from shadowing the linz package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with a LINZ API key (custom auth).

    SDK 2.0.1+ requires the platform auth envelope; flat auth is rejected
    with a VALIDATION_ERROR before the handler runs.
    """
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": "test_api_key"}}  # nosec B105
    return ctx

import os
import sys

from unittest.mock import AsyncMock, MagicMock

import pytest

# Make typeform.py importable as a top-level module (`from typeform import typeform`).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext with a platform-OAuth credential envelope.

    Typeform uses platform OAuth (config.auth.type == "platform"); the token is
    injected by the platform into context.fetch, so the action code never reads
    context.auth. The envelope here just matches the shape the SDK expects.
    """
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx

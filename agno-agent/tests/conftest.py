import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make agno_agent.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with this integration's custom-auth credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_url": "https://agno.example.com",
            "api_token": "test-token",  # nosec B105
            "agent_id": "my-agent",
        },
    }
    return ctx

"""Figma tests use the same credential envelope as Autohive."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_figma_token"},  # nosec B105
    }
    context.fetch = AsyncMock()
    return context

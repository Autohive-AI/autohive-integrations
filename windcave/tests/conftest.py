import os
import sys

# Make windcave.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_context(monkeypatch):
    """Mock ExecutionContext pre-loaded with Windcave's wrapped custom-auth envelope."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "username": "test_user",
            "api_key": "test_api_key",  # nosec B105
        },
    }
    import importlib

    module = importlib.import_module("windcave.windcave")
    ctx.request_mock = AsyncMock(name="_windcave_request")
    monkeypatch.setattr(module, "_windcave_request", ctx.request_mock)
    return ctx

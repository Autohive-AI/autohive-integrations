import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Hyphenated folder name: put the integration directory on sys.path so
# `import stats_nz_datafinder` resolves to stats_nz_datafinder.py.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock ExecutionContext with the SDK 2.x custom-auth envelope."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": "test_api_key"}}  # nosec B105
    return ctx


@pytest.fixture
def mock_wfs(monkeypatch):
    """Patch the single WFS request seam (`_wfs_request`)."""
    import stats_nz_datafinder as module

    mocked = AsyncMock(name="_wfs_request")
    monkeypatch.setattr(module, "_wfs_request", mocked)
    return mocked

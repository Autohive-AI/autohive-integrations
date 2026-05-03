"""Local pytest setup for the Supadata integration.

The integration's source file `supadata_transcribe.py` lives at the top of
the `supadata/` directory. Putting that directory on sys.path lets tests
import it as a top-level module, while leaving `from supadata import ...`
inside the source resolving to the PyPI `supadata` package (since this
folder no longer ships an `__init__.py`).

The repo-wide `conftest.py` provides `mock_context`, `make_context` and
`env_credentials` — we only override `mock_context` here so it carries
the credentials shape this integration expects.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make `supadata_transcribe.py` importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context() -> MagicMock:
    """Mock ExecutionContext pre-loaded with a Supadata API key."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test_api_key"}}  # nosec B105
    return ctx

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
    ctx.auth = {"auth_type": "Custom", "credentials": {"api_key": "test_api_key"}}  # nosec B105
    return ctx


@pytest.fixture
def mock_wfs(monkeypatch):
    """Patch the single WFS request seam (`_wfs_request`).

    The integration now issues its HTTP calls with aiohttp directly (not
    `context.fetch`) so the API key — which LINZ carries in the URL path —
    never reaches the SDK's request logging. Unit tests therefore mock this
    one function: set `.return_value`/`.side_effect` to feed responses, and
    inspect `.call_args.kwargs["params"]` to assert on the request.
    """
    import importlib

    # `from linz import linz` resolves to the Integration instance (the package
    # __init__ re-exports it), so reach the module object via its full name.
    linz_module = importlib.import_module("linz.linz")

    m = AsyncMock(name="_wfs_request")
    monkeypatch.setattr(linz_module, "_wfs_request", m)
    return m

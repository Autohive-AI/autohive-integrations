"""
Root conftest.py — shared fixtures for all integration test suites.

Provides:
- mock_context: A pre-configured MagicMock ExecutionContext with AsyncMock fetch
- make_context: Factory for building mock contexts with custom auth shapes
- env_credentials: Helper to load credentials from env/.env files

Also patches Integration.load() so it resolves config.json from the calling
module's directory (instead of the SDK's package tree), which is needed when
the SDK is installed as a site-package rather than vendored.

Usage in any integration's tests/:
    def test_something(mock_context):
        mock_context.fetch.return_value = {"data": ...}
        ...
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Patch Integration.load() for non-vendored SDK installs
# ---------------------------------------------------------------------------
# The SDK's default load() resolves config.json relative to the SDK package
# itself (three dirname() calls up from integration.py).  When the SDK is a
# normal site-package this resolves into site-packages/, not the integration
# directory.  We monkeypatch it to use caller frame inspection instead.

from autohive_integrations_sdk import Integration  # noqa: E402

_original_load = Integration.load.__func__


@classmethod  # type: ignore[misc]
def _patched_load(cls, config_path: Union[str, Path, None] = None) -> "Integration":
    if config_path is None:
        frame = inspect.stack()[1]
        caller_dir = Path(frame.filename).resolve().parent
        config_path = caller_dir / "config.json"
    return _original_load(cls, config_path)


Integration.load = _patched_load  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# .env file loading (stdlib-only, no third-party dependency)
# ---------------------------------------------------------------------------

def _load_dotenv(path: Path) -> None:
    """Load a .env file into os.environ (simple key=value, ignores comments)."""
    if not path.is_file():
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


# Load project-root .env once at collection time
_load_dotenv(Path(__file__).parent / ".env")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_context() -> MagicMock:
    """Minimal mock ExecutionContext with an async-capable ``fetch``."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


@pytest.fixture
def make_context():
    """Factory fixture — build a mock context with arbitrary auth.

    Example::

        def test_foo(make_context):
            ctx = make_context(auth={"credentials": {"api_key": "k"}})
            ctx.fetch.return_value = {...}
    """

    def _factory(
        *,
        auth: Optional[Dict[str, Any]] = None,
    ) -> MagicMock:
        ctx = MagicMock(name="ExecutionContext")
        ctx.fetch = AsyncMock(name="fetch")
        ctx.auth = auth or {}
        return ctx

    return _factory


@pytest.fixture
def env_credentials():
    """Return a helper that reads credentials from environment variables.

    Example::

        def test_live(env_credentials):
            creds = env_credentials("BITLY_ACCESS_TOKEN")
            if creds is None:
                pytest.skip("BITLY_ACCESS_TOKEN not set")
    """

    def _get(var_name: str) -> Optional[str]:
        val = os.environ.get(var_name)
        return val if val else None

    return _get

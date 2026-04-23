import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Allow 'from context import ...' to work when pytest runs from repo root
sys.path.insert(0, os.path.dirname(__file__))


class _FetchMock(AsyncMock):
    """AsyncMock whose return_value is auto-wrapped in `SimpleNamespace(data=...)`.

    SDK 2.x returns a FetchResponse with a `.data` attribute. This lets tests
    keep assigning plain dicts to `mock_context.fetch.return_value` — the
    wrapping happens here instead of in every call site.
    """

    async def _execute_mock_call(self, *args, **kwargs):
        value = await super()._execute_mock_call(*args, **kwargs)
        if isinstance(value, (dict, list)) or value is None:
            return SimpleNamespace(data=value)
        return value


@pytest.fixture
def mock_context():
    """ClickUp-local override of root mock_context — wraps fetch returns in .data."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = _FetchMock(name="fetch")
    ctx.auth = {}
    return ctx

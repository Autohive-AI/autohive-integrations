from unittest.mock import AsyncMock, MagicMock

import pytest

# Note: the repo-root conftest.py puts the workspace root on sys.path and
# monkeypatches Integration.load() to resolve config.json from the caller
# frame, so `from gmail.gmail import gmail` resolves to the gmail/ package
# without any extra path manipulation here.


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with the platform-OAuth shape Gmail expects.

    Gmail uses platform OAuth (config.auth.type == "platform") so the SDK wraps
    the access token in {"auth_type": "PlatformOauth2", "credentials": {...}}.
    """
    ctx = MagicMock(name="ExecutionContext")
    # gmail uses googleapiclient directly (not context.fetch), but unit tests
    # still receive an AsyncMock for fetch so the standard fixture contract holds.
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_access_token"},  # nosec B105
    }
    return ctx

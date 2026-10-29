import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make shopify_storefront.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

FAKE_PUBLIC_CREDENTIAL = "test-public-value"


@pytest.fixture
def mock_context():
    """Mock ExecutionContext pre-loaded with Storefront public-token credentials."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "shop_url": "test-store.myshopify.com",
            "public_token": FAKE_PUBLIC_CREDENTIAL,
        },
    }
    return ctx

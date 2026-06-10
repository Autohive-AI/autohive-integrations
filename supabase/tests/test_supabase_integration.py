import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import MagicMock
from autohive_integrations_sdk import ExecutionContext, ResultType
from supabase import supabase  # noqa: E402

pytestmark = pytest.mark.integration

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

skip_if_no_creds = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY,
    reason="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for integration tests",
)


@pytest.fixture
def live_context():
    ctx = MagicMock(spec=ExecutionContext)
    ctx.auth = {
        "host": SUPABASE_URL,
        "service_role_secret": SUPABASE_SERVICE_ROLE_KEY,
    }
    return ctx


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_buckets_live(live_context):
    result = await supabase.execute_action("list_buckets", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "buckets" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_users_live(live_context):
    result = await supabase.execute_action("list_users", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "users" in result.result.data

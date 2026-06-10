import os
import pytest
from autohive_integrations_sdk import ResultType
from grammarly.grammarly import grammarly

GRAMMARLY_CLIENT_ID = os.getenv("GRAMMARLY_CLIENT_ID", "")
GRAMMARLY_CLIENT_SECRET = os.getenv("GRAMMARLY_CLIENT_SECRET", "")

pytestmark = pytest.mark.skipif(
    not GRAMMARLY_CLIENT_ID or not GRAMMARLY_CLIENT_SECRET,
    reason="Grammarly credentials not set in environment",
)


@pytest.fixture
def live_context():
    class _Ctx:
        auth = {
            "client_id": GRAMMARLY_CLIENT_ID,
            "client_secret": GRAMMARLY_CLIENT_SECRET,
        }

    return _Ctx()


@pytest.mark.asyncio
async def test_analyze_writing_score_live(live_context):
    result = await grammarly.execute_action(
        "analyze_writing_score",
        {
            "filename": "test.txt",
            "file_content": (
                "The quick brown fox jumps over the lazy dog. "
                "This is a sample text for writing quality analysis. "
                "It contains multiple sentences to meet the minimum word count requirement."
            ),
        },
        live_context,
    )
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type != ResultType.ACTION_ERROR:
        assert "score_request_id" in result.result.data


@pytest.mark.asyncio
async def test_get_user_analytics_live(live_context):
    result = await grammarly.execute_action(
        "get_user_analytics",
        {"date_from": "2024-01-01", "date_to": "2024-01-31"},
        live_context,
    )
    assert result.type in (ResultType.SUCCESS, ResultType.ACTION_ERROR)
    if result.type != ResultType.ACTION_ERROR:
        assert "data" in result.result.data

import pytest
from unittest.mock import AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType
from grammarly.grammarly import grammarly

pytestmark = pytest.mark.unit

TOKEN_RESPONSE = FetchResponse(status=200, headers={}, data={"access_token": "test_token"})  # nosec B105
UPLOAD_RESPONSE = FetchResponse(status=200, headers={}, data={})


def _make_fetch(responses):
    """Return an AsyncMock that returns responses in sequence."""
    mock = AsyncMock(side_effect=responses)
    return mock


@pytest.mark.asyncio
async def test_analyze_writing_score(mock_context):
    score_resp = FetchResponse(
        status=200, headers={}, data={"score_request_id": "req-123", "file_upload_url": "https://s3.example.com/upload"}
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, score_resp, UPLOAD_RESPONSE])
    result = await grammarly.execute_action(
        "analyze_writing_score",
        {"filename": "doc.txt", "file_content": "Hello world, this is a test document."},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["score_request_id"] == "req-123"


@pytest.mark.asyncio
async def test_analyze_writing_score_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Auth failed"))
    result = await grammarly.execute_action(
        "analyze_writing_score",
        {"filename": "doc.txt", "file_content": "test content"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Auth failed" in result.result.message


@pytest.mark.asyncio
async def test_get_writing_score_results_pending(mock_context):
    score_resp = FetchResponse(status=200, headers={}, data={"status": "PENDING"})
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, score_resp])
    result = await grammarly.execute_action(
        "get_writing_score_results",
        {"score_request_id": "req-123"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_writing_score_results_completed(mock_context):
    score_resp = FetchResponse(
        status=200,
        headers={},
        data={
            "status": "COMPLETED",
            "score": {
                "generalScore": 85,
                "engagement": 80,
                "correctness": 90,
                "delivery": 82,
                "clarity": 88,
            },
        },
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, score_resp])
    result = await grammarly.execute_action(
        "get_writing_score_results",
        {"score_request_id": "req-123"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["general_score"] == 85
    assert result.result.data["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_get_writing_score_results_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, Exception("Not found")])
    result = await grammarly.execute_action(
        "get_writing_score_results",
        {"score_request_id": "bad-id"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Not found" in result.result.message


@pytest.mark.asyncio
async def test_get_user_analytics(mock_context):
    analytics_resp = FetchResponse(
        status=200,
        headers={},
        data={
            "data": [{"id": "u1", "email": "user@example.com", "days_active": 10}],
            "paging": {"has_more": False},
        },
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, analytics_resp])
    result = await grammarly.execute_action(
        "get_user_analytics",
        {"date_from": "2024-01-01", "date_to": "2024-01-31"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["data"]) == 1
    assert "paging" in result.result.data


@pytest.mark.asyncio
async def test_get_user_analytics_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Rate limit exceeded"))
    result = await grammarly.execute_action(
        "get_user_analytics",
        {"date_from": "2024-01-01", "date_to": "2024-01-31"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Rate limit" in result.result.message


@pytest.mark.asyncio
async def test_analyze_ai_detection(mock_context):
    ai_resp = FetchResponse(
        status=200,
        headers={},
        data={"score_request_id": "ai-req-456", "file_upload_url": "https://s3.example.com/upload"},
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, ai_resp, UPLOAD_RESPONSE])
    result = await grammarly.execute_action(
        "analyze_ai_detection",
        {"filename": "essay.txt", "file_content": "This essay was written by a human."},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["score_request_id"] == "ai-req-456"


@pytest.mark.asyncio
async def test_get_ai_detection_results_completed(mock_context):
    ai_resp = FetchResponse(
        status=200,
        headers={},
        data={
            "status": "COMPLETED",
            "updated_at": "2024-01-15T10:00:00Z",
            "score": {"average_confidence": 0.12, "ai_generated_percentage": 8.5},
        },
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, ai_resp])
    result = await grammarly.execute_action(
        "get_ai_detection_results",
        {"score_request_id": "ai-req-456"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["average_confidence"] == 0.12
    assert result.result.data["ai_generated_percentage"] == 8.5


@pytest.mark.asyncio
async def test_get_ai_detection_results_pending(mock_context):
    ai_resp = FetchResponse(status=200, headers={}, data={"status": "PENDING"})
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, ai_resp])
    result = await grammarly.execute_action(
        "get_ai_detection_results",
        {"score_request_id": "ai-req-456"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_analyze_plagiarism_detection(mock_context):
    plag_resp = FetchResponse(
        status=200,
        headers={},
        data={"score_request_id": "plag-req-789", "file_upload_url": "https://s3.example.com/upload"},
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, plag_resp, UPLOAD_RESPONSE])
    result = await grammarly.execute_action(
        "analyze_plagiarism_detection",
        {"filename": "paper.txt", "file_content": "Original research content here."},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["score_request_id"] == "plag-req-789"


@pytest.mark.asyncio
async def test_get_plagiarism_detection_results_completed(mock_context):
    plag_resp = FetchResponse(
        status=200,
        headers={},
        data={
            "status": "COMPLETED",
            "updated_at": "2024-01-15T10:00:00Z",
            "score": {"originality_score": 95},
        },
    )
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, plag_resp])
    result = await grammarly.execute_action(
        "get_plagiarism_detection_results",
        {"score_request_id": "plag-req-789"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["originality_score"] == 95
    assert result.result.data["plagiarism_percentage"] == 5


@pytest.mark.asyncio
async def test_get_plagiarism_detection_results_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Request timeout"))
    result = await grammarly.execute_action(
        "get_plagiarism_detection_results",
        {"score_request_id": "bad-id"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "timeout" in result.result.message

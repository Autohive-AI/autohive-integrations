"""
End-to-end integration tests for the Grammarly integration.

Requires credentials set in environment variables or a .env file at the repo root:
    GRAMMARLY_CLIENT_ID     -- OAuth2 Client ID from the Grammarly developer portal
    GRAMMARLY_CLIENT_SECRET -- OAuth2 Client Secret

Run safely (all tests are read-like submit-and-poll, no destructive data):
    pytest grammarly/tests/test_grammarly_integration.py -m integration

Never runs in CI -- the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from datetime import date, timedelta
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from grammarly.grammarly import grammarly

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("GRAMMARLY_CLIENT_ID") or not os.getenv("GRAMMARLY_CLIENT_SECRET"),
        reason="GRAMMARLY_CLIENT_ID and GRAMMARLY_CLIENT_SECRET required",
    ),
]

GRAMMARLY_CLIENT_ID = os.getenv("GRAMMARLY_CLIENT_ID", "")
GRAMMARLY_CLIENT_SECRET = os.getenv("GRAMMARLY_CLIENT_SECRET", "")

SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a sample text for writing quality analysis. "
    "It contains multiple sentences to meet the minimum word count requirement."
)


@pytest.fixture
def live_context(make_context):
    async def real_fetch(
        url, *, method="GET", params=None, headers=None, json=None, data=None, content_type=None, **kwargs
    ):
        req_headers = dict(headers or {})
        if content_type:
            req_headers["Content-Type"] = content_type
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=req_headers,
            ) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()

                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(resp_data), resp_data)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(resp_data), resp_data)

                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"client_id": GRAMMARLY_CLIENT_ID, "client_secret": GRAMMARLY_CLIENT_SECRET},
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


@pytest.mark.asyncio
async def test_analyze_writing_score(live_context):
    result = await grammarly.execute_action(
        "analyze_writing_score",
        {"filename": "test.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "score_request_id" in result.result.data
    assert result.result.data["score_request_id"]


@pytest.mark.asyncio
async def test_get_writing_score_results(live_context):
    submit = await grammarly.execute_action(
        "analyze_writing_score",
        {"filename": "test.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert submit.type == ResultType.ACTION, submit.result.message
    score_request_id = submit.result.data["score_request_id"]

    result = await grammarly.execute_action(
        "get_writing_score_results",
        {"score_request_id": score_request_id},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "status" in result.result.data


@pytest.mark.asyncio
async def test_get_user_analytics(live_context):
    date_to = date.today() - timedelta(days=2)
    date_from = date_to - timedelta(days=30)
    result = await grammarly.execute_action(
        "get_user_analytics",
        {"date_from": date_from.strftime("%Y-%m-%d"), "date_to": date_to.strftime("%Y-%m-%d")},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "data" in result.result.data
    assert "paging" in result.result.data


@pytest.mark.asyncio
async def test_analyze_ai_detection(live_context):
    result = await grammarly.execute_action(
        "analyze_ai_detection",
        {"filename": "essay.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "score_request_id" in result.result.data
    assert result.result.data["score_request_id"]


@pytest.mark.asyncio
async def test_get_ai_detection_results(live_context):
    submit = await grammarly.execute_action(
        "analyze_ai_detection",
        {"filename": "essay.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert submit.type == ResultType.ACTION, submit.result.message
    score_request_id = submit.result.data["score_request_id"]

    result = await grammarly.execute_action(
        "get_ai_detection_results",
        {"score_request_id": score_request_id},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "status" in result.result.data


@pytest.mark.asyncio
async def test_analyze_plagiarism_detection(live_context):
    result = await grammarly.execute_action(
        "analyze_plagiarism_detection",
        {"filename": "paper.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "score_request_id" in result.result.data
    assert result.result.data["score_request_id"]


@pytest.mark.asyncio
async def test_get_plagiarism_detection_results(live_context):
    submit = await grammarly.execute_action(
        "analyze_plagiarism_detection",
        {"filename": "paper.txt", "file_content": SAMPLE_TEXT},
        live_context,
    )
    assert submit.type == ResultType.ACTION, submit.result.message
    score_request_id = submit.result.data["score_request_id"]

    result = await grammarly.execute_action(
        "get_plagiarism_detection_results",
        {"score_request_id": score_request_id},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert "status" in result.result.data

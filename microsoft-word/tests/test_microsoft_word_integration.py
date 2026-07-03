"""
End-to-end integration tests for the Microsoft Word integration.

Read-only tests require a valid OAuth access token in MICROSOFT_WORD_ACCESS_TOKEN
(via .env or export) with Files.Read/Files.ReadWrite scopes against Microsoft Graph.

Destructive tests (create/update/delete document content) are gated behind
MICROSOFT_WORD_RUN_DESTRUCTIVE_TESTS=1 since they create and mutate real
files in the connected OneDrive account.

Run with:
    pytest microsoft-word/tests/test_microsoft_word_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib.util
import os

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import aiohttp  # noqa: E402
import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402

from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("microsoft_word_mod", os.path.join(_parent, "microsoft_word.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

microsoft_word = _mod.microsoft_word

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("MICROSOFT_WORD_ACCESS_TOKEN", "")
RUN_DESTRUCTIVE = os.environ.get("MICROSOFT_WORD_RUN_DESTRUCTIVE_TESTS", "") == "1"

skip_if_no_creds = pytest.mark.skipif(not ACCESS_TOKEN, reason="MICROSOFT_WORD_ACCESS_TOKEN required")
skip_if_not_destructive = pytest.mark.skipif(
    not RUN_DESTRUCTIVE, reason="MICROSOFT_WORD_RUN_DESTRUCTIVE_TESTS=1 required"
)


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with a Microsoft Graph OAuth token.

    The Microsoft Word integration relies on context.fetch to auto-inject the
    OAuth token (auth.type = "platform"). In tests we bypass the SDK auth
    layer and manually add the Authorization header to every request.
    """

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, data=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, data=data, headers=merged_headers, params=params
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    body = await resp.json(content_type=None)
                else:
                    body = await resp.read()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


class TestListDocuments:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_documents(self, live_context):
        result = await microsoft_word.execute_action("word_list_documents", {"page_size": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["documents"], list)


class TestDocumentLifecycle:
    @skip_if_not_destructive
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_01_create_update_search_replace(self, live_context):
        create_result = await microsoft_word.execute_action(
            "word_create_document",
            {"name": "Autohive Integration Test", "content": "Hello world"},
            live_context,
        )
        assert create_result.type != ResultType.ACTION_ERROR, create_result.result.message
        document_id = create_result.result.data["document_id"]

        update_result = await microsoft_word.execute_action(
            "word_update_content",
            {"document_id": document_id, "content": "Updated by integration test"},
            live_context,
        )
        assert update_result.type != ResultType.ACTION_ERROR, update_result.result.message

        replace_result = await microsoft_word.execute_action(
            "word_search_replace",
            {"document_id": document_id, "search_text": "integration", "replace_text": "automated"},
            live_context,
        )
        assert replace_result.type != ResultType.ACTION_ERROR, replace_result.result.message

"""
End-to-end integration tests for the LinkedIn integration.

These tests call the real LinkedIn REST API (version 202601) and require a
valid platform OAuth access token set in LINKEDIN_ACCESS_TOKEN (via .env or
exported in the shell). The token must have these scopes:

    w_member_social, openid, profile, email

Run with:
    pytest linkedin/tests/test_linkedin_integration.py -m integration

Read-only tests only:
    pytest linkedin/tests/test_linkedin_integration.py -m "integration and not destructive"

Destructive tests (create/update/delete real posts):
    pytest linkedin/tests/test_linkedin_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.

Each destructive class is a self-contained lifecycle: anything created by the
test is deleted at the end of the same test, so tests can be re-run safely.
"""

import importlib.util
import os
import sys
import time

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("linkedin_mod", os.path.join(_parent, "linkedin.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

linkedin = _mod.linkedin

pytestmark = pytest.mark.integration


ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")

# 1x1 PNG (LinkedIn-acceptable image), small enough to upload quickly.
SAMPLE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def live_context():
    """Variant 3 — platform OAuth. Manually injects Authorization: Bearer header
    on every request, since the SDK auth layer is bypassed in tests."""
    if not ACCESS_TOKEN:
        pytest.skip("LINKEDIN_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp
    from yarl import URL

    async def real_fetch(url, *, method="GET", json=None, data=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

        # The integration constructs URLs with already-encoded URN path segments
        # (e.g. urn%3Ali%3Ashare%3A123). yarl decodes path segments on parse and
        # re-encodes on send, which mangles those URNs and gets us 400s from
        # LinkedIn. encoded=True tells yarl the URL is already canonical and to
        # leave it alone — verified the same URL works in Postman without this.
        yarl_url = URL(url, encoded=True)

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, yarl_url, json=json, data=data, headers=merged_headers, params=params
            ) as resp:
                text = await resp.text()
                body = None
                if text:
                    try:
                        import json as _json
                        body = _json.loads(text)
                    except ValueError:
                        body = text
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---- Read-Only Tests ----


class TestGetUserInfo:
    async def test_returns_user_info(self, live_context):
        result = await linkedin.execute_action("get_user_info", {}, live_context)
        data = result.result.data

        assert data["result"] == "User information retrieved successfully."
        assert "user_info" in data
        assert data["user_info"]["sub"]

    async def test_user_info_has_openid_claims(self, live_context):
        result = await linkedin.execute_action("get_user_info", {}, live_context)
        info = result.result.data["user_info"]

        assert "sub" in info
        assert "name" in info


# ---- Destructive Tests (Write Operations) ----


@pytest.mark.destructive
class TestPostLifecycle:
    """create_post (text) → update_post → delete_post."""

    async def test_full_lifecycle(self, live_context):
        unique = f"Autohive integration test {os.getpid()}-{int(time.time())}"

        create = await linkedin.execute_action("create_post", {"text": unique}, live_context)
        assert create.result.data["result"] == "Post created successfully."
        post_id = create.result.data["post_id"]
        assert post_id is not None
        assert post_id.startswith("urn:li:share:") or post_id.startswith("urn:li:ugcPost:")

        try:
            update = await linkedin.execute_action(
                "update_post", {"post_urn": post_id, "commentary": f"{unique} (updated)"}, live_context
            )
            assert update.result.data["result"] == "Post updated successfully."
            assert update.result.data["post_urn"] == post_id
        finally:
            delete = await linkedin.execute_action("delete_post", {"post_urn": post_id}, live_context)
            assert delete.result.data["result"] == "Post deleted successfully."


@pytest.mark.destructive
class TestPostWithImage:
    """create_post with a single image → delete_post."""

    async def test_create_with_image_then_delete(self, live_context):
        unique = f"Autohive image test {os.getpid()}-{int(time.time())}"

        create = await linkedin.execute_action(
            "create_post",
            {
                "text": unique,
                "files": [
                    {
                        "content": SAMPLE_PNG_BASE64,
                        "name": "test pixel.png",
                        "contentType": "image/png",
                    }
                ],
            },
            live_context,
        )
        assert create.result.data["result"] == "Post created successfully."
        assert create.result.data["images_uploaded"] == 1
        post_id = create.result.data["post_id"]

        delete = await linkedin.execute_action("delete_post", {"post_urn": post_id}, live_context)
        assert delete.result.data["result"] == "Post deleted successfully."


@pytest.mark.destructive
class TestShareArticle:
    """share_article → delete the resulting post."""

    async def test_share_then_delete(self, live_context):
        result = await linkedin.execute_action(
            "share_article",
            {
                "article_url": "https://www.example.com/",
                "article_title": f"Autohive test article {os.getpid()}",
                "article_description": "Article shared by integration test, will be removed.",
                "commentary": "Integration test — please ignore.",
            },
            live_context,
        )
        assert result.result.data["result"] == "Article shared successfully."
        post_id = result.result.data["post_id"]
        assert post_id is not None

        delete = await linkedin.execute_action("delete_post", {"post_urn": post_id}, live_context)
        assert delete.result.data["result"] == "Post deleted successfully."


@pytest.mark.destructive
class TestResharePost:
    """create_post → reshare_post → delete both."""

    async def test_reshare_then_cleanup(self, live_context):
        unique = f"Autohive reshare source {os.getpid()}-{int(time.time())}"
        original = await linkedin.execute_action("create_post", {"text": unique}, live_context)
        original_id = original.result.data["post_id"]

        reshare_id = None
        try:
            reshare = await linkedin.execute_action(
                "reshare_post",
                {"original_post_urn": original_id, "commentary": "Resharing for integration test."},
                live_context,
            )
            assert reshare.result.data["result"] == "Post reshared successfully."
            reshare_id = reshare.result.data["post_id"]
            assert reshare_id is not None
        finally:
            if reshare_id:
                rdel = await linkedin.execute_action("delete_post", {"post_urn": reshare_id}, live_context)
                assert rdel.result.data["result"] == "Post deleted successfully."
            odel = await linkedin.execute_action("delete_post", {"post_urn": original_id}, live_context)
            assert odel.result.data["result"] == "Post deleted successfully."



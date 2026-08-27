"""
Live tests for the Karakeep integration.

Requires KARAKEEP_BASE_URL (https:// only) and KARAKEEP_API_KEY (repo-root .env
is loaded by the root conftest). Destructive tests create a real tag and bookmark.

Read-only (default):
    pytest karakeep/tests/test_karakeep_integration.py -m "integration and not destructive"

Opt-in writes:
    pytest karakeep/tests/test_karakeep_integration.py -m "integration and destructive"
"""

import os
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType
from karakeep.karakeep import karakeep

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("KARAKEEP_BASE_URL", "").strip().rstrip("/")
API_KEY = os.getenv("KARAKEEP_API_KEY", "").strip()

skip_if_no_creds = pytest.mark.skipif(
    not BASE_URL or not API_KEY,
    reason="KARAKEEP_BASE_URL and KARAKEEP_API_KEY required",
)


@pytest.fixture
def live_context(make_context):
    if not BASE_URL or not API_KEY:
        pytest.skip("KARAKEEP_BASE_URL and KARAKEEP_API_KEY required")
    parsed = urlparse(BASE_URL)
    if parsed.scheme != "https" or not parsed.netloc:
        pytest.skip(
            f"KARAKEEP_BASE_URL must be https:// (got {BASE_URL!r}). "
            "Use https://cloud.karakeep.app or another HTTPS origin."
        )

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, body=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                data=body,
                headers=headers,
                params=params,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "base_url": BASE_URL,
                "api_key": API_KEY,
            },
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


def _assert_ok(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    return result.result.data


async def _delete_bookmark(context, bookmark_id: str | None) -> None:
    if not bookmark_id:
        return
    try:
        await context.fetch(
            f"{BASE_URL}/api/v1/bookmarks/{quote(bookmark_id, safe='')}",
            method="DELETE",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    except Exception:
        pass


async def _delete_tag(context, tag_id: str | None) -> None:
    if not tag_id:
        return
    try:
        await context.fetch(
            f"{BASE_URL}/api/v1/tags/{quote(tag_id, safe='')}",
            method="DELETE",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    except Exception:
        pass


@skip_if_no_creds
class TestReadOnly:
    @pytest.mark.asyncio
    async def test_list_tags(self, live_context):
        data = _assert_ok(await karakeep.execute_action("list_tags", {"limit": 5}, live_context))
        assert "tags" in data
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_list_bookmarks(self, live_context):
        data = _assert_ok(await karakeep.execute_action("list_bookmarks", {"limit": 5}, live_context))
        assert "bookmarks" in data
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_search_bookmarks(self, live_context):
        data = _assert_ok(await karakeep.execute_action("search_bookmarks", {"query": "AI", "limit": 5}, live_context))
        assert "bookmarks" in data
        assert isinstance(data["count"], int)


@skip_if_no_creds
@pytest.mark.destructive
class TestIngestLifecycle:
    @pytest.mark.asyncio
    async def test_create_tag_bookmark_attach_get_and_dedup(self, live_context):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        test_url = f"https://example.com/autohive-karakeep-integration-{stamp}"
        tag_name = f"autohive-itest-{stamp}"
        bookmark_id = None
        tag_id = None

        try:
            tag = _assert_ok(await karakeep.execute_action("create_tag", {"name": tag_name}, live_context))
            tag_id = tag["tag_id"]
            assert tag_id
            assert tag["name"]

            listed_tags = _assert_ok(
                await karakeep.execute_action("list_tags", {"name_contains": tag_name, "limit": 20}, live_context)
            )
            listed_tag_ids = [t.get("id") for t in listed_tags.get("tags") or []]
            assert tag_id in listed_tag_ids

            created = _assert_ok(
                await karakeep.execute_action(
                    "create_bookmark",
                    {
                        "url": test_url,
                        "title": f"Autohive integration test {stamp}",
                        "note": "Created by integration test",
                    },
                    live_context,
                )
            )
            bookmark_id = created["bookmark_id"]
            assert bookmark_id
            assert created["already_existed"] is False

            tagged = _assert_ok(
                await karakeep.execute_action(
                    "attach_tags",
                    {"bookmark_id": bookmark_id, "tags": [tag_name]},
                    live_context,
                )
            )
            assert tagged["count"] == 1
            assert isinstance(tagged["attached"], list)

            fetched = _assert_ok(
                await karakeep.execute_action("get_bookmark", {"bookmark_id": bookmark_id}, live_context)
            )
            bookmark = fetched["bookmark"]
            assert bookmark.get("id") == bookmark_id

            dup = _assert_ok(await karakeep.execute_action("create_bookmark", {"url": test_url}, live_context))
            assert dup["bookmark_id"] == bookmark_id
            assert dup["already_existed"] is True

            by_tag = _assert_ok(
                await karakeep.execute_action(
                    "get_tag_bookmarks",
                    {"tag_id": tag_id, "limit": 10},
                    live_context,
                )
            )
            ids = [b.get("id") for b in by_tag.get("bookmarks") or []]
            assert bookmark_id in ids
        finally:
            await _delete_bookmark(live_context, bookmark_id)
            await _delete_tag(live_context, tag_id)

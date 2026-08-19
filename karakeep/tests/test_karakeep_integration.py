import os
from datetime import datetime, timezone
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType
from karakeep.karakeep import karakeep

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("KARAKEEP_BASE_URL", "")
API_KEY = os.getenv("KARAKEEP_API_KEY", "")

skip_if_no_creds = pytest.mark.skipif(
    not BASE_URL or not API_KEY,
    reason="KARAKEEP_BASE_URL and KARAKEEP_API_KEY required",
)


@pytest.fixture
def live_context(make_context):
    if not BASE_URL or not API_KEY:
        pytest.skip("KARAKEEP_BASE_URL and KARAKEEP_API_KEY required")

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
                "base_url": BASE_URL.rstrip("/"),
                "api_key": API_KEY,
            },
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


def _assert_ok(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    return result.result.data


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

        tag = _assert_ok(await karakeep.execute_action("create_tag", {"name": tag_name}, live_context))
        assert tag["tag_id"]
        assert tag["name"]

        listed_tags = _assert_ok(
            await karakeep.execute_action("list_tags", {"name_contains": tag_name, "limit": 20}, live_context)
        )
        listed_tag_ids = [t.get("id") for t in listed_tags.get("tags") or []]
        assert tag["tag_id"] in listed_tag_ids

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
                {"bookmark_id": bookmark_id, "tags": [tag_name, "source:autohive-integration-test"]},
                live_context,
            )
        )
        assert tagged["count"] == 2
        assert isinstance(tagged["attached"], list)

        fetched = _assert_ok(await karakeep.execute_action("get_bookmark", {"bookmark_id": bookmark_id}, live_context))
        bookmark = fetched["bookmark"]
        assert bookmark.get("id") == bookmark_id

        dup = _assert_ok(await karakeep.execute_action("create_bookmark", {"url": test_url}, live_context))
        assert dup["bookmark_id"] == bookmark_id
        assert dup["already_existed"] is True

        by_tag = _assert_ok(
            await karakeep.execute_action(
                "get_tag_bookmarks",
                {"tag_id": tag["tag_id"], "limit": 10},
                live_context,
            )
        )
        ids = [b.get("id") for b in by_tag.get("bookmarks") or []]
        assert bookmark_id in ids

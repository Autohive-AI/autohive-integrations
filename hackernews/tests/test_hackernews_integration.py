"""
End-to-end integration tests for the Hacker News integration.

These tests call the real Hacker News Firebase API (public, no auth needed).

Run with:
    pytest hackernews/tests/test_hackernews_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402

_spec = importlib.util.spec_from_file_location("hackernews_mod", os.path.join(_parent, "hackernews.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

hackernews = _mod.hackernews

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client via aiohttp."""
    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                return await resp.json(content_type=None)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {}
    return ctx


# ---- Story List Actions ----


class TestGetTopStories:
    async def test_returns_stories(self, live_context):
        result = await hackernews.execute_action("get_top_stories", {"limit": 5}, live_context)

        data = result.result.data
        assert "stories" in data
        assert "fetched_at" in data
        assert "count" in data
        assert data["count"] > 0
        assert len(data["stories"]) <= 5

    async def test_story_structure(self, live_context):
        result = await hackernews.execute_action("get_top_stories", {"limit": 1}, live_context)

        story = result.result.data["stories"][0]
        assert "id" in story
        assert "title" in story
        assert "hn_url" in story
        assert "score" in story
        assert "by" in story
        assert "time" in story
        assert story["hn_url"].startswith("https://news.ycombinator.com/item?id=")

    async def test_cost_is_zero(self, live_context):
        result = await hackernews.execute_action("get_top_stories", {"limit": 1}, live_context)

        assert result.result.cost_usd == 0.0


class TestGetBestStories:
    async def test_returns_stories(self, live_context):
        result = await hackernews.execute_action("get_best_stories", {"limit": 3}, live_context)

        data = result.result.data
        assert data["count"] > 0
        assert len(data["stories"]) <= 3


class TestGetNewStories:
    async def test_returns_stories(self, live_context):
        result = await hackernews.execute_action("get_new_stories", {"limit": 3}, live_context)

        data = result.result.data
        assert data["count"] > 0
        assert len(data["stories"]) <= 3


class TestGetAskHNStories:
    async def test_returns_stories(self, live_context):
        result = await hackernews.execute_action("get_ask_hn_stories", {"limit": 3}, live_context)

        data = result.result.data
        assert "stories" in data
        assert data["count"] >= 0


class TestGetShowHNStories:
    async def test_returns_stories(self, live_context):
        result = await hackernews.execute_action("get_show_hn_stories", {"limit": 3}, live_context)

        data = result.result.data
        assert "stories" in data
        assert data["count"] >= 0


class TestGetJobStories:
    async def test_returns_jobs(self, live_context):
        result = await hackernews.execute_action("get_job_stories", {"limit": 3}, live_context)

        data = result.result.data
        assert "jobs" in data
        assert "count" in data
        assert data["count"] >= 0


# ---- Story with Comments ----


class TestGetStoryWithComments:
    async def test_fetches_story_and_comments(self, live_context):
        # First get a real story ID from top stories
        top = await hackernews.execute_action("get_top_stories", {"limit": 1}, live_context)
        story_id = top.result.data["stories"][0]["id"]

        result = await hackernews.execute_action(
            "get_story_with_comments", {"story_id": story_id, "comment_limit": 3, "comment_depth": 1}, live_context
        )

        data = result.result.data
        assert "story" in data
        assert "comments" in data
        assert "fetched_at" in data
        assert data["story"]["id"] == story_id

    async def test_comment_structure(self, live_context):
        top = await hackernews.execute_action("get_top_stories", {"limit": 5}, live_context)

        # Find a story that has comments
        story_id = None
        for story in top.result.data["stories"]:
            if story.get("descendants", 0) > 0:
                story_id = story["id"]
                break

        if story_id is None:
            pytest.skip("No stories with comments found in top 5")

        result = await hackernews.execute_action(
            "get_story_with_comments", {"story_id": story_id, "comment_limit": 2, "comment_depth": 1}, live_context
        )

        comments = result.result.data["comments"]
        assert len(comments) > 0
        comment = comments[0]
        assert "id" in comment
        assert "by" in comment
        assert "text" in comment


# ---- User Profile ----


class TestGetUserProfile:
    async def test_known_user(self, live_context):
        result = await hackernews.execute_action("get_user_profile", {"username": "dang"}, live_context)

        data = result.result.data
        assert data["id"] == "dang"
        assert data["karma"] > 0
        assert "profile_url" in data
        assert "created" in data

    async def test_nonexistent_user(self, live_context):
        result = await hackernews.execute_action(
            "get_user_profile", {"username": "this_user_definitely_does_not_exist_99999"}, live_context
        )

        data = result.result.data
        assert "error" in data

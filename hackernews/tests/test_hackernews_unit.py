import sys
import os
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "hackernews_mod", os.path.join(_parent, "hackernews.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

hackernews = _mod.hackernews
format_item = _mod.format_item
format_comment = _mod.format_comment

pytestmark = pytest.mark.unit

SAMPLE_STORY = {
    "id": 12345,
    "title": "Show HN: A new project",
    "type": "story",
    "by": "testuser",
    "score": 42,
    "descendants": 10,
    "time": 1700000000,
    "url": "https://example.com",
    "kids": [100, 101],
}

SAMPLE_COMMENT = {
    "id": 100,
    "type": "comment",
    "by": "commenter1",
    "text": "Great post!",
    "time": 1700000100,
    "kids": [200],
}

SAMPLE_REPLY = {
    "id": 200,
    "type": "comment",
    "by": "commenter2",
    "text": "I agree!",
    "time": 1700000200,
}

SAMPLE_USER = {
    "id": "dang",
    "karma": 50000,
    "created": 1200000000,
    "about": "HN moderator",
}


class TestFormatItem:
    def test_full_item(self):
        result = format_item(SAMPLE_STORY)
        assert result["id"] == 12345
        assert result["title"] == "Show HN: A new project"
        assert result["type"] == "story"
        assert result["by"] == "testuser"
        assert result["score"] == 42
        assert result["descendants"] == 10
        assert result["url"] == "https://example.com"
        assert result["hn_url"] == "https://news.ycombinator.com/item?id=12345"
        assert "time" in result

    def test_item_without_url(self):
        item = {**SAMPLE_STORY}
        del item["url"]
        result = format_item(item)
        assert "url" not in result

    def test_item_without_text(self):
        result = format_item(SAMPLE_STORY)
        assert "text" not in result

    def test_item_with_text(self):
        item = {**SAMPLE_STORY, "text": "Some text content"}
        result = format_item(item)
        assert result["text"] == "Some text content"

    def test_item_without_time(self):
        item = {k: v for k, v in SAMPLE_STORY.items() if k != "time"}
        result = format_item(item)
        assert "time" not in result

    def test_defaults_for_missing_score_and_descendants(self):
        item = {"id": 1, "title": "Test"}
        result = format_item(item)
        assert result["score"] == 0
        assert result["descendants"] == 0


class TestFormatComment:
    def test_normal_comment(self):
        result = format_comment(SAMPLE_COMMENT)
        assert result["id"] == 100
        assert result["by"] == "commenter1"
        assert result["text"] == "Great post!"
        assert "time" in result
        assert "replies" not in result

    def test_comment_with_replies(self):
        replies = [{"id": 200, "by": "someone", "text": "reply"}]
        result = format_comment(SAMPLE_COMMENT, replies=replies)
        assert result["replies"] == replies

    def test_deleted_comment_returns_none(self):
        item = {**SAMPLE_COMMENT, "deleted": True}
        assert format_comment(item) is None

    def test_dead_comment_returns_none(self):
        item = {**SAMPLE_COMMENT, "dead": True}
        assert format_comment(item) is None

    def test_comment_without_author(self):
        item = {"id": 300, "text": "anonymous"}
        result = format_comment(item)
        assert result["by"] == "[deleted]"

    def test_comment_without_time(self):
        item = {"id": 300, "by": "user", "text": "hi"}
        result = format_comment(item)
        assert "time" not in result

    def test_empty_replies_not_included(self):
        result = format_comment(SAMPLE_COMMENT, replies=None)
        assert "replies" not in result


def _story_ids_and_items(ids, items):
    """Build a side_effect for fetch that returns story IDs first, then items."""
    responses = iter([ids] + items)
    return lambda *args, **kwargs: next(responses)


class TestGetTopStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345, 12346]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
            FetchResponse(
                status=200,
                headers={},
                data={**SAMPLE_STORY, "id": 12346, "title": "Second story"},
            ),
        ]

        result = await hackernews.execute_action(
            "get_top_stories", {"limit": 2}, mock_context
        )
        data = result.result.data

        assert "stories" in data
        assert data["count"] == 2
        assert "fetched_at" in data
        assert data["stories"][0]["id"] == 12345
        assert data["stories"][1]["id"] == 12346

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_context):
        mock_context.fetch.return_value = None

        result = await hackernews.execute_action(
            "get_top_stories", {"limit": 5}, mock_context
        )
        data = result.result.data

        assert data["stories"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
        ]

        result = await hackernews.execute_action("get_top_stories", {}, mock_context)
        data = result.result.data

        assert data["count"] == 1


class TestGetBestStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
        ]

        result = await hackernews.execute_action(
            "get_best_stories", {"limit": 3}, mock_context
        )
        data = result.result.data

        assert "stories" in data
        assert data["count"] == 1


class TestGetNewStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
        ]

        result = await hackernews.execute_action(
            "get_new_stories", {"limit": 3}, mock_context
        )
        data = result.result.data

        assert "stories" in data
        assert data["count"] == 1


class TestGetAskHNStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
        ]

        result = await hackernews.execute_action(
            "get_ask_hn_stories", {"limit": 3}, mock_context
        )
        data = result.result.data

        assert "stories" in data
        assert data["count"] == 1


class TestGetShowHNStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
        ]

        result = await hackernews.execute_action(
            "get_show_hn_stories", {"limit": 3}, mock_context
        )
        data = result.result.data

        assert "stories" in data
        assert data["count"] == 1


class TestGetJobStories:
    @pytest.mark.asyncio
    async def test_returns_jobs(self, mock_context):
        job_item = {**SAMPLE_STORY, "type": "job", "title": "Hiring Engineers"}
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[12345]),
            FetchResponse(status=200, headers={}, data=job_item),
        ]

        result = await hackernews.execute_action(
            "get_job_stories", {"limit": 3}, mock_context
        )
        data = result.result.data

        assert "jobs" in data
        assert data["count"] == 1
        assert data["jobs"][0]["type"] == "job"


class TestGetStoryWithComments:
    @pytest.mark.asyncio
    async def test_story_with_comments(self, mock_context):
        second_comment = {
            "id": 101,
            "type": "comment",
            "by": "commenter3",
            "text": "Nice work!",
            "time": 1700000300,
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
            FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT),
            FetchResponse(status=200, headers={}, data=second_comment),
            FetchResponse(status=200, headers={}, data=SAMPLE_REPLY),
        ]

        inputs = {"story_id": 12345, "comment_limit": 5, "comment_depth": 2}
        result = await hackernews.execute_action(
            "get_story_with_comments", inputs, mock_context
        )
        data = result.result.data

        assert data["story"]["id"] == 12345
        assert "comments" in data
        assert "fetched_at" in data
        assert len(data["comments"]) == 2
        assert data["comments"][0]["by"] == "commenter1"
        assert data["comments"][0]["replies"][0]["by"] == "commenter2"
        assert data["comments"][1]["by"] == "commenter3"

    @pytest.mark.asyncio
    async def test_story_not_found(self, mock_context):
        mock_context.fetch.return_value = None

        inputs = {"story_id": 99999}
        result = await hackernews.execute_action(
            "get_story_with_comments", inputs, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message is not None
        assert "99999" in result.result.message

    @pytest.mark.asyncio
    async def test_story_without_comments(self, mock_context):
        story_no_kids = {k: v for k, v in SAMPLE_STORY.items() if k != "kids"}
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=story_no_kids)
        ]

        inputs = {"story_id": 12345}
        result = await hackernews.execute_action(
            "get_story_with_comments", inputs, mock_context
        )
        data = result.result.data

        assert data["story"]["id"] == 12345
        assert data["comments"] == []

    @pytest.mark.asyncio
    async def test_deleted_comments_filtered(self, mock_context):
        deleted_comment = {**SAMPLE_COMMENT, "deleted": True}
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_STORY),
            FetchResponse(status=200, headers={}, data=deleted_comment),
            FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT),
        ]

        inputs = {"story_id": 12345, "comment_limit": 5, "comment_depth": 1}
        result = await hackernews.execute_action(
            "get_story_with_comments", inputs, mock_context
        )
        data = result.result.data

        assert len(data["comments"]) == 1
        assert data["comments"][0]["id"] == 100


class TestGetUserProfile:
    @pytest.mark.asyncio
    async def test_returns_profile(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_USER
        )

        result = await hackernews.execute_action(
            "get_user_profile", {"username": "dang"}, mock_context
        )
        data = result.result.data

        assert data["id"] == "dang"
        assert data["karma"] == 50000
        assert data["about"] == "HN moderator"
        assert "created" in data
        assert "profile_url" in data

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_context):
        mock_context.fetch.return_value = None

        result = await hackernews.execute_action(
            "get_user_profile", {"username": "nonexistent_user_xyz"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message is not None
        assert "nonexistent_user_xyz" in result.result.message

    @pytest.mark.asyncio
    async def test_user_without_about(self, mock_context):
        user = {k: v for k, v in SAMPLE_USER.items() if k != "about"}
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=user
        )

        result = await hackernews.execute_action(
            "get_user_profile", {"username": "dang"}, mock_context
        )
        data = result.result.data

        assert "about" not in data

    @pytest.mark.asyncio
    async def test_fetch_error_handled(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await hackernews.execute_action(
            "get_user_profile", {"username": "dang"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message is not None

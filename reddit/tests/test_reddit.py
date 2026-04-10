import asyncio
from typing import Any, Dict, Optional

from context import reddit  # integration instance


class MockExecutionContext:
    def __init__(self, responses: Dict[str, Any]):
        # mimic SDK context shape expected by reddit.py
        self.auth = {}  # OAuth handled by SDK
        self._responses = responses

    async def fetch(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs):
        # Route by endpoint for simplicity
        if "search" in url and method == "GET":
            return self._responses.get("GET /search", {"data": {"children": []}})
        if url.endswith("/hot") and method == "GET":
            return self._responses.get("GET /hot", {"data": {"children": []}})
        if url.endswith("/top") and method == "GET":
            return self._responses.get("GET /top", {"data": {"children": []}})
        if url.endswith("/new") and method == "GET":
            return self._responses.get("GET /new", {"data": {"children": []}})
        if url.endswith("/api/comment") and method == "POST":
            return self._responses.get("POST /api/comment", {"json": {"data": {"things": [{"data": {"id": "abc123", "permalink": "/r/test/comments/abc123/"}}]}}})
        return {}


async def test_search_subreddit_basic():
    responses = {
        "GET /search": {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "post1",
                            "title": "Test Post 1",
                            "selftext": "This is a test post",
                            "url": "https://reddit.com/r/test/post1",
                            "author": "testuser1",
                            "score": 100,
                            "num_comments": 5,
                            "created_utc": 1640995200.0,
                            "permalink": "/r/test/comments/post1/"
                        }
                    },
                    {
                        "data": {
                            "id": "post2",
                            "title": "Test Post 2",
                            "selftext": "",
                            "url": "https://example.com",
                            "author": "testuser2",
                            "score": 50,
                            "num_comments": 2,
                            "created_utc": 1640995300.0,
                            "permalink": "/r/test/comments/post2/"
                        }
                    }
                ]
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("search_subreddit", {
        "subreddit": "test", 
        "query": "python",
        "limit": 10
    }, context)
    
    assert "posts" in result
    assert len(result["posts"]) == 2
    assert result["posts"][0]["id"] == "post1"
    assert result["posts"][0]["title"] == "Test Post 1"
    assert result["posts"][0]["permalink"] == "https://reddit.com/r/test/comments/post1/"


async def test_search_subreddit_no_query():
    responses = {
        "GET /hot": {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "hot1",
                            "title": "Hot Post",
                            "selftext": "This is hot",
                            "url": "https://reddit.com/r/test/hot1",
                            "author": "hotuser",
                            "score": 500,
                            "num_comments": 20,
                            "created_utc": 1640995400.0,
                            "permalink": "/r/test/comments/hot1/"
                        }
                    }
                ]
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("search_subreddit", {
        "subreddit": "test",
        "sort": "hot"
    }, context)
    
    assert "posts" in result
    assert len(result["posts"]) == 1
    assert result["posts"][0]["id"] == "hot1"
    assert result["posts"][0]["title"] == "Hot Post"


async def test_search_subreddit_with_sort_and_time_filter():
    responses = {
        "GET /top": {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "top1",
                            "title": "Top Post This Week",
                            "selftext": "Weekly top post",
                            "url": "https://reddit.com/r/test/top1",
                            "author": "topuser",
                            "score": 1000,
                            "num_comments": 50,
                            "created_utc": 1640995500.0,
                            "permalink": "/r/test/comments/top1/"
                        }
                    }
                ]
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("search_subreddit", {
        "subreddit": "test",
        "sort": "top",
        "time_filter": "week",
        "limit": 5
    }, context)
    
    assert "posts" in result
    assert len(result["posts"]) == 1
    assert result["posts"][0]["score"] == 1000


async def test_search_subreddit_empty_results():
    responses = {
        "GET /search": {
            "data": {
                "children": []
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("search_subreddit", {
        "subreddit": "emptysub",
        "query": "nonexistent"
    }, context)
    
    assert "posts" in result
    assert len(result["posts"]) == 0


async def test_post_comment_success():
    responses = {
        "POST /api/comment": {
            "json": {
                "data": {
                    "things": [
                        {
                            "data": {
                                "id": "comment123",
                                "permalink": "/r/test/comments/post1/comment123/"
                            }
                        }
                    ]
                }
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("post_comment", {
        "parent_id": "t3_post1",
        "text": "This is a test comment"
    }, context)
    
    assert result["success"] == True
    assert result["comment_id"] == "comment123"
    assert result["permalink"] == "https://reddit.com/r/test/comments/post1/comment123/"


async def test_post_comment_with_error():
    responses = {
        "POST /api/comment": {
            "json": {
                "errors": [["THREAD_LOCKED", "thread is archived", None]]
            }
        }
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("post_comment", {
        "parent_id": "t3_archived_post",
        "text": "This should fail"
    }, context)
    
    assert result["success"] == False
    assert "error" in result
    assert "THREAD_LOCKED" in result["error"]


async def test_search_subreddit_missing_data():
    responses = {
        "GET /search": {}  # Missing data structure
    }
    context = MockExecutionContext(responses)
    result = await reddit.execute_action("search_subreddit", {
        "subreddit": "test",
        "query": "python"
    }, context)
    
    assert "posts" in result
    assert len(result["posts"]) == 0


async def main():
    await test_search_subreddit_basic()
    await test_search_subreddit_no_query()
    await test_search_subreddit_with_sort_and_time_filter()
    await test_search_subreddit_empty_results()
    await test_post_comment_success()
    await test_post_comment_with_error()
    await test_search_subreddit_missing_data()
    print("All tests passed")


if __name__ == "__main__":
    asyncio.run(main())

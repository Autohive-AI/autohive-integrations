import asyncio
from typing import Any, Dict, Optional

from context import gong  # integration instance


class MockExecutionContext:
    def __init__(self, responses: Dict[str, Any]):
        # mimic SDK context shape expected by gong.py
        self.auth = {}  # OAuth handled by SDK
        self.metadata = {"api_base_url": "https://api.gong.io"}
        self._responses = responses

    async def fetch(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, json: Any = None, headers: Optional[Dict[str, str]] = None, **kwargs):
        # Route by endpoint suffix for simplicity
        if url.endswith("/calls") and method == "GET":
            return self._responses.get("GET /calls", {"calls": [], "hasMore": False})
        
        # Match GET /calls/{id}
        if "/calls/" in url and method == "GET" and not url.endswith("/calls"):
             # Simple ID extraction or just return a default "GET /calls/{id}" mock
            return self._responses.get("GET /calls/{id}", {})
            
        if url.endswith("/calls/extensive") and method == "POST":
            return self._responses.get("POST /calls/extensive", {"calls": []})
        if url.endswith("/calls/transcript") and method == "POST":
            return self._responses.get("POST /calls/transcript", {"callTranscripts": []})
        if url.endswith("/users") and method == "GET":
            return self._responses.get("GET /users", {"users": [], "hasMore": False})
        return {}


async def test_list_calls_basic():
    responses = {
        "GET /calls": {
            "calls": [
                {"id": "2", "title": "B", "started": "2025-01-02T00:00:00Z", "duration": 5, "participants": [], "outcome": ""},
                {"id": "1", "title": "A", "started": "2025-01-01T00:00:00Z", "duration": 10, "participants": [], "outcome": ""},
            ],
            "hasMore": False,
            "nextCursor": None,
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("list_calls", {"limit": 2}, context)
    data = result.result.data
    assert "calls" in data and len(data["calls"]) == 2
    assert data["calls"][0]["id"] == "2"  # sorted newest first


async def test_get_call_details_shim():
    responses = {
        "GET /calls/{id}": {
            "call": {
                "id": "abc",
                "title": "Demo",
                "started": "2025-01-01T00:00:00Z",
                "duration": 60,
                # Basic GET doesn't return parties in this scenario
            }
        },
        "POST /calls/extensive": {
            "calls": [
                {
                    "id": "abc",
                    "parties": [{"userId": "u1", "name": "Jane"}],
                    "crmData": {"opp": 123},
                    "outcome": "Won"
                }
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("get_call_details", {"call_id": "abc"}, context)
    data = result.result.data
    assert data["id"] == "abc"
    assert data["title"] == "Demo"
    assert len(data["participants"]) == 1
    assert data["participants"][0]["name"] == "Jane"


async def test_get_call_transcript_mapping():
    responses = {
        "GET /calls/{id}": {
            "call": {"id": "xyz", "started": "2025-01-01T00:00:00Z"}
        },
        "POST /calls/extensive": {
            "calls": [
                {"parties": [{"speakerId": 1, "name": "Alice"}, {"speakerId": 2, "name": "Bob"}]}
            ]
        },
        "POST /calls/transcript": {
            "callTranscripts": [
                {"transcript": [
                    {"speakerId": 1, "sentences": [{"start": 0, "end": 1000, "text": "Hi"}]},
                    {"speakerId": 2, "sentences": [{"start": 1000, "end": 2000, "text": "Hello"}]}
                ]}
            ]
        },
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("get_call_transcript", {"call_id": "xyz"}, context)
    data = result.result.data
    assert len(data["transcript"]) == 2
    assert data["transcript"][0]["speaker_name"] == "Alice"


async def test_list_users():
    responses = {
        "GET /users": {
            "users": [
                {"id": "u1", "name": "Alice", "email": "a@example.com", "role": "admin", "active": True}
            ],
            "hasMore": False,
            "nextCursor": None,
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("list_users", {"limit": 1}, context)
    data = result.result.data
    assert data["users"][0]["id"] == "u1"


async def test_list_calls_filters_private():
    responses = {
        "GET /calls": {
            "calls": [
                {"id": "p1", "title": "Private", "started": "2025-01-03T00:00:00Z", "duration": 1, "isPrivate": True},
                {"id": "pub", "title": "Public", "started": "2025-01-02T00:00:00Z", "duration": 2, "isPrivate": False},
            ],
            "hasMore": False,
            "nextCursor": None,
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("list_calls", {"limit": 10}, context)
    data = result.result.data
    ids = [c["id"] for c in data["calls"]]
    assert "p1" not in ids and "pub" in ids


async def test_get_call_details_private_filtered():
    responses = {
        "GET /calls/{id}": {
            "id": "x",
            "isPrivate": True
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("get_call_details", {"call_id": "x"}, context)
    data = result.result.data
    assert data.get("error") == "private_call_filtered"
    assert data.get("id") == "x"
    assert data.get("duration") == 0


async def test_get_call_transcript_private_filtered():
    responses = {
        "GET /calls/{id}": {
            "id": "y",
            "isPrivate": True
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("get_call_transcript", {"call_id": "y"}, context)
    data = result.result.data
    assert data.get("error") == "private_call_filtered"
    assert data.get("transcript") == []


async def test_search_calls_skips_private():
    responses = {
        "POST /calls/extensive": {
            "calls": [
                {
                    "id": "priv",
                    "isPrivate": True,
                    "content": {"pointsOfInterest": [{"action": "demo pricing", "startTime": 0}]}
                },
                {
                    "id": "pub",
                    "isPrivate": False,
                    "title": "Public",
                    "started": "2025-01-01T00:00:00Z",
                    "content": {"pointsOfInterest": [{"action": "product demo pricing", "startTime": 10}]}
                }
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await gong.execute_action("search_calls", {"query": "pricing"}, context)
    data = result.result.data
    ids = [r["call_id"] for r in data["results"]]
    assert ids == ["pub"]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


if __name__ == "__main__":
    _run(test_list_calls_basic())
    _run(test_get_call_details_shim())
    _run(test_get_call_transcript_mapping())
    _run(test_list_users())
    # New tests for private call filtering
    _run(test_list_calls_filters_private())
    _run(test_get_call_details_private_filtered())
    _run(test_get_call_transcript_private_filtered())
    _run(test_search_calls_skips_private())
    print("All tests passed")






# Substack Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Substack integration with 8 actions covering publication posts, post content, publication info, publication search, post search, comments, subscriptions, and reader feed.

**Architecture:** Single `substack.py` entry point using the `autohive_integrations_sdk`. All HTTP via `context.fetch`. A shared `_normalise_url` helper and a shared `_build_headers` helper keep the action handlers thin. Authenticated actions (`get_subscriptions`, `get_reader_feed`) resolve the numeric user ID with a `/api/v1/profile` pre-flight call.

**Tech Stack:** Python 3.13+, `autohive_integrations_sdk`, `aiohttp` (required by SDK), no extra HTTP library.

**Spec:** `docs/superpowers/specs/2026-03-18-substack-integration-design.md`

---

## File Map

| File | Action |
|---|---|
| `substack/__init__.py` | Create (empty) |
| `substack/substack.py` | Create — integration entry point, all 8 action handlers |
| `substack/config.json` | Create — actions schema + custom auth |
| `substack/requirements.txt` | Create |
| `substack/README.md` | Create |
| `substack/icon.png` | Copy from another integration (placeholder) |
| `substack/tests/__init__.py` | Create (empty) |
| `substack/tests/context.py` | Create — sys.path setup + import |
| `substack/tests/test_substack.py` | Create — all test cases |
| `README.md` | Modify — add Substack to the integrations list |

---

## Task 1: Scaffold the integration folder

**Files:**
- Create: `substack/__init__.py`
- Create: `substack/requirements.txt`
- Create: `substack/tests/__init__.py`
- Create: `substack/tests/context.py`

- [ ] **Step 1: Create the folder structure**

```bash
mkdir -p substack/tests
```

- [ ] **Step 2: Create `substack/__init__.py`**

```python
```
(empty file)

- [ ] **Step 3: Create `substack/requirements.txt`**

```
autohive-integrations-sdk
aiohttp>=3.9.0
```

- [ ] **Step 4: Create `substack/tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 5: Create `substack/tests/context.py`**

```python
# -*- coding: utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
)

from substack import substack  # noqa: F401
```

- [ ] **Step 6: Copy an icon as placeholder**

```bash
cp hackernews/icon.png substack/icon.png
```

- [ ] **Step 7: Commit scaffold**

```bash
git add substack/
git commit -m "feat(substack): scaffold integration folder"
```

---

## Task 2: Write `config.json`

**Files:**
- Create: `substack/config.json`

- [ ] **Step 1: Create `substack/config.json`**

```json
{
    "name": "Substack",
    "version": "1.0.0",
    "description": "Read Substack publications, posts, comments, and your personal subscriptions and reader feed.",
    "entry_point": "substack.py",
    "auth": {
        "identifier": "substack_authentication",
        "type": "custom",
        "fields": {
            "type": "object",
            "properties": {
                "connect_sid": {
                    "type": "string",
                    "format": "password",
                    "label": "connect.sid cookie",
                    "help_text": "From browser DevTools → Application → Cookies → substack.com after logging in. Required for subscriptions and reader feed."
                },
                "substack_sid": {
                    "type": "string",
                    "format": "password",
                    "label": "substack.sid cookie",
                    "help_text": "Secondary session cookie from the same location as connect.sid. Required for subscriptions and reader feed."
                }
            },
            "required": []
        }
    },
    "actions": {
        "get_publication_posts": {
            "display_name": "Get Publication Posts",
            "description": "List posts from a Substack publication archive. Supports sorting, keyword filtering, and pagination.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "publication_url": {
                        "type": "string",
                        "description": "Base URL of the publication, e.g. https://example.substack.com or a custom domain."
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["new", "top"],
                        "description": "Sort order for posts.",
                        "default": "new"
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional keyword filter."
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of posts to skip for pagination.",
                        "default": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of posts to return.",
                        "default": 12,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["publication_url"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "posts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "slug": {"type": "string"},
                                "title": {"type": "string"},
                                "subtitle": {"type": "string"},
                                "post_date": {"type": "string"},
                                "canonical_url": {"type": "string"},
                                "audience": {"type": "string"},
                                "paywall": {"type": "boolean"},
                                "reading_time_minutes": {"type": "integer"},
                                "cover_image": {"type": "string"},
                                "like_count": {"type": "integer"},
                                "comment_count": {"type": "integer"},
                                "type": {"type": "string"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            }
        },
        "get_post": {
            "display_name": "Get Post",
            "description": "Fetch full content of a specific post by its slug. Body HTML is truncated for paywalled posts without a paid subscriber session.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "publication_url": {
                        "type": "string",
                        "description": "Base URL of the publication."
                    },
                    "slug": {
                        "type": "string",
                        "description": "Post slug from the URL or archive listing."
                    }
                },
                "required": ["publication_url", "slug"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "body_html": {"type": "string"},
                    "post_date": {"type": "string"},
                    "canonical_url": {"type": "string"},
                    "audience": {"type": "string"},
                    "paywall": {"type": "boolean"},
                    "reading_time_minutes": {"type": "integer"},
                    "cover_image": {"type": "string"},
                    "like_count": {"type": "integer"},
                    "comment_count": {"type": "integer"},
                    "type": {"type": "string"},
                    "audio_url": {"type": "string"}
                }
            }
        },
        "get_publication_info": {
            "display_name": "Get Publication Info",
            "description": "Fetch metadata about a Substack publication: name, description, subscriber count, logo, and more.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "publication_url": {
                        "type": "string",
                        "description": "Base URL of the publication."
                    }
                },
                "required": ["publication_url"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "subdomain": {"type": "string"},
                    "custom_domain": {"type": "string"},
                    "logo_url": {"type": "string"},
                    "cover_photo_url": {"type": "string"},
                    "hero_text": {"type": "string"},
                    "subscriber_count": {"type": "integer"},
                    "author_id": {"type": "integer"},
                    "email_from_name": {"type": "string"},
                    "type": {"type": "string"}
                }
            }
        },
        "search_publications": {
            "display_name": "Search Publications",
            "description": "Search for Substack publications by keyword across the entire platform.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query."
                    },
                    "page": {
                        "type": "integer",
                        "description": "0-based page number.",
                        "default": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page.",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["query"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "publications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "subdomain": {"type": "string"},
                                "custom_domain": {"type": "string"},
                                "logo_url": {"type": "string"},
                                "description": {"type": "string"},
                                "subscriber_count": {"type": "integer"}
                            }
                        }
                    },
                    "more": {"type": "boolean"}
                }
            }
        },
        "search_posts": {
            "display_name": "Search Posts",
            "description": "Search posts within a specific Substack publication by keyword.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "publication_url": {
                        "type": "string",
                        "description": "Base URL of the publication."
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query."
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset.",
                        "default": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results.",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["publication_url", "query"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "posts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "slug": {"type": "string"},
                                "title": {"type": "string"},
                                "subtitle": {"type": "string"},
                                "post_date": {"type": "string"},
                                "canonical_url": {"type": "string"},
                                "audience": {"type": "string"},
                                "paywall": {"type": "boolean"},
                                "reading_time_minutes": {"type": "integer"},
                                "cover_image": {"type": "string"},
                                "like_count": {"type": "integer"},
                                "comment_count": {"type": "integer"},
                                "type": {"type": "string"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            }
        },
        "get_post_comments": {
            "display_name": "Get Post Comments",
            "description": "Fetch comments for a specific post. Uses numeric post ID (from archive listing), not the slug.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "publication_url": {
                        "type": "string",
                        "description": "Base URL of the publication."
                    },
                    "post_id": {
                        "type": "integer",
                        "description": "Numeric post ID (the 'id' field from get_publication_posts or get_post)."
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["best", "newest"],
                        "description": "Sort order for comments.",
                        "default": "best"
                    },
                    "all_comments": {
                        "type": "boolean",
                        "description": "Return all comments.",
                        "default": true
                    }
                },
                "required": ["publication_url", "post_id"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "comments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "body": {"type": "string"},
                                "date": {"type": "string"},
                                "author_name": {"type": "string"},
                                "author_id": {"type": "integer"},
                                "like_count": {"type": "integer"},
                                "children": {"type": "array"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            }
        },
        "get_subscriptions": {
            "display_name": "Get Subscriptions",
            "description": "Fetch the authenticated user's Substack subscriptions. Requires connect_sid and substack_sid cookies.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "subscriptions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "subdomain": {"type": "string"},
                                "custom_domain": {"type": "string"},
                                "author_name": {"type": "string"},
                                "is_paid": {"type": "boolean"},
                                "subscriber_count": {"type": "integer"},
                                "logo_url": {"type": "string"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            }
        },
        "get_reader_feed": {
            "display_name": "Get Reader Feed",
            "description": "Fetch the authenticated user's Substack reader activity feed (likes and restacks). Requires connect_sid and substack_sid cookies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["like", "restack"]
                        },
                        "description": "Filter by activity type. Omit for all activity."
                    }
                },
                "required": []
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "date": {"type": "string"},
                                "post_title": {"type": "string"},
                                "post_url": {"type": "string"},
                                "publication_name": {"type": "string"},
                                "publication_url": {"type": "string"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            }
        }
    }
}
```

- [ ] **Step 2: Commit config**

```bash
git add substack/config.json
git commit -m "feat(substack): add config.json with 8 actions and custom auth schema"
```

---

## Task 3: Write helpers and failing tests

**Files:**
- Create: `substack/tests/test_substack.py`

The tests use a mock `ExecutionContext`. The mock's `fetch` method is patched per test to return controlled JSON. This is the standard pattern — do NOT use `unittest.mock.patch("httpx...")`.

- [ ] **Step 1: Create `substack/tests/test_substack.py` with all test cases**

```python
import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
)

from substack import substack  # noqa: E402


def make_context(auth=None, fetch_side_effect=None, fetch_return_value=None):
    """Create a mock ExecutionContext."""
    context = MagicMock()
    context.auth = auth or {}
    if fetch_side_effect is not None:
        context.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        context.fetch = AsyncMock(return_value=fetch_return_value)
    return context


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Helpers ──────────────────────────────────────────────────────────────────

class TestNormaliseUrl(unittest.TestCase):
    def _normalise(self, url):
        from substack.substack import _normalise_url
        return _normalise_url(url)

    def test_strips_trailing_slash(self):
        assert self._normalise("https://example.substack.com/") == "https://example.substack.com"

    def test_upgrades_http_to_https(self):
        assert self._normalise("http://example.substack.com") == "https://example.substack.com"

    def test_strips_path(self):
        assert self._normalise("https://example.substack.com/p/some-post") == "https://example.substack.com"

    def test_custom_domain_unchanged(self):
        assert self._normalise("https://newsletter.example.com") == "https://newsletter.example.com"

    def test_no_change_needed(self):
        assert self._normalise("https://example.substack.com") == "https://example.substack.com"


class TestBuildHeaders(unittest.TestCase):
    def _headers(self, auth):
        from substack.substack import _build_headers
        return _build_headers(auth)

    def test_no_auth_no_cookie_header(self):
        headers = self._headers({})
        assert "Cookie" not in headers

    def test_with_both_cookies(self):
        headers = self._headers({"connect_sid": "abc", "substack_sid": "xyz"})
        assert headers["Cookie"] == "connect.sid=abc; substack.sid=xyz"

    def test_with_only_connect_sid(self):
        headers = self._headers({"connect_sid": "abc"})
        assert "connect.sid=abc" in headers["Cookie"]
        assert "substack.sid" not in headers["Cookie"]

    def test_empty_strings_excluded(self):
        headers = self._headers({"connect_sid": "", "substack_sid": ""})
        assert "Cookie" not in headers


# ── get_publication_posts ─────────────────────────────────────────────────────

class TestGetPublicationPosts(unittest.TestCase):
    MOCK_RESPONSE = [
        {
            "id": 123,
            "slug": "hello-world",
            "title": "Hello World",
            "subtitle": "A subtitle",
            "post_date": "2024-01-01T00:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/hello-world",
            "audience": "everyone",
            "paywall": False,
            "reading_time_minutes": 3,
            "cover_image": None,
            "like_count": 10,
            "comment_count": 2,
            "type": "newsletter",
        }
    ]

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            context,
        ))
        assert len(result["posts"]) == 1
        assert result["posts"][0]["slug"] == "hello-world"
        assert result["count"] == 1

    def test_passes_pagination_params(self):
        context = make_context(fetch_return_value=[])
        run(substack.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com", "offset": 12, "limit": 6},
            context,
        ))
        call_kwargs = context.fetch.call_args
        # params should include offset and limit
        params = call_kwargs[1].get("params") or call_kwargs[0][2] if len(call_kwargs[0]) > 2 else {}
        assert params.get("offset") == 12
        assert params.get("limit") == 6

    def test_url_normalisation(self):
        context = make_context(fetch_return_value=[])
        run(substack.execute_action(
            "get_publication_posts",
            {"publication_url": "http://example.substack.com/"},
            context,
        ))
        url_called = context.fetch.call_args[0][0]
        assert url_called.startswith("https://example.substack.com")

    def test_no_auth_no_cookie_header(self):
        context = make_context(auth={}, fetch_return_value=[])
        run(substack.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            context,
        ))
        headers = context.fetch.call_args[1].get("headers", {})
        assert "Cookie" not in headers

    def test_auth_sets_cookie_header(self):
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_return_value=[],
        )
        run(substack.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            context,
        ))
        headers = context.fetch.call_args[1].get("headers", {})
        assert "Cookie" in headers


# ── get_post ──────────────────────────────────────────────────────────────────

class TestGetPost(unittest.TestCase):
    MOCK_RESPONSE = {
        "id": 123,
        "slug": "hello-world",
        "title": "Hello World",
        "subtitle": "A subtitle",
        "body_html": "<p>Content here</p>",
        "post_date": "2024-01-01T00:00:00.000Z",
        "canonical_url": "https://example.substack.com/p/hello-world",
        "audience": "everyone",
        "paywall": False,
        "reading_time_minutes": 3,
        "cover_image": None,
        "like_count": 10,
        "comment_count": 2,
        "type": "newsletter",
        "audio_url": None,
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            context,
        ))
        assert result["slug"] == "hello-world"
        assert result["body_html"] == "<p>Content here</p>"

    def test_url_contains_slug(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(substack.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            context,
        ))
        url_called = context.fetch.call_args[0][0]
        assert "hello-world" in url_called


# ── get_publication_info ──────────────────────────────────────────────────────

class TestGetPublicationInfo(unittest.TestCase):
    MOCK_RESPONSE = {
        "id": 1,
        "name": "Example Newsletter",
        "subdomain": "example",
        "custom_domain": None,
        "logo_url": "https://example.com/logo.png",
        "cover_photo_url": None,
        "hero_text": "A great newsletter",
        "subscriber_count": 1000,
        "author_id": 42,
        "email_from_name": "Author Name",
        "type": "newsletter",
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "get_publication_info",
            {"publication_url": "https://example.substack.com"},
            context,
        ))
        assert result["name"] == "Example Newsletter"
        assert result["subscriber_count"] == 1000


# ── search_publications ───────────────────────────────────────────────────────

class TestSearchPublications(unittest.TestCase):
    MOCK_RESPONSE = {
        "publications": [
            {
                "id": 1,
                "name": "Example Newsletter",
                "subdomain": "example",
                "custom_domain": None,
                "logo_url": None,
                "description": "A newsletter about things",
                "subscriber_count": 500,
            }
        ],
        "more": False,
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "search_publications",
            {"query": "tech"},
            context,
        ))
        assert len(result["publications"]) == 1
        assert result["more"] is False

    def test_passes_query_param(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(substack.execute_action(
            "search_publications",
            {"query": "finance"},
            context,
        ))
        call_kwargs = context.fetch.call_args
        params = call_kwargs[1].get("params", {})
        assert params.get("query") == "finance"


# ── search_posts ──────────────────────────────────────────────────────────────

class TestSearchPosts(unittest.TestCase):
    MOCK_RESPONSE = [
        {
            "id": 99,
            "slug": "matching-post",
            "title": "Matching Post",
            "subtitle": "",
            "post_date": "2024-06-01T00:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/matching-post",
            "audience": "everyone",
            "paywall": False,
            "reading_time_minutes": 2,
            "cover_image": None,
            "like_count": 5,
            "comment_count": 1,
            "type": "newsletter",
        }
    ]

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "keyword"},
            context,
        ))
        assert len(result["posts"]) == 1
        assert result["posts"][0]["slug"] == "matching-post"

    def test_limit_maximum_passed(self):
        context = make_context(fetch_return_value=[])
        run(substack.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "x", "limit": 50},
            context,
        ))
        params = context.fetch.call_args[1].get("params", {})
        assert params.get("limit") == 50


# ── get_post_comments ─────────────────────────────────────────────────────────

class TestGetPostComments(unittest.TestCase):
    MOCK_RESPONSE = {
        "comments": [
            {
                "id": 1001,
                "body": "Great post!",
                "date": "2024-01-02T00:00:00.000Z",
                "author_name": "Alice",
                "author_id": 55,
                "like_count": 3,
                "children": [],
            }
        ]
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(substack.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            context,
        ))
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author_name"] == "Alice"

    def test_url_uses_singular_post_path(self):
        """URL must use /api/v1/post/ (singular), not /api/v1/posts/."""
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(substack.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            context,
        ))
        url_called = context.fetch.call_args[0][0]
        assert "/api/v1/post/123/comments" in url_called
        assert "/api/v1/posts/123/comments" not in url_called


# ── get_subscriptions ─────────────────────────────────────────────────────────

class TestGetSubscriptions(unittest.TestCase):
    PROFILE_RESPONSE = {"id": 999, "name": "Test User"}
    PROFILE_DATA_RESPONSE = {
        "subscriptions": [
            {
                "name": "Cool Newsletter",
                "subdomain": "cool",
                "custom_domain": None,
                "author_name": "Bob",
                "is_paid": False,
                "subscriber_count": 200,
                "logo_url": None,
            }
        ]
    }

    def test_success(self):
        responses = [self.PROFILE_RESPONSE, self.PROFILE_DATA_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        result = run(substack.execute_action("get_subscriptions", {}, context))
        assert len(result["subscriptions"]) == 1
        assert result["subscriptions"][0]["name"] == "Cool Newsletter"

    def test_preflight_401_raises_auth_error(self):
        from autohive_integrations_sdk import AuthError
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=AuthError("Unauthorized"),
        )
        with self.assertRaises(AuthError):
            run(substack.execute_action("get_subscriptions", {}, context))

    def test_makes_two_fetch_calls(self):
        responses = [self.PROFILE_RESPONSE, self.PROFILE_DATA_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        run(substack.execute_action("get_subscriptions", {}, context))
        assert context.fetch.call_count == 2


# ── get_reader_feed ───────────────────────────────────────────────────────────

class TestGetReaderFeed(unittest.TestCase):
    PROFILE_RESPONSE = {"id": 999}
    FEED_RESPONSE = {
        "items": [
            {
                "id": "item-1",
                "type": "like",
                "date": "2024-02-01T00:00:00.000Z",
                "post_title": "A Post I Liked",
                "post_url": "https://example.substack.com/p/a-post",
                "publication_name": "Example Newsletter",
                "publication_url": "https://example.substack.com",
            }
        ]
    }

    def test_success(self):
        responses = [self.PROFILE_RESPONSE, self.FEED_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        result = run(substack.execute_action("get_reader_feed", {}, context))
        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "like"

    def test_preflight_401_raises_auth_error(self):
        from autohive_integrations_sdk import AuthError
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=AuthError("Unauthorized"),
        )
        with self.assertRaises(AuthError):
            run(substack.execute_action("get_reader_feed", {}, context))

    def test_types_filter_passed_as_params(self):
        responses = [self.PROFILE_RESPONSE, self.FEED_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        run(substack.execute_action(
            "get_reader_feed",
            {"types": ["like"]},
            context,
        ))
        # Second call is the feed call — check its params
        feed_call = context.fetch.call_args_list[1]
        params = feed_call[1].get("params", {})
        assert "like" in str(params)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — confirm they all fail (module not found)**

```bash
cd substack/tests && python -m pytest test_substack.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `substack.py` doesn't exist yet.

- [ ] **Step 3: Commit failing tests**

```bash
git add substack/tests/test_substack.py
git commit -m "test(substack): add failing tests for all 8 actions"
```

---

## Task 4: Implement `substack.py`

**Files:**
- Create: `substack/substack.py`

- [ ] **Step 1: Create `substack/substack.py`**

```python
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    AuthError,
    NotFoundError,
    RateLimitError,
    ServerError,
    APIError,
)
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urlunparse

substack = Integration.load()

SUBSTACK_BASE = "https://substack.com"


# ── Shared helpers ────────────────────────────────────────────────────────────

def _normalise_url(url: str) -> str:
    """Normalise a publication URL: enforce https, strip path, strip trailing slash."""
    parsed = urlparse(url)
    # Upgrade http to https
    scheme = "https"
    # Strip path — keep only scheme + netloc
    normalised = urlunparse((scheme, parsed.netloc, "", "", "", ""))
    return normalised.rstrip("/")


def _build_headers(auth: Dict[str, Any]) -> Dict[str, str]:
    """Build request headers, adding Cookie header if session credentials provided."""
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    cookie_parts = []
    connect_sid = (auth or {}).get("connect_sid", "")
    substack_sid = (auth or {}).get("substack_sid", "")
    if connect_sid:
        cookie_parts.append(f"connect.sid={connect_sid}")
    if substack_sid:
        cookie_parts.append(f"substack.sid={substack_sid}")
    if cookie_parts:
        headers["Cookie"] = "; ".join(cookie_parts)
    return headers


def _handle_http_error(status_code: int, message: str = "") -> None:
    """Raise the appropriate SDK error for a given HTTP status code."""
    if status_code in (401, 403):
        raise AuthError(message or f"Authentication required (HTTP {status_code})")
    if status_code == 404:
        raise NotFoundError(message or "Resource not found")
    if status_code == 429:
        raise RateLimitError(message or "Rate limited by Substack")
    if status_code >= 500:
        raise ServerError(message or f"Substack server error (HTTP {status_code})")
    raise APIError(message or f"Substack API error (HTTP {status_code})")


def _format_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the standard post fields used by list/search actions."""
    return {
        "id": post.get("id"),
        "slug": post.get("slug", ""),
        "title": post.get("title", ""),
        "subtitle": post.get("subtitle", ""),
        "post_date": post.get("post_date", ""),
        "canonical_url": post.get("canonical_url", ""),
        "audience": post.get("audience", ""),
        "paywall": post.get("paywall", False),
        "reading_time_minutes": post.get("reading_time_minutes"),
        "cover_image": post.get("cover_image"),
        "like_count": post.get("like_count", 0),
        "comment_count": post.get("comment_count", 0),
        "type": post.get("type", ""),
    }


async def _resolve_user_id(context: ExecutionContext, headers: Dict[str, str]) -> int:
    """Resolve the authenticated user's numeric ID via /api/v1/profile."""
    profile = await context.fetch(
        f"{SUBSTACK_BASE}/api/v1/profile",
        method="GET",
        headers=headers,
    )
    return profile["id"]


# ── Action handlers ───────────────────────────────────────────────────────────

@substack.action("get_publication_posts")
class GetPublicationPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)
        params: Dict[str, Any] = {
            "sort": inputs.get("sort", "new"),
            "offset": inputs.get("offset", 0),
            "limit": min(inputs.get("limit", 12), 50),
        }
        if inputs.get("search"):
            params["search"] = inputs["search"]

        posts_raw = await context.fetch(
            f"{base_url}/api/v1/archive",
            method="GET",
            params=params,
            headers=headers,
        )
        posts = [_format_post(p) for p in (posts_raw or [])]
        return ActionResult(data={"posts": posts, "count": len(posts)}, cost_usd=0.0)


@substack.action("get_post")
class GetPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        slug = inputs["slug"]
        headers = _build_headers(context.auth)

        post = await context.fetch(
            f"{base_url}/api/v1/posts/{slug}",
            method="GET",
            headers=headers,
        )
        result = {
            "id": post.get("id"),
            "slug": post.get("slug", ""),
            "title": post.get("title", ""),
            "subtitle": post.get("subtitle", ""),
            "body_html": post.get("body_html", ""),
            "post_date": post.get("post_date", ""),
            "canonical_url": post.get("canonical_url", ""),
            "audience": post.get("audience", ""),
            "paywall": post.get("paywall", False),
            "reading_time_minutes": post.get("reading_time_minutes"),
            "cover_image": post.get("cover_image"),
            "like_count": post.get("like_count", 0),
            "comment_count": post.get("comment_count", 0),
            "type": post.get("type", ""),
            "audio_url": post.get("audio_url"),
        }
        return ActionResult(data=result, cost_usd=0.0)


@substack.action("get_publication_info")
class GetPublicationInfoAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)

        pub = await context.fetch(
            f"{base_url}/api/v1/publication",
            method="GET",
            headers=headers,
        )
        result = {
            "id": pub.get("id"),
            "name": pub.get("name", ""),
            "subdomain": pub.get("subdomain", ""),
            "custom_domain": pub.get("custom_domain"),
            "logo_url": pub.get("logo_url"),
            "cover_photo_url": pub.get("cover_photo_url"),
            "hero_text": pub.get("hero_text", ""),
            "subscriber_count": pub.get("subscriber_count"),
            "author_id": pub.get("author_id"),
            "email_from_name": pub.get("email_from_name", ""),
            "type": pub.get("type", ""),
        }
        return ActionResult(data=result, cost_usd=0.0)


@substack.action("search_publications")
class SearchPublicationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)
        params = {
            "query": inputs["query"],
            "page": inputs.get("page", 0),
            "limit": min(inputs.get("limit", 10), 100),
        }

        response = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/publication/search",
            method="GET",
            params=params,
            headers=headers,
        )
        pubs_raw = response.get("publications", []) if isinstance(response, dict) else response
        pubs = [
            {
                "id": p.get("id"),
                "name": p.get("name", ""),
                "subdomain": p.get("subdomain", ""),
                "custom_domain": p.get("custom_domain"),
                "logo_url": p.get("logo_url"),
                "description": p.get("description", ""),
                "subscriber_count": p.get("subscriber_count"),
            }
            for p in pubs_raw
        ]
        more = response.get("more", False) if isinstance(response, dict) else False
        return ActionResult(data={"publications": pubs, "more": more}, cost_usd=0.0)


@substack.action("search_posts")
class SearchPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)
        params = {
            "query": inputs["query"],
            "offset": inputs.get("offset", 0),
            "limit": min(inputs.get("limit", 10), 50),
        }

        posts_raw = await context.fetch(
            f"{base_url}/api/v1/posts/search",
            method="GET",
            params=params,
            headers=headers,
        )
        posts = [_format_post(p) for p in (posts_raw or [])]
        return ActionResult(data={"posts": posts, "count": len(posts)}, cost_usd=0.0)


@substack.action("get_post_comments")
class GetPostCommentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        post_id = inputs["post_id"]
        headers = _build_headers(context.auth)
        params = {
            "sort": inputs.get("sort", "best"),
            "all_comments": str(inputs.get("all_comments", True)).lower(),
        }

        # NOTE: path is singular /post/ not /posts/
        response = await context.fetch(
            f"{base_url}/api/v1/post/{post_id}/comments",
            method="GET",
            params=params,
            headers=headers,
        )
        comments = response.get("comments", []) if isinstance(response, dict) else []
        return ActionResult(data={"comments": comments, "count": len(comments)}, cost_usd=0.0)


@substack.action("get_subscriptions")
class GetSubscriptionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)

        # Step 1: resolve user ID (raises AuthError on 401/403)
        user_id = await _resolve_user_id(context, headers)

        # Step 2: fetch profile with subscriptions
        profile_data = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/user/{user_id}/public_profile/self",
            method="GET",
            headers=headers,
        )
        subs_raw = profile_data.get("subscriptions", [])
        subs = [
            {
                "name": s.get("name", ""),
                "subdomain": s.get("subdomain", ""),
                "custom_domain": s.get("custom_domain"),
                "author_name": s.get("author_name", ""),
                "is_paid": s.get("is_paid", False),
                "subscriber_count": s.get("subscriber_count"),
                "logo_url": s.get("logo_url"),
            }
            for s in subs_raw
        ]
        return ActionResult(data={"subscriptions": subs, "count": len(subs)}, cost_usd=0.0)


@substack.action("get_reader_feed")
class GetReaderFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)

        # Step 1: resolve user ID
        user_id = await _resolve_user_id(context, headers)

        # Step 2: fetch reader feed
        params: Dict[str, Any] = {}
        types = inputs.get("types")
        if types:
            params["types[]"] = types

        response = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/reader/feed/profile/{user_id}",
            method="GET",
            params=params,
            headers=headers,
        )
        items_raw = response.get("items", []) if isinstance(response, dict) else []
        items = [
            {
                "id": item.get("id", ""),
                "type": item.get("type", ""),
                "date": item.get("date", ""),
                "post_title": item.get("post_title", ""),
                "post_url": item.get("post_url", ""),
                "publication_name": item.get("publication_name", ""),
                "publication_url": item.get("publication_url", ""),
            }
            for item in items_raw
        ]
        return ActionResult(data={"items": items, "count": len(items)}, cost_usd=0.0)
```

- [ ] **Step 2: Run tests — confirm they pass**

```bash
cd substack/tests && python -m pytest test_substack.py -v
```

Expected: All tests pass. If any fail, fix only the failing handler — do not change the tests.

- [ ] **Step 3: Commit implementation**

```bash
git add substack/substack.py
git commit -m "feat(substack): implement all 8 action handlers"
```

---

## Task 5: Write README and update main README

**Files:**
- Create: `substack/README.md`
- Modify: `README.md`

- [ ] **Step 1: Create `substack/README.md`**

```markdown
# Substack

Read Substack publications, posts, comments, and your personal subscriptions and reader feed.

> **Note:** Substack has no official public API. This integration uses internal endpoints that are widely used but undocumented and subject to change. Personal/automation use is low risk; commercial use should review Substack's ToS.

## Authentication

Authentication is optional — public actions work without credentials. To access your subscriptions and reader feed, provide session cookies from your browser:

1. Log in to [substack.com](https://substack.com) in your browser
2. Open DevTools → Application → Cookies → `substack.com`
3. Copy the values of `connect.sid` and `substack.sid`

> Cookies are invalidated when you log out. Consider using a dedicated account for automation.

## Actions

| Action | Auth Required | Description |
|---|---|---|
| `get_publication_posts` | No | List posts from a publication archive |
| `get_post` | No | Get full post content by slug |
| `get_publication_info` | No | Get publication metadata |
| `search_publications` | No | Search publications across Substack |
| `search_posts` | No | Search posts within a publication |
| `get_post_comments` | No | Get comments on a post |
| `get_subscriptions` | Yes | List your subscriptions |
| `get_reader_feed` | Yes | Get your reader activity feed |

## Notes

- Paywalled post `body_html` is truncated without a paid subscriber session
- `get_post_comments` requires the numeric `post_id` (from `get_publication_posts`), not the slug
- `get_subscriptions` and `get_reader_feed` make two HTTP requests per invocation to resolve your user ID
```

- [ ] **Step 2: Add Substack to the main `README.md`**

Find the integrations list section in `README.md` and add an entry for Substack in alphabetical order:

```markdown
[substack](substack): Read Substack publications, posts, comments, and personal subscriptions. Supports listing publication archives, fetching full post content, searching publications and posts, retrieving comments, and accessing authenticated subscriptions and reader activity feed via session cookie auth. 8 actions covering public and subscriber-only content.
```

- [ ] **Step 3: Commit docs**

```bash
git add substack/README.md README.md
git commit -m "docs(substack): add README and update main integrations list"
```

---

## Task 6: Final validation

- [ ] **Step 1: Run full test suite**

```bash
cd substack/tests && python -m pytest test_substack.py -v
```

Expected: All tests pass with no warnings.

- [ ] **Step 2: Run ruff lint**

```bash
ruff check substack/
```

Expected: No errors. If there are issues, run `ruff check --fix substack/` then re-check.

- [ ] **Step 3: Run ruff format**

```bash
ruff format substack/
```

- [ ] **Step 4: Commit any lint/format fixes**

```bash
git add substack/
git commit -m "style(substack): apply ruff lint and format fixes"
```

Only create this commit if there were actual changes. Skip if nothing changed.

- [ ] **Step 5: Final commit summary**

```bash
git log --oneline -6
```

Expected output should show commits for: scaffold, config, tests, implementation, docs, (optionally) style.

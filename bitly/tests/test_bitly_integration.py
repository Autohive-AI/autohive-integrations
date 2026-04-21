"""
End-to-end integration tests for the Bitly integration (read-only actions).

These tests call the real Bitly API and require a valid OAuth access token
set in the BITLY_ACCESS_TOKEN environment variable (via .env or export).

Write actions (shorten_url, create_bitlink, update_bitlink) are intentionally
excluded — they create/modify real data in the Bitly account.

Some tests require at least one bitlink to exist in the account. These will
skip gracefully if none are found:
    - TestGetBitlink
    - TestExpandBitlink
    - TestGetClicks
    - TestGetClicksSummary

Run with:
    pytest bitly/tests/test_bitly_integration.py -m integration

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
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "bitly_mod", os.path.join(_parent, "bitly.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

bitly = _mod.bitly

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("BITLY_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with Bitly OAuth token.

    The Bitly integration relies on context.fetch to auto-inject the OAuth token
    (auth.type = "platform"). In tests we bypass the SDK auth layer and manually
    add the Authorization header to every request.
    """
    if not ACCESS_TOKEN:
        pytest.skip("BITLY_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(
        url, *, method="GET", json=None, headers=None, params=None, **kwargs
    ):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, headers=merged_headers, params=params
            ) as resp:
                data = await resp.json()
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---- User ----


class TestGetUser:
    async def test_returns_user_info(self, live_context):
        result = await bitly.execute_action("get_user", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "user" in data
        user = data["user"]
        assert "login" in user
        assert "default_group_guid" in user


# ---- Groups & Organizations ----


class TestListGroups:
    async def test_returns_groups(self, live_context):
        result = await bitly.execute_action("list_groups", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "groups" in data
        assert len(data["groups"]) > 0

    async def test_group_structure(self, live_context):
        result = await bitly.execute_action("list_groups", {}, live_context)

        group = result.result.data["groups"][0]
        assert "guid" in group
        assert "organization_guid" in group


class TestGetGroup:
    async def test_fetches_group_by_guid(self, live_context):
        # First get a real group GUID
        groups_result = await bitly.execute_action("list_groups", {}, live_context)
        group_guid = groups_result.result.data["groups"][0]["guid"]

        result = await bitly.execute_action(
            "get_group", {"group_guid": group_guid}, live_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["group"]["guid"] == group_guid


class TestListOrganizations:
    async def test_returns_organizations(self, live_context):
        result = await bitly.execute_action("list_organizations", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "organizations" in data
        assert len(data["organizations"]) > 0


# ---- Bitlinks ----


class TestListBitlinks:
    async def test_returns_bitlinks(self, live_context):
        result = await bitly.execute_action("list_bitlinks", {"size": 5}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "bitlinks" in data


class TestGetBitlink:
    async def test_fetches_bitlink_details(self, live_context):
        # First get a real bitlink from the account
        list_result = await bitly.execute_action(
            "list_bitlinks", {"size": 1}, live_context
        )
        bitlinks = list_result.result.data["bitlinks"]

        if not bitlinks:
            pytest.skip("No bitlinks in account to test with")

        bitlink_id = bitlinks[0].get("id", bitlinks[0].get("link", ""))

        result = await bitly.execute_action(
            "get_bitlink", {"bitlink": bitlink_id}, live_context
        )

        data = result.result.data
        assert data["result"] is True
        assert "bitlink" in data
        assert "long_url" in data["bitlink"]


class TestExpandBitlink:
    async def test_expands_to_long_url(self, live_context):
        list_result = await bitly.execute_action(
            "list_bitlinks", {"size": 1}, live_context
        )
        bitlinks = list_result.result.data["bitlinks"]

        if not bitlinks:
            pytest.skip("No bitlinks in account to test with")

        bitlink_id = bitlinks[0].get("id", bitlinks[0].get("link", ""))

        result = await bitly.execute_action(
            "expand_bitlink", {"bitlink": bitlink_id}, live_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["long_url"] != ""
        assert data["long_url"].startswith("http")


# ---- Click Analytics ----


class TestGetClicks:
    async def test_returns_click_data(self, live_context):
        list_result = await bitly.execute_action(
            "list_bitlinks", {"size": 1}, live_context
        )
        bitlinks = list_result.result.data["bitlinks"]

        if not bitlinks:
            pytest.skip("No bitlinks in account to test with")

        bitlink_id = bitlinks[0].get("id", bitlinks[0].get("link", ""))

        result = await bitly.execute_action(
            "get_clicks",
            {"bitlink": bitlink_id, "unit": "day", "units": 7},
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "clicks" in data


class TestGetClicksSummary:
    async def test_returns_summary(self, live_context):
        list_result = await bitly.execute_action(
            "list_bitlinks", {"size": 1}, live_context
        )
        bitlinks = list_result.result.data["bitlinks"]

        if not bitlinks:
            pytest.skip("No bitlinks in account to test with")

        bitlink_id = bitlinks[0].get("id", bitlinks[0].get("link", ""))

        result = await bitly.execute_action(
            "get_clicks_summary",
            {"bitlink": bitlink_id, "unit": "day", "units": 30},
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "total_clicks" in data
        assert isinstance(data["total_clicks"], int)

"""
Live integration smoke tests for the Trello integration.

These tests hit the real Trello API and are **opt-in only** — they are skipped
unless ``TRELLO_API_KEY`` and ``TRELLO_API_TOKEN`` are set in the environment
(or in a project-root ``.env`` file picked up by the root ``conftest.py``).

Run with::

    pytest trello/tests/test_trello_integration.py -m integration

They will never run in CI (see ``pyproject.toml``: default discovery is
``test_*_unit.py`` only).
"""

from __future__ import annotations

import os
import sys

import pytest
from autohive_integrations_sdk import ActionError, ActionResult, ExecutionContext

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from trello.trello import trello as trello_integration  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture
def trello_auth():
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_API_TOKEN")
    if not api_key or not token:
        pytest.skip("TRELLO_API_KEY and TRELLO_API_TOKEN must be set for integration tests")
    return {
        "auth_type": "custom",
        "credentials": {"api_key": api_key, "token": token},
    }


def _assert_ok(result):
    assert not isinstance(result, ActionError), (
        f"Expected success but got ActionError: {getattr(result, 'message', result)!r}"
    )
    assert isinstance(result, ActionResult)
    return result.data


@pytest.mark.asyncio
async def test_get_current_member(trello_auth):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("get_current_member", {}, context)
    data = _assert_ok(result)
    assert "member" in data
    assert data["member"].get("id")


@pytest.mark.asyncio
async def test_list_boards(trello_auth):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("list_boards", {"filter": "open"}, context)
    data = _assert_ok(result)
    assert "boards" in data and "count" in data
    assert data["count"] == len(data["boards"])


@pytest.mark.asyncio
async def test_search_cards_by_name(trello_auth):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "search_cards",
            {"card_name": "a", "limit": 5, "partial": True},
            context,
        )
    data = _assert_ok(result)
    assert "cards" in data and "count" in data
    assert data["count"] == len(data["cards"])
    assert data["count"] <= 5

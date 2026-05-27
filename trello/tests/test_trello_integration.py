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
from autohive_integrations_sdk import ActionError, ActionResult, ExecutionContext, IntegrationResult
from autohive_integrations_sdk.integration import ResultType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from trello.trello import trello as trello_integration  # noqa: E402

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Auth fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def trello_auth():
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_API_TOKEN")
    if not api_key or not token:
        pytest.skip("TRELLO_API_KEY and TRELLO_API_TOKEN must be set for integration tests")
    return {
        "auth_type": "Custom",
        "credentials": {"api_key": api_key, "token": token},
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_ok(result):
    if isinstance(result, IntegrationResult):
        assert result.type != ResultType.ACTION_ERROR, (
            f"Expected success but got ActionError: {getattr(result.result, 'message', result)!r}"
        )
        return result.result.data
    assert not isinstance(result, ActionError), (
        f"Expected success but got ActionError: {getattr(result, 'message', result)!r}"
    )
    assert isinstance(result, ActionResult)
    return result.data


# ---------------------------------------------------------------------------
# Session-scoped shared resources (created once, reused across all tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def board_id(trello_auth, event_loop_policy):
    """Create a test board and delete it after the session."""
    import asyncio

    async def _create():
        async with ExecutionContext(auth=trello_auth) as ctx:
            result = await trello_integration.execute_action(
                "create_board",
                {"name": "Autohive Integration Test Board", "defaultLists": False},
                ctx,
            )
        return _assert_ok(result)["board"]["id"]

    async def _delete(bid):
        async with ExecutionContext(auth=trello_auth) as ctx:
            await trello_integration.execute_action("update_board", {"board_id": bid, "closed": True}, ctx)

    bid = asyncio.get_event_loop().run_until_complete(_create())
    yield bid
    asyncio.get_event_loop().run_until_complete(_delete(bid))


@pytest.fixture(scope="session")
def list_id(trello_auth, board_id, event_loop_policy):
    import asyncio

    async def _create():
        async with ExecutionContext(auth=trello_auth) as ctx:
            result = await trello_integration.execute_action(
                "create_list",
                {"board_id": board_id, "name": "Test List"},
                ctx,
            )
        return _assert_ok(result)["list"]["id"]

    return asyncio.get_event_loop().run_until_complete(_create())


@pytest.fixture(scope="session")
def card_id(trello_auth, list_id, event_loop_policy):
    import asyncio

    async def _create():
        async with ExecutionContext(auth=trello_auth) as ctx:
            result = await trello_integration.execute_action(
                "create_card",
                {"list_id": list_id, "name": "Test Card", "desc": "Integration test card"},
                ctx,
            )
        return _assert_ok(result)["card"]["id"]

    return asyncio.get_event_loop().run_until_complete(_create())


@pytest.fixture(scope="session")
def checklist_id(trello_auth, card_id, event_loop_policy):
    import asyncio

    async def _create():
        async with ExecutionContext(auth=trello_auth) as ctx:
            result = await trello_integration.execute_action(
                "create_checklist",
                {"card_id": card_id, "name": "Test Checklist"},
                ctx,
            )
        return _assert_ok(result)["checklist"]["id"]

    return asyncio.get_event_loop().run_until_complete(_create())


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_member(trello_auth):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("get_current_member", {}, context)
    data = _assert_ok(result)
    assert "member" in data
    assert data["member"].get("id")


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_board(trello_auth, board_id):
    # board_id fixture already created it — just verify it's a non-empty string
    assert isinstance(board_id, str) and board_id


@pytest.mark.asyncio
async def test_get_board(trello_auth, board_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("get_board", {"board_id": board_id}, context)
    data = _assert_ok(result)
    assert data["board"]["id"] == board_id
    assert "name" in data["board"]


@pytest.mark.asyncio
async def test_update_board(trello_auth, board_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "update_board",
            {"board_id": board_id, "desc": "Updated by integration test"},
            context,
        )
    data = _assert_ok(result)
    assert data["board"]["id"] == board_id


@pytest.mark.asyncio
async def test_list_boards(trello_auth):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("list_boards", {"filter": "open"}, context)
    data = _assert_ok(result)
    assert "boards" in data and "count" in data
    assert data["count"] == len(data["boards"])
    assert data["count"] >= 1


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_list(trello_auth, list_id):
    assert isinstance(list_id, str) and list_id


@pytest.mark.asyncio
async def test_get_list(trello_auth, list_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("get_list", {"list_id": list_id}, context)
    data = _assert_ok(result)
    assert data["list"]["id"] == list_id


@pytest.mark.asyncio
async def test_update_list(trello_auth, list_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "update_list",
            {"list_id": list_id, "name": "Updated Test List"},
            context,
        )
    data = _assert_ok(result)
    assert data["list"]["id"] == list_id


@pytest.mark.asyncio
async def test_list_lists(trello_auth, board_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("list_lists", {"board_id": board_id}, context)
    data = _assert_ok(result)
    assert "lists" in data and "count" in data
    assert data["count"] >= 1


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_card(trello_auth, card_id):
    assert isinstance(card_id, str) and card_id


@pytest.mark.asyncio
async def test_get_card(trello_auth, card_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("get_card", {"card_id": card_id}, context)
    data = _assert_ok(result)
    assert data["card"]["id"] == card_id


@pytest.mark.asyncio
async def test_update_card(trello_auth, card_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "update_card",
            {"card_id": card_id, "desc": "Updated by integration test"},
            context,
        )
    data = _assert_ok(result)
    assert data["card"]["id"] == card_id


@pytest.mark.asyncio
async def test_list_cards_by_list(trello_auth, list_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("list_cards", {"list_id": list_id}, context)
    data = _assert_ok(result)
    assert "cards" in data and "count" in data
    assert data["count"] >= 1


@pytest.mark.asyncio
async def test_list_cards_by_board(trello_auth, board_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("list_cards", {"board_id": board_id}, context)
    data = _assert_ok(result)
    assert "cards" in data and "count" in data
    assert data["count"] >= 1


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


@pytest.mark.asyncio
async def test_delete_card(trello_auth, list_id):
    # Create a throwaway card so we don't delete the session-scoped one
    async with ExecutionContext(auth=trello_auth) as context:
        create_result = await trello_integration.execute_action(
            "create_card",
            {"list_id": list_id, "name": "Throwaway Card"},
            context,
        )
    throwaway_id = _assert_ok(create_result)["card"]["id"]

    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action("delete_card", {"card_id": throwaway_id}, context)
    data = _assert_ok(result)
    assert data["deleted"] is True
    assert data["card_id"] == throwaway_id


# ---------------------------------------------------------------------------
# Checklist / checklist item / comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_checklist(trello_auth, checklist_id):
    assert isinstance(checklist_id, str) and checklist_id


@pytest.mark.asyncio
async def test_add_checklist_item(trello_auth, checklist_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "add_checklist_item",
            {"checklist_id": checklist_id, "name": "Step 1", "checked": False},
            context,
        )
    data = _assert_ok(result)
    assert "checkItem" in data
    assert data["checkItem"]["name"] == "Step 1"


@pytest.mark.asyncio
async def test_add_comment(trello_auth, card_id):
    async with ExecutionContext(auth=trello_auth) as context:
        result = await trello_integration.execute_action(
            "add_comment",
            {"card_id": card_id, "text": "Automated integration test comment"},
            context,
        )
    data = _assert_ok(result)
    assert "comment" in data
    assert data["comment"].get("id")

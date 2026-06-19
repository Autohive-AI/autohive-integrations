import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import ResultType

from kajabi.kajabi import kajabi

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONTACT = {
    "data": {
        "id": "c1",
        "type": "contacts",
        "attributes": {"name": "Alice", "email": "alice@example.com"},
    }
}

CONTACT_LIST = {
    "data": [
        {
            "id": "c1",
            "type": "contacts",
            "attributes": {"name": "Alice", "email": "alice@example.com"},
        }
    ],
    "meta": {"page": {"total-count": 1}},
}

TAG = {"data": {"id": "t1", "type": "contact_tags", "attributes": {"name": "VIP"}}}

TAG_LIST = {
    "data": [{"id": "t1", "type": "contact_tags", "attributes": {"name": "VIP"}}],
    "meta": {"page": {"total-count": 1}},
}

NOTE = {
    "data": {
        "id": "n1",
        "type": "contact_notes",
        "attributes": {"body": "Follow up"},
    }
}

NOTE_LIST = {
    "data": [
        {
            "id": "n1",
            "type": "contact_notes",
            "attributes": {"body": "Follow up"},
        }
    ],
    "meta": {"page": {"total-count": 1}},
}

COURSE = {
    "data": {
        "id": "cr1",
        "type": "courses",
        "attributes": {"title": "Python Basics"},
    }
}

COURSE_LIST = {
    "data": [{"id": "cr1", "type": "courses", "attributes": {"title": "Python Basics"}}],
    "meta": {"page": {"total-count": 1}},
}

POST = {
    "data": {
        "id": "p1",
        "type": "blog_posts",
        "attributes": {"title": "Hello World"},
    }
}

POST_LIST = {
    "data": [{"id": "p1", "type": "blog_posts", "attributes": {"title": "Hello World"}}],
    "meta": {"page": {"total-count": 1}},
}

OFFER_LIST = {
    "data": [{"id": "o1", "type": "offers"}],
}

EMPTY_204 = {}


def fetch_returning(payload):
    return AsyncMock(return_value=MagicMock(data=payload))


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_contacts(mock_context):
    mock_context.fetch = fetch_returning(CONTACT_LIST)
    result = await kajabi.execute_action("list_contacts", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["contacts"][0]["name"] == "Alice"
    assert result.result.data["total"] == 1


@pytest.mark.asyncio
async def test_get_contact(mock_context):
    mock_context.fetch = fetch_returning(CONTACT)
    result = await kajabi.execute_action("get_contact", {"contact_id": "c1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "c1"
    assert result.result.data["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_create_contact(mock_context):
    mock_context.fetch = fetch_returning(CONTACT)
    result = await kajabi.execute_action(
        "create_contact",
        {"name": "Alice", "email": "alice@example.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "c1"


@pytest.mark.asyncio
async def test_update_contact(mock_context):
    mock_context.fetch = fetch_returning(CONTACT)
    result = await kajabi.execute_action(
        "update_contact",
        {"contact_id": "c1", "name": "Alice Updated"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "c1"


@pytest.mark.asyncio
async def test_delete_contact(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action("delete_contact", {"contact_id": "c1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_contacts_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("api error"))
    result = await kajabi.execute_action("list_contacts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "api error" in result.result.message


# ---------------------------------------------------------------------------
# Contact Tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_contact_tags(mock_context):
    mock_context.fetch = fetch_returning(TAG_LIST)
    result = await kajabi.execute_action("list_contact_tags", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["tags"][0]["name"] == "VIP"
    assert result.result.data["total"] == 1


@pytest.mark.asyncio
async def test_get_contact_tag(mock_context):
    mock_context.fetch = fetch_returning(TAG)
    result = await kajabi.execute_action("get_contact_tag", {"tag_id": "t1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "t1"
    assert result.result.data["name"] == "VIP"


@pytest.mark.asyncio
async def test_add_tag_to_contact(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action(
        "add_tag_to_contact",
        {"contact_id": "c1", "tag_ids": ["t1"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["added"] is True


@pytest.mark.asyncio
async def test_remove_tag_from_contact(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action(
        "remove_tag_from_contact",
        {"contact_id": "c1", "tag_ids": ["t1"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["removed"] is True


# ---------------------------------------------------------------------------
# Contact Notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_contact_notes(mock_context):
    mock_context.fetch = fetch_returning(NOTE_LIST)
    result = await kajabi.execute_action("list_contact_notes", {"contact_id": "c1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["notes"][0]["body"] == "Follow up"


@pytest.mark.asyncio
async def test_get_contact_note(mock_context):
    mock_context.fetch = fetch_returning(NOTE)
    result = await kajabi.execute_action("get_contact_note", {"note_id": "n1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["body"] == "Follow up"


@pytest.mark.asyncio
async def test_create_contact_note(mock_context):
    mock_context.fetch = fetch_returning(NOTE)
    result = await kajabi.execute_action(
        "create_contact_note",
        {"contact_id": "c1", "body": "Follow up"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "n1"


@pytest.mark.asyncio
async def test_update_contact_note(mock_context):
    mock_context.fetch = fetch_returning(NOTE)
    result = await kajabi.execute_action(
        "update_contact_note",
        {"note_id": "n1", "body": "Updated note"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "n1"


@pytest.mark.asyncio
async def test_delete_contact_note(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action("delete_contact_note", {"note_id": "n1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


# ---------------------------------------------------------------------------
# Contact Offers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_contact_offers(mock_context):
    mock_context.fetch = fetch_returning(OFFER_LIST)
    result = await kajabi.execute_action("list_contact_offers", {"contact_id": "c1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["offers"][0]["id"] == "o1"


@pytest.mark.asyncio
async def test_grant_offer_to_contact(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action(
        "grant_offer_to_contact",
        {"contact_id": "c1", "offer_id": "o1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["granted"] is True


@pytest.mark.asyncio
async def test_revoke_offer_from_contact(mock_context):
    mock_context.fetch = fetch_returning(EMPTY_204)
    result = await kajabi.execute_action(
        "revoke_offer_from_contact",
        {"contact_id": "c1", "offer_id": "o1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["revoked"] is True


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_courses(mock_context):
    mock_context.fetch = fetch_returning(COURSE_LIST)
    result = await kajabi.execute_action("list_courses", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["courses"][0]["title"] == "Python Basics"


@pytest.mark.asyncio
async def test_get_course(mock_context):
    mock_context.fetch = fetch_returning(COURSE)
    result = await kajabi.execute_action("get_course", {"course_id": "cr1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["title"] == "Python Basics"


# ---------------------------------------------------------------------------
# Blog Posts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_blog_posts(mock_context):
    mock_context.fetch = fetch_returning(POST_LIST)
    result = await kajabi.execute_action("list_blog_posts", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["posts"][0]["title"] == "Hello World"


@pytest.mark.asyncio
async def test_get_blog_post(mock_context):
    mock_context.fetch = fetch_returning(POST)
    result = await kajabi.execute_action("get_blog_post", {"post_id": "p1"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["title"] == "Hello World"


@pytest.mark.asyncio
async def test_get_blog_post_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await kajabi.execute_action("get_blog_post", {"post_id": "bad"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "not found" in result.result.message

"""End-to-end integration tests for the Google Forms integration.

The integration uses Google's ``googleapiclient`` Python SDK directly rather
than ``context.fetch``, so this file follows **Variant 4 — External Python SDK**
from the writing-integration-tests skill: build an ``ExecutionContext`` with
real OAuth credentials and let the upstream SDK make HTTP calls itself.

Required environment variables (loaded from project ``.env``):
    GOOGLE_FORMS_ACCESS_TOKEN  — required; OAuth token with forms.body and
                                 forms.responses.readonly scopes
    GOOGLE_FORMS_TEST_FORM_ID  — optional; pre-existing form ID for the
                                 read-only TestExistingForm class

Run with:
    pytest google-forms/tests/test_google_forms_integration.py -m "integration and not destructive"
    pytest google-forms/tests/test_google_forms_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter ``-m unit`` excludes these,
and the file naming (``test_*_integration.py``) is not matched by ``python_files``.
"""

from __future__ import annotations

import os
import uuid

import pytest

from autohive_integrations_sdk.integration import ResultType

from google_forms import google_forms

pytestmark = pytest.mark.integration


TEST_FORM_ID = os.environ.get("GOOGLE_FORMS_TEST_FORM_ID", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def live_context(env_credentials, make_context):
    """Variant 4 — External SDK: hand the OAuth token to the integration via
    ``context.auth`` and let ``googleapiclient`` do its own networking."""
    access_token = env_credentials("GOOGLE_FORMS_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("GOOGLE_FORMS_ACCESS_TOKEN not set — skipping integration tests")
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )


def require_form_id():
    if not TEST_FORM_ID:
        pytest.skip("GOOGLE_FORMS_TEST_FORM_ID not set")


def _ok(envelope):
    """Assert the envelope wraps a successful ActionResult and return its data."""
    assert envelope.type != ResultType.ACTION_ERROR, getattr(envelope.result, "message", "") or "unexpected ActionError"
    return envelope.result.data


# ---------------------------------------------------------------------------
# Read-Only Tests
# ---------------------------------------------------------------------------


class TestExistingForm:
    """Read-only operations against a pre-existing form."""

    async def test_get_form(self, live_context):
        require_form_id()
        envelope = await google_forms.execute_action(
            "get_form",
            {"form_id": TEST_FORM_ID},
            live_context,
        )
        data = _ok(envelope)
        assert "form" in data
        assert data["form"]["formId"] == TEST_FORM_ID

    async def test_list_responses(self, live_context):
        require_form_id()
        envelope = await google_forms.execute_action(
            "list_responses",
            {"form_id": TEST_FORM_ID, "page_size": 5},
            live_context,
        )
        data = _ok(envelope)
        assert "responses" in data
        assert isinstance(data["responses"], list)
        assert len(data["responses"]) <= 5


class TestNonexistentForm:
    """Confirm the integration translates Drive 404s into clean ActionErrors."""

    async def test_get_form_with_bad_id_returns_action_error(self, live_context):
        envelope = await google_forms.execute_action(
            "get_form",
            {"form_id": "definitely-not-a-real-form-id"},
            live_context,
        )
        assert envelope.type == ResultType.ACTION_ERROR


# ---------------------------------------------------------------------------
# Destructive Tests (Write Operations)
# Only run with: pytest -m "integration and destructive"
#
# Recommended: run these against a throwaway Google account. Each lifecycle
# test creates a brand-new form, exercises a flow, then leaves the form in
# place (the Forms API has no delete endpoint — forms must be removed via
# the Drive API or the user's UI). Empty forms are harmless.
# ---------------------------------------------------------------------------


@pytest.mark.destructive
class TestCreateFormLifecycle:
    """Create → read back → update info."""

    async def test_create_then_get_then_rename(self, live_context):
        suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        create_env = await google_forms.execute_action(
            "create_form",
            {"title": f"autohive-test {suffix}"},
            live_context,
        )
        data = _ok(create_env)
        form_id = data["form_id"]
        assert form_id
        # Default behavior: the form should arrive already published so the
        # returned responder_uri actually accepts submissions.
        assert data["auto_published"] is True

        get_env = await google_forms.execute_action(
            "get_form",
            {"form_id": form_id},
            live_context,
        )
        assert _ok(get_env)["form"]["formId"] == form_id

        update_env = await google_forms.execute_action(
            "update_form_info",
            {"form_id": form_id, "title": f"autohive-test {suffix} (renamed)"},
            live_context,
        )
        renamed = _ok(update_env)
        # batchUpdate returns the full form when includeFormInResponse=true
        assert renamed["form"]["info"]["title"].endswith("(renamed)")

    async def test_auto_publish_false_creates_draft(self, live_context):
        """With auto_publish=false, the integration passes unpublished=true to
        forms.create — verify by re-fetching the form and asserting its
        publishState shows isPublished as false/absent (protobuf JSON omits
        false defaults)."""
        suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        create_env = await google_forms.execute_action(
            "create_form",
            {"title": f"autohive-draft {suffix}", "auto_publish": False},
            live_context,
        )
        data = _ok(create_env)
        form_id = data["form_id"]
        assert form_id
        assert data["auto_published"] is False

        # Authoritative check: re-fetch and confirm the form is actually
        # unpublished — the create response can be lossy in shape, the get
        # response is canonical.
        get_env = await google_forms.execute_action(
            "get_form",
            {"form_id": form_id},
            live_context,
        )
        form = _ok(get_env)["form"]
        publish_state = form.get("publishSettings", {}).get("publishState", {})
        # isPublished is False ⇒ protobuf omits it, OR explicitly false.
        assert publish_state.get("isPublished", False) is False


@pytest.mark.destructive
class TestAddQuestionsLifecycle:
    """Create a form, add one of each question type, verify items, then delete one."""

    async def test_add_and_delete(self, live_context):
        suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        create_env = await google_forms.execute_action(
            "create_form",
            {"title": f"autohive-questions {suffix}"},
            live_context,
        )
        form_id = _ok(create_env)["form_id"]

        # Text question
        text_env = await google_forms.execute_action(
            "add_text_question",
            {"form_id": form_id, "title": "Your name?", "required": True},
            live_context,
        )
        _ok(text_env)

        # Multiple-choice
        mc_env = await google_forms.execute_action(
            "add_multiple_choice_question",
            {
                "form_id": form_id,
                "title": "Pick one",
                "type": "RADIO",
                "options": ["A", "B", "C"],
            },
            live_context,
        )
        _ok(mc_env)

        # Scale
        scale_env = await google_forms.execute_action(
            "add_scale_question",
            {
                "form_id": form_id,
                "title": "Rate it",
                "low": 1,
                "high": 5,
                "low_label": "Bad",
                "high_label": "Great",
            },
            live_context,
        )
        scale_data = _ok(scale_env)
        items = scale_data["form"].get("items", [])
        assert len(items) == 3, f"expected 3 items, got {len(items)}"

        # Delete the first item
        delete_env = await google_forms.execute_action(
            "delete_item",
            {"form_id": form_id, "index": 0},
            live_context,
        )
        after_delete = _ok(delete_env)["form"].get("items", [])
        assert len(after_delete) == 2


@pytest.mark.destructive
class TestBatchUpdateEscapeHatch:
    """Verify the raw batchUpdate path works for a custom Request the
    convenience wrappers don't cover (here: updateSettings to make the form
    a quiz)."""

    async def test_raw_request(self, live_context):
        suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        create_env = await google_forms.execute_action(
            "create_form",
            {"title": f"autohive-batch {suffix}"},
            live_context,
        )
        form_id = _ok(create_env)["form_id"]

        # Promote to quiz mode — only exposed via raw batchUpdate.
        env = await google_forms.execute_action(
            "batch_update_form",
            {
                "form_id": form_id,
                "requests": [
                    {
                        "updateSettings": {
                            "settings": {"quizSettings": {"isQuiz": True}},
                            "updateMask": "quizSettings.isQuiz",
                        }
                    }
                ],
            },
            live_context,
        )
        data = _ok(env)
        assert data["form"]["settings"]["quizSettings"]["isQuiz"] is True


@pytest.mark.destructive
class TestPublishLifecycle:
    """Toggle publish state on a freshly-created form."""

    async def test_publish_then_unpublish(self, live_context):
        suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        create_env = await google_forms.execute_action(
            "create_form",
            {"title": f"autohive-publish {suffix}"},
            live_context,
        )
        form_id = _ok(create_env)["form_id"]

        publish_env = await google_forms.execute_action(
            "set_publish_settings",
            {"form_id": form_id, "is_published": True},
            live_context,
        )
        published = _ok(publish_env)["publish_settings"]
        # Forms API uses protobuf JSON serialization — false-default booleans
        # are omitted from the response. Read defensively with .get(..., False).
        assert published.get("publishState", {}).get("isPublished") is True

        unpublish_env = await google_forms.execute_action(
            "set_publish_settings",
            {"form_id": form_id, "is_published": False},
            live_context,
        )
        unpublished = _ok(unpublish_env)["publish_settings"]
        assert unpublished.get("publishState", {}).get("isPublished", False) is False

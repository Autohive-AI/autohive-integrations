# Freshsales CRM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `freshsales/` integration (30 actions: CRUD on Contacts/Accounts/Deals/Tasks/Appointments, create/update/delete Notes, `list_views`, `search`) per the approved spec at `docs/superpowers/specs/2026-07-06-freshsales-integration-design.md`.

**Architecture:** Single-file integration (`freshsales/freshsales.py`) mirroring `freshdesk/freshdesk.py`: module-level helpers for auth headers, base URL, request-body building, and default-view resolution; one `ActionHandler` class per action. Custom auth (`api_key` + `bundle_alias`); all requests hit `https://{alias}.myfreshworks.com/crm/sales/api` with `Authorization: Token token={api_key}` and entity-wrapped JSON bodies (`{"contact": {...}}`).

**Tech Stack:** Python 3.13+, autohive-integrations-sdk~=2.0.0 (SDK 2.x — `context.fetch` returns `FetchResponse`, read `.data`), pytest (asyncio auto mode), ruff/bandit via the sibling tooling repo.

## Global Constraints

- **Public repo:** committed files must contain ONLY fake credentials (`"test_api_key"`, `"testcompany"`) with `# nosec B105` where bandit flags them. Real creds live only in the gitignored `.env`.
- SDK pin: `autohive-integrations-sdk~=2.0.0` in `freshsales/requirements.txt`. Always read fetch results via `response.data`.
- All work happens under `freshsales/` + one root `README.md` edit + these plan/spec docs. Do NOT touch `shopify-customer/config.json` (unrelated user change) or any other integration.
- `config.json` action keys must exactly match `@freshsales.action(...)` decorators at every commit.
- Conventional commits: `feat(freshsales): ...` / `test(freshsales): ...` / `docs(freshsales): ...`. Branch: stay on `rp/freshsales-integration`. No force-push.
- Every commit message ends with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Lint/format with the tooling config: `ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales && ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales` (line-length 120, target py313). Run before every commit.
- Unit tests run from repo root: `pytest freshsales/ -v` (only `test_*_unit.py` auto-discovered; `-m unit` is in addopts).
- All shell commands below run from the repo root `/Users/risheet1/Public Integrations/autohive-integrations` with `.venv` activated (`source .venv/bin/activate`).
- API reference (official): https://developers.freshworks.com/crm/api/

---

### Task 1: Preflight, GitHub issue, scaffolding, helpers, `list_views`

**Files:**
- Create: `freshsales/__init__.py` (empty)
- Create: `freshsales/requirements.txt`
- Create: `freshsales/config.json`
- Create: `freshsales/freshsales.py`
- Create: `freshsales/tests/__init__.py` (empty)
- Create: `freshsales/tests/conftest.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Produces (later tasks import these from `freshsales.py`):
  - `freshsales` — the `Integration` instance; handlers register via `@freshsales.action("name")`
  - `get_auth_headers(context: ExecutionContext) -> Dict[str, str]`
  - `get_base_url(context: ExecutionContext) -> str` — returns `https://{alias}.myfreshworks.com/crm/sales/api`, no trailing slash
  - `build_body(inputs: Dict[str, Any], fields: tuple) -> Dict[str, Any]`
  - `resolve_view_id(context: ExecutionContext, resource: str) -> int` (async)
  - `ENTITY_PATHS = {"contacts": "contacts", "accounts": "sales_accounts", "deals": "deals"}`
- Test file conventions all later tasks append to: module loaded via importlib as `freshsales_mod`; fixtures `mock_context` from conftest; `pytestmark = pytest.mark.unit`.

- [ ] **Step 1: Preflight**

```bash
source .venv/bin/activate
python --version                                    # expect 3.13+
python -c "import autohive_integrations_sdk; print(autohive_integrations_sdk.__name__)"
ls ../autohive-integrations-tooling/scripts/validate_integration.py
```
Expected: all succeed. If the SDK import fails: `uv pip install -r requirements-test.txt && uv pip install "autohive-integrations-sdk~=2.0.0"`.

- [ ] **Step 2: Create the GitHub issue (user pre-approved)**

```bash
gh issue create --title "feat: add Freshsales CRM integration" \
  --body "Add a new freshsales/ integration covering Contacts, Sales Accounts, Deals, Tasks, Appointments, Notes (30 actions), with custom API-key auth against https://{bundle}.myfreshworks.com/crm/sales/api. Spec: docs/superpowers/specs/2026-07-06-freshsales-integration-design.md"
```
Expected: prints the new issue URL. **Record the issue number** — the PR description will reference it (`Closes #N`).

- [ ] **Step 3: Scaffold files**

```bash
mkdir -p freshsales/tests
touch freshsales/__init__.py freshsales/tests/__init__.py
printf 'autohive-integrations-sdk~=2.0.0\n' > freshsales/requirements.txt
```

Create `freshsales/tests/conftest.py`:

```python
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make freshsales.py importable as a top-level module.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_context():
    """Mock execution context with the wrapped Custom auth envelope Freshsales expects."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    credentials = {"api_key": "test_api_key", "bundle_alias": "testcompany"}  # nosec B105
    ctx.auth = {"auth_type": "Custom", "credentials": credentials}
    return ctx
```

Create `freshsales/config.json` (auth + the first action; later tasks add keys to `"actions"`):

```json
{
    "name": "Freshsales",
    "display_name": "Freshsales",
    "version": "1.0.0",
    "description": "Freshsales CRM integration for managing contacts, accounts, deals, tasks, appointments, and notes",
    "entry_point": "freshsales.py",
    "auth": {
        "type": "custom",
        "title": "Freshsales API Credentials",
        "fields": {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "format": "password",
                    "label": "API Key",
                    "help_text": "Your Freshsales API key. Find it in Personal Settings > API Settings."
                },
                "bundle_alias": {
                    "type": "string",
                    "label": "Bundle Alias",
                    "help_text": "Your Freshworks bundle alias — the 'yourcompany' in yourcompany.myfreshworks.com"
                }
            },
            "required": ["api_key", "bundle_alias"]
        }
    },
    "actions": {
        "list_views": {
            "display_name": "List Views",
            "description": "List the available list views (filters) for contacts, accounts, or deals. Freshsales lists records through views; pass a view id from here to list_contacts/list_accounts/list_deals to use a specific view.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["contacts", "accounts", "deals"],
                        "description": "Which resource to fetch views for"
                    }
                },
                "required": ["entity"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "views": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Available views, each with id and name"
                    },
                    "total": {"type": "integer", "description": "Number of views"}
                },
                "required": ["views"]
            }
        }
    }
}
```

Create `freshsales/freshsales.py`:

```python
from typing import Any, Dict

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

# Create the integration using the config.json
freshsales = Integration.load()

# Maps user-facing entity names to Freshsales API path segments.
ENTITY_PATHS = {"contacts": "contacts", "accounts": "sales_accounts", "deals": "deals"}


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Freshsales API requests.
    Freshsales uses token auth: 'Authorization: Token token=API_KEY'.
    """
    api_key = context.auth["credentials"].get("api_key", "")
    return {"Authorization": f"Token token={api_key}", "Content-Type": "application/json"}


def get_base_url(context: ExecutionContext) -> str:
    """
    Construct the base URL for Freshsales API requests from the bundle alias.

    Tolerates a pasted full domain ('https://acme.myfreshworks.com/') by
    stripping the protocol, path, and domain suffix down to the bare alias.
    """
    alias = context.auth["credentials"].get("bundle_alias", "").strip()
    alias = alias.removeprefix("https://").removeprefix("http://")
    alias = alias.split("/")[0].split(".")[0]
    return f"https://{alias}.myfreshworks.com/crm/sales/api"


def build_body(inputs: Dict[str, Any], fields: tuple) -> Dict[str, Any]:
    """Collect the provided (non-None) input fields into a request body dict."""
    return {field: inputs[field] for field in fields if inputs.get(field) is not None}


async def resolve_view_id(context: ExecutionContext, resource: str) -> int:
    """
    Return the id of the default 'All ...' view for a resource.

    Freshsales has no plain list endpoint — records are listed through views.
    Falls back to the first available view when no 'All ...' view exists.
    """
    headers = get_auth_headers(context)
    base_url = get_base_url(context)
    response = await context.fetch(f"{base_url}/{resource}/filters", method="GET", headers=headers)
    views = response.data.get("filters", [])
    if not views:
        raise ValueError(f"No list views available for {resource}")
    for view in views:
        if view.get("name", "").lower().startswith("all "):
            return view["id"]
    return views[0]["id"]


# ---- Action Handlers ----


@freshsales.action("list_views")
class ListViewsAction(ActionHandler):
    """List the available list views (filters) for contacts, accounts, or deals."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            resource = ENTITY_PATHS[inputs["entity"]]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/{resource}/filters", method="GET", headers=headers)
            views = response.data.get("filters", [])
            return ActionResult(data={"views": views, "total": len(views)})
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 4: Write the failing tests**

Create `freshsales/tests/test_freshsales_unit.py`:

```python
import importlib.util
import json
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("freshsales_mod", os.path.join(_parent, "freshsales.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

freshsales = _mod.freshsales  # the Integration instance
get_auth_headers = _mod.get_auth_headers
get_base_url = _mod.get_base_url
build_body = _mod.build_body

CONFIG_PATH = os.path.join(_parent, "config.json")

pytestmark = pytest.mark.unit


# ---- Config/Handler Sync ----


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        defined_actions = set(config.get("actions", {}).keys())
        registered_actions = set(freshsales._action_handlers.keys())

        missing_handlers = defined_actions - registered_actions
        extra_handlers = registered_actions - defined_actions

        assert not missing_handlers, f"Missing handlers for actions: {missing_handlers}"
        assert not extra_handlers, f"Extra handlers without config: {extra_handlers}"


# ---- Helper Function Tests ----


class TestGetAuthHeaders:
    def test_token_header_format(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Authorization"] == "Token token=test_api_key"  # nosec B105

    def test_content_type_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Content-Type"] == "application/json"


class TestGetBaseUrl:
    def test_bare_alias(self, mock_context):
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"

    def test_full_domain_pasted(self, mock_context):
        mock_context.auth["credentials"]["bundle_alias"] = "https://testcompany.myfreshworks.com/"
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"

    def test_domain_without_protocol(self, mock_context):
        mock_context.auth["credentials"]["bundle_alias"] = "testcompany.myfreshworks.com"
        assert get_base_url(mock_context) == "https://testcompany.myfreshworks.com/crm/sales/api"


class TestBuildBody:
    def test_includes_only_provided_fields(self):
        body = build_body({"a": 1, "b": None, "d": "x"}, ("a", "b", "c"))
        assert body == {"a": 1}

    def test_keeps_falsy_but_not_none_values(self):
        body = build_body({"a": 0, "b": ""}, ("a", "b"))
        assert body == {"a": 0, "b": ""}


# ---- List Views ----


class TestListViews:
    @pytest.mark.asyncio
    async def test_happy_path_returns_views(self, mock_context):
        views = [{"id": 1, "name": "My Contacts"}, {"id": 4, "name": "All Contacts"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": views})

        result = await freshsales.execute_action("list_views", {"entity": "contacts"}, mock_context)

        assert result.result.data["views"] == views
        assert result.result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_accounts_entity_maps_to_sales_accounts_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": []})

        await freshsales.execute_action("list_views", {"entity": "accounts"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "testcompany.myfreshworks.com/crm/sales/api/sales_accounts/filters" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await freshsales.execute_action("list_views", {"entity": "deals"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message
```

- [ ] **Step 5: Run tests — expected mixed result**

Run: `pytest freshsales/ -v`
Expected: PASS for everything once Step 3's files exist (TDD note: if you write this test file before `freshsales.py`, the import fails — that is the "red" state; then create Step 3's `freshsales.py` and re-run for green). If `ResultType` import fails, check the SDK is installed in the venv.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): scaffold integration with auth helpers and list_views action

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Contacts (5 actions)

**Files:**
- Modify: `freshsales/config.json` (add 5 keys to `"actions"`)
- Modify: `freshsales/freshsales.py` (append `CONTACT_FIELDS` + 5 handlers)
- Test: `freshsales/tests/test_freshsales_unit.py` (append test classes)

**Interfaces:**
- Consumes: `get_auth_headers`, `get_base_url`, `build_body`, `resolve_view_id` from Task 1.
- Produces: actions `create_contact`, `get_contact`, `update_contact`, `delete_contact`, `list_contacts`; module constant `CONTACT_FIELDS`.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
# ---- Sample Data ----

SAMPLE_CONTACT = {
    "id": 3001,
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "mobile_number": "555-0100",
}


# ---- Contact Tests ----


class TestCreateContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contact(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        result = await freshsales.execute_action(
            "create_contact", {"first_name": "Jane", "email": "jane@example.com"}, mock_context
        )

        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_request_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        await freshsales.execute_action(
            "create_contact", {"first_name": "Jane", "email": "jane@example.com", "owner_id": 7}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://testcompany.myfreshworks.com/crm/sales/api/contacts"
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"contact": {"first_name": "Jane", "email": "jane@example.com", "owner_id": 7}}
        assert call_args.kwargs["headers"]["Authorization"] == "Token token=test_api_key"  # nosec B105

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_contact", {"first_name": "Jane"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "create failed" in result.result.message


class TestGetContact:
    @pytest.mark.asyncio
    async def test_happy_path_and_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        result = await freshsales.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_include_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": SAMPLE_CONTACT})

        await freshsales.execute_action("get_contact", {"contact_id": 3001, "include": "owner,deals"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"include": "owner,deals"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateContact:
    @pytest.mark.asyncio
    async def test_happy_path_put_with_wrapped_body(self, mock_context):
        updated = {**SAMPLE_CONTACT, "job_title": "CTO"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contact": updated})

        result = await freshsales.execute_action(
            "update_contact", {"contact_id": 3001, "job_title": "CTO"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"contact": {"job_title": "CTO"}}
        assert result.result.data["contact"]["job_title"] == "CTO"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteContact:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/contacts/3001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["contact_id"] == 3001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListContacts:
    @pytest.mark.asyncio
    async def test_explicit_view_id_lists_directly(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"contacts": [SAMPLE_CONTACT], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_contacts", {"view_id": 42}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/contacts/view/42" in call_args.args[0]
        assert call_args.kwargs["params"]["page"] == 1
        assert result.result.data["contacts"] == [SAMPLE_CONTACT]
        assert result.result.data["meta"] == {"total": 1}
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_auto_resolves_all_view_when_view_id_omitted(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"filters": [{"id": 9, "name": "My Contacts"}, {"id": 4, "name": "All Contacts"}]},
            ),
            FetchResponse(status=200, headers={}, data={"contacts": [SAMPLE_CONTACT], "meta": {}}),
        ]

        result = await freshsales.execute_action("list_contacts", {}, mock_context)

        first_url = mock_context.fetch.call_args_list[0].args[0]
        second_url = mock_context.fetch.call_args_list[1].args[0]
        assert first_url.endswith("/contacts/filters")
        assert "/contacts/view/4" in second_url
        assert result.result.data["contacts"] == [SAMPLE_CONTACT]

    @pytest.mark.asyncio
    async def test_pagination_and_sort_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"contacts": [], "meta": {}})

        await freshsales.execute_action(
            "list_contacts", {"view_id": 42, "page": 3, "sort": "updated_at", "sort_type": "desc"}, mock_context
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params == {"page": 3, "sort": "updated_at", "sort_type": "desc"}

    @pytest.mark.asyncio
    async def test_no_views_available_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"filters": []})

        result = await freshsales.execute_action("list_contacts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "No list views available" in result.result.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Contact"`
Expected: FAIL — `Action create_contact not found` (or similar) for each new class; `TestConfigValidation` still passes (config not yet touched either).

- [ ] **Step 3: Add config schemas** — add these 5 keys inside `"actions"` in `freshsales/config.json`:

```json
"create_contact": {
    "display_name": "Create Contact",
    "description": "Create a new contact. Freshsales requires first_name or last_name, plus email or mobile_number.",
    "input_schema": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "email": {"type": "string", "description": "Primary email address"},
            "mobile_number": {"type": "string", "description": "Mobile phone number"},
            "work_number": {"type": "string", "description": "Work phone number"},
            "job_title": {"type": "string", "description": "Job title"},
            "address": {"type": "string", "description": "Street address"},
            "city": {"type": "string", "description": "City"},
            "state": {"type": "string", "description": "State"},
            "zipcode": {"type": "string", "description": "Zip code"},
            "country": {"type": "string", "description": "Country"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the contact"},
            "sales_account_id": {"type": "integer", "description": "ID of the account to associate with"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "lead_source_id": {"type": "integer", "description": "ID of the lead source"},
            "medium": {"type": "string", "description": "Marketing medium the contact came from"},
            "keyword": {"type": "string", "description": "Keywords for the contact"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {"contact": {"type": "object", "description": "The created contact record"}},
        "required": ["contact"]
    }
},
"get_contact": {
    "display_name": "Get Contact",
    "description": "Retrieve a contact by ID, optionally embedding related records.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "integer", "description": "Contact ID"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner,sales_accounts,deals,tasks,appointments,notes)"}
        },
        "required": ["contact_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"contact": {"type": "object", "description": "The contact record"}},
        "required": ["contact"]
    }
},
"update_contact": {
    "display_name": "Update Contact",
    "description": "Update fields on an existing contact. Only provided fields are changed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "integer", "description": "Contact ID"},
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "email": {"type": "string", "description": "Primary email address"},
            "mobile_number": {"type": "string", "description": "Mobile phone number"},
            "work_number": {"type": "string", "description": "Work phone number"},
            "job_title": {"type": "string", "description": "Job title"},
            "address": {"type": "string", "description": "Street address"},
            "city": {"type": "string", "description": "City"},
            "state": {"type": "string", "description": "State"},
            "zipcode": {"type": "string", "description": "Zip code"},
            "country": {"type": "string", "description": "Country"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the contact"},
            "sales_account_id": {"type": "integer", "description": "ID of the account to associate with"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "lead_source_id": {"type": "integer", "description": "ID of the lead source"},
            "medium": {"type": "string", "description": "Marketing medium the contact came from"},
            "keyword": {"type": "string", "description": "Keywords for the contact"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": ["contact_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"contact": {"type": "object", "description": "The updated contact record"}},
        "required": ["contact"]
    }
},
"delete_contact": {
    "display_name": "Delete Contact",
    "description": "Delete a contact by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"contact_id": {"type": "integer", "description": "Contact ID"}},
        "required": ["contact_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "contact_id": {"type": "integer", "description": "ID of the deleted contact"}
        },
        "required": ["success"]
    }
},
"list_contacts": {
    "display_name": "List Contacts",
    "description": "List contacts from a view. Omit view_id to use the 'All Contacts' view automatically (use list_views to discover other views). Returns 25 records per page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "view_id": {"type": "integer", "description": "View (filter) ID to list from; omit for the default 'All Contacts' view"},
            "page": {"type": "integer", "minimum": 1, "description": "Page number (default 1)"},
            "sort": {"type": "string", "description": "Field to sort by (e.g. created_at, updated_at)"},
            "sort_type": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner,sales_accounts)"}
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "contacts": {"type": "array", "items": {"type": "object"}, "description": "Contacts in the view page"},
            "meta": {"type": "object", "description": "Pagination metadata (total, total_pages)"}
        },
        "required": ["contacts"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
CONTACT_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "mobile_number",
    "work_number",
    "job_title",
    "address",
    "city",
    "state",
    "zipcode",
    "country",
    "owner_id",
    "sales_account_id",
    "territory_id",
    "lead_source_id",
    "medium",
    "keyword",
    "custom_field",
)


@freshsales.action("create_contact")
class CreateContactAction(ActionHandler):
    """Create a new contact. Requires first_name or last_name plus email or mobile_number."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, CONTACT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts", method="POST", headers=headers, json={"contact": body}
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_contact")
class GetContactAction(ActionHandler):
    """Retrieve a contact by ID, optionally embedding related records via `include`."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_contact")
class UpdateContactAction(ActionHandler):
    """Update fields on an existing contact. Only provided fields are changed."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, CONTACT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="PUT", headers=headers, json={"contact": body}
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_contact")
class DeleteContactAction(ActionHandler):
    """Delete a contact by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "contact_id": inputs["contact_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_contacts")
class ListContactsAction(ActionHandler):
    """List contacts from a view, auto-resolving the 'All Contacts' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id") or await resolve_view_id(context, "contacts")
            params = {"page": inputs.get("page", 1)}
            for param in ("sort", "sort_type", "include"):
                if inputs.get(param):
                    params[param] = inputs[param]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(
                data={"contacts": response.data.get("contacts", []), "meta": response.data.get("meta", {})}
            )
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS, including `TestConfigValidation` (config and handlers added together).

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add contact CRUD and list actions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Accounts (5 actions)

**Files:**
- Modify: `freshsales/config.json`
- Modify: `freshsales/freshsales.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: actions `create_account`, `get_account`, `update_account`, `delete_account`, `list_accounts`; constant `ACCOUNT_FIELDS`. API path is `sales_accounts`; request wrapper key and response key are `sales_account`; the action's OUTPUT key is `account`.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
SAMPLE_ACCOUNT = {"id": 2001, "name": "Widgetz.io", "website": "https://widgetz.io"}


class TestCreateAccount:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body_and_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": SAMPLE_ACCOUNT})

        result = await freshsales.execute_action("create_account", {"name": "Widgetz.io"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"sales_account": {"name": "Widgetz.io"}}
        assert result.result.data["account"] == SAMPLE_ACCOUNT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_account", {"name": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_happy_path_and_include(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": SAMPLE_ACCOUNT})

        result = await freshsales.execute_action("get_account", {"account_id": 2001, "include": "owner"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"include": "owner"}
        assert result.result.data["account"] == SAMPLE_ACCOUNT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateAccount:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_ACCOUNT, "city": "Auckland"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sales_account": updated})

        result = await freshsales.execute_action("update_account", {"account_id": 2001, "city": "Auckland"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"sales_account": {"city": "Auckland"}}
        assert result.result.data["account"]["city"] == "Auckland"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteAccount:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_account", {"account_id": 2001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/sales_accounts/2001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["account_id"] == 2001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_account", {"account_id": 2001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAccounts:
    @pytest.mark.asyncio
    async def test_explicit_view_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"sales_accounts": [SAMPLE_ACCOUNT], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_accounts", {"view_id": 8}, mock_context)

        assert "/sales_accounts/view/8" in mock_context.fetch.call_args.args[0]
        assert result.result.data["accounts"] == [SAMPLE_ACCOUNT]

    @pytest.mark.asyncio
    async def test_auto_resolves_view(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"filters": [{"id": 6, "name": "All Accounts"}]}),
            FetchResponse(status=200, headers={}, data={"sales_accounts": [], "meta": {}}),
        ]

        await freshsales.execute_action("list_accounts", {}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0].endswith("/sales_accounts/filters")
        assert "/sales_accounts/view/6" in mock_context.fetch.call_args_list[1].args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_accounts", {"view_id": 8}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Account"`
Expected: FAIL — actions not found.

- [ ] **Step 3: Add config schemas** — add to `"actions"` in `freshsales/config.json`:

```json
"create_account": {
    "display_name": "Create Account",
    "description": "Create a new sales account (organization). Name is required.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Account name"},
            "website": {"type": "string", "description": "Website URL"},
            "phone": {"type": "string", "description": "Phone number"},
            "address": {"type": "string", "description": "Street address"},
            "city": {"type": "string", "description": "City"},
            "state": {"type": "string", "description": "State"},
            "zipcode": {"type": "string", "description": "Zip code"},
            "country": {"type": "string", "description": "Country"},
            "industry_type_id": {"type": "integer", "description": "ID of the industry type"},
            "business_type_id": {"type": "integer", "description": "ID of the business type"},
            "number_of_employees": {"type": "integer", "description": "Employee count"},
            "annual_revenue": {"type": "number", "description": "Annual revenue"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the account"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "parent_sales_account_id": {"type": "integer", "description": "ID of the parent account"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": ["name"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"account": {"type": "object", "description": "The created account record"}},
        "required": ["account"]
    }
},
"get_account": {
    "display_name": "Get Account",
    "description": "Retrieve a sales account by ID, optionally embedding related records.",
    "input_schema": {
        "type": "object",
        "properties": {
            "account_id": {"type": "integer", "description": "Account ID"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner,contacts,deals)"}
        },
        "required": ["account_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"account": {"type": "object", "description": "The account record"}},
        "required": ["account"]
    }
},
"update_account": {
    "display_name": "Update Account",
    "description": "Update fields on an existing sales account. Only provided fields are changed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "account_id": {"type": "integer", "description": "Account ID"},
            "name": {"type": "string", "description": "Account name"},
            "website": {"type": "string", "description": "Website URL"},
            "phone": {"type": "string", "description": "Phone number"},
            "address": {"type": "string", "description": "Street address"},
            "city": {"type": "string", "description": "City"},
            "state": {"type": "string", "description": "State"},
            "zipcode": {"type": "string", "description": "Zip code"},
            "country": {"type": "string", "description": "Country"},
            "industry_type_id": {"type": "integer", "description": "ID of the industry type"},
            "business_type_id": {"type": "integer", "description": "ID of the business type"},
            "number_of_employees": {"type": "integer", "description": "Employee count"},
            "annual_revenue": {"type": "number", "description": "Annual revenue"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the account"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "parent_sales_account_id": {"type": "integer", "description": "ID of the parent account"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": ["account_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"account": {"type": "object", "description": "The updated account record"}},
        "required": ["account"]
    }
},
"delete_account": {
    "display_name": "Delete Account",
    "description": "Delete a sales account by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"account_id": {"type": "integer", "description": "Account ID"}},
        "required": ["account_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "account_id": {"type": "integer", "description": "ID of the deleted account"}
        },
        "required": ["success"]
    }
},
"list_accounts": {
    "display_name": "List Accounts",
    "description": "List sales accounts from a view. Omit view_id to use the 'All Accounts' view automatically (use list_views to discover other views). Returns 25 records per page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "view_id": {"type": "integer", "description": "View (filter) ID to list from; omit for the default 'All Accounts' view"},
            "page": {"type": "integer", "minimum": 1, "description": "Page number (default 1)"},
            "sort": {"type": "string", "description": "Field to sort by (e.g. created_at, updated_at, last_contacted)"},
            "sort_type": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner)"}
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "accounts": {"type": "array", "items": {"type": "object"}, "description": "Accounts in the view page"},
            "meta": {"type": "object", "description": "Pagination metadata (total, total_pages)"}
        },
        "required": ["accounts"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
ACCOUNT_FIELDS = (
    "name",
    "website",
    "phone",
    "address",
    "city",
    "state",
    "zipcode",
    "country",
    "industry_type_id",
    "business_type_id",
    "number_of_employees",
    "annual_revenue",
    "owner_id",
    "territory_id",
    "parent_sales_account_id",
    "custom_field",
)


@freshsales.action("create_account")
class CreateAccountAction(ActionHandler):
    """Create a new sales account (organization)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, ACCOUNT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts", method="POST", headers=headers, json={"sales_account": body}
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_account")
class GetAccountAction(ActionHandler):
    """Retrieve a sales account by ID, optionally embedding related records."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_account")
class UpdateAccountAction(ActionHandler):
    """Update fields on an existing sales account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, ACCOUNT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}",
                method="PUT",
                headers=headers,
                json={"sales_account": body},
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_account")
class DeleteAccountAction(ActionHandler):
    """Delete a sales account by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "account_id": inputs["account_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_accounts")
class ListAccountsAction(ActionHandler):
    """List sales accounts from a view, auto-resolving the 'All Accounts' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id") or await resolve_view_id(context, "sales_accounts")
            params = {"page": inputs.get("page", 1)}
            for param in ("sort", "sort_type", "include"):
                if inputs.get(param):
                    params[param] = inputs[param]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(
                data={"accounts": response.data.get("sales_accounts", []), "meta": response.data.get("meta", {})}
            )
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add sales account CRUD and list actions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Deals (5 actions)

**Files:**
- Modify: `freshsales/config.json`
- Modify: `freshsales/freshsales.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: actions `create_deal`, `get_deal`, `update_deal`, `delete_deal`, `list_deals`; constant `DEAL_FIELDS`. Wrapper key `deal`, path `/deals`.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
SAMPLE_DEAL = {"id": 4001, "name": "Big deal", "amount": "23456.0", "sales_account_id": 2001}


class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": SAMPLE_DEAL})

        result = await freshsales.execute_action(
            "create_deal", {"name": "Big deal", "amount": 23456, "sales_account_id": 2001}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"deal": {"name": "Big deal", "amount": 23456, "sales_account_id": 2001}}
        assert result.result.data["deal"] == SAMPLE_DEAL

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action("create_deal", {"name": "X", "amount": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_happy_path_and_include(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": SAMPLE_DEAL})

        result = await freshsales.execute_action("get_deal", {"deal_id": 4001, "include": "owner"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"include": "owner"}
        assert result.result.data["deal"] == SAMPLE_DEAL

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateDeal:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_DEAL, "amount": "99999.0"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"deal": updated})

        result = await freshsales.execute_action("update_deal", {"deal_id": 4001, "amount": 99999}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"deal": {"amount": 99999}}
        assert result.result.data["deal"]["amount"] == "99999.0"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteDeal:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_deal", {"deal_id": 4001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/deals/4001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["deal_id"] == 4001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_deal", {"deal_id": 4001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListDeals:
    @pytest.mark.asyncio
    async def test_explicit_view_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"deals": [SAMPLE_DEAL], "meta": {"total": 1}}
        )

        result = await freshsales.execute_action("list_deals", {"view_id": 12}, mock_context)

        assert "/deals/view/12" in mock_context.fetch.call_args.args[0]
        assert result.result.data["deals"] == [SAMPLE_DEAL]

    @pytest.mark.asyncio
    async def test_auto_resolves_view(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"filters": [{"id": 3, "name": "All Deals"}]}),
            FetchResponse(status=200, headers={}, data={"deals": [], "meta": {}}),
        ]

        await freshsales.execute_action("list_deals", {}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0].endswith("/deals/filters")
        assert "/deals/view/3" in mock_context.fetch.call_args_list[1].args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_deals", {"view_id": 12}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Deal"`
Expected: FAIL — actions not found.

- [ ] **Step 3: Add config schemas** — add to `"actions"` in `freshsales/config.json`:

```json
"create_deal": {
    "display_name": "Create Deal",
    "description": "Create a new deal. Name and amount are required.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Deal name"},
            "amount": {"type": "number", "description": "Deal value"},
            "sales_account_id": {"type": "integer", "description": "ID of the account the deal belongs to"},
            "deal_stage_id": {"type": "integer", "description": "ID of the deal stage"},
            "deal_pipeline_id": {"type": "integer", "description": "ID of the deal pipeline"},
            "deal_type_id": {"type": "integer", "description": "ID of the deal type"},
            "lead_source_id": {"type": "integer", "description": "ID of the lead source"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the deal"},
            "expected_close": {"type": "string", "description": "Expected close date (YYYY-MM-DD)"},
            "probability": {"type": "integer", "description": "Win probability (0-100)"},
            "currency_id": {"type": "integer", "description": "ID of the deal currency"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "campaign_id": {"type": "integer", "description": "ID of the campaign"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": ["name", "amount"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"deal": {"type": "object", "description": "The created deal record"}},
        "required": ["deal"]
    }
},
"get_deal": {
    "display_name": "Get Deal",
    "description": "Retrieve a deal by ID, optionally embedding related records.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "integer", "description": "Deal ID"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner,sales_account,contacts)"}
        },
        "required": ["deal_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"deal": {"type": "object", "description": "The deal record"}},
        "required": ["deal"]
    }
},
"update_deal": {
    "display_name": "Update Deal",
    "description": "Update fields on an existing deal (e.g. move stage, change amount). Only provided fields are changed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "integer", "description": "Deal ID"},
            "name": {"type": "string", "description": "Deal name"},
            "amount": {"type": "number", "description": "Deal value"},
            "sales_account_id": {"type": "integer", "description": "ID of the account the deal belongs to"},
            "deal_stage_id": {"type": "integer", "description": "ID of the deal stage"},
            "deal_pipeline_id": {"type": "integer", "description": "ID of the deal pipeline"},
            "deal_type_id": {"type": "integer", "description": "ID of the deal type"},
            "lead_source_id": {"type": "integer", "description": "ID of the lead source"},
            "owner_id": {"type": "integer", "description": "ID of the user who owns the deal"},
            "expected_close": {"type": "string", "description": "Expected close date (YYYY-MM-DD)"},
            "probability": {"type": "integer", "description": "Win probability (0-100)"},
            "currency_id": {"type": "integer", "description": "ID of the deal currency"},
            "territory_id": {"type": "integer", "description": "ID of the territory"},
            "campaign_id": {"type": "integer", "description": "ID of the campaign"},
            "custom_field": {"type": "object", "description": "Custom field key-value pairs"}
        },
        "required": ["deal_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"deal": {"type": "object", "description": "The updated deal record"}},
        "required": ["deal"]
    }
},
"delete_deal": {
    "display_name": "Delete Deal",
    "description": "Delete a deal by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"deal_id": {"type": "integer", "description": "Deal ID"}},
        "required": ["deal_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "deal_id": {"type": "integer", "description": "ID of the deleted deal"}
        },
        "required": ["success"]
    }
},
"list_deals": {
    "display_name": "List Deals",
    "description": "List deals from a view. Omit view_id to use the 'All Deals' view automatically (use list_views to discover other views, e.g. pipeline-specific ones). Returns 25 records per page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "view_id": {"type": "integer", "description": "View (filter) ID to list from; omit for the default 'All Deals' view"},
            "page": {"type": "integer", "minimum": 1, "description": "Page number (default 1)"},
            "sort": {"type": "string", "description": "Field to sort by (e.g. created_at, updated_at)"},
            "sort_type": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction"},
            "include": {"type": "string", "description": "Comma-separated related records to embed (e.g. owner,sales_account)"}
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "deals": {"type": "array", "items": {"type": "object"}, "description": "Deals in the view page"},
            "meta": {"type": "object", "description": "Pagination metadata (total, total_pages)"}
        },
        "required": ["deals"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
DEAL_FIELDS = (
    "name",
    "amount",
    "sales_account_id",
    "deal_stage_id",
    "deal_pipeline_id",
    "deal_type_id",
    "lead_source_id",
    "owner_id",
    "expected_close",
    "probability",
    "currency_id",
    "territory_id",
    "campaign_id",
    "custom_field",
)


@freshsales.action("create_deal")
class CreateDealAction(ActionHandler):
    """Create a new deal. Name and amount are required."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, DEAL_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/deals", method="POST", headers=headers, json={"deal": body})
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_deal")
class GetDealAction(ActionHandler):
    """Retrieve a deal by ID, optionally embedding related records."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/{inputs['deal_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_deal")
class UpdateDealAction(ActionHandler):
    """Update fields on an existing deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, DEAL_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/{inputs['deal_id']}", method="PUT", headers=headers, json={"deal": body}
            )
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_deal")
class DeleteDealAction(ActionHandler):
    """Delete a deal by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/deals/{inputs['deal_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "deal_id": inputs["deal_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_deals")
class ListDealsAction(ActionHandler):
    """List deals from a view, auto-resolving the 'All Deals' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id") or await resolve_view_id(context, "deals")
            params = {"page": inputs.get("page", 1)}
            for param in ("sort", "sort_type", "include"):
                if inputs.get(param):
                    params[param] = inputs[param]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"deals": response.data.get("deals", []), "meta": response.data.get("meta", {})})
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add deal CRUD and list actions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Tasks (5 actions)

**Files:**
- Modify: `freshsales/config.json`
- Modify: `freshsales/freshsales.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: actions `create_task`, `get_task`, `update_task`, `delete_task`, `list_tasks`; constant `TASK_FIELDS`. Wrapper key `task`, path `/tasks`. Tasks list via `?filter=` (open/due_today/due_tomorrow/overdue/completed) — NOT the view mechanism.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
SAMPLE_TASK = {
    "id": 5001,
    "title": "Follow up",
    "due_date": "2026-07-10T10:00:00Z",
    "targetable_type": "Contact",
    "targetable_id": 3001,
    "status": 0,
}


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": SAMPLE_TASK})

        inputs = {
            "title": "Follow up",
            "due_date": "2026-07-10T10:00:00Z",
            "targetable_type": "Contact",
            "targetable_id": 3001,
        }
        result = await freshsales.execute_action("create_task", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"task": inputs}
        assert result.result.data["task"] == SAMPLE_TASK

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_task",
            {"title": "X", "due_date": "2026-07-10", "targetable_type": "Contact", "targetable_id": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetTask:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": SAMPLE_TASK})

        result = await freshsales.execute_action("get_task", {"task_id": 5001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["task"] == SAMPLE_TASK

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_mark_done_via_status(self, mock_context):
        done = {**SAMPLE_TASK, "status": 1}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"task": done})

        result = await freshsales.execute_action("update_task", {"task_id": 5001, "status": 1}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"task": {"status": 1}}
        assert result.result.data["task"]["status"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_task", {"task_id": 5001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks/5001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["task_id"] == 5001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_task", {"task_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListTasks:
    @pytest.mark.asyncio
    async def test_default_filter_open(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"tasks": [SAMPLE_TASK]})

        result = await freshsales.execute_action("list_tasks", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks")
        assert call_args.kwargs["params"] == {"filter": "open"}
        assert result.result.data["tasks"] == [SAMPLE_TASK]

    @pytest.mark.asyncio
    async def test_explicit_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"tasks": []})

        await freshsales.execute_action("list_tasks", {"filter": "completed"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"filter": "completed"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Task"`
Expected: FAIL — actions not found.

- [ ] **Step 3: Add config schemas** — add to `"actions"` in `freshsales/config.json`:

```json
"create_task": {
    "display_name": "Create Task",
    "description": "Create a task attached to a contact, account, or deal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Task title"},
            "description": {"type": "string", "description": "Task description"},
            "due_date": {"type": "string", "description": "Due date-time (ISO 8601, e.g. 2026-07-10T10:00:00Z)"},
            "owner_id": {"type": "integer", "description": "ID of the user the task is assigned to"},
            "targetable_type": {"type": "string", "enum": ["Contact", "SalesAccount", "Deal"], "description": "Type of record the task is attached to"},
            "targetable_id": {"type": "integer", "description": "ID of the record the task is attached to"}
        },
        "required": ["title", "due_date", "targetable_type", "targetable_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"task": {"type": "object", "description": "The created task record"}},
        "required": ["task"]
    }
},
"get_task": {
    "display_name": "Get Task",
    "description": "Retrieve a task by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"task_id": {"type": "integer", "description": "Task ID"}},
        "required": ["task_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"task": {"type": "object", "description": "The task record"}},
        "required": ["task"]
    }
},
"update_task": {
    "display_name": "Update Task",
    "description": "Update fields on an existing task. Set status to 1 to mark the task as done.",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "Task ID"},
            "title": {"type": "string", "description": "Task title"},
            "description": {"type": "string", "description": "Task description"},
            "due_date": {"type": "string", "description": "Due date-time (ISO 8601)"},
            "owner_id": {"type": "integer", "description": "ID of the user the task is assigned to"},
            "targetable_type": {"type": "string", "enum": ["Contact", "SalesAccount", "Deal"], "description": "Type of record the task is attached to"},
            "targetable_id": {"type": "integer", "description": "ID of the record the task is attached to"},
            "status": {"type": "integer", "description": "Task status: set 1 to mark as done"}
        },
        "required": ["task_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"task": {"type": "object", "description": "The updated task record"}},
        "required": ["task"]
    }
},
"delete_task": {
    "display_name": "Delete Task",
    "description": "Delete a task by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"task_id": {"type": "integer", "description": "Task ID"}},
        "required": ["task_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "task_id": {"type": "integer", "description": "ID of the deleted task"}
        },
        "required": ["success"]
    }
},
"list_tasks": {
    "display_name": "List Tasks",
    "description": "List tasks filtered by status (open, due_today, due_tomorrow, overdue, completed). Defaults to open tasks.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "enum": ["open", "due_today", "due_tomorrow", "overdue", "completed"],
                "description": "Task status filter (default: open)"
            }
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "tasks": {"type": "array", "items": {"type": "object"}, "description": "Tasks matching the filter"}
        },
        "required": ["tasks"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
TASK_FIELDS = ("title", "description", "due_date", "owner_id", "targetable_type", "targetable_id", "status")


@freshsales.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a task attached to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, TASK_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks", method="POST", headers=headers, json={"task": body})
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_task")
class GetTaskAction(ActionHandler):
    """Retrieve a task by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks/{inputs['task_id']}", method="GET", headers=headers)
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update fields on an existing task; set status=1 to mark it done."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, TASK_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/tasks/{inputs['task_id']}", method="PUT", headers=headers, json={"task": body}
            )
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks/{inputs['task_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "task_id": inputs["task_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List tasks by status filter (open, due_today, due_tomorrow, overdue, completed)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"filter": inputs.get("filter", "open")}
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks", method="GET", headers=headers, params=params)
            return ActionResult(data={"tasks": response.data.get("tasks", [])})
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add task CRUD and list actions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Appointments (5 actions)

**Files:**
- Modify: `freshsales/config.json`
- Modify: `freshsales/freshsales.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: actions `create_appointment`, `get_appointment`, `update_appointment`, `delete_appointment`, `list_appointments`; constant `APPOINTMENT_FIELDS`. Wrapper key `appointment`, path `/appointments`. List filter values: `past`, `upcoming`.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
SAMPLE_APPOINTMENT = {
    "id": 6001,
    "title": "Demo call",
    "from_date": "2026-07-10T10:00:00Z",
    "end_date": "2026-07-10T11:00:00Z",
    "targetable_type": "Contact",
    "targetable_id": 3001,
}


class TestCreateAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointment": SAMPLE_APPOINTMENT})

        inputs = {
            "title": "Demo call",
            "from_date": "2026-07-10T10:00:00Z",
            "end_date": "2026-07-10T11:00:00Z",
            "targetable_type": "Contact",
            "targetable_id": 3001,
        }
        result = await freshsales.execute_action("create_appointment", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"appointment": inputs}
        assert result.result.data["appointment"] == SAMPLE_APPOINTMENT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_appointment",
            {
                "title": "X",
                "from_date": "2026-07-10T10:00:00Z",
                "end_date": "2026-07-10T11:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": 1,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetAppointment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointment": SAMPLE_APPOINTMENT})

        result = await freshsales.execute_action("get_appointment", {"appointment_id": 6001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "GET"
        assert result.result.data["appointment"] == SAMPLE_APPOINTMENT

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("get failed")

        result = await freshsales.execute_action("get_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_put_wrapped_body(self, mock_context):
        updated = {**SAMPLE_APPOINTMENT, "location": "Zoom"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointment": updated})

        result = await freshsales.execute_action(
            "update_appointment", {"appointment_id": 6001, "location": "Zoom"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"appointment": {"location": "Zoom"}}
        assert result.result.data["appointment"]["location"] == "Zoom"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteAppointment:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_appointment", {"appointment_id": 6001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments/6001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["appointment_id"] == 6001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_appointment", {"appointment_id": 6001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAppointments:
    @pytest.mark.asyncio
    async def test_no_filter_by_default(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointments": [SAMPLE_APPOINTMENT]})

        result = await freshsales.execute_action("list_appointments", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/appointments")
        assert call_args.kwargs["params"] == {}
        assert result.result.data["appointments"] == [SAMPLE_APPOINTMENT]

    @pytest.mark.asyncio
    async def test_explicit_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"appointments": []})

        await freshsales.execute_action("list_appointments", {"filter": "upcoming"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"] == {"filter": "upcoming"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("list failed")

        result = await freshsales.execute_action("list_appointments", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Appointment"`
Expected: FAIL — actions not found.

- [ ] **Step 3: Add config schemas** — add to `"actions"` in `freshsales/config.json`:

```json
"create_appointment": {
    "display_name": "Create Appointment",
    "description": "Schedule an appointment attached to a contact, account, or deal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Appointment title"},
            "description": {"type": "string", "description": "Appointment description"},
            "from_date": {"type": "string", "description": "Start date-time (ISO 8601, e.g. 2026-07-10T10:00:00Z)"},
            "end_date": {"type": "string", "description": "End date-time (ISO 8601)"},
            "time_zone": {"type": "string", "description": "Time zone name (e.g. Pacific/Auckland)"},
            "location": {"type": "string", "description": "Location or meeting link"},
            "is_allday": {"type": "boolean", "description": "Whether this is an all-day appointment"},
            "targetable_type": {"type": "string", "enum": ["Contact", "SalesAccount", "Deal"], "description": "Type of record the appointment is attached to"},
            "targetable_id": {"type": "integer", "description": "ID of the record the appointment is attached to"}
        },
        "required": ["title", "from_date", "end_date", "targetable_type", "targetable_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"appointment": {"type": "object", "description": "The created appointment record"}},
        "required": ["appointment"]
    }
},
"get_appointment": {
    "display_name": "Get Appointment",
    "description": "Retrieve an appointment by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"appointment_id": {"type": "integer", "description": "Appointment ID"}},
        "required": ["appointment_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"appointment": {"type": "object", "description": "The appointment record"}},
        "required": ["appointment"]
    }
},
"update_appointment": {
    "display_name": "Update Appointment",
    "description": "Update fields on an existing appointment. Only provided fields are changed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "appointment_id": {"type": "integer", "description": "Appointment ID"},
            "title": {"type": "string", "description": "Appointment title"},
            "description": {"type": "string", "description": "Appointment description"},
            "from_date": {"type": "string", "description": "Start date-time (ISO 8601)"},
            "end_date": {"type": "string", "description": "End date-time (ISO 8601)"},
            "time_zone": {"type": "string", "description": "Time zone name"},
            "location": {"type": "string", "description": "Location or meeting link"},
            "is_allday": {"type": "boolean", "description": "Whether this is an all-day appointment"},
            "targetable_type": {"type": "string", "enum": ["Contact", "SalesAccount", "Deal"], "description": "Type of record the appointment is attached to"},
            "targetable_id": {"type": "integer", "description": "ID of the record the appointment is attached to"}
        },
        "required": ["appointment_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"appointment": {"type": "object", "description": "The updated appointment record"}},
        "required": ["appointment"]
    }
},
"delete_appointment": {
    "display_name": "Delete Appointment",
    "description": "Delete an appointment by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"appointment_id": {"type": "integer", "description": "Appointment ID"}},
        "required": ["appointment_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "appointment_id": {"type": "integer", "description": "ID of the deleted appointment"}
        },
        "required": ["success"]
    }
},
"list_appointments": {
    "display_name": "List Appointments",
    "description": "List appointments, optionally filtered to past or upcoming.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filter": {"type": "string", "enum": ["past", "upcoming"], "description": "Time-based filter; omit for all appointments"}
        },
        "required": []
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "appointments": {"type": "array", "items": {"type": "object"}, "description": "Appointments matching the filter"}
        },
        "required": ["appointments"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
APPOINTMENT_FIELDS = (
    "title",
    "description",
    "from_date",
    "end_date",
    "time_zone",
    "location",
    "is_allday",
    "targetable_type",
    "targetable_id",
)


@freshsales.action("create_appointment")
class CreateAppointmentAction(ActionHandler):
    """Schedule an appointment attached to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, APPOINTMENT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments", method="POST", headers=headers, json={"appointment": body}
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_appointment")
class GetAppointmentAction(ActionHandler):
    """Retrieve an appointment by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}", method="GET", headers=headers
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_appointment")
class UpdateAppointmentAction(ActionHandler):
    """Update fields on an existing appointment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, APPOINTMENT_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}",
                method="PUT",
                headers=headers,
                json={"appointment": body},
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_appointment")
class DeleteAppointmentAction(ActionHandler):
    """Delete an appointment by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(
                data={"success": bool(data.get("success", True)), "appointment_id": inputs["appointment_id"]}
            )
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_appointments")
class ListAppointmentsAction(ActionHandler):
    """List appointments, optionally filtered to past or upcoming."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("filter"):
                params["filter"] = inputs["filter"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/appointments", method="GET", headers=headers, params=params)
            return ActionResult(data={"appointments": response.data.get("appointments", [])})
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add appointment CRUD and list actions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Notes (3 actions) + Search (1 action)

**Files:**
- Modify: `freshsales/config.json`
- Modify: `freshsales/freshsales.py`
- Test: `freshsales/tests/test_freshsales_unit.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: actions `create_note`, `update_note`, `delete_note`, `search`. Note wrapper key `note`, path `/notes`. Search: `GET /search?q=...&include=contact,sales_account,deal` — response is a JSON ARRAY, not an object.

- [ ] **Step 1: Write the failing tests** — append to `freshsales/tests/test_freshsales_unit.py`:

```python
SAMPLE_NOTE = {"id": 7001, "description": "Call summary", "targetable_type": "Contact", "targetable_id": 3001}


class TestCreateNote:
    @pytest.mark.asyncio
    async def test_happy_path_wrapped_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"note": SAMPLE_NOTE})

        inputs = {"description": "Call summary", "targetable_type": "Contact", "targetable_id": 3001}
        result = await freshsales.execute_action("create_note", inputs, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes")
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"note": inputs}
        assert result.result.data["note"] == SAMPLE_NOTE

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("create failed")

        result = await freshsales.execute_action(
            "create_note", {"description": "X", "targetable_type": "Contact", "targetable_id": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateNote:
    @pytest.mark.asyncio
    async def test_happy_path_put(self, mock_context):
        updated = {**SAMPLE_NOTE, "description": "Updated summary"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"note": updated})

        result = await freshsales.execute_action(
            "update_note", {"note_id": 7001, "description": "Updated summary"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes/7001")
        assert call_args.kwargs["method"] == "PUT"
        assert call_args.kwargs["json"] == {"note": {"description": "Updated summary"}}
        assert result.result.data["note"]["description"] == "Updated summary"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("update failed")

        result = await freshsales.execute_action("update_note", {"note_id": 7001, "description": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteNote:
    @pytest.mark.asyncio
    async def test_happy_path_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await freshsales.execute_action("delete_note", {"note_id": 7001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/notes/7001")
        assert call_args.kwargs["method"] == "DELETE"
        assert result.result.data["success"] is True
        assert result.result.data["note_id"] == 7001

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("delete failed")

        result = await freshsales.execute_action("delete_note", {"note_id": 7001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestSearch:
    @pytest.mark.asyncio
    async def test_happy_path_returns_results(self, mock_context):
        results = [{"id": 3001, "type": "contact", "name": "Jane Doe"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=results)

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/search")
        assert call_args.kwargs["params"]["q"] == "jane"
        assert call_args.kwargs["params"]["include"] == "contact,sales_account,deal"
        assert result.result.data["results"] == results
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_custom_include_entities(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshsales.execute_action("search", {"query": "acme", "include": "sales_account"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["include"] == "sales_account"

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"unexpected": True})

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        assert result.result.data["results"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("search failed")

        result = await freshsales.execute_action("search", {"query": "jane"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest freshsales/ -v -k "Note or Search"`
Expected: FAIL — actions not found.

- [ ] **Step 3: Add config schemas** — add to `"actions"` in `freshsales/config.json`:

```json
"create_note": {
    "display_name": "Create Note",
    "description": "Attach a note to a contact, account, or deal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Note content"},
            "targetable_type": {"type": "string", "enum": ["Contact", "SalesAccount", "Deal"], "description": "Type of record the note is attached to"},
            "targetable_id": {"type": "integer", "description": "ID of the record the note is attached to"}
        },
        "required": ["description", "targetable_type", "targetable_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"note": {"type": "object", "description": "The created note record"}},
        "required": ["note"]
    }
},
"update_note": {
    "display_name": "Update Note",
    "description": "Update the content of an existing note.",
    "input_schema": {
        "type": "object",
        "properties": {
            "note_id": {"type": "integer", "description": "Note ID"},
            "description": {"type": "string", "description": "New note content"}
        },
        "required": ["note_id", "description"]
    },
    "output_schema": {
        "type": "object",
        "properties": {"note": {"type": "object", "description": "The updated note record"}},
        "required": ["note"]
    }
},
"delete_note": {
    "display_name": "Delete Note",
    "description": "Delete a note by ID.",
    "input_schema": {
        "type": "object",
        "properties": {"note_id": {"type": "integer", "description": "Note ID"}},
        "required": ["note_id"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the deletion succeeded"},
            "note_id": {"type": "integer", "description": "ID of the deleted note"}
        },
        "required": ["success"]
    }
},
"search": {
    "display_name": "Search",
    "description": "Search across contacts, accounts, and deals by name, email, or other text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search text"},
            "include": {"type": "string", "description": "Comma-separated entity types to search: contact, sales_account, deal, user (default: contact,sales_account,deal)"},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Max results to return"}
        },
        "required": ["query"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "results": {"type": "array", "items": {"type": "object"}, "description": "Matching records with their entity type"},
            "total": {"type": "integer", "description": "Number of results returned"}
        },
        "required": ["results"]
    }
}
```

- [ ] **Step 4: Implement handlers** — append to `freshsales/freshsales.py`:

```python
NOTE_FIELDS = ("description", "targetable_type", "targetable_id")


@freshsales.action("create_note")
class CreateNoteAction(ActionHandler):
    """Attach a note to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, NOTE_FIELDS)
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/notes", method="POST", headers=headers, json={"note": body})
            return ActionResult(data={"note": response.data.get("note", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_note")
class UpdateNoteAction(ActionHandler):
    """Update the content of an existing note."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"description": inputs["description"]}
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/notes/{inputs['note_id']}", method="PUT", headers=headers, json={"note": body}
            )
            return ActionResult(data={"note": response.data.get("note", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_note")
class DeleteNoteAction(ActionHandler):
    """Delete a note by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/notes/{inputs['note_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "note_id": inputs["note_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("search")
class SearchAction(ActionHandler):
    """Search across contacts, sales accounts, and deals."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"q": inputs["query"], "include": inputs.get("include", "contact,sales_account,deal")}
            if inputs.get("per_page"):
                params["per_page"] = inputs["per_page"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/search", method="GET", headers=headers, params=params)
            results = response.data if isinstance(response.data, list) else []
            return ActionResult(data={"results": results, "total": len(results)})
        except Exception as e:
            return ActionError(message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest freshsales/ -v`
Expected: ALL PASS — all 30 actions now registered; `TestConfigValidation` confirms config/handler sync.

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
git add freshsales/
git commit -m "feat(freshsales): add note actions and global search

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Live integration tests

**Files:**
- Create: `freshsales/tests/test_freshsales_integration.py`

**Interfaces:**
- Consumes: root `conftest.py` fixtures `env_credentials` and `make_context`; all 30 actions.
- Produces: live test suite gated on `FRESHSALES_API_KEY` + `FRESHSALES_BUNDLE_ALIAS` in `.env`.

- [ ] **Step 1: Write the integration tests**

Create `freshsales/tests/test_freshsales_integration.py`:

```python
"""
Live integration tests for the Freshsales integration.

Requires FRESHSALES_API_KEY and FRESHSALES_BUNDLE_ALIAS set in the environment (.env).

Run with:
    pytest freshsales/tests/test_freshsales_integration.py -m "integration" --import-mode=importlib --tb=short

Lifecycle tests that create/delete real records carry the `destructive` marker; exclude
them with -m "integration and not destructive".
"""

import time

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from freshsales.freshsales import freshsales

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("FRESHSALES_API_KEY")
    bundle_alias = env_credentials("FRESHSALES_BUNDLE_ALIAS")
    if not api_key:
        pytest.skip("FRESHSALES_API_KEY not set — skipping integration tests")
    if not bundle_alias:
        pytest.skip("FRESHSALES_BUNDLE_ALIAS not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, **kwargs) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    credentials = {"api_key": api_key, "bundle_alias": bundle_alias}
    ctx = make_context(auth={"auth_type": "Custom", "credentials": credentials})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


async def test_list_views_contacts(live_context):
    result = await freshsales.execute_action("list_views", {"entity": "contacts"}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["views"], list)
    assert result.result.data["total"] >= 1


async def test_list_contacts_auto_view(live_context):
    result = await freshsales.execute_action("list_contacts", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["contacts"], list)


async def test_list_accounts_auto_view(live_context):
    result = await freshsales.execute_action("list_accounts", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["accounts"], list)


async def test_list_deals_auto_view(live_context):
    result = await freshsales.execute_action("list_deals", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["deals"], list)


async def test_list_tasks(live_context):
    result = await freshsales.execute_action("list_tasks", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["tasks"], list)


async def test_search(live_context):
    result = await freshsales.execute_action("search", {"query": "a"}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["results"], list)


# ---- Destructive / Lifecycle Tests ----


@pytest.mark.destructive
async def test_contact_lifecycle(live_context):
    """create -> get -> update -> delete contact."""
    uid = int(time.time())
    contact_id = None

    try:
        create = await freshsales.execute_action(
            "create_contact",
            {"first_name": "AH Test", "last_name": f"Contact {uid}", "email": f"ah.test.{uid}@example.com"},
            live_context,
        )
        assert create.type == ResultType.ACTION
        contact_id = create.result.data["contact"]["id"]

        get = await freshsales.execute_action("get_contact", {"contact_id": contact_id}, live_context)
        assert get.result.data["contact"]["id"] == contact_id

        update = await freshsales.execute_action(
            "update_contact", {"contact_id": contact_id, "job_title": "Integration Test"}, live_context
        )
        assert update.result.data["contact"]["job_title"] == "Integration Test"
    finally:
        if contact_id:
            delete = await freshsales.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
            assert delete.type == ResultType.ACTION


@pytest.mark.destructive
async def test_account_and_deal_lifecycle(live_context):
    """create account -> create deal on it -> update deal -> delete both."""
    uid = int(time.time())
    account_id = None
    deal_id = None

    try:
        acc = await freshsales.execute_action("create_account", {"name": f"AH Test Co {uid}"}, live_context)
        assert acc.type == ResultType.ACTION
        account_id = acc.result.data["account"]["id"]

        deal = await freshsales.execute_action(
            "create_deal", {"name": f"AH Test Deal {uid}", "amount": 100, "sales_account_id": account_id}, live_context
        )
        assert deal.type == ResultType.ACTION
        deal_id = deal.result.data["deal"]["id"]

        update = await freshsales.execute_action("update_deal", {"deal_id": deal_id, "amount": 200}, live_context)
        assert update.type == ResultType.ACTION
    finally:
        if deal_id:
            await freshsales.execute_action("delete_deal", {"deal_id": deal_id}, live_context)
        if account_id:
            await freshsales.execute_action("delete_account", {"account_id": account_id}, live_context)


@pytest.mark.destructive
async def test_task_note_appointment_lifecycle(live_context):
    """create a temp contact, attach task/note/appointment, clean everything up."""
    uid = int(time.time())
    contact_id = None
    task_id = None
    note_id = None
    appointment_id = None

    try:
        contact = await freshsales.execute_action(
            "create_contact",
            {"first_name": "AH Test", "last_name": f"Target {uid}", "email": f"ah.target.{uid}@example.com"},
            live_context,
        )
        contact_id = contact.result.data["contact"]["id"]

        task = await freshsales.execute_action(
            "create_task",
            {
                "title": f"AH Test Task {uid}",
                "due_date": "2027-01-01T10:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": contact_id,
            },
            live_context,
        )
        assert task.type == ResultType.ACTION
        task_id = task.result.data["task"]["id"]

        done = await freshsales.execute_action("update_task", {"task_id": task_id, "status": 1}, live_context)
        assert done.type == ResultType.ACTION

        note = await freshsales.execute_action(
            "create_note",
            {"description": f"AH test note {uid}", "targetable_type": "Contact", "targetable_id": contact_id},
            live_context,
        )
        assert note.type == ResultType.ACTION
        note_id = note.result.data["note"]["id"]

        appt = await freshsales.execute_action(
            "create_appointment",
            {
                "title": f"AH Test Appt {uid}",
                "from_date": "2027-01-01T10:00:00Z",
                "end_date": "2027-01-01T11:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": contact_id,
            },
            live_context,
        )
        assert appt.type == ResultType.ACTION
        appointment_id = appt.result.data["appointment"]["id"]
    finally:
        if appointment_id:
            await freshsales.execute_action("delete_appointment", {"appointment_id": appointment_id}, live_context)
        if note_id:
            await freshsales.execute_action("delete_note", {"note_id": note_id}, live_context)
        if task_id:
            await freshsales.execute_action("delete_task", {"task_id": task_id}, live_context)
        if contact_id:
            await freshsales.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
```

- [ ] **Step 2: Verify skip behavior without credentials**

Run: `pytest freshsales/tests/test_freshsales_integration.py -m integration -v`
Expected (no `.env` creds): all tests SKIPPED with "FRESHSALES_API_KEY not set".

- [ ] **Step 3: Run live (user has credentials)**

Ask the user to add to `.env` at repo root (NEVER commit):
```
FRESHSALES_API_KEY=<their key>
FRESHSALES_BUNDLE_ALIAS=<their bundle alias>
```
Run: `pytest freshsales/tests/test_freshsales_integration.py -m integration -v`
Expected: all PASS against the live account. If a specific endpoint 404s or a payload key differs, fix the handler + unit tests to match reality (official docs: https://developers.freshworks.com/crm/api/), re-run unit + live tests.

- [ ] **Step 4: Verify unit suite still green and commit**

```bash
pytest freshsales/ -v
git status --short          # confirm .env is NOT staged
git add freshsales/tests/test_freshsales_integration.py
git commit -m "test(freshsales): add live integration tests with lifecycle cleanup

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Icon, integration README, root README row

**Files:**
- Create: `freshsales/icon.png` (512×512)
- Create: `freshsales/README.md`
- Modify: root `README.md` (add Freshsales section after the Freshdesk section, ~line 260)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the remaining files `validate_integration.py` requires.

- [ ] **Step 1: Source the icon**

Find the official logo URL from the Freshsales site, then download and normalize to 512×512:

```bash
curl -sL https://www.freshworks.com/crm/sales/ | grep -oiE '(apple-touch-icon|og:image)[^>]*' | head -5
# take a logo/icon URL from the output, then:
curl -sL -o /tmp/freshsales-logo.png "<logo-url>"
sips -g pixelWidth -g pixelHeight /tmp/freshsales-logo.png
sips -z 512 512 /tmp/freshsales-logo.png --out freshsales/icon.png
```
Expected: `freshsales/icon.png` exists at 512×512. If no usable PNG is found, STOP and ask the user to supply a logo file — do not ship a placeholder.

- [ ] **Step 2: Write `freshsales/README.md`**

```markdown
# Freshsales Integration for Autohive

Connects Autohive to the [Freshsales](https://www.freshworks.com/crm/sales/) CRM
(Freshworks) to manage contacts, sales accounts, deals, tasks, appointments, and notes.

## Description

This integration covers the core Freshsales CRM objects with full CRUD actions, plus
list-view discovery and global search. Freshsales lists records through *views*
(saved filters): the list actions accept an optional `view_id` and automatically use
the "All Contacts/Accounts/Deals" view when none is given. Use the `list_views` action
to discover other views (e.g. pipeline- or owner-specific ones).

## Setup & Authentication

1. In Freshsales, go to **Personal Settings → API Settings** and copy your **API key**.
2. Note your **bundle alias** — the `yourcompany` part of `yourcompany.myfreshworks.com`.
3. When adding the integration in Autohive, enter both values.

Note: the Freshsales API is included in all plans under a fair-usage policy. Rate
limits are per account per hour and vary by plan; exceeding them returns HTTP 429.

## Actions

| Action | Description |
| ------ | ----------- |
| `create_contact` / `get_contact` / `update_contact` / `delete_contact` / `list_contacts` | Contact CRUD; list supports views, pagination, sorting, and includes |
| `create_account` / `get_account` / `update_account` / `delete_account` / `list_accounts` | Sales account (organization) CRUD |
| `create_deal` / `get_deal` / `update_deal` / `delete_deal` / `list_deals` | Deal CRUD with pipeline/stage support |
| `create_task` / `get_task` / `update_task` / `delete_task` / `list_tasks` | Task CRUD; list filters by open/due_today/due_tomorrow/overdue/completed; set `status: 1` to complete |
| `create_appointment` / `get_appointment` / `update_appointment` / `delete_appointment` / `list_appointments` | Appointment CRUD; list filters by past/upcoming |
| `create_note` / `update_note` / `delete_note` | Attach notes to contacts, accounts, or deals |
| `list_views` | Discover list views (filters) for contacts, accounts, or deals |
| `search` | Global search across contacts, accounts, and deals |

## Requirements

- Python 3.13+
- autohive-integrations-sdk ~= 2.0.0

## Testing

```bash
# Unit tests (mocked)
pytest freshsales/ -v

# Live integration tests — requires FRESHSALES_API_KEY and FRESHSALES_BUNDLE_ALIAS in .env
pytest freshsales/tests/test_freshsales_integration.py -m integration -v
```
```

- [ ] **Step 3: Add the root README section** — insert after the Freshdesk section (after the `[freshdesk](freshdesk): ...` paragraph, around line 260):

```markdown
### Freshsales

[freshsales](freshsales): CRM integration with Freshsales (Freshworks) for complete sales pipeline operations. Supports contact management (full CRUD with view-based listing and related-record embedding), sales account management (create and manage organizations), deal management (full CRUD with pipeline, stage, and amount control), task management (create, filter by status, complete, and delete tasks), appointment scheduling (create and manage appointments attached to CRM records), and note taking (attach notes to contacts, accounts, or deals). Also provides list-view discovery and global search across entities. Features custom API key authentication with token headers, automatic default-view resolution for list operations, pagination and sorting support, and robust error handling. Ideal for automating sales workflows, pipeline management, and CRM data operations.
```

- [ ] **Step 4: Verify and commit**

```bash
pytest freshsales/ -v
git add freshsales/icon.png freshsales/README.md README.md
git commit -m "docs(freshsales): add icon, integration README, and root README entry

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Full validation pipeline

**Files:**
- Modify: whatever the validators flag (expect none or small fixes)

**Interfaces:**
- Consumes: everything.
- Produces: a CI-clean integration.

- [ ] **Step 1: Structure validation**

Run: `python ../autohive-integrations-tooling/scripts/validate_integration.py freshsales`
Expected: exit 0, no `❌` errors. Fix any errors it reports and re-run.

- [ ] **Step 2: Code quality checks**

Run: `python ../autohive-integrations-tooling/scripts/check_code.py freshsales`
Expected: `✅ CODE CHECK PASSED` (syntax, imports, JSON validity, ruff, bandit, pip-audit, config↔code sync, fetch pattern). Common fixes: `# nosec B105` on fake test credentials; ruff auto-fix.

- [ ] **Step 3: Full unit suite + lint one last time**

```bash
ruff check --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --check --config ../autohive-integrations-tooling/ruff.toml freshsales
pytest freshsales/ -v
```
Expected: all clean, all pass.

- [ ] **Step 4: Commit any validator fixes**

```bash
git add freshsales/ README.md
git commit -m "fix(freshsales): address validation pipeline findings

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
(Skip this commit if Steps 1-3 required no changes.)

- [ ] **Step 5: Report done**

Summarize to the user: actions delivered, test results (unit + live), validation output, the issue number from Task 1, and that the branch is ready for `git push` + PR (title `feat: add Freshsales CRM integration`, body `Closes #<issue>`). Do NOT push without the user's go-ahead.

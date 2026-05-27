from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    FetchResponse,
)
from typing import Any, Dict, List
import re

# Create the integration using the config.json
trello = Integration.load()

# Base URL for Trello API
TRELLO_API_BASE_URL = "https://api.trello.com/1"

# Defaults
DEFAULT_CARD_FIELDS = "id,name,idList,idBoard,due,dueComplete,closed,url,shortUrl"
DEFAULT_LIST_CARDS_LIMIT = 50
DEFAULT_SEARCH_CARDS_LIMIT = 10

# Detect explicit card-status operators in a user-supplied query so we don't
# accidentally append `is:open` when they asked for `is:closed`/`is:archived`.
_STATUS_QUERY_RE = re.compile(r"(^|\s)-?is:(open|closed|archived)\b", re.IGNORECASE)


# ---- Helpers ----


def get_auth_params(context: ExecutionContext) -> Dict[str, str]:
    """Get authentication parameters from context credentials."""
    credentials = context.auth.get("credentials", {})
    return {"key": credentials.get("api_key"), "token": credentials.get("token")}


def merge_params(params: Dict[str, Any], auth_params: Dict[str, str]) -> Dict[str, Any]:
    """Merge request params with auth params."""
    merged = {**params}
    merged.update(auth_params)
    return merged


def _bool_param(value: Any, default: bool = False) -> str:
    """Render a value as Trello's lowercase boolean query string."""
    if value is None:
        coerced = default
    elif isinstance(value, bool):
        coerced = value
    elif isinstance(value, str):
        coerced = value.strip().lower() in {"true", "1", "yes", "y"}
    else:
        coerced = bool(value)
    return "true" if coerced else "false"


def _clamp_limit(value: Any, default: int, lo: int = 1, hi: int = 1000) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(n, hi))


def _quote_search_value(value: str) -> str:
    """Quote a Trello search value and escape embedded quotes."""
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _trello_error_message(response: FetchResponse) -> str:
    """Build a useful error message from a Trello FetchResponse."""
    body = response.data
    if isinstance(body, dict):
        for key in ("message", "error", "errorDescription"):
            val = body.get(key)
            if val:
                return str(val)
        return str(body)
    if isinstance(body, str) and body.strip():
        return body.strip()
    return f"Trello API returned HTTP {response.status}"


def _unwrap_trello_response(response: FetchResponse) -> Any:
    """Raise if the Trello response is non-2xx; otherwise return its body."""
    if response.status < 200 or response.status >= 300:
        raise RuntimeError(_trello_error_message(response))
    return response.data


def _project_card_fields(cards: List[Any], fields: str) -> List[Any]:
    """Client-side projection: keep only requested fields per card.

    Guarantees compact output even if Trello ignores the ``fields`` query param.
    Pass ``"all"`` (or empty) to disable projection.
    """
    if not fields or fields == "all":
        return cards
    wanted = {f.strip() for f in fields.split(",") if f.strip()}
    if not wanted:
        return cards
    return [{k: v for k, v in card.items() if k in wanted} if isinstance(card, dict) else card for card in cards]


# ---- Member Handlers ----


@trello.action("get_current_member")
class GetCurrentMemberAction(ActionHandler):
    """Get information about the authenticated member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/members/me", method="GET", params=auth_params)
            member = _unwrap_trello_response(response)

            return ActionResult(data={"member": member}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Board Handlers ----


@trello.action("create_board")
class CreateBoardAction(ActionHandler):
    """Create a new board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"name": inputs["name"]}

            if inputs.get("desc"):
                params["desc"] = inputs["desc"]
            if inputs.get("defaultLists") is not None:
                params["defaultLists"] = _bool_param(inputs["defaultLists"])
            if inputs.get("prefs_permissionLevel"):
                params["prefs_permissionLevel"] = inputs["prefs_permissionLevel"]
            if inputs.get("prefs_background"):
                params["prefs_background"] = inputs["prefs_background"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/boards/", method="POST", params=merged_params)
            board = _unwrap_trello_response(response)

            return ActionResult(data={"board": board}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("get_board")
class GetBoardAction(ActionHandler):
    """Get details of a specific board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs["board_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("fields"):
                params["fields"] = inputs["fields"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}", method="GET", params=merged_params
            )
            board = _unwrap_trello_response(response)

            return ActionResult(data={"board": board}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("update_board")
class UpdateBoardAction(ActionHandler):
    """Update an existing board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs["board_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("name"):
                params["name"] = inputs["name"]
            if inputs.get("desc"):
                params["desc"] = inputs["desc"]
            if inputs.get("closed") is not None:
                params["closed"] = _bool_param(inputs["closed"])
            if inputs.get("prefs_permissionLevel"):
                params["prefs/permissionLevel"] = inputs["prefs_permissionLevel"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}", method="PUT", params=merged_params
            )
            board = _unwrap_trello_response(response)

            return ActionResult(data={"board": board}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("list_boards")
class ListBoardsAction(ActionHandler):
    """List all boards for the authenticated member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("filter"):
                params["filter"] = inputs["filter"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/members/me/boards", method="GET", params=merged_params
            )
            body = _unwrap_trello_response(response)
            boards = body if isinstance(body, list) else []

            return ActionResult(data={"boards": boards, "count": len(boards)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- List Handlers ----


@trello.action("create_list")
class CreateListAction(ActionHandler):
    """Create a new list on a board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"name": inputs["name"], "idBoard": inputs["board_id"]}

            if inputs.get("pos"):
                params["pos"] = inputs["pos"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/lists", method="POST", params=merged_params)
            list_ = _unwrap_trello_response(response)

            return ActionResult(data={"list": list_}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("get_list")
class GetListAction(ActionHandler):
    """Get details of a specific list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]
            auth_params = get_auth_params(context)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/lists/{list_id}", method="GET", params=auth_params)
            list_ = _unwrap_trello_response(response)

            return ActionResult(data={"list": list_}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("update_list")
class UpdateListAction(ActionHandler):
    """Update a list's properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("name"):
                params["name"] = inputs["name"]
            if inputs.get("closed") is not None:
                params["closed"] = _bool_param(inputs["closed"])
            if inputs.get("pos"):
                params["pos"] = inputs["pos"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/lists/{list_id}", method="PUT", params=merged_params)
            list_ = _unwrap_trello_response(response)

            return ActionResult(data={"list": list_}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("list_lists")
class ListListsAction(ActionHandler):
    """List all lists on a board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs["board_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("filter"):
                params["filter"] = inputs["filter"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists",
                method="GET",
                params=merged_params,
            )
            body = _unwrap_trello_response(response)
            lists = body if isinstance(body, list) else []

            return ActionResult(data={"lists": lists, "count": len(lists)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Card Handlers ----


@trello.action("create_card")
class CreateCardAction(ActionHandler):
    """Create a new card on a list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"name": inputs["name"], "idList": inputs["list_id"]}

            if inputs.get("desc"):
                params["desc"] = inputs["desc"]
            if inputs.get("pos"):
                params["pos"] = inputs["pos"]
            if inputs.get("due"):
                params["due"] = inputs["due"]
            if inputs.get("idMembers"):
                params["idMembers"] = ",".join(inputs["idMembers"])
            if inputs.get("idLabels"):
                params["idLabels"] = ",".join(inputs["idLabels"])

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/cards", method="POST", params=merged_params)
            card = _unwrap_trello_response(response)

            return ActionResult(data={"card": card}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("get_card")
class GetCardAction(ActionHandler):
    """Get details of a specific card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs["card_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("fields"):
                params["fields"] = inputs["fields"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/cards/{card_id}", method="GET", params=merged_params)
            card = _unwrap_trello_response(response)

            return ActionResult(data={"card": card}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("update_card")
class UpdateCardAction(ActionHandler):
    """Update an existing card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs["card_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {}

            if inputs.get("name"):
                params["name"] = inputs["name"]
            if inputs.get("desc"):
                params["desc"] = inputs["desc"]
            if inputs.get("closed") is not None:
                params["closed"] = _bool_param(inputs["closed"])
            if inputs.get("idList"):
                params["idList"] = inputs["idList"]
            if inputs.get("due"):
                params["due"] = inputs["due"]
            if inputs.get("dueComplete") is not None:
                params["dueComplete"] = _bool_param(inputs["dueComplete"])
            if inputs.get("idMembers"):
                params["idMembers"] = ",".join(inputs["idMembers"])

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/cards/{card_id}", method="PUT", params=merged_params)
            card = _unwrap_trello_response(response)

            return ActionResult(data={"card": card}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("delete_card")
class DeleteCardAction(ActionHandler):
    """Delete a card permanently."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs["card_id"]
            auth_params = get_auth_params(context)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}", method="DELETE", params=auth_params
            )
            _unwrap_trello_response(response)

            return ActionResult(data={"deleted": True, "card_id": card_id}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("list_cards")
class ListCardsAction(ActionHandler):
    """List cards on a list or board with cursor-based pagination.

    Uses Trello's documented ``limit`` + ``before``/``since`` pagination on
    ``/lists/{id}/cards`` and ``/boards/{id}/cards`` (per
    https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/#paging).
    Returns a ``next_before`` cursor when more results may exist, so callers can
    paginate by passing that value back as ``before``. ``fields`` is also
    enforced client-side so callers always get the compact shape.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)

            limit = _clamp_limit(inputs.get("limit"), DEFAULT_LIST_CARDS_LIMIT)
            fields = inputs.get("fields") or DEFAULT_CARD_FIELDS

            # Always request `id` from Trello so we can generate `next_before`,
            # even when the user-requested projection excludes it. The user's
            # projection is still enforced client-side after pagination.
            api_fields = fields
            if fields != "all":
                parts = [f.strip() for f in fields.split(",") if f.strip()]
                if parts and "id" not in parts:
                    api_fields = ",".join([*parts, "id"])

            # Trello caps /cards endpoints at 1000 per request; send limit
            # server-side so we don't pull more than needed.
            params: Dict[str, Any] = {"fields": api_fields, "limit": limit}

            # Default filter to "open" so config, README, and runtime agree.
            params["filter"] = inputs.get("filter") or "open"
            if inputs.get("before"):
                params["before"] = inputs["before"]
            if inputs.get("since"):
                params["since"] = inputs["since"]

            merged_params = merge_params(params, auth_params)

            if inputs.get("list_id"):
                url = f"{TRELLO_API_BASE_URL}/lists/{inputs['list_id']}/cards"
            elif inputs.get("board_id"):
                url = f"{TRELLO_API_BASE_URL}/boards/{inputs['board_id']}/cards"
            else:
                return ActionError(message="Either list_id or board_id is required")

            response = await context.fetch(url, method="GET", params=merged_params)
            body = _unwrap_trello_response(response)
            cards = body if isinstance(body, list) else []

            # Defensive local cap in case Trello returns more than asked.
            cards = cards[:limit]

            # Compute next-page cursor BEFORE projection (need raw id).
            # Trello returns cards in reverse-creation order (newest first), so
            # the oldest card's id is the cursor to pass as `before` to fetch
            # the next page. We only emit it when a full page came back, which
            # is the standard "may have more" heuristic.
            next_before = None
            if len(cards) == limit and cards:
                last = cards[-1]
                if isinstance(last, dict):
                    next_before = last.get("id")

            cards = _project_card_fields(cards, fields)

            data: Dict[str, Any] = {"cards": cards, "count": len(cards)}
            if next_before:
                data["next_before"] = next_before

            return ActionResult(data=data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("search_cards")
class SearchCardsAction(ActionHandler):
    """Search for Trello cards by name/text or advanced Trello query.

    Uses ``GET /1/search?modelTypes=cards``. Defaults to ``is:open`` unless the
    user-supplied ``query`` already specifies a card status operator
    (``is:open``, ``is:closed``, ``is:archived``, or their negations).
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)

            card_name = inputs.get("card_name")
            advanced_query = (inputs.get("query") or "").strip()

            query_parts = []
            if card_name:
                query_parts.append(f"name:{_quote_search_value(card_name)}")
            if advanced_query:
                query_parts.append(advanced_query)

            query_text = " ".join(query_parts).strip()
            if not query_text:
                return ActionError(message="Either card_name or query is required")

            # Only inject is:open when the user's advanced query has no
            # explicit card-status operator (avoids contradictions like
            # `is:closed is:open`).
            if _bool_param(inputs.get("open_only"), default=True) == "true" and not _STATUS_QUERY_RE.search(
                advanced_query
            ):
                query_text = f"{query_text} is:open"

            limit = _clamp_limit(inputs.get("limit"), DEFAULT_SEARCH_CARDS_LIMIT)

            params: Dict[str, Any] = {
                "query": query_text,
                "modelTypes": "cards",
                "cards_limit": limit,
                "partial": _bool_param(inputs.get("partial"), default=True),
                "card_fields": inputs.get("fields") or DEFAULT_CARD_FIELDS,
                "card_board": _bool_param(inputs.get("include_board"), default=True),
                "card_list": _bool_param(inputs.get("include_list"), default=True),
                "card_members": _bool_param(inputs.get("include_members"), default=False),
                "card_attachments": _bool_param(inputs.get("include_attachments"), default=False),
            }

            page = inputs.get("page")
            if page is not None:
                try:
                    params["cards_page"] = max(0, int(page))
                except (TypeError, ValueError):
                    pass

            if inputs.get("board_id"):
                params["idBoards"] = inputs["board_id"]
            if inputs.get("organization_id"):
                params["idOrganizations"] = inputs["organization_id"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/search", method="GET", params=merged_params)
            body = _unwrap_trello_response(response)

            if isinstance(body, dict):
                cards = body.get("cards") or []
                options = body.get("options") or {}
            elif isinstance(body, list):
                cards = body
                options = {}
            else:
                cards = []
                options = {}

            return ActionResult(
                data={"cards": cards, "count": len(cards), "options": options},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


# ---- Checklist Handlers ----


@trello.action("create_checklist")
class CreateChecklistAction(ActionHandler):
    """Create a new checklist on a card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"idCard": inputs["card_id"], "name": inputs["name"]}

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(f"{TRELLO_API_BASE_URL}/checklists", method="POST", params=merged_params)
            checklist = _unwrap_trello_response(response)

            return ActionResult(data={"checklist": checklist}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@trello.action("add_checklist_item")
class AddChecklistItemAction(ActionHandler):
    """Add a new item to a checklist."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            checklist_id = inputs["checklist_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"name": inputs["name"]}

            if inputs.get("checked") is not None:
                params["checked"] = _bool_param(inputs["checked"])
            if inputs.get("pos"):
                params["pos"] = inputs["pos"]

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/checklists/{checklist_id}/checkItems",
                method="POST",
                params=merged_params,
            )
            check_item = _unwrap_trello_response(response)

            return ActionResult(data={"checkItem": check_item}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Comment Handler ----


@trello.action("add_comment")
class AddCommentAction(ActionHandler):
    """Add a comment to a card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs["card_id"]
            auth_params = get_auth_params(context)
            params: Dict[str, Any] = {"text": inputs["text"]}

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}/actions/comments",
                method="POST",
                params=merged_params,
            )
            comment = _unwrap_trello_response(response)

            return ActionResult(data={"comment": comment}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

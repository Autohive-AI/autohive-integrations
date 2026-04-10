from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

# Create the integration using the config.json
trello = Integration.load()

# Base URL for Trello API
TRELLO_API_BASE_URL = "https://api.trello.com/1"


# Helper function to build auth params
def get_auth_params(context: ExecutionContext) -> Dict[str, str]:
    """Get authentication parameters from context credentials."""
    credentials = context.auth.get("credentials", {})
    return {
        "key": credentials.get("api_key"),
        "token": credentials.get("token")
    }


# Helper function to merge params with auth
def merge_params(params: Dict[str, Any], auth_params: Dict[str, str]) -> Dict[str, Any]:
    """Merge request params with auth params."""
    merged = {**params}
    merged.update(auth_params)
    return merged


# ---- Member Handlers ----

@trello.action("get_current_member")
class GetCurrentMemberAction(ActionHandler):
    """Get information about the authenticated member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/members/me",
                method="GET",
                params=auth_params
            )

            return ActionResult(
                data={"member": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"member": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Board Handlers ----

@trello.action("create_board")
class CreateBoardAction(ActionHandler):
    """Create a new board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {"name": inputs['name']}

            # Add optional fields
            if 'desc' in inputs and inputs['desc']:
                params['desc'] = inputs['desc']
            if 'defaultLists' in inputs and inputs['defaultLists'] is not None:
                params['defaultLists'] = str(inputs['defaultLists']).lower()
            if 'prefs_permissionLevel' in inputs and inputs['prefs_permissionLevel']:
                params['prefs_permissionLevel'] = inputs['prefs_permissionLevel']
            if 'prefs_background' in inputs and inputs['prefs_background']:
                params['prefs_background'] = inputs['prefs_background']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"board": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"board": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("get_board")
class GetBoardAction(ActionHandler):
    """Get details of a specific board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs['board_id']
            auth_params = get_auth_params(context)
            params = {}

            if 'fields' in inputs and inputs['fields']:
                params['fields'] = inputs['fields']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}",
                method="GET",
                params=merged_params
            )

            return ActionResult(
                data={"board": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"board": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("update_board")
class UpdateBoardAction(ActionHandler):
    """Update an existing board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs['board_id']
            auth_params = get_auth_params(context)
            params = {}

            # Add only provided fields
            if 'name' in inputs and inputs['name']:
                params['name'] = inputs['name']
            if 'desc' in inputs and inputs['desc']:
                params['desc'] = inputs['desc']
            if 'closed' in inputs and inputs['closed'] is not None:
                params['closed'] = str(inputs['closed']).lower()
            if 'prefs_permissionLevel' in inputs and inputs['prefs_permissionLevel']:
                params['prefs/permissionLevel'] = inputs['prefs_permissionLevel']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}",
                method="PUT",
                params=merged_params
            )

            return ActionResult(
                data={"board": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"board": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("list_boards")
class ListBoardsAction(ActionHandler):
    """List all boards for the authenticated member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {}

            if 'filter' in inputs and inputs['filter']:
                params['filter'] = inputs['filter']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/members/me/boards",
                method="GET",
                params=merged_params
            )

            # Response is already an array
            boards = response if isinstance(response, list) else []
            return ActionResult(
                data={"boards": boards, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"boards": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- List Handlers ----

@trello.action("create_list")
class CreateListAction(ActionHandler):
    """Create a new list on a board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {
                "name": inputs['name'],
                "idBoard": inputs['board_id']
            }

            if 'pos' in inputs and inputs['pos']:
                params['pos'] = inputs['pos']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/lists",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("get_list")
class GetListAction(ActionHandler):
    """Get details of a specific list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']
            auth_params = get_auth_params(context)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/lists/{list_id}",
                method="GET",
                params=auth_params
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("update_list")
class UpdateListAction(ActionHandler):
    """Update a list's properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']
            auth_params = get_auth_params(context)
            params = {}

            if 'name' in inputs and inputs['name']:
                params['name'] = inputs['name']
            if 'closed' in inputs and inputs['closed'] is not None:
                params['closed'] = str(inputs['closed']).lower()
            if 'pos' in inputs and inputs['pos']:
                params['pos'] = inputs['pos']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/lists/{list_id}",
                method="PUT",
                params=merged_params
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("list_lists")
class ListListsAction(ActionHandler):
    """List all lists on a board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            board_id = inputs['board_id']
            auth_params = get_auth_params(context)
            params = {}

            if 'filter' in inputs and inputs['filter']:
                params['filter'] = inputs['filter']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists",
                method="GET",
                params=merged_params
            )

            lists = response if isinstance(response, list) else []
            return ActionResult(
                data={"lists": lists, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"lists": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Card Handlers ----

@trello.action("create_card")
class CreateCardAction(ActionHandler):
    """Create a new card on a list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {
                "name": inputs['name'],
                "idList": inputs['list_id']
            }

            # Add optional fields
            if 'desc' in inputs and inputs['desc']:
                params['desc'] = inputs['desc']
            if 'pos' in inputs and inputs['pos']:
                params['pos'] = inputs['pos']
            if 'due' in inputs and inputs['due']:
                params['due'] = inputs['due']
            if 'idMembers' in inputs and inputs['idMembers']:
                params['idMembers'] = ','.join(inputs['idMembers'])
            if 'idLabels' in inputs and inputs['idLabels']:
                params['idLabels'] = ','.join(inputs['idLabels'])

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"card": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"card": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("get_card")
class GetCardAction(ActionHandler):
    """Get details of a specific card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs['card_id']
            auth_params = get_auth_params(context)
            params = {}

            if 'fields' in inputs and inputs['fields']:
                params['fields'] = inputs['fields']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}",
                method="GET",
                params=merged_params
            )

            return ActionResult(
                data={"card": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"card": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("update_card")
class UpdateCardAction(ActionHandler):
    """Update an existing card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs['card_id']
            auth_params = get_auth_params(context)
            params = {}

            # Add only provided fields
            if 'name' in inputs and inputs['name']:
                params['name'] = inputs['name']
            if 'desc' in inputs and inputs['desc']:
                params['desc'] = inputs['desc']
            if 'closed' in inputs and inputs['closed'] is not None:
                params['closed'] = str(inputs['closed']).lower()
            if 'idList' in inputs and inputs['idList']:
                params['idList'] = inputs['idList']
            if 'due' in inputs and inputs['due']:
                params['due'] = inputs['due']
            if 'dueComplete' in inputs and inputs['dueComplete'] is not None:
                params['dueComplete'] = str(inputs['dueComplete']).lower()
            if 'idMembers' in inputs and inputs['idMembers']:
                params['idMembers'] = ','.join(inputs['idMembers'])

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}",
                method="PUT",
                params=merged_params
            )

            return ActionResult(
                data={"card": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"card": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("delete_card")
class DeleteCardAction(ActionHandler):
    """Delete a card permanently."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs['card_id']
            auth_params = get_auth_params(context)

            await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}",
                method="DELETE",
                params=auth_params
            )

            return ActionResult(
                data={"result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("list_cards")
class ListCardsAction(ActionHandler):
    """List all cards on a list or board."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {}

            if 'filter' in inputs and inputs['filter']:
                params['filter'] = inputs['filter']

            merged_params = merge_params(params, auth_params)

            # Determine endpoint based on input
            if 'list_id' in inputs and inputs['list_id']:
                url = f"{TRELLO_API_BASE_URL}/lists/{inputs['list_id']}/cards"
            elif 'board_id' in inputs and inputs['board_id']:
                url = f"{TRELLO_API_BASE_URL}/boards/{inputs['board_id']}/cards"
            else:
                return ActionResult(
                    data={"cards": [], "result": False, "error": "Either list_id or board_id is required"},
                    cost_usd=0.0
                )

            response = await context.fetch(
                url,
                method="GET",
                params=merged_params
            )

            cards = response if isinstance(response, list) else []
            return ActionResult(
                data={"cards": cards, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"cards": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Checklist Handlers ----

@trello.action("create_checklist")
class CreateChecklistAction(ActionHandler):
    """Create a new checklist on a card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            auth_params = get_auth_params(context)
            params = {
                "idCard": inputs['card_id'],
                "name": inputs['name']
            }

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/checklists",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"checklist": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"checklist": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@trello.action("add_checklist_item")
class AddChecklistItemAction(ActionHandler):
    """Add a new item to a checklist."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            checklist_id = inputs['checklist_id']
            auth_params = get_auth_params(context)
            params = {
                "name": inputs['name']
            }

            if 'checked' in inputs and inputs['checked'] is not None:
                params['checked'] = str(inputs['checked']).lower()
            if 'pos' in inputs and inputs['pos']:
                params['pos'] = inputs['pos']

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/checklists/{checklist_id}/checkItems",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"checkItem": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"checkItem": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Comment Handler ----

@trello.action("add_comment")
class AddCommentAction(ActionHandler):
    """Add a comment to a card."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = inputs['card_id']
            auth_params = get_auth_params(context)
            params = {
                "text": inputs['text']
            }

            merged_params = merge_params(params, auth_params)

            response = await context.fetch(
                f"{TRELLO_API_BASE_URL}/cards/{card_id}/actions/comments",
                method="POST",
                params=merged_params
            )

            return ActionResult(
                data={"comment": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comment": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )

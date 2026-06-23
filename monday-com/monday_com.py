from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any

monday_com = Integration.load()


def build_headers(context: ExecutionContext):
    access_token = context.auth["credentials"]["access_token"]
    return {"Authorization": access_token, "Content-Type": "application/json", "API-Version": "2024-10"}


async def execute_graphql_query(query: str, variables: Dict[str, Any], context: ExecutionContext):
    url = "https://api.monday.com/v2"
    headers = build_headers(context)
    payload = {"query": query, "variables": variables}
    fetch_response = await context.fetch(url, method="POST", json=payload, headers=headers)
    if fetch_response.data is None:
        raise ValueError("Empty response body from Monday.com API")
    return fetch_response.data


@monday_com.action("get_boards")
class GetBoards(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve boards from Monday.com workspace."""
        try:
            query = """
                query GetBoards($limit: Int, $page: Int, $board_kind: BoardKind) {
                    boards(limit: $limit, page: $page, board_kind: $board_kind) {
                        id
                        name
                        description
                        state
                        board_kind
                        workspace_id
                        columns {
                            id
                            title
                            type
                        }
                        groups {
                            id
                            title
                        }
                    }
                }
            """

            variables = {
                "limit": inputs.get("limit", 25),
                "page": inputs.get("page", 1),
                "board_kind": inputs.get("board_kind"),
            }

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            boards = result.get("data", {}).get("boards", [])

            return ActionResult(data={"boards": boards, "board_count": len(boards)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@monday_com.action("get_items")
class GetItems(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve items from a Monday.com board."""
        try:
            query = """
                query GetItems($board_id: [ID!]!, $limit: Int, $cursor: String) {
                    boards(ids: $board_id) {
                        items_page(limit: $limit, cursor: $cursor) {
                            cursor
                            items {
                                id
                                name
                                state
                                created_at
                                updated_at
                                creator {
                                    id
                                    name
                                }
                                group {
                                    id
                                    title
                                }
                                column_values {
                                    id
                                    text
                                    value
                                    type
                                }
                            }
                        }
                    }
                }
            """

            variables = {
                "board_id": [str(inputs["board_id"])],
                "limit": inputs.get("limit", 25),
                "cursor": inputs.get("cursor"),
            }

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            boards = result.get("data", {}).get("boards", [])
            items = []
            cursor = None
            if boards:
                items_page = boards[0].get("items_page", {})
                items = items_page.get("items", [])
                cursor = items_page.get("cursor")

            return ActionResult(data={"items": items, "item_count": len(items), "cursor": cursor}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@monday_com.action("create_item")
class CreateItem(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Create a new item on a Monday.com board."""
        try:
            query = """
                mutation CreateItem($board_id: ID!, $group_id: String, $item_name: String!, $column_values: JSON) {
                    create_item(
                        board_id: $board_id,
                        group_id: $group_id,
                        item_name: $item_name,
                        column_values: $column_values
                    ) {
                        id
                        name
                        state
                        created_at
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            """

            variables = {
                "board_id": str(inputs["board_id"]),
                "group_id": inputs.get("group_id"),
                "item_name": inputs["item_name"],
                "column_values": inputs.get("column_values"),
            }

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            item = result.get("data", {}).get("create_item")

            return ActionResult(data={"item": item}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@monday_com.action("update_item")
class UpdateItem(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Update an existing item on a Monday.com board."""
        try:
            query = """
                mutation UpdateItem($board_id: ID!, $item_id: ID!, $column_values: JSON!) {
                    change_multiple_column_values(
                        board_id: $board_id,
                        item_id: $item_id,
                        column_values: $column_values
                    ) {
                        id
                        name
                        updated_at
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            """

            variables = {
                "board_id": str(inputs["board_id"]),
                "item_id": str(inputs["item_id"]),
                "column_values": inputs["column_values"],
            }

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            item = result.get("data", {}).get("change_multiple_column_values")

            return ActionResult(data={"item": item}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@monday_com.action("create_update")
class CreateUpdate(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Create an update (comment) on a Monday.com item."""
        try:
            query = """
                mutation CreateUpdate($item_id: ID!, $body: String!) {
                    create_update(
                        item_id: $item_id,
                        body: $body
                    ) {
                        id
                        body
                        created_at
                        creator {
                            id
                            name
                        }
                    }
                }
            """

            variables = {"item_id": str(inputs["item_id"]), "body": inputs["body"]}

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            update = result.get("data", {}).get("create_update")

            return ActionResult(data={"update": update}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@monday_com.action("get_users")
class GetUsers(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve users from Monday.com workspace."""
        try:
            query = """
                query GetUsers($limit: Int, $page: Int) {
                    users(limit: $limit, page: $page) {
                        id
                        name
                        email
                        title
                        photo_thumb
                        is_admin
                        is_guest
                        enabled
                        created_at
                        teams {
                            id
                            name
                        }
                    }
                }
            """

            variables = {"limit": inputs.get("limit", 25), "page": inputs.get("page", 1)}

            result = await execute_graphql_query(query, variables, context)

            if "errors" in result:
                return ActionError(message=str(result["errors"]))

            users = result.get("data", {}).get("users", [])

            return ActionResult(data={"users": users, "user_count": len(users)}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

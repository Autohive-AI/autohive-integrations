from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, PollingTriggerHandler, ActionResult
)
from typing import Dict, Any, List, Optional

# API Version constant for Notion API
NOTION_API_VERSION = "2025-09-03"

# Create the integration using the config.json
notion = Integration.load()

# ---- Action Handlers ----

@notion.action("search_notion")
class NotionSearchHandler(ActionHandler):
    """Handler for searching pages and databases in Notion workspace"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Execute a search query against the Notion API

        Args:
            inputs: Dictionary containing 'query' and optional 'filter', 'sort', 'page_size', 'start_cursor'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing search results from Notion API
        """
        # Prepare the search request body
        search_body = {
            "query": inputs["query"]
        }

        # Add optional filter if provided
        if "filter" in inputs and inputs["filter"]:
            search_body["filter"] = inputs["filter"]

        # Add optional sort if provided
        if "sort" in inputs and inputs["sort"]:
            search_body["sort"] = inputs["sort"]

        # Add pagination parameters if provided
        if "page_size" in inputs and inputs["page_size"]:
            search_body["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            search_body["start_cursor"] = inputs["start_cursor"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the search request to Notion API
        try:
            response = await context.fetch(
                url="https://api.notion.com/v1/search",
                method="POST",
                headers=headers,
                json=search_body
            )

            return ActionResult(data={
                "object": response.get("object", "list"),
                "results": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
                "type": response.get("type")
            })

        except Exception as e:
            return ActionResult(data={
                "object": "list",
                "error": str(e),
                "results": [],
                "has_more": False
            })


@notion.action("get_notion_page")
class NotionGetPageHandler(ActionHandler):
    """Handler for retrieving a specific page from Notion"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Retrieve a specific page by its ID

        Args:
            inputs: Dictionary containing 'page_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing page data from Notion API
        """
        page_id = inputs["page_id"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION
        }

        # Make the get page request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/pages/{page_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(data={"page": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "page": None})


@notion.action("create_notion_page")
class NotionCreatePageHandler(ActionHandler):
    """Handler for creating new pages in Notion"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new page in Notion

        Args:
            inputs: Dictionary containing 'parent' and 'properties'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created page data from Notion API
        """
        # Prepare the create page request body
        create_body = {
            "parent": inputs["parent"],
            "properties": inputs["properties"]
        }

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the create page request to Notion API
        try:
            response = await context.fetch(
                url="https://api.notion.com/v1/pages",
                method="POST",
                headers=headers,
                json=create_body
            )

            return ActionResult(data={"page": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "page": None})


@notion.action("create_notion_comment")
class NotionCreateCommentHandler(ActionHandler):
    """Handler for creating comments on Notion pages"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a comment on a Notion page

        Args:
            inputs: Dictionary containing 'parent' and 'rich_text'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created comment data from Notion API
        """
        # Prepare the create comment request body
        comment_body = {
            "parent": inputs["parent"],
            "rich_text": inputs["rich_text"]
        }

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the create comment request to Notion API
        try:
            response = await context.fetch(
                url="https://api.notion.com/v1/comments",
                method="POST",
                headers=headers,
                json=comment_body
            )

            return ActionResult(data={"comment": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "comment": None})


@notion.action("get_notion_comments")
class NotionGetCommentsHandler(ActionHandler):
    """Handler for retrieving comments from a Notion page or block"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        block_id = inputs["block_id"]
        include_child_blocks_with_comments = inputs.get("include_child_blocks_with_comments", False)

        params = {"block_id": block_id}

        if "page_size" in inputs and inputs["page_size"]:
            params["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            params["start_cursor"] = inputs["start_cursor"]

        headers = {"Notion-Version": NOTION_API_VERSION}

        try:
            response = await context.fetch(
                url="https://api.notion.com/v1/comments",
                method="GET",
                headers=headers,
                params=params
            )

            result = {
                "comments": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor")
            }

            if include_child_blocks_with_comments:
                blocks_with_comments = []

                blocks_response = await context.fetch(
                    url=f"https://api.notion.com/v1/blocks/{block_id}/children",
                    method="GET",
                    headers=headers
                )

                for block in blocks_response.get("results", []):
                    child_block_id = block.get("id")
                    if child_block_id:
                        comments_response = await context.fetch(
                            url="https://api.notion.com/v1/comments",
                            method="GET",
                            headers=headers,
                            params={"block_id": child_block_id, "page_size": 1}
                        )
                        if comments_response.get("results"):
                            blocks_with_comments.append({
                                "block_id": child_block_id,
                                "block_type": block.get("type"),
                                "has_comments": True
                            })

                result["child_blocks_with_comments"] = blocks_with_comments

            return ActionResult(data=result)
        except Exception as e:
            return ActionResult(data={"error": str(e), "comments": []})


@notion.action("list_data_sources")
class NotionListDataSourcesHandler(ActionHandler):
    """Handler for listing data sources within a database container"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List data sources within a database container

        Args:
            inputs: Dictionary containing 'database_id' and optional 'page_size', 'start_cursor'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of data sources from Notion API
        """
        database_id = inputs["database_id"]

        params = {}

        if "page_size" in inputs and inputs["page_size"]:
            params["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            params["start_cursor"] = inputs["start_cursor"]

        headers = {"Notion-Version": NOTION_API_VERSION}

        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/databases/{database_id}/data_sources",
                method="GET",
                headers=headers,
                params=params
            )
            return ActionResult(data={
                "data_sources": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor")
            })
        except Exception as e:
            return ActionResult(data={"error": str(e), "data_sources": []})


@notion.action("get_data_source")
class NotionGetDataSourceHandler(ActionHandler):
    """Handler for retrieving a specific data source's schema"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Retrieve a specific data source's schema

        Args:
            inputs: Dictionary containing 'data_source_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing data source schema from Notion API
        """
        data_source_id = inputs["data_source_id"]

        headers = {"Notion-Version": NOTION_API_VERSION}

        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/data_sources/{data_source_id}",
                method="GET",
                headers=headers
            )
            return ActionResult(data={"data_source": response})
        except Exception as e:
            return ActionResult(data={"error": str(e), "data_source": None})


# ---- Phase 1 Enhancement Handlers ----

@notion.action("query_notion_data_source")
class NotionQueryDataSourceHandler(ActionHandler):
    """Handler for querying data sources with filtering, sorting, and pagination"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Query a data source with advanced filtering and sorting

        Args:
            inputs: Dictionary containing 'data_source_id' and optional 'filter', 'sorts', 'page_size', 'start_cursor'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing data source query results from Notion API
        """
        data_source_id = inputs["data_source_id"]

        # Prepare the query request body
        query_body = {}

        # Add optional filter if provided
        if "filter" in inputs and inputs["filter"]:
            query_body["filter"] = inputs["filter"]

        # Add optional sorts if provided
        if "sorts" in inputs and inputs["sorts"]:
            query_body["sorts"] = inputs["sorts"]

        # Add pagination parameters if provided
        if "page_size" in inputs and inputs["page_size"]:
            query_body["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            query_body["start_cursor"] = inputs["start_cursor"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the query request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/data_sources/{data_source_id}/query",
                method="POST",
                headers=headers,
                json=query_body
            )

            return ActionResult(data={
                "results": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
                "type": response.get("type")
            })

        except Exception as e:
            return ActionResult(data={"error": str(e), "results": []})


@notion.action("get_notion_block_children")
class NotionGetBlockChildrenHandler(ActionHandler):
    """Handler for retrieving child blocks of a page or block"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Retrieve child blocks of a parent block or page

        Args:
            inputs: Dictionary containing 'block_id' and optional 'page_size', 'start_cursor'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing child blocks from Notion API
        """
        block_id = inputs["block_id"]

        # Prepare query parameters
        params = {}

        if "page_size" in inputs and inputs["page_size"]:
            params["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            params["start_cursor"] = inputs["start_cursor"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION
        }

        # Make the get block children request to Notion API
        try:
            url = f"https://api.notion.com/v1/blocks/{block_id}/children"

            response = await context.fetch(
                url=url,
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(data={
                "blocks": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
                "type": response.get("type")
            })

        except Exception as e:
            return ActionResult(data={"error": str(e), "blocks": []})


@notion.action("append_notion_block_children")
class NotionAppendBlockChildrenHandler(ActionHandler):
    """Handler for appending child blocks to a page or block"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Append child blocks to a parent block or page

        Args:
            inputs: Dictionary containing 'block_id', 'children', and optional 'after'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created blocks from Notion API
        """
        block_id = inputs["block_id"]

        # Prepare the append request body
        append_body = {
            "children": inputs["children"]
        }

        # Add optional after parameter if provided
        if "after" in inputs and inputs["after"]:
            append_body["after"] = inputs["after"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the append block children request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/blocks/{block_id}/children",
                method="PATCH",
                headers=headers,
                json=append_body
            )

            return ActionResult(data={
                "blocks": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
                "type": response.get("type")
            })

        except Exception as e:
            return ActionResult(data={"error": str(e), "blocks": []})


@notion.action("get_notion_page_property")
class NotionGetPagePropertyHandler(ActionHandler):
    """Handler for retrieving specific page property values"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Retrieve a specific property value from a page

        Args:
            inputs: Dictionary containing 'page_id', 'property_id' and optional 'page_size', 'start_cursor'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing property value from Notion API
        """
        page_id = inputs["page_id"]
        property_id = inputs["property_id"]

        # Prepare query parameters
        params = {}

        if "page_size" in inputs and inputs["page_size"]:
            params["page_size"] = inputs["page_size"]

        if "start_cursor" in inputs and inputs["start_cursor"]:
            params["start_cursor"] = inputs["start_cursor"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION
        }

        # Make the get page property request to Notion API
        try:
            url = f"https://api.notion.com/v1/pages/{page_id}/properties/{property_id}"

            response = await context.fetch(
                url=url,
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(data={"property": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "property": None})


@notion.action("update_notion_block")
class NotionUpdateBlockHandler(ActionHandler):
    """Handler for updating existing blocks"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update the content of an existing block

        Args:
            inputs: Dictionary containing 'block_id' and block content (paragraph, heading_1, etc.)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated block from Notion API
        """
        block_id = inputs["block_id"]

        # Valid block types that can be updated
        valid_block_types = {
            "paragraph", "heading_1", "heading_2", "heading_3",
            "bulleted_list_item", "numbered_list_item", "to_do",
            "code", "quote", "callout", "toggle", "embed", "bookmark",
            "image", "video", "pdf", "file", "audio", "equation",
            "divider", "breadcrumb", "table_of_contents", "link_to_page",
            "table_row", "table", "column", "synced_block", "template"
        }

        # Prepare the update request body (only include valid block type fields, exclude internal fields)
        update_body = {key: value for key, value in inputs.items()
                      if key in valid_block_types and value is not None and not key.startswith("NOTION_")}

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the update block request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/blocks/{block_id}",
                method="PATCH",
                headers=headers,
                json=update_body
            )

            return ActionResult(data={"block": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "block": None})


@notion.action("delete_notion_block")
class NotionDeleteBlockHandler(ActionHandler):
    """Handler for deleting (archiving) blocks"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete (archive) a block by moving it to trash

        Args:
            inputs: Dictionary containing 'block_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing deleted block from Notion API
        """
        block_id = inputs["block_id"]

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION
        }

        # Make the delete block request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/blocks/{block_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(data={"block": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "block": None})


@notion.action("update_notion_page")
class NotionUpdatePageHandler(ActionHandler):
    """Handler for updating page properties"""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update properties of a page (for database pages)

        Args:
            inputs: Dictionary containing 'page_id' and optional 'properties', 'icon', 'cover', 'archived'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated page from Notion API
        """
        page_id = inputs["page_id"]

        # Valid page update fields
        valid_page_fields = {
            "properties", "icon", "cover", "archived"
        }

        # Prepare the update request body (only include valid page fields, exclude internal fields)
        update_body = {key: value for key, value in inputs.items()
                      if key in valid_page_fields and value is not None and not key.startswith("NOTION_")}

        # Prepare headers for Notion API
        headers = {
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

        # Make the update page request to Notion API
        try:
            response = await context.fetch(
                url=f"https://api.notion.com/v1/pages/{page_id}",
                method="PATCH",
                headers=headers,
                json=update_body
            )

            return ActionResult(data={"page": response})

        except Exception as e:
            return ActionResult(data={"error": str(e), "page": None})

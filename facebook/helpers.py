"""
Facebook integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ExecutionContext

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def extract_page_id(compound_id: str) -> str:
    """
    Extract the page ID from a compound ID (e.g., post_id or comment_id).
    
    Facebook compound IDs are formatted as "PAGEID_ITEMID". This function
    extracts the page ID portion. If no underscore is present, returns
    the original ID (assumes it's already a page ID).
    
    Args:
        compound_id: A Facebook ID that may be compound (PAGEID_ITEMID) or simple
        
    Returns:
        The page ID portion of the compound ID
    """
    if "_" in compound_id:
        return compound_id.split("_")[0]
    return compound_id


async def get_page_access_token(context: ExecutionContext, page_id: str) -> str:
    """
    Retrieve the Page Access Token for a specific Facebook Page ID.
    
    This requires the user access token in `context` to include the necessary
    page permissions (e.g. pages_show_list, pages_read_engagement, 
    pages_manage_metadata, etc.).
    
    Args:
        context: The execution context with authentication
        page_id: The Facebook Page ID
        
    Returns:
        The page access token string
        
    Raises:
        Exception: If the page is not accessible or user lacks permission
    """
    response = await context.fetch(
        f"{GRAPH_API_BASE}/{page_id}",
        method="GET",
        params={"fields": "access_token"}
    )

    token = response.get("access_token")
    if not token:
        raise Exception(
            f"Failed to retrieve page access token for Page '{page_id}'. "
            "Ensure the user has granted required permissions."
        )

    return token

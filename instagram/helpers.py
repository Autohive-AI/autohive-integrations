"""
Instagram integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ExecutionContext

GRAPH_API_VERSION = "v24.0"
INSTAGRAM_GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"


async def get_instagram_account_id(context: ExecutionContext) -> str:
    """
    Retrieve the Instagram Business/Creator account ID for the authenticated user.
    
    This fetches the Instagram account ID connected to the user's Facebook Page.
    For Instagram Login flow, this returns the /me endpoint result.
    
    Args:
        context: The execution context with authentication
        
    Returns:
        The Instagram account ID string
        
    Raises:
        Exception: If no Instagram account is connected or user lacks permission
    """
    response = await context.fetch(
        f"{INSTAGRAM_GRAPH_API_BASE}/me",
        method="GET",
        params={"fields": "id,username"}
    )
    
    account_id = response.get("id")
    if not account_id:
        raise Exception(
            "Failed to retrieve Instagram account ID. "
            "Ensure the user has granted required permissions and has an Instagram Business/Creator account."
        )
    
    return account_id


async def wait_for_media_container(context: ExecutionContext, container_id: str, max_attempts: int = 30, delay: float = 2.0) -> dict:
    """
    Poll the container status until it's ready to publish or fails.
    
    Instagram requires containers to be processed before publishing. This function
    polls the status endpoint until the container is finished processing.
    
    Args:
        context: The execution context with authentication
        container_id: The media container ID to check
        max_attempts: Maximum number of polling attempts (default 30)
        delay: Seconds between polling attempts (default 2.0)
        
    Returns:
        The final container status response
        
    Raises:
        Exception: If container processing fails or times out
    """
    import asyncio
    
    for attempt in range(max_attempts):
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{container_id}",
            method="GET",
            params={"fields": "status_code,status"}
        )
        
        status_code = response.get("status_code", "").upper()
        
        if status_code == "FINISHED":
            return response
        elif status_code == "ERROR":
            error_msg = response.get("status", "Unknown error during media processing")
            raise Exception(f"Media container processing failed: {error_msg}")
        elif status_code in ("EXPIRED", "FAILED"):
            raise Exception(f"Media container {status_code.lower()}: {response.get('status', 'Unknown error')}")
        
        await asyncio.sleep(delay)
    
    raise Exception(f"Media container processing timed out after {max_attempts * delay} seconds")

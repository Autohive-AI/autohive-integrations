from autohive_integrations_sdk import ExecutionContext

GRAPH_API_VERSION = "v24.0"
INSTAGRAM_GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"


async def get_instagram_account_id(context: ExecutionContext) -> str:
    response = await context.fetch(
        f"{INSTAGRAM_GRAPH_API_BASE}/me", method="GET", params={"fields": "id,username"}
    )
    account_id = response.data.get("id")
    if not account_id:
        raise Exception(
            "Failed to retrieve Instagram account ID. "
            "Ensure the user has granted required permissions and has an Instagram Business/Creator account."
        )
    return account_id


async def wait_for_media_container(
    context: ExecutionContext, container_id: str, max_attempts: int = 30, delay: float = 2.0
) -> dict:
    import asyncio

    for _ in range(max_attempts):
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{container_id}",
            method="GET",
            params={"fields": "status_code,status"},
        )
        data = response.data
        status_code = data.get("status_code", "").upper()
        if status_code == "FINISHED":
            return data
        elif status_code == "ERROR":
            raise Exception(f"Media container processing failed: {data.get('status', 'Unknown error')}")
        elif status_code in ("EXPIRED", "FAILED"):
            raise Exception(f"Media container {status_code.lower()}: {data.get('status', 'Unknown error')}")
        await asyncio.sleep(delay)

    raise Exception(f"Media container processing timed out after {max_attempts * delay} seconds")

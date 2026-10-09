import asyncio

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from instagram import instagram
from helpers import (
    INSTAGRAM_GRAPH_API_BASE,
    get_instagram_account_id,
    wait_for_media_container,
)


def _build_media_response(media: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": media.get("id", ""),
        "media_type": media.get("media_type", ""),
        "media_product_type": media.get("media_product_type", ""),
        "caption": media.get("caption", ""),
        "permalink": media.get("permalink", ""),
        "timestamp": media.get("timestamp", ""),
        "thumbnail_url": media.get("thumbnail_url", ""),
        "media_url": media.get("media_url", ""),
        "like_count": media.get("like_count", 0),
        "comments_count": media.get("comments_count", 0),
    }


ASYNC_POLL_ATTEMPTS = 6
ASYNC_POLL_DELAY_SECONDS = 2
ASYNC_MAX_COMPLETION_CALLS = 12


def _async_post_result(
    status: str,
    publish_state: Dict[str, Any],
    *,
    message: str,
    media_id: str = "",
    permalink: str = "",
) -> ActionResult:
    is_processing = status == "PROCESSING"
    return ActionResult(
        data={
            "status": status,
            "publish_state": publish_state,
            "retry_after_seconds": ASYNC_POLL_DELAY_SECONDS if is_processing else 0,
            "next_action": "complete_post" if is_processing else "",
            "message": message,
            "media_id": media_id,
            "permalink": permalink,
        }
    )


async def _get_container_status(context: ExecutionContext, container_id: str) -> Dict[str, Any]:
    response = await context.fetch(
        f"{INSTAGRAM_GRAPH_API_BASE}/{container_id}",
        method="GET",
        params={"fields": "status_code,status"},
    )
    return response.data


async def _poll_container_ids(
    context: ExecutionContext,
    container_ids: list[str],
) -> tuple[str, str]:
    for poll_attempt in range(ASYNC_POLL_ATTEMPTS):
        statuses = await asyncio.gather(
            *[_get_container_status(context, container_id) for container_id in container_ids]
        )
        all_ready = True
        any_published = False
        for data in statuses:
            status_code = data.get("status_code", "").upper()
            if status_code in {"ERROR", "EXPIRED", "FAILED"}:
                detail = data.get("status", "Unknown error")
                return "FAILED", f"Media container {status_code.lower()}: {detail}"
            if status_code == "PUBLISHED":
                any_published = True
            elif status_code != "FINISHED":
                all_ready = False

        if all_ready:
            return ("PUBLISHED" if any_published else "FINISHED"), ""
        if poll_attempt < ASYNC_POLL_ATTEMPTS - 1:
            await asyncio.sleep(ASYNC_POLL_DELAY_SECONDS)

    return "PROCESSING", ""


@instagram.action("get_posts")
class GetPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        media_id = inputs.get("media_id")
        limit = min(inputs.get("limit", 25), 100)
        after_cursor = inputs.get("after_cursor")

        fields = ",".join(
            [
                "id",
                "media_type",
                "media_product_type",
                "caption",
                "permalink",
                "timestamp",
                "thumbnail_url",
                "media_url",
                "like_count",
                "comments_count",
            ]
        )

        if media_id:
            response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{media_id}",
                method="GET",
                params={"fields": fields},
            )
            media_list = [_build_media_response(response.data)]
            next_cursor = None
        else:
            account_id = await get_instagram_account_id(context)
            params = {"fields": fields, "limit": limit}
            if after_cursor:
                params["after"] = after_cursor
            response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="GET",
                params=params,
            )
            data = response.data
            media_list = [_build_media_response(m) for m in data.get("data", [])]
            paging = data.get("paging", {})
            cursors = paging.get("cursors", {})
            next_cursor = cursors.get("after") if paging.get("next") else None

        return ActionResult(data={"media": media_list, "next_cursor": next_cursor})


@instagram.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        media_type = inputs["media_type"].upper()
        media_url = inputs.get("media_url")
        caption = inputs.get("caption", "")
        children = inputs.get("children", [])
        alt_text = inputs.get("alt_text")

        account_id = await get_instagram_account_id(context)

        if media_type == "CAROUSEL":
            if not children or len(children) < 2:
                raise Exception("Carousel requires at least 2 media items in 'children' array")
            if len(children) > 10:
                raise Exception("Carousel supports maximum 10 media items")

            child_container_ids = []
            for index, child in enumerate(children):
                child_url = child.get("media_url") if isinstance(child, dict) else child
                child_type = child.get("media_type", "IMAGE").upper() if isinstance(child, dict) else "IMAGE"
                if not child_url:
                    raise Exception(f"Carousel item {index + 1} requires a media_url")
                if child_type not in {"IMAGE", "VIDEO"}:
                    raise Exception(f"Carousel item {index + 1} media_type must be IMAGE or VIDEO")

                child_data = {"is_carousel_item": "true"}
                if child_type == "VIDEO":
                    child_data["media_type"] = "VIDEO"
                    child_data["video_url"] = child_url
                else:
                    child_data["image_url"] = child_url
                r = await context.fetch(
                    f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                    method="POST",
                    data=child_data,
                )
                child_container_ids.append(r.data.get("id"))

            for cid in child_container_ids:
                await wait_for_media_container(context, cid)

            r = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="POST",
                data={
                    "media_type": "CAROUSEL",
                    "caption": caption,
                    "children": ",".join(child_container_ids),
                },
            )
            container_id = r.data.get("id")

        elif media_type in {"VIDEO", "REELS"}:
            if not media_url:
                raise Exception(f"media_url is required for {media_type}")
            r = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="POST",
                data={
                    "media_type": "REELS",
                    "video_url": media_url,
                    "caption": caption,
                },
            )
            container_id = r.data.get("id")

        else:
            if not media_url:
                raise Exception("media_url is required for IMAGE")
            post_data = {"image_url": media_url, "caption": caption}
            if alt_text:
                post_data["alt_text"] = alt_text
            r = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="POST",
                data=post_data,
            )
            container_id = r.data.get("id")

        await wait_for_media_container(context, container_id)

        publish_r = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media_publish",
            method="POST",
            data={"creation_id": container_id},
        )
        media_id = publish_r.data.get("id", "")

        details_r = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{media_id}",
            method="GET",
            params={"fields": "permalink"},
        )
        return ActionResult(
            data={
                "media_id": media_id,
                "permalink": details_r.data.get("permalink", ""),
            }
        )


@instagram.action("start_post")
class StartPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        media_type = inputs["media_type"].upper()
        media_url = inputs.get("media_url")
        caption = inputs.get("caption", "")
        children = inputs.get("children", [])
        alt_text = inputs.get("alt_text")

        if media_type == "CAROUSEL":
            if not children or len(children) < 2:
                return ActionError(message="Carousel requires at least 2 media items in 'children' array")
            if len(children) > 10:
                return ActionError(message="Carousel supports maximum 10 media items")
        elif not media_url:
            return ActionError(message=f"media_url is required for {media_type}")

        try:
            account_id = await get_instagram_account_id(context)
        except Exception as exc:
            return ActionError(message=str(exc))

        if media_type == "CAROUSEL":

            async def create_child(child: Dict[str, Any]) -> str:
                child_type = child["media_type"].upper()
                child_data = {"is_carousel_item": "true"}
                if child_type == "VIDEO":
                    child_data["media_type"] = "VIDEO"
                    child_data["video_url"] = child["media_url"]
                else:
                    child_data["image_url"] = child["media_url"]
                response = await context.fetch(
                    f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                    method="POST",
                    data=child_data,
                )
                container_id = response.data.get("id")
                if not container_id:
                    raise Exception("Instagram did not return a carousel child container ID")
                return container_id

            try:
                child_container_ids = await asyncio.gather(*[create_child(child) for child in children])
            except Exception as exc:
                return ActionError(message=str(exc))
            publish_state = {
                "media_type": "CAROUSEL",
                "phase": "CHILDREN",
                "container_id": "",
                "child_container_ids": child_container_ids,
                "caption": caption,
                "attempt": 0,
            }
        else:
            normalized_media_type = "REELS" if media_type in {"VIDEO", "REELS"} else "IMAGE"
            if normalized_media_type == "REELS":
                post_data = {
                    "media_type": "REELS",
                    "video_url": media_url,
                    "caption": caption,
                }
            else:
                post_data = {"image_url": media_url, "caption": caption}
                if alt_text:
                    post_data["alt_text"] = alt_text

            try:
                response = await context.fetch(
                    f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                    method="POST",
                    data=post_data,
                )
            except Exception as exc:
                return ActionError(message=str(exc))
            container_id = response.data.get("id")
            if not container_id:
                return ActionError(message="Instagram did not return a media container ID")
            publish_state = {
                "media_type": normalized_media_type,
                "phase": "MEDIA",
                "container_id": container_id,
                "child_container_ids": [],
                "caption": caption,
                "attempt": 0,
            }

        return _async_post_result(
            "PROCESSING",
            publish_state,
            message=(
                "Upload started. Call complete_post now with publish_state. "
                "Continue calling complete_post automatically while its status is PROCESSING; do not ask the user."
            ),
        )


@instagram.action("complete_post")
class CompletePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        try:
            publish_state = dict(inputs["publish_state"])
            return await self._execute(publish_state, context)
        except Exception as exc:
            return ActionError(message=str(exc))

    async def _execute(self, publish_state: Dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        publish_state["child_container_ids"] = list(publish_state.get("child_container_ids", []))
        publish_state["attempt"] = int(publish_state.get("attempt", 0)) + 1

        if publish_state["attempt"] > ASYNC_MAX_COMPLETION_CALLS:
            return ActionError(
                message="Instagram media processing did not finish after the maximum automatic completion attempts."
            )

        account_id = await get_instagram_account_id(context)
        phase = publish_state.get("phase", "")

        if phase == "CHILDREN":
            processing_status, error = await _poll_container_ids(context, publish_state["child_container_ids"])
            if processing_status == "FAILED":
                return ActionError(message=error)
            if processing_status == "PUBLISHED":
                return ActionError(message="A carousel child has already been published and cannot be reused")
            if processing_status == "PROCESSING":
                return _async_post_result(
                    "PROCESSING",
                    publish_state,
                    message=(
                        "Carousel media is still processing. Call complete_post again immediately with publish_state. "
                        "Do not ask the user to continue."
                    ),
                )

            response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="POST",
                data={
                    "media_type": "CAROUSEL",
                    "caption": publish_state.get("caption", ""),
                    "children": ",".join(publish_state["child_container_ids"]),
                },
            )
            parent_container_id = response.data.get("id")
            if not parent_container_id:
                return ActionError(message="Instagram did not return a carousel container ID")
            publish_state["container_id"] = parent_container_id
            publish_state["phase"] = "PARENT"
            return _async_post_result(
                "PROCESSING",
                publish_state,
                message=(
                    "Carousel container created. Call complete_post again immediately with publish_state. "
                    "Do not ask the user to continue."
                ),
            )

        if phase not in {"MEDIA", "PARENT"} or not publish_state.get("container_id"):
            return ActionError(message="publish_state must identify a media or parent container")

        processing_status, error = await _poll_container_ids(context, [publish_state["container_id"]])
        if processing_status == "FAILED":
            return ActionError(message=error)
        if processing_status == "PUBLISHED":
            return _async_post_result(
                "PUBLISHED",
                publish_state,
                message=(
                    "Instagram reports that this media container was already published. "
                    "The media ID and permalink were not available from the previous publish response."
                ),
            )
        if processing_status == "PROCESSING":
            return _async_post_result(
                "PROCESSING",
                publish_state,
                message=(
                    "Instagram media is still processing. Call complete_post again immediately with publish_state. "
                    "Do not ask the user to continue."
                ),
            )

        publish_response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media_publish",
            method="POST",
            data={"creation_id": publish_state["container_id"]},
        )
        media_id = publish_response.data.get("id", "")
        if not media_id:
            status_data = await _get_container_status(context, publish_state["container_id"])
            if status_data.get("status_code", "").upper() == "PUBLISHED":
                return _async_post_result(
                    "PUBLISHED",
                    publish_state,
                    message=(
                        "Instagram published the post but did not return its media ID. "
                        "The permalink could not be retrieved."
                    ),
                )
            return ActionError(message="Instagram did not return a published media ID")

        permalink = ""
        message = "Instagram post published successfully."
        try:
            details_response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{media_id}",
                method="GET",
                params={"fields": "permalink"},
            )
            permalink = details_response.data.get("permalink", "")
        except Exception:
            # Publishing is irreversible. A best-effort details lookup must not
            # turn a successfully published post into a failed, unsafe-to-retry action.
            message = "Instagram post published successfully, but its permalink could not be retrieved."

        return _async_post_result(
            "PUBLISHED",
            publish_state,
            message=message,
            media_id=media_id,
            permalink=permalink,
        )


@instagram.action("create_story")
class CreateStoryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        media_type = inputs["media_type"].upper()
        media_url = inputs["media_url"]

        account_id = await get_instagram_account_id(context)
        data = {"media_type": "STORIES"}
        if media_type == "VIDEO":
            data["video_url"] = media_url
        else:
            data["image_url"] = media_url

        r = await context.fetch(f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media", method="POST", data=data)
        container_id = r.data.get("id")
        await wait_for_media_container(context, container_id)

        publish_r = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media_publish",
            method="POST",
            data={"creation_id": container_id},
        )
        return ActionResult(data={"media_id": publish_r.data.get("id", "")})

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
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
            for child in children:
                child_url = child.get("media_url") if isinstance(child, dict) else child
                child_type = child.get("media_type", "IMAGE").upper() if isinstance(child, dict) else "IMAGE"
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

        elif media_type == "REELS":
            if not media_url:
                raise Exception("media_url is required for REELS")
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

        elif media_type == "VIDEO":
            if not media_url:
                raise Exception("media_url is required for VIDEO")
            r = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/media",
                method="POST",
                data={
                    "media_type": "VIDEO",
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

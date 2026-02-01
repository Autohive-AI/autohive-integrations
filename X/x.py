import base64
import asyncio

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult,
    ConnectedAccountHandler, ConnectedAccountInfo
)
from typing import Dict, Any

# Create the integration
x = Integration.load()

# Base URL for X API v2
X_API_BASE_URL = "https://api.x.com/2"

# Media upload URL - X API v2
X_MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"


# ---- Connected Account Handler ----

@x.connected_account()
class XConnectedAccountHandler(ConnectedAccountHandler):
    """Handler to fetch X account information after OAuth connection."""

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """Fetch X user information for the connected account."""
        response = await context.fetch(
            f"{X_API_BASE_URL}/users/me",
            method="GET",
            params={"user.fields": "username,name,profile_image_url"}
        )

        user_data = response.get("data", {})
        username = user_data.get("username")
        name = user_data.get("name", "")
        user_id = user_data.get("id")
        profile_image = user_data.get("profile_image_url")

        first_name = None
        last_name = None
        if name:
            name_parts = name.split(maxsplit=1)
            first_name = name_parts[0] if len(name_parts) > 0 else None
            last_name = name_parts[1] if len(name_parts) > 1 else None

        return ConnectedAccountInfo(
            username=username,
            first_name=first_name,
            last_name=last_name,
            user_id=user_id,
            avatar_url=profile_image
        )


# ---- Media Upload Helper ----

async def _upload_media(context: ExecutionContext, file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Internal helper to upload media using X API v2 chunked upload. Returns dict with media_id or error."""
    media_content = file_data.get('content', '')
    content_type = file_data.get('contentType', 'image/jpeg')

    media_bytes = base64.b64decode(media_content)
    total_bytes = len(media_bytes)

    # Determine media category
    if content_type.startswith("video/"):
        media_category = "tweet_video"
    elif content_type == "image/gif":
        media_category = "tweet_gif"
    else:
        media_category = "tweet_image"

    # Step 1: INIT - Initialize upload (all params in JSON body)
    init_response = await context.fetch(
        f"{X_MEDIA_UPLOAD_URL}/initialize",
        method="POST",
        json={
            "media_category": media_category,
            "media_type": content_type,
            "total_bytes": total_bytes
        }
    )

    if isinstance(init_response, dict) and "errors" in init_response:
        error_msg = init_response.get("errors", [{}])[0].get("message", str(init_response))
        return {"error": f"Initialize failed: {error_msg}"}

    # Extract media_id from response (v2 returns in data object)
    media_id = None
    if isinstance(init_response, dict):
        if "data" in init_response:
            media_id = init_response.get("data", {}).get("id")
        else:
            media_id = init_response.get("media_id_string") or init_response.get("media_id")

    if not media_id:
        return {"error": f"No media_id returned: {str(init_response)[:300]}"}

    media_id = str(media_id)

    # Step 2: APPEND - Upload chunks (2MB chunks to avoid issues)
    chunk_size = min(2 * 1024 * 1024, total_bytes)
    segment_index = 0

    for i in range(0, total_bytes, chunk_size):
        chunk = media_bytes[i:i + chunk_size]
        chunk_base64 = base64.b64encode(chunk).decode('utf-8')

        # v2 APPEND: media_id in URL, media and segment_index in JSON body
        append_response = await context.fetch(
            f"{X_MEDIA_UPLOAD_URL}/{media_id}/append",
            method="POST",
            json={
                "media": chunk_base64,
                "segment_index": segment_index
            }
        )

        if isinstance(append_response, dict) and "errors" in append_response:
            error_msg = append_response.get("errors", [{}])[0].get("message", str(append_response))
            return {"error": f"Append chunk {segment_index} failed: {error_msg}"}

        segment_index += 1

    # Step 3: FINALIZE - Complete the upload
    finalize_response = await context.fetch(
        f"{X_MEDIA_UPLOAD_URL}/{media_id}/finalize",
        method="POST"
    )

    if isinstance(finalize_response, dict) and "errors" in finalize_response:
        error_msg = finalize_response.get("errors", [{}])[0].get("message", str(finalize_response))
        return {"error": f"Finalize failed: {error_msg}"}

    # Step 4: STATUS - Poll for processing completion (for videos/gifs)
    if media_category in ["tweet_video", "tweet_gif"]:
        processing_info = None
        if isinstance(finalize_response, dict):
            processing_info = finalize_response.get("data", {}).get("processing_info") or finalize_response.get("processing_info")

        if processing_info:
            max_attempts = 30
            attempt = 0

            while attempt < max_attempts:
                state = processing_info.get("state")

                if state == "succeeded":
                    break
                elif state == "failed":
                    error_msg = processing_info.get("error", {}).get("message", "Processing failed")
                    return {"error": error_msg}

                wait_time = processing_info.get("check_after_secs", 5)
                await asyncio.sleep(wait_time)

                status_response = await context.fetch(
                    X_MEDIA_UPLOAD_URL,
                    method="GET",
                    params={"id": media_id}
                )

                if isinstance(status_response, dict):
                    processing_info = status_response.get("data", {}).get("processing_info") or status_response.get("processing_info")
                    if not processing_info:
                        break
                else:
                    break

                attempt += 1

    return {
        "media_id": media_id,
        "media_type": content_type,
        "size": total_bytes
    }


# ---- Post Handlers ----

@x.action("create_tweet")
class CreateTweetAction(ActionHandler):
    """Create a new post on X, optionally with media."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"text": inputs['text']}
            media_id = None

            # Handle file upload if provided
            file_data = None
            if 'file' in inputs and inputs['file']:
                file_data = inputs['file']
            elif 'files' in inputs and inputs['files'] and len(inputs['files']) > 0:
                file_data = inputs['files'][0]

            if file_data:
                upload_result = await _upload_media(context, file_data)
                if "error" in upload_result:
                    return ActionResult(
                        data={"post": {}, "result": False, "error": upload_result["error"]},
                        cost_usd=0.0
                    )
                media_id = upload_result["media_id"]
                data['media'] = {"media_ids": [media_id]}

            if 'reply_to' in inputs and inputs['reply_to']:
                data['reply'] = {"in_reply_to_tweet_id": inputs['reply_to']}

            if 'quote_tweet_id' in inputs and inputs['quote_tweet_id']:
                data['quote_tweet_id'] = inputs['quote_tweet_id']

            if 'poll_options' in inputs and inputs['poll_options']:
                data['poll'] = {
                    "options": inputs['poll_options'],
                    "duration_minutes": inputs.get('poll_duration_minutes', 1440)
                }

            response = await context.fetch(
                f"{X_API_BASE_URL}/tweets",
                method="POST",
                json=data
            )

            if isinstance(response, dict) and "errors" in response:
                error_msg = response.get("errors", [{}])[0].get("message", str(response))
                return ActionResult(
                    data={"post": {}, "media_id": media_id, "result": False, "error": f"Tweet failed: {error_msg}"},
                    cost_usd=0.0
                )

            result_data = {"post": response.get('data', {}), "result": True}
            if media_id:
                result_data["media_id"] = media_id

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"post": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("get_tweet")
class GetTweetAction(ActionHandler):
    """Get details of a specific post by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post_id = inputs['post_id']
            params = {}
            expansions = []
            tweet_fields = ["created_at", "public_metrics", "author_id", "conversation_id"]

            if inputs.get('include_user'):
                expansions.append("author_id")
                params['user.fields'] = "username,name,profile_image_url,verified"

            if inputs.get('include_metrics'):
                tweet_fields.extend(["non_public_metrics", "organic_metrics"])

            if expansions:
                params['expansions'] = ",".join(expansions)
            params['tweet.fields'] = ",".join(tweet_fields)

            response = await context.fetch(
                f"{X_API_BASE_URL}/tweets/{post_id}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"post": response.get('data', {}), "includes": response.get('includes', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"post": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("delete_tweet")
class DeleteTweetAction(ActionHandler):
    """Delete a post on X."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post_id = inputs['post_id']
            response = await context.fetch(f"{X_API_BASE_URL}/tweets/{post_id}", method="DELETE")

            return ActionResult(
                data={"deleted": response.get('data', {}).get('deleted', False), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("search_tweets")
class SearchTweetsAction(ActionHandler):
    """Search for posts using a query."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "query": inputs['query'],
                "tweet.fields": "created_at,public_metrics,author_id,conversation_id,lang",
                "expansions": "author_id",
                "user.fields": "username,name,verified"
            }

            if inputs.get('max_results'):
                params['max_results'] = min(inputs['max_results'], 100)
            if inputs.get('start_time'):
                params['start_time'] = inputs['start_time']
            if inputs.get('end_time'):
                params['end_time'] = inputs['end_time']
            if inputs.get('next_token'):
                params['next_token'] = inputs['next_token']

            response = await context.fetch(
                f"{X_API_BASE_URL}/tweets/search/recent",
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "posts": response.get('data', []),
                    "includes": response.get('includes', {}),
                    "meta": response.get('meta', {}),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"posts": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("get_user_tweets")
class GetUserTweetsAction(ActionHandler):
    """Get posts from a specific user's timeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs['user_id']
            params = {
                "tweet.fields": "created_at,public_metrics,conversation_id",
                "max_results": inputs.get('max_results', 10)
            }

            if inputs.get('pagination_token'):
                params['pagination_token'] = inputs['pagination_token']

            excludes = []
            if inputs.get('exclude_replies'):
                excludes.append("replies")
            if inputs.get('exclude_retweets'):
                excludes.append("retweets")
            if excludes:
                params['exclude'] = ",".join(excludes)

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{user_id}/tweets",
                method="GET",
                params=params
            )

            return ActionResult(
                data={"posts": response.get('data', []), "meta": response.get('meta', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"posts": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("get_liked_tweets")
class GetLikedTweetsAction(ActionHandler):
    """Get posts liked by a user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs['user_id']
            params = {
                "tweet.fields": "created_at,public_metrics,author_id",
                "expansions": "author_id",
                "user.fields": "username,name,verified",
                "max_results": inputs.get('max_results', 10)
            }

            if inputs.get('pagination_token'):
                params['pagination_token'] = inputs['pagination_token']

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{user_id}/liked_tweets",
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "posts": response.get('data', []),
                    "includes": response.get('includes', {}),
                    "meta": response.get('meta', {}),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"posts": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Repost Handlers ----

@x.action("retweet")
class RetweetAction(ActionHandler):
    """Repost a post on X."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs['user_id']
            post_id = inputs['post_id']

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{user_id}/retweets",
                method="POST",
                json={"tweet_id": post_id}
            )

            return ActionResult(
                data={"reposted": response.get('data', {}).get('retweeted', False), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"reposted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("unretweet")
class UnretweetAction(ActionHandler):
    """Remove a repost on X."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs['user_id']
            post_id = inputs['post_id']

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{user_id}/retweets/{post_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"unreposted": not response.get('data', {}).get('retweeted', True), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"unreposted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- User Handlers ----

@x.action("get_user")
class GetUserAction(ActionHandler):
    """Get user profile information by ID or username."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "user.fields": "created_at,description,location,public_metrics,verified,profile_image_url,url"
            }

            if inputs.get('user_id'):
                url = f"{X_API_BASE_URL}/users/{inputs['user_id']}"
            elif inputs.get('username'):
                url = f"{X_API_BASE_URL}/users/by/username/{inputs['username']}"
            else:
                return ActionResult(
                    data={"user": {}, "result": False, "error": "Either user_id or username is required"},
                    cost_usd=0.0
                )

            response = await context.fetch(url, method="GET", params=params)

            return ActionResult(
                data={"user": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("get_me")
class GetMeAction(ActionHandler):
    """Get authenticated user's profile information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "user.fields": "created_at,description,location,public_metrics,verified,profile_image_url,url"
            }

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/me",
                method="GET",
                params=params
            )

            return ActionResult(
                data={"user": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("follow_user")
class FollowUserAction(ActionHandler):
    """Follow a user on X."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            source_user_id = inputs['source_user_id']
            target_user_id = inputs['target_user_id']

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{source_user_id}/following",
                method="POST",
                json={"target_user_id": target_user_id}
            )

            return ActionResult(
                data={"followed": response.get('data', {}).get('following', False), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"followed": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@x.action("unfollow_user")
class UnfollowUserAction(ActionHandler):
    """Unfollow a user on X."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            source_user_id = inputs['source_user_id']
            target_user_id = inputs['target_user_id']

            response = await context.fetch(
                f"{X_API_BASE_URL}/users/{source_user_id}/following/{target_user_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"unfollowed": not response.get('data', {}).get('following', True), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"unfollowed": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )

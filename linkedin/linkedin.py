"""
LinkedIn Integration for Autohive

This module provides LinkedIn integration including:
- User profile information retrieval
- Content sharing/posting (text, articles, reshares)
- Post management (update, delete)

All actions use the LinkedIn API with version 202601.

Comment and reaction actions are not included because they require LinkedIn's
Community Management API product approval (a partnership level beyond the
self-serve "Share on LinkedIn" product). w_member_social on its own returns
HTTP 403 ACCESS_DENIED for the partnerApiComments / partnerApiReactions
backend services.
"""

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, Tuple, List
from urllib.parse import quote

import base64
import aiohttp

linkedin = Integration.load()

# LinkedIn API version - January 2026
LINKEDIN_VERSION = "202601"


# Common headers for LinkedIn REST API
def get_linkedin_headers():
    return {
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def encode_urn(urn: str) -> str:
    """URL-encode a LinkedIn URN for use in API paths."""
    return quote(urn, safe="")


async def get_current_user_urn(context: ExecutionContext) -> str:
    """Fetch the current authenticated user's URN."""
    user_info_url = "https://api.linkedin.com/v2/userinfo"
    user_response = await context.fetch(user_info_url, method="GET")
    body = user_response.data

    if isinstance(body, dict) and body.get("sub"):
        return f"urn:li:person:{body.get('sub')}"
    raise ValueError("Could not determine current user. Please ensure proper authentication.")


async def post_to_linkedin(url: str, payload: dict, access_token: str) -> Tuple[int, dict, Any]:
    """
    Make a POST request to LinkedIn API and return status, headers, and body.

    This is separate from context.fetch() because LinkedIn returns the post ID
    in the x-restli-id response header, which context.fetch() doesn't expose.

    Returns:
        Tuple of (status_code, headers_dict, response_body)
    """
    headers = get_linkedin_headers()
    headers["Authorization"] = f"Bearer {access_token}"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            # Get response body if any
            body = None
            if response.content_length and response.content_length > 0:
                try:
                    body = await response.json()
                except Exception:
                    body = await response.text()

            return response.status, dict(response.headers), body


# =============================================================================
# IMAGE UPLOAD HELPERS
# =============================================================================

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_IMAGES_PER_POST = 20


async def initialize_image_upload(context: ExecutionContext, owner_urn: str) -> dict:
    """
    Initialize image upload with LinkedIn.

    Args:
        context: Execution context with auth
        owner_urn: The owner URN (person or organization)

    Returns:
        dict with upload_url, image_urn
    """
    url = "https://api.linkedin.com/rest/images?action=initializeUpload"

    payload = {"initializeUploadRequest": {"owner": owner_urn}}

    response = await context.fetch(url, method="POST", json=payload, headers=get_linkedin_headers())
    body = response.data

    if isinstance(body, dict) and "value" in body:
        value = body["value"]
        return {"upload_url": value.get("uploadUrl"), "image_urn": value.get("image")}

    raise ValueError(f"Failed to initialize image upload: {body}")


async def upload_image_binary(context: ExecutionContext, upload_url: str, image_data: bytes, content_type: str) -> None:
    """
    Upload binary image data to LinkedIn's upload URL.

    Args:
        context: Execution context
        upload_url: The upload URL from initialize_image_upload
        image_data: Raw binary image data
        content_type: MIME type (image/jpeg, image/png, image/gif)
    """
    headers = {"Content-Type": content_type, "LinkedIn-Version": LINKEDIN_VERSION}

    await context.fetch(upload_url, method="PUT", data=image_data, headers=headers)


async def upload_image_from_base64(
    context: ExecutionContext, owner_urn: str, image_content: str, content_type: str
) -> str:
    """
    Complete image upload workflow: initialize + upload binary.

    Args:
        context: Execution context
        owner_urn: The owner URN
        image_content: Base64-encoded image data
        content_type: MIME type

    Returns:
        Image URN for use in post creation
    """
    # Initialize the upload
    init_result = await initialize_image_upload(context, owner_urn)
    upload_url = init_result["upload_url"]
    image_urn = init_result["image_urn"]

    # Strip data URL prefix if present (e.g., "data:image/jpeg;base64,")
    if "," in image_content and image_content.startswith("data:"):
        image_content = image_content.split(",", 1)[1]

    # Fix padding if needed (base64 strings must be multiple of 4)
    padding_needed = len(image_content) % 4
    if padding_needed:
        image_content += "=" * (4 - padding_needed)

    # Decode and upload the binary
    image_data = base64.b64decode(image_content)
    await upload_image_binary(context, upload_url, image_data, content_type)

    return image_urn


def validate_file_input(file_obj: dict) -> Tuple[str, str, str]:
    """
    Validate a file input object using the standard platform format.

    Args:
        file_obj: Dict with content, name, and contentType

    Returns:
        Tuple of (content, content_type, alt_text)
        alt_text is derived from filename without extension

    Raises:
        ValueError: If validation fails
    """
    content = file_obj.get("content")
    content_type = file_obj.get("contentType")
    name = file_obj.get("name", "")

    if not content:
        raise ValueError("File 'content' (base64-encoded data) is required")

    if not content_type:
        raise ValueError("File 'contentType' is required")

    if not name:
        raise ValueError("File 'name' is required")

    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}. Supported types: {', '.join(SUPPORTED_IMAGE_TYPES)}")

    # Derive alt_text from filename (without extension)
    alt_text = name.rsplit(".", 1)[0] if "." in name else name

    return content, content_type, alt_text


# =============================================================================
# USER INFO ACTION
# =============================================================================


@linkedin.action("get_user_info")
class UserInfoActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve user profile information via OpenID Connect userinfo endpoint."""
        url = "https://api.linkedin.com/v2/userinfo"

        response = await context.fetch(url, method="GET")
        body = response.data

        if isinstance(body, dict) and body.get("sub"):
            return ActionResult(
                data={
                    "result": "User information retrieved successfully.",
                    "user_info": body,
                }
            )

        error_details = body.get("error", "Unknown error") if isinstance(body, dict) else "Unknown error"
        return ActionError(message=f"Failed to retrieve user information: {error_details}")


# =============================================================================
# POST MANAGEMENT ACTIONS
# =============================================================================


@linkedin.action("create_post")
class CreatePostActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Create a LinkedIn post with optional images.

        Supports:
        - Text-only posts (no images)
        - Single image posts (1 image)
        - Multi-image posts (2-20 images)
        """
        text = inputs.get("text", "")
        visibility = inputs.get("visibility", "PUBLIC")
        author_id = inputs.get("author_id")
        disable_reshare = inputs.get("disable_reshare", False)

        # Handle both 'file' (single) and 'files' (array) inputs
        files = inputs.get("files", [])
        single_file = inputs.get("file")
        if single_file:
            files = [single_file]

        # Validate file count before any API calls
        if len(files) > MAX_IMAGES_PER_POST:
            return ActionError(message=f"Too many images. Maximum allowed is {MAX_IMAGES_PER_POST}, got {len(files)}.")

        # Validate all files upfront before any uploads
        validated_images: List[Tuple[str, str, str]] = []
        for idx, file_obj in enumerate(files):
            try:
                content, content_type, alt_text = validate_file_input(file_obj)
                validated_images.append((content, content_type, alt_text))
            except ValueError as e:
                return ActionError(message=f"Invalid file at index {idx}: {str(e)}")

        # Require at least text or files
        if not text and not files:
            return ActionError(message="Post must have either text or at least one file.")

        # Determine author URN
        if author_id:
            author_urn = f"urn:li:person:{author_id}"
        else:
            try:
                author_urn = await get_current_user_urn(context)
            except Exception as e:
                return ActionError(message=f"Failed to create post. Could not determine current user: {str(e)}")

        # Upload images if provided
        uploaded_image_urns: List[Tuple[str, str]] = []
        for idx, (content, content_type, alt_text) in enumerate(validated_images):
            try:
                image_urn = await upload_image_from_base64(context, author_urn, content, content_type)
                uploaded_image_urns.append((image_urn, alt_text))
            except Exception as e:
                return ActionError(message=f"Failed to upload image at index {idx}: {str(e)}")

        # Build post payload
        posts_url = "https://api.linkedin.com/rest/posts"

        payload = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": disable_reshare,
        }

        # Add content based on number of images
        if len(uploaded_image_urns) == 1:
            # Single image post
            image_urn, alt_text = uploaded_image_urns[0]
            media_content = {"id": image_urn}
            if alt_text:
                media_content["altText"] = alt_text
            payload["content"] = {"media": media_content}
        elif len(uploaded_image_urns) > 1:
            # Multi-image post
            multi_images = []
            for image_urn, alt_text in uploaded_image_urns:
                image_obj = {"id": image_urn}
                if alt_text:
                    image_obj["altText"] = alt_text
                multi_images.append(image_obj)
            payload["content"] = {"multiImage": {"images": multi_images}}
        # No content field for text-only posts

        try:
            # Use helper function to get response headers (LinkedIn returns post ID in header)
            access_token = context.auth.get("credentials", {}).get("access_token")
            status, headers, body = await post_to_linkedin(posts_url, payload, access_token)

            if status >= 400:
                return ActionError(message=f"Failed to create post: HTTP {status} {body}")

            post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
            post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None

            return ActionResult(
                data={
                    "result": "Post created successfully.",
                    "post_id": post_id,
                    "post_url": post_url,
                    "images_uploaded": len(uploaded_image_urns),
                }
            )
        except Exception as e:
            return ActionError(message=f"Failed to create post: {str(e)}")


@linkedin.action("share_article")
class ShareArticleActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Share an article post on LinkedIn with URL, title, and description."""
        commentary = inputs.get("commentary", "")
        article_url = inputs["article_url"]
        article_title = inputs["article_title"]
        article_description = inputs.get("article_description", "")
        author_id = inputs.get("author_id")
        visibility = inputs.get("visibility", "PUBLIC")

        # Determine author URN
        if author_id:
            author_urn = f"urn:li:person:{author_id}"
        else:
            try:
                author_urn = await get_current_user_urn(context)
            except Exception as e:
                return ActionError(message=f"Failed to share article. Could not determine current user: {str(e)}")

        posts_url = "https://api.linkedin.com/rest/posts"

        payload = {
            "author": author_urn,
            "commentary": commentary,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "article": {
                    "source": article_url,
                    "title": article_title,
                    "description": article_description,
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            access_token = context.auth.get("credentials", {}).get("access_token")
            status, headers, body = await post_to_linkedin(posts_url, payload, access_token)

            if status >= 400:
                return ActionError(message=f"Failed to share article: HTTP {status} {body}")

            post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
            post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None

            return ActionResult(
                data={
                    "result": "Article shared successfully.",
                    "post_id": post_id,
                    "post_url": post_url,
                }
            )
        except Exception as e:
            return ActionError(message=f"Failed to share article: {str(e)}")


@linkedin.action("reshare_post")
class ResharePostActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Reshare an existing LinkedIn post."""
        original_post_urn = inputs["original_post_urn"]
        commentary = inputs.get("commentary", "")
        author_id = inputs.get("author_id")
        visibility = inputs.get("visibility", "PUBLIC")

        # Determine author URN
        if author_id:
            author_urn = f"urn:li:person:{author_id}"
        else:
            try:
                author_urn = await get_current_user_urn(context)
            except Exception as e:
                return ActionError(message=f"Failed to reshare post. Could not determine current user: {str(e)}")

        posts_url = "https://api.linkedin.com/rest/posts"

        payload = {
            "author": author_urn,
            "commentary": commentary,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
            "reshareContext": {"parent": original_post_urn},
        }

        try:
            access_token = context.auth.get("credentials", {}).get("access_token")
            status, headers, body = await post_to_linkedin(posts_url, payload, access_token)

            if status >= 400:
                return ActionError(message=f"Failed to reshare post: HTTP {status} {body}")

            post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
            post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None

            return ActionResult(
                data={
                    "result": "Post reshared successfully.",
                    "post_id": post_id,
                    "post_url": post_url,
                }
            )
        except Exception as e:
            return ActionError(message=f"Failed to reshare post: {str(e)}")


@linkedin.action("update_post")
class UpdatePostActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Update an existing post's commentary."""
        post_urn = inputs["post_urn"]
        commentary = inputs["commentary"]

        encoded_urn = encode_urn(post_urn)
        url = f"https://api.linkedin.com/rest/posts/{encoded_urn}"

        payload = {"patch": {"$set": {"commentary": commentary}}}

        headers = get_linkedin_headers()
        headers["X-RestLi-Method"] = "PARTIAL_UPDATE"

        try:
            response = await context.fetch(url, method="POST", json=payload, headers=headers)
            if response.status >= 400:
                return ActionError(message=f"Failed to update post: HTTP {response.status} {response.data}")

            return ActionResult(data={"result": "Post updated successfully.", "post_urn": post_urn})
        except Exception as e:
            return ActionError(message=f"Failed to update post: {str(e)}")


@linkedin.action("delete_post")
class DeletePostActionHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Delete a post."""
        post_urn = inputs["post_urn"]

        encoded_urn = encode_urn(post_urn)
        url = f"https://api.linkedin.com/rest/posts/{encoded_urn}"

        headers = get_linkedin_headers()
        headers["X-RestLi-Method"] = "DELETE"

        try:
            response = await context.fetch(url, method="DELETE", headers=headers)
            if response.status >= 400:
                return ActionError(message=f"Failed to delete post: HTTP {response.status} {response.data}")

            return ActionResult(data={"result": "Post deleted successfully.", "post_urn": post_urn})
        except Exception as e:
            return ActionError(message=f"Failed to delete post: {str(e)}")

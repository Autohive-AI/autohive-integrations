from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
heygen = Integration.load()

# Base URL for HeyGen API
HEYGEN_API_BASE_URL = "https://api.heygen.com/v2"


# ---- Helper Functions ----

def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for HeyGen API requests.
    Uses OAuth 2.0 Bearer token authentication (required for HeyGen partnership).

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with authentication headers
    """
    credentials = context.auth.get("credentials", {})
    access_token = credentials.get("access_token", "")

    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AutoHive/1.0"
    }


# ---- Action Handlers ----

@heygen.action("generate_photo_avatar")
class GeneratePhotoAvatarHandler(ActionHandler):
    """Handler for generating photo avatar photos"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Generate photos for photo avatar development

        Args:
            inputs: Dictionary containing avatar attributes (name, age, gender, ethnicity, orientation, pose, style, appearance)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing generation_id for status tracking
        """
        # Prepare the request body with required attributes
        request_body = {
            "name": inputs["name"],
            "age": inputs["age"],
            "gender": inputs["gender"],
            "ethnicity": inputs["ethnicity"],
            "orientation": inputs["orientation"],
            "pose": inputs["pose"],
            "style": inputs["style"],
            "appearance": inputs["appearance"]
        }

        # Add optional parameters if provided
        if "callback_url" in inputs and inputs["callback_url"]:
            request_body["callback_url"] = inputs["callback_url"]

        if "callback_id" in inputs and inputs["callback_id"]:
            request_body["callback_id"] = inputs["callback_id"]

        # Get authentication headers
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/photo/generate",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("check_generation_status")
class CheckGenerationStatusHandler(ActionHandler):
    """Handler for checking the status of a photo or look generation request"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Check the status of a generation request

        Args:
            inputs: Dictionary containing 'generation_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing status information and image URLs when complete
        """
        generation_id = inputs["generation_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/generation/{generation_id}",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("create_avatar_group")
class CreateAvatarGroupHandler(ActionHandler):
    """Handler for creating an avatar group by grouping photos of the same subject"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Create an avatar group collection

        Args:
            inputs: Dictionary containing 'name', 'image_key', and optional 'generation_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing group_id for subsequent operations
        """
        request_body = {
            "name": inputs["name"],
            "image_key": inputs["image_key"]
        }

        # Add optional generation_id if provided (only for AI-generated avatars)
        if "generation_id" in inputs and inputs["generation_id"]:
            request_body["generation_id"] = inputs["generation_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/avatar_group/create",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("add_looks_to_group")
class AddLooksToGroupHandler(ActionHandler):
    """Handler for adding additional looks to an existing avatar group"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Add looks to an existing avatar group

        Args:
            inputs: Dictionary containing 'group_id', 'image_keys' (array, max 4), 'name', and optional 'generation_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing updated group information
        """
        request_body = {
            "group_id": inputs["group_id"],
            "image_keys": inputs["image_keys"],
            "name": inputs["name"]
        }

        # Add optional generation_id if provided (only for AI-generated avatars)
        if "generation_id" in inputs and inputs["generation_id"]:
            request_body["generation_id"] = inputs["generation_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/avatar_group/add",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("train_avatar_group")
class TrainAvatarGroupHandler(ActionHandler):
    """Handler for training an avatar group using machine learning"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Train an avatar group to recognize the subject's unique features

        Args:
            inputs: Dictionary containing 'group_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing training job information
        """
        request_body = {
            "group_id": inputs["group_id"]
        }

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/train",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("check_training_status")
class CheckTrainingStatusHandler(ActionHandler):
    """Handler for checking the status of a group training job"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Check the training status of an avatar group

        Args:
            inputs: Dictionary containing 'group_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing training progress and completion status
        """
        group_id = inputs["group_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/train/status/{group_id}",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("generate_avatar_look")
class GenerateAvatarLookHandler(ActionHandler):
    """Handler for generating new looks for a trained avatar group"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Generate new appearance variations for a trained avatar group

        Args:
            inputs: Dictionary containing 'group_id', 'prompt', 'orientation', 'pose', 'style'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing generation_id for status tracking
        """
        request_body = {
            "group_id": inputs["group_id"],
            "prompt": inputs["prompt"],
            "orientation": inputs["orientation"],
            "pose": inputs["pose"],
            "style": inputs["style"]
        }

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/look/generate",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("add_motion_to_avatar")
class AddMotionToAvatarHandler(ActionHandler):
    """Handler for adding motion to a photo avatar"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Add animated effects to a static avatar

        Args:
            inputs: Dictionary containing 'id', optional 'prompt', and optional 'motion_type'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing new ID for motion-enhanced version
        """
        request_body = {
            "id": inputs["id"]
        }

        # Add optional parameters if provided
        if "prompt" in inputs and inputs["prompt"]:
            request_body["prompt"] = inputs["prompt"]

        if "motion_type" in inputs and inputs["motion_type"]:
            request_body["motion_type"] = inputs["motion_type"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/add_motion",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("add_sound_effect_to_avatar")
class AddSoundEffectToAvatarHandler(ActionHandler):
    """Handler for adding sound effects to an avatar"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Attach audio enhancements to an avatar

        Args:
            inputs: Dictionary containing 'id' (avatar identifier)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing updated avatar information
        """
        request_body = {
            "id": inputs["id"]
        }

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/add_sound_effect",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("list_avatar_groups")
class ListAvatarGroupsHandler(ActionHandler):
    """Handler for listing all photo avatar groups"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        List all photo avatar groups in the account

        Args:
            inputs: Dictionary with optional pagination parameters (page, limit, include_public)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing list of avatar groups with pagination info
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "limit" in inputs and inputs["limit"]:
            params["limit"] = inputs["limit"]

        if "include_public" in inputs and inputs["include_public"] is not None:
            params["include_public"] = inputs["include_public"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatar_group.list",
                headers=headers,
                method="GET",
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("list_avatars_in_group")
class ListAvatarsInGroupHandler(ActionHandler):
    """Handler for listing all avatars/looks within a specific avatar group"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        List all avatars and looks within a specific avatar group

        Args:
            inputs: Dictionary containing 'group_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing group info and list of avatars/looks
        """
        group_id = inputs["group_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatar_group/{group_id}/avatars",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("get_avatar_details")
class GetAvatarDetailsHandler(ActionHandler):
    """Handler for retrieving comprehensive video avatar information"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Get detailed information about a video avatar (public/studio avatar)

        Args:
            inputs: Dictionary containing 'avatar_id' (avatar identifier)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing comprehensive avatar information
        """
        avatar_id = inputs["avatar_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatar/{avatar_id}/details",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("get_photo_avatar_details")
class GetPhotoAvatarDetailsHandler(ActionHandler):
    """Handler for retrieving comprehensive photo avatar information"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Get detailed information about a photo avatar/talking photo

        Args:
            inputs: Dictionary containing 'id' (photo avatar identifier)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing comprehensive photo avatar information
        """
        photo_avatar_id = inputs["id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/{photo_avatar_id}",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("list_voices")
class ListVoicesHandler(ActionHandler):
    """Handler for listing all available voices"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        List all available voices for text-to-speech

        Args:
            inputs: Dictionary (no parameters required)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing list of voices with their IDs and characteristics
        """
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/voices",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("list_voice_locales")
class ListVoiceLocalesHandler(ActionHandler):
    """Handler for listing available voice locales/accents"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        List all available locales/accents for multilingual voices

        Args:
            inputs: Dictionary with optional 'voice_id' parameter
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing list of available locales
        """
        headers = get_auth_headers(context)
        params = {}

        if "voice_id" in inputs and inputs["voice_id"]:
            params["voice_id"] = inputs["voice_id"]

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/voices/locales",
                headers=headers,
                method="GET",
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("list_avatars")
class ListAvatarsHandler(ActionHandler):
    """Handler for listing all available avatars"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        List all avatars in the account

        Args:
            inputs: Dictionary with optional pagination parameters
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing list of avatars
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "limit" in inputs and inputs["limit"]:
            params["limit"] = inputs["limit"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatars",
                headers=headers,
                method="GET",
                params=params
            )

            # Simplify response to reduce size - remove long URLs
            if response.get("data"):
                data = response["data"]

                # Simplify avatars list
                if "avatars" in data and data["avatars"]:
                    simplified_avatars = []
                    for avatar in data["avatars"]:
                        simplified_avatars.append({
                            "avatar_id": avatar.get("avatar_id"),
                            "avatar_name": avatar.get("avatar_name"),
                            "gender": avatar.get("gender"),
                            "type": avatar.get("type"),
                            "premium": avatar.get("premium"),
                            "default_voice_id": avatar.get("default_voice_id")
                        })
                    data["avatars"] = simplified_avatars

                # Simplify talking_photos list
                if "talking_photos" in data and data["talking_photos"]:
                    simplified_photos = []
                    for photo in data["talking_photos"]:
                        simplified_photos.append({
                            "talking_photo_id": photo.get("talking_photo_id"),
                            "talking_photo_name": photo.get("talking_photo_name")
                        })
                    data["talking_photos"] = simplified_photos

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("create_avatar_video")
class CreateAvatarVideoHandler(ActionHandler):
    """Handler for creating videos with avatars"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Create a video using an avatar with multiple scenes

        Args:
            inputs: Dictionary containing video configuration (video_inputs, title, dimension, etc.)
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing video_id for status tracking
        """
        request_body = {
            "video_inputs": inputs["video_inputs"]
        }

        # Add optional parameters
        if "title" in inputs and inputs["title"]:
            request_body["title"] = inputs["title"]

        if "caption" in inputs and inputs["caption"] is not None:
            request_body["caption"] = inputs["caption"]

        if "dimension" in inputs and inputs["dimension"]:
            request_body["dimension"] = inputs["dimension"]

        if "folder_id" in inputs and inputs["folder_id"]:
            request_body["folder_id"] = inputs["folder_id"]

        if "callback_id" in inputs and inputs["callback_id"]:
            request_body["callback_id"] = inputs["callback_id"]

        if "callback_url" in inputs and inputs["callback_url"]:
            request_body["callback_url"] = inputs["callback_url"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/video/generate",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("create_photo_avatar_video")
class CreatePhotoAvatarVideoHandler(ActionHandler):
    """Handler for creating simple photo avatar videos (Avatar IV)"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Create a simple photo avatar video using Avatar IV endpoint

        Args:
            inputs: Dictionary containing image_key, video_title, script/voice or audio
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing video_id for status tracking
        """
        request_body = {
            "image_key": inputs["image_key"],
            "video_title": inputs["video_title"]
        }

        # Add script and voice_id if provided (text-to-speech)
        if "script" in inputs and inputs["script"]:
            request_body["script"] = inputs["script"]

        if "voice_id" in inputs and inputs["voice_id"]:
            request_body["voice_id"] = inputs["voice_id"]

        # Add audio if provided (instead of text-to-speech)
        if "audio_url" in inputs and inputs["audio_url"]:
            request_body["audio_url"] = inputs["audio_url"]

        if "audio_asset_id" in inputs and inputs["audio_asset_id"]:
            request_body["audio_asset_id"] = inputs["audio_asset_id"]

        # Add optional parameters
        if "video_orientation" in inputs and inputs["video_orientation"]:
            request_body["video_orientation"] = inputs["video_orientation"]

        if "fit" in inputs and inputs["fit"]:
            request_body["fit"] = inputs["fit"]

        if "custom_motion_prompt" in inputs and inputs["custom_motion_prompt"]:
            request_body["custom_motion_prompt"] = inputs["custom_motion_prompt"]

        if "enhance_custom_motion_prompt" in inputs and inputs["enhance_custom_motion_prompt"] is not None:
            request_body["enhance_custom_motion_prompt"] = inputs["enhance_custom_motion_prompt"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/video/av4/generate",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )


@heygen.action("get_video_status")
class GetVideoStatusHandler(ActionHandler):
    """Handler for checking video generation status"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Check the status of a video generation request

        Args:
            inputs: Dictionary containing 'video_id'
            context: Execution context with auth and network capabilities

        Returns:
            Dictionary containing video status and URL when complete
        """
        video_id = inputs["video_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers=headers,
                method="GET"
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "error": str(e),
                    "data": None
                },
                cost_usd=0.0
            )



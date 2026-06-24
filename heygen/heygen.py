from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any

# Create the integration using the config.json
heygen = Integration.load()

# Base URL for HeyGen API
HEYGEN_API_BASE_URL = "https://api.heygen.com/v2"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    credentials = context.auth.get("credentials", {})
    access_token = credentials.get("access_token", "")

    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "User-Agent": "AutoHive/1.0"}


# ---- Action Handlers ----


@heygen.action("generate_photo_avatar")
class GeneratePhotoAvatarHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {
            "name": inputs["name"],
            "age": inputs["age"],
            "gender": inputs["gender"],
            "ethnicity": inputs["ethnicity"],
            "orientation": inputs["orientation"],
            "pose": inputs["pose"],
            "style": inputs["style"],
            "appearance": inputs["appearance"],
        }

        if "callback_url" in inputs and inputs["callback_url"]:
            request_body["callback_url"] = inputs["callback_url"]

        if "callback_id" in inputs and inputs["callback_id"]:
            request_body["callback_id"] = inputs["callback_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/photo/generate",
                method="POST",
                headers=headers,
                json=request_body,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("check_generation_status")
class CheckGenerationStatusHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        generation_id = inputs["generation_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/generation/{generation_id}", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("create_avatar_group")
class CreateAvatarGroupHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"name": inputs["name"], "image_key": inputs["image_key"]}

        if "generation_id" in inputs and inputs["generation_id"]:
            request_body["generation_id"] = inputs["generation_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/avatar_group/create",
                method="POST",
                headers=headers,
                json=request_body,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("add_looks_to_group")
class AddLooksToGroupHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"group_id": inputs["group_id"], "image_keys": inputs["image_keys"], "name": inputs["name"]}

        if "generation_id" in inputs and inputs["generation_id"]:
            request_body["generation_id"] = inputs["generation_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/avatar_group/add",
                method="POST",
                headers=headers,
                json=request_body,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("train_avatar_group")
class TrainAvatarGroupHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"group_id": inputs["group_id"]}

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/train", method="POST", headers=headers, json=request_body
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("check_training_status")
class CheckTrainingStatusHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        group_id = inputs["group_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/train/status/{group_id}", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("generate_avatar_look")
class GenerateAvatarLookHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {
            "group_id": inputs["group_id"],
            "prompt": inputs["prompt"],
            "orientation": inputs["orientation"],
            "pose": inputs["pose"],
            "style": inputs["style"],
        }

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/look/generate",
                method="POST",
                headers=headers,
                json=request_body,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("add_motion_to_avatar")
class AddMotionToAvatarHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"id": inputs["id"]}

        if "prompt" in inputs and inputs["prompt"]:
            request_body["prompt"] = inputs["prompt"]

        if "motion_type" in inputs and inputs["motion_type"]:
            request_body["motion_type"] = inputs["motion_type"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/add_motion", method="POST", headers=headers, json=request_body
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("add_sound_effect_to_avatar")
class AddSoundEffectToAvatarHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"id": inputs["id"]}

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/add_sound_effect",
                method="POST",
                headers=headers,
                json=request_body,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("list_avatar_groups")
class ListAvatarGroupsHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
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
                url=f"{HEYGEN_API_BASE_URL}/avatar_group.list", headers=headers, method="GET", params=params
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("list_avatars_in_group")
class ListAvatarsInGroupHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        group_id = inputs["group_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatar_group/{group_id}/avatars", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("get_avatar_details")
class GetAvatarDetailsHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        avatar_id = inputs["avatar_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatar/{avatar_id}/details", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("get_photo_avatar_details")
class GetPhotoAvatarDetailsHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        photo_avatar_id = inputs["id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/photo_avatar/{photo_avatar_id}", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("list_voices")
class ListVoicesHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(url=f"{HEYGEN_API_BASE_URL}/voices", headers=headers, method="GET")

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("list_voice_locales")
class ListVoiceLocalesHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        headers = get_auth_headers(context)
        params = {}

        if "voice_id" in inputs and inputs["voice_id"]:
            params["voice_id"] = inputs["voice_id"]

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/voices/locales", headers=headers, method="GET", params=params
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("list_avatars")
class ListAvatarsHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "limit" in inputs and inputs["limit"]:
            params["limit"] = inputs["limit"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{HEYGEN_API_BASE_URL}/avatars", headers=headers, method="GET", params=params
            )

            body = response.data

            # Simplify response to reduce size - remove long URLs
            if body.get("data"):
                data = body["data"]

                # Simplify avatars list
                if "avatars" in data and data["avatars"]:
                    simplified_avatars = []
                    for avatar in data["avatars"]:
                        simplified_avatars.append(
                            {
                                "avatar_id": avatar.get("avatar_id"),
                                "avatar_name": avatar.get("avatar_name"),
                                "gender": avatar.get("gender"),
                                "type": avatar.get("type"),
                                "premium": avatar.get("premium"),
                                "default_voice_id": avatar.get("default_voice_id"),
                            }
                        )
                    data["avatars"] = simplified_avatars

                # Simplify talking_photos list
                if "talking_photos" in data and data["talking_photos"]:
                    simplified_photos = []
                    for photo in data["talking_photos"]:
                        simplified_photos.append(
                            {
                                "talking_photo_id": photo.get("talking_photo_id"),
                                "talking_photo_name": photo.get("talking_photo_name"),
                            }
                        )
                    data["talking_photos"] = simplified_photos

            return ActionResult(data=body, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("create_avatar_video")
class CreateAvatarVideoHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"video_inputs": inputs["video_inputs"]}

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
                url=f"{HEYGEN_API_BASE_URL}/video/generate", method="POST", headers=headers, json=request_body
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("create_photo_avatar_video")
class CreatePhotoAvatarVideoHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        request_body = {"image_key": inputs["image_key"], "video_title": inputs["video_title"]}

        if "script" in inputs and inputs["script"]:
            request_body["script"] = inputs["script"]

        if "voice_id" in inputs and inputs["voice_id"]:
            request_body["voice_id"] = inputs["voice_id"]

        if "audio_url" in inputs and inputs["audio_url"]:
            request_body["audio_url"] = inputs["audio_url"]

        if "audio_asset_id" in inputs and inputs["audio_asset_id"]:
            request_body["audio_asset_id"] = inputs["audio_asset_id"]

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
                url=f"{HEYGEN_API_BASE_URL}/video/av4/generate", method="POST", headers=headers, json=request_body
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@heygen.action("get_video_status")
class GetVideoStatusHandler(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        video_id = inputs["video_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"https://api.heygen.com/v1/video_status.get?video_id={video_id}", headers=headers, method="GET"
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
)
from typing import Dict, Any
import base64

# Create the integration using the config.json
canva = Integration.load()
service_endpoint = "https://api.canva.com/rest"

# ---- Connected Account Handler ----


@canva.connected_account()
class CanvaConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """Fetch Canva user information"""
        # Get user profile (returns display name)
        profile_response = await context.fetch(f"{service_endpoint}/v1/users/me/profile", method="GET")

        # Get user details (returns user_id and team_id)
        user_response = await context.fetch(f"{service_endpoint}/v1/users/me", method="GET")

        # Extract information from responses
        display_name = profile_response.data.get("profile", {}).get("display_name")
        team_user = user_response.data.get("team_user", {})
        user_id = team_user.get("user_id")
        team_id = team_user.get("team_id")

        # Split display name into first/last if possible
        first_name = None
        last_name = None
        if display_name:
            name_parts = display_name.split(maxsplit=1)
            first_name = name_parts[0] if len(name_parts) > 0 else None
            last_name = name_parts[1] if len(name_parts) > 1 else None

        return ConnectedAccountInfo(
            username=display_name, first_name=first_name, last_name=last_name, user_id=user_id, organization=team_id
        )


# ---- Action Handlers ----

# User Actions


@canva.action("get_user_capabilities")
class GetUserCapabilities(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{service_endpoint}/v1/users/me/capabilities", method="GET")

            return ActionResult(data={"capabilities": response.data.get("capabilities", [])}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# Asset Actions


@canva.action("upload_asset")
class UploadAsset(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Get file object from inputs (handle both 'file' and 'files' array)
            file_obj = inputs.get("file")
            files_arr = inputs.get("files")
            if not file_obj and isinstance(files_arr, list) and files_arr:
                file_obj = files_arr[0]

            if not file_obj:
                raise ValueError("No file provided")

            file_name = file_obj.get("name", "asset")
            file_content_base64 = file_obj.get("content", "")

            if not file_content_base64:
                raise ValueError("File content is empty")

            # Decode the base64 file data
            file_data = base64.b64decode(file_content_base64)

            # Encode the asset name in base64 for the header (max 50 chars)
            asset_name = file_name[:50]  # Truncate to 50 chars max
            name_base64 = base64.b64encode(asset_name.encode("utf-8")).decode("utf-8")

            # Prepare headers
            headers = {
                "Content-Type": "application/octet-stream",
                "Asset-Upload-Metadata": f'{{"name_base64": "{name_base64}"}}',
            }

            # Make the upload request with binary data
            response = await context.fetch(
                f"{service_endpoint}/v1/asset-uploads", method="POST", headers=headers, data=file_data
            )

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("id"):
                result["job_id"] = job_data["id"]
            if job_data.get("status"):
                result["status"] = job_data["status"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_asset_upload_status")
class GetAssetUploadStatus(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            job_id = inputs["job_id"]

            response = await context.fetch(f"{service_endpoint}/v1/asset-uploads/{job_id}", method="GET")

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("status"):
                result["status"] = job_data["status"]
            if job_data.get("asset"):
                result["asset"] = job_data["asset"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_asset")
class GetAsset(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            asset_id = inputs["asset_id"]

            response = await context.fetch(f"{service_endpoint}/v1/assets/{asset_id}", method="GET")

            result = {}

            if response.data.get("asset"):
                result["asset"] = response.data["asset"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("update_asset")
class UpdateAsset(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            asset_id = inputs["asset_id"]

            # Build update payload
            update_data = {}
            name = inputs.get("name")
            if name is not None:
                update_data["name"] = name
            tags = inputs.get("tags")
            if tags is not None:
                update_data["tags"] = tags

            await context.fetch(f"{service_endpoint}/v1/assets/{asset_id}", method="PATCH", json=update_data)

            return ActionResult(data={}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("delete_asset")
class DeleteAsset(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            asset_id = inputs["asset_id"]

            await context.fetch(f"{service_endpoint}/v1/assets/{asset_id}", method="DELETE")

            return ActionResult(data={}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# Design Actions


@canva.action("create_design")
class CreateDesign(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build design creation payload
            design_data = {"design_type": {"type": "preset", "name": inputs["preset_type"]}}

            # Add optional fields
            title = inputs.get("title")
            if title is not None:
                design_data["title"] = title
            asset_id = inputs.get("asset_id")
            if asset_id is not None:
                design_data["asset_id"] = asset_id

            response = await context.fetch(f"{service_endpoint}/v1/designs", method="POST", json=design_data)

            result = {}

            if response.data.get("design"):
                result["design"] = response.data["design"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("list_designs")
class ListDesigns(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}
            query = inputs.get("query")
            if query is not None:
                params["query"] = query
            continuation = inputs.get("continuation")
            if continuation is not None:
                params["continuation"] = continuation
            ownership = inputs.get("ownership")
            if ownership is not None:
                params["ownership"] = ownership
            sort_by = inputs.get("sort_by")
            if sort_by is not None:
                params["sort_by"] = sort_by

            response = await context.fetch(f"{service_endpoint}/v1/designs", method="GET", params=params)

            # Wrap response to match output schema
            result = {"designs": response.data.get("items", [])}

            # Only include continuation if it exists
            if response.data.get("continuation"):
                result["continuation"] = response.data["continuation"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_design")
class GetDesign(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            design_id = inputs["design_id"]

            response = await context.fetch(f"{service_endpoint}/v1/designs/{design_id}", method="GET")

            result = {}

            if response.data.get("design"):
                result["design"] = response.data["design"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("export_design")
class ExportDesign(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            design_id = inputs["design_id"]
            export_format = inputs["format"]

            # Build export format object
            format_obj = {"type": export_format}

            # Optional format parameters (all optional in the input schema)
            export_quality = inputs.get("export_quality")
            paper_size = inputs.get("paper_size")
            pages = inputs.get("pages")
            jpg_quality = inputs.get("jpg_quality")
            width = inputs.get("width")
            height = inputs.get("height")
            lossless = inputs.get("lossless")
            transparent_background = inputs.get("transparent_background")
            as_single_image = inputs.get("as_single_image")
            image_quality = inputs.get("image_quality")

            # Add format-specific parameters
            if export_format.lower() == "pdf":
                # PDF-specific parameters
                if export_quality:
                    format_obj["export_quality"] = export_quality
                if paper_size:
                    format_obj["size"] = paper_size
                if pages:
                    format_obj["pages"] = pages

            elif export_format.lower() in ["jpg", "jpeg"]:
                # JPG parameters
                if jpg_quality:
                    try:
                        quality_val = int(jpg_quality)
                        format_obj["quality"] = max(1, min(100, quality_val))
                    except (ValueError, TypeError):
                        format_obj["quality"] = 85
                else:
                    format_obj["quality"] = 85
                if export_quality:
                    format_obj["export_quality"] = export_quality
                if width:
                    format_obj["width"] = width
                if height:
                    format_obj["height"] = height
                if pages:
                    format_obj["pages"] = pages

            elif export_format.lower() == "png":
                # PNG parameters
                if export_quality:
                    format_obj["export_quality"] = export_quality
                if width:
                    format_obj["width"] = width
                if height:
                    format_obj["height"] = height
                if lossless is not None:
                    format_obj["lossless"] = lossless
                if transparent_background is not None:
                    format_obj["transparent_background"] = transparent_background
                if as_single_image is not None:
                    format_obj["as_single_image"] = as_single_image
                if pages:
                    format_obj["pages"] = pages

            elif export_format.lower() in ["mp4", "gif"]:
                # MP4/GIF parameters - use quality with orientation_resolution
                if image_quality:
                    format_obj["quality"] = image_quality
                else:
                    format_obj["quality"] = "horizontal_1080p"
                if export_quality:
                    format_obj["export_quality"] = export_quality
                if pages:
                    format_obj["pages"] = pages

            # Build export payload
            export_data = {"design_id": design_id, "format": format_obj}

            response = await context.fetch(f"{service_endpoint}/v1/exports", method="POST", json=export_data)

            job_id = response.data.get("job", {}).get("id")

            return ActionResult(data={"job_id": job_id} if job_id else {}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_export_status")
class GetExportStatus(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            export_id = inputs["export_id"]

            response = await context.fetch(f"{service_endpoint}/v1/exports/{export_id}", method="GET")

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("status"):
                result["status"] = job_data["status"]
            if job_data.get("urls"):
                result["urls"] = job_data["urls"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("import_design")
class ImportDesign(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Get file object from inputs (handle both 'file' and 'files' array)
            file_obj = inputs.get("file")
            files_arr = inputs.get("files")
            if not file_obj and isinstance(files_arr, list) and files_arr:
                file_obj = files_arr[0]

            if not file_obj:
                raise ValueError("No file provided")

            file_name = file_obj.get("name", "design")
            file_content_base64 = file_obj.get("content", "")
            mime_type = file_obj.get("contentType", "application/pdf")

            if not file_content_base64:
                raise ValueError("File content is empty")

            # Decode the base64 file data
            file_data = base64.b64decode(file_content_base64)

            # Use provided title or filename
            title = inputs.get("title", file_name)

            # Encode the title in base64 for the header
            title_base64 = base64.b64encode(title.encode("utf-8")).decode("utf-8")

            # Build Import-Metadata header
            metadata = {"title_base64": title_base64, "mime_type": mime_type}

            # Prepare headers
            headers = {
                "Content-Type": "application/octet-stream",
                "Import-Metadata": str(metadata).replace("'", '"'),  # Convert to JSON format
            }

            # Make the import request with binary data
            response = await context.fetch(
                f"{service_endpoint}/v1/imports", method="POST", headers=headers, data=file_data
            )

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("id"):
                result["job_id"] = job_data["id"]
            if job_data.get("status"):
                result["status"] = job_data["status"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_design_import_status")
class GetDesignImportStatus(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            job_id = inputs["job_id"]

            response = await context.fetch(f"{service_endpoint}/v1/imports/{job_id}", method="GET")

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("status"):
                result["status"] = job_data["status"]
            if job_data.get("designs"):
                result["designs"] = job_data["designs"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("import_design_from_url")
class ImportDesignFromUrl(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body for URL-based import
            import_data = {"url": inputs["url"], "title": inputs["title"]}

            # Add optional MIME type
            mime_type = inputs.get("mime_type")
            if mime_type is not None:
                import_data["mime_type"] = mime_type

            response = await context.fetch(f"{service_endpoint}/v1/url-imports", method="POST", json=import_data)

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("id"):
                result["job_id"] = job_data["id"]
            if job_data.get("status"):
                result["status"] = job_data["status"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_url_import_status")
class GetUrlImportStatus(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            job_id = inputs["job_id"]

            response = await context.fetch(f"{service_endpoint}/v1/url-imports/{job_id}", method="GET")

            result = {}
            job_data = response.data.get("job", {})

            if job_data.get("status"):
                result["status"] = job_data["status"]
            if job_data.get("designs"):
                result["designs"] = job_data["designs"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# Folder Actions


@canva.action("create_folder")
class CreateFolder(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build folder creation payload
            # If parent_folder_id not provided, default to "root"
            folder_data = {"name": inputs["name"], "parent_folder_id": inputs.get("parent_folder_id", "root")}

            response = await context.fetch(f"{service_endpoint}/v1/folders", method="POST", json=folder_data)

            return ActionResult(data={"folder": response.data.get("folder")}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("get_folder")
class GetFolder(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            response = await context.fetch(f"{service_endpoint}/v1/folders/{folder_id}", method="GET")

            result = {}

            if response.data.get("folder"):
                result["folder"] = response.data["folder"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("list_folder_items")
class ListFolderItems(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            # Build query parameters
            params = {}
            continuation = inputs.get("continuation")
            if continuation is not None:
                params["continuation"] = continuation

            response = await context.fetch(
                f"{service_endpoint}/v1/folders/{folder_id}/items", method="GET", params=params
            )

            result = {"items": response.data.get("items", [])}

            # Only include continuation if it exists
            if response.data.get("continuation"):
                result["continuation"] = response.data["continuation"]

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("update_folder")
class UpdateFolder(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            # Build update payload
            update_data = {"name": inputs["name"]}

            await context.fetch(f"{service_endpoint}/v1/folders/{folder_id}", method="PATCH", json=update_data)

            return ActionResult(data={}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("delete_folder")
class DeleteFolder(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            await context.fetch(f"{service_endpoint}/v1/folders/{folder_id}", method="DELETE")

            return ActionResult(data={}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@canva.action("move_item_to_folder")
class MoveItemToFolder(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build move payload - flat structure per Canva API
            move_data = {"to_folder_id": inputs["destination_folder_id"], "item_id": inputs["item_id"]}

            await context.fetch(f"{service_endpoint}/v1/folders/move", method="POST", json=move_data)

            return ActionResult(data={}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))

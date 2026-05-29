from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any
import binascii
import json
import base64

# Create the integration using the config.json
dropbox = Integration.load()

# Base URLs for Dropbox API
DROPBOX_API_BASE_URL = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_BASE_URL = "https://content.dropboxapi.com/2"


# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


def _build_upload_path(path: str, file_name: str) -> str:
    """Combine an optional folder ``path`` with ``file_name`` into a Dropbox path.

    - Empty / ``"/"`` path → ``/<file_name>``
    - Ensures a leading ``/``
    - Strips trailing slashes
    - Backwards compatible: if ``path`` already ends with the same ``file_name``
      (the previous flat-path schema), it is returned unchanged so callers
      migrating from the 1.x shape do not get ``/folder/a.txt/a.txt``.
    """
    destination = (path or "").strip()

    if destination in ("", "/"):
        return f"/{file_name}"

    if not destination.startswith("/"):
        destination = f"/{destination}"

    destination = destination.rstrip("/")

    if destination.rsplit("/", 1)[-1] == file_name:
        return destination

    return f"{destination}/{file_name}"


# ---- Action Handlers ----

# ---- File and Folder Listing Handlers ----


@dropbox.action("list_folder")
class ListFolderAction(ActionHandler):
    """List contents of a folder. Supports pagination via optional cursor parameter."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # If cursor is provided, use the continue endpoint for pagination
            cursor = inputs.get("cursor")
            if cursor:
                data = {"cursor": cursor}
                response = await context.fetch(
                    f"{DROPBOX_API_BASE_URL}/files/list_folder/continue", method="POST", json=data
                )
            else:
                # Initial listing request
                data = {
                    "path": inputs.get("path", ""),
                    "recursive": inputs.get("recursive", False),
                    "include_deleted": inputs.get("include_deleted", False),
                    "include_has_explicit_shared_members": inputs.get("include_has_explicit_shared_members", False),
                    "include_mounted_folders": inputs.get("include_mounted_folders", True),
                }

                limit = inputs.get("limit")
                if limit is not None:
                    data["limit"] = limit

                response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/list_folder", method="POST", json=data)

            body = response.data or {}
            entries = body.get("entries", [])
            new_cursor = body.get("cursor")
            has_more = body.get("has_more", False)

            data = {"entries": entries, "has_more": has_more}
            if new_cursor is not None:
                data["cursor"] = new_cursor

            return ActionResult(data=data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Metadata Handlers ----


@dropbox.action("get_metadata")
class GetMetadataAction(ActionHandler):
    """Get metadata for a file or folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "path": inputs["path"],
                "include_deleted": inputs.get("include_deleted", False),
                "include_has_explicit_shared_members": inputs.get("include_has_explicit_shared_members", False),
            }

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/get_metadata", method="POST", json=data)

            return ActionResult(data={"metadata": response.data or {}}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Download Handlers ----


@dropbox.action("get_temporary_link")
class GetTemporaryLinkAction(ActionHandler):
    """Get a temporary link to stream content of a file."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"path": inputs["path"]}

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/get_temporary_link", method="POST", json=data)

            body = response.data or {}
            link = body.get("link")
            metadata = body.get("metadata", {})

            return ActionResult(data={"link": link, "metadata": metadata}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Write Operations ----


@dropbox.action("upload_file")
class UploadFileAction(ActionHandler):
    """Upload a file to Dropbox."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            file_obj = inputs.get("file") or {}
            # Treat only missing/None content as an error — zero-byte files (base64 == "") are valid.
            if "content" not in file_obj or file_obj.get("content") is None:
                return ActionError(message="File content is required")

            file_name = file_obj.get("name")
            if not file_name:
                return ActionError(message="File name is required")

            try:
                content = base64.b64decode(file_obj["content"], validate=True)
            except (binascii.Error, ValueError) as e:
                return ActionError(message=f"File content must be valid base64: {e}")

            dropbox_path = _build_upload_path(inputs.get("path") or "", file_name)

            api_arg = {
                "path": dropbox_path,
                "mode": inputs.get("mode", "add"),
                "autorename": inputs.get("autorename", False),
                "mute": inputs.get("mute", False),
            }

            headers = {"Dropbox-API-Arg": json.dumps(api_arg), "Content-Type": "application/octet-stream"}

            response = await context.fetch(
                f"{DROPBOX_CONTENT_BASE_URL}/files/upload", method="POST", headers=headers, data=content
            )

            return ActionResult(data={"file": response.data or {}}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@dropbox.action("create_folder")
class CreateFolderAction(ActionHandler):
    """Create a new folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"path": inputs["path"], "autorename": inputs.get("autorename", False)}

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/create_folder_v2", method="POST", json=data)

            body = response.data or {}
            return ActionResult(data={"folder": body.get("metadata", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@dropbox.action("delete")
class DeleteAction(ActionHandler):
    """Delete a file or folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"path": inputs["path"]}

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/delete_v2", method="POST", json=data)

            body = response.data or {}
            return ActionResult(data={"metadata": body.get("metadata", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@dropbox.action("move")
class MoveAction(ActionHandler):
    """Move a file or folder to a different location."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "from_path": inputs["from_path"],
                "to_path": inputs["to_path"],
                "autorename": inputs.get("autorename", False),
                "allow_ownership_transfer": inputs.get("allow_ownership_transfer", False),
            }

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/move_v2", method="POST", json=data)

            body = response.data or {}
            return ActionResult(data={"metadata": body.get("metadata", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@dropbox.action("copy")
class CopyAction(ActionHandler):
    """Copy a file or folder to a different location."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "from_path": inputs["from_path"],
                "to_path": inputs["to_path"],
                "autorename": inputs.get("autorename", False),
            }

            response = await context.fetch(f"{DROPBOX_API_BASE_URL}/files/copy_v2", method="POST", json=data)

            body = response.data or {}
            return ActionResult(data={"metadata": body.get("metadata", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

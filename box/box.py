from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler
from typing import Dict, Any
import json
import base64
import aiohttp

# Create the integration using the config.json
box = Integration.load()

# Box API Base URLs
BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"

# ---- Action Handlers ----


@box.action("list_shared_folders")
class ListSharedFolders(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page_size = inputs.get("pageSize", 100)
            page_token = inputs.get("pageToken")

            # List root folder contents (folder_id "0" is the root folder in Box)
            url = f"{BOX_API_BASE}/folders/0/items"
            params = {"limit": page_size, "fields": "id,name,type,description,created_at,modified_at"}
            if page_token:
                params["offset"] = page_token

            data = await context.fetch(url, method="GET", params=params)

            # Filter for folders only
            folders = []
            for item in data.get("entries", []):
                if item.get("type") == "folder":
                    folders.append(
                        {
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "type": item.get("type"),
                            "description": item.get("description", ""),
                            "created_at": item.get("created_at"),
                            "modified_at": item.get("modified_at"),
                        }
                    )

            response_data = {"folders": folders, "result": True}

            # Add pagination token if there are more items
            total_count = data.get("total_count", 0)
            current_offset = int(params.get("offset", 0))
            if current_offset + page_size < total_count:
                response_data["nextPageToken"] = str(current_offset + page_size)

            return response_data

        except Exception as e:
            return {"folders": [], "result": False, "error": str(e)}


@box.action("list_files")
class ListFiles(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            query = inputs.get("query", "")
            file_extensions = inputs.get("file_extensions", [])
            folder_id = inputs.get("folder_id")
            page_size = inputs.get("pageSize", 100)

            if query or file_extensions or folder_id:
                # Use search API
                url = f"{BOX_API_BASE}/search"

                # Build search query
                search_query = query if query else "*"
                if file_extensions:
                    ext_query = " OR ".join([f"file_extension:{ext}" for ext in file_extensions])
                    search_query = f"({search_query}) AND ({ext_query})"
                if folder_id:
                    search_query = f"({search_query}) AND ancestor_folder_ids:{folder_id}"

                params = {
                    "query": search_query,
                    "limit": page_size,
                    "type": "file",
                    "fields": "id,name,type,size,modified_at,created_at",
                }
            else:
                # List recent files from root
                url = f"{BOX_API_BASE}/folders/0/items"
                params = {"limit": page_size, "fields": "id,name,type,size,modified_at,created_at"}

            data = await context.fetch(url, method="GET", params=params)

            # Format the files response
            files = []
            entries = data.get("entries", [])
            for item in entries:
                if item.get("type") == "file":
                    files.append(
                        {
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "type": item.get("type"),
                            "size": item.get("size"),
                            "modified_at": item.get("modified_at"),
                            "created_at": item.get("created_at"),
                        }
                    )

            response_data = {"files": files, "result": True}

            # Add pagination if available
            if "next_marker" in data:
                response_data["nextPageToken"] = data["next_marker"]

            return response_data

        except Exception as e:
            return {"files": [], "result": False, "error": str(e)}


@box.action("list_folder_contents")
class ListFolderContents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]
            recursive = inputs.get("recursive", False)
            page_size = inputs.get("pageSize", 100)

            url = f"{BOX_API_BASE}/folders/{folder_id}/items"
            params = {"limit": page_size, "fields": "id,name,type,size,created_at,modified_at"}

            data = await context.fetch(url, method="GET", params=params)

            # Format the items response
            items = []
            for item in data.get("entries", []):
                formatted_item = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "created_at": item.get("created_at"),
                    "modified_at": item.get("modified_at"),
                }

                # Only add size for files
                if item.get("type") == "file" and "size" in item:
                    formatted_item["size"] = item.get("size")

                items.append(formatted_item)

                # If recursive and this is a folder, get its contents too
                if recursive and item.get("type") == "folder":
                    try:
                        subfolder_url = f"{BOX_API_BASE}/folders/{item['id']}/items"
                        sub_data = await context.fetch(subfolder_url, method="GET", params=params)

                        for sub_item in sub_data.get("entries", []):
                            sub_formatted_item = {
                                "id": sub_item.get("id"),
                                "name": f"{item['name']}/{sub_item.get('name')}",
                                "type": sub_item.get("type"),
                                "created_at": sub_item.get("created_at"),
                                "modified_at": sub_item.get("modified_at"),
                            }
                            if sub_item.get("type") == "file" and "size" in sub_item:
                                sub_formatted_item["size"] = sub_item.get("size")
                            items.append(sub_formatted_item)
                    except Exception:
                        pass  # Skip subfolders that can't be read

            response_data = {"items": items, "result": True}

            # Add pagination if available
            if "next_marker" in data:
                response_data["nextPageToken"] = data["next_marker"]

            return response_data

        except Exception as e:
            return {"items": [], "result": False, "error": str(e)}


@box.action("get_file")
class GetFile(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            file_id = inputs["file_id"]

            # First get file metadata
            metadata_url = f"{BOX_API_BASE}/files/{file_id}"
            metadata = await context.fetch(metadata_url, method="GET")

            # For file content download, we need to handle binary data manually
            # since context.fetch() calls response.text() which fails for binary content
            content_url = f"{BOX_API_BASE}/files/{file_id}/content"

            async with context:  # Use context as async context manager
                session = context._session
                if not session:
                    session = aiohttp.ClientSession()
                    context._session = session

                # Get auth headers from context
                headers = {}
                if context.auth and "credentials" in context.auth:
                    credentials = context.auth["credentials"]
                    if "access_token" in credentials:
                        headers["Authorization"] = f"Bearer {credentials['access_token']}"

                async with session.get(content_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {
                            "file": {"name": "", "content": "", "contentType": ""},
                            "metadata": {"id": file_id},
                            "result": False,
                            "error": f"Box API error getting content: {response.status} - {error_text}",
                        }

                    # Read binary content and encode as base64
                    file_content = await response.read()
                    content_base64 = base64.b64encode(file_content).decode("utf-8")

            # Extract information from metadata
            file_name = metadata.get("name", f"file_{file_id}")
            content_type = metadata.get("content_type") or "application/octet-stream"

            # Structure the metadata to match the required format
            structured_metadata = {
                "id": file_id,
                "name": file_name,
                "size": str(metadata.get("size", 0)),
                "mimeType": content_type,
                "createdTime": metadata.get("created_at", ""),
                "modifiedTime": metadata.get("modified_at", ""),
                "parents": [metadata.get("parent", {}).get("id", "")] if metadata.get("parent") else [],
            }

            return {
                "file": {"name": file_name, "content": content_base64, "contentType": content_type},
                "metadata": structured_metadata,
                "result": True,
            }

        except Exception as e:
            return {
                "file": {"name": "", "content": "", "contentType": ""},
                "metadata": {"id": file_id},
                "result": False,
                "error": str(e),
            }


@box.action("upload_file")
class UploadFile(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            file_obj = inputs["file"]
            folder_id = inputs.get("folder_id", "0")  # Default to root folder

            # Extract file object properties
            content = file_obj["content"]
            file_name = file_obj["name"]
            content_type = file_obj["contentType"]

            # Decode base64 content
            file_content = base64.b64decode(content)

            # For uploads, we need to use multipart form data
            # The Box API expects a specific format for file uploads
            url = f"{BOX_UPLOAD_BASE}/files/content"

            # Create the form data manually since context.fetch doesn't handle multipart forms
            # We'll need to use a different approach for uploads
            async with context:  # Use context as async context manager
                # Prepare multipart form data for upload
                data = aiohttp.FormData()
                data.add_field(
                    "attributes",
                    json.dumps({"name": file_name, "parent": {"id": folder_id}}),
                    content_type="application/json",
                )
                data.add_field("file", file_content, filename=file_name, content_type=content_type)

                # Use context's session directly with authentication handled
                session = context._session
                if not session:
                    session = aiohttp.ClientSession()
                    context._session = session

                # Get auth headers from context
                headers = {}
                if context.auth and "credentials" in context.auth:
                    credentials = context.auth["credentials"]
                    if "access_token" in credentials:
                        headers["Authorization"] = f"Bearer {credentials['access_token']}"

                async with session.post(url, headers=headers, data=data) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        return {"result": False, "error": f"Box upload error: {response.status} - {error_text}"}

                    upload_result = await response.json()

                    # Extract file information from response
                    entries = upload_result.get("entries", [])
                    if entries:
                        uploaded_file = entries[0]
                        return {
                            "file_id": uploaded_file.get("id"),
                            "file_name": uploaded_file.get("name"),
                            "file_size": uploaded_file.get("size"),
                            "content_type": content_type,
                            "result": True,
                        }
                    else:
                        return {
                            "file_name": file_name,
                            "content_type": content_type,
                            "result": True,
                            "error": "Upload succeeded but no file details returned",
                        }

        except Exception as e:
            return {"result": False, "error": str(e)}


# ---- Polling Trigger Handlers ----

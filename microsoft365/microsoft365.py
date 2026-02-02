from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import base64
import aiohttp
import urllib.parse

# Create the integration using the config.json
microsoft365 = Integration.load()

# Microsoft Graph API Base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

async def fetch_binary_content(url: str, context: ExecutionContext) -> bytes:
    """Fetch binary content directly without SDK text parsing"""
    headers = {}
    if context.auth and "credentials" in context.auth:
        access_token = context.auth["credentials"]["access_token"]
        headers["Authorization"] = f"Bearer {access_token}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if not response.ok:
                raise Exception(f"HTTP {response.status}: {await response.text()}")
            return await response.read()  # Returns bytes directly

# ---- Action Handlers ----

@microsoft365.action("send_email")
class SendEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build email message
            message = {
                "subject": inputs["subject"],
                "body": {
                    "contentType": inputs.get("body_type", "Text"),
                    "content": inputs["body"]
                },
                "toRecipients": [
                    {"emailAddress": {"address": inputs["to"]}}
                ]
            }
            
            # Add CC recipients if provided
            if inputs.get("cc"):
                message["ccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in inputs["cc"]
                ]
            
            # Add BCC recipients if provided
            if inputs.get("bcc"):
                message["bccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in inputs["bcc"]
                ]
            
            # Send email
            email_data = {
                "message": message,
                "saveToSentItems": True
            }
            
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/sendMail",
                method="POST",
                json=email_data
            )
            
            return ActionResult(
                data={
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("create_calendar_event")
class CreateCalendarEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build event data
            event_data = {
                "subject": inputs["subject"],
                "start": {
                    "dateTime": inputs["start_time"],
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": inputs["end_time"],
                    "timeZone": "UTC"
                }
            }
            
            # Add optional fields
            if inputs.get("location"):
                event_data["location"] = {
                    "displayName": inputs["location"]
                }
            
            if inputs.get("body"):
                event_data["body"] = {
                    "contentType": "Text",
                    "content": inputs["body"]
                }
            
            if inputs.get("attendees"):
                event_data["attendees"] = [
                    {
                        "emailAddress": {"address": email, "name": email},
                        "type": "required"
                    } for email in inputs["attendees"]
                ]
            
            # Create event
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/events",
                method="POST",
                json=event_data
            )
            
            return ActionResult(
                data={
                "id": response["id"],
                "webLink": response["webLink"],
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("upload_file")
class UploadFileAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filename = inputs["filename"]
            content = inputs["content"]
            content_type = inputs.get("content_type", "text/plain")
            folder_path = inputs.get("folder_path", "/").strip("/")
            
            # Convert text to bytes
            file_content = content.encode('utf-8')
            
            # Build upload URL
            if folder_path:
                upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{folder_path}/{filename}:/content"
            else:
                upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{filename}:/content"
            
            # Upload file
            response = await context.fetch(
                upload_url,
                method="PUT",
                data=file_content,
                headers={"Content-Type": content_type}
            )
            
            return ActionResult(
                data={
                "id": response["id"],
                "webUrl": response["webUrl"],
                "size": response["size"],
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_files")
class ListFilesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            folder_path = inputs.get("folder_path", "/").strip("/")
            limit = inputs.get("limit", 100)
            
            # Build API URL
            if folder_path:
                api_url = f"{GRAPH_API_BASE}/me/drive/root:/{folder_path}:/children"
            else:
                api_url = f"{GRAPH_API_BASE}/me/drive/root/children"
            
            # Add query parameters
            params = {
                "$top": limit,
                "$select": "id,name,size,lastModifiedDateTime,webUrl,folder"
            }
            
            response = await context.fetch(api_url, params=params)
            
            # Format files
            files = []
            for item in response.get("value", []):
                file_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "size": item.get("size", 0),
                    "lastModifiedDateTime": item["lastModifiedDateTime"],
                    "webUrl": item["webUrl"]
                }
                # Only include folder property if it exists (for folders only)
                if "folder" in item:
                    file_item["folder"] = item["folder"]
                files.append(file_item)
            
            return ActionResult(
                data={
                "files": files,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "files": [],
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("update_calendar_event")
class UpdateCalendarEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            event_id = inputs["event_id"]
            
            # Build event update data (only include fields that are provided)
            event_data = {}
            
            if inputs.get("subject"):
                event_data["subject"] = inputs["subject"]
            
            if inputs.get("start_time"):
                event_data["start"] = {
                    "dateTime": inputs["start_time"],
                    "timeZone": "UTC"
                }
            
            if inputs.get("end_time"):
                event_data["end"] = {
                    "dateTime": inputs["end_time"],
                    "timeZone": "UTC"
                }
            
            if inputs.get("location"):
                event_data["location"] = {
                    "displayName": inputs["location"]
                }
            
            if inputs.get("body"):
                event_data["body"] = {
                    "contentType": "Text",
                    "content": inputs["body"]
                }
            
            if inputs.get("attendees"):
                event_data["attendees"] = [
                    {
                        "emailAddress": {"address": email, "name": email},
                        "type": "required"
                    } for email in inputs["attendees"]
                ]
            
            # Update event
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/events/{event_id}",
                method="PATCH",
                json=event_data
            )
            
            return ActionResult(
                data={
                "id": response["id"],
                "webLink": response["webLink"],
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_calendar_events")
class ListCalendarEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Accept either datetime or date parameters, with intelligent defaults
            if "start_datetime" in inputs:
                start_datetime = inputs["start_datetime"]
                end_datetime = inputs.get("end_datetime", start_datetime)
            elif "start_date" in inputs:
                # Legacy date-only support (defaults to UTC)
                start_date = inputs["start_date"]
                end_date = inputs.get("end_date", start_date)
                start_datetime = f"{start_date}T00:00:00Z"
                end_datetime = f"{end_date}T23:59:59Z"
            else:
                # Intelligent default: next 30 days of calendar events (more useful for calendars)
                # Use UTC time for intelligent defaults (agent can provide timezone-aware datetime if needed)
                now = datetime.utcnow()
                end_time = now + timedelta(days=30)
                start_datetime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                end_datetime = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            limit = inputs.get("limit", 100)

            # Build query parameters using calendarView for proper date filtering
            # CalendarView is recommended for date range queries per Microsoft Graph docs
            params = {
                "$top": limit,
                "$orderby": "start/dateTime",
                "$select": "id,subject,start,end,location,bodyPreview,organizer,attendees,webLink,isAllDay"
            }

            # Use calendarView endpoint with startDateTime/endDateTime query parameters
            # GET /me/calendarView?startDateTime={start}&endDateTime={end}
            api_url = f"{GRAPH_API_BASE}/me/calendarView?startDateTime={start_datetime}&endDateTime={end_datetime}"

            response = await context.fetch(api_url, params=params)
            
            # Format events
            events = []
            for event in response.get("value", []):
                # Process attendees
                attendees = []
                for attendee in event.get("attendees", []):
                    attendees.append({
                        "email": attendee["emailAddress"]["address"],
                        "name": attendee["emailAddress"]["name"],
                        "response_status": attendee["status"]["response"]
                    })
                
                # Get organizer email
                organizer_email = ""
                if event.get("organizer") and event["organizer"].get("emailAddress"):
                    organizer_email = event["organizer"]["emailAddress"]["address"]
                
                events.append({
                    "id": event["id"],
                    "subject": event.get("subject") or "",
                    "start": event["start"],
                    "end": event["end"],
                    "location": event.get("location", {}).get("displayName") or "",
                    "bodyPreview": event.get("bodyPreview") or "",
                    "organizer": organizer_email,
                    "attendees": attendees,
                    "webLink": event["webLink"],
                    "isAllDay": event.get("isAllDay", False)
                })
            
            return ActionResult(
                data={
                "events": events,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "events": [],
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_emails")
class ListEmailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Accept either datetime or date parameters, with intelligent defaults
            if "start_datetime" in inputs:
                start_datetime = inputs["start_datetime"]
                end_datetime = inputs.get("end_datetime", start_datetime)
            elif "start_date" in inputs:
                # Legacy date-only support (defaults to UTC)
                start_date = inputs["start_date"]
                end_date = inputs.get("end_date", start_date)
                start_datetime = f"{start_date}T00:00:00Z"
                end_datetime = f"{end_date}T23:59:59Z"
            else:
                # Intelligent default: last 1 day of emails
                # Use UTC time for intelligent defaults (agent can provide timezone-aware datetime if needed)
                now = datetime.utcnow()
                start_time = now - timedelta(days=1)
                start_datetime = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                end_datetime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            folder = inputs.get("folder", "Inbox")
            limit = inputs.get("limit", 50)
            
            # Build query parameters
            params = {
                "$top": limit,
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,sender,receivedDateTime,bodyPreview,body,hasAttachments,isRead,importance",
                "$filter": f"receivedDateTime ge {start_datetime} and receivedDateTime le {end_datetime}"
            }
            
            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"
            response = await context.fetch(api_url, params=params)
            
            # Format emails
            emails = []
            for email in response.get("value", []):
                emails.append({
                    "id": email["id"],
                    "subject": email.get("subject") or "",
                    "sender": email["sender"],
                    "receivedDateTime": email["receivedDateTime"],
                    "bodyPreview": email.get("bodyPreview") or "",
                    "body": email.get("body", {}),
                    "hasAttachments": email.get("hasAttachments", False),
                    "isRead": email.get("isRead", False),
                    "importance": email.get("importance", "normal")
                })
            
            return ActionResult(
                data={
                "emails": emails,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "emails": [],
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_emails_from_contact")
class ListEmailsFromContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_email = inputs["contact_email"]
            limit = inputs.get("limit", 5)
            folder = inputs.get("folder", "Inbox")
            
            # Build query parameters - skip complex filters due to API limitations
            params = {
                "$top": limit,
                "$orderby": "receivedDateTime desc", 
                "$select": "id,subject,sender,receivedDateTime,bodyPreview,body,hasAttachments,isRead,importance"
            }
            
            # TODO: Implement contact filtering in post-processing
            
            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"
            response = await context.fetch(api_url, params=params)
            
            # Format emails
            emails = []
            for email in response.get("value", []):
                emails.append({
                    "id": email["id"],
                    "subject": email.get("subject") or "",
                    "sender": email["sender"],
                    "receivedDateTime": email["receivedDateTime"],
                    "bodyPreview": email.get("bodyPreview") or "",
                    "body": email.get("body", {}),
                    "hasAttachments": email.get("hasAttachments", False),
                    "isRead": email.get("isRead", False),
                    "importance": email.get("importance", "normal")
                })
            
            return ActionResult(
                data={
                "emails": emails,
                "contact_email": contact_email,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "emails": [],
                "contact_email": contact_email,
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("mark_email_read")
class MarkEmailReadAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            is_read = inputs["is_read"]
            
            # Update email read status
            update_data = {
                "isRead": is_read
            }
            
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}",
                method="PATCH",
                json=update_data
            )
            
            return ActionResult(
                data={
                "id": response["id"],
                "isRead": response["isRead"],
                "lastModifiedDateTime": response["lastModifiedDateTime"],
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_mail_folders")
class ListMailFoldersAction(ActionHandler):
    """List mail folders in the user's mailbox.

    Returns root-level folders by default. Use include_hidden to show hidden folders.
    Use include_children to recursively fetch all nested folders.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            include_hidden = inputs.get("include_hidden", False)
            include_children = inputs.get("include_children", False)
            folder_id = inputs.get("folder_id")  # Optional: list children of specific folder

            # Build API URL
            if folder_id:
                api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder_id}/childFolders"
            else:
                api_url = f"{GRAPH_API_BASE}/me/mailFolders"

            # Build query parameters
            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }

            if include_hidden:
                params["includeHiddenFolders"] = "true"

            # Fetch all pages (default page size is 10)
            all_folder_items = []
            next_url = api_url
            is_first_request = True

            while next_url:
                if is_first_request:
                    response = await context.fetch(next_url, params=params)
                    is_first_request = False
                else:
                    # nextLink already contains query params, don't pass params again
                    response = await context.fetch(next_url)

                all_folder_items.extend(response.get("value", []))
                next_url = response.get("@odata.nextLink")

            # Format folders
            folders = []
            for folder in all_folder_items:
                folder_data = {
                    "id": folder["id"],
                    "displayName": folder.get("displayName", ""),
                    "parentFolderId": folder.get("parentFolderId", ""),
                    "childFolderCount": folder.get("childFolderCount", 0),
                    "unreadItemCount": folder.get("unreadItemCount", 0),
                    "totalItemCount": folder.get("totalItemCount", 0),
                    "isHidden": folder.get("isHidden", False)
                }
                folders.append(folder_data)

                # Recursively fetch child folders if requested
                if include_children and folder.get("childFolderCount", 0) > 0:
                    child_folders = await self._fetch_child_folders_recursive(
                        folder["id"], context, include_hidden
                    )
                    folders.extend(child_folders)

            return ActionResult(
                data={
                    "folders": folders,
                    "total_count": len(folders),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "folders": [],
                    "total_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

    async def _fetch_child_folders_recursive(
        self, parent_folder_id: str, context: ExecutionContext, include_hidden: bool
    ) -> List[Dict[str, Any]]:
        """Recursively fetch all child folders under a parent folder."""
        try:
            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{parent_folder_id}/childFolders"
            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }
            if include_hidden:
                params["includeHiddenFolders"] = "true"

            # Fetch all pages (default page size is 10)
            all_folder_items = []
            next_url = api_url
            is_first_request = True

            while next_url:
                if is_first_request:
                    response = await context.fetch(next_url, params=params)
                    is_first_request = False
                else:
                    # nextLink already contains query params, don't pass params again
                    response = await context.fetch(next_url)

                all_folder_items.extend(response.get("value", []))
                next_url = response.get("@odata.nextLink")

            folders = []
            for folder in all_folder_items:
                folder_data = {
                    "id": folder["id"],
                    "displayName": folder.get("displayName", ""),
                    "parentFolderId": folder.get("parentFolderId", ""),
                    "childFolderCount": folder.get("childFolderCount", 0),
                    "unreadItemCount": folder.get("unreadItemCount", 0),
                    "totalItemCount": folder.get("totalItemCount", 0),
                    "isHidden": folder.get("isHidden", False)
                }
                folders.append(folder_data)

                # Recursively fetch children if this folder has child folders
                if folder.get("childFolderCount", 0) > 0:
                    child_folders = await self._fetch_child_folders_recursive(
                        folder["id"], context, include_hidden
                    )
                    folders.extend(child_folders)

            return folders
        except Exception:
            # If fetching children fails, return empty list but don't fail the whole operation
            return []


@microsoft365.action("get_mail_folder")
class GetMailFolderAction(ActionHandler):
    """Get a specific mail folder by ID or well-known name.

    Well-known folder names: inbox, drafts, sentitems, deleteditems, junkemail,
    archive, outbox, clutter, scheduled, searchfolders, conversationhistory
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            folder_id = inputs["folder_id"]

            # Build API URL - works with both folder IDs and well-known names
            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder_id}"

            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }

            response = await context.fetch(api_url, params=params)

            folder_data = {
                "id": response["id"],
                "displayName": response.get("displayName", ""),
                "parentFolderId": response.get("parentFolderId", ""),
                "childFolderCount": response.get("childFolderCount", 0),
                "unreadItemCount": response.get("unreadItemCount", 0),
                "totalItemCount": response.get("totalItemCount", 0),
                "isHidden": response.get("isHidden", False)
            }

            return ActionResult(
                data={
                    "folder": folder_data,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "folder": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@microsoft365.action("move_email")
class MoveEmailAction(ActionHandler):
    """Move an email to a different folder.

    The destination_folder_id must be either:
    1. A folder ID (e.g., 'AQMkADYAAAIBXQAAAA==') obtained from list_mail_folders
    2. A well-known folder name (lowercase, no spaces): inbox, drafts, sentitems,
       deleteditems, junkemail, archive, outbox, clutter, scheduled

    For custom folders, use list_mail_folders with include_children=true to find the folder ID.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            destination_folder_id = inputs["destination_folder_id"]

            # Move email to destination folder
            move_data = {
                "destinationId": destination_folder_id
            }

            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}/move",
                method="POST",
                json=move_data
            )

            return ActionResult(
                data={
                    "id": response["id"],
                    "parentFolderId": response["parentFolderId"],
                    "subject": response.get("subject", ""),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )

@microsoft365.action("read_email")
class ReadEmailAction(ActionHandler):
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            include_attachments = inputs.get("include_attachments", True)
            
            # Get email details
            email_response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}",
                params={
                    "$select": "id,subject,sender,receivedDateTime,body,hasAttachments"
                }
            )
            
            # Format email details
            email_details = {
                "id": email_response["id"],
                "subject": email_response.get("subject") or "",
                "sender": email_response["sender"],
                "receivedDateTime": email_response["receivedDateTime"],
                "body": email_response.get("body", {}),
                "hasAttachments": email_response.get("hasAttachments", False)
            }
            
            attachments = []
            
            if include_attachments and email_details["hasAttachments"]:
                # Get attachments
                attachments_response = await context.fetch(
                    f"{GRAPH_API_BASE}/me/messages/{email_id}/attachments"
                )
                
                for attachment in attachments_response.get("value", []):
                    attachment_id = attachment["id"]
                    attachment_name = attachment["name"]
                    attachment_size = attachment.get("size", 0)
                    content_type = attachment.get("contentType", "application/octet-stream")
                    
                    # Return attachment metadata only (no content download)
                    attachment_data = {
                        "id": attachment_id,
                        "name": attachment_name,
                        "size": attachment_size,
                        "contentType": content_type,
                        "message": "Attachment metadata only. Content extraction not supported for this file type."
                    }
                    
                    attachments.append(attachment_data)
            
            return ActionResult(
                data={
                "email": email_details,
                "attachments": attachments,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "email": {},
                "attachments": [],
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("read_contacts")
class ReadContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 100)
            search = inputs.get("search")
            
            # Build API URL
            api_url = f"{GRAPH_API_BASE}/me/contacts"
            
            # Build query parameters
            params = {
                "$top": limit,
                "$select": "id,displayName,givenName,surname,emailAddresses,businessPhones,homePhones,mobilePhone,companyName,jobTitle"
            }
            
            response = await context.fetch(api_url, params=params)

            # Format and filter contacts
            all_contacts = response.get("value", [])
            contacts = []

            for contact in all_contacts:
                # Client-side search filtering if search term provided
                if search:
                    search_lower = search.lower()
                    display_name = contact.get("displayName", "").lower()
                    given_name = contact.get("givenName", "").lower()
                    surname = contact.get("surname", "").lower()
                    company = contact.get("companyName", "").lower()

                    # Check if search term appears anywhere in name or company
                    if not (search_lower in display_name or
                           search_lower in given_name or
                           search_lower in surname or
                           search_lower in company):
                        continue  # Skip this contact
                # Process email addresses
                email_addresses = []
                for email in contact.get("emailAddresses", []):
                    email_addresses.append({
                        "address": email.get("address", ""),
                        "name": email.get("name", "")
                    })
                
                # Process phone numbers
                phone_numbers = []
                
                # Business phones
                for phone in contact.get("businessPhones", []):
                    phone_numbers.append({
                        "number": phone,
                        "type": "business"
                    })
                
                # Home phones  
                for phone in contact.get("homePhones", []):
                    phone_numbers.append({
                        "number": phone,
                        "type": "home"
                    })
                
                # Mobile phone
                mobile = contact.get("mobilePhone")
                if mobile:
                    phone_numbers.append({
                        "number": mobile,
                        "type": "mobile"
                    })
                
                contacts.append({
                    "id": contact.get("id", ""),
                    "displayName": contact.get("displayName", ""),
                    "givenName": contact.get("givenName", ""),
                    "surname": contact.get("surname", ""),
                    "emailAddresses": email_addresses,
                    "businessPhones": contact.get("businessPhones", []),
                    "homePhones": contact.get("homePhones", []),
                    "mobilePhone": contact.get("mobilePhone", ""),
                    "companyName": contact.get("companyName", ""),
                    "jobTitle": contact.get("jobTitle", "")
                })
            
            # Provide better result messaging
            if search:
                if contacts:
                    message = f"Found {len(contacts)} contact(s) matching '{search}'"
                else:
                    message = f"No contacts found matching '{search}'"

                return ActionResult(
                    data={
                    "contacts": contacts,
                    "result": True,
                    "message": message,
                    "search_term": search,
                    "total_searched": len(all_contacts)
                },
                    cost_usd=0.0
                )
            else:
                return ActionResult(
                    data={
                    "contacts": contacts,
                    "result": True,
                    "message": f"Retrieved {len(contacts)} contacts",
                    "total_contacts": len(contacts)
                },
                    cost_usd=0.0
                )
            
        except Exception as e:
            return ActionResult(
                data={
                "contacts": [],
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("search_onedrive_files")
class SearchOneDriveFilesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            search_query = inputs["query"]
            limit = inputs.get("limit", 10)
            
            # Build search URL
            # URL encode the search query to handle special characters
            encoded_query = urllib.parse.quote(search_query)
            
            # Add query parameters
            params = {
                "$top": limit,
                "$select": "id,name,size,lastModifiedDateTime,webUrl,folder,file"
            }
            
            api_url = f"{GRAPH_API_BASE}/me/drive/root/search(q='{encoded_query}')"
            response = await context.fetch(api_url, params=params)
            
            # Format search results
            files = []
            for item in response.get("value", []):
                file_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "size": item.get("size", 0),
                    "lastModifiedDateTime": item["lastModifiedDateTime"],
                    "webUrl": item["webUrl"]
                }
                # Only include folder property if it exists (for folders only)
                if "folder" in item:
                    file_item["folder"] = item["folder"]
                # Include file type information if available
                if "file" in item:
                    file_item["file"] = item["file"]
                files.append(file_item)
            
            return ActionResult(
                data={
                "files": files,
                "query": search_query,
                "result": True
            },
                cost_usd=0.0
            )
            
        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("read_onedrive_file_content")
class ReadOneDriveFileContentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            file_id = inputs["file_id"]
            
            # Get file metadata first
            metadata_params = {
                "$select": "id,name,size,mimeType,file,webUrl"
            }
            metadata_response = await context.fetch(
                f"{GRAPH_API_BASE}/me/drive/items/{file_id}",
                params=metadata_params
            )
            
            file_name = metadata_response["name"]
            file_size = metadata_response.get("size", 0)
            mime_type = metadata_response.get("mimeType", "")
            web_url = metadata_response.get("webUrl", "")
            
            # Try to get file content
            content = None
            try:
                # For Office documents, use Microsoft's PDF conversion API
                if any(ext in file_name.lower() for ext in ['.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']):
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content?format=pdf"
                    # Use binary fetch to avoid SDK text parsing for converted PDFs
                    content_bytes = await fetch_binary_content(content_url, context)

                    # Encode as base64 for JSON serialization
                    content = base64.b64encode(content_bytes).decode('utf-8')
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "Office document converted to PDF and encoded for LLM processing"
                elif file_name.lower().endswith('.pdf'):
                    # For native PDF files, get content directly (no conversion needed)
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content"
                    # Use binary fetch to avoid SDK text parsing for PDFs
                    content_bytes = await fetch_binary_content(content_url, context)

                    # Encode as base64 for JSON serialization
                    content = base64.b64encode(content_bytes).decode('utf-8')
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "PDF content retrieved and encoded for LLM processing"
                else:
                    # For text files, get raw content
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content"
                    content_response = await context.fetch(content_url, method="GET")

                    # Encode as base64 for consistent handling
                    if isinstance(content_response, bytes):
                        content = base64.b64encode(content_response).decode('utf-8')
                    elif isinstance(content_response, str):
                        # Use latin-1 encoding to preserve binary data in string
                        content = base64.b64encode(content_response.encode('latin-1')).decode('utf-8')
                    else:
                        content = base64.b64encode(str(content_response).encode('latin-1')).decode('utf-8')

                    content_type = mime_type or "text/plain"
                    content_available = True
                    content_info = "Text content retrieved and encoded successfully"
                
            except Exception as content_error:
                # If content retrieval fails, still return file metadata
                content = None
                content_available = False
                content_info = f"Content retrieval failed: {str(content_error)}"
            
            # Determine content type based on file extension if mime_type is empty
            if not mime_type:
                if file_name.lower().endswith('.pdf'):
                    mime_type = "application/pdf"
                elif any(ext in file_name.lower() for ext in ['.docx', '.doc']):
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif any(ext in file_name.lower() for ext in ['.xlsx', '.xls']):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif any(ext in file_name.lower() for ext in ['.pptx', '.ppt']):
                    mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    mime_type = "application/octet-stream"

            # Return in Google Drive format for consistency
            if content_available and content:
                return ActionResult(
                    data={
                    "file": {
                        "content": content,
                        "name": file_name,
                        "contentType": content_type
                    },
                    "metadata": {
                        "id": file_id,
                        "name": file_name,
                        "size": file_size,
                        "mimeType": mime_type,
                        "webUrl": web_url
                    },
                    "result": True
                },
                    cost_usd=0.0
                )
            else:
                # Set fallback content type for failed cases
                fallback_content_type = mime_type
                if file_name.lower().endswith('.pdf'):
                    fallback_content_type = "application/pdf"

                return ActionResult(
                    data={
                    "file": {
                        "content": "",
                        "name": file_name,
                        "contentType": fallback_content_type
                    },
                    "metadata": {
                        "id": file_id,
                        "name": file_name,
                        "size": file_size,
                        "mimeType": mime_type,
                        "webUrl": web_url
                    },
                    "result": False,
                    "error": content_info
                },
                    cost_usd=0.0
                )

        except Exception as e:
            return ActionResult(
                data={
                "file": {
                    "content": "",
                    "name": "",
                    "contentType": "application/octet-stream"
                },
                "metadata": {},
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("create_draft_email")
class CreateDraftEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            # Build email message according to Microsoft Graph API spec
            message = {
                "subject": inputs["subject"],
                "body": {
                    "contentType": inputs.get("body_type", "Text"),
                    "content": inputs["body"]
                },
                "toRecipients": []
            }

            # Add to recipients (required)
            for recipient in inputs["to_recipients"]:
                if isinstance(recipient, str):
                    message["toRecipients"].append({
                        "emailAddress": {"address": recipient}
                    })
                else:
                    message["toRecipients"].append({
                        "emailAddress": {
                            "address": recipient.get("address", recipient.get("email")),
                            "name": recipient.get("name", "")
                        }
                    })

            # Add CC recipients if provided
            if inputs.get("cc_recipients"):
                message["ccRecipients"] = []
                for recipient in inputs["cc_recipients"]:
                    if isinstance(recipient, str):
                        message["ccRecipients"].append({
                            "emailAddress": {"address": recipient}
                        })
                    else:
                        message["ccRecipients"].append({
                            "emailAddress": {
                                "address": recipient.get("address", recipient.get("email")),
                                "name": recipient.get("name", "")
                            }
                        })

            # Add BCC recipients if provided
            if inputs.get("bcc_recipients"):
                message["bccRecipients"] = []
                for recipient in inputs["bcc_recipients"]:
                    if isinstance(recipient, str):
                        message["bccRecipients"].append({
                            "emailAddress": {"address": recipient}
                        })
                    else:
                        message["bccRecipients"].append({
                            "emailAddress": {
                                "address": recipient.get("address", recipient.get("email")),
                                "name": recipient.get("name", "")
                            }
                        })

            # Add importance if specified
            if inputs.get("importance"):
                message["importance"] = inputs["importance"]

            # Create draft using Microsoft Graph API
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages",
                method="POST",
                json=message
            )

            return ActionResult(
                data={
                "result": True,
                "draft_id": response["id"],
                "subject": response.get("subject") or "",
                "created_datetime": response.get("createdDateTime") or "",
                "is_draft": response.get("isDraft", True)
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("send_draft_email")
class SendDraftEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_id = inputs["draft_id"]

            # Send draft using Microsoft Graph API
            # API requires Content-Length: 0 header and no body
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{draft_id}/send",
                method="POST",
                headers={"Content-Length": "0"}
            )

            return ActionResult(
                data={
                "result": True,
                "draft_id": draft_id,
                "status": "sent"
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "draft_id": inputs.get("draft_id", ""),
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("reply_to_email")
class ReplyToEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]

            # Build reply request according to Microsoft Graph API spec
            reply_data = {}
            if inputs.get("comment"):
                reply_data["comment"] = inputs["comment"]

            # Reply to message using Microsoft Graph API
            # API returns HTTP 202 Accepted with no body
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/reply",
                method="POST",
                json=reply_data
            )

            return ActionResult(
                data={
                "result": True,
                "message_id": message_id,
                "operation": "reply",
                "status": "sent"
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "message_id": inputs.get("message_id", ""),
                "operation": "reply",
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("forward_email")
class ForwardEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]

            # Build forward request according to Microsoft Graph API spec
            forward_data = {
                "toRecipients": []
            }

            # Add to recipients (required)
            for recipient in inputs["to_recipients"]:
                if isinstance(recipient, str):
                    forward_data["toRecipients"].append({
                        "emailAddress": {"address": recipient}
                    })
                else:
                    forward_data["toRecipients"].append({
                        "emailAddress": {
                            "address": recipient.get("address", recipient.get("email")),
                            "name": recipient.get("name", "")
                        }
                    })

            # Add comment if provided
            if inputs.get("comment"):
                forward_data["comment"] = inputs["comment"]

            # Forward message using Microsoft Graph API
            # API returns HTTP 202 Accepted with no body
            response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/forward",
                method="POST",
                json=forward_data
            )

            return ActionResult(
                data={
                "result": True,
                "message_id": message_id,
                "operation": "forward",
                "status": "sent"
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "message_id": inputs.get("message_id", ""),
                "operation": "forward",
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("download_email_attachment")
class DownloadEmailAttachmentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]
            attachment_id = inputs["attachment_id"]
            include_content = inputs.get("include_content", True)

            # Get attachment metadata using Microsoft Graph API
            attachment_response = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{attachment_id}",
                method="GET"
            )

            # Extract metadata
            attachment_id_val = attachment_response["id"]
            attachment_name = attachment_response.get("name") or ""
            content_type = attachment_response.get("contentType") or "application/octet-stream"
            size = attachment_response.get("size", 0)
            is_inline = attachment_response.get("isInline", False)

            # Get attachment content if requested
            content = ""
            content_available = False
            content_error_msg = None

            if include_content:
                try:
                    # Use binary fetch helper for /$value endpoint to get raw content
                    # GET /me/messages/{message-id}/attachments/{attachment-id}/$value
                    content_url = f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{attachment_id}/$value"
                    content_bytes = await fetch_binary_content(content_url, context)

                    # Base64 encode for JSON serialization (same as OneDrive/SharePoint)
                    content = base64.b64encode(content_bytes).decode('utf-8')
                    content_available = True

                except Exception as content_error:
                    # If binary content fails, try getting contentBytes from attachment object
                    if "contentBytes" in attachment_response:
                        content = attachment_response["contentBytes"]
                        content_available = True
                    else:
                        content = ""
                        content_available = False
                        content_error_msg = f"Content retrieval failed: {str(content_error)}"

            # Return in same format as OneDrive/SharePoint for consistency
            if content_available and content:
                return ActionResult(
                    data={
                    "file": {
                        "content": content,
                        "name": attachment_name,
                        "contentType": content_type
                    },
                    "metadata": {
                        "id": attachment_id_val,
                        "name": attachment_name,
                        "size": size,
                        "contentType": content_type,
                        "message_id": message_id,
                        "is_inline": is_inline
                    },
                    "result": True
                },
                    cost_usd=0.0
                )
            else:
                return ActionResult(
                    data={
                    "file": {
                        "content": "",
                        "name": attachment_name,
                        "contentType": content_type
                    },
                    "metadata": {
                        "id": attachment_id_val,
                        "name": attachment_name,
                        "size": size,
                        "contentType": content_type,
                        "message_id": message_id,
                        "is_inline": is_inline
                    },
                    "result": False,
                    "error": content_error_msg or "Content not available"
                },
                    cost_usd=0.0
                )

        except Exception as e:
            return ActionResult(
                data={
                "file": {
                    "content": "",
                    "name": "",
                    "contentType": "application/octet-stream"
                },
                "metadata": {
                    "id": inputs.get("attachment_id", ""),
                    "name": "",
                    "size": 0,
                    "contentType": "",
                    "message_id": inputs.get("message_id", ""),
                    "is_inline": False
                },
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("search_emails")
class SearchEmailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            query = inputs["query"]
            limit = inputs.get("limit", 25)
            enable_top_results = inputs.get("enable_top_results", False)

            # Build search request according to Microsoft Graph Search API spec
            search_request = {
                "entityTypes": ["message"],
                "query": {
                    "queryString": query
                },
                "from": 0,
                "size": min(limit, 1000)  # API max is 1000
            }

            if enable_top_results:
                search_request["enableTopResults"] = True

            # Use Microsoft Graph Search API
            response = await context.fetch(
                "https://graph.microsoft.com/v1.0/search/query",
                method="POST",
                json={"requests": [search_request]}
            )

            # Process search results
            messages = []
            total_results = 0

            if response.get("value") and len(response["value"]) > 0:
                search_result = response["value"][0]
                hits = search_result.get("hitsContainers", [])

                if hits:
                    hits_container = hits[0]
                    total_results = hits_container.get("total", 0)

                    for hit in hits_container.get("hits", []):
                        message_data = hit.get("resource", {})

                        # Extract sender information
                        sender = {}
                        if message_data.get("from"):
                            sender = {
                                "emailAddress": message_data["from"].get("emailAddress", {}),
                                "name": message_data["from"].get("emailAddress", {}).get("name", "")
                            }

                        messages.append({
                            "message_id": message_data.get("id") or "",
                            "subject": message_data.get("subject") or "",
                            "sender": sender,
                            "received_datetime": message_data.get("receivedDateTime") or "",
                            "body_preview": message_data.get("bodyPreview") or "",
                            "has_attachments": message_data.get("hasAttachments", False)
                        })

            return ActionResult(
                data={
                "result": True,
                "query": query,
                "total_results": total_results,
                "messages": messages
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "query": inputs.get("query", ""),
                "total_results": 0,
                "messages": [],
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("search_sharepoint_sites")
class SearchSharePointSitesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            search_query = inputs["query"]

            # Build search URL according to Microsoft Graph API spec
            # GET /sites?search={query}
            params = {
                "search": search_query
            }

            # Add optional sorting by createdDateTime if specified
            if inputs.get("order_by_created"):
                params["$orderby"] = "createdDateTime desc"

            response = await context.fetch(
                f"{GRAPH_API_BASE}/sites",
                params=params
            )

            # Process search results according to API response format
            sites = []
            for site in response.get("value", []):
                sites.append({
                    "id": site.get("id") or "",
                    "name": site.get("name") or "",
                    "display_name": site.get("displayName") or "",
                    "description": site.get("description") or "",
                    "web_url": site.get("webUrl") or "",
                    "created_datetime": site.get("createdDateTime") or "",
                    "last_modified_datetime": site.get("lastModifiedDateTime") or ""
                })

            return ActionResult(
                data={
                "result": True,
                "query": search_query,
                "sites": sites,
                "total_sites": len(sites)
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "query": inputs.get("query", ""),
                "sites": [],
                "total_sites": 0,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("get_sharepoint_site_details")
class GetSharePointSiteDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            # Get site details according to Microsoft Graph API spec
            # GET /sites/{site-id}
            response = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}"
            )

            # Process response according to API documentation
            site_details = {
                "id": response.get("id") or "",
                "display_name": response.get("displayName") or "",
                "name": response.get("name") or "",
                "description": response.get("description") or "",
                "web_url": response.get("webUrl") or "",
                "created_datetime": response.get("createdDateTime") or "",
                "last_modified_datetime": response.get("lastModifiedDateTime") or "",
                "is_personal_site": response.get("isPersonalSite", False)
            }

            # Add additional metadata if available
            if "siteCollection" in response:
                site_details["site_collection"] = response["siteCollection"]

            return ActionResult(
                data={
                "result": True,
                "site": site_details
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "site": {},
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_sharepoint_libraries")
class ListSharePointLibrariesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            # Add optional query parameters
            params = {}
            if inputs.get("limit"):
                params["$top"] = inputs["limit"]
            if inputs.get("select_fields"):
                # Filter out invalid field names that don't exist on Drive resource
                valid_drive_fields = {
                    "id", "name", "description", "driveType", "webUrl",
                    "createdDateTime", "lastModifiedDateTime", "createdBy",
                    "lastModifiedBy", "owner", "quota", "sharepointIds", "system"
                }
                requested_fields = [f.strip() for f in inputs["select_fields"].split(",")]
                valid_fields = [f for f in requested_fields if f in valid_drive_fields]

                if valid_fields:
                    params["$select"] = ",".join(valid_fields)

            # List drives (document libraries) according to Microsoft Graph API spec
            # GET /sites/{site-id}/drives
            response = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/drives",
                params=params
            )

            # Process response according to API documentation
            libraries = []
            for drive in response.get("value", []):
                library_data = {
                    "id": drive.get("id", ""),
                    "name": drive.get("name", ""),
                    "description": drive.get("description", ""),
                    "drive_type": drive.get("driveType", ""),
                    "web_url": drive.get("webUrl", ""),
                    "created_datetime": drive.get("createdDateTime", ""),
                    "last_modified_datetime": drive.get("lastModifiedDateTime", "")
                }

                # Add quota information if available
                if "quota" in drive:
                    library_data["quota"] = {
                        "total": drive["quota"].get("total", 0),
                        "remaining": drive["quota"].get("remaining", 0),
                        "used": drive["quota"].get("used", 0),
                        "deleted": drive["quota"].get("deleted", 0),
                        "state": drive["quota"].get("state", "")
                    }

                # Add owner information if available
                if "owner" in drive and "user" in drive["owner"]:
                    library_data["owner"] = {
                        "display_name": drive["owner"]["user"].get("displayName", ""),
                        "email": drive["owner"]["user"].get("email", "")
                    }

                libraries.append(library_data)

            return ActionResult(
                data={
                "result": True,
                "site_id": site_id,
                "libraries": libraries,
                "total_libraries": len(libraries)
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "site_id": inputs.get("site_id", ""),
                "libraries": [],
                "total_libraries": 0,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("search_sharepoint_documents")
class SearchSharePointDocumentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            search_query = inputs["query"]
            limit = inputs.get("limit", 10)

            # Step 1: Get all drives (document libraries) for the site
            # GET /sites/{site-id}/drives
            drives_response = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/drives"
            )

            drives = drives_response.get("value", [])
            if not drives:
                return ActionResult(
                    data={
                    "result": True,
                    "site_id": site_id,
                    "query": search_query,
                    "files": [],
                    "total_files": 0,
                    "drives_searched": 0,
                    "message": "No document libraries found in this site"
                },
                    cost_usd=0.0
                )

            # Step 2: Search each drive individually
            # GET /drives/{drive-id}/root/search(q='{query}')
            encoded_query = urllib.parse.quote(search_query)
            all_files = []
            drives_searched = 0
            search_errors = []

            for drive in drives:
                try:
                    drive_id = drive["id"]
                    drive_name = drive.get("name", "Unknown")
                    drives_searched += 1

                    # Search within this specific drive
                    params = {
                        "$top": limit,
                        "$select": "id,name,size,lastModifiedDateTime,webUrl,folder,file"
                    }
                    api_url = f"{GRAPH_API_BASE}/drives/{drive_id}/root/search(q='{encoded_query}')"
                    drive_response = await context.fetch(api_url, params=params)

                    # Process files from this drive
                    for item in drive_response.get("value", []):
                        file_item = {
                            "id": item["id"],
                            "name": item["name"],
                            "size": item.get("size", 0),
                            "lastModifiedDateTime": item["lastModifiedDateTime"],
                            "webUrl": item["webUrl"],
                            "drive_id": drive_id,
                            "drive_name": drive_name
                        }
                        # Only include folder property if it exists (for folders only)
                        if "folder" in item:
                            file_item["folder"] = item["folder"]
                        # Include file type information if available
                        if "file" in item:
                            file_item["file"] = item["file"]
                        all_files.append(file_item)

                        # Stop if we've reached the limit
                        if len(all_files) >= limit:
                            break

                except Exception as drive_error:
                    search_errors.append(f"Drive '{drive.get('name', drive.get('id'))}': {str(drive_error)}")
                    continue

                # Stop if we've reached the limit
                if len(all_files) >= limit:
                    break

            # Truncate to limit if necessary
            if len(all_files) > limit:
                all_files = all_files[:limit]

            result = {
                "result": True,
                "site_id": site_id,
                "query": search_query,
                "files": all_files,
                "total_files": len(all_files),
                "drives_searched": drives_searched,
                "total_drives": len(drives)
            }

            if search_errors:
                result["search_errors"] = search_errors

            return ActionResult(
                data=result,
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "site_id": inputs.get("site_id", ""),
                "query": inputs.get("query", ""),
                "files": [],
                "total_files": 0,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("read_sharepoint_document")
class ReadSharePointDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            file_id = inputs["file_id"]
            drive_id = inputs.get("drive_id")  # Optional: specific drive ID

            # Get file metadata - use drive-specific endpoint if drive_id provided
            # GET /drives/{drive-id}/items/{file-id} OR /sites/{site-id}/drive/items/{file-id}
            metadata_params = {
                "$select": "id,name,size,mimeType,file,webUrl"
            }

            if drive_id:
                # Use specific drive endpoint for files from non-default libraries
                metadata_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}"
            else:
                # Fallback to site default drive for backward compatibility
                metadata_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}"

            metadata_response = await context.fetch(metadata_url, params=metadata_params)

            file_name = metadata_response["name"]
            file_size = metadata_response.get("size", 0)
            mime_type = metadata_response.get("mimeType", "")
            web_url = metadata_response.get("webUrl", "")

            # Try to get file content (reuse OneDrive logic)
            content = None
            try:
                # For Office documents, use Microsoft's PDF conversion API
                if any(ext in file_name.lower() for ext in ['.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']):
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content?format=pdf"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content?format=pdf"
                    # Use binary fetch to avoid SDK text parsing for converted PDFs
                    content_bytes = await fetch_binary_content(content_url, context)

                    # Encode as base64 for JSON serialization
                    content = base64.b64encode(content_bytes).decode('utf-8')
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "Office document converted to PDF and encoded for LLM processing"
                elif file_name.lower().endswith('.pdf'):
                    # For native PDF files, get content directly (no conversion needed)
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content"
                    # Use binary fetch to avoid SDK text parsing for PDFs
                    content_bytes = await fetch_binary_content(content_url, context)

                    # Encode as base64 for JSON serialization
                    content = base64.b64encode(content_bytes).decode('utf-8')
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "PDF content retrieved and encoded for LLM processing"
                else:
                    # For text files, get raw content
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content"
                    content_response = await context.fetch(content_url, method="GET")

                    # Encode as base64 for consistent handling
                    if isinstance(content_response, bytes):
                        content = base64.b64encode(content_response).decode('utf-8')
                    elif isinstance(content_response, str):
                        # Use latin-1 encoding to preserve binary data in string
                        content = base64.b64encode(content_response.encode('latin-1')).decode('utf-8')
                    else:
                        content = base64.b64encode(str(content_response).encode('latin-1')).decode('utf-8')

                    content_type = mime_type or "text/plain"
                    content_available = True
                    content_info = "Text content retrieved and encoded successfully"

            except Exception as content_error:
                # If content retrieval fails, still return file metadata
                content = None
                content_available = False
                content_info = f"Content retrieval failed: {str(content_error)}"

            # Determine content type based on file extension if mime_type is empty
            if not mime_type:
                if file_name.lower().endswith('.pdf'):
                    mime_type = "application/pdf"
                elif any(ext in file_name.lower() for ext in ['.docx', '.doc']):
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif any(ext in file_name.lower() for ext in ['.xlsx', '.xls']):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif any(ext in file_name.lower() for ext in ['.pptx', '.ppt']):
                    mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    mime_type = "application/octet-stream"

            # Return in same format as OneDrive for consistency
            if content_available and content:
                return ActionResult(
                    data={
                    "file": {
                        "content": content,
                        "name": file_name,
                        "contentType": content_type
                    },
                    "metadata": {
                        "id": file_id,
                        "name": file_name,
                        "size": file_size,
                        "mimeType": mime_type,
                        "webUrl": web_url,
                        "site_id": site_id,
                        "drive_id": drive_id
                    },
                    "result": True
                },
                    cost_usd=0.0
                )
            else:
                # Set fallback content type for failed cases
                fallback_content_type = mime_type
                if file_name.lower().endswith('.pdf'):
                    fallback_content_type = "application/pdf"

                return ActionResult(
                    data={
                    "file": {
                        "content": "",
                        "name": file_name,
                        "contentType": fallback_content_type
                    },
                    "metadata": {
                        "id": file_id,
                        "name": file_name,
                        "size": file_size,
                        "mimeType": mime_type,
                        "webUrl": web_url,
                        "site_id": site_id,
                        "drive_id": drive_id
                    },
                    "result": False,
                    "error": content_info
                },
                    cost_usd=0.0
                )

        except Exception as e:
            return ActionResult(
                data={
                "file": {
                    "content": "",
                    "name": "",
                    "contentType": "application/octet-stream"
                },
                "metadata": {
                    "id": inputs.get("file_id", ""),
                    "name": "",
                    "site_id": inputs.get("site_id", "")
                },
                "result": False,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("list_sharepoint_pages")
class ListSharePointPagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            # Build request according to Microsoft Graph API spec
            # GET /sites/{site-id}/pages/microsoft.graph.sitePage
            params = {}

            # Add optional query parameters
            if inputs.get("limit"):
                params["$top"] = inputs["limit"]
            if inputs.get("order_by"):
                params["$orderby"] = inputs["order_by"]
            if inputs.get("select_fields"):
                params["$select"] = inputs["select_fields"]
            else:
                # Default selection for useful page metadata
                params["$select"] = "id,name,webUrl,title,pageLayout,createdDateTime,lastModifiedDateTime,createdBy,lastModifiedBy"

            response = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/pages/microsoft.graph.sitePage",
                params=params
            )

            # Process response according to API documentation
            pages = []
            for page in response.get("value", []):
                page_data = {
                    "id": page.get("id", ""),
                    "name": page.get("name", ""),
                    "title": page.get("title", ""),
                    "web_url": page.get("webUrl", ""),
                    "page_layout": page.get("pageLayout", ""),
                    "created_datetime": page.get("createdDateTime", ""),
                    "last_modified_datetime": page.get("lastModifiedDateTime", "")
                }

                # Add creator information if available
                if "createdBy" in page and "user" in page["createdBy"]:
                    page_data["created_by"] = {
                        "display_name": page["createdBy"]["user"].get("displayName", ""),
                        "email": page["createdBy"]["user"].get("email", "")
                    }

                # Add last modifier information if available
                if "lastModifiedBy" in page and "user" in page["lastModifiedBy"]:
                    page_data["last_modified_by"] = {
                        "display_name": page["lastModifiedBy"]["user"].get("displayName", ""),
                        "email": page["lastModifiedBy"]["user"].get("email", "")
                    }

                pages.append(page_data)

            return ActionResult(
                data={
                "result": True,
                "site_id": site_id,
                "pages": pages,
                "total_pages": len(pages)
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "site_id": inputs.get("site_id", ""),
                "pages": [],
                "total_pages": 0,
                "error": str(e)
            },
                cost_usd=0.0
            )

@microsoft365.action("read_sharepoint_page_content")
class ReadSharePointPageContentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            page_id = inputs["page_id"]
            include_content = inputs.get("include_content", True)

            # Build request according to Microsoft Graph API spec
            # GET /sites/{site-id}/pages/{page-id}/microsoft.graph.sitePage
            params = {
                "$select": "id,name,webUrl,title,pageLayout,createdDateTime,lastModifiedDateTime,createdBy,lastModifiedBy"
            }

            # Include page content if requested
            if include_content:
                params["$expand"] = "canvasLayout"

            response = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/pages/{page_id}/microsoft.graph.sitePage",
                params=params
            )

            # Process response according to API documentation
            page_data = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "title": response.get("title", ""),
                "web_url": response.get("webUrl", ""),
                "page_layout": response.get("pageLayout", ""),
                "created_datetime": response.get("createdDateTime", ""),
                "last_modified_datetime": response.get("lastModifiedDateTime", "")
            }

            # Add creator information if available
            if "createdBy" in response and "user" in response["createdBy"]:
                page_data["created_by"] = {
                    "display_name": response["createdBy"]["user"].get("displayName", ""),
                    "email": response["createdBy"]["user"].get("email", "")
                }

            # Add page content if available
            if include_content and "canvasLayout" in response:
                page_data["content"] = response["canvasLayout"]

            return ActionResult(
                data={
                "result": True,
                "site_id": site_id,
                "page": page_data
            },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                "result": False,
                "site_id": inputs.get("site_id", ""),
                "page": {},
                "error": str(e)
            },
                cost_usd=0.0
            )
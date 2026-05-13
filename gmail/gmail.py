from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError

from typing import Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import html2text
import bleach

gmail = Integration.load()


def create_email_message(body: str, files: list = None, is_html: bool = False) -> MIMEMultipart:
    """Create email message with optional files and HTML support.

    Args:
        body: Email body text or HTML content
        files: List of file dictionaries with name, contentType, and content
        is_html: Whether the body content is HTML that should be rendered as rich email

    Returns:
        MIMEMultipart or MIMEText message object
    """
    if is_html:
        # Sanitize HTML content to prevent XSS and other security issues
        allowed_tags = [
            "p",
            "br",
            "strong",
            "em",
            "u",
            "i",
            "b",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "blockquote",
            "div",
            "span",
            "a",
            "img",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "hr",
            "pre",
            "code",
        ]

        allowed_attributes = {
            "*": ["style", "class"],
            "a": ["href", "title"],
            "img": ["src", "alt", "title", "width", "height"],
            "table": ["border", "cellpadding", "cellspacing"],
            "th": ["colspan", "rowspan"],
            "td": ["colspan", "rowspan"],
        }

        allowed_protocols = ["http", "https", "mailto"]

        # Sanitize the HTML content
        sanitized_body = bleach.clean(
            body,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True,  # Remove disallowed tags entirely
        )

        # Generate plain text version from sanitized HTML for better email client compatibility
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0  # No line wrapping
        plain_text = h.handle(sanitized_body)

        if files:
            # HTML email with attachments: multipart/mixed containing multipart/alternative + files
            message = MIMEMultipart("mixed")

            # Create alternative container for HTML and plain text versions
            alternative_container = MIMEMultipart("alternative")

            # Add plain text version first (preferred order for email clients)
            text_part = MIMEText(plain_text, "plain", "utf-8")
            alternative_container.attach(text_part)

            # Add HTML version
            html_part = MIMEText(sanitized_body, "html", "utf-8")
            alternative_container.attach(html_part)

            # Attach alternative container to main message
            message.attach(alternative_container)
        else:
            # HTML email without attachments: simple multipart/alternative
            message = MIMEMultipart("alternative")

            # Add plain text version first (preferred order for email clients)
            text_part = MIMEText(plain_text, "plain", "utf-8")
            message.attach(text_part)

            # Add HTML version
            html_part = MIMEText(sanitized_body, "html", "utf-8")
            message.attach(html_part)

    elif files:
        # Plain text email with attachments: multipart/mixed
        message = MIMEMultipart("mixed")

        # Add the text body
        text_part = MIMEText(body, "plain", "utf-8")
        message.attach(text_part)
    else:
        # Simple plain text email
        message = MIMEText(body, "plain", "utf-8")

    # Add files if present
    if files:
        for file_item in files:
            part = MIMEBase("application", "octet-stream")

            # Decode base64 content. The input 'content' might be base64url encoded
            # (e.g., if it came from a read_email action) and may lack padding.
            # We use urlsafe_b64decode and ensure correct padding.
            content_as_string = file_item["content"]

            # Add necessary padding. len() on string is fine for calculating padding length.
            padded_content_string = content_as_string + "=" * (-len(content_as_string) % 4)

            # base64.urlsafe_b64decode can take an ASCII string or bytes.
            # Encoding to 'ascii' bytes first is a robust practice.
            file_binary_data = base64.urlsafe_b64decode(padded_content_string.encode("ascii"))
            part.set_payload(file_binary_data)

            # Encode the payload in base64
            encoders.encode_base64(part)

            # Add header with filename
            part.add_header("Content-Disposition", f"attachment; filename= {file_item['name']}")

            # Set content type if provided
            if "contentType" in file_item:
                part.set_type(file_item["contentType"])

            message.attach(part)

    return message


def build_credentials(context: ExecutionContext):
    """Build Google credentials from ExecutionContext.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        Google credentials object
    """
    # Extract access token from context.auth.credentials
    access_token = context.auth.get("credentials", {}).get("access_token", "")

    creds = Credentials(token=access_token, token_uri="https://oauth2.googleapis.com/token")  # nosec B106

    return creds


def build_gmail_service(context: ExecutionContext):
    """Build Gmail service object.

    Args:
        context: ExecutionContext containing authentication information

    Returns:
        Gmail service object
    """
    credentials = build_credentials(context)
    service = build("gmail", "v1", credentials=credentials)
    return service


class GmailMessageParser:
    @staticmethod
    def decode_body(data: str) -> str:
        """Decode base64 encoded message body."""
        try:
            return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def extract_plain_text(payload: Dict[str, Any], depth: int = 0, max_depth: int = 5) -> str:
        """Extract plain text content from message payload.

        Args:
            payload: The message payload to extract text from
            depth: Current recursion depth (internal use)
            max_depth: Maximum recursion depth to prevent stack overflow
        """
        # Prevent excessive recursion
        if depth > max_depth:
            return "[Email content too deeply nested to extract]"

        # Case 1: Body data directly in the payload (simple emails)
        if "body" in payload and "data" in payload["body"]:
            return GmailMessageParser.decode_body(payload["body"]["data"])

        # Case 2: Simple email with mimeType text/plain
        if payload.get("mimeType") == "text/plain" and "body" in payload and "data" in payload["body"]:
            return GmailMessageParser.decode_body(payload["body"]["data"])

        # Case 3: Handle multipart messages recursively
        if "parts" in payload:
            # First, try to find a text/plain part
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and "body" in part and "data" in part["body"]:
                    return GmailMessageParser.decode_body(part["body"]["data"])

            # If no text/plain, try to find content recursively in each part
            for part in payload["parts"]:
                text = GmailMessageParser.extract_plain_text(part, depth + 1, max_depth)
                if text:
                    return text

        return ""

    @staticmethod
    def get_header_value(headers: list, name: str) -> str:
        """Extract header value by name."""
        for header in headers:
            if header["name"].lower() == name.lower():
                return header["value"]
        return ""

    @staticmethod
    def parse_email_list(email_str: str) -> list:
        """Parse a comma-separated list of email addresses into an array."""
        if not email_str:
            return []
        # Split by comma and strip whitespace from each email
        return [email.strip() for email in email_str.split(",")]

    @staticmethod
    def extract_files(
        service, user_id: str, message_id: str, payload: Dict[str, Any], depth: int = 0, max_depth: int = 5
    ) -> list:
        """Extract files from message payload.

        Args:
            service: Gmail service object
            user_id: User ID for Gmail API calls
            message_id: Message ID for file retrieval
            payload: The message payload to extract files from
            depth: Current recursion depth (internal use)
            max_depth: Maximum recursion depth to prevent stack overflow
        """
        files = []

        # Prevent excessive recursion
        if depth > max_depth:
            return files

        # Check if this part has an attachment (file)
        if "body" in payload and "attachmentId" in payload["body"]:
            filename = payload.get("filename", "attachment")
            if filename:
                try:
                    attachment_data = (
                        service.users()
                        .messages()
                        .attachments()
                        .get(userId=user_id, messageId=message_id, id=payload["body"]["attachmentId"])
                        .execute()
                    )

                    # Convert Gmail's base64url to standard base64
                    base64url_string = attachment_data["data"]
                    # Add padding for urlsafe_b64decode
                    padded_base64url_string = base64url_string + "=" * (-len(base64url_string) % 4)
                    # Decode from base64url (handles '-' and '_')
                    binary_data = base64.urlsafe_b64decode(padded_base64url_string)
                    # Re-encode to standard base64 (uses '+' and '/', adds padding)
                    standard_base64_bytes = base64.b64encode(binary_data)
                    # Decode bytes to string for JSON output
                    standard_base64_string = standard_base64_bytes.decode("utf-8")

                    files.append(
                        {
                            "name": filename,
                            "contentType": payload.get("mimeType", "application/octet-stream"),
                            "content": standard_base64_string,  # Store the standard base64 string
                        }
                    )
                except Exception as e:
                    print(f"Error retrieving or converting file {filename}: {e}")  # Updated log

        if "parts" in payload:
            for part in payload["parts"]:
                files.extend(GmailMessageParser.extract_files(service, user_id, message_id, part, depth + 1, max_depth))

        return files

    @staticmethod
    def parse_message_with_snippet(raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Gmail message into standardized format."""
        headers = raw_message["payload"]["headers"]
        cc_header = GmailMessageParser.get_header_value(headers, "Cc")

        return {
            "id": raw_message["id"],
            "thread_id": raw_message["threadId"],
            "subject": GmailMessageParser.get_header_value(headers, "Subject"),
            "from": GmailMessageParser.get_header_value(headers, "From"),
            "to": GmailMessageParser.get_header_value(headers, "To"),
            "cc": GmailMessageParser.parse_email_list(cc_header),
            "date": GmailMessageParser.get_header_value(headers, "Date"),
            "snippet": raw_message.get("snippet", ""),
        }

    @staticmethod
    def parse_message_with_body(raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Gmail message into standardized format."""
        headers = raw_message["payload"]["headers"]
        cc_header = GmailMessageParser.get_header_value(headers, "Cc")

        return {
            "id": raw_message["id"],
            "thread_id": raw_message["threadId"],
            "subject": GmailMessageParser.get_header_value(headers, "Subject"),
            "from": GmailMessageParser.get_header_value(headers, "From"),
            "to": GmailMessageParser.get_header_value(headers, "To"),
            "cc": GmailMessageParser.parse_email_list(cc_header),
            "date": GmailMessageParser.get_header_value(headers, "Date"),
            "body": GmailMessageParser.extract_plain_text(raw_message["payload"]),
        }


@gmail.action("mark_emails_as_unread")
class MarkEmailsAsUnread(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            ids = inputs["ids"]

            body = {"ids": ids, "addLabelIds": ["UNREAD"], "removeLabelIds": []}

            request = service.users().messages().batchModify(userId=user_id, body=body)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("mark_emails_as_read")
class MarkEmailsAsRead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            ids = inputs["ids"]

            body = {"ids": ids, "addLabelIds": [], "removeLabelIds": ["UNREAD"]}

            request = service.users().messages().batchModify(userId=user_id, body=body)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("get_user_info")
class GetUserInfo(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]

            request = service.users().getProfile(userId=user_id)
            result = request.execute()

            return ActionResult(
                data={
                    "user_info": {
                        "email_address": result["emailAddress"],
                        "messages_total": result["messagesTotal"],
                        "threads_total": result["threadsTotal"],
                        "history_id": result["historyId"],
                    },
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("read_email")
class ReadEmail(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            email_id = inputs["email_id"]

            # Fetch the full email message
            message_data = service.users().messages().get(userId=user_id, id=email_id, format="full").execute()

            # Parse the main email fields (without files)
            email_object = GmailMessageParser.parse_message_with_body(message_data)

            # Extract files separately
            extracted_files = GmailMessageParser.extract_files(
                service, user_id, message_data["id"], message_data["payload"]
            )

            return ActionResult(data={"email": email_object, "files": extracted_files}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("send_email")
class SendEmail(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Send an email using Gmail API."""

        try:
            service = build_gmail_service(context)
            user_id = "me"

            # Create the email message
            message = {"raw": self._create_raw_email(inputs)}

            # Send the email using Gmail API
            request = service.users().messages().send(userId=user_id, body=message)
            response = request.execute()

            return ActionResult(data={"id": response.get("id", "")}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

    def _create_raw_email(self, inputs: Dict[str, Any]) -> str:
        """Create base64 encoded email message."""
        # Determine if HTML formatting is requested
        body_format = inputs.get("body_format", "text")
        is_html = body_format == "html"

        # Create message with optional files and HTML support
        input_files = inputs.get("files", [])
        message = create_email_message(inputs["body"], input_files, is_html)

        # Handle multiple recipients in 'to' field
        if isinstance(inputs["to"], list):
            message["to"] = ", ".join(inputs["to"])
        else:
            message["to"] = inputs["to"]

        # Handle CC recipients if present
        if "cc" in inputs:
            if isinstance(inputs["cc"], list):
                message["cc"] = ", ".join(inputs["cc"])
            else:
                message["cc"] = inputs["cc"]

        message["subject"] = inputs["subject"]

        # Add from if provided
        if "from" in inputs and inputs["from"] != "me":
            message["from"] = inputs["from"]

        # Encode the message
        return base64.urlsafe_b64encode(message.as_bytes()).decode()


@gmail.action("reply_to_thread")
class ReplyToThread(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")
            thread_id = inputs["thread_id"]
            message_id = inputs["message_id"]
            body = inputs["body"]

            # Fetch the original message to get headers
            original_request = service.users().messages().get(userId=user_id, id=message_id)
            original_message = original_request.execute()

            # Parse original message headers
            headers = original_message["payload"]["headers"]
            original_subject = GmailMessageParser.get_header_value(headers, "Subject")
            original_from = GmailMessageParser.get_header_value(headers, "From")
            message_id_header = GmailMessageParser.get_header_value(headers, "Message-ID")
            references = GmailMessageParser.get_header_value(headers, "References")

            # Determine if HTML formatting is requested
            body_format = inputs.get("body_format", "text")
            is_html = body_format == "html"

            # Create message with optional files and HTML support
            input_files = inputs.get("files", [])
            message = create_email_message(body, input_files, is_html)

            # Set recipients
            recipients = [original_from]
            if "to" in inputs and inputs["to"]:
                recipients.extend(inputs["to"])
            message["to"] = ", ".join(recipients)

            # Add CC if provided
            if "cc" in inputs and inputs["cc"]:
                message["cc"] = ", ".join(inputs["cc"])

            message["subject"] = (
                f"Re: {original_subject}" if not original_subject.startswith("Re:") else original_subject
            )

            # Add threading headers
            message["In-Reply-To"] = message_id_header
            # Combine existing references with the new message ID
            new_references = f"{references} {message_id_header}" if references else message_id_header
            message["References"] = new_references

            # Add thread ID to keep messages grouped
            message_payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode(), "threadId": thread_id}

            # Send the reply
            request = service.users().messages().send(userId=user_id, body=message_payload)
            response = request.execute()

            return ActionResult(data={"id": response.get("id", "")}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("read_inbox")
class ReadInbox(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]

            # Build query based on scope
            scope = inputs.get("scope", "all")

            if scope == "unread":
                query = "is:unread in:inbox"
            elif scope == "read":
                query = "-is:unread in:inbox"
            else:  # 'all'
                query = "in:inbox"

            request_params = {"userId": user_id, "q": query}
            if "pageToken" in inputs:
                request_params["pageToken"] = inputs["pageToken"]

            # Get list of messages
            request = service.users().messages().list(**request_params)
            messages = request.execute()

            inbox_emails = []
            for message in messages.get("messages", []):
                # Get individual message details
                message_request = service.users().messages().get(userId=user_id, id=message["id"])
                email_with_id = message_request.execute()

                inbox_emails.append(GmailMessageParser.parse_message_with_snippet(email_with_id))

            # Prepare response with pagination support
            response = {"emails": inbox_emails}

            # Add nextPageToken if present in Gmail API response
            if "nextPageToken" in messages:
                response["nextPageToken"] = messages["nextPageToken"]

            return ActionResult(data=response, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("read_all_mail")
class ReadAllMail(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]

            # No label filtering - return all mail
            include_spam_trash = inputs.get("include_spam_trash", False)
            scope = inputs.get("scope", "all")

            if scope == "unread":
                query = "is:unread"
            elif scope == "read":
                query = "-is:unread"
            else:  # 'all'
                query = ""

            request_params = {"userId": user_id, "includeSpamTrash": include_spam_trash}
            if query:
                request_params["q"] = query
            if "pageToken" in inputs:
                request_params["pageToken"] = inputs["pageToken"]

            # Get list of messages
            request = service.users().messages().list(**request_params)
            messages = request.execute()

            all_emails = []
            for message in messages.get("messages", []):
                # Get individual message details
                message_request = service.users().messages().get(userId=user_id, id=message["id"])
                email_with_id = message_request.execute()

                all_emails.append(GmailMessageParser.parse_message_with_snippet(email_with_id))

            # Prepare response with pagination support
            response = {"emails": all_emails}

            # Add nextPageToken if present in Gmail API response
            if "nextPageToken" in messages:
                response["nextPageToken"] = messages["nextPageToken"]

            return ActionResult(data=response, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("list_labels")
class ListLabels(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]

            # Get list of labels
            request = service.users().labels().list(userId=user_id)
            result = request.execute()

            labels = result.get("labels", [])

            # Filter labels based on type if specified
            if "label_type" in inputs:
                label_type = inputs["label_type"].lower()
                if label_type == "user":
                    labels = [label for label in labels if label.get("type") == "user"]
                elif label_type == "system":
                    labels = [label for label in labels if label.get("type") == "system"]

            return ActionResult(data={"labels": labels}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("list_emails_by_label")
class ListEmailsByLabel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            label_names = inputs["label_names"]

            # Build query for label filtering
            if isinstance(label_names, list):
                # Multiple labels - emails must have ALL specified labels
                label_query = " ".join([f"label:{label_name}" for label_name in label_names])
            else:
                # Single label
                label_query = f"label:{label_names}"

            # Default to inbox-only emails unless include_archived is True
            # Exception: if user explicitly requests INBOX label, don't add inbox restriction
            include_archived = inputs.get("include_archived", False)
            if not include_archived:
                # Check if INBOX is already in the query (case-insensitive)
                label_names_list = label_names if isinstance(label_names, list) else [label_names]
                inbox_already_specified = any(name.upper() == "INBOX" for name in label_names_list)

                if not inbox_already_specified:
                    label_query += " in:inbox"

            # Build request parameters
            request_params = {"userId": user_id, "q": label_query}

            if "pageToken" in inputs:
                request_params["pageToken"] = inputs["pageToken"]
            if "maxResults" in inputs:
                request_params["maxResults"] = inputs["maxResults"]

            # Get list of messages
            request = service.users().messages().list(**request_params)
            messages = request.execute()

            emails = []
            for message in messages.get("messages", []):
                # Get individual message details
                message_request = service.users().messages().get(userId=user_id, id=message["id"])
                email_with_id = message_request.execute()

                # Trust the Gmail API query - no additional filtering needed
                emails.append(GmailMessageParser.parse_message_with_snippet(email_with_id))

            # Prepare response with pagination support
            response = {"emails": emails}

            # Add nextPageToken if present in Gmail API response
            if "nextPageToken" in messages:
                response["nextPageToken"] = messages["nextPageToken"]

            return ActionResult(data=response, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("add_labels_to_emails")
class AddLabelsToEmails(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            message_ids = inputs["message_ids"]
            label_ids = inputs["label_ids"]

            body = {"ids": message_ids, "addLabelIds": label_ids, "removeLabelIds": []}

            request = service.users().messages().batchModify(userId=user_id, body=body)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("remove_labels_from_emails")
class RemoveLabelsFromEmails(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            message_ids = inputs["message_ids"]
            label_ids = inputs["label_ids"]

            body = {"ids": message_ids, "addLabelIds": [], "removeLabelIds": label_ids}

            request = service.users().messages().batchModify(userId=user_id, body=body)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("create_label")
class CreateLabel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]

            # Build the label object for creation
            label_body = {
                "name": inputs["name"],
                "messageListVisibility": inputs.get("messageListVisibility", "show"),
                "labelListVisibility": inputs.get("labelListVisibility", "labelShow"),
            }

            # Add color if provided
            if "textColor" in inputs or "backgroundColor" in inputs:
                color = {}
                if "textColor" in inputs:
                    color["textColor"] = inputs["textColor"]
                if "backgroundColor" in inputs:
                    color["backgroundColor"] = inputs["backgroundColor"]
                label_body["color"] = color

            # Create the label using Gmail API
            request = service.users().labels().create(userId=user_id, body=label_body)
            created_label = request.execute()

            return ActionResult(
                data={
                    "label": {
                        "id": created_label.get("id", ""),
                        "name": created_label.get("name", ""),
                        "type": created_label.get("type", "user"),
                        "messageListVisibility": created_label.get("messageListVisibility", "show"),
                        "labelListVisibility": created_label.get("labelListVisibility", "labelShow"),
                    },
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("get_thread_emails")
class GetThreadEmails(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            thread_id = inputs["thread_id"]

            # Get the thread with all messages
            thread_request = service.users().threads().get(userId=user_id, id=thread_id)
            thread_data = thread_request.execute()

            thread_emails = []
            for message in thread_data.get("messages", []):
                # Parse each message in the thread
                parsed_email = GmailMessageParser.parse_message_with_snippet(message)
                thread_emails.append(parsed_email)

            # Sort emails by date to ensure chronological order
            # Parse the date string and sort by it
            def parse_date_for_sorting(email):
                try:
                    # Gmail date format is typically: "Mon, 1 Jan 2024 12:00:00 +0000"
                    from email.utils import parsedate_to_datetime

                    return parsedate_to_datetime(email["date"])
                except Exception:
                    # Fallback: use the email ID as a rough ordering mechanism
                    return email["id"]

            thread_emails.sort(key=parse_date_for_sorting)

            return ActionResult(data={"thread_id": thread_id, "emails": thread_emails}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("archive_emails")
class ArchiveEmails(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs["user_id"]
            ids = inputs["ids"]

            body = {"ids": ids, "addLabelIds": [], "removeLabelIds": ["INBOX"]}

            request = service.users().messages().batchModify(userId=user_id, body=body)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("create_draft")
class CreateDraft(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")

            # Get user's email address for From header if not provided
            if "from" not in inputs or not inputs["from"] or inputs["from"] == "me":
                profile = service.users().getProfile(userId=user_id).execute()
                inputs["from"] = profile["emailAddress"]

            # Check if this is a reply (thread_id and message_id provided)
            is_reply = (
                "thread_id" in inputs
                and inputs.get("thread_id")
                and "message_id" in inputs
                and inputs.get("message_id")
            )

            if is_reply:
                # Handle reply draft with threading headers
                thread_id = inputs["thread_id"]
                message_id = inputs["message_id"]

                # Fetch the original message to get proper headers and recipient info
                original_message = service.users().messages().get(userId=user_id, id=message_id).execute()
                headers = original_message["payload"]["headers"]

                # Get original sender to set as recipient for the reply
                original_from = GmailMessageParser.get_header_value(headers, "From")

                # Get Message-ID header for proper threading
                message_id_header = GmailMessageParser.get_header_value(headers, "Message-ID")

                # Get original subject for Re: prefix
                original_subject = GmailMessageParser.get_header_value(headers, "Subject")

                # Get References header for threading
                references = GmailMessageParser.get_header_value(headers, "References")

                # Set recipients: if not provided, default to original sender
                if "to" not in inputs or not inputs["to"]:
                    inputs["to"] = [original_from]
                elif isinstance(inputs["to"], str):
                    inputs["to"] = [inputs["to"]]
                else:
                    # If 'to' is provided as list, prepend original sender
                    if original_from not in inputs["to"]:
                        inputs["to"] = [original_from] + list(inputs["to"])

                # Set subject with Re: prefix if not provided
                if "subject" not in inputs or not inputs["subject"]:
                    if original_subject.startswith("Re:"):
                        inputs["subject"] = original_subject
                    else:
                        inputs["subject"] = f"Re: {original_subject}"

                # Create the draft reply message with threading headers
                draft_message = {
                    "raw": self._create_raw_email(inputs, message_id_header, references),
                    "threadId": thread_id,
                }
            else:
                # Create a new draft (not a reply)
                draft_message = {"raw": self._create_raw_email(inputs)}

            # Create the draft using Gmail API
            draft_body = {"message": draft_message}
            request = service.users().drafts().create(userId=user_id, body=draft_body)
            response = request.execute()

            return ActionResult(
                data={
                    "draft": {
                        "id": response.get("id", ""),
                        "message": {
                            "id": response.get("message", {}).get("id", ""),
                            "threadId": response.get("message", {}).get("threadId", ""),
                        },
                    },
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))

    def _create_raw_email(self, inputs: Dict[str, Any], message_id_header: str = None, references: str = None) -> str:
        """Create base64 encoded email message for draft."""
        # Determine if HTML formatting is requested
        body_format = inputs.get("body_format", "text")
        is_html = body_format == "html"

        # Create message with optional files and HTML support
        input_files = inputs.get("files", [])
        body = inputs.get("body", "")
        message = create_email_message(body, input_files, is_html)

        # Add From header (REQUIRED for drafts to display properly in Gmail)
        if "from" in inputs and inputs["from"]:
            message["from"] = inputs["from"]

        # Add reply headers for proper threading if provided
        if message_id_header:
            message["In-Reply-To"] = message_id_header
            # Combine existing references with the new message ID
            if references:
                message["References"] = f"{references} {message_id_header}"
            else:
                message["References"] = message_id_header

        # Handle recipients
        if "to" in inputs and inputs["to"]:
            if isinstance(inputs["to"], list):
                message["to"] = ", ".join(inputs["to"])
            else:
                message["to"] = inputs["to"]

        # Handle CC recipients if present
        if "cc" in inputs and inputs["cc"]:
            if isinstance(inputs["cc"], list):
                message["cc"] = ", ".join(inputs["cc"])
            else:
                message["cc"] = inputs["cc"]

        # Handle BCC recipients if present
        if "bcc" in inputs and inputs["bcc"]:
            if isinstance(inputs["bcc"], list):
                message["bcc"] = ", ".join(inputs["bcc"])
            else:
                message["bcc"] = inputs["bcc"]

        # Set subject
        if "subject" in inputs and inputs["subject"]:
            message["subject"] = inputs["subject"]

        # Encode the message
        return base64.urlsafe_b64encode(message.as_bytes()).decode()


@gmail.action("update_draft")
class UpdateDraft(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")
            draft_id = inputs["draft_id"]

            # Get user's email address for From header if not provided
            if "from" not in inputs or not inputs["from"] or inputs["from"] == "me":
                profile = service.users().getProfile(userId=user_id).execute()
                inputs["from"] = profile["emailAddress"]

            # Fetch the existing draft to preserve threadId and threading headers
            existing_draft = service.users().drafts().get(userId=user_id, id=draft_id, format="metadata").execute()
            existing_thread_id = existing_draft.get("message", {}).get("threadId")

            # Get existing headers for threading info (In-Reply-To, References)
            existing_headers = existing_draft.get("message", {}).get("payload", {}).get("headers", [])
            message_id_header = None
            references = None
            for header in existing_headers:
                if header["name"] == "In-Reply-To":
                    message_id_header = header["value"]
                elif header["name"] == "References":
                    references = header["value"]

            # Create the updated email message with threading headers if this was a reply
            draft_message = {"raw": self._create_raw_email(inputs, message_id_header, references)}

            # Preserve threadId if the draft was part of a thread
            if existing_thread_id:
                draft_message["threadId"] = existing_thread_id

            # Update the draft using Gmail API
            draft_body = {"message": draft_message}
            request = service.users().drafts().update(userId=user_id, id=draft_id, body=draft_body)
            response = request.execute()

            return ActionResult(
                data={
                    "draft": {
                        "id": response.get("id", ""),
                        "message": {
                            "id": response.get("message", {}).get("id", ""),
                            "threadId": response.get("message", {}).get("threadId", ""),
                        },
                    },
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))

    def _create_raw_email(self, inputs: Dict[str, Any], message_id_header: str = None, references: str = None) -> str:
        """Create base64 encoded email message for draft."""
        # Determine if HTML formatting is requested
        body_format = inputs.get("body_format", "text")
        is_html = body_format == "html"

        # Create message with optional files and HTML support
        input_files = inputs.get("files", [])
        body = inputs.get("body", "")
        message = create_email_message(body, input_files, is_html)

        # Add From header (REQUIRED for drafts to display properly in Gmail)
        if "from" in inputs and inputs["from"]:
            message["from"] = inputs["from"]

        # Add reply headers for proper threading if provided (preserved from existing draft)
        if message_id_header:
            message["In-Reply-To"] = message_id_header
            # Combine existing references with the message ID
            if references:
                message["References"] = references
            else:
                message["References"] = message_id_header

        # Handle recipients
        if "to" in inputs and inputs["to"]:
            if isinstance(inputs["to"], list):
                message["to"] = ", ".join(inputs["to"])
            else:
                message["to"] = inputs["to"]

        # Handle CC recipients if present
        if "cc" in inputs and inputs["cc"]:
            if isinstance(inputs["cc"], list):
                message["cc"] = ", ".join(inputs["cc"])
            else:
                message["cc"] = inputs["cc"]

        # Handle BCC recipients if present
        if "bcc" in inputs and inputs["bcc"]:
            if isinstance(inputs["bcc"], list):
                message["bcc"] = ", ".join(inputs["bcc"])
            else:
                message["bcc"] = inputs["bcc"]

        # Set subject
        if "subject" in inputs and inputs["subject"]:
            message["subject"] = inputs["subject"]

        # Encode the message
        return base64.urlsafe_b64encode(message.as_bytes()).decode()


@gmail.action("list_drafts")
class ListDrafts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")

            # Build request parameters
            request_params = {"userId": user_id}

            if "pageToken" in inputs:
                request_params["pageToken"] = inputs["pageToken"]

            if "maxResults" in inputs:
                request_params["maxResults"] = inputs["maxResults"]

            if "q" in inputs:
                request_params["q"] = inputs["q"]

            if "includeSpamTrash" in inputs:
                request_params["includeSpamTrash"] = inputs["includeSpamTrash"]

            # Get list of drafts
            request = service.users().drafts().list(**request_params)
            response = request.execute()

            drafts = response.get("drafts", [])

            # Prepare response with pagination support
            result = {"drafts": drafts}

            # Add pagination info if present
            if "nextPageToken" in response:
                result["nextPageToken"] = response["nextPageToken"]

            if "resultSizeEstimate" in response:
                result["resultSizeEstimate"] = response["resultSizeEstimate"]

            return ActionResult(data=result, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("get_draft")
class GetDraft(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")
            draft_id = inputs["draft_id"]
            format_type = inputs.get("format", "full")

            # Get the draft with specified format
            request = service.users().drafts().get(userId=user_id, id=draft_id, format=format_type)
            draft_data = request.execute()

            # Parse the draft message if format is full
            draft_info = {
                "id": draft_data.get("id", ""),
                "message": {
                    "id": draft_data.get("message", {}).get("id", ""),
                    "threadId": draft_data.get("message", {}).get("threadId", ""),
                },
            }

            extracted_files = []

            # If format is full, parse the message content
            if format_type == "full" and "message" in draft_data:
                message_data = draft_data["message"]
                if "payload" in message_data:
                    # Parse message headers and content
                    headers = message_data["payload"].get("headers", [])

                    draft_info["message"].update(
                        {
                            "subject": GmailMessageParser.get_header_value(headers, "Subject"),
                            "from": GmailMessageParser.get_header_value(headers, "From"),
                            "to": GmailMessageParser.get_header_value(headers, "To"),
                            "cc": GmailMessageParser.parse_email_list(
                                GmailMessageParser.get_header_value(headers, "Cc")
                            ),
                            "bcc": GmailMessageParser.parse_email_list(
                                GmailMessageParser.get_header_value(headers, "Bcc")
                            ),
                            "body": GmailMessageParser.extract_plain_text(message_data["payload"]),
                        }
                    )

                    # Extract files if present
                    extracted_files = GmailMessageParser.extract_files(
                        service, user_id, message_data["id"], message_data["payload"]
                    )

            return ActionResult(data={"draft": draft_info, "files": extracted_files}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("send_draft")
class SendDraft(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")
            draft_id = inputs["draft_id"]

            # Send the draft using Gmail API
            draft_body = {"id": draft_id}
            request = service.users().drafts().send(userId=user_id, body=draft_body)
            response = request.execute()

            return ActionResult(
                data={
                    "message": {"id": response.get("id", ""), "threadId": response.get("threadId", "")},
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@gmail.action("delete_draft")
class DeleteDraft(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_gmail_service(context)
            user_id = inputs.get("user_id", "me")
            draft_id = inputs["draft_id"]

            # Delete the draft using Gmail API
            request = service.users().drafts().delete(userId=user_id, id=draft_id)
            request.execute()

            return ActionResult(data={}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

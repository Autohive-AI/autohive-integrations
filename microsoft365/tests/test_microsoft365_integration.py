import unittest
from unittest.mock import AsyncMock, Mock, patch
import json
from context import microsoft365

class TestMicrosoft365Integration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()
    
    async def test_send_email_success(self):
        """Test successful email sending."""
        # Mock successful API response
        self.mock_context.fetch.return_value = None
        
        # Create action handler
        handler = microsoft365.SendEmailAction()
        
        # Test inputs
        inputs = {
            "to": "test@example.com",
            "subject": "Test Email",
            "body": "This is a test email",
            "body_type": "Text"
        }
        
        # Execute action
        result = await handler.execute(inputs, self.mock_context)
        
        # Verify result
        self.assertTrue(result.data["result"])
        
        # Verify API call
        self.mock_context.fetch.assert_called_once()
        call_args = self.mock_context.fetch.call_args
        self.assertIn("sendMail", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
    
    async def test_send_email_with_cc_bcc(self):
        """Test email sending with CC and BCC."""
        self.mock_context.fetch.return_value = None
        
        handler = microsoft365.SendEmailAction()
        inputs = {
            "to": "test@example.com",
            "subject": "Test Email",
            "body": "Test body",
            "cc": ["cc@example.com"],
            "bcc": ["bcc@example.com"]
        }
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        
        # Check that the API was called with CC and BCC recipients
        call_args = self.mock_context.fetch.call_args
        email_data = call_args[1]["json"]
        self.assertIn("ccRecipients", email_data["message"])
        self.assertIn("bccRecipients", email_data["message"])
    
    async def test_create_calendar_event_success(self):
        """Test successful calendar event creation."""
        # Mock API response
        mock_response = {
            "id": "event123",
            "webLink": "https://outlook.office365.com/calendar/event123"
        }
        self.mock_context.fetch.return_value = mock_response
        
        handler = microsoft365.CreateCalendarEventAction()
        inputs = {
            "subject": "Test Event",
            "start_time": "2024-08-01T14:00:00Z",
            "end_time": "2024-08-01T15:00:00Z",
            "location": "Conference Room",
            "attendees": ["attendee@example.com"]
        }
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["id"], "event123")
        self.assertIn("webLink", result.data)
    
    async def test_upload_file_success(self):
        """Test successful file upload."""
        # Mock API response
        mock_response = {
            "id": "file123",
            "webUrl": "https://onedrive.com/file123",
            "size": 1024,
            "@microsoft.graph.downloadUrl": "https://download.url"
        }
        self.mock_context.fetch.return_value = mock_response
        
        handler = microsoft365.UploadFileAction()
        inputs = {
            "filename": "test.txt",
            "content": "Test content",
            "content_type": "text/plain",
            "folder_path": "/Documents"
        }
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["id"], "file123")
        self.assertEqual(result.data["size"], 1024)
    
    async def test_list_files_success(self):
        """Test successful file listing."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "file1",
                    "name": "document.pdf",
                    "size": 2048,
                    "lastModifiedDateTime": "2024-08-01T10:00:00Z",
                    "webUrl": "https://onedrive.com/file1"
                },
                {
                    "id": "folder1",
                    "name": "My Folder",
                    "lastModifiedDateTime": "2024-08-01T09:00:00Z",
                    "webUrl": "https://onedrive.com/folder1",
                    "folder": {}
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response
        
        handler = microsoft365.ListFilesAction()
        inputs = {"folder_path": "/", "limit": 100}
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["files"]), 2)
        self.assertIsNone(result.data["files"][0]["folder"])     # document.pdf (no folder facet)
        self.assertIsNotNone(result.data["files"][1]["folder"]) # My Folder (has folder facet)
    
    async def test_error_handling(self):
        """Test error handling in actions."""
        # Mock API error
        self.mock_context.fetch.side_effect = Exception("API Error")
        
        handler = microsoft365.SendEmailAction()
        inputs = {
            "to": "test@example.com",
            "subject": "Test",
            "body": "Test"
        }
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertFalse(result.data["result"])
        self.assertIn("error", result.data)
        self.assertEqual(result.data["error"], "API Error")
    
    async def test_search_onedrive_files_success(self):
        """Test successful OneDrive file search."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "file123",
                    "name": "quarterly-report.docx", 
                    "size": 4096,
                    "lastModifiedDateTime": "2024-08-01T10:00:00Z",
                    "webUrl": "https://onedrive.com/file123",
                    "file": {
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                },
                {
                    "id": "folder456",
                    "name": "Documents",
                    "lastModifiedDateTime": "2024-08-01T09:00:00Z", 
                    "webUrl": "https://onedrive.com/folder456",
                    "folder": {"childCount": 10}
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response
        
        handler = microsoft365.SearchOneDriveFilesAction()
        inputs = {"query": "quarterly report", "limit": 10}
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["files"]), 2)
        self.assertEqual(result.data["query"], "quarterly report")
        
        # Check file item structure
        file_item = result.data["files"][0]
        self.assertEqual(file_item["id"], "file123")
        self.assertEqual(file_item["name"], "quarterly-report.docx")
        self.assertIn("file", file_item)
        
        # Check folder item structure
        folder_item = result.data["files"][1] 
        self.assertEqual(folder_item["id"], "folder456")
        self.assertIn("folder", folder_item)
        
        # Verify API call with URL encoding
        call_args = self.mock_context.fetch.call_args
        api_url = call_args[0][0]
        self.assertIn("search(q='quarterly%20report')", api_url)
    
    @patch('microsoft365.microsoft365.fetch_binary_content')
    async def test_read_onedrive_file_content_success(self, mock_fetch_binary):
        """Test successful OneDrive file content reading."""
        # Mock metadata response
        mock_metadata = {
            "id": "file123",
            "name": "document.docx",
            "size": 2048,
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "webUrl": "https://onedrive.com/file123"
        }

        # Mock content response (PDF conversion)
        mock_content = b"%PDF-1.4\n%fake PDF content for testing"

        # Mock context.fetch for metadata and fetch_binary_content for content
        self.mock_context.fetch.return_value = mock_metadata
        mock_fetch_binary.return_value = mock_content

        handler = microsoft365.ReadOneDriveFileContentAction()
        inputs = {"file_id": "file123"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["metadata"]["id"], "file123")
        self.assertEqual(result.data["file"]["name"], "document.docx")
        self.assertEqual(result.data["metadata"]["size"], 2048)
        self.assertEqual(result.data["file"]["contentType"], "application/pdf")
        self.assertIsNotNone(result.data["file"]["content"])  # Should have base64 encoded PDF

        # Verify API calls
        self.mock_context.fetch.assert_called_once()  # Metadata call
        mock_fetch_binary.assert_called_once()        # Binary content call

        # Check metadata call
        metadata_call = self.mock_context.fetch.call_args
        self.assertIn("/drive/items/file123", metadata_call[0][0])
        self.assertIn("$select", metadata_call[1]["params"])

        # Check binary content call (PDF conversion for Office doc)
        binary_call_args = mock_fetch_binary.call_args[0]
        self.assertIn("/drive/items/file123/content", binary_call_args[0])
        self.assertIn("format=pdf", binary_call_args[0])
    
    async def test_read_onedrive_file_content_non_office_file(self):
        """Test file content reading for non-Office files (no PDF conversion)."""
        # Mock metadata response for text file
        mock_metadata = {
            "id": "file456", 
            "name": "notes.txt",
            "size": 512,
            "mimeType": "text/plain",
            "webUrl": "https://onedrive.com/file456"
        }
        
        # Mock content response
        mock_content = b"Sample text content"
        
        self.mock_context.fetch.side_effect = [mock_metadata, mock_content]
        
        handler = microsoft365.ReadOneDriveFileContentAction()
        inputs = {"file_id": "file456"}
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["file"]["name"], "notes.txt")
        self.assertEqual(result.data["file"]["contentType"], "text/plain")
        self.assertIsNotNone(result.data["file"]["content"])  # Should have base64 encoded content
        
        # Check content call (no PDF conversion for text file)
        content_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("/drive/items/file456/content", content_call[0][0])
        self.assertNotIn("format=pdf", content_call[0][0])

    @patch('microsoft365.microsoft365.fetch_binary_content')
    async def test_read_onedrive_file_content_native_pdf(self, mock_fetch_binary):
        """Test file content reading for native PDF files."""
        # Mock metadata response for PDF file
        mock_metadata = {
            "id": "file789",
            "name": "AICPA_SOC2_Compliance_Guide_on_AWS.pdf",
            "size": 755287,
            "mimeType": "application/pdf",
            "webUrl": "https://onedrive.com/file789"
        }

        # Mock PDF binary content
        mock_content = b"%PDF-1.4\n%\xc4\xe5\xf2\xe5\xeb\xa7\xf3\xa0\xd0\xc4\xc6 Native PDF content with binary data"

        # Mock context.fetch for metadata and fetch_binary_content for content
        self.mock_context.fetch.return_value = mock_metadata
        mock_fetch_binary.return_value = mock_content

        handler = microsoft365.ReadOneDriveFileContentAction()
        inputs = {"file_id": "file789"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["file"]["name"], "AICPA_SOC2_Compliance_Guide_on_AWS.pdf")
        self.assertEqual(result.data["file"]["contentType"], "application/pdf")
        self.assertIsNotNone(result.data["file"]["content"])  # Should have base64 encoded content

        # Verify binary fetch was called with correct URL
        mock_fetch_binary.assert_called_once()
        call_args = mock_fetch_binary.call_args[0]
        self.assertIn("/drive/items/file789/content", call_args[0])
        self.assertNotIn("format=pdf", call_args[0])

    async def test_read_onedrive_file_content_with_content_error(self):
        """Test file content reading when content retrieval fails."""
        # Mock metadata response
        mock_metadata = {
            "id": "file789",
            "name": "restricted.pdf", 
            "size": 1024,
            "mimeType": "application/pdf",
            "webUrl": "https://onedrive.com/file789"
        }
        
        # Mock content error
        self.mock_context.fetch.side_effect = [mock_metadata, Exception("Access denied")]
        
        handler = microsoft365.ReadOneDriveFileContentAction()
        inputs = {"file_id": "file789"}
        
        result = await handler.execute(inputs, self.mock_context)
        
        self.assertFalse(result.data["result"])  # Operation fails when content retrieval fails
        self.assertEqual(result.data["file"]["name"], "restricted.pdf")
        self.assertEqual(result.data["file"]["content"], "")  # Empty content on failure
        self.assertIn("Access denied", result.data["error"])


class TestListCalendarEventsAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for calendar events listing tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_list_calendar_events_with_date_range(self):
        """Test listing calendar events with date range filtering using calendarView."""
        # Mock API response from calendarView
        mock_response = {
            "value": [
                {
                    "id": "event123",
                    "subject": "Team Meeting",
                    "start": {
                        "dateTime": "2024-08-20T14:00:00.0000000",
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": "2024-08-20T15:00:00.0000000",
                        "timeZone": "UTC"
                    },
                    "location": {
                        "displayName": "Conference Room A"
                    },
                    "bodyPreview": "Weekly team sync",
                    "organizer": {
                        "emailAddress": {
                            "address": "organizer@example.com",
                            "name": "Organizer Name"
                        }
                    },
                    "attendees": [
                        {
                            "emailAddress": {
                                "address": "attendee@example.com",
                                "name": "Attendee Name"
                            },
                            "status": {
                                "response": "accepted"
                            }
                        }
                    ],
                    "webLink": "https://outlook.office365.com/calendar/item123",
                    "isAllDay": False
                }
            ]
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListCalendarEventsAction()
        inputs = {
            "start_datetime": "2024-08-20T00:00:00Z",
            "end_datetime": "2024-08-20T23:59:59Z",
            "limit": 50
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["events"]), 1)
        self.assertEqual(result.data["events"][0]["subject"], "Team Meeting")
        self.assertEqual(result.data["events"][0]["location"], "Conference Room A")

        # Verify calendarView endpoint is called with date parameters
        call_args = self.mock_context.fetch.call_args[0][0]
        self.assertIn("/me/calendarView", call_args)
        self.assertIn("startDateTime=2024-08-20T00:00:00Z", call_args)
        self.assertIn("endDateTime=2024-08-20T23:59:59Z", call_args)


class TestCreateDraftEmailAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for draft email tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_create_draft_email_success(self):
        """Test successful draft email creation."""
        # Mock API response
        mock_response = {
            "id": "draft123",
            "subject": "Test Draft",
            "createdDateTime": "2024-08-20T10:00:00Z",
            "isDraft": True
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.CreateDraftEmailAction()
        inputs = {
            "subject": "Test Draft",
            "body": "This is a test draft",
            "body_type": "Text",
            "to_recipients": ["test@example.com"]
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["draft_id"], "draft123")
        self.assertEqual(result.data["subject"], "Test Draft")
        self.assertTrue(result.data["is_draft"])

        # Verify API call
        self.mock_context.fetch.assert_called_once()
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/messages", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

    async def test_create_draft_email_with_all_recipients(self):
        """Test draft creation with CC and BCC recipients."""
        mock_response = {
            "id": "draft456",
            "subject": "Complete Draft",
            "createdDateTime": "2024-08-20T10:00:00Z",
            "isDraft": True
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.CreateDraftEmailAction()
        inputs = {
            "subject": "Complete Draft",
            "body": "Draft with all recipient types",
            "to_recipients": [{"address": "to@example.com", "name": "To User"}],
            "cc_recipients": ["cc@example.com"],
            "bcc_recipients": [{"address": "bcc@example.com"}],
            "importance": "High"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["draft_id"], "draft456")

        # Check the message structure in the API call
        call_args = self.mock_context.fetch.call_args
        message_body = call_args[1]["json"]
        self.assertIn("ccRecipients", message_body)
        self.assertIn("bccRecipients", message_body)
        self.assertEqual(message_body["importance"], "High")


class TestSendDraftEmailAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for send draft tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_send_draft_email_success(self):
        """Test successful draft sending."""
        # Mock API response (202 Accepted with no body)
        self.mock_context.fetch.return_value = None

        handler = microsoft365.SendDraftEmailAction()
        inputs = {"draft_id": "draft123"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["draft_id"], "draft123")
        self.assertEqual(result.data["status"], "sent")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/messages/draft123/send", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
        self.assertEqual(call_args[1]["headers"]["Content-Length"], "0")


class TestReplyToEmailAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for reply tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_reply_to_email_success(self):
        """Test successful email reply."""
        # Mock API response (202 Accepted with no body)
        self.mock_context.fetch.return_value = None

        handler = microsoft365.ReplyToEmailAction()
        inputs = {
            "message_id": "msg123",
            "comment": "Thanks for the email!"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["message_id"], "msg123")
        self.assertEqual(result.data["operation"], "reply")
        self.assertEqual(result.data["status"], "sent")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/messages/msg123/reply", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
        self.assertEqual(call_args[1]["json"]["comment"], "Thanks for the email!")

    async def test_reply_to_email_without_comment(self):
        """Test email reply without comment."""
        self.mock_context.fetch.return_value = None

        handler = microsoft365.ReplyToEmailAction()
        inputs = {"message_id": "msg456"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["message_id"], "msg456")

        # Verify API call with empty JSON body
        call_args = self.mock_context.fetch.call_args
        self.assertEqual(call_args[1]["json"], {})


class TestForwardEmailAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for forward tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_forward_email_success(self):
        """Test successful email forwarding."""
        # Mock API response (202 Accepted with no body)
        self.mock_context.fetch.return_value = None

        handler = microsoft365.ForwardEmailAction()
        inputs = {
            "message_id": "msg789",
            "to_recipients": ["forward@example.com", {"address": "user@test.com", "name": "Test User"}],
            "comment": "FYI"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["message_id"], "msg789")
        self.assertEqual(result.data["operation"], "forward")
        self.assertEqual(result.data["status"], "sent")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/messages/msg789/forward", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

        # Check recipients structure
        forward_data = call_args[1]["json"]
        self.assertEqual(len(forward_data["toRecipients"]), 2)
        self.assertEqual(forward_data["comment"], "FYI")


class TestDownloadEmailAttachmentAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for attachment download tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    @patch('microsoft365.microsoft365.fetch_binary_content')
    async def test_download_attachment_success(self, mock_fetch_binary):
        """Test successful attachment download."""
        # Mock attachment metadata
        mock_metadata = {
            "id": "att123",
            "name": "document.pdf",
            "contentType": "application/pdf",
            "size": 1024,
            "isInline": False
        }

        # Mock binary content
        mock_binary_content = b"PDF binary data here"

        self.mock_context.fetch.return_value = mock_metadata
        mock_fetch_binary.return_value = mock_binary_content

        handler = microsoft365.DownloadEmailAttachmentAction()
        inputs = {
            "message_id": "msg123",
            "attachment_id": "att123",
            "include_content": True
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        # Verify file structure (matches OneDrive/SharePoint format)
        self.assertEqual(result.data["file"]["name"], "document.pdf")
        self.assertEqual(result.data["file"]["contentType"], "application/pdf")
        self.assertIsNotNone(result.data["file"]["content"])  # Base64 encoded
        # Verify metadata structure
        self.assertEqual(result.data["metadata"]["id"], "att123")
        self.assertEqual(result.data["metadata"]["name"], "document.pdf")
        self.assertEqual(result.data["metadata"]["size"], 1024)
        self.assertEqual(result.data["metadata"]["message_id"], "msg123")
        self.assertFalse(result.data["metadata"]["is_inline"])

        # Verify API calls
        self.mock_context.fetch.assert_called_once()
        mock_fetch_binary.assert_called_once()

    async def test_download_attachment_metadata_only(self):
        """Test attachment metadata retrieval without content."""
        mock_metadata = {
            "id": "att456",
            "name": "image.jpg",
            "contentType": "image/jpeg",
            "size": 2048,
            "isInline": True
        }

        self.mock_context.fetch.return_value = mock_metadata

        handler = microsoft365.DownloadEmailAttachmentAction()
        inputs = {
            "message_id": "msg456",
            "attachment_id": "att456",
            "include_content": False
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result.data["result"])  # False because content not retrieved
        self.assertEqual(result.data["file"]["content"], "")  # No content
        self.assertEqual(result.data["file"]["name"], "image.jpg")
        self.assertTrue(result.data["metadata"]["is_inline"])


class TestSearchEmailsAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for search tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_search_emails_success(self):
        """Test successful email search."""
        # Mock search API response
        mock_response = {
            "value": [{
                "hitsContainers": [{
                    "total": 2,
                    "hits": [
                        {
                            "resource": {
                                "id": "msg1",
                                "subject": "Project Update",
                                "from": {
                                    "emailAddress": {
                                        "address": "sender@example.com",
                                        "name": "Sender Name"
                                    }
                                },
                                "receivedDateTime": "2024-08-20T10:00:00Z",
                                "bodyPreview": "Here is the project update...",
                                "hasAttachments": True
                            }
                        },
                        {
                            "resource": {
                                "id": "msg2",
                                "subject": "Meeting Notes",
                                "from": {
                                    "emailAddress": {
                                        "address": "colleague@example.com",
                                        "name": "Colleague"
                                    }
                                },
                                "receivedDateTime": "2024-08-19T15:30:00Z",
                                "bodyPreview": "Notes from today's meeting...",
                                "hasAttachments": False
                            }
                        }
                    ]
                }]
            }]
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.SearchEmailsAction()
        inputs = {
            "query": "project meeting",
            "limit": 25,
            "enable_top_results": True
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["query"], "project meeting")
        self.assertEqual(result.data["total_results"], 2)
        self.assertEqual(len(result.data["messages"]), 2)

        # Check first message structure
        first_msg = result.data["messages"][0]
        self.assertEqual(first_msg["message_id"], "msg1")
        self.assertEqual(first_msg["subject"], "Project Update")
        self.assertTrue(first_msg["has_attachments"])

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("search/query", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

        # Check search request structure
        search_request = call_args[1]["json"]["requests"][0]
        self.assertEqual(search_request["entityTypes"], ["message"])
        self.assertEqual(search_request["query"]["queryString"], "project meeting")
        self.assertTrue(search_request["enableTopResults"])

    async def test_search_emails_no_results(self):
        """Test search with no results."""
        mock_response = {
            "value": [{
                "hitsContainers": [{
                    "total": 0,
                    "hits": []
                }]
            }]
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.SearchEmailsAction()
        inputs = {"query": "nonexistent"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["total_results"], 0)
        self.assertEqual(len(result.data["messages"]), 0)

    async def test_search_emails_with_null_fields(self):
        """Test email search handles null subject and bodyPreview fields."""
        # Mock response with None values for optional fields
        mock_response = {
            "value": [{
                "hitsContainers": [{
                    "total": 1,
                    "hits": [
                        {
                            "resource": {
                                "id": "msg1",
                                "subject": None,  # Null subject
                                "from": {
                                    "emailAddress": {
                                        "address": "sender@example.com",
                                        "name": "Sender Name"
                                    }
                                },
                                "receivedDateTime": "2024-08-20T10:00:00Z",
                                "bodyPreview": None,  # Null bodyPreview
                                "hasAttachments": False
                            }
                        }
                    ]
                }]
            }]
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.SearchEmailsAction()
        inputs = {"query": "test"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["total_results"], 1)

        # Verify null values are converted to empty strings
        first_msg = result.data["messages"][0]
        self.assertEqual(first_msg["subject"], "")
        self.assertEqual(first_msg["body_preview"], "")
        self.assertIsInstance(first_msg["subject"], str)
        self.assertIsInstance(first_msg["body_preview"], str)


class TestSearchSharePointSitesAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint sites search tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_search_sharepoint_sites_success(self):
        """Test successful SharePoint sites search."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "contoso.sharepoint.com,da60e844-ba1d-49bc-b4d4-d5e36bae9019,712a596e-90a1-49e3-9b48-bfa80bee8740",
                    "name": "Team A Site",
                    "displayName": "Team A Collaboration Site",
                    "description": "Site for Team A projects",
                    "webUrl": "https://contoso.sharepoint.com/sites/siteA",
                    "createdDateTime": "2024-01-15T10:00:00Z",
                    "lastModifiedDateTime": "2024-08-20T14:30:00Z"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.SearchSharePointSitesAction()
        inputs = {"query": "Team A"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["query"], "Team A")
        self.assertEqual(len(result.data["sites"]), 1)
        self.assertEqual(result.data["total_sites"], 1)
        self.assertEqual(result.data["sites"][0]["name"], "Team A Site")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/sites", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["search"], "Team A")


class TestGetSharePointSiteDetailsAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint site details tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_get_sharepoint_site_details_success(self):
        """Test successful SharePoint site details retrieval."""
        # Mock API response
        mock_response = {
            "id": "contoso.sharepoint.com,da60e844-ba1d-49bc-b4d4-d5e36bae9019,712a596e-90a1-49e3-9b48-bfa80bee8740",
            "displayName": "Team A Collaboration Site",
            "name": "Team A Site",
            "description": "Site for Team A projects and documentation",
            "webUrl": "https://contoso.sharepoint.com/sites/siteA",
            "createdDateTime": "2024-01-15T10:00:00Z",
            "lastModifiedDateTime": "2024-08-20T14:30:00Z",
            "isPersonalSite": False
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.GetSharePointSiteDetailsAction()
        inputs = {"site_id": "contoso.sharepoint.com,da60e844-ba1d-49bc-b4d4-d5e36bae9019,712a596e-90a1-49e3-9b48-bfa80bee8740"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["site"]["name"], "Team A Site")
        self.assertEqual(result.data["site"]["display_name"], "Team A Collaboration Site")
        self.assertFalse(result.data["site"]["is_personal_site"])

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/sites/contoso.sharepoint.com", call_args[0][0])


class TestListSharePointLibrariesAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint libraries tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_list_sharepoint_libraries_success(self):
        """Test successful SharePoint libraries listing."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "b!-RIj2DuyvEyV1T4NlOaMHk8XkS_I8MdFlUCq1BlcjgmhRfAj3-Z8RY2VpuvV_tpd",
                    "name": "Documents",
                    "description": "Shared Documents",
                    "driveType": "documentLibrary",
                    "webUrl": "https://contoso.sharepoint.com/sites/siteA/Shared Documents",
                    "createdDateTime": "2024-01-15T10:00:00Z",
                    "lastModifiedDateTime": "2024-08-20T14:30:00Z",
                    "owner": {
                        "user": {
                            "displayName": "Site Owner",
                            "email": "owner@contoso.com"
                        }
                    },
                    "quota": {
                        "total": 1099511627776,
                        "remaining": 1099217021300,
                        "used": 294606476,
                        "deleted": 0,
                        "state": "normal"
                    }
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListSharePointLibrariesAction()
        inputs = {"site_id": "test-site-id"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["site_id"], "test-site-id")
        self.assertEqual(len(result.data["libraries"]), 1)
        self.assertEqual(result.data["total_libraries"], 1)

        library = result.data["libraries"][0]
        self.assertEqual(library["name"], "Documents")
        self.assertEqual(library["drive_type"], "documentLibrary")
        self.assertIn("quota", library)
        self.assertIn("owner", library)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/sites/test-site-id/drives", call_args[0][0])


class TestSearchSharePointDocumentsAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint documents search tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_search_sharepoint_documents_success(self):
        """Test successful SharePoint documents search across multiple drives."""
        # Mock drives response (Step 1: Get all drives)
        mock_drives_response = {
            "value": [
                {
                    "id": "drive1",
                    "name": "Documents",
                    "driveType": "documentLibrary"
                },
                {
                    "id": "drive2",
                    "name": "HRDocumentLibrary",
                    "driveType": "documentLibrary"
                }
            ]
        }

        # Mock search results for each drive (Step 2: Search each drive)
        mock_search_response_drive1 = {
            "value": [
                {
                    "id": "doc123",
                    "name": "Project Plan.docx",
                    "size": 45678,
                    "lastModifiedDateTime": "2024-08-20T10:00:00Z",
                    "webUrl": "https://contoso.sharepoint.com/sites/siteA/Documents/Project Plan.docx",
                    "file": {
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                }
            ]
        }

        mock_search_response_drive2 = {
            "value": [
                {
                    "id": "doc456",
                    "name": "HR Policy.pdf",
                    "size": 23456,
                    "lastModifiedDateTime": "2024-08-19T15:30:00Z",
                    "webUrl": "https://contoso.sharepoint.com/sites/siteA/HRDocumentLibrary/HR Policy.pdf",
                    "file": {
                        "mimeType": "application/pdf"
                    }
                }
            ]
        }

        # Configure mock to return different responses for different calls
        self.mock_context.fetch.side_effect = [
            mock_drives_response,           # First call: GET /sites/{site-id}/drives
            mock_search_response_drive1,    # Second call: GET /drives/drive1/root/search
            mock_search_response_drive2     # Third call: GET /drives/drive2/root/search
        ]

        handler = microsoft365.SearchSharePointDocumentsAction()
        inputs = {
            "site_id": "test-site-id",
            "query": "project plan",
            "limit": 10
        }

        result = await handler.execute(inputs, self.mock_context)

        # Verify the result
        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["site_id"], "test-site-id")
        self.assertEqual(result.data["query"], "project plan")
        self.assertEqual(len(result.data["files"]), 2)
        self.assertEqual(result.data["total_files"], 2)
        self.assertEqual(result.data["drives_searched"], 2)
        self.assertEqual(result.data["total_drives"], 2)

        # Verify file details include drive information
        files = result.data["files"]
        self.assertEqual(files[0]["name"], "Project Plan.docx")
        self.assertEqual(files[0]["drive_id"], "drive1")
        self.assertEqual(files[0]["drive_name"], "Documents")
        self.assertEqual(files[1]["name"], "HR Policy.pdf")
        self.assertEqual(files[1]["drive_id"], "drive2")
        self.assertEqual(files[1]["drive_name"], "HRDocumentLibrary")

        # Verify the API calls were made correctly
        self.assertEqual(self.mock_context.fetch.call_count, 3)
        call_args_list = self.mock_context.fetch.call_args_list

        # First call: Get drives
        self.assertIn("/sites/test-site-id/drives", call_args_list[0][0])

        # Second call: Search first drive
        self.assertIn("/drives/drive1/root/search", call_args_list[1][0])
        self.assertIn("project%20plan", call_args_list[1][0])

        # Third call: Search second drive
        self.assertIn("/drives/drive2/root/search", call_args_list[2][0])
        self.assertIn("project%20plan", call_args_list[2][0])


class TestListSharePointPagesAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint pages tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_list_sharepoint_pages_success(self):
        """Test successful SharePoint pages listing."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "page123",
                    "name": "Home.aspx",
                    "title": "Welcome to Team A",
                    "webUrl": "https://contoso.sharepoint.com/sites/siteA/SitePages/Home.aspx",
                    "pageLayout": "home",
                    "createdDateTime": "2024-01-15T10:00:00Z",
                    "lastModifiedDateTime": "2024-08-20T14:30:00Z",
                    "createdBy": {
                        "user": {
                            "displayName": "John Doe",
                            "email": "john@contoso.com"
                        }
                    }
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListSharePointPagesAction()
        inputs = {"site_id": "test-site-id"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["site_id"], "test-site-id")
        self.assertEqual(len(result.data["pages"]), 1)
        self.assertEqual(result.data["total_pages"], 1)

        page = result.data["pages"][0]
        self.assertEqual(page["name"], "Home.aspx")
        self.assertEqual(page["title"], "Welcome to Team A")
        self.assertEqual(page["page_layout"], "home")
        self.assertIn("created_by", page)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/sites/test-site-id/pages/microsoft.graph.sitePage", call_args[0][0])


class TestReadSharePointDocumentAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint document reading tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    @patch('microsoft365.microsoft365.fetch_binary_content')
    async def test_read_sharepoint_document_success(self, mock_fetch_binary):
        """Test successful SharePoint document reading."""
        # Mock metadata response
        mock_metadata = {
            "id": "doc123",
            "name": "SharePoint_Report.docx",
            "size": 3072,
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "webUrl": "https://contoso.sharepoint.com/sites/siteA/Documents/SharePoint_Report.docx"
        }

        # Mock PDF content from conversion
        mock_content = b"%PDF-1.4\n%SharePoint document converted to PDF"

        self.mock_context.fetch.return_value = mock_metadata
        mock_fetch_binary.return_value = mock_content

        handler = microsoft365.ReadSharePointDocumentAction()
        inputs = {"site_id": "test-site-id", "file_id": "doc123"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["file"]["name"], "SharePoint_Report.docx")
        self.assertEqual(result.data["file"]["contentType"], "application/pdf")
        self.assertEqual(result.data["metadata"]["site_id"], "test-site-id")
        self.assertIsNotNone(result.data["file"]["content"])  # Base64 encoded PDF

        # Verify API calls
        self.mock_context.fetch.assert_called_once()  # Metadata call
        mock_fetch_binary.assert_called_once()        # Binary content call

        # Check binary content call includes format=pdf for Office docs
        binary_call_args = mock_fetch_binary.call_args[0]
        self.assertIn("/sites/test-site-id/drive/items/doc123/content", binary_call_args[0])
        self.assertIn("format=pdf", binary_call_args[0])

    @patch('microsoft365.microsoft365.fetch_binary_content')
    async def test_read_sharepoint_document_with_drive_id_success(self, mock_fetch_binary):
        """Test successful SharePoint document reading with specific drive ID."""
        # Mock metadata response
        mock_metadata = {
            "id": "doc456",
            "name": "HR_Policy.pdf",
            "size": 4096,
            "mimeType": "application/pdf",
            "webUrl": "https://contoso.sharepoint.com/sites/siteA/HRDocumentLibrary/HR_Policy.pdf"
        }
        # Mock PDF content
        mock_content = b"%PDF-1.4\n%HR Policy document"
        self.mock_context.fetch.return_value = mock_metadata
        mock_fetch_binary.return_value = mock_content

        handler = microsoft365.ReadSharePointDocumentAction()
        inputs = {
            "site_id": "test-site-id",
            "file_id": "doc456",
            "drive_id": "drive123"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["file"]["name"], "HR_Policy.pdf")
        self.assertEqual(result.data["file"]["contentType"], "application/pdf")
        self.assertEqual(result.data["metadata"]["site_id"], "test-site-id")
        self.assertEqual(result.data["metadata"]["drive_id"], "drive123")
        self.assertIsNotNone(result.data["file"]["content"])  # Base64 encoded PDF

        # Verify API calls use drive-specific endpoints
        metadata_call_args = self.mock_context.fetch.call_args[0]
        self.assertIn("/drives/drive123/items/doc456", metadata_call_args[0])

        # Check binary content call uses drive-specific endpoint
        binary_call_args = mock_fetch_binary.call_args[0]
        self.assertIn("/drives/drive123/items/doc456/content", binary_call_args[0])


class TestListMailFoldersAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for mail folder listing tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_list_mail_folders_success(self):
        """Test successful mail folder listing."""
        # Mock API response
        mock_response = {
            "value": [
                {
                    "id": "AQMkADYAAAIBDAAAAA==",
                    "displayName": "Inbox",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 2,
                    "unreadItemCount": 10,
                    "totalItemCount": 50,
                    "isHidden": False
                },
                {
                    "id": "AQMkADYAAAIBXQAAAA==",
                    "displayName": "Archive",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 0,
                    "totalItemCount": 100,
                    "isHidden": False
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListMailFoldersAction()
        inputs = {"include_hidden": False, "include_children": False}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["folders"]), 2)
        self.assertEqual(result.data["total_count"], 2)
        self.assertEqual(result.data["folders"][0]["displayName"], "Inbox")
        self.assertEqual(result.data["folders"][1]["displayName"], "Archive")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/mailFolders", call_args[0][0])

    async def test_list_mail_folders_pagination(self):
        """Test mail folder listing handles pagination correctly when more than 10 folders exist."""
        # First page with @odata.nextLink
        mock_page1 = {
            "value": [
                {
                    "id": "AQMkADYAAAIBDAAAAA==",
                    "displayName": "Inbox",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 10,
                    "totalItemCount": 50,
                    "isHidden": False
                },
                {
                    "id": "AQMkADYAAAIBXQAAAA==",
                    "displayName": "Archive",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 0,
                    "totalItemCount": 100,
                    "isHidden": False
                }
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/mailFolders?$skiptoken=xxx"
        }
        # Second page without @odata.nextLink (last page)
        mock_page2 = {
            "value": [
                {
                    "id": "AQMkADYAAAIBEAAAAA==",
                    "displayName": "Drafts",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 2,
                    "totalItemCount": 5,
                    "isHidden": False
                }
            ]
        }
        self.mock_context.fetch.side_effect = [mock_page1, mock_page2]

        handler = microsoft365.ListMailFoldersAction()
        inputs = {"include_hidden": False, "include_children": False}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        # Should have all 3 folders from both pages
        self.assertEqual(len(result.data["folders"]), 3)
        self.assertEqual(result.data["total_count"], 3)
        self.assertEqual(result.data["folders"][0]["displayName"], "Inbox")
        self.assertEqual(result.data["folders"][1]["displayName"], "Archive")
        self.assertEqual(result.data["folders"][2]["displayName"], "Drafts")

        # Verify fetch was called twice (once for each page)
        self.assertEqual(self.mock_context.fetch.call_count, 2)

    async def test_list_mail_folders_with_children(self):
        """Test mail folder listing with recursive child folder retrieval."""
        # Mock root folders response
        mock_root_response = {
            "value": [
                {
                    "id": "AQMkADYAAAIBDAAAAA==",
                    "displayName": "Inbox",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 1,
                    "unreadItemCount": 10,
                    "totalItemCount": 50,
                    "isHidden": False
                }
            ]
        }

        # Mock child folders response
        mock_child_response = {
            "value": [
                {
                    "id": "AQMkADYAAAIBEAAAAA==",
                    "displayName": "Clients",
                    "parentFolderId": "AQMkADYAAAIBDAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 5,
                    "totalItemCount": 20,
                    "isHidden": False
                }
            ]
        }

        self.mock_context.fetch.side_effect = [mock_root_response, mock_child_response]

        handler = microsoft365.ListMailFoldersAction()
        inputs = {"include_hidden": False, "include_children": True}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["folders"]), 2)  # Inbox + Clients
        self.assertEqual(result.data["total_count"], 2)

        # Verify both folders are returned
        folder_names = [f["displayName"] for f in result.data["folders"]]
        self.assertIn("Inbox", folder_names)
        self.assertIn("Clients", folder_names)

    async def test_list_mail_folders_with_hidden(self):
        """Test mail folder listing including hidden folders."""
        mock_response = {
            "value": [
                {
                    "id": "AQMkADYAAAIBDAAAAA==",
                    "displayName": "Inbox",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 10,
                    "totalItemCount": 50,
                    "isHidden": False
                },
                {
                    "id": "AQMkADYAAAIBFAAAAA==",
                    "displayName": "Clutter",
                    "parentFolderId": "AQMkADYAAAIBCAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 0,
                    "totalItemCount": 5,
                    "isHidden": True
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListMailFoldersAction()
        inputs = {"include_hidden": True, "include_children": False}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["folders"]), 2)

        # Verify hidden folder parameter was passed
        call_args = self.mock_context.fetch.call_args
        self.assertEqual(call_args[1]["params"]["includeHiddenFolders"], "true")

    async def test_list_mail_folders_specific_parent(self):
        """Test listing child folders of a specific parent folder."""
        mock_response = {
            "value": [
                {
                    "id": "AQMkADYAAAIBEAAAAA==",
                    "displayName": "Projects",
                    "parentFolderId": "AQMkADYAAAIBDAAAAA==",
                    "childFolderCount": 0,
                    "unreadItemCount": 3,
                    "totalItemCount": 15,
                    "isHidden": False
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ListMailFoldersAction()
        inputs = {"folder_id": "AQMkADYAAAIBDAAAAA==", "include_children": False}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(len(result.data["folders"]), 1)
        self.assertEqual(result.data["folders"][0]["displayName"], "Projects")

        # Verify API call uses childFolders endpoint
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/mailFolders/AQMkADYAAAIBDAAAAA==/childFolders", call_args[0][0])


class TestGetMailFolderAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for get mail folder tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_get_mail_folder_by_id_success(self):
        """Test getting a mail folder by ID."""
        mock_response = {
            "id": "AQMkADYAAAIBDAAAAA==",
            "displayName": "Inbox",
            "parentFolderId": "AQMkADYAAAIBCAAAAA==",
            "childFolderCount": 2,
            "unreadItemCount": 10,
            "totalItemCount": 50,
            "isHidden": False
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.GetMailFolderAction()
        inputs = {"folder_id": "AQMkADYAAAIBDAAAAA=="}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["folder"]["id"], "AQMkADYAAAIBDAAAAA==")
        self.assertEqual(result.data["folder"]["displayName"], "Inbox")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/mailFolders/AQMkADYAAAIBDAAAAA==", call_args[0][0])

    async def test_get_mail_folder_by_well_known_name(self):
        """Test getting a mail folder by well-known name."""
        mock_response = {
            "id": "AQMkADYAAAIBXQAAAA==",
            "displayName": "Archive",
            "parentFolderId": "AQMkADYAAAIBCAAAAA==",
            "childFolderCount": 0,
            "unreadItemCount": 0,
            "totalItemCount": 100,
            "isHidden": False
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.GetMailFolderAction()
        inputs = {"folder_id": "archive"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["folder"]["displayName"], "Archive")

        # Verify API call uses well-known name
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/mailFolders/archive", call_args[0][0])

    async def test_get_mail_folder_not_found(self):
        """Test getting a non-existent mail folder."""
        self.mock_context.fetch.side_effect = Exception("Resource not found")

        handler = microsoft365.GetMailFolderAction()
        inputs = {"folder_id": "nonexistent"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result.data["result"])
        self.assertIn("error", result.data)


class TestMoveEmailAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for move email tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_move_email_with_folder_id_success(self):
        """Test moving email to folder using folder ID."""
        mock_response = {
            "id": "msg123-moved",
            "parentFolderId": "AQMkADYAAAIBXQAAAA==",
            "subject": "Test Email"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.MoveEmailAction()
        inputs = {
            "email_id": "msg123",
            "destination_folder_id": "AQMkADYAAAIBXQAAAA=="
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["id"], "msg123-moved")
        self.assertEqual(result.data["parentFolderId"], "AQMkADYAAAIBXQAAAA==")
        self.assertEqual(result.data["subject"], "Test Email")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/messages/msg123/move", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
        self.assertEqual(call_args[1]["json"]["destinationId"], "AQMkADYAAAIBXQAAAA==")

    async def test_move_email_with_well_known_name_success(self):
        """Test moving email to folder using well-known name."""
        mock_response = {
            "id": "msg456-moved",
            "parentFolderId": "AQMkADYAAAIBGAAAAA==",
            "subject": "Another Test Email"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.MoveEmailAction()
        inputs = {
            "email_id": "msg456",
            "destination_folder_id": "deleteditems"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["id"], "msg456-moved")

        # Verify API call uses well-known name
        call_args = self.mock_context.fetch.call_args
        self.assertEqual(call_args[1]["json"]["destinationId"], "deleteditems")

    async def test_move_email_failure(self):
        """Test move email failure handling."""
        self.mock_context.fetch.side_effect = Exception("Folder not found")

        handler = microsoft365.MoveEmailAction()
        inputs = {
            "email_id": "msg789",
            "destination_folder_id": "invalid-folder"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result.data["result"])
        self.assertIn("error", result.data)
        self.assertIn("Folder not found", result.data["error"])


class TestReadSharePointPageContentAction(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for SharePoint page content tests."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    async def test_read_sharepoint_page_content_success(self):
        """Test successful SharePoint page content reading."""
        # Mock API response with canvasLayout
        mock_response = {
            "id": "page123",
            "name": "Home.aspx",
            "title": "Welcome to SharePoint",
            "webUrl": "https://contoso.sharepoint.com/sites/siteA/SitePages/Home.aspx",
            "pageLayout": "home",
            "createdDateTime": "2024-01-15T10:00:00Z",
            "lastModifiedDateTime": "2024-08-20T14:30:00Z",
            "createdBy": {
                "user": {
                    "displayName": "Page Creator",
                    "email": "creator@contoso.com"
                }
            },
            "canvasLayout": {
                "horizontalSections": [
                    {
                        "layout": "oneColumn",
                        "columns": [
                            {
                                "webparts": [
                                    {
                                        "@odata.type": "#oneDrive.textWebPart",
                                        "innerHtml": "<h1>Welcome</h1><p>This is the home page content.</p>"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ReadSharePointPageContentAction()
        inputs = {
            "site_id": "test-site-id",
            "page_id": "page123",
            "include_content": True
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["site_id"], "test-site-id")
        self.assertEqual(result.data["page"]["name"], "Home.aspx")
        self.assertEqual(result.data["page"]["title"], "Welcome to SharePoint")
        self.assertEqual(result.data["page"]["page_layout"], "home")
        self.assertIn("content", result.data["page"])  # canvasLayout content
        self.assertIn("created_by", result.data["page"])

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/sites/test-site-id/pages/page123/microsoft.graph.sitePage", call_args[0][0])
        self.assertIn("$expand", call_args[1]["params"])
        self.assertEqual(call_args[1]["params"]["$expand"], "canvasLayout")

    async def test_read_sharepoint_page_content_metadata_only(self):
        """Test SharePoint page metadata retrieval without content."""
        mock_response = {
            "id": "page456",
            "name": "About.aspx",
            "title": "About Us",
            "webUrl": "https://contoso.sharepoint.com/sites/siteA/SitePages/About.aspx",
            "pageLayout": "article"
        }

        self.mock_context.fetch.return_value = mock_response

        handler = microsoft365.ReadSharePointPageContentAction()
        inputs = {
            "site_id": "test-site-id",
            "page_id": "page456",
            "include_content": False
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result.data["result"])
        self.assertEqual(result.data["page"]["title"], "About Us")
        self.assertNotIn("content", result.data["page"])  # No content when include_content=False

        # Verify API call doesn't include $expand
        call_args = self.mock_context.fetch.call_args
        self.assertNotIn("$expand", call_args[1]["params"])


if __name__ == '__main__':
    unittest.main()
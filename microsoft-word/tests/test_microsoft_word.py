import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockActionResult:
    """Mock ActionResult that mimics the SDK's ActionResult class."""
    def __init__(self, is_success: bool, data: dict = None, error: str = None):
        self.is_success = is_success
        self.data = data or {}
        self.error = error
    
    @classmethod
    def success(cls, data: dict = None):
        return cls(is_success=True, data=data or {})
    
    @classmethod
    def failure(cls, error: str = None):
        return cls(is_success=False, error=error)


mock_integration = MagicMock()
mock_integration.action = lambda name: lambda cls: cls

with patch.dict('sys.modules', {'autohive_integrations_sdk': MagicMock()}):
    with patch('autohive_integrations_sdk.Integration.load', return_value=mock_integration):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "microsoft_word", 
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "microsoft_word.py")
        )
        
        import autohive_integrations_sdk
        autohive_integrations_sdk.Integration = MagicMock()
        autohive_integrations_sdk.Integration.load = MagicMock(return_value=mock_integration)
        autohive_integrations_sdk.ExecutionContext = MagicMock
        autohive_integrations_sdk.ActionHandler = object
        autohive_integrations_sdk.ActionResult = MockActionResult
        
        from microsoft_word import (
            ListDocuments,
            GetDocument,
            GetContent,
            CreateDocument,
            UpdateContent,
            InsertText,
            GetParagraphs,
            SearchReplace,
            ExportPdf,
            GetTables,
            ensure_docx_extension,
            count_words,
            count_characters,
            create_docx_from_text,
            parse_docx_content,
        )


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.fetch = AsyncMock()
    return context


class TestUtilities:
    def test_ensure_docx_extension_adds_extension(self):
        assert ensure_docx_extension("report") == "report.docx"
        assert ensure_docx_extension("my document") == "my document.docx"
    
    def test_ensure_docx_extension_preserves_existing(self):
        assert ensure_docx_extension("report.docx") == "report.docx"
        assert ensure_docx_extension("Report.DOCX") == "Report.DOCX"
    
    def test_count_words(self):
        assert count_words("Hello world") == 2
        assert count_words("One two three four") == 4
        assert count_words("") == 0
        assert count_words("Single") == 1
    
    def test_count_characters(self):
        assert count_characters("Hello") == 5
        assert count_characters("") == 0
        assert count_characters("Test 123") == 8


class TestCreateDocxFromText:
    def test_creates_valid_docx(self):
        text = "Hello world\nSecond paragraph"
        docx_bytes = create_docx_from_text(text)
        
        assert docx_bytes is not None
        assert len(docx_bytes) > 0
        assert docx_bytes[:4] == b'PK\x03\x04'
    
    def test_empty_text(self):
        docx_bytes = create_docx_from_text("")
        assert docx_bytes is not None
        assert len(docx_bytes) > 0
    
    def test_special_characters(self):
        text = "Test <xml> & 'quotes' \"double\""
        docx_bytes = create_docx_from_text(text)
        assert docx_bytes is not None


class TestParseDocxContent:
    def test_parse_simple_docx(self):
        text = "First paragraph\nSecond paragraph"
        docx_bytes = create_docx_from_text(text)
        
        parsed = parse_docx_content(docx_bytes)
        
        assert 'paragraphs' in parsed
        assert 'full_text' in parsed
        assert 'word_count' in parsed
        assert parsed['paragraph_count'] >= 2
    
    def test_parse_empty_docx(self):
        docx_bytes = create_docx_from_text("")
        parsed = parse_docx_content(docx_bytes)
        
        assert parsed['paragraph_count'] >= 0


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_list_documents_success(self, mock_context):
        mock_context.fetch.return_value = {
            'value': [
                {
                    'id': 'doc1',
                    'name': 'Report.docx',
                    'webUrl': 'https://example.com/doc1',
                    'lastModifiedDateTime': '2024-01-15T10:30:00Z',
                    'size': 45678,
                    'createdBy': {'user': {'displayName': 'John Doe'}}
                },
                {
                    'id': 'doc2',
                    'name': 'Notes.docx',
                    'webUrl': 'https://example.com/doc2',
                    'lastModifiedDateTime': '2024-01-14T09:00:00Z',
                    'size': 12345,
                    'createdBy': {'user': {'displayName': 'Jane Smith'}}
                }
            ]
        }
        
        action = ListDocuments()
        result = await action.execute({}, mock_context)
        
        assert result.is_success is True
        assert len(result.data['documents']) == 2
        assert result.data['documents'][0]['name'] == 'Report.docx'
    
    @pytest.mark.asyncio
    async def test_list_documents_with_filter(self, mock_context):
        mock_context.fetch.return_value = {'value': []}
        
        action = ListDocuments()
        result = await action.execute({
            'name_contains': 'Report',
            'folder_path': 'Documents'
        }, mock_context)
        
        assert result.is_success is True
        mock_context.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, mock_context):
        mock_context.fetch.return_value = {
            'value': [],
            '@odata.nextLink': 'https://graph.microsoft.com/v1.0/next-page'
        }
        
        action = ListDocuments()
        result = await action.execute({'page_size': 10}, mock_context)
        
        assert result.is_success is True
        assert result.data['next_page_token'] == 'https://graph.microsoft.com/v1.0/next-page'


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_get_document_success(self, mock_context):
        mock_context.fetch.return_value = {
            'id': 'doc123',
            'name': 'Test.docx',
            'size': 50000,
            'webUrl': 'https://example.com/doc',
            'createdDateTime': '2024-01-01T00:00:00Z',
            'lastModifiedDateTime': '2024-01-15T12:00:00Z'
        }
        
        action = GetDocument()
        result = await action.execute({'document_id': 'doc123'}, mock_context)
        
        assert result.is_success is True
        assert result.data['document']['id'] == 'doc123'
        assert result.data['document']['name'] == 'Test.docx'
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_context):
        mock_context.fetch.side_effect = Exception("Resource not found")
        
        action = GetDocument()
        result = await action.execute({'document_id': 'invalid'}, mock_context)
        
        assert result.is_success is False
        assert result.error is not None


class TestGetContent:
    @pytest.mark.asyncio
    async def test_get_content_text_format(self, mock_context):
        docx_bytes = create_docx_from_text("Hello world\nSecond line")
        mock_context.fetch.return_value = docx_bytes
        
        action = GetContent()
        result = await action.execute({
            'document_id': 'doc123',
            'format': 'text'
        }, mock_context)
        
        assert result.is_success is True
        assert 'content' in result.data
        assert result.data['word_count'] > 0
    
    @pytest.mark.asyncio
    async def test_get_content_html_format(self, mock_context):
        docx_bytes = create_docx_from_text("Test content")
        mock_context.fetch.return_value = docx_bytes
        
        action = GetContent()
        result = await action.execute({
            'document_id': 'doc123',
            'format': 'html'
        }, mock_context)
        
        assert result.is_success is True
        assert '<html>' in result.data['content']


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_document_success(self, mock_context):
        mock_context.fetch.return_value = {
            'id': 'new-doc-id',
            'name': 'NewDoc.docx',
            'webUrl': 'https://example.com/new-doc'
        }
        
        action = CreateDocument()
        result = await action.execute({
            'name': 'NewDoc',
            'content': 'Initial content'
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['document_id'] == 'new-doc-id'
        assert result.data['name'] == 'NewDoc.docx'
    
    @pytest.mark.asyncio
    async def test_create_document_with_folder(self, mock_context):
        mock_context.fetch.return_value = {
            'id': 'new-doc-id',
            'name': 'Report.docx',
            'webUrl': 'https://example.com/docs/report'
        }
        
        action = CreateDocument()
        result = await action.execute({
            'name': 'Report.docx',
            'folder_path': 'Documents/Reports',
            'content': 'Report content'
        }, mock_context)
        
        assert result.is_success is True


class TestUpdateContent:
    @pytest.mark.asyncio
    async def test_update_content_success(self, mock_context):
        mock_context.fetch.return_value = {}
        
        action = UpdateContent()
        result = await action.execute({
            'document_id': 'doc123',
            'content': 'New content here'
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['updated'] is True
        assert result.data['word_count'] == 3


class TestInsertText:
    @pytest.mark.asyncio
    async def test_insert_text_at_end(self, mock_context):
        docx_bytes = create_docx_from_text("Existing content")
        mock_context.fetch.side_effect = [docx_bytes, {}]
        
        action = InsertText()
        result = await action.execute({
            'document_id': 'doc123',
            'text': 'Appended text',
            'location': 'end'
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['inserted'] is True
    
    @pytest.mark.asyncio
    async def test_insert_text_at_start(self, mock_context):
        docx_bytes = create_docx_from_text("Existing content")
        mock_context.fetch.side_effect = [docx_bytes, {}]
        
        action = InsertText()
        result = await action.execute({
            'document_id': 'doc123',
            'text': 'Prepended text',
            'location': 'start'
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['inserted'] is True


class TestGetParagraphs:
    @pytest.mark.asyncio
    async def test_get_paragraphs_success(self, mock_context):
        docx_bytes = create_docx_from_text("First paragraph\nSecond paragraph\nThird paragraph")
        mock_context.fetch.return_value = docx_bytes
        
        action = GetParagraphs()
        result = await action.execute({'document_id': 'doc123'}, mock_context)
        
        assert result.is_success is True
        assert 'paragraphs' in result.data
        assert result.data['total_count'] > 0
    
    @pytest.mark.asyncio
    async def test_get_paragraphs_with_range(self, mock_context):
        docx_bytes = create_docx_from_text("P1\nP2\nP3\nP4\nP5")
        mock_context.fetch.return_value = docx_bytes
        
        action = GetParagraphs()
        result = await action.execute({
            'document_id': 'doc123',
            'start_index': 1,
            'count': 2
        }, mock_context)
        
        assert result.is_success is True
        assert len(result.data['paragraphs']) <= 2


class TestSearchReplace:
    @pytest.mark.asyncio
    async def test_search_replace_success(self, mock_context):
        docx_bytes = create_docx_from_text("Hello {{name}}, welcome!")
        mock_context.fetch.side_effect = [docx_bytes, {}]
        
        action = SearchReplace()
        result = await action.execute({
            'document_id': 'doc123',
            'search_text': '{{name}}',
            'replace_text': 'John'
        }, mock_context)
        
        assert result.is_success is True
    
    @pytest.mark.asyncio
    async def test_search_replace_no_match(self, mock_context):
        docx_bytes = create_docx_from_text("Hello world")
        mock_context.fetch.return_value = docx_bytes
        
        action = SearchReplace()
        result = await action.execute({
            'document_id': 'doc123',
            'search_text': 'xyz123',
            'replace_text': 'replacement'
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['replaced'] is False
        assert result.data['replacement_count'] == 0


class TestExportPdf:
    @pytest.mark.asyncio
    async def test_export_pdf_base64(self, mock_context):
        mock_context.fetch.return_value = b'%PDF-1.4 fake pdf content'
        
        action = ExportPdf()
        result = await action.execute({'document_id': 'doc123'}, mock_context)
        
        assert result.is_success is True
        assert 'pdf_content' in result.data
        assert result.data['encoding'] == 'base64'
        assert result.data['content_type'] == 'application/pdf'
    
    @pytest.mark.asyncio
    async def test_export_pdf_save_to_drive(self, mock_context):
        mock_context.fetch.side_effect = [
            b'%PDF-1.4 fake pdf content',
            {'id': 'doc123', 'name': 'Report.docx'},
            {'id': 'pdf-id', 'name': 'Report.pdf', 'webUrl': 'https://example.com/pdf', 'size': 12345}
        ]
        
        action = ExportPdf()
        result = await action.execute({
            'document_id': 'doc123',
            'save_to_drive': True
        }, mock_context)
        
        assert result.is_success is True
        assert result.data['pdf_url'] == 'https://example.com/pdf'


class TestGetTables:
    @pytest.mark.asyncio
    async def test_get_tables_empty(self, mock_context):
        docx_bytes = create_docx_from_text("No tables here")
        mock_context.fetch.return_value = docx_bytes
        
        action = GetTables()
        result = await action.execute({'document_id': 'doc123'}, mock_context)
        
        assert result.is_success is True
        assert result.data['tables'] == []
        assert result.data['table_count'] == 0

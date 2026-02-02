from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler
from typing import Dict, Any, List, Optional

google_docs = Integration.load()

# Google Docs API base URL
DOCS_API_BASE = "https://docs.googleapis.com/v1"


def handle_api_error(error: Exception, message: str = "Google API error") -> Dict[str, Any]:
    """Handle API error responses."""
    return {'result': False, 'error': f'{message}: {str(error)}'}


# ---- Action Handlers ----

@google_docs.action("docs_create")
class CreateDocument(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Create a new Google Doc."""
        try:
            title = inputs.get('title', 'Untitled Document')
            url = f"{DOCS_API_BASE}/documents"
            payload = {'title': title}

            document = await context.fetch(url, method="POST", json=payload)

            document_id = document.get('documentId')
            document_url = f"https://docs.google.com/document/d/{document_id}/edit"

            return {
                'documentId': document_id,
                'documentUrl': document_url,
                'title': document.get('title'),
                'result': True
            }
        except Exception as e:
            return handle_api_error(e, "Failed to create document")


@google_docs.action("docs_get")
class GetDocument(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Retrieve full document content."""
        try:
            document_id = inputs['document_id']
            include_tabs = inputs.get('include_tabs_content', True)

            # Build the URL with query parameters
            url = f"{DOCS_API_BASE}/documents/{document_id}"
            params = {}

            if include_tabs:
                params['includeTabsContent'] = 'true'

            document = await context.fetch(url, method="GET", params=params)

            return {
                'document': document,
                'result': True
            }
        except Exception as e:
            error_result = handle_api_error(e, "Failed to get document")
            error_result['document'] = {}
            return error_result


@google_docs.action("docs_insert_paragraphs")
class InsertParagraphs(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Insert multiple plain text paragraphs into the document.

        This action is for inserting bulk plain paragraphs without markdown formatting.
        Each paragraph will be separated by double newlines.

        For structured content with headings, use docs_smart_insert_with_tabs instead.

        Inputs:
        - document_id: The document ID
        - paragraphs: Array of paragraph text strings
        - append: If true, append to end; if false, insert at beginning (default: true)
        - tab_id: Optional tab ID if working with a specific tab
        """
        try:
            document_id = inputs['document_id']
            paragraphs = inputs['paragraphs']
            tab_id = inputs.get('tab_id')
            append = inputs.get('append', True)

            # Validate paragraphs is an array
            if not isinstance(paragraphs, list):
                return {'result': False, 'error': 'paragraphs must be an array of strings'}

            if not paragraphs:
                return {'result': False, 'error': 'paragraphs array is empty'}

            # Get insertion index
            if append:
                # Get the end index for appending
                url = f"{DOCS_API_BASE}/documents/{document_id}"
                params = {}

                if tab_id:
                    params['includeTabsContent'] = 'true'
                    params['fields'] = 'tabs(tabId,documentTab/body/content(endIndex))'
                else:
                    params['fields'] = 'body/content(endIndex)'

                document = await context.fetch(url, method="GET", params=params)

                if tab_id:
                    index = None
                    for tab in document.get('tabs', []):
                        if tab.get('tabId') == tab_id:
                            doc_tab = tab.get('documentTab', {})
                            body = doc_tab.get('body', {})
                            content = body.get('content', [])
                            index = content[-1].get('endIndex', 1) - 1 if content else 1
                            break
                    if index is None:
                        return {'result': False, 'error': f'Tab with ID {tab_id} not found'}
                else:
                    body = document.get('body', {})
                    content = body.get('content', [])
                    index = content[-1].get('endIndex', 1) - 1 if content else 1
            else:
                # Insert at beginning
                index = 1

            # Build batch requests for all paragraphs
            batch_requests = []
            current_index = index

            for paragraph in paragraphs:
                para_text = str(paragraph) + '\n\n'
                insert_request = {
                    'insertText': {
                        'text': para_text,
                        'location': {'index': current_index}
                    }
                }

                if tab_id:
                    insert_request['insertText']['location']['tabId'] = tab_id

                batch_requests.append(insert_request)
                current_index += len(para_text)

            # Execute batch insert
            url = f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate"
            payload = {'requests': batch_requests}

            await context.fetch(url, method="POST", json=payload)

            return {
                'result': True,
                'paragraphs_inserted': len(paragraphs),
                'inserted_at_index': index
            }
        except Exception as e:
            return handle_api_error(e, "Failed to insert paragraphs")


@google_docs.action("docs_batch_update")
class BatchUpdate(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute multiple document updates in a single batch request.

        This is a flexible action that can handle any Google Docs API request type.

        Common use cases:

        1. Insert text:
           {"insertText": {"text": "Hello", "location": {"index": 1}}}

        2. Apply bold formatting:
           {"updateTextStyle": {
               "range": {"startIndex": 1, "endIndex": 10},
               "textStyle": {"bold": true},
               "fields": "bold"
           }}

        3. Apply italic formatting:
           {"updateTextStyle": {
               "range": {"startIndex": 1, "endIndex": 10},
               "textStyle": {"italic": true},
               "fields": "italic"
           }}

        4. Apply multiple text styles (bold + italic + font size):
           {"updateTextStyle": {
               "range": {"startIndex": 1, "endIndex": 10},
               "textStyle": {
                   "bold": true,
                   "italic": true,
                   "fontSize": {"magnitude": 14, "unit": "PT"}
               },
               "fields": "bold,italic,fontSize"
           }}

        5. Apply paragraph style (heading):
           {"updateParagraphStyle": {
               "range": {"startIndex": 1, "endIndex": 20},
               "paragraphStyle": {"namedStyleType": "HEADING_1"},
               "fields": "namedStyleType"
           }}

        6. Change text color:
           {"updateTextStyle": {
               "range": {"startIndex": 1, "endIndex": 10},
               "textStyle": {
                   "foregroundColor": {
                       "color": {"rgbColor": {"red": 1.0, "green": 0.0, "blue": 0.0}}
                   }
               },
               "fields": "foregroundColor"
           }}

        Inputs:
        - document_id: The document ID
        - requests: Array of Google Docs API request objects
        """
        try:
            document_id = inputs['document_id']
            batch_requests = inputs['requests']

            # Validate requests is a list of dicts
            if not isinstance(batch_requests, list) or not all(isinstance(r, dict) for r in batch_requests):
                return {'result': False, 'error': 'requests must be an array of objects'}

            url = f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate"
            payload = {'requests': batch_requests}

            result = await context.fetch(url, method="POST", json=payload)

            return {
                'replies': result.get('replies', []),
                'result': True
            }
        except Exception as e:
            error_result = handle_api_error(e, "Failed to execute batch update")
            error_result['replies'] = []
            return error_result


@google_docs.action("docs_parse_structure")
class ParseStructure(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Parse document structure to identify headings, paragraphs, and their positions."""
        try:
            document_id = inputs['document_id']
            tab_id = inputs.get('tab_id')

            # Fetch document with full content
            url = f"{DOCS_API_BASE}/documents/{document_id}"
            params = {}

            if tab_id:
                params['includeTabsContent'] = 'true'

            document = await context.fetch(url, method="GET", params=params)

            # Get the body content
            if tab_id:
                # Find the specific tab
                body = None
                for tab in document.get('tabs', []):
                    if tab.get('tabId') == tab_id:
                        doc_tab = tab.get('documentTab', {})
                        body = doc_tab.get('body', {})
                        break
                if body is None:
                    return {'result': False, 'error': f'Tab with ID {tab_id} not found'}
            else:
                body = document.get('body', {})

            content = body.get('content', [])

            # Parse the structure
            structure = []
            for element in content:
                # Skip elements without proper indices
                start_index = element.get('startIndex')
                end_index = element.get('endIndex')

                if start_index is None or end_index is None:
                    continue

                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    para_style = paragraph.get('paragraphStyle', {})
                    named_style = para_style.get('namedStyleType', 'NORMAL_TEXT')

                    # Extract text content
                    text_content = ''
                    for text_element in paragraph.get('elements', []):
                        if 'textRun' in text_element:
                            text_content += text_element['textRun'].get('content', '')

                    # Determine if it's a heading or body paragraph
                    element_type = 'heading' if named_style.startswith('HEADING') or named_style in ['TITLE', 'SUBTITLE'] else 'paragraph'

                    structure_element = {
                        'type': element_type,
                        'style': named_style,
                        'text': text_content.strip(),
                        'startIndex': start_index,
                        'endIndex': end_index
                    }

                    # Add alignment if present
                    if 'alignment' in para_style:
                        structure_element['alignment'] = para_style['alignment']

                    structure.append(structure_element)
                elif 'table' in element:
                    structure.append({
                        'type': 'table',
                        'startIndex': start_index,
                        'endIndex': end_index
                    })
                elif 'sectionBreak' in element:
                    structure.append({
                        'type': 'section_break',
                        'startIndex': start_index,
                        'endIndex': end_index
                    })

            return {
                'structure': structure,
                'result': True
            }
        except Exception as e:
            error_result = handle_api_error(e, "Failed to parse document structure")
            error_result['structure'] = []
            return error_result


@google_docs.action("docs_insert_markdown_content")
class InsertMarkdownContent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Insert markdown-formatted content with automatic styling.

        Features:
        - Parses ALL markdown headings (# H1, ## H2, ### H3, etc.) in a single call
        - Parses inline formatting: **bold** and *italic*
        - Automatically applies Google Docs styles (headings, bold, italic)
        - Inserts and styles in a single batch operation
        - No duplicate content

        Inputs:
        - document_id: The document ID
        - content: Markdown text with headings and inline formatting
        - tab_id: Optional tab ID if working with a specific tab
        - append: If true, append to end of document (default: True)
        """
        try:
            document_id = inputs['document_id']
            content = inputs['content']
            tab_id = inputs.get('tab_id')
            append = inputs.get('append', True)

            # Step 1: Parse content into structured elements
            elements = self._parse_markdown(content)

            if not elements:
                return {'result': False, 'error': 'No content found to insert'}

            # Step 2: Get the insertion index
            insertion_index = await self._get_insertion_index(
                context, document_id, tab_id, append
            )

            # Step 3: Insert all content with styles in a single batch operation
            result = await self._insert_and_style_content(
                context, document_id, tab_id, elements, insertion_index
            )

            return result

        except Exception as e:
            return handle_api_error(e, "Failed to insert markdown content")

    def _parse_markdown(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse markdown content into structured elements with heading levels and inline formatting.

        Returns a list of elements, each with:
        - type: 'heading' or 'paragraph'
        - text: plain text (without markdown symbols)
        - level: heading level (1-6) if type is 'heading'
        - formatting: list of {type, start, end} for inline formatting
        """
        import re

        elements = []
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                i += 1
                continue

            # Check for headings (# to ######)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2)

                # Parse inline formatting in heading
                plain_text, formatting = self._parse_inline_formatting(heading_text)

                elements.append({
                    'type': 'heading',
                    'level': level,
                    'text': plain_text,
                    'formatting': formatting
                })
                i += 1
                continue

            # Otherwise, it's a paragraph - collect until empty line
            para_lines = []
            while i < len(lines) and lines[i].strip():
                para_lines.append(lines[i].strip())
                i += 1

            if para_lines:
                para_text = ' '.join(para_lines)
                plain_text, formatting = self._parse_inline_formatting(para_text)

                elements.append({
                    'type': 'paragraph',
                    'text': plain_text,
                    'formatting': formatting
                })

        return elements

    def _parse_inline_formatting(self, text: str) -> tuple:
        """
        Parse inline formatting (bold, italic) from markdown text.

        Returns:
        - plain_text: text without markdown symbols
        - formatting: list of {type: 'bold'/'italic', start: int, end: int}
        """
        import re

        formatting = []
        plain_text = ""
        offset = 0  # Track position in plain text

        # Process text character by character to handle nested/overlapping formatting
        i = 0
        while i < len(text):
            # Check for bold (**text**)
            if i + 1 < len(text) and text[i:i+2] == '**':
                # Find closing **
                end = text.find('**', i + 2)
                if end != -1:
                    bold_text = text[i+2:end]
                    start_pos = offset
                    plain_text += bold_text
                    end_pos = offset + len(bold_text)
                    formatting.append({
                        'type': 'bold',
                        'start': start_pos,
                        'end': end_pos
                    })
                    offset += len(bold_text)
                    i = end + 2
                    continue

            # Check for italic (*text*) - but not part of **
            if text[i] == '*' and (i == 0 or text[i-1] != '*') and (i + 1 >= len(text) or text[i+1] != '*'):
                # Find closing *
                end = i + 1
                while end < len(text):
                    if text[end] == '*' and (end + 1 >= len(text) or text[end+1] != '*'):
                        break
                    end += 1

                if end < len(text):
                    italic_text = text[i+1:end]
                    start_pos = offset
                    plain_text += italic_text
                    end_pos = offset + len(italic_text)
                    formatting.append({
                        'type': 'italic',
                        'start': start_pos,
                        'end': end_pos
                    })
                    offset += len(italic_text)
                    i = end + 1
                    continue

            # Regular character
            plain_text += text[i]
            offset += 1
            i += 1

        return plain_text, formatting

    async def _get_insertion_index(self, context: ExecutionContext,
                                   document_id: str, tab_id: Optional[str],
                                   append: bool) -> int:
        """Get the index where content should be inserted."""
        if not append:
            return 1  # Insert at beginning

        # Get end index for appending
        url = f"{DOCS_API_BASE}/documents/{document_id}"
        params = {}

        if tab_id:
            params['includeTabsContent'] = 'true'
            params['fields'] = 'tabs(tabId,documentTab/body/content(endIndex))'
        else:
            params['fields'] = 'body/content(endIndex)'

        try:
            document = await context.fetch(url, method="GET", params=params)
        except Exception:
            return 1  # Default to beginning on error

        if tab_id:
            for tab in document.get('tabs', []):
                if tab.get('tabId') == tab_id:
                    doc_tab = tab.get('documentTab', {})
                    body = doc_tab.get('body', {})
                    content = body.get('content', [])
                    return content[-1].get('endIndex', 1) - 1 if content else 1
            return 1
        else:
            body = document.get('body', {})
            content = body.get('content', [])
            return content[-1].get('endIndex', 1) - 1 if content else 1

    async def _insert_and_style_content(self, context: ExecutionContext,
                                        document_id: str, tab_id: Optional[str],
                                        elements: List[Dict[str, Any]],
                                        start_index: int) -> Dict[str, Any]:
        """
        Insert all content and apply styles in a single batch operation.
        """
        try:
            batch_requests = []
            current_index = start_index

            # Map heading level to Google Docs heading style
            heading_style_map = {
                1: 'HEADING_1',
                2: 'HEADING_2',
                3: 'HEADING_3',
                4: 'HEADING_4',
                5: 'HEADING_5',
                6: 'HEADING_6'
            }

            heading_count = 0
            paragraph_count = 0

            # Build all insertion and styling requests
            for element in elements:
                element_type = element['type']
                text = element['text']
                formatting = element.get('formatting', [])

                # Add newline for proper spacing
                if element_type == 'heading':
                    full_text = text + '\n'
                else:
                    full_text = text + '\n\n'

                # Insert text
                insert_request = {
                    'insertText': {
                        'text': full_text,
                        'location': {'index': current_index}
                    }
                }
                if tab_id:
                    insert_request['insertText']['location']['tabId'] = tab_id
                batch_requests.append(insert_request)

                # Apply paragraph-level style for headings
                if element_type == 'heading':
                    level = element['level']
                    heading_style = heading_style_map.get(level, 'HEADING_1')

                    style_request = {
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': current_index,
                                'endIndex': current_index + len(full_text)
                            },
                            'paragraphStyle': {
                                'namedStyleType': heading_style
                            },
                            'fields': 'namedStyleType'
                        }
                    }
                    if tab_id:
                        style_request['updateParagraphStyle']['range']['tabId'] = tab_id
                    batch_requests.append(style_request)
                    heading_count += 1
                else:
                    paragraph_count += 1

                # Apply inline formatting (bold, italic)
                for fmt in formatting:
                    fmt_type = fmt['type']
                    fmt_start = current_index + fmt['start']
                    fmt_end = current_index + fmt['end']

                    text_style = {}
                    fields = []

                    if fmt_type == 'bold':
                        text_style['bold'] = True
                        fields.append('bold')
                    elif fmt_type == 'italic':
                        text_style['italic'] = True
                        fields.append('italic')

                    if text_style:
                        style_request = {
                            'updateTextStyle': {
                                'range': {
                                    'startIndex': fmt_start,
                                    'endIndex': fmt_end
                                },
                                'textStyle': text_style,
                                'fields': ','.join(fields)
                            }
                        }
                        if tab_id:
                            style_request['updateTextStyle']['range']['tabId'] = tab_id
                        batch_requests.append(style_request)

                current_index += len(full_text)

            # Execute all insertions and styling in a single batch
            url = f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate"
            payload = {'requests': batch_requests}

            await context.fetch(url, method="POST", json=payload)

            return {
                'result': True,
                'headings_inserted': heading_count,
                'paragraphs_inserted': paragraph_count,
                'total_elements': len(elements)
            }

        except Exception as e:
            return handle_api_error(e, "Failed to insert and style content")


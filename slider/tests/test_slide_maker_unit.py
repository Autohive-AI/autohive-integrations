import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("slide_maker_mod", os.path.join(_parent, "slide_maker.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

slide_maker = _mod.slide_maker  # the Integration instance
detect_placeholders_with_metadata = _mod.detect_placeholders_with_metadata
has_markdown_formatting = _mod.has_markdown_formatting
calculate_best_fit_font_size = _mod.calculate_best_fit_font_size
hex_to_rgb = _mod.hex_to_rgb
detect_element_type_from_markdown = _mod.detect_element_type_from_markdown

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- Helper Function Tests ----


class TestHexToRgb:
    def test_red(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_without_hash(self):
        assert hex_to_rgb("#003366") == (0, 51, 102)


class TestHasMarkdownFormatting:
    def test_bold(self):
        assert has_markdown_formatting("**Bold text**") is True

    def test_italic(self):
        assert has_markdown_formatting("*italic*") is True

    def test_code(self):
        assert has_markdown_formatting("`code`") is True

    def test_underline(self):
        assert has_markdown_formatting("__underline__") is True

    def test_plain_text(self):
        assert has_markdown_formatting("Plain text") is False

    def test_empty_string(self):
        assert has_markdown_formatting("") is False

    def test_mixed(self):
        assert has_markdown_formatting("**Bold** and *italic*") is True


class TestDetectElementTypeFromMarkdown:
    def test_table_detection(self):
        table_md = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        assert detect_element_type_from_markdown(table_md) == "table"

    def test_bullet_detection(self):
        bullets_md = "- Item 1\n- Item 2\n- Item 3"
        assert detect_element_type_from_markdown(bullets_md) == "bullets"

    def test_numbered_list_detection(self):
        numbered_md = "1. First\n2. Second\n3. Third"
        assert detect_element_type_from_markdown(numbered_md) == "bullets"

    def test_text_detection(self):
        assert detect_element_type_from_markdown("Plain text paragraph") == "text"

    def test_bold_text_is_text(self):
        assert detect_element_type_from_markdown("**Bold heading**") == "text"


class TestDetectPlaceholdersWithMetadata:
    def test_simple_bracket(self):
        placeholders, _ = detect_placeholders_with_metadata("[Company Name]")
        assert placeholders == ["[Company Name]"]

    def test_curly_brace(self):
        placeholders, _ = detect_placeholders_with_metadata("{Company}")
        assert placeholders == ["{Company}"]

    def test_double_curly(self):
        placeholders, _ = detect_placeholders_with_metadata("{{Date}}")
        assert placeholders == ["{{Date}}"]

    def test_multiple_placeholders(self):
        placeholders, _ = detect_placeholders_with_metadata("[A] and [B] and [C]")
        assert len(placeholders) == 3
        assert "[A]" in placeholders

    def test_no_placeholders(self):
        placeholders, _ = detect_placeholders_with_metadata("Plain text with no placeholders")
        assert placeholders == []

    def test_special_characters(self):
        placeholders, _ = detect_placeholders_with_metadata("[$x,xxx]")
        assert placeholders == ["[$x,xxx]"]

    def test_fontsize_metadata(self):
        _, metadata = detect_placeholders_with_metadata("[Title, Fontsize=32pt]")
        meta = metadata.get("[Title, Fontsize=32pt]", {})
        assert meta.get("fontsize") == "32pt"

    def test_bold_shorthand(self):
        _, metadata = detect_placeholders_with_metadata("[Title, Bold]")
        meta = metadata.get("[Title, Bold]", {})
        assert meta.get("bold") == "true"

    def test_bold_negation(self):
        _, metadata = detect_placeholders_with_metadata("[Text, !Bold]")
        meta = metadata.get("[Text, !Bold]", {})
        assert meta.get("bold") == "false"

    def test_color_extraction(self):
        _, metadata = detect_placeholders_with_metadata("[Title, Color=#FF0000]")
        meta = metadata.get("[Title, Color=#FF0000]", {})
        assert meta.get("color") == "#FF0000"

    def test_font_extraction(self):
        _, metadata = detect_placeholders_with_metadata("[Title, Font=Sofia Pro]")
        meta = metadata.get("[Title, Font=Sofia Pro]", {})
        assert meta.get("font") == "Sofia Pro"

    def test_complex_metadata(self):
        text = "[Title, Fontsize=32pt, Bold, !Italic, Color=#003366]"
        _, metadata = detect_placeholders_with_metadata(text)
        meta = metadata.get(text, {})
        assert meta.get("fontsize") == "32pt"
        assert meta.get("bold") == "true"
        assert meta.get("italic") == "false"
        assert meta.get("color") == "#003366"

    def test_simple_placeholder_no_metadata(self):
        _, metadata = detect_placeholders_with_metadata("[Company]")
        assert metadata == {}

    def test_email_like_placeholder(self):
        placeholders, _ = detect_placeholders_with_metadata("[email@example.com]")
        assert placeholders == ["[email@example.com]"]


class TestCalculateBestFitFontSize:
    def test_short_text_stays_at_max(self):
        size = calculate_best_fit_font_size("Hello", width_inches=8.0, height_inches=2.0, max_font_size=24)
        assert size == 24

    def test_long_text_scales_down(self):
        long_text = "This is a very long piece of text that contains significantly more content " * 5
        size = calculate_best_fit_font_size(long_text, width_inches=4.0, height_inches=1.0, max_font_size=18)
        assert size < 18

    def test_minimum_size_enforced(self):
        very_long_text = "Text " * 1000
        size = calculate_best_fit_font_size(very_long_text, width_inches=1.0, height_inches=0.5, max_font_size=18)
        assert size >= 10

    def test_empty_text_returns_max(self):
        size = calculate_best_fit_font_size("", width_inches=5.0, height_inches=2.0, max_font_size=20)
        assert size == 20


# ---- Action Tests ----


class TestCreatePresentation:
    @pytest.mark.asyncio
    async def test_create_blank_presentation(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert "presentation_id" in result.result.data
        assert result.result.data["slide_count"] >= 1
        assert result.result.data["saved"] is True
        assert "file" in result.result.data

    @pytest.mark.asyncio
    async def test_create_with_title(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {"title": "Test Slide"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["presentation_id"] is not None

    @pytest.mark.asyncio
    async def test_create_with_title_and_subtitle(self, mock_context):
        result = await slide_maker.execute_action(
            "create_presentation",
            {"title": "**Bold Title**", "subtitle": "A subtitle here"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["slide_count"] >= 1

    @pytest.mark.asyncio
    async def test_response_has_file_object(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {}, mock_context)

        assert result.type == ResultType.ACTION
        file_obj = result.result.data["file"]
        assert "content" in file_obj
        assert "name" in file_obj
        assert file_obj["contentType"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    @pytest.mark.asyncio
    async def test_custom_filename(self, mock_context):
        result = await slide_maker.execute_action(
            "create_presentation", {"custom_filename": "my_presentation"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["file"]["name"] == "my_presentation.pptx"


class TestAddSlide:
    @pytest.mark.asyncio
    async def test_add_slide_increases_count(self, mock_context):
        # First create a presentation
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        assert create_result.type == ResultType.ACTION
        presentation_id = create_result.result.data["presentation_id"]
        initial_count = create_result.result.data["slide_count"]

        # Then add a slide
        result = await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["slide_count"] == initial_count + 1

    @pytest.mark.asyncio
    async def test_add_slide_returns_slide_index(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)

        assert result.type == ResultType.ACTION
        assert "slide_index" in result.result.data

    @pytest.mark.asyncio
    async def test_add_slide_missing_presentation_raises_error(self, mock_context):
        # The action raises ValueError when presentation not found and no files provided
        with pytest.raises(ValueError, match="not found and no files provided"):
            await slide_maker.execute_action("add_slide", {"presentation_id": "nonexistent-id-12345"}, mock_context)


class TestGetSlideElements:
    @pytest.mark.asyncio
    async def test_get_elements_single_slide(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id, "slide_index": 0},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["slide_index"] == 0
        assert "total_elements" in result.result.data
        assert "elements" in result.result.data

    @pytest.mark.asyncio
    async def test_get_elements_all_slides(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements", {"presentation_id": presentation_id}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert "total_slides" in result.result.data
        assert "slides" in result.result.data


class TestSetSlideBackgroundColor:
    @pytest.mark.asyncio
    async def test_set_hex_background_color(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "set_slide_background_color",
            {"presentation_id": presentation_id, "slide_index": 0, "color": "#FF0000"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_set_rgb_background_color(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "set_slide_background_color",
            {"presentation_id": presentation_id, "slide_index": 0, "color": {"rgb": [0, 0, 255]}},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True


class TestAddElements:
    @pytest.mark.asyncio
    async def test_add_text_element(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Hello World"}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["successfully_added"] >= 1

    @pytest.mark.asyncio
    async def test_add_elements_auto_layout(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "auto_layout": True,
                "markdown": "# Title\n\nSome paragraph text.",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["mode"] == "auto_layout"

    @pytest.mark.asyncio
    async def test_add_table_element(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        table_md = "| Name | Value |\n|------|-------|\n| A | 1 |\n| B | 2 |"
        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": table_md}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION

    @pytest.mark.asyncio
    async def test_add_elements_response_structure(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Test content"}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "mode" in data
        assert "total_requested" in data
        assert "successfully_added" in data
        assert "elements_added" in data
        assert "saved" in data


class TestDeleteElement:
    @pytest.mark.asyncio
    async def test_delete_element(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        # Add an element first
        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Element to delete"}],
            },
            mock_context,
        )

        # Delete it
        result = await slide_maker.execute_action(
            "delete_element",
            {"presentation_id": presentation_id, "slide_index": 0, "shape_index": 0},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["deleted"] is True


class TestFindAndReplace:
    @pytest.mark.asyncio
    async def test_find_and_replace_text(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        # Add text with a placeholder
        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "[Company Name]"}],
            },
            mock_context,
        )

        # Replace the placeholder
        result = await slide_maker.execute_action(
            "find_and_replace",
            {
                "presentation_id": presentation_id,
                "replacements": [{"find": "[Company Name]", "replace": "Autohive"}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert "status" in result.result.data
        assert "summary" in result.result.data

    @pytest.mark.asyncio
    async def test_find_and_replace_not_found(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "find_and_replace",
            {
                "presentation_id": presentation_id,
                "replacements": [{"find": "[NonExistentPlaceholder]", "replace": "Value"}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["status"] in ("all_failed", "partial_success")

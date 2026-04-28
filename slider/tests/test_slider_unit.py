import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("slide_maker_mod", os.path.join(_parent, "slide_maker.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

slide_maker = _mod.slide_maker
presentations = _mod.presentations

# Helper functions exposed for direct testing
detect_placeholders_with_metadata = _mod.detect_placeholders_with_metadata
strip_conflicting_markdown = _mod.strip_conflicting_markdown
hex_to_rgb = _mod.hex_to_rgb
calculate_overlap = _mod.calculate_overlap
has_markdown_formatting = _mod.has_markdown_formatting

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


@pytest.fixture(autouse=True)
def clear_presentations():
    """Clear global presentations dict before each test to avoid cross-test pollution."""
    presentations.clear()
    yield
    presentations.clear()


# ---- Helper Function Tests ----


class TestHexToRgb:
    def test_red(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_without_hash(self):
        assert hex_to_rgb("0080FF") == (0, 128, 255)


class TestDetectPlaceholders:
    def test_bracket_placeholder(self):
        placeholders, metadata = detect_placeholders_with_metadata("[Title]")
        assert "[Title]" in placeholders

    def test_curly_placeholder(self):
        placeholders, metadata = detect_placeholders_with_metadata("{Name}")
        assert "{Name}" in placeholders

    def test_double_curly_placeholder(self):
        placeholders, metadata = detect_placeholders_with_metadata("{{Date}}")
        assert "{{Date}}" in placeholders

    def test_metadata_extraction(self):
        placeholders, metadata = detect_placeholders_with_metadata("[Title, Fontsize=32pt, Bold=true]")
        assert len(placeholders) == 1
        key = placeholders[0]
        assert metadata[key]["fontsize"] == "32pt"
        assert metadata[key]["bold"] == "true"

    def test_empty_text(self):
        placeholders, metadata = detect_placeholders_with_metadata("")
        assert placeholders == []
        assert metadata == {}

    def test_none_text(self):
        placeholders, metadata = detect_placeholders_with_metadata(None)
        assert placeholders == []
        assert metadata == {}

    def test_no_placeholders(self):
        placeholders, metadata = detect_placeholders_with_metadata("Just plain text")
        assert placeholders == []


class TestStripConflictingMarkdown:
    def test_strip_bold_when_metadata_bold(self):
        result = strip_conflicting_markdown("**Hello**", {"bold": "true"})
        assert "**" not in result
        assert "Hello" in result

    def test_no_strip_when_no_metadata(self):
        result = strip_conflicting_markdown("**Hello**", {})
        assert result == "**Hello**"

    def test_none_metadata(self):
        result = strip_conflicting_markdown("**Hello**", None)
        assert result == "**Hello**"


class TestCalculateOverlap:
    def test_no_overlap(self):
        e1 = {"left": 0, "top": 0, "right": 2, "bottom": 2, "width": 2, "height": 2}
        e2 = {"left": 3, "top": 3, "right": 5, "bottom": 5, "width": 2, "height": 2}
        result = calculate_overlap(e1, e2)
        assert result["overlaps"] is False

    def test_full_overlap(self):
        e1 = {"left": 0, "top": 0, "right": 4, "bottom": 4, "width": 4, "height": 4}
        e2 = {"left": 1, "top": 1, "right": 3, "bottom": 3, "width": 2, "height": 2}
        result = calculate_overlap(e1, e2)
        assert result["overlaps"] is True
        assert result["overlap_area"] == pytest.approx(4.0)


class TestHasMarkdownFormatting:
    def test_bold(self):
        assert has_markdown_formatting("**bold**") is True

    def test_italic(self):
        assert has_markdown_formatting("*italic*") is True

    def test_plain_text(self):
        assert has_markdown_formatting("plain text") is False


# ---- Action Tests ----


class TestCreatePresentation:
    @pytest.mark.asyncio
    async def test_creates_blank_presentation(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        assert result.type == ResultType.ACTION
        assert "presentation_id" in result.result.data
        assert result.result.data["slide_count"] >= 1
        assert result.result.data["saved"] is True

    @pytest.mark.asyncio
    async def test_creates_presentation_with_title(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {"title": "My Title"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["presentation_id"] is not None

    @pytest.mark.asyncio
    async def test_creates_presentation_with_title_and_subtitle(self, mock_context):
        result = await slide_maker.execute_action(
            "create_presentation",
            {"title": "My Title", "subtitle": "My Subtitle"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["slide_count"] >= 1

    @pytest.mark.asyncio
    async def test_returns_file_object(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        assert result.type == ResultType.ACTION
        file_obj = result.result.data["file"]
        assert "content" in file_obj
        assert "name" in file_obj
        assert "contentType" in file_obj
        assert file_obj["contentType"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    @pytest.mark.asyncio
    async def test_custom_filename(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {"custom_filename": "my_deck"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["file"]["name"] == "my_deck.pptx"

    @pytest.mark.asyncio
    async def test_custom_filename_with_extension(self, mock_context):
        result = await slide_maker.execute_action(
            "create_presentation", {"custom_filename": "my_deck.pptx"}, mock_context
        )
        assert result.type == ResultType.ACTION
        # Should not have double .pptx extension
        assert result.result.data["file"]["name"] == "my_deck.pptx"

    @pytest.mark.asyncio
    async def test_markdown_title(self, mock_context):
        result = await slide_maker.execute_action("create_presentation", {"title": "**Bold Title**"}, mock_context)
        assert result.type == ResultType.ACTION


class TestAddSlide:
    @pytest.mark.asyncio
    async def test_adds_slide_to_existing_presentation(self, mock_context):
        # First create a presentation
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["slide_count"] == 2
        assert result.result.data["slide_index"] == 1

    @pytest.mark.asyncio
    async def test_add_multiple_slides(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)
        result = await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["slide_count"] == 3

    @pytest.mark.asyncio
    async def test_add_slide_invalid_presentation_id(self, mock_context):
        with pytest.raises(ValueError, match="not found"):
            await slide_maker.execute_action("add_slide", {"presentation_id": "nonexistent-id"}, mock_context)

    @pytest.mark.asyncio
    async def test_returns_file(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action("add_slide", {"presentation_id": presentation_id}, mock_context)
        assert result.type == ResultType.ACTION
        assert "file" in result.result.data
        assert result.result.data["saved"] is True


class TestGetSlideElements:
    @pytest.mark.asyncio
    async def test_get_elements_empty_slide(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id, "slide_index": 0},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "slide_index" in result.result.data
        assert result.result.data["slide_index"] == 0
        assert "elements" in result.result.data

    @pytest.mark.asyncio
    async def test_get_all_slides_elements(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "total_slides" in result.result.data
        assert "slides" in result.result.data

    @pytest.mark.asyncio
    async def test_slide_dimensions_present(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id, "slide_index": 0},
            mock_context,
        )
        assert "slide_dimensions" in result.result.data
        dims = result.result.data["slide_dimensions"]
        assert "width" in dims
        assert "height" in dims
        assert dims["width"] > 0
        assert dims["height"] > 0

    @pytest.mark.asyncio
    async def test_get_elements_invalid_slide_index(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id, "slide_index": 999},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


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
        assert result.result.data["successfully_added"] == 1
        assert result.result.data["mode"] == "granular"

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
                "markdown": "# Title\n\nSome content",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["mode"] == "auto_layout"

    @pytest.mark.asyncio
    async def test_add_elements_returns_file(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Test text"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "file" in result.result.data

    @pytest.mark.asyncio
    async def test_add_elements_with_position(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [
                    {
                        "content": "Positioned text",
                        "position": {"left": 1.0, "top": 1.0, "width": 4.0, "height": 1.0},
                    }
                ],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["successfully_added"] == 1


class TestDeleteElement:
    @pytest.mark.asyncio
    async def test_delete_text_element(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        # Add an element first
        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Delete me"}],
            },
            mock_context,
        )

        # Get elements to find shape count
        elements_result = await slide_maker.execute_action(
            "get_slide_elements",
            {"presentation_id": presentation_id, "slide_index": 0},
            mock_context,
        )
        initial_count = elements_result.result.data["total_elements"]

        # Delete the first element
        result = await slide_maker.execute_action(
            "delete_element",
            {"presentation_id": presentation_id, "slide_index": 0, "shape_index": 0},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["deleted"] is True
        assert result.result.data["remaining_shapes"] == initial_count - 1

    @pytest.mark.asyncio
    async def test_delete_element_invalid_shape_index(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        with pytest.raises(ValueError, match="out of range"):
            await slide_maker.execute_action(
                "delete_element",
                {"presentation_id": presentation_id, "slide_index": 0, "shape_index": 999},
                mock_context,
            )


class TestSetSlideBackgroundColor:
    @pytest.mark.asyncio
    async def test_set_hex_color(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "set_slide_background_color",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "color": "#FF0000",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_set_rgb_color(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "set_slide_background_color",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "color": {"rgb": [0, 128, 255]},
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True


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
                "elements": [{"content": "[Name]"}],
            },
            mock_context,
        )

        result = await slide_maker.execute_action(
            "find_and_replace",
            {
                "presentation_id": presentation_id,
                "replacements": [{"find": "[Name]", "replace": "John Doe"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["total_replacements"] >= 1
        assert result.result.data["status"] == "all_successful"

    @pytest.mark.asyncio
    async def test_find_and_replace_not_found(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "find_and_replace",
            {
                "presentation_id": presentation_id,
                "replacements": [{"find": "nonexistent_text_xyz", "replace": "replacement"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        # Not found should result in all_failed status
        assert result.result.data["status"] == "all_failed"

    @pytest.mark.asyncio
    async def test_find_and_replace_returns_summary(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "find_and_replace",
            {
                "presentation_id": presentation_id,
                "replacements": [{"find": "text", "replace": "new text"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "summary" in result.result.data
        summary = result.result.data["summary"]
        assert "requested" in summary
        assert "successful" in summary
        assert "failed" in summary
        assert "blocked" in summary


class TestAddChart:
    @pytest.mark.asyncio
    async def test_add_column_chart(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_chart",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "chart_type": "column_clustered",
                "position": {"left": 1.0, "top": 1.0, "width": 5.0, "height": 3.0},
                "data": {
                    "categories": ["Q1", "Q2", "Q3"],
                    "series": [{"name": "Sales", "values": [100, 150, 200]}],
                },
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "chart_id" in result.result.data

    @pytest.mark.asyncio
    async def test_add_pie_chart(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "add_chart",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "chart_type": "pie",
                "position": {"left": 0.5, "top": 0.5, "width": 6.0, "height": 4.0},
                "data": {
                    "categories": ["A", "B", "C"],
                    "series": [{"name": "Values", "values": [30, 50, 20]}],
                },
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "chart_id" in result.result.data


class TestSetTextAutosize:
    @pytest.mark.asyncio
    async def test_set_autosize(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Some text"}],
            },
            mock_context,
        )

        result = await slide_maker.execute_action(
            "set_text_autosize",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "shape_index": 0,
                "autosize_type": "TEXT_TO_FIT_SHAPE",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True


class TestSetSlideBackgroundGradient:
    @pytest.mark.asyncio
    async def test_set_gradient(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "set_slide_background_gradient",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "angle": 45,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True


class TestResetSlideBackground:
    @pytest.mark.asyncio
    async def test_reset_background(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "reset_slide_background",
            {"presentation_id": presentation_id, "slide_index": 0},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True


class TestRepositionElement:
    @pytest.mark.asyncio
    async def test_reposition_element(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Reposition me"}],
            },
            mock_context,
        )

        result = await slide_maker.execute_action(
            "reposition_element",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "element_index": 0,
                "position": {"left": 2.0, "top": 2.0, "width": 3.0, "height": 1.5},
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["modified"] is True
        new_pos = result.result.data["new_position"]
        assert new_pos["left"] == pytest.approx(2.0, abs=0.1)


class TestGetElementStyling:
    @pytest.mark.asyncio
    async def test_get_element_styling(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        await slide_maker.execute_action(
            "add_elements",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "elements": [{"content": "Styled text"}],
            },
            mock_context,
        )

        result = await slide_maker.execute_action(
            "get_element_styling",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "element_index": 0,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "element_type" in result.result.data
        assert "position" in result.result.data
        assert "styling_description" in result.result.data

    @pytest.mark.asyncio
    async def test_get_element_styling_invalid_element_index(self, mock_context):
        create_result = await slide_maker.execute_action("create_presentation", {}, mock_context)
        presentation_id = create_result.result.data["presentation_id"]

        result = await slide_maker.execute_action(
            "get_element_styling",
            {
                "presentation_id": presentation_id,
                "slide_index": 0,
                "element_index": 999,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

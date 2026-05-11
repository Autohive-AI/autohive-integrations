"""
Unit tests for the LinkedIn integration.

Covers all six actions (get_user_info, create_post, share_article,
reshare_post, update_post, delete_post) plus the image-upload helpers.
"""

import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("linkedin_mod", os.path.join(_parent, "linkedin.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

linkedin = _mod.linkedin

pytestmark = pytest.mark.unit  # asyncio_mode = "auto" handles async tests automatically


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# 1x1 PNG / JPEG samples for image-upload tests
SAMPLE_JPEG_BASE64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQCEAwEPwAB//9k="  # noqa: E501
SAMPLE_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

USERINFO_RESPONSE = FetchResponse(
    status=200,
    headers={},
    data={"sub": "abc123", "name": "Test User", "email": "test@example.com"},
)


def _image_init_response(image_urn: str = "urn:li:image:test") -> FetchResponse:
    return FetchResponse(
        status=200,
        headers={},
        data={
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/test",
                "image": image_urn,
            }
        },
    )


def _image_upload_response() -> FetchResponse:
    return FetchResponse(status=201, headers={}, data=None)


# ---- get_user_info ----


class TestGetUserInfo:
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "sub": "user123",
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "email": "john.doe@example.com",
                "email_verified": True,
            },
        )

        result = await linkedin.execute_action("get_user_info", {}, mock_context)

        data = result.result.data
        assert data["result"] == "User information retrieved successfully."
        assert data["user_info"]["sub"] == "user123"
        assert data["user_info"]["email"] == "john.doe@example.com"

    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sub": "x"})

        await linkedin.execute_action("get_user_info", {}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.linkedin.com/v2/userinfo"
        assert call.kwargs["method"] == "GET"

    async def test_missing_sub_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"error": "invalid_token", "error_description": "The access token is invalid"},
        )

        result = await linkedin.execute_action("get_user_info", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve user information" in result.result.message


# ---- create_post ----


class TestCreatePost:
    @patch.object(_mod, "post_to_linkedin")
    async def test_text_only_happy_path(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:text123"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        result = await linkedin.execute_action("create_post", {"text": "Hello from create_post!"}, mock_context)

        data = result.result.data
        assert data["result"] == "Post created successfully."
        assert data["post_id"] == "urn:li:share:text123"
        assert data["post_url"] == "https://www.linkedin.com/feed/update/urn:li:share:text123"
        assert data["images_uploaded"] == 0

    @patch.object(_mod, "post_to_linkedin")
    async def test_text_only_payload_has_no_content_field(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:1"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        await linkedin.execute_action("create_post", {"text": "hi"}, mock_context)

        payload = mock_post.call_args.args[1]
        assert "content" not in payload
        assert payload["commentary"] == "hi"

    @patch.object(_mod, "post_to_linkedin")
    async def test_single_image_payload_has_media(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:img"}, None)
        mock_context.fetch.side_effect = [
            USERINFO_RESPONSE,
            _image_init_response("urn:li:image:single"),
            _image_upload_response(),
        ]

        result = await linkedin.execute_action(
            "create_post",
            {
                "text": "Image post",
                "files": [{"content": SAMPLE_JPEG_BASE64, "name": "photo.jpg", "contentType": "image/jpeg"}],
            },
            mock_context,
        )

        assert result.result.data["images_uploaded"] == 1
        payload = mock_post.call_args.args[1]
        assert payload["content"]["media"]["id"] == "urn:li:image:single"

    @patch.object(_mod, "post_to_linkedin")
    async def test_multi_image_payload_has_multiImage(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:multi"}, None)
        mock_context.fetch.side_effect = [
            USERINFO_RESPONSE,
            _image_init_response("urn:li:image:1"),
            _image_upload_response(),
            _image_init_response("urn:li:image:2"),
            _image_upload_response(),
            _image_init_response("urn:li:image:3"),
            _image_upload_response(),
        ]

        result = await linkedin.execute_action(
            "create_post",
            {
                "text": "Multi",
                "files": [
                    {"content": SAMPLE_JPEG_BASE64, "name": f"img{i}.jpg", "contentType": "image/jpeg"}
                    for i in range(3)
                ],
            },
            mock_context,
        )

        assert result.result.data["images_uploaded"] == 3
        images = mock_post.call_args.args[1]["content"]["multiImage"]["images"]
        assert len(images) == 3

    @patch.object(_mod, "post_to_linkedin")
    async def test_alt_text_derived_from_filename(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:alt"}, None)
        mock_context.fetch.side_effect = [
            USERINFO_RESPONSE,
            _image_init_response(),
            _image_upload_response(),
        ]

        await linkedin.execute_action(
            "create_post",
            {
                "text": "Alt",
                "files": [
                    {
                        "content": SAMPLE_JPEG_BASE64,
                        "name": "A beautiful sunset over the mountains.jpg",
                        "contentType": "image/jpeg",
                    }
                ],
            },
            mock_context,
        )

        payload = mock_post.call_args.args[1]
        assert payload["content"]["media"]["altText"] == "A beautiful sunset over the mountains"

    @patch.object(_mod, "post_to_linkedin")
    async def test_visibility_passed_through(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:vis"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        await linkedin.execute_action(
            "create_post", {"text": "Connections only", "visibility": "CONNECTIONS"}, mock_context
        )

        payload = mock_post.call_args.args[1]
        assert payload["visibility"] == "CONNECTIONS"

    @patch.object(_mod, "post_to_linkedin")
    async def test_author_id_skips_userinfo_lookup(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:auth"}, None)
        mock_context.fetch.side_effect = [
            _image_init_response("urn:li:image:auth"),
            _image_upload_response(),
        ]

        await linkedin.execute_action(
            "create_post",
            {
                "text": "Explicit author",
                "author_id": "explicit_author",
                "files": [{"content": SAMPLE_JPEG_BASE64, "name": "photo.jpg", "contentType": "image/jpeg"}],
            },
            mock_context,
        )

        urls = [c.args[0] for c in mock_context.fetch.call_args_list]
        assert not any("/userinfo" in u for u in urls)
        payload = mock_post.call_args.args[1]
        assert payload["author"] == "urn:li:person:explicit_author"

    @patch.object(_mod, "post_to_linkedin")
    async def test_image_only_post(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:imgonly"}, None)
        mock_context.fetch.side_effect = [
            USERINFO_RESPONSE,
            _image_init_response(),
            _image_upload_response(),
        ]

        result = await linkedin.execute_action(
            "create_post",
            {"files": [{"content": SAMPLE_PNG_BASE64, "name": "photo.png", "contentType": "image/png"}]},
            mock_context,
        )

        assert result.result.data["images_uploaded"] == 1
        assert mock_post.call_args.args[1]["commentary"] == ""

    async def test_too_many_images_rejected_before_api_call(self, mock_context):
        files = [
            {"content": SAMPLE_JPEG_BASE64, "name": f"image{i}.jpg", "contentType": "image/jpeg"} for i in range(21)
        ]

        result = await linkedin.execute_action("create_post", {"text": "Too many", "files": files}, mock_context)

        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
        mock_context.fetch.assert_not_called()

    async def test_unsupported_image_type_rejected(self, mock_context):
        result = await linkedin.execute_action(
            "create_post",
            {
                "text": "Bad type",
                "files": [{"content": "base64data", "name": "image.bmp", "contentType": "image/bmp"}],
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Unsupported image type" in result.result.message
        mock_context.fetch.assert_not_called()

    async def test_no_text_no_files_rejected(self, mock_context):
        result = await linkedin.execute_action("create_post", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "must have either text or at least one file" in result.result.message

    async def test_missing_file_content_rejected(self, mock_context):
        result = await linkedin.execute_action(
            "create_post",
            {"text": "x", "files": [{"name": "photo.jpg", "contentType": "image/jpeg"}]},
            mock_context,
        )

        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)

    async def test_missing_file_content_type_rejected(self, mock_context):
        result = await linkedin.execute_action(
            "create_post",
            {"text": "x", "files": [{"content": SAMPLE_JPEG_BASE64, "name": "photo.jpg"}]},
            mock_context,
        )

        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)

    @patch.object(_mod, "post_to_linkedin")
    async def test_post_failure_returns_action_error(self, mock_post, mock_context):
        mock_post.return_value = (500, {}, "Internal Server Error")
        mock_context.fetch.return_value = USERINFO_RESPONSE

        result = await linkedin.execute_action("create_post", {"text": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


# ---- share_article ----


class TestShareArticle:
    @patch.object(_mod, "post_to_linkedin")
    async def test_happy_path(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:article"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        result = await linkedin.execute_action(
            "share_article",
            {
                "article_url": "https://example.com/article",
                "article_title": "Test Article",
                "article_description": "Description",
                "commentary": "Check this out!",
            },
            mock_context,
        )

        data = result.result.data
        assert data["result"] == "Article shared successfully."
        assert data["post_id"] == "urn:li:share:article"

    @patch.object(_mod, "post_to_linkedin")
    async def test_payload_has_article_content(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:1"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        await linkedin.execute_action(
            "share_article",
            {
                "article_url": "https://example.com/a",
                "article_title": "T",
                "commentary": "c",
            },
            mock_context,
        )

        article = mock_post.call_args.args[1]["content"]["article"]
        assert article["source"] == "https://example.com/a"
        assert article["title"] == "T"

    @patch.object(_mod, "post_to_linkedin")
    async def test_minimal_inputs_use_defaults(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:min"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        await linkedin.execute_action(
            "share_article",
            {"article_url": "https://example.com/min", "article_title": "Min"},
            mock_context,
        )

        payload = mock_post.call_args.args[1]
        assert payload["commentary"] == ""
        assert payload["content"]["article"]["description"] == ""

    @patch.object(_mod, "post_to_linkedin")
    async def test_post_failure_returns_action_error(self, mock_post, mock_context):
        mock_post.return_value = (500, {}, "boom")
        mock_context.fetch.return_value = USERINFO_RESPONSE

        result = await linkedin.execute_action(
            "share_article",
            {"article_url": "https://example.com", "article_title": "T"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


# ---- reshare_post ----


class TestResharePost:
    @patch.object(_mod, "post_to_linkedin")
    async def test_happy_path(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:reshare"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        result = await linkedin.execute_action(
            "reshare_post",
            {"original_post_urn": "urn:li:share:original123", "commentary": "Great post!"},
            mock_context,
        )

        data = result.result.data
        assert data["result"] == "Post reshared successfully."
        assert data["post_id"] == "urn:li:share:reshare"

    @patch.object(_mod, "post_to_linkedin")
    async def test_payload_has_reshare_context(self, mock_post, mock_context):
        mock_post.return_value = (201, {"x-restli-id": "urn:li:share:1"}, None)
        mock_context.fetch.return_value = USERINFO_RESPONSE

        await linkedin.execute_action(
            "reshare_post",
            {"original_post_urn": "urn:li:share:orig"},
            mock_context,
        )

        payload = mock_post.call_args.args[1]
        assert payload["reshareContext"]["parent"] == "urn:li:share:orig"
        assert payload["commentary"] == ""


# ---- update_post ----


class TestUpdatePost:
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await linkedin.execute_action(
            "update_post",
            {"post_urn": "urn:li:share:update123", "commentary": "Updated content"},
            mock_context,
        )

        data = result.result.data
        assert data["result"] == "Post updated successfully."
        assert data["post_urn"] == "urn:li:share:update123"

    async def test_partial_update_header_set(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await linkedin.execute_action(
            "update_post",
            {"post_urn": "urn:li:share:1", "commentary": "x"},
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"

    async def test_patch_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await linkedin.execute_action(
            "update_post",
            {"post_urn": "urn:li:share:1", "commentary": "new text"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["patch"]["$set"]["commentary"] == "new text"

    async def test_error_status_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=403, headers={}, data="Forbidden")

        result = await linkedin.execute_action(
            "update_post",
            {"post_urn": "urn:li:share:1", "commentary": "x"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message


# ---- delete_post ----


class TestDeletePost:
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await linkedin.execute_action("delete_post", {"post_urn": "urn:li:share:delete123"}, mock_context)

        data = result.result.data
        assert data["result"] == "Post deleted successfully."
        assert data["post_urn"] == "urn:li:share:delete123"

    async def test_request_method_and_header(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await linkedin.execute_action("delete_post", {"post_urn": "urn:li:share:1"}, mock_context)

        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "DELETE"
        assert call.kwargs["headers"]["X-RestLi-Method"] == "DELETE"

    async def test_post_urn_url_encoded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await linkedin.execute_action("delete_post", {"post_urn": "urn:li:share:abc"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "urn%3Ali%3Ashare%3Aabc" in url

    async def test_error_status_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=404, headers={}, data="Not Found")

        result = await linkedin.execute_action("delete_post", {"post_urn": "urn:li:share:gone"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


# ---- helper functions ----


class TestValidateFileInput:
    def test_valid_jpeg(self):
        content, ctype, alt = _mod.validate_file_input(
            {"content": "data", "name": "photo.jpg", "contentType": "image/jpeg"}
        )
        assert content == "data"
        assert ctype == "image/jpeg"
        assert alt == "photo"

    def test_alt_text_strips_extension(self):
        _, _, alt = _mod.validate_file_input(
            {"content": "x", "name": "Sunset over the lake.png", "contentType": "image/png"}
        )
        assert alt == "Sunset over the lake"

    def test_missing_content_raises(self):
        with pytest.raises(ValueError, match="content"):
            _mod.validate_file_input({"name": "p.jpg", "contentType": "image/jpeg"})

    def test_missing_content_type_raises(self):
        with pytest.raises(ValueError, match="contentType"):
            _mod.validate_file_input({"content": "x", "name": "p.jpg"})

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            _mod.validate_file_input({"content": "x", "contentType": "image/jpeg"})

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported image type"):
            _mod.validate_file_input({"content": "x", "name": "p.bmp", "contentType": "image/bmp"})


class TestEncodeUrn:
    def test_colons_encoded(self):
        assert _mod.encode_urn("urn:li:share:123") == "urn%3Ali%3Ashare%3A123"

import base64
from unittest.mock import AsyncMock
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from ghost.ghost import ghost

pytestmark = pytest.mark.unit


def _fetch_result(data):
    return FetchResponse(status=200, headers={}, data=data)


# ---- Content API ----


@pytest.mark.asyncio
async def test_get_posts(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"id": "1", "title": "Hello"}], "meta": {}}))
    result = await ghost.execute_action("get_posts", {}, mock_context)
    assert len(result.result.data["posts"]) == 1
    params = mock_context.fetch.call_args[1]["params"]
    assert params["limit"] == 15
    assert params["key"] == "test_content_key"


@pytest.mark.asyncio
async def test_get_posts_with_filters(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [], "meta": {}}))
    await ghost.execute_action("get_posts", {"limit": 5, "filter": "featured:true", "include": "tags"}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params["limit"] == 5
    assert params["filter"] == "featured:true"
    assert params["include"] == "tags"


@pytest.mark.asyncio
async def test_get_post_by_id(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"id": "abc", "title": "Post"}]}))
    result = await ghost.execute_action("get_post", {"id": "abc"}, mock_context)
    assert result.result.data["post"]["id"] == "abc"
    assert "abc" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_post_by_slug(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"slug": "hello-world"}]}))
    result = await ghost.execute_action("get_post", {"slug": "hello-world"}, mock_context)
    assert result.result.data["post"]["slug"] == "hello-world"
    assert "slug/hello-world" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_post_no_id_or_slug(mock_context):
    result = await ghost.execute_action("get_post", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_get_pages(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"pages": [{"id": "p1"}], "meta": {}}))
    result = await ghost.execute_action("get_pages", {}, mock_context)
    assert len(result.result.data["pages"]) == 1
    assert "content/pages" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_page_by_id(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"pages": [{"id": "p1"}]}))
    result = await ghost.execute_action("get_page", {"id": "p1"}, mock_context)
    assert result.result.data["page"]["id"] == "p1"


@pytest.mark.asyncio
async def test_get_page_by_slug(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"pages": [{"slug": "about"}]}))
    await ghost.execute_action("get_page", {"slug": "about"}, mock_context)
    assert "slug/about" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": [{"name": "news"}], "meta": {}}))
    result = await ghost.execute_action("get_tags", {}, mock_context)
    assert result.result.data["tags"][0]["name"] == "news"
    assert "content/tags" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_authors(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"authors": [{"name": "Alice"}], "meta": {}}))
    result = await ghost.execute_action("get_authors", {}, mock_context)
    assert result.result.data["authors"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_get_settings(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"settings": {"title": "My Blog"}}))
    result = await ghost.execute_action("get_settings", {}, mock_context)
    assert result.result.data["settings"]["title"] == "My Blog"


@pytest.mark.asyncio
async def test_get_tiers(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tiers": [{"name": "Free"}]}))
    result = await ghost.execute_action("get_tiers", {}, mock_context)
    assert result.result.data["tiers"][0]["name"] == "Free"


# ---- Admin API ----


@pytest.mark.asyncio
async def test_create_post(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=_fetch_result({"posts": [{"id": "new1", "title": "New Post", "status": "draft"}]})
    )
    result = await ghost.execute_action("create_post", {"title": "New Post"}, mock_context)
    assert result.result.data["post"]["id"] == "new1"
    body = mock_context.fetch.call_args[1]["json"]
    assert body["posts"][0]["status"] == "draft"
    assert "admin/posts" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_create_post_published(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"id": "p2", "status": "published"}]}))
    await ghost.execute_action(
        "create_post", {"title": "Live Post", "status": "published", "html": "<p>Hi</p>"}, mock_context
    )
    params = mock_context.fetch.call_args[1]["params"]
    assert params == {"source": "html"}


@pytest.mark.asyncio
async def test_update_post(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"id": "p1", "title": "Updated"}]}))
    result = await ghost.execute_action(
        "update_post",
        {"id": "p1", "updated_at": "2024-01-01T00:00:00.000Z", "title": "Updated"},
        mock_context,
    )
    assert result.result.data["post"]["title"] == "Updated"
    url = mock_context.fetch.call_args[0][0]
    assert "posts/p1" in url


@pytest.mark.asyncio
async def test_create_page(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"pages": [{"id": "pg1", "title": "About"}]}))
    result = await ghost.execute_action("create_page", {"title": "About"}, mock_context)
    assert result.result.data["page"]["id"] == "pg1"
    assert "admin/pages" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_upload_image(mock_context):
    file_obj = {"name": "test.png", "content": base64.b64encode(b"\x89PNG\r\n").decode(), "contentType": "image/png"}
    mock_context.fetch = AsyncMock(
        return_value=_fetch_result({"images": [{"url": "https://demo.ghost.io/content/images/test.png"}]})
    )
    result = await ghost.execute_action("upload_image", {"file": file_obj}, mock_context)
    assert result.type == ResultType.ACTION
    assert "url" in result.result.data["image"]
    url = mock_context.fetch.call_args[0][0]
    assert "admin/images/upload" in url
    # multipart body passed as data=, not files= or body=
    body = mock_context.fetch.call_args[1].get("data")
    assert body is not None
    assert b"test.png" in body
    assert b"Content-Type: image/png" in body
    assert b"\x89PNG\r\n" in body


def _image_file(name="test.png", data=b"\x89PNG\r\n", content_type="image/png"):
    return {"name": name, "content": base64.b64encode(data).decode(), "contentType": content_type}


@pytest.mark.asyncio
async def test_upload_image_request_shape(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"images": [{"url": "u"}]}))
    await ghost.execute_action("upload_image", {"file": _image_file()}, mock_context)
    kwargs = mock_context.fetch.call_args[1]
    assert kwargs["method"] == "POST"
    assert kwargs["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert kwargs["headers"]["Authorization"].startswith("Ghost ")
    boundary = kwargs["headers"]["Content-Type"].split("boundary=")[1]
    assert kwargs["data"].endswith(f"--{boundary}--\r\n".encode())


@pytest.mark.asyncio
async def test_upload_image_default_purpose(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"images": [{"url": "u"}]}))
    await ghost.execute_action("upload_image", {"file": _image_file()}, mock_context)
    body = mock_context.fetch.call_args[1]["data"]
    assert b'name="purpose"\r\n\r\nimage\r\n' in body


@pytest.mark.asyncio
async def test_upload_image_custom_purpose(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"images": [{"url": "u"}]}))
    await ghost.execute_action("upload_image", {"file": _image_file(), "purpose": "profile_image"}, mock_context)
    body = mock_context.fetch.call_args[1]["data"]
    assert b'name="purpose"\r\n\r\nprofile_image\r\n' in body


@pytest.mark.asyncio
async def test_upload_image_sends_decoded_bytes(mock_context):
    data = bytes(range(256))
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"images": [{"url": "u"}]}))
    await ghost.execute_action(
        "upload_image", {"file": _image_file(name="photo.jpg", data=data, content_type="image/jpeg")}, mock_context
    )
    body = mock_context.fetch.call_args[1]["data"]
    assert data in body
    assert b'filename="photo.jpg"' in body
    assert b"Content-Type: image/jpeg" in body


@pytest.mark.asyncio
async def test_upload_image_empty_response(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"images": []}))
    result = await ghost.execute_action("upload_image", {"file": _image_file()}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["image"] is None


@pytest.mark.asyncio
async def test_upload_image_invalid_base64(mock_context):
    file_obj = {"name": "test.png", "content": "not-base64!", "contentType": "image/png"}
    mock_context.fetch = AsyncMock()
    result = await ghost.execute_action("upload_image", {"file": file_obj}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_upload_image_fetch_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("HTTP 413: Request Entity Too Large"))
    result = await ghost.execute_action("upload_image", {"file": _image_file()}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "413" in result.result.message


@pytest.mark.asyncio
async def test_upload_image_missing_file(mock_context):
    result = await ghost.execute_action("upload_image", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_member(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"members": [{"id": "m1", "email": "user@example.com"}]}))
    result = await ghost.execute_action("create_member", {"email": "user@example.com", "name": "User"}, mock_context)
    assert result.result.data["member"]["email"] == "user@example.com"
    assert "admin/members" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_update_member(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"members": [{"id": "m1", "name": "Updated"}]}))
    result = await ghost.execute_action("update_member", {"id": "m1", "name": "Updated"}, mock_context)
    assert result.result.data["member"]["name"] == "Updated"
    assert "members/m1" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_send_newsletter(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": [{"id": "p1", "status": "published"}]}))
    result = await ghost.execute_action(
        "send_newsletter",
        {
            "post_id": "p1",
            "updated_at": "2024-01-01T00:00:00.000Z",
            "newsletter_slug": "my-newsletter",
        },
        mock_context,
    )
    assert result.result.data["post"]["status"] == "published"
    params = mock_context.fetch.call_args[1]["params"]
    assert params["newsletter"] == "my-newsletter"


@pytest.mark.asyncio
async def test_missing_content_api_key(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"api_url": "https://demo.ghost.io", "admin_api_key": "id:aabbcc"},
    }
    result = await ghost.execute_action("get_posts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_missing_api_url(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"content_api_key": "key", "admin_api_key": "id:aabbcc"},
    }
    result = await ghost.execute_action("get_posts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_id", ["", "chosen-post"])
async def test_live_get_post_uses_configured_or_discovered_post(mock_context, monkeypatch, configured_id):
    from ghost.tests import test_ghost_integration as live_tests

    monkeypatch.setattr(live_tests, "GHOST_TEST_POST_ID", configured_id)
    post_id = configured_id or "published-post"
    responses = [_fetch_result({"posts": [{"id": post_id}]})]
    if not configured_id:
        responses.insert(0, _fetch_result({"posts": [{"id": post_id}]}))
    mock_context.fetch = AsyncMock(side_effect=responses)
    await live_tests.test_get_post_live(mock_context)
    assert mock_context.fetch.await_count == (1 if configured_id else 2)
    assert mock_context.fetch.call_args.args[0].endswith(f"/posts/{post_id}/")


@pytest.mark.asyncio
async def test_live_get_post_skips_only_when_no_published_posts(mock_context, monkeypatch):
    from ghost.tests import test_ghost_integration as live_tests

    monkeypatch.setattr(live_tests, "GHOST_TEST_POST_ID", "")
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"posts": []}))
    with pytest.raises(pytest.skip.Exception, match="No published posts"):
        await live_tests.test_get_post_live(mock_context)

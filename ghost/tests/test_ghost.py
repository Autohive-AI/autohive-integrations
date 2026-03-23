"""
Ghost CMS Integration Tests

Tests all 15 Ghost actions across the Content API (read) and Admin API (write).

To run these tests:
1. Update TEST_AUTH below with your Ghost credentials
2. Run: python tests/test_ghost.py

Note: Write tests (create_post, etc.) create real content in your Ghost instance.
"""

import asyncio
from context import integration
from autohive_integrations_sdk import ExecutionContext

TEST_AUTH = {
    "credentials": {
        "api_url": "https://yoursite.ghost.io",
        "content_api_key": "YOUR_CONTENT_API_KEY",  # nosec B105
        "admin_api_key": "YOUR_ADMIN_KEY_ID:YOUR_ADMIN_KEY_SECRET",  # nosec B105
    }
}


def get_data(result):
    """Extract action data from an IntegrationResult."""
    return result.result.data


# =============================================================================
# Read Actions (Content API)
# =============================================================================


async def test_get_posts():
    print("\n=== Testing get_posts ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_posts", {"limit": 5}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("posts"), list), "Expected posts to be a list"
        assert "meta" in data, "Expected meta in response"
        print(f"OK — {len(data['posts'])} posts returned")
        return data["posts"]


async def test_get_post(posts):
    print("\n=== Testing get_post ===")
    if not posts:
        print("SKIP — no posts available")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        slug = posts[0].get("slug")
        post_id = posts[0].get("id")

        result = await integration.execute_action("get_post", {"slug": slug}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("post") is not None, "Expected a post object"
        assert data["post"].get("slug") == slug, "Slug mismatch"
        print(f"OK (slug) — {data['post']['title']}")

        result = await integration.execute_action("get_post", {"id": post_id}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data["post"]["id"] == post_id, "ID mismatch"
        print(f"OK (id) — {data['post']['title']}")


async def test_get_pages():
    print("\n=== Testing get_pages ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_pages", {"limit": 5}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("pages"), list), "Expected pages to be a list"
        print(f"OK — {len(data['pages'])} pages returned")
        return data["pages"]


async def test_get_page(pages):
    print("\n=== Testing get_page ===")
    if not pages:
        print("SKIP — no pages available")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        slug = pages[0].get("slug")
        result = await integration.execute_action("get_page", {"slug": slug}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("page") is not None, "Expected a page object"
        print(f"OK — {data['page']['title']}")


async def test_get_tags():
    print("\n=== Testing get_tags ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_tags", {}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("tags"), list), "Expected tags to be a list"
        print(f"OK — {len(data['tags'])} tags returned")


async def test_get_authors():
    print("\n=== Testing get_authors ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_authors", {}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("authors"), list), "Expected authors to be a list"
        print(f"OK — {len(data['authors'])} authors returned")


async def test_get_settings():
    print("\n=== Testing get_settings ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_settings", {}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("settings"), dict), "Expected settings to be a dict"
        assert "title" in data["settings"], "Expected title in settings"
        print(f"OK — site title: {data['settings']['title']}")


async def test_get_tiers():
    print("\n=== Testing get_tiers ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action("get_tiers", {}, context)
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert isinstance(data.get("tiers"), list), "Expected tiers to be a list"
        print(f"OK — {len(data['tiers'])} tiers returned")


# =============================================================================
# Write Actions (Admin API)
# =============================================================================


async def test_create_post():
    print("\n=== Testing create_post ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "create_post",
            {
                "title": "Test Post from Autohive",
                "html": "<p>This is a test post.</p>",
                "status": "draft",
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("post") is not None, "Expected a post object"
        assert data["post"].get("id"), "Expected post to have an id"
        assert data["post"].get("title") == "Test Post from Autohive", "Title mismatch"
        print(f"OK — created post {data['post']['id']}")
        return data["post"]


async def test_update_post(post):
    print("\n=== Testing update_post ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "update_post",
            {
                "id": post["id"],
                "updated_at": post["updated_at"],
                "title": "Test Post from Autohive (updated)",
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data["post"]["title"] == "Test Post from Autohive (updated)", (
            "Title not updated"
        )
        print(f"OK — updated post {data['post']['id']}")
        return data["post"]


async def test_create_page():
    print("\n=== Testing create_page ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "create_page",
            {
                "title": "Test Page from Autohive",
                "html": "<p>This is a test page.</p>",
                "status": "draft",
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("page") is not None, "Expected a page object"
        assert data["page"].get("id"), "Expected page to have an id"
        print(f"OK — created page {data['page']['id']}")


async def test_upload_image():
    print("\n=== Testing upload_image ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        # Update this path to an image file that exists on your system
        result = await integration.execute_action(
            "upload_image",
            {
                "file_path": "/path/to/test-image.png",
                "purpose": "image",
            },
            context,
        )
        data = get_data(result)
        # Skips gracefully if the placeholder path doesn't exist
        if data.get("result"):
            assert data.get("image") is not None, "Expected an image object"
            assert data["image"].get("url"), "Expected image to have a url"
            print(f"OK — uploaded image: {data['image']['url']}")
        else:
            print(f"SKIP — {data.get('error')} (update file_path to test)")


async def test_send_newsletter(post):
    print("\n=== Testing send_newsletter ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "send_newsletter",
            {
                "post_id": post["id"],
                "updated_at": post["updated_at"],
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("post") is not None, "Expected a post object"
        print(f"OK — newsletter triggered for post {post['id']}")


async def test_create_member():
    print("\n=== Testing create_member ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "create_member",
            {
                "email": "testmember@example.com",
                "name": "Test Member",
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data.get("member") is not None, "Expected a member object"
        assert data["member"].get("id"), "Expected member to have an id"
        print(f"OK — created member {data['member']['id']}")
        return data["member"]


async def test_update_member(member):
    print("\n=== Testing update_member ===")
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await integration.execute_action(
            "update_member",
            {
                "id": member["id"],
                "name": "Test Member (updated)",
            },
            context,
        )
        data = get_data(result)
        assert data.get("result") is True, f"Expected result=True, got: {data}"
        assert data["member"]["name"] == "Test Member (updated)", "Name not updated"
        print(f"OK — updated member {data['member']['id']}")


if __name__ == "__main__":

    async def run_all():
        # Read actions
        posts = await test_get_posts()
        await test_get_post(posts)
        pages = await test_get_pages()
        await test_get_page(pages)
        await test_get_tags()
        await test_get_authors()
        await test_get_settings()
        await test_get_tiers()

        # Write actions
        post = await test_create_post()
        if post:
            post = await test_update_post(post)
        if post:
            await test_send_newsletter(post)

        await test_create_page()
        await test_upload_image()

        member = await test_create_member()
        if member:
            await test_update_member(member)

        print("\n=== All tests complete ===")

    asyncio.run(run_all())

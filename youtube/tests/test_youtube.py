# Testbed for YouTube integration
import asyncio
from context import youtube
from autohive_integrations_sdk import ExecutionContext

async def test_search():
    """Test searching for videos."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "query": "python programming",
        "max_results": 5,
        "type": "video"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("search", inputs, context)
            print(f"Search Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing search: {e}")
            return None


async def test_get_video():
    """Test getting video details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "video_id": "test_video_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("get_video", inputs, context)
            print(f"Get Video Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_video: {e}")
            return None


async def test_update_video():
    """Test updating video metadata."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "video_id": "test_video_id_here",
        "title": "Updated Video Title",
        "description": "This video has been updated via the integration",
        "tags": ["test", "integration", "youtube"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("update_video", inputs, context)
            print(f"Update Video Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_video: {e}")
            return None


async def test_get_channel():
    """Test getting channel details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "mine": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("get_channel", inputs, context)
            print(f"Get Channel Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_channel: {e}")
            return None


async def test_list_playlists():
    """Test listing playlists."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "mine": True,
        "max_results": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("list_playlists", inputs, context)
            print(f"List Playlists Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_playlists: {e}")
            return None


async def test_create_playlist():
    """Test creating a new playlist."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "title": "Test Playlist",
        "description": "A test playlist created by the integration",
        "privacy_status": "private"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("create_playlist", inputs, context)
            print(f"Create Playlist Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_playlist: {e}")
            return None


async def test_list_playlist_items():
    """Test listing items in a playlist."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "playlist_id": "test_playlist_id_here",
        "max_results": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("list_playlist_items", inputs, context)
            print(f"List Playlist Items Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_playlist_items: {e}")
            return None


async def test_add_video_to_playlist():
    """Test adding a video to a playlist."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "playlist_id": "test_playlist_id_here",
        "video_id": "test_video_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("add_video_to_playlist", inputs, context)
            print(f"Add Video to Playlist Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing add_video_to_playlist: {e}")
            return None


async def test_list_comments():
    """Test listing comments on a video."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "video_id": "test_video_id_here",
        "max_results": 20,
        "order": "relevance"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("list_comments", inputs, context)
            print(f"List Comments Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_comments: {e}")
            return None


async def test_post_comment():
    """Test posting a comment on a video."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "video_id": "test_video_id_here",
        "text": "This is a test comment from the integration!"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("post_comment", inputs, context)
            print(f"Post Comment Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing post_comment: {e}")
            return None


async def test_update_comment():
    """Test updating a comment."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "comment_id": "test_comment_id_here",
        "text": "This comment has been updated!"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("update_comment", inputs, context)
            print(f"Update Comment Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_comment: {e}")
            return None


async def test_delete_comment():
    """Test deleting a comment."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "comment_id": "test_comment_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await youtube.execute_action("delete_comment", inputs, context)
            print(f"Delete Comment Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing delete_comment: {e}")
            return None


async def main():
    print("Testing YouTube Integration")
    print("===========================")
    print()

    # Test each action
    print("1. Testing search...")
    await test_search()
    print()

    print("2. Testing get_video...")
    await test_get_video()
    print()

    print("3. Testing update_video...")
    await test_update_video()
    print()

    print("4. Testing get_channel...")
    await test_get_channel()
    print()

    print("5. Testing list_playlists...")
    await test_list_playlists()
    print()

    print("6. Testing create_playlist...")
    created_playlist = await test_create_playlist()
    print()

    # If create succeeded, try to add video and list items
    if created_playlist and created_playlist.get('result'):
        playlist_id = created_playlist.get('playlist', {}).get('id')
        if playlist_id:
            print("7. Testing add_video_to_playlist on created playlist...")
            await test_add_video_to_playlist()
            print()

            print("8. Testing list_playlist_items on created playlist...")
            await test_list_playlist_items()
            print()

    print("9. Testing list_comments...")
    await test_list_comments()
    print()

    print("10. Testing post_comment...")
    posted_comment = await test_post_comment()
    print()

    # If post succeeded, try to update and delete
    if posted_comment and posted_comment.get('result'):
        comment_id = posted_comment.get('comment', {}).get('id')
        if comment_id:
            print("11. Testing update_comment on posted comment...")
            await test_update_comment()
            print()

            print("12. Testing delete_comment on posted comment...")
            await test_delete_comment()
            print()

    print("Testing completed!")


if __name__ == "__main__":
    asyncio.run(main())

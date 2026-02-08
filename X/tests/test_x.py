# Test suite for X integration
import asyncio
from context import x
from autohive_integrations_sdk import ExecutionContext


async def test_get_me():
    """Test getting authenticated user profile."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("get_me", {}, context)
            print(f"Get Me Result: {result}")
            assert result.get('result') == True
            assert 'user' in result
            return result
        except Exception as e:
            print(f"Error testing get_me: {e}")
            return None


async def test_get_user():
    """Test getting user profile by username."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"username": "X"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("get_user", inputs, context)
            print(f"Get User Result: {result}")
            assert result.get('result') == True
            assert 'user' in result
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


async def test_create_tweet():
    """Test creating a post."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"text": "Test post from Autohive X integration!"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("create_tweet", inputs, context)
            print(f"Create Post Result: {result}")
            assert result.get('result') == True
            assert 'post' in result
            return result
        except Exception as e:
            print(f"Error testing create_tweet: {e}")
            return None


async def test_create_tweet_with_media():
    """Test creating a post with media."""
    import base64

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    # Minimal valid PNG (1x1 pixel)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xFE,
        0xD4, 0xEF, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
        0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])

    inputs = {
        "text": "Test post with media!",
        "file": {
            "content": base64.b64encode(png_data).decode('utf-8'),
            "name": "test_image.png",
            "contentType": "image/png"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("create_tweet", inputs, context)
            print(f"Create Post With Media Result: {result}")
            assert result.get('result') == True
            assert 'post' in result
            assert 'media_id' in result
            return result
        except Exception as e:
            print(f"Error testing create_tweet with media: {e}")
            return None


async def test_get_tweet():
    """Test getting a post by ID."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"post_id": "1234567890123456789", "include_user": True, "include_metrics": True}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("get_tweet", inputs, context)
            print(f"Get Post Result: {result}")
            assert result.get('result') == True
            assert 'post' in result
            return result
        except Exception as e:
            print(f"Error testing get_tweet: {e}")
            return None


async def test_search_tweets():
    """Test searching for posts."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"query": "#AI -is:retweet lang:en", "max_results": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("search_tweets", inputs, context)
            print(f"Search Posts Result: {result}")
            assert result.get('result') == True
            assert 'posts' in result
            return result
        except Exception as e:
            print(f"Error testing search_tweets: {e}")
            return None


async def test_delete_tweet():
    """Test deleting a post."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"post_id": "1234567890123456789"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await x.execute_action("delete_tweet", inputs, context)
            print(f"Delete Post Result: {result}")
            assert result.get('result') == True
            assert 'deleted' in result
            return result
        except Exception as e:
            print(f"Error testing delete_tweet: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("X Integration Test Suite")
    print("=" * 60)

    test_functions = [
        ("Get Authenticated User", test_get_me),
        ("Get User by Username", test_get_user),
        ("Create Post", test_create_tweet),
        ("Create Post With Media", test_create_tweet_with_media),
        ("Get Post", test_get_tweet),
        ("Search Posts", test_search_tweets),
        ("Delete Post", test_delete_tweet),
    ]

    results = []
    for test_name, test_func in test_functions:
        print(f"\n{'-' * 60}")
        print(f"Running: {test_name}")
        print(f"{'-' * 60}")
        result = await test_func()
        results.append((test_name, result is not None))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

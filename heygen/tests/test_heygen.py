# Test suite for HeyGen integration
import asyncio
from context import heygen
from autohive_integrations_sdk import ExecutionContext

# Test configuration - OAuth 2.0 Authentication
# Get your access_token via HeyGen OAuth flow: https://app.heygen.com/oauth/authorize
TEST_AUTH = {
    "credentials": {
        "access_token": "your_oauth_access_token_here"
    }
}

# Store IDs for dependent tests
test_voice_id = None
test_avatar_id = None
test_group_id = None
test_video_id = None


async def test_list_voices():
    """Test listing available voices. FREE - no credits used."""
    print("\n[TEST] Listing available voices...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await heygen.execute_action("list_voices", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("error") is None, "Should not have error"
            assert response_data.get("data") is not None, "Should return data"
            voices = response_data["data"].get("voices", [])
            print(f"✓ Found {len(voices)} voice(s)")

            if voices:
                global test_voice_id
                test_voice_id = voices[0].get("voice_id")
                print(f"  Using voice: {voices[0].get('name', 'Unnamed')} (ID: {test_voice_id})")

                # Show first few voices
                for i, voice in enumerate(voices[:3]):
                    print(f"  - {voice.get('name', 'Unnamed')} ({voice.get('language', 'N/A')})")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_voice_locales():
    """Test listing available voice locales. FREE - no credits used."""
    print("\n[TEST] Listing available voice locales...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await heygen.execute_action("list_voice_locales", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("error") is None, "Should not have error"
            assert response_data.get("data") is not None, "Should return data"
            locales = response_data["data"].get("locales", [])
            print(f"✓ Found {len(locales)} locale(s)")

            if locales:
                for i, locale in enumerate(locales[:5]):
                    print(f"  - {locale}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_avatars():
    """Test listing available avatars. FREE - no credits used."""
    print("\n[TEST] Listing available avatars...")

    inputs = {
        "page": 1,
        "limit": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await heygen.execute_action("list_avatars", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("error") is None, "Should not have error"
            assert response_data.get("data") is not None, "Should return data"
            data = response_data["data"]
            avatars = data.get("avatars", [])
            talking_photos = data.get("talking_photos", [])

            print(f"✓ Found {len(avatars)} avatar(s) and {len(talking_photos)} talking photo(s)")

            if avatars:
                global test_avatar_id
                test_avatar_id = avatars[0].get("avatar_id")
                print(f"  Using avatar: {avatars[0].get('avatar_name', 'Unnamed')} (ID: {test_avatar_id})")

                # Show first few avatars
                for i, avatar in enumerate(avatars[:3]):
                    print(f"  - {avatar.get('avatar_name', 'Unnamed')} ({avatar.get('gender', 'N/A')})")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_avatar_details():
    """Test getting avatar details. FREE - no credits used."""
    if not test_avatar_id:
        print("\n[TEST] Skipping get_avatar_details - no avatar ID available")
        return None

    print(f"\n[TEST] Getting avatar details for {test_avatar_id}...")

    inputs = {
        "avatar_id": test_avatar_id
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await heygen.execute_action("get_avatar_details", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("error") is None, "Should not have error"
            assert response_data.get("data") is not None, "Should return data"
            avatar = response_data["data"].get("avatar")

            if avatar:
                print(f"✓ Retrieved avatar: {avatar.get('avatar_name', 'Unnamed')}")
                print(f"  Gender: {avatar.get('gender', 'N/A')}")
                print(f"  Preview Video: {avatar.get('preview_video_url', 'N/A')[:50]}...")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_avatar_groups():
    """Test listing avatar groups. FREE - no credits used."""
    print("\n[TEST] Listing avatar groups...")

    inputs = {
        "page": 1,
        "limit": 10
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await heygen.execute_action("list_avatar_groups", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("error") is None, "Should not have error"
            assert response_data.get("data") is not None, "Should return data"
            groups = response_data["data"].get("avatar_groups", [])
            print(f"✓ Found {len(groups)} avatar group(s)")

            if groups:
                global test_group_id
                test_group_id = groups[0].get("id")
                print(f"  Using group: {groups[0].get('name', 'Unnamed')} (ID: {test_group_id})")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_generate_photo_avatar():
    """Test generating photo avatar. COSTS CREDITS - This test is commented out by default."""
    print("\n[TEST] Skipping generate_photo_avatar - COSTS CREDITS")
    print("  To enable, uncomment this test and provide valid inputs")
    return None

    # Uncomment below to actually test (WARNING: COSTS CREDITS)
    # inputs = {
    #     "name": "Test Avatar",
    #     "age": "30-40",
    #     "gender": "male",
    #     "ethnicity": "caucasian",
    #     "orientation": "front",
    #     "pose": "standing",
    #     "style": "professional",
    #     "appearance": "business casual attire"
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await heygen.execute_action("generate_photo_avatar", inputs, context)
    #         response_data = result.result.data
    #         generation_id = response_data.get("data", {}).get("generation_id")
    #         print(f"✓ Started photo generation: {generation_id}")
    #         return result
    #     except Exception as e:
    #         print(f"✗ Error: {e}")
    #         return None


async def test_create_avatar_video():
    """Test creating avatar video. COSTS CREDITS - This test is commented out by default."""
    print("\n[TEST] Skipping create_avatar_video - COSTS CREDITS")
    print("  To enable, uncomment this test and provide valid avatar_id and voice_id")
    return None

    # Uncomment below to actually test (WARNING: COSTS CREDITS)
    # if not test_avatar_id or not test_voice_id:
    #     print("  Skipping - need avatar_id and voice_id")
    #     return None
    #
    # inputs = {
    #     "title": "Test Video",
    #     "video_inputs": [
    #         {
    #             "character": {
    #                 "type": "avatar",
    #                 "avatar_id": test_avatar_id
    #             },
    #             "voice": {
    #                 "type": "text",
    #                 "input_text": "Hello, this is a test video from HeyGen integration.",
    #                 "voice_id": test_voice_id
    #             }
    #         }
    #     ]
    # }
    #
    # async with ExecutionContext(auth=TEST_AUTH) as context:
    #     try:
    #         result = await heygen.execute_action("create_avatar_video", inputs, context)
    #         response_data = result.result.data
    #         global test_video_id
    #         test_video_id = response_data.get("data", {}).get("video_id")
    #         print(f"✓ Started video creation: {test_video_id}")
    #         return result
    #     except Exception as e:
    #         print(f"✗ Error: {e}")
    #         return None


async def main():
    print("=" * 70)
    print("HeyGen Integration Test Suite")
    print("=" * 70)
    print("\n📝 SETUP INSTRUCTIONS:")
    print("1. Complete OAuth flow via https://app.heygen.com/oauth/authorize")
    print("2. Replace 'your_oauth_access_token_here' in TEST_AUTH with your token")
    print("")
    print("📋 ACTION TYPES:")
    print("   - Free actions: list_voices, list_avatars, list_avatar_groups, etc.")
    print("   - Paid actions: generate_photo_avatar, create_avatar_video (costs credits)")
    print("\n" + "=" * 70)

    try:
        # Test voice discovery
        print("\n" + "=" * 70)
        print("VOICE DISCOVERY (2 actions - FREE)")
        print("=" * 70)
        await test_list_voices()
        await test_list_voice_locales()

        # Test avatar discovery
        print("\n" + "=" * 70)
        print("AVATAR DISCOVERY (3 actions - FREE)")
        print("=" * 70)
        await test_list_avatars()
        await test_get_avatar_details()
        await test_list_avatar_groups()

        # Test photo avatar generation (COSTS CREDITS - commented out)
        print("\n" + "=" * 70)
        print("PHOTO AVATAR GENERATION (1 action - PAID)")
        print("=" * 70)
        await test_generate_photo_avatar()

        # Test video creation (COSTS CREDITS - commented out)
        print("\n" + "=" * 70)
        print("VIDEO CREATION (1 action - PAID)")
        print("=" * 70)
        await test_create_avatar_video()

        print("\n" + "=" * 70)
        print("✓ Test suite completed!")
        print("=" * 70)
        print("\n📊 Summary: 5 actions tested")
        print("  - Auth Method: OAuth 2.0 (Bearer Token)")
        print("  - 5 FREE actions (no credits used)")
        print("  - 2 PAID actions (commented out by default)")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

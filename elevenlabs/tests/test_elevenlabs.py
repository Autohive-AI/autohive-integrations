# Test suite for ElevenLabs integration
import asyncio
from context import elevenlabs
from autohive_integrations_sdk import ExecutionContext

# Test configuration
# IMPORTANT: Replace with your actual ElevenLabs API key
TEST_AUTH = {
    "credentials": {
        "api_key": "your_api_key_here"
    }
}

# Store voice and history IDs for dependent tests
test_voice_id = None
test_history_item_id = None


async def test_get_user_subscription():
    """Test getting user subscription info. FREE - no credits used."""
    print("\n[TEST] Getting user subscription info...")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("get_user_subscription", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "subscription" in result, "Should return subscription object"

            sub = result["subscription"]
            print(f"✓ Subscription retrieved")
            print(f"  Tier: {sub.get('tier', 'N/A')}")
            print(f"  Character Count: {sub.get('character_count', 0)}/{sub.get('character_limit', 0)}")
            print(f"  Voice Limit: {sub.get('voice_limit', 0)}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_voices():
    """Test listing available voices. FREE - no credits used."""
    print("\n[TEST] Listing available voices...")

    inputs = {
        "page_size": 20
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("list_voices", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "voices" in result, "Should return voices array"

            voices = result["voices"]
            print(f"✓ Found {len(voices)} voice(s)")

            if voices:
                global test_voice_id
                test_voice_id = voices[0]["voice_id"]
                print(f"  Using voice: {voices[0].get('name', 'Unnamed')} (ID: {test_voice_id})")

                # Show first few voices
                for i, voice in enumerate(voices[:3]):
                    print(f"  - {voice.get('name', 'Unnamed')}: {voice.get('description', 'No description')[:50]}...")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_voice():
    """Test getting a specific voice. FREE - no credits used."""
    if not test_voice_id:
        print("\n[TEST] Skipping get_voice - no voice ID available")
        return None

    print(f"\n[TEST] Getting voice details for {test_voice_id}...")

    inputs = {
        "voice_id": test_voice_id,
        "with_settings": True
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("get_voice", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "voice" in result, "Should return voice object"

            voice = result["voice"]
            print(f"✓ Retrieved voice: {voice.get('name', 'Unnamed')}")
            print(f"  Category: {voice.get('category', 'N/A')}")
            print(f"  Description: {voice.get('description', 'No description')}")

            if "settings" in voice:
                settings = voice["settings"]
                print(f"  Settings: stability={settings.get('stability')}, similarity={settings.get('similarity_boost')}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_voice_settings():
    """Test getting voice settings. FREE - no credits used."""
    if not test_voice_id:
        print("\n[TEST] Skipping get_voice_settings - no voice ID available")
        return None

    print(f"\n[TEST] Getting voice settings for {test_voice_id}...")

    inputs = {"voice_id": test_voice_id}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("get_voice_settings", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "settings" in result, "Should return settings object"

            settings = result["settings"]
            print(f"✓ Retrieved voice settings:")
            print(f"  Stability: {settings.get('stability', 'N/A')}")
            print(f"  Similarity Boost: {settings.get('similarity_boost', 'N/A')}")
            print(f"  Style: {settings.get('style', 'N/A')}")
            print(f"  Use Speaker Boost: {settings.get('use_speaker_boost', 'N/A')}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_text_to_speech():
    """Test text-to-speech conversion. COSTS CREDITS! (1 per character for standard, 0.5 for Turbo)"""
    if not test_voice_id:
        print("\n[TEST] Skipping text_to_speech - no voice ID available")
        return None

    print(f"\n[TEST] Generating speech from text...")
    print("  ⚠ WARNING: This action costs credits!")

    text = "Hello from Autohive! This is a test of the ElevenLabs integration."
    print(f"  Text length: {len(text)} characters")

    inputs = {
        "text": text,
        "voice_id": test_voice_id,
        "output_format": "mp3_44100_128",
        "model_id": "eleven_turbo_v2_5"  # Use Turbo model for cheaper credits
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("text_to_speech", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "file" in result, "Should return file object"

            file_obj = result["file"]
            assert "content" in file_obj, "File should have content"
            assert "name" in file_obj, "File should have name"
            assert "contentType" in file_obj, "File should have contentType"

            content_length = len(file_obj["content"])
            print(f"✓ Generated audio file")
            print(f"  Name: {file_obj['name']}")
            print(f"  Type: {file_obj['contentType']}")
            print(f"  Size: {content_length} bytes (base64-encoded)")
            print(f"  Estimated cost: {len(text) * 0.5} credits (Turbo model)")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_history():
    """Test listing generation history. FREE - no credits used."""
    print("\n[TEST] Listing generation history...")

    inputs = {"page_size": 10}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("list_history", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "history" in result, "Should return history array"

            history = result["history"]
            print(f"✓ Found {len(history)} history item(s)")

            if history:
                global test_history_item_id
                test_history_item_id = history[0]["history_item_id"]

                # Show first few items
                for i, item in enumerate(history[:3]):
                    print(f"  {i+1}. {item.get('text', '')[:50]}... (ID: {item.get('history_item_id', 'N/A')})")
                    print(f"     Voice: {item.get('voice_name', 'N/A')}, Created: {item.get('date_unix', 'N/A')}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_download_history_audio():
    """Test downloading audio from history. FREE - no new credits used."""
    if not test_history_item_id:
        print("\n[TEST] Skipping download_history_audio - no history item ID available")
        print("  Run this test after generating audio with text_to_speech")
        return None

    print(f"\n[TEST] Downloading audio from history item {test_history_item_id}...")

    inputs = {"history_item_id": test_history_item_id}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await elevenlabs.execute_action("download_history_audio", inputs, context)

            assert result["result"] is True, "Action should succeed"
            assert "file" in result, "Should return file object"

            file_obj = result["file"]
            content_length = len(file_obj["content"])
            print(f"✓ Downloaded audio file")
            print(f"  Name: {file_obj['name']}")
            print(f"  Type: {file_obj['contentType']}")
            print(f"  Size: {content_length} bytes (base64-encoded)")
            print(f"  Cost: FREE (no new generation)")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def main():
    print("=" * 70)
    print("ElevenLabs Integration Test Suite")
    print("=" * 70)
    print("\n📝 SETUP INSTRUCTIONS:")
    print("1. Get your API key from https://elevenlabs.io/app/settings/api-keys")
    print("2. Replace 'your_api_key_here' in TEST_AUTH with your actual key")
    print("3. Free tier includes 10,000 credits/month")
    print("4. Only text_to_speech costs credits (0.5-1 per character)")
    print("\n" + "=" * 70)

    try:
        # Test account and subscription
        print("\n" + "=" * 70)
        print("ACCOUNT MANAGEMENT (1 action - FREE)")
        print("=" * 70)
        await test_get_user_subscription()

        # Test voice discovery
        print("\n" + "=" * 70)
        print("VOICE DISCOVERY (3 actions - FREE)")
        print("=" * 70)
        await test_list_voices()
        await test_get_voice()
        await test_get_voice_settings()

        # Test text-to-speech (COSTS CREDITS)
        print("\n" + "=" * 70)
        print("AUDIO GENERATION (1 action - PAID)")
        print("=" * 70)
        await test_text_to_speech()

        # Test history management
        print("\n" + "=" * 70)
        print("HISTORY MANAGEMENT (2 actions - FREE)")
        print("=" * 70)
        await test_list_history()
        await test_download_history_audio()

        print("\n" + "=" * 70)
        print("✓ Test suite completed!")
        print("=" * 70)
        print("\n📊 Summary: 7 actions tested")
        print("  - 6 FREE actions (no credits used)")
        print("  - 1 PAID action (text_to_speech)")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

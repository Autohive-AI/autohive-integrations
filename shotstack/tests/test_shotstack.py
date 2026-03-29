# Testbed for Shotstack integration
import asyncio
from context import shotstack
from autohive_integrations_sdk import ExecutionContext

AUTH = {
    "auth_type": "ApiKey",
    "credentials": {
        "api_key": "your_api_key_here",
        "environment": "stage",
    },
}

TEST_VIDEO_URL = "https://github.com/shotstack/test-media/raw/main/captioning/scott-ko.mp4"
TEST_IMAGE_URL = "https://shotstack-assets.s3.ap-southeast-2.amazonaws.com/logos/shotstack-green.png"


async def test_get_media_info():
    """Test probing media metadata."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "get_media_info",
                {"url": TEST_VIDEO_URL},
                context,
            )
            print(f"Get Media Info: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_upload_media():
    """Test uploading media from URL."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "upload_media",
                {"url": TEST_VIDEO_URL},
                context,
            )
            print(f"Upload Media: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            if result.get("source_id"):
                print(f"  -> Source ID: {result['source_id']}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_create_video():
    """Test rendering a simple video."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "create_video",
                {
                    "clips": [{"url": TEST_IMAGE_URL, "duration": 3}],
                    "output_format": "mp4",
                    "resolution": "sd",
                    "wait_for_completion": False,
                },
                context,
            )
            print(f"Create Video: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            if result.get("render_id"):
                print(f"  -> Render ID: {result['render_id']}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_renders():
    """Test listing renders."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "list_renders",
                {},
                context,
            )
            print(f"List Renders: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def main():
    print("=== Shotstack Integration Tests ===\n")

    print("1. Get Media Info")
    await test_get_media_info()
    print()

    print("2. Upload Media")
    await test_upload_media()
    print()

    print("3. Create Video (no wait)")
    await test_create_video()
    print()

    print("4. List Renders")
    await test_list_renders()
    print()

    print("=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())

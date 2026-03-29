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


async def test_submit_render():
    """Test submitting a render job (no wait)."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "submit_render",
                {
                    "timeline": {
                        "tracks": [
                            {
                                "clips": [
                                    {
                                        "asset": {"type": "image", "src": TEST_IMAGE_URL},
                                        "start": 0,
                                        "length": 3,
                                    }
                                ]
                            }
                        ]
                    },
                    "output": {"format": "mp4", "resolution": "preview"},
                },
                context,
            )
            print(f"Submit Render: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            if result.get("render_id"):
                print(f"  -> Render ID: {result['render_id']}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_check_render_status(render_id: str):
    """Test checking render status."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "check_render_status",
                {"render_id": render_id},
                context,
            )
            print(f"Check Render Status: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            print(f"  -> Status: {result.get('status')}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_compose_video():
    """Test composing a video from clips."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "compose_video",
                {
                    "clips": [{"url": TEST_IMAGE_URL, "duration": 3}],
                    "wait_for_completion": False,
                },
                context,
            )
            print(f"Compose Video: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            if result.get("render_id"):
                print(f"  -> Render ID: {result['render_id']}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_custom_edit():
    """Test custom_edit with full timeline."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await shotstack.execute_action(
                "custom_edit",
                {
                    "timeline": {
                        "tracks": [
                            {
                                "clips": [
                                    {
                                        "asset": {
                                            "type": "title",
                                            "text": "Hello Shotstack",
                                            "style": "minimal",
                                            "color": "#ffffff",
                                        },
                                        "start": 0,
                                        "length": 3,
                                    }
                                ]
                            },
                            {
                                "clips": [
                                    {
                                        "asset": {"type": "image", "src": TEST_IMAGE_URL},
                                        "start": 0,
                                        "length": 3,
                                    }
                                ]
                            },
                        ]
                    },
                    "output": {"format": "mp4", "resolution": "sd"},
                    "wait_for_completion": False,
                },
                context,
            )
            print(f"Custom Edit: {result}")
            assert result.get("result") is True, f"Failed: {result.get('error')}"
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def main():
    print("=== Shotstack Integration Tests ===\n")

    print("1. Submit Render")
    render = await test_submit_render()
    print()

    if render and render.get("render_id"):
        print("2. Check Render Status")
        await test_check_render_status(render["render_id"])
        print()

    print("3. Compose Video (no wait)")
    await test_compose_video()
    print()

    print("4. Custom Edit (no wait)")
    await test_custom_edit()
    print()

    print("=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())

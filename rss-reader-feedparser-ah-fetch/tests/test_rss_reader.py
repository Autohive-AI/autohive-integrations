# Testbed for a simple integration that reads RSS feeds.
# The IUT (integration under test) is the rss_reader.py file and does not use the integration
# framework for authentication.
import asyncio
from context import rss_reader
from autohive_integrations_sdk import ExecutionContext


async def test_get_feed():

    # Uncomment this to use HTTP Basic Authentication
    auth = {
        "user_name": "test_user",
        "password": "test_password",  # nosec B105
    }

    # Uncomment this to use API token authentication
    # auth = {
    #    "api_token": "test_api_token"
    # }

    # Define test configuration
    inputs = {"feed_url": "https://www.nasa.gov/feed/", "limit": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await rss_reader.execute_action("get_feed", inputs, context)
            print("\n=== Get Feed Results ===")
            print(f"Feed Title: {result['feed_title']}")
            print(f"Feed URL: {result['feed_link']}")
            print("\nEntries:")
            for entry in result["entries"]:
                print(f"\nTitle: {entry['title']}")
                print(f"Link: {entry['link']}")
                print(f"Published: {entry['published']}")
        except Exception as e:
            print(f"Error testing get_feed: {e.message}")


async def main():
    print("Testing RSS Reader Integration")
    print("=============================")

    await test_get_feed()


if __name__ == "__main__":
    asyncio.run(main())

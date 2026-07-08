# Testbed for a simple integration that reads RSS feeds.
# The IUT (integration under test) is the rss_reader.py file and does not use the integration
# framework for authentication.
import asyncio
from context import rss_reader
from autohive_integrations_sdk import ExecutionContext, ResultType


async def test_get_feed():

    # Uncomment this to use HTTP Basic Authentication
    auth = {
        "auth_type": "Custom",
        "credentials": {
            "user_name": "test_user",
            "password": "test_password",  # nosec B105
        },
    }

    # Uncomment this to use API token authentication
    # auth = {
    #    "auth_type": "Custom",
    #    "credentials": {"api_token": "test_api_token"},
    # }

    # Define test configuration
    inputs = {"feed_url": "https://www.nasa.gov/feed/", "limit": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await rss_reader.execute_action("get_feed", inputs, context)
            if result.type != ResultType.ACTION:
                print(f"Error testing get_feed: {result.result.message}")
                return

            data = result.result.data
            print("\n=== Get Feed Results ===")
            print(f"Feed Title: {data['feed_title']}")
            print(f"Feed URL: {data['feed_link']}")
            print("\nEntries:")
            for entry in data["entries"]:
                print(f"\nTitle: {entry['title']}")
                print(f"Link: {entry['link']}")
                print(f"Published: {entry['published']}")
        except Exception as e:
            print(f"Error testing get_feed: {e}")


async def main():
    print("Testing RSS Reader Integration")
    print("=============================")

    await test_get_feed()


if __name__ == "__main__":
    asyncio.run(main())

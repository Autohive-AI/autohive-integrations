# Testbed for Google Business Profile integration
import asyncio
from context import reviews
from autohive_integrations_sdk import ExecutionContext

async def test_list_accounts():
    """Test listing business accounts with OAuth2 authentication."""
    # Setup OAuth2 auth object
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}  # No inputs required for listing accounts

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await reviews.execute_action("list_accounts", inputs, context)
            print(f"List Accounts Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_accounts: {e}")
            return None

async def test_list_locations():
    """Test listing business locations for a specific account."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "account_name": "accounts/your_account_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await reviews.execute_action("list_locations", inputs, context)
            print(f"List Locations Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_locations: {e}")
            return None

async def test_list_reviews():
    """Test listing reviews for a specific business location."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "location_name": "accounts/your_account_id/locations/your_location_id"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await reviews.execute_action("list_reviews", inputs, context)
            print(f"List Reviews Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_reviews: {e}")
            return None

async def test_reply_to_review():
    """Test replying to a customer review."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "review_name": "accounts/your_account_id/locations/your_location_id/reviews/your_review_id",
        "reply_comment": "Thank you for your feedback! We're glad you had a great experience with our service."
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await reviews.execute_action("reply_to_review", inputs, context)
            print(f"Reply to Review Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing reply_to_review: {e}")
            return None

async def test_delete_review_reply():
    """Test deleting a review reply."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "review_name": "accounts/your_account_id/locations/your_location_id/reviews/your_review_id"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await reviews.execute_action("delete_review_reply", inputs, context)
            print(f"Delete Review Reply Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing delete_review_reply: {e}")
            return None

async def main():
    print("Testing Google Business Profile Integration")
    print("=========================================")
    print()

    # Test each action
    print("1. Testing list_accounts...")
    accounts_result = await test_list_accounts()
    print()

    print("2. Testing list_locations...")
    locations_result = await test_list_locations()
    print()

    print("3. Testing list_reviews...")
    reviews_result = await test_list_reviews()
    print()

    print("4. Testing reply_to_review...")
    reply_result = await test_reply_to_review()
    print()

    # Note: Only test delete if you actually want to remove a reply
    # print("5. Testing delete_review_reply...")
    # await test_delete_review_reply()
    # print()

    print("Testing completed!")
    print()
    print("NOTE: To run these tests with real data:")
    print("1. Replace 'your_access_token_here' with a valid Google Business Profile access token")
    print("2. Replace account_id, location_id, and review_id with actual values from your business")
    print("3. Be careful with reply and delete operations as they affect real customer interactions")

if __name__ == "__main__":
    asyncio.run(main())
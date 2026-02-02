# Comprehensive testbed for the unified SerpAPI integration
# Tests all three review sources: App Store, Google Play, and Google Maps
import asyncio
from context import app_business_reviews
from autohive_integrations_sdk import ExecutionContext

# ============ Apple App Store Tests ============

async def test_search_apps_ios():
    """Test searching for iOS apps"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "term": "WhatsApp",
        "country": "us",
        "num": 5
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("search_apps_ios", inputs, context)
            print(f"[iOS] Found {result['total_results']} apps for 'WhatsApp'")

            for i, app in enumerate(result['apps']):
                print(f"  {i+1}. {app['title']} (ID: {app['id']})")
                print(f"     Developer: {app['developer']['name']}")
                if app['rating']:
                    print(f"     Rating: {app['rating'][0].get('rating', 'N/A')}")
                print(f"     Link: {app['link']}")

        except Exception as e:
            print(f"[iOS] Error testing search_apps_ios: {e}")

async def test_get_reviews_app_store_by_id():
    """Test getting App Store reviews by product ID"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "product_id": "310633997",  # WhatsApp
        "country": "us",
        "sort": "mostrecent",
        "max_pages": 2
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_app_store", inputs, context)
            print(f"[iOS] Found {result['total_reviews']} reviews for {result['app_name']}")
            print(f"[iOS] Product ID: {result['product_id']}")

            # Print first few reviews
            for i, review in enumerate(result['reviews'][:3]):
                print(f"  Review {i+1}: {review['rating']} stars - {review['title']}")
                print(f"    By: {review['author']['name']}")
                print(f"    Date: {review['review_date']}")
                print(f"    {review['text'][:80]}...")

        except Exception as e:
            print(f"[iOS] Error testing get_reviews_app_store: {e}")

async def test_get_reviews_app_store_by_name():
    """Test getting App Store reviews by app name (auto-resolve ID)"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "app_name": "Instagram",
        "country": "us",
        "sort": "mostfavorable",
        "max_pages": 1
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_app_store", inputs, context)
            print(f"[iOS] Auto-resolved '{inputs['app_name']}' to ID: {result['product_id']}")
            print(f"[iOS] Fetched {result['total_reviews']} favorable reviews")

            if result['reviews']:
                first_review = result['reviews'][0]
                print(f"  Top review: {first_review['rating']} stars - {first_review['title']}")

        except Exception as e:
            print(f"[iOS] Error testing reviews by name: {e}")

# ============ Google Play Store Tests ============

async def test_search_apps_android():
    """Test searching for Android apps"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "query": "Spotify",
        "limit": 5
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("search_apps_android", inputs, context)
            print(f"[Android] Found {result['total_results']} apps for 'Spotify'")

            for i, app in enumerate(result['apps']):
                print(f"  {i+1}. {app['title']}")
                print(f"     ID: {app['product_id']}")
                print(f"     Developer: {app['developer']}")
                print(f"     Rating: {app['rating']} | Price: {app['price']}")

        except Exception as e:
            print(f"[Android] Error testing search_apps_android: {e}")

async def test_get_reviews_google_play_basic():
    """Test getting Google Play reviews with basic params"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "product_id": "com.whatsapp",
        "sort_by": 2,  # Newest
        "num_reviews": 20,
        "max_pages": 2
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_play", inputs, context)
            print(f"[Android] Found {result['total_reviews']} reviews for {result['app_name']}")
            print(f"[Android] App rating: {result['app_rating']}")
            print(f"[Android] Product ID: {result['product_id']}")

            # Print first few reviews
            for i, review in enumerate(result['reviews'][:3]):
                print(f"  Review {i+1}: {review['rating']} stars by {review['author']}")
                print(f"    Date: {review['date']} | Likes: {review['likes']}")
                print(f"    {review['text'][:80]}...")

        except Exception as e:
            print(f"[Android] Error testing get_reviews_google_play: {e}")

async def test_get_reviews_google_play_with_filters():
    """Test getting Google Play reviews with filters"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "product_id": "com.instagram.android",
        "rating": 5,  # Only 5-star reviews
        "platform": "phone",
        "sort_by": 1,  # Most relevant
        "num_reviews": 15,
        "max_pages": 1
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_play", inputs, context)
            print(f"[Android] Found {result['total_reviews']} 5-star phone reviews for {result['app_name']}")

            # Verify filter worked
            ratings = [review['rating'] for review in result['reviews']]
            print(f"[Android] Review ratings (should all be 5): {set(ratings)}")

        except Exception as e:
            print(f"[Android] Error testing filtered reviews: {e}")

async def test_get_reviews_google_play_by_name():
    """Test getting Google Play reviews by app name (auto-resolve ID)"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "app_name": "Bumble",
        "sort_by": 3,  # Rating
        "num_reviews": 10,
        "max_pages": 1
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_play", inputs, context)
            print(f"[Android] Auto-resolved '{inputs['app_name']}' to: {result['product_id']}")
            print(f"[Android] Fetched {result['total_reviews']} reviews")
            print(f"[Android] App: {result['app_name']} (Rating: {result['app_rating']})")

        except Exception as e:
            print(f"[Android] Error testing reviews by name: {e}")

# ============ Google Maps Tests ============

async def test_search_places_google_maps():
    """Test searching for places on Google Maps"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "query": "Pizza restaurant",
        "location": "San Francisco, CA",
        "num_results": 5
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("search_places_google_maps", inputs, context)
            print(f"[Maps] Found {result['total_results']} places for 'Pizza restaurant' in San Francisco")

            for i, place in enumerate(result['places']):
                print(f"  {i+1}. {place['title']}")
                print(f"     Address: {place['address']}")
                print(f"     Rating: {place['rating']} ({place['reviews']} reviews)")
                print(f"     Place ID: {place['place_id']}")

        except Exception as e:
            print(f"[Maps] Error testing search_places_google_maps: {e}")

async def test_get_reviews_google_maps_by_place_id():
    """Test getting Google Maps reviews by place ID"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",  # Example place ID
        "sort_by": "newestFirst",
        "num_reviews": 20,
        "max_pages": 3
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_maps", inputs, context)
            print(f"[Maps] Found {result['total_reviews']} reviews for {result['business_name']}")
            print(f"[Maps] Average rating: {result['average_rating']}")
            print(f"[Maps] Place ID: {result['place_id']}")

            # Print first few reviews
            for i, review in enumerate(result['reviews'][:3]):
                print(f"  Review {i+1}: {review['rating']} stars by {review['author']}")
                print(f"    Date: {review['date']} | Likes: {review['likes']}")
                print(f"    {review['text'][:80]}...")

        except Exception as e:
            print(f"[Maps] Error testing get_reviews_google_maps with place_id: {e}")

async def test_get_reviews_google_maps_by_query():
    """Test getting Google Maps reviews by business name (auto-resolve place ID)"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "query": "Starbucks Reserve Roastery",
        "location": "Seattle, WA",
        "sort_by": "qualityScore",
        "num_reviews": 15,
        "max_pages": 2
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_maps", inputs, context)
            print(f"[Maps] Auto-resolved business to: {result['business_name']}")
            print(f"[Maps] Place ID: {result['place_id']}")
            print(f"[Maps] Fetched {result['total_reviews']} reviews")
            print(f"[Maps] Average rating: {result['average_rating']}")

            if result['reviews']:
                first_review = result['reviews'][0]
                print(f"  Top review: {first_review['rating']} stars")

        except Exception as e:
            print(f"[Maps] Error testing reviews by query: {e}")

async def test_get_reviews_google_maps_with_data_id():
    """Test getting Google Maps reviews by data ID"""
    auth = {
        "api_key": "your_serpapi_key_here"
    }

    inputs = {
        "data_id": "0x808fb9fe2f8abe5f:0x3d1e3c3b33e4c4d8",  # Example data ID
        "sort_by": "ratingHigh",
        "num_reviews": 10,
        "max_pages": 1
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await app_business_reviews.execute_action("get_reviews_google_maps", inputs, context)
            print(f"[Maps] Found {result['total_reviews']} high-rated reviews")
            print(f"[Maps] Business: {result['business_name']}")

        except Exception as e:
            print(f"[Maps] Error testing get_reviews_google_maps with data_id: {e}")

# ============ Main Test Runner ============

async def main():
    print("=" * 60)
    print("TESTING UNIFIED SERPAPI INTEGRATION")
    print("=" * 60)
    print()

    print("=" * 60)
    print("APPLE APP STORE TESTS")
    print("=" * 60)
    await test_search_apps_ios()
    print()
    await test_get_reviews_app_store_by_id()
    print()
    await test_get_reviews_app_store_by_name()
    print()

    print("=" * 60)
    print("GOOGLE PLAY STORE TESTS")
    print("=" * 60)
    await test_search_apps_android()
    print()
    await test_get_reviews_google_play_basic()
    print()
    await test_get_reviews_google_play_with_filters()
    print()
    await test_get_reviews_google_play_by_name()
    print()

    print("=" * 60)
    print("GOOGLE MAPS TESTS")
    print("=" * 60)
    await test_search_places_google_maps()
    print()
    await test_get_reviews_google_maps_by_place_id()
    print()
    await test_get_reviews_google_maps_by_query()
    print()
    await test_get_reviews_google_maps_with_data_id()
    print()

    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

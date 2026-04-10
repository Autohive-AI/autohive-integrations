import asyncio
from pprint import pprint
from context import google_ads
from autohive_integrations_sdk import ExecutionContext

# Test configuration - replace with your actual values
TEST_AUTH = {
    "auth_type": "PlatformOAuth2",
    "credentials": {
        "access_token": "ACCESS_TOKEN",
        "refresh_token": "REFRESH_TOKEN",
    }
}

TEST_INPUTS = {
    "login_customer_id": "LOGIN_CUSTOMER_ID",
    "customer_id": "CUSTOMER_ID",
}


async def test_get_accessible_accounts():
    """Test retrieving accessible accounts."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {}

    try:
        result = await google_ads.execute_action("get_accessible_accounts", inputs, context)
        print("\n=== Get Accessible Accounts Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_retrieve_campaign_metrics():
    """Test retrieving campaign metrics."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "date_ranges": ["2025-05-14_2025-05-20"]
    }

    try:
        result = await google_ads.execute_action("retrieve_campaign_metrics", inputs, context)
        print("\n=== Campaign Metrics Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_retrieve_keyword_metrics():
    """Test retrieving keyword metrics."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "ad_group_ids": ["123456789"],
        "campaign_ids": ["111222333"],
        "date_ranges": ["2025-05-14_2025-05-20"]
    }

    try:
        result = await google_ads.execute_action("retrieve_keyword_metrics", inputs, context)
        print("\n=== Keyword Metrics Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_create_campaign():
    """Test creating a new campaign."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "campaign_name": "Test Campaign via API",
        "budget_amount_micros": 10000000,  # $10/day
        "budget_name": "Test Budget",
        "bidding_strategy": "MANUAL_CPC"
    }

    try:
        result = await google_ads.execute_action("create_campaign", inputs, context)
        print("\n=== Create Campaign Test ===")
        pprint(result)
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_update_campaign(campaign_id: str):
    """Test updating an existing campaign."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "name": "Updated Campaign Name"
    }

    try:
        result = await google_ads.execute_action("update_campaign", inputs, context)
        print("\n=== Update Campaign Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_create_ad_group(campaign_id: str):
    """Test creating a new ad group."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "campaign_id": campaign_id,
        "ad_group_name": "Test Ad Group",
        "cpc_bid_micros": 500000,  # $0.50
        "status": "PAUSED"
    }

    try:
        result = await google_ads.execute_action("create_ad_group", inputs, context)
        print("\n=== Create Ad Group Test ===")
        pprint(result)
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_create_responsive_search_ad(ad_group_id: str):
    """Test creating a Responsive Search Ad."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "ad_group_id": ad_group_id,
        "headlines": [
            "Best Product Ever",
            "Amazing Quality",
            "Free Shipping Today"
        ],
        "descriptions": [
            "Shop now and save big on our amazing products.",
            "Limited time offer. Don't miss out!"
        ],
        "final_url": "https://www.example.com",
        "path1": "products",
        "path2": "deals",
        "status": "PAUSED"
    }

    try:
        result = await google_ads.execute_action("create_responsive_search_ad", inputs, context)
        print("\n=== Create RSA Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_add_keywords(ad_group_id: str):
    """Test adding keywords to an ad group."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "ad_group_id": ad_group_id,
        "keywords": [
            {"text": "best product", "match_type": "BROAD"},
            {"text": "buy product online", "match_type": "PHRASE"},
            {"text": "product store", "match_type": "EXACT"}
        ]
    }

    try:
        result = await google_ads.execute_action("add_keywords", inputs, context)
        print("\n=== Add Keywords Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_generate_keyword_ideas():
    """Test generating keyword ideas via Keyword Planner."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "seed_keywords": ["digital marketing", "seo services"],
        "language_id": "1000",  # English
        "location_ids": ["2840"],  # USA
        "include_adult_keywords": False
    }

    try:
        result = await google_ads.execute_action("generate_keyword_ideas", inputs, context)
        print("\n=== Keyword Ideas Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_generate_keyword_historical_metrics():
    """Test getting historical metrics for keywords."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "keywords": ["digital marketing", "seo services", "ppc advertising"],
        "language_id": "1000",
        "location_ids": ["2840"]
    }

    try:
        result = await google_ads.execute_action("generate_keyword_historical_metrics", inputs, context)
        print("\n=== Keyword Historical Metrics Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_remove_campaign(campaign_id: str):
    """Test removing a campaign."""
    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        **TEST_INPUTS,
        "campaign_id": campaign_id
    }

    try:
        result = await google_ads.execute_action("remove_campaign", inputs, context)
        print("\n=== Remove Campaign Test ===")
        pprint(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    print("=" * 50)
    print("Google Ads Integration Tests")
    print("=" * 50)
    
    # Read operations
    await test_get_accessible_accounts()
    await test_retrieve_campaign_metrics()
    await test_retrieve_keyword_metrics()
    
    # Keyword Planner operations
    await test_generate_keyword_ideas()
    await test_generate_keyword_historical_metrics()
    
    # CRUD operations (uncomment to test - will create real resources)
    # campaign_result = await test_create_campaign()
    # if campaign_result:
    #     campaign_id = campaign_result.result.data.get('campaign_id')
    #     await test_update_campaign(campaign_id)
    #     
    #     ad_group_result = await test_create_ad_group(campaign_id)
    #     if ad_group_result:
    #         ad_group_id = ad_group_result.result.data.get('ad_group_id')
    #         await test_create_responsive_search_ad(ad_group_id)
    #         await test_add_keywords(ad_group_id)
    #     
    #     await test_remove_campaign(campaign_id)


if __name__ == "__main__":
    asyncio.run(main())

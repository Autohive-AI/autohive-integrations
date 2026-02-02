# Testbed for Google Search Console integration
import asyncio
from context import google_search_console
from autohive_integrations_sdk import ExecutionContext

# Configuration - Replace these placeholder values with actual values for testing
SITE_URL = "https://your-site.com"  # Replace with actual site URL (e.g., "https://example.com" or "sc-domain:example.com")

# Sample auth configuration
# Note: You'll need a valid Google OAuth2 access token with Search Console API access
auth = {
    "auth_type": "custom",
    "credentials": {
        "access_token": "your_access_token_here"  # Replace with actual access token
    }
}

async def test_list_sites():
    """Test listing all sites in Search Console account."""
    print("=== TESTING LIST SITES ===")

    try:
        inputs = {}

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("list_sites", inputs, context)

            if result.get('result'):
                print(f"   ✓ Sites retrieved successfully")
                print(f"   Sites found: {result.get('site_count')}")
                if result.get('sites'):
                    for site in result.get('sites', []):
                        print(f"   - {site.get('site_url')} ({site.get('permission_level')})")
            else:
                print(f"   ✗ Failed to list sites: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== LIST SITES TEST COMPLETED ===\n")

async def test_query_analytics():
    """Test querying search analytics data."""
    print("=== TESTING QUERY ANALYTICS ===")

    try:
        inputs = {
            "site_url": SITE_URL,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "dimensions": ["query", "page"],
            "row_limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("query_analytics", inputs, context)

            if result.get('result'):
                print(f"   ✓ Analytics data retrieved successfully")
                print(f"   Rows returned: {result.get('row_count')}")
                if result.get('rows'):
                    print(f"   Sample row: {result.get('rows')[0]}")
            else:
                print(f"   ✗ Failed to query analytics: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== QUERY ANALYTICS TEST COMPLETED ===\n")

async def test_query_analytics_with_filters():
    """Test querying search analytics data with filters."""
    print("=== TESTING QUERY ANALYTICS WITH FILTERS ===")

    try:
        inputs = {
            "site_url": SITE_URL,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "dimensions": ["query"],
            "dimension_filter_groups": [
                {
                    "filters": [
                        {
                            "dimension": "country",
                            "operator": "equals",
                            "expression": "USA"
                        }
                    ]
                }
            ],
            "row_limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("query_analytics", inputs, context)

            if result.get('result'):
                print(f"   ✓ Filtered analytics data retrieved successfully")
                print(f"   Rows returned: {result.get('row_count')}")
                if result.get('rows'):
                    print(f"   Sample row: {result.get('rows')[0]}")
            else:
                print(f"   ✗ Failed to query analytics with filters: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== QUERY ANALYTICS WITH FILTERS TEST COMPLETED ===\n")

async def test_query_analytics_by_device():
    """Test querying search analytics data by device."""
    print("=== TESTING QUERY ANALYTICS BY DEVICE ===")

    try:
        inputs = {
            "site_url": SITE_URL,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "dimensions": ["device"],
            "row_limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("query_analytics", inputs, context)

            if result.get('result'):
                print(f"   ✓ Device analytics data retrieved successfully")
                print(f"   Rows returned: {result.get('row_count')}")
                for row in result.get('rows', []):
                    print(f"   - Device: {row.get('device')}, Clicks: {row.get('clicks')}, Impressions: {row.get('impressions')}")
            else:
                print(f"   ✗ Failed to query device analytics: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== QUERY ANALYTICS BY DEVICE TEST COMPLETED ===\n")

async def test_list_sitemaps():
    """Test listing sitemaps for a site."""
    print("=== TESTING LIST SITEMAPS ===")

    try:
        inputs = {
            "site_url": SITE_URL
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("list_sitemaps", inputs, context)

            if result.get('result'):
                print(f"   ✓ Sitemaps retrieved successfully")
                print(f"   Sitemaps found: {result.get('sitemap_count')}")
                if result.get('sitemaps'):
                    for sitemap in result.get('sitemaps', []):
                        print(f"   - {sitemap.get('path')}")
            else:
                print(f"   ✗ Failed to list sitemaps: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== LIST SITEMAPS TEST COMPLETED ===\n")

async def test_inspect_url():
    """Test inspecting a URL."""
    print("=== TESTING INSPECT URL ===")

    try:
        # Replace with an actual URL from your site
        inspection_url = f"{SITE_URL}/"

        inputs = {
            "site_url": SITE_URL,
            "inspection_url": inspection_url
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_search_console.execute_action("inspect_url", inputs, context)

            if result.get('result'):
                print(f"   ✓ URL inspected successfully")
                inspection_result = result.get('inspection_result', {})
                print(f"   Inspection result keys: {list(inspection_result.keys())}")
            else:
                print(f"   ✗ Failed to inspect URL: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== INSPECT URL TEST COMPLETED ===\n")

async def test_get_sitemap():
    """Test getting details for a specific sitemap."""
    print("=== TESTING GET SITEMAP ===")

    try:
        # First, get the list of sitemaps
        list_inputs = {
            "site_url": SITE_URL
        }

        async with ExecutionContext(auth=auth) as context:
            list_result = await google_search_console.execute_action("list_sitemaps", list_inputs, context)

            if list_result.get('result') and list_result.get('sitemaps'):
                # Get details for the first sitemap
                first_sitemap = list_result.get('sitemaps')[0]
                sitemap_url = first_sitemap.get('path')

                inputs = {
                    "site_url": SITE_URL,
                    "sitemap_url": sitemap_url
                }

                result = await google_search_console.execute_action("get_sitemap", inputs, context)

                if result.get('result'):
                    print(f"   ✓ Sitemap details retrieved successfully")
                    sitemap = result.get('sitemap', {})
                    print(f"   Sitemap keys: {list(sitemap.keys())}")
                else:
                    print(f"   ✗ Failed to get sitemap: {result.get('error')}")
            else:
                print(f"   ⚠ No sitemaps found to test with")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== GET SITEMAP TEST COMPLETED ===\n")

async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GOOGLE SEARCH CONSOLE INTEGRATION TEST SUITE")
    print("="*60 + "\n")

    print("NOTE: Update SITE_URL and access_token before running tests\n")

    await test_list_sites()
    await test_query_analytics()
    await test_query_analytics_with_filters()
    await test_query_analytics_by_device()
    await test_list_sitemaps()
    await test_inspect_url()
    await test_get_sitemap()

    print("="*60)
    print("ALL TESTS COMPLETED")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

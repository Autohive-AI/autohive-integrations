"""
Test suite for NZBN integration.

These tests require valid NZBN API credentials to run against the live API.
Set environment variables before running:
- NZBN_CLIENT_ID
- NZBN_CLIENT_SECRET  
- NZBN_SUBSCRIPTION_KEY

Usage:
    cd nzbn/tests
    python test_nzbn.py           # Full test suite
    python test_nzbn.py --quick   # Validation tests only (no API calls)
"""

import asyncio
import sys

from context import nzbn
from autohive_integrations_sdk import ExecutionContext


TEST_AUTH = {
    "credentials": {}
}

TEST_NZBN = "9429041525746"


async def test_search_entities():
    """Test searching for entities."""
    print("\n=== Test: Search Entities ===")
    
    inputs = {"search_term": "Xero", "page_size": 5}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("search_entities", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Found {data.get('totalItems', 0)} entities")
                if data.get("items"):
                    entity = data["items"][0]
                    print(f"     First result: {entity.get('entityName', 'N/A')}")
            else:
                print(f"[INFO] Search returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_search_entities_with_filters():
    """Test searching with entity type filter."""
    print("\n=== Test: Search Entities with Filters ===")
    
    inputs = {
        "search_term": "Limited",
        "entity_type": "LTD",
        "entity_status": "Registered",
        "page_size": 3
    }
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("search_entities", inputs, context)
            data = result.result.data
            print(f"[OK] Search with filters completed: result={data.get('result')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_search_entities_missing_term():
    """Test search without search term - should fail validation."""
    print("\n=== Test: Search Entities (Missing Term) ===")
    
    inputs = {}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("search_entities", inputs, context)
            data = result.result.data
            
            if data.get("result") is False and "required" in data.get("error", "").lower():
                print(f"[OK] Correctly returned error for missing search term")
            else:
                print(f"[FAIL] Expected validation error, got: {data}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity():
    """Test getting entity details."""
    print("\n=== Test: Get Entity ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                entity = data["entity"]
                print(f"[OK] Got entity: {entity.get('entityName', 'N/A')}")
            else:
                print(f"[INFO] Get entity returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_missing_nzbn():
    """Test get entity without NZBN - should fail validation."""
    print("\n=== Test: Get Entity (Missing NZBN) ===")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity", inputs, context)
            data = result.result.data

            if data.get("result") is False and "required" in data.get("error", "").lower():
                print(f"[OK] Correctly returned error for missing NZBN")
            else:
                print(f"[FAIL] Expected validation error, got: {data}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_summary():
    """Test getting entity summary (token optimized)."""
    print("\n=== Test: Get Entity Summary ===")

    inputs = {"nzbn": TEST_NZBN}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_summary", inputs, context)
            data = result.result.data

            if data.get("result"):
                summary = data["summary"]
                print(f"[OK] Got entity summary:")
                print(f"     NZBN: {summary.get('nzbn', 'N/A')}")
                print(f"     Name: {summary.get('entityName', 'N/A')}")
                print(f"     Office: {summary.get('registeredOffice', 'N/A')}")

                # Verify only 3 fields returned
                if len(summary.keys()) == 3:
                    print(f"[OK] Summary contains exactly 3 fields (optimized)")
                else:
                    print(f"[WARN] Summary has {len(summary.keys())} fields, expected 3")
            else:
                print(f"[INFO] Get entity summary returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_summary_missing_nzbn():
    """Test get entity summary without NZBN - should fail validation."""
    print("\n=== Test: Get Entity Summary (Missing NZBN) ===")

    inputs = {}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_summary", inputs, context)
            data = result.result.data

            if data.get("result") is False and "required" in data.get("error", "").lower():
                print(f"[OK] Correctly returned error for missing NZBN")
            else:
                print(f"[FAIL] Expected validation error, got: {data}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_token_savings_comparison():
    """Test that entity summary provides significant token savings."""
    print("\n=== Test: Token Savings (Full vs Summary) ===")

    inputs = {"nzbn": TEST_NZBN}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            # Get full entity
            full_result = await nzbn.execute_action("get_entity", inputs, context)
            full_data = full_result.result.data

            # Get summary
            summary_result = await nzbn.execute_action("get_entity_summary", inputs, context)
            summary_data = summary_result.result.data

            if full_data.get("result") and summary_data.get("result"):
                import json
                full_size = len(json.dumps(full_data.get("entity", {})))
                summary_size = len(json.dumps(summary_data.get("summary", {})))

                savings_pct = 100 - int(summary_size / full_size * 100) if full_size > 0 else 0

                print(f"[OK] Full entity size: {full_size:,} chars")
                print(f"[OK] Summary size: {summary_size:,} chars")
                print(f"[OK] Token savings: {savings_pct}%")

                if savings_pct >= 95:
                    print(f"[OK] Achieved target of 95%+ token savings")
                else:
                    print(f"[WARN] Token savings below 95% target")
            else:
                print(f"[INFO] Could not compare - one action failed")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_addresses():
    """Test getting entity addresses."""
    print("\n=== Test: Get Entity Addresses ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_addresses", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('addresses', []))} addresses")
            else:
                print(f"[INFO] Get addresses returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_roles():
    """Test getting entity roles."""
    print("\n=== Test: Get Entity Roles ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_roles", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('roles', []))} roles")
            else:
                print(f"[INFO] Get roles returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_trading_names():
    """Test getting entity trading names."""
    print("\n=== Test: Get Entity Trading Names ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_trading_names", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('tradingNames', []))} trading names")
            else:
                print(f"[INFO] Get trading names returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_company_details():
    """Test getting company details."""
    print("\n=== Test: Get Company Details ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_company_details", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got company details")
            else:
                print(f"[INFO] Get company details returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_gst_numbers():
    """Test getting entity GST numbers."""
    print("\n=== Test: Get Entity GST Numbers ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_gst_numbers", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('gstNumbers', []))} GST numbers")
            else:
                print(f"[INFO] Get GST numbers returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_entity_industry_classifications():
    """Test getting entity industry classifications."""
    print("\n=== Test: Get Entity Industry Classifications ===")
    
    inputs = {"nzbn": TEST_NZBN}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_entity_industry_classifications", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('industryClassifications', []))} classifications")
            else:
                print(f"[INFO] Get industry classifications returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_changes():
    """Test getting recent changes."""
    print("\n=== Test: Get Changes ===")
    
    inputs = {
        "change_event_type": "NewRegistration",
        "page_size": 5
    }
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_changes", inputs, context)
            data = result.result.data
            
            if data.get("result"):
                print(f"[OK] Got {len(data.get('changes', []))} change events")
            else:
                print(f"[INFO] Get changes returned: {data.get('error', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def test_get_changes_missing_event_type():
    """Test get changes without event type - should fail validation."""
    print("\n=== Test: Get Changes (Missing Event Type) ===")
    
    inputs = {}
    
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await nzbn.execute_action("get_changes", inputs, context)
            data = result.result.data
            
            if data.get("result") is False and "required" in data.get("error", "").lower():
                print(f"[OK] Correctly returned error for missing event type")
            else:
                print(f"[FAIL] Expected validation error, got: {data}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")


async def run_quick_tests():
    """Run validation tests only (no API calls needed)."""
    print("\n" + "=" * 60)
    print("Running Quick Tests (Validation Only)")
    print("=" * 60)

    await test_search_entities_missing_term()
    await test_get_entity_missing_nzbn()
    await test_get_entity_summary_missing_nzbn()
    await test_get_changes_missing_event_type()


async def run_full_tests():
    """Run full test suite (requires API credentials)."""
    print("\n" + "=" * 60)
    print("Running Full Test Suite")
    print("=" * 60)
    print("\nNote: Set NZBN_CLIENT_ID, NZBN_CLIENT_SECRET, and")
    print("      NZBN_SUBSCRIPTION_KEY environment variables.\n")
    
    await run_quick_tests()
    
    print("\n" + "-" * 60)
    print("API Tests (require valid credentials)")
    print("-" * 60)
    
    await test_search_entities()
    await test_search_entities_with_filters()
    await test_get_entity()
    await test_get_entity_summary()
    await test_token_savings_comparison()
    await test_get_entity_addresses()
    await test_get_entity_roles()
    await test_get_entity_trading_names()
    await test_get_company_details()
    await test_get_entity_gst_numbers()
    await test_get_entity_industry_classifications()
    await test_get_changes()


async def main():
    quick_mode = "--quick" in sys.argv
    
    if quick_mode:
        await run_quick_tests()
    else:
        await run_full_tests()
    
    print("\n" + "=" * 60)
    print("[DONE] All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

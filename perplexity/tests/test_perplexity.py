# Test suite for Perplexity integration
import asyncio
from context import perplexity
from autohive_integrations_sdk import ExecutionContext


async def test_basic_search():
    """Test basic search with default parameters"""
    auth = {}

    inputs = {"query": "latest AI developments 2025"}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 1: Basic Search")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                print(f"SUCCESS: Found {result.get('total_results', 0)} results")
                for idx, item in enumerate(result.get("results", [])[:3], 1):
                    print(f"\n{idx}. {item.get('title', 'No title')}")
                    print(f"   URL: {item.get('url', 'No URL')}")

            return result
        except Exception as e:
            print(f"Error testing basic_search: {e}")
            return None


async def test_search_with_max_results():
    """Test search with custom max_results"""
    auth = {}

    inputs = {"query": "quantum computing breakthroughs", "max_results": 5}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 2: Search with max_results=5")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                total = result.get("total_results", 0)
                print(f"SUCCESS: Found {total} results (expected max 5)")
                assert total <= 5, f"Expected max 5 results, got {total}"

            return result
        except Exception as e:
            print(f"Error testing search_with_max_results: {e}")
            return None


async def test_search_with_content_depth():
    """Test search with different content_depth settings"""
    auth = {}

    for depth in ["quick", "default", "detailed"]:
        inputs = {"query": "Python best practices", "max_results": 3, "content_depth": depth}

        async with ExecutionContext(auth=auth) as context:
            try:
                print(f"\nTest 3.{['quick', 'default', 'detailed'].index(depth) + 1}: Content Depth = {depth}")
                print("=" * 60)
                result = await perplexity.execute_action("search_web", inputs, context)

                if "error" in result:
                    print(f"ERROR: {result['error']}")
                else:
                    print(f"SUCCESS: Found {result.get('total_results', 0)} results with {depth} depth")

            except Exception as e:
                print(f"Error testing content_depth={depth}: {e}")


async def test_search_with_country():
    """Test search with country filter"""
    auth = {}

    inputs = {"query": "top tech companies", "max_results": 5, "country": "US"}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 4: Search with country=US")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                print(f"SUCCESS: Found {result.get('total_results', 0)} US-filtered results")

            return result
        except Exception as e:
            print(f"Error testing search_with_country: {e}")
            return None


async def test_multi_query_search():
    """Test multi-query search (array of queries)"""
    auth = {}

    inputs = {
        "query": ["artificial intelligence trends", "machine learning applications", "neural networks research"],
        "max_results": 3,
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 5: Multi-Query Search (3 queries)")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                print(f"SUCCESS: Found {result.get('total_results', 0)} results from multi-query")

            return result
        except Exception as e:
            print(f"Error testing multi_query_search: {e}")
            return None


async def test_comprehensive_search():
    """Test search with all parameters"""
    auth = {}

    inputs = {"query": "climate change solutions", "max_results": 10, "content_depth": "detailed", "country": "GB"}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 6: Comprehensive Search (all parameters)")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                print(f"SUCCESS: Found {result.get('total_results', 0)} results")
                print("Parameters: max_results=10, content_depth=detailed, country=GB")

            return result
        except Exception as e:
            print(f"Error testing comprehensive_search: {e}")
            return None


async def test_maximum_results():
    """Test search with maximum allowed results (20)"""
    auth = {}

    inputs = {"query": "space exploration 2025", "max_results": 20}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 7: Maximum Results (20)")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                total = result.get("total_results", 0)
                print(f"SUCCESS: Found {total} results (max allowed is 20)")

            return result
        except Exception as e:
            print(f"Error testing maximum_results: {e}")
            return None


async def test_single_result():
    """Test search with minimum results (1)"""
    auth = {}

    inputs = {"query": "latest SpaceX launch", "max_results": 1}

    async with ExecutionContext(auth=auth) as context:
        try:
            print("\nTest 8: Single Result (1)")
            print("=" * 60)
            result = await perplexity.execute_action("search_web", inputs, context)

            if "error" in result:
                print(f"ERROR: {result['error']}")
            else:
                total = result.get("total_results", 0)
                print(f"SUCCESS: Found {total} result")
                if total > 0:
                    item = result.get("results", [])[0]
                    print(f"\nTitle: {item.get('title')}")
                    print(f"URL: {item.get('url')}")

            return result
        except Exception as e:
            print(f"Error testing single_result: {e}")
            return None


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PERPLEXITY INTEGRATION TEST SUITE")
    print("=" * 60)

    # Run all tests
    await test_basic_search()
    await test_search_with_max_results()
    await test_search_with_content_depth()
    await test_search_with_country()
    await test_multi_query_search()
    await test_comprehensive_search()
    await test_maximum_results()
    await test_single_result()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

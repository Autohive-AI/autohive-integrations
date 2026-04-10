# Testbed for Google Analytics integration
import asyncio
from context import google_analytics
from autohive_integrations_sdk import ExecutionContext

# Configuration - Replace these placeholder values with actual values for testing
PROPERTY_ID = "your_property_id_here"  # Replace with actual Google Analytics 4 Property ID (e.g., "123456789")

# Sample auth configuration
# Note: You'll need a valid Google OAuth2 access token with Analytics Data API access
auth = {
    "auth_type": "custom",
    "credentials": {
        "access_token": "your_access_token_here"  # Replace with actual access token
    }
}

async def test_run_report():
    """Test running a standard Google Analytics report."""
    print("=== TESTING RUN REPORT ===")

    try:
        inputs = {
            "property_id": PROPERTY_ID,
            "date_ranges": [
                {
                    "start_date": "7daysAgo",
                    "end_date": "today"
                }
            ],
            "dimensions": [
                {"name": "country"},
                {"name": "city"}
            ],
            "metrics": [
                {"name": "activeUsers"},
                {"name": "sessions"}
            ],
            "limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_analytics.execute_action("run_report", inputs, context)

            if result.get('result'):
                print(f"   ✓ Report generated successfully")
                print(f"   Rows returned: {result.get('row_count')}")
                if result.get('rows'):
                    print(f"   Sample row: {result.get('rows')[0]}")
            else:
                print(f"   ✗ Failed to run report: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== RUN REPORT TEST COMPLETED ===\n")

async def test_run_realtime_report():
    """Test running a realtime Google Analytics report."""
    print("=== TESTING RUN REALTIME REPORT ===")

    try:
        inputs = {
            "property_id": PROPERTY_ID,
            "dimensions": [
                {"name": "country"}
            ],
            "metrics": [
                {"name": "activeUsers"}
            ],
            "limit": 10
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_analytics.execute_action("run_realtime_report", inputs, context)

            if result.get('result'):
                print(f"   ✓ Realtime report generated successfully")
                print(f"   Rows returned: {result.get('row_count')}")
                if result.get('rows'):
                    print(f"   Sample row: {result.get('rows')[0]}")
            else:
                print(f"   ✗ Failed to run realtime report: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== RUN REALTIME REPORT TEST COMPLETED ===\n")

async def test_get_metadata():
    """Test retrieving metadata for available dimensions and metrics."""
    print("=== TESTING GET METADATA ===")

    try:
        inputs = {
            "property_id": PROPERTY_ID
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_analytics.execute_action("get_metadata", inputs, context)

            if result.get('result'):
                print(f"   ✓ Metadata retrieved successfully")
                print(f"   Dimensions: {result.get('dimension_count')}")
                print(f"   Metrics: {result.get('metric_count')}")
            else:
                print(f"   ✗ Failed to get metadata: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== GET METADATA TEST COMPLETED ===\n")

async def test_batch_run_reports():
    """Test running multiple reports in a single batch request."""
    print("=== TESTING BATCH RUN REPORTS ===")

    try:
        inputs = {
            "property_id": PROPERTY_ID,
            "report_requests": [
                {
                    "date_ranges": [
                        {
                            "start_date": "7daysAgo",
                            "end_date": "today"
                        }
                    ],
                    "dimensions": [{"name": "country"}],
                    "metrics": [{"name": "activeUsers"}],
                    "limit": 5
                },
                {
                    "date_ranges": [
                        {
                            "start_date": "30daysAgo",
                            "end_date": "today"
                        }
                    ],
                    "dimensions": [{"name": "deviceCategory"}],
                    "metrics": [{"name": "sessions"}],
                    "limit": 5
                }
            ]
        }

        async with ExecutionContext(auth=auth) as context:
            result = await google_analytics.execute_action("batch_run_reports", inputs, context)

            if result.get('result'):
                print(f"   ✓ Batch reports generated successfully")
                print(f"   Reports returned: {result.get('report_count')}")
                for i, report in enumerate(result.get('reports', [])):
                    print(f"   Report {i+1}: {report.get('row_count')} rows")
            else:
                print(f"   ✗ Failed to run batch reports: {result.get('error')}")

    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")

    print("=== BATCH RUN REPORTS TEST COMPLETED ===\n")

async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GOOGLE ANALYTICS INTEGRATION TEST SUITE")
    print("="*60 + "\n")

    print("NOTE: Update PROPERTY_ID and access_token before running tests\n")

    await test_run_report()
    await test_run_realtime_report()
    await test_get_metadata()
    await test_batch_run_reports()

    print("="*60)
    print("ALL TESTS COMPLETED")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

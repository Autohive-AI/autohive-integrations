"""
AWS Integration Tests

Tests all 20 AWS actions across Security Hub, GuardDuty,
CloudWatch, CloudWatch Logs, and CloudTrail.

To run these tests:
1. Update the credentials below with valid AWS access keys
2. Run: python tests/test_aws.py
"""

import asyncio
from context import integration
from autohive_integrations_sdk import ExecutionContext

TEST_AUTH = {
    "credentials": {
        "aws_access_key_id": "YOUR_ACCESS_KEY_ID",
        "aws_secret_access_key": "YOUR_SECRET_ACCESS_KEY",
        "aws_region": "us-east-1"
    }
}


# =============================================================================
# Security Hub Actions
# =============================================================================

async def test_get_findings():
    """Test retrieving Security Hub findings."""
    print("\n=== Testing get_findings ===")
    inputs = {"max_results": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_findings", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_finding_details():
    """Test retrieving details for a specific Security Hub finding."""
    print("\n=== Testing get_finding_details ===")
    inputs = {
        "finding_arn": "arn:aws:securityhub:us-east-1:123456789012:finding/example"
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_finding_details", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_update_finding_workflow():
    """Test updating the workflow status of Security Hub findings."""
    print("\n=== Testing update_finding_workflow ===")
    inputs = {
        "finding_arns": [
            "arn:aws:securityhub:us-east-1:123456789012:finding/example"
        ],
        "workflow_status": "RESOLVED",
        "note": "Resolved via Autohive"
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("update_finding_workflow", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_insights():
    """Test retrieving Security Hub insights."""
    print("\n=== Testing get_insights ===")
    inputs = {"max_results": 5}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_insights", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# =============================================================================
# GuardDuty Actions
# =============================================================================

async def test_list_detectors():
    """Test listing GuardDuty detectors."""
    print("\n=== Testing list_detectors ===")
    inputs = {"max_results": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("list_detectors", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_guardduty_findings():
    """Test listing GuardDuty findings for a detector."""
    print("\n=== Testing list_guardduty_findings ===")
    inputs = {
        "detector_id": "YOUR_DETECTOR_ID",
        "max_results": 10
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("list_guardduty_findings", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_guardduty_finding_details():
    """Test retrieving details for specific GuardDuty findings."""
    print("\n=== Testing get_guardduty_finding_details ===")
    inputs = {
        "detector_id": "YOUR_DETECTOR_ID",
        "finding_ids": ["example-finding-id"]
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_guardduty_finding_details", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_archive_findings():
    """Test archiving GuardDuty findings."""
    print("\n=== Testing archive_findings ===")
    inputs = {
        "detector_id": "YOUR_DETECTOR_ID",
        "finding_ids": ["example-finding-id"]
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("archive_findings", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# =============================================================================
# CloudWatch Actions
# =============================================================================

async def test_list_metrics():
    """Test listing CloudWatch metrics."""
    print("\n=== Testing list_metrics ===")
    inputs = {"namespace": "AWS/EC2"}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("list_metrics", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_metric_data():
    """Test retrieving CloudWatch metric data."""
    print("\n=== Testing get_metric_data ===")
    inputs = {
        "metric_data_queries": [
            {
                "Id": "m1",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization"
                    },
                    "Period": 300,
                    "Stat": "Average"
                }
            }
        ],
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-02T00:00:00Z"
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_metric_data", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_describe_alarms():
    """Test describing CloudWatch alarms."""
    print("\n=== Testing describe_alarms ===")
    inputs = {"max_records": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("describe_alarms", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_alarm_history():
    """Test retrieving CloudWatch alarm history."""
    print("\n=== Testing get_alarm_history ===")
    inputs = {"max_records": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_alarm_history", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_set_alarm_state():
    """Test setting the state of a CloudWatch alarm."""
    print("\n=== Testing set_alarm_state ===")
    inputs = {
        "alarm_name": "test-alarm",
        "state_value": "OK",
        "state_reason": "Testing via Autohive"
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("set_alarm_state", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# =============================================================================
# CloudWatch Logs Actions
# =============================================================================

async def test_describe_log_groups():
    """Test describing CloudWatch log groups."""
    print("\n=== Testing describe_log_groups ===")
    inputs = {"limit": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("describe_log_groups", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_filter_log_events():
    """Test filtering CloudWatch log events."""
    print("\n=== Testing filter_log_events ===")
    inputs = {
        "log_group_name": "/aws/lambda/test-function",
        "limit": 10
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("filter_log_events", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_log_events():
    """Test retrieving CloudWatch log events from a specific stream."""
    print("\n=== Testing get_log_events ===")
    inputs = {
        "log_group_name": "/aws/lambda/test-function",
        "log_stream_name": "test-stream",
        "limit": 10
    }
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_log_events", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# =============================================================================
# CloudTrail Actions
# =============================================================================

async def test_lookup_events():
    """Test looking up CloudTrail events."""
    print("\n=== Testing lookup_events ===")
    inputs = {"max_results": 10}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("lookup_events", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_describe_trails():
    """Test describing CloudTrail trails."""
    print("\n=== Testing describe_trails ===")
    inputs = {}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("describe_trails", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_trail_status():
    """Test retrieving the status of a CloudTrail trail."""
    print("\n=== Testing get_trail_status ===")
    inputs = {"trail_name": "management-events"}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_trail_status", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_event_selectors():
    """Test retrieving event selectors for a CloudTrail trail."""
    print("\n=== Testing get_event_selectors ===")
    inputs = {"trail_name": "management-events"}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await integration.execute_action("get_event_selectors", inputs, context)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


# =============================================================================
# Run All Tests
# =============================================================================

async def run_all_tests():
    """Run all 20 AWS integration tests and print a summary."""
    print("=" * 60)
    print("AWS Integration Tests")
    print("=" * 60)

    tests = [
        # Security Hub
        ("get_findings", test_get_findings),
        ("get_finding_details", test_get_finding_details),
        ("update_finding_workflow", test_update_finding_workflow),
        ("get_insights", test_get_insights),
        # GuardDuty
        ("list_detectors", test_list_detectors),
        ("list_guardduty_findings", test_list_guardduty_findings),
        ("get_guardduty_finding_details", test_get_guardduty_finding_details),
        ("archive_findings", test_archive_findings),
        # CloudWatch
        ("list_metrics", test_list_metrics),
        ("get_metric_data", test_get_metric_data),
        ("describe_alarms", test_describe_alarms),
        ("get_alarm_history", test_get_alarm_history),
        ("set_alarm_state", test_set_alarm_state),
        # CloudWatch Logs
        ("describe_log_groups", test_describe_log_groups),
        ("filter_log_events", test_filter_log_events),
        ("get_log_events", test_get_log_events),
        # CloudTrail
        ("lookup_events", test_lookup_events),
        ("describe_trails", test_describe_trails),
        ("get_trail_status", test_get_trail_status),
        ("get_event_selectors", test_get_event_selectors),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            if result is not None:
                results.append((name, "PASSED"))
            else:
                results.append((name, "FAILED: returned None"))
        except Exception as e:
            results.append((name, f"FAILED: {e}"))
            print(f"Error in {name}: {e}")

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = 0
    failed = 0
    for name, status in results:
        tag = "PASS" if status == "PASSED" else "FAIL"
        print(f"[{tag}] {name}: {status}")
        if status == "PASSED":
            passed += 1
        else:
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())

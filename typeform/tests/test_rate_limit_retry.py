"""
Test script to verify rate limit response structure.

This tests that when a 429 error occurs, the integration returns
a properly structured rate limit response that allows the LLM to:
1. Identify the error as a rate limit (error_type: 'rate_limit')
2. Know how long to wait (retry_after_seconds)
3. Track retry attempts (_retry_attempt)
4. Know when to stop retrying (can_retry, max_retries)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import SDK components directly (avoid loading integration config)
from autohive_integrations_sdk import ActionResult
from autohive_integrations_sdk.integration import RateLimitError
from typing import Dict, Any

# ============================================================
# Copy of rate limit functions from typeform.py for testing
# (This avoids SDK config loading issues during tests)
# ============================================================

MAX_RATE_LIMIT_RETRIES = 3


def create_rate_limit_response(
    retry_after_seconds: int,
    retry_attempt: int = 0,
    action_name: str = "",
    empty_data: Dict[str, Any] = None
) -> ActionResult:
    """Create a structured rate limit response for the LLM."""
    can_retry = retry_attempt < MAX_RATE_LIMIT_RETRIES

    if can_retry:
        error_message = (
            f"Rate limit exceeded. Please wait {retry_after_seconds} seconds before retrying. "
            f"This is attempt {retry_attempt + 1} of {MAX_RATE_LIMIT_RETRIES + 1} allowed attempts."
        )
        retry_instructions = (
            f"To retry: wait at least {retry_after_seconds} seconds, then call this action again "
            f"with _retry_attempt={retry_attempt + 1}. "
            f"You have {MAX_RATE_LIMIT_RETRIES - retry_attempt} retries remaining."
        )
    else:
        error_message = (
            f"Rate limit exceeded and maximum retry attempts ({MAX_RATE_LIMIT_RETRIES}) exhausted. "
            f"The Typeform API requires waiting {retry_after_seconds} seconds between requests. "
            "Please try again later or reduce request frequency."
        )
        retry_instructions = (
            "Maximum retries exceeded. Do not retry automatically. "
            "Inform the user that the Typeform API rate limit has been reached."
        )

    response_data = {
        **(empty_data or {}),
        "result": False,
        "error": error_message,
        "error_type": "rate_limit",
        "retry_after_seconds": retry_after_seconds,
        "retry_attempt": retry_attempt,
        "max_retries": MAX_RATE_LIMIT_RETRIES,
        "can_retry": can_retry,
        "retry_instructions": retry_instructions,
    }

    if action_name:
        response_data["action"] = action_name

    return ActionResult(data=response_data, cost_usd=0.0)


def is_rate_limit_error(error: Exception) -> tuple:
    """Check if an exception is a rate limit error and extract retry_after."""
    if isinstance(error, RateLimitError):
        return True, getattr(error, 'retry_after', 60)

    error_str = str(error).lower()
    if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
        return True, 60

    return False, 0


# ============================================================
# Tests
# ============================================================

def test_rate_limit_response_structure():
    """Test that rate limit response has all required fields."""
    print("=" * 60)
    print("Testing Rate Limit Response Structure")
    print("=" * 60)

    result = create_rate_limit_response(
        retry_after_seconds=37,
        retry_attempt=0,
        action_name="list_forms",
        empty_data={"forms": [], "total_items": 0}
    )

    data = result.data

    # Check all required fields exist
    required_fields = [
        "result", "error", "error_type", "retry_after_seconds",
        "retry_attempt", "max_retries", "can_retry", "retry_instructions"
    ]

    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"FAIL: Missing required fields: {missing}")
        return False

    # Validate field values
    checks = [
        (data["result"] == False, "result should be False"),
        (data["error_type"] == "rate_limit", "error_type should be 'rate_limit'"),
        (data["retry_after_seconds"] == 37, "retry_after_seconds should be 37"),
        (data["retry_attempt"] == 0, "retry_attempt should be 0"),
        (data["max_retries"] == MAX_RATE_LIMIT_RETRIES, f"max_retries should be {MAX_RATE_LIMIT_RETRIES}"),
        (data["can_retry"] == True, "can_retry should be True on first attempt"),
        (data["action"] == "list_forms", "action should be 'list_forms'"),
        (data["forms"] == [], "empty_data should be preserved"),
    ]

    for check, message in checks:
        if not check:
            print(f"FAIL: {message}")
            print(f"  Got: {data}")
            return False

    print("PASS: All required fields present and valid")
    print(f"  Response: {data}")
    return True


def test_max_retries_exceeded():
    """Test that can_retry becomes False after max retries."""
    print("\n" + "=" * 60)
    print("Testing Max Retries Exceeded")
    print("=" * 60)

    # Simulate exceeding max retries
    result = create_rate_limit_response(
        retry_after_seconds=60,
        retry_attempt=MAX_RATE_LIMIT_RETRIES,  # Already at max
        action_name="get_form",
        empty_data={"form": {}}
    )

    data = result.data

    if data["can_retry"] != False:
        print(f"FAIL: can_retry should be False after {MAX_RATE_LIMIT_RETRIES} attempts")
        return False

    if "do not retry" not in data["retry_instructions"].lower():
        print("FAIL: retry_instructions should tell LLM not to retry")
        return False

    print("PASS: can_retry is False and instructions say not to retry")
    print(f"  retry_instructions: {data['retry_instructions']}")
    return True


def test_is_rate_limit_error_detection():
    """Test that rate limit errors are correctly detected."""
    print("\n" + "=" * 60)
    print("Testing Rate Limit Error Detection")
    print("=" * 60)

    # Test SDK RateLimitError
    sdk_error = RateLimitError(30, 429, "Rate limit exceeded", "")
    is_rate_limit, retry_after = is_rate_limit_error(sdk_error)
    if not is_rate_limit:
        print("FAIL: Should detect RateLimitError from SDK")
        return False
    print(f"PASS: Detected SDK RateLimitError (retry_after={retry_after})")

    # Test 429 in error message
    http_error = Exception("HTTP 429: Too Many Requests")
    is_rate_limit, retry_after = is_rate_limit_error(http_error)
    if not is_rate_limit:
        print("FAIL: Should detect '429' in error message")
        return False
    print(f"PASS: Detected 429 in error message (retry_after={retry_after})")

    # Test "rate limit" in error message
    rate_limit_error = Exception("Rate limit exceeded for this API")
    is_rate_limit, retry_after = is_rate_limit_error(rate_limit_error)
    if not is_rate_limit:
        print("FAIL: Should detect 'rate limit' in error message")
        return False
    print(f"PASS: Detected 'rate limit' in error message (retry_after={retry_after})")

    # Test non-rate-limit error
    other_error = Exception("Connection timeout")
    is_rate_limit, retry_after = is_rate_limit_error(other_error)
    if is_rate_limit:
        print("FAIL: Should NOT detect regular errors as rate limits")
        return False
    print("PASS: Did not falsely detect regular error as rate limit")

    return True


def test_retry_attempt_tracking():
    """Test that retry attempts are properly tracked in responses."""
    print("\n" + "=" * 60)
    print("Testing Retry Attempt Tracking")
    print("=" * 60)

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 2):
        result = create_rate_limit_response(
            retry_after_seconds=30,
            retry_attempt=attempt,
            action_name="test_action",
            empty_data={}
        )
        data = result.data

        expected_can_retry = attempt < MAX_RATE_LIMIT_RETRIES

        if data["retry_attempt"] != attempt:
            print(f"FAIL: retry_attempt should be {attempt}, got {data['retry_attempt']}")
            return False

        if data["can_retry"] != expected_can_retry:
            print(f"FAIL: can_retry should be {expected_can_retry} at attempt {attempt}")
            return False

        status = "can retry" if expected_can_retry else "max retries reached"
        print(f"  Attempt {attempt}: {status}")

    print("PASS: Retry attempt tracking works correctly")
    return True


if __name__ == "__main__":
    print("\nTypeform Rate Limit Response Tests")
    print("=" * 60)

    tests = [
        ("Response Structure", test_rate_limit_response_structure),
        ("Max Retries Exceeded", test_max_retries_exceeded),
        ("Error Detection", test_is_rate_limit_error_detection),
        ("Retry Tracking", test_retry_attempt_tracking),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\nERROR in {name}: {type(e).__name__}: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    print("=" * 60)

    all_passed = all(passed for _, passed in results)
    sys.exit(0 if all_passed else 1)

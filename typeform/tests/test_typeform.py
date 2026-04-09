# Test suite for Typeform integration
import asyncio
import sys
from typing import Dict, Any

# Import SDK components (always available)
from autohive_integrations_sdk import ActionResult
from autohive_integrations_sdk.integration import RateLimitError


# ============================================================
# Rate Limit Unit Tests (no credentials needed)
# ============================================================

MAX_RATE_LIMIT_RETRIES = 3


def _create_rate_limit_response(
    retry_after_seconds: int,
    retry_attempt: int = 0,
    action_name: str = "",
    empty_data: Dict[str, Any] = None
) -> ActionResult:
    """Copy of rate limit response function for testing."""
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


def _is_rate_limit_error(error: Exception) -> tuple:
    """Copy of rate limit error detection for testing."""
    # SDK RateLimitError has retry_after from Retry-After header
    if isinstance(error, RateLimitError):
        return True, getattr(error, 'retry_after', 60)

    # Generic exceptions - detect from message, default to 60s
    # (can't access Retry-After header from exception message)
    error_str = str(error)
    error_lower = error_str.lower()
    if '429' in error_str or 'rate limit' in error_lower or 'too many requests' in error_lower:
        return True, 60

    return False, 0


def test_rate_limit_response_structure():
    """Test that rate limit response has all required fields."""
    result = _create_rate_limit_response(
        retry_after_seconds=37,
        retry_attempt=0,
        action_name="list_forms",
        empty_data={"forms": [], "total_items": 0}
    )
    data = result.data

    required_fields = ["result", "error", "error_type", "retry_after_seconds",
                       "retry_attempt", "max_retries", "can_retry", "retry_instructions"]

    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    assert data["result"] == False
    assert data["error_type"] == "rate_limit"
    assert data["retry_after_seconds"] == 37
    assert data["can_retry"] == True
    return True


def test_rate_limit_max_retries():
    """Test that can_retry becomes False after max retries."""
    result = _create_rate_limit_response(
        retry_after_seconds=60,
        retry_attempt=MAX_RATE_LIMIT_RETRIES,
        action_name="get_form",
        empty_data={"form": {}}
    )
    data = result.data

    assert data["can_retry"] == False
    assert "do not retry" in data["retry_instructions"].lower()
    return True


def test_rate_limit_error_detection():
    """Test that rate limit errors are correctly detected."""
    # SDK RateLimitError - has retry_after from Retry-After header
    sdk_error = RateLimitError(30, 429, "Rate limit exceeded", "")
    is_rate_limit, retry_after = _is_rate_limit_error(sdk_error)
    assert is_rate_limit, "Should detect RateLimitError"
    assert retry_after == 30, "Should get retry_after from SDK error"

    # 429 in message - defaults to 60s (can't get header from exception)
    http_error = Exception("HTTP 429: Too Many Requests")
    is_rate_limit, retry_after = _is_rate_limit_error(http_error)
    assert is_rate_limit, "Should detect 429 in message"
    assert retry_after == 60, f"Should default to 60, got {retry_after}"

    # "rate limit" in message
    rate_error = Exception("Rate limit exceeded")
    is_rate_limit, retry_after = _is_rate_limit_error(rate_error)
    assert is_rate_limit, "Should detect 'rate limit' in message"
    assert retry_after == 60, f"Should default to 60, got {retry_after}"

    # Non-rate-limit error
    other_error = Exception("Connection timeout")
    is_rate_limit, _ = _is_rate_limit_error(other_error)
    assert not is_rate_limit, "Should NOT detect regular error"

    return True


def run_rate_limit_tests():
    """Run rate limit unit tests (no credentials needed)."""
    print("=" * 60)
    print("Rate Limit Unit Tests (no credentials needed)")
    print("=" * 60)

    tests = [
        ("Response Structure", test_rate_limit_response_structure),
        ("Max Retries", test_rate_limit_max_retries),
        ("Error Detection", test_rate_limit_error_detection),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, True))
            print(f"  PASS: {name}")
        except AssertionError as e:
            results.append((name, False))
            print(f"  FAIL: {name} - {e}")
        except Exception as e:
            results.append((name, False))
            print(f"  ERROR: {name} - {e}")

    return all(passed for _, passed in results)


# ============================================================
# Integration Tests (requires credentials and config)
# ============================================================

# Lazy imports for integration tests
typeform = None
ExecutionContext = None


def _load_integration():
    """Lazy load integration components."""
    global typeform, ExecutionContext
    if typeform is None:
        from context import typeform as tf
        from autohive_integrations_sdk import ExecutionContext as EC
        typeform = tf
        ExecutionContext = EC


# ---- User Tests ----

async def test_get_current_user():
    """Test getting current user info."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_current_user", {}, context)
            print(f"Get Current User Result: {result}")
            assert result.data.get('result') == True
            assert 'user' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_current_user: {e}")
            return None


# ---- Form Tests ----

async def test_list_forms():
    """Test listing forms."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"page_size": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_forms", inputs, context)
            print(f"List Forms Result: {result}")
            assert result.data.get('result') == True
            assert 'forms' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_forms: {e}")
            return None


async def test_get_form():
    """Test getting form details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_form", inputs, context)
            print(f"Get Form Result: {result}")
            assert result.data.get('result') == True
            assert 'form' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_form: {e}")
            return None


async def test_create_form():
    """Test creating a form."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "title": "Test Form",
        "fields": [
            {
                "type": "short_text",
                "title": "What is your name?"
            }
        ]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("create_form", inputs, context)
            print(f"Create Form Result: {result}")
            assert result.data.get('result') == True
            assert 'form' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_form: {e}")
            return None


async def test_update_form():
    """Test updating a form."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "form_id": "your_form_id_here",
        "title": "Updated Test Form"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("update_form", inputs, context)
            print(f"Update Form Result: {result}")
            assert result.data.get('result') == True
            assert 'form' in result.data
            return result
        except Exception as e:
            print(f"Error testing update_form: {e}")
            return None


async def test_delete_form():
    """Test deleting a form."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_form", inputs, context)
            print(f"Delete Form Result: {result}")
            assert result.data.get('result') == True
            assert result.data.get('deleted') == True
            return result
        except Exception as e:
            print(f"Error testing delete_form: {e}")
            return None


# ---- Response Tests ----

async def test_list_responses():
    """Test listing form responses."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_here", "page_size": 25}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_responses", inputs, context)
            print(f"List Responses Result: {result}")
            assert result.data.get('result') == True
            assert 'responses' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_responses: {e}")
            return None


async def test_delete_responses():
    """Test deleting form responses."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "form_id": "your_form_id_here",
        "included_response_ids": "response_id_1,response_id_2"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_responses", inputs, context)
            print(f"Delete Responses Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_responses: {e}")
            return None


# ---- Workspace Tests ----

async def test_list_workspaces():
    """Test listing workspaces."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_workspaces", inputs, context)
            print(f"List Workspaces Result: {result}")
            assert result.data.get('result') == True
            assert 'workspaces' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_workspaces: {e}")
            return None


async def test_get_workspace():
    """Test getting workspace details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"workspace_id": "your_workspace_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_workspace", inputs, context)
            print(f"Get Workspace Result: {result}")
            assert result.data.get('result') == True
            assert 'workspace' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_workspace: {e}")
            return None


async def test_create_workspace():
    """Test creating a workspace."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"name": "Test Workspace"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("create_workspace", inputs, context)
            print(f"Create Workspace Result: {result}")
            assert result.data.get('result') == True
            assert 'workspace' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_workspace: {e}")
            return None


async def test_update_workspace():
    """Test updating a workspace."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"workspace_id": "your_workspace_id_here", "name": "Updated Workspace Name"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("update_workspace", inputs, context)
            print(f"Update Workspace Result: {result}")
            assert result.data.get('result') == True
            assert 'workspace' in result.data
            return result
        except Exception as e:
            print(f"Error testing update_workspace: {e}")
            return None


async def test_delete_workspace():
    """Test deleting a workspace."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"workspace_id": "your_workspace_id_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_workspace", inputs, context)
            print(f"Delete Workspace Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_workspace: {e}")
            return None


# ---- Theme Tests ----

async def test_list_themes():
    """Test listing themes."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_themes", inputs, context)
            print(f"List Themes Result: {result}")
            assert result.data.get('result') == True
            assert 'themes' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_themes: {e}")
            return None


async def test_get_theme():
    """Test getting theme details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"theme_id": "your_theme_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_theme", inputs, context)
            print(f"Get Theme Result: {result}")
            assert result.data.get('result') == True
            assert 'theme' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_theme: {e}")
            return None


async def test_create_theme():
    """Test creating a theme."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "name": "Test Theme",
        "colors": {
            "question": "#3D3D3D",
            "answer": "#4FB0AE",
            "button": "#4FB0AE",
            "background": "#FFFFFF"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("create_theme", inputs, context)
            print(f"Create Theme Result: {result}")
            assert result.data.get('result') == True
            assert 'theme' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_theme: {e}")
            return None


async def test_delete_theme():
    """Test deleting a theme."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"theme_id": "your_theme_id_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_theme", inputs, context)
            print(f"Delete Theme Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_theme: {e}")
            return None


# ---- Image Tests ----

async def test_list_images():
    """Test listing images."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_images", inputs, context)
            print(f"List Images Result: {result}")
            assert result.data.get('result') == True
            assert 'images' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_images: {e}")
            return None


async def test_get_image():
    """Test getting image details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"image_id": "your_image_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_image", inputs, context)
            print(f"Get Image Result: {result}")
            assert result.data.get('result') == True
            assert 'image' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_image: {e}")
            return None


async def test_delete_image():
    """Test deleting an image."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"image_id": "your_image_id_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_image", inputs, context)
            print(f"Delete Image Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_image: {e}")
            return None


# ---- Webhook Tests ----

async def test_list_webhooks():
    """Test listing webhooks."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("list_webhooks", inputs, context)
            print(f"List Webhooks Result: {result}")
            assert result.data.get('result') == True
            assert 'webhooks' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_webhooks: {e}")
            return None


async def test_get_webhook():
    """Test getting webhook details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_here", "tag": "your_webhook_tag"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("get_webhook", inputs, context)
            print(f"Get Webhook Result: {result}")
            assert result.data.get('result') == True
            assert 'webhook' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_webhook: {e}")
            return None


async def test_create_webhook():
    """Test creating a webhook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "form_id": "your_form_id_here",
        "tag": "test_webhook",
        "url": "https://example.com/webhook",
        "enabled": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("create_webhook", inputs, context)
            print(f"Create Webhook Result: {result}")
            assert result.data.get('result') == True
            assert 'webhook' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_webhook: {e}")
            return None


async def test_delete_webhook():
    """Test deleting a webhook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"form_id": "your_form_id_here", "tag": "webhook_tag_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await typeform.execute_action("delete_webhook", inputs, context)
            print(f"Delete Webhook Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_webhook: {e}")
            return None


# Main test runner
async def run_integration_tests():
    """Run integration tests (requires credentials)."""
    print("\n" + "=" * 60)
    print("Integration Tests (requires credentials)")
    print("=" * 60)

    # Load integration (lazy import)
    _load_integration()

    test_functions = [
        # User
        ("Get Current User", test_get_current_user),
        # Forms
        ("List Forms", test_list_forms),
        ("Get Form", test_get_form),
        ("Create Form", test_create_form),
        ("Update Form", test_update_form),
        ("Delete Form", test_delete_form),
        # Responses
        ("List Responses", test_list_responses),
        ("Delete Responses", test_delete_responses),
        # Workspaces
        ("List Workspaces", test_list_workspaces),
        ("Get Workspace", test_get_workspace),
        ("Create Workspace", test_create_workspace),
        ("Update Workspace", test_update_workspace),
        ("Delete Workspace", test_delete_workspace),
        # Themes
        ("List Themes", test_list_themes),
        ("Get Theme", test_get_theme),
        ("Create Theme", test_create_theme),
        ("Delete Theme", test_delete_theme),
        # Images
        ("List Images", test_list_images),
        ("Get Image", test_get_image),
        ("Delete Image", test_delete_image),
        # Webhooks
        ("List Webhooks", test_list_webhooks),
        ("Get Webhook", test_get_webhook),
        ("Create Webhook", test_create_webhook),
        ("Delete Webhook", test_delete_webhook),
    ]

    results = []
    for test_name, test_func in test_functions:
        print(f"\n{'-' * 60}")
        print(f"Running: {test_name}")
        print(f"{'-' * 60}")
        result = await test_func()
        results.append((test_name, result is not None))

    print("\n" + "=" * 60)
    print("Integration Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    return passed_count == len(results)


if __name__ == "__main__":
    # Parse arguments
    run_integration = "--integration" in sys.argv or "-i" in sys.argv
    run_unit = "--unit" in sys.argv or "-u" in sys.argv or (not run_integration)

    print("Typeform Test Suite")
    print("=" * 60)

    all_passed = True

    # Always run unit tests (no credentials needed)
    if run_unit:
        unit_passed = run_rate_limit_tests()
        all_passed = all_passed and unit_passed

    # Run integration tests only if requested
    if run_integration:
        integration_passed = asyncio.run(run_integration_tests())
        all_passed = all_passed and integration_passed

    print("\n" + "=" * 60)
    if not run_integration:
        print("Note: Run with --integration to run API tests (requires credentials)")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)

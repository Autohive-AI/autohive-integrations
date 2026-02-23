"""
Test context helper for Companies Register integration tests.

Provides test authentication context for both sandbox and production testing.
"""
from typing import Dict, Any


def get_test_auth(subscription_key: str = None, access_token: str = None) -> Dict[str, Any]:
    """
    Create test authentication context.

    Args:
        subscription_key: Azure API Management subscription key
        access_token: OAuth access token from RealMe

    Returns:
        Auth dictionary for ExecutionContext
    """
    return {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "subscription_key": subscription_key or "test_subscription_key",
            "access_token": access_token or "test_access_token"
        }
    }


def get_sandbox_auth() -> Dict[str, Any]:
    """
    Get sandbox test authentication.

    For actual testing, replace these with real credentials:
    - Subscription key from: https://portal.api.business.govt.nz/
    - Access token from: OAuth flow with L_testuser
    """
    return get_test_auth(
        subscription_key="0edb88c378df45e5aa0fc4a361cfaa51",
        access_token="your_oauth_token_here"
    )


# Test company UUIDs (from MBIE testing)
TEST_COMPANY_UUIDS = [
    "b65f62b6-65c5-4141-9cbf-094c4573878c",  # Testing 1 Limited
    "6e4a42c7-e7d5-4f7d-a2e1-c3322dbaa02c",  # Testing 2 Limited
    "3d6deda2-3e7d-43b7-b806-941bb2817cab",  # Testing 3 Limited
    "efa332db-ba82-44e7-adb4-32bc81b17d64",  # Testing 4 Limited
    "51c59c3e-e3cb-4c36-a8f7-cc094e0efc5b",  # Testing 5 Limited
]

# Test organization ID (TESTING LTD in sandbox)
TEST_ORG_ID = "137859"

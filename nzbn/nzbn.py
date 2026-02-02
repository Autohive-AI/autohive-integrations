"""
NZBN (New Zealand Business Number) Integration

This integration provides access to the NZBN Register API for searching and
retrieving business entity information in New Zealand.

SECURITY MODEL:
---------------
This integration uses Autohive's registered NZBN application credentials.
The OAuth client_id, client_secret, and subscription_key are NOT stored in this
source code. The placeholder values below MUST be replaced with actual secrets
at deployment time via:
- Environment variables
- Secrets management system
- Secure configuration injection

The 2-legged OAuth (Client Credentials) flow is appropriate here because:
1. Autohive owns the registered NZBN application
2. Credentials are injected server-side at deployment, not distributed to users
3. Users don't need to configure any credentials - zero-config experience

DO NOT commit actual secrets to this file.
"""

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, Optional, Tuple
import base64
import time
import os

nzbn = Integration.load()

# =============================================================================
# API Configuration
# =============================================================================

PRODUCTION_BASE_URL = "https://api.business.govt.nz/gateway/nzbn/v5"
TOKEN_URL = "https://login.microsoftonline.com/b2cessmapprd.onmicrosoft.com/oauth2/v2.0/token"
PRODUCTION_SCOPE = "https://api.business.govt.nz/gateway/.default"

# =============================================================================
# Credentials Configuration
# 
# IMPORTANT: These placeholders MUST be replaced at deployment time.
# Secrets should be injected via environment variables or secrets management.
# =============================================================================

# OAuth App Credentials (Autohive's registered NZBN application)
OAUTH_CLIENT_ID = os.environ.get("NZBN_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("NZBN_CLIENT_SECRET", "")

# NZBN API Subscription Key (Autohive's enterprise subscription)
SUBSCRIPTION_KEY = os.environ.get("NZBN_SUBSCRIPTION_KEY", "")

# =============================================================================
# OAuth Token Cache
# 
# Caches OAuth tokens to avoid fetching a new token on every request.
# Tokens are refreshed 60 seconds before expiry for safety margin.
# =============================================================================

_token_cache: Dict[str, Tuple[str, float]] = {}
TOKEN_REFRESH_BUFFER_SECONDS = 60


def _get_cached_token(cache_key: str) -> Optional[str]:
    """Get a valid cached token if available."""
    if cache_key in _token_cache:
        token, expiry = _token_cache[cache_key]
        if time.time() < expiry - TOKEN_REFRESH_BUFFER_SECONDS:
            return token
    return None


def _cache_token(cache_key: str, token: str, expires_in: int) -> None:
    """Cache a token with its expiry time."""
    _token_cache[cache_key] = (token, time.time() + expires_in)


async def get_oauth_token(context: ExecutionContext) -> Optional[str]:
    """
    Get OAuth access token using 2-legged client credentials flow.
    
    Implements token caching to minimize API calls to the token endpoint.
    Tokens are cached until 60 seconds before expiry.
    """
    cache_key = PRODUCTION_SCOPE
    
    # Check cache first
    cached_token = _get_cached_token(cache_key)
    if cached_token:
        return cached_token
    
    # Validate credentials are configured
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        return None
    
    auth_string = f"{OAUTH_CLIENT_ID}:{OAUTH_CLIENT_SECRET}"
    auth_bytes = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_bytes}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = await context.fetch(
        TOKEN_URL,
        method="POST",
        headers=headers,
        data={"grant_type": "client_credentials", "scope": PRODUCTION_SCOPE}
    )
    
    # Handle response
    token_data = None
    if hasattr(response, 'status_code') and response.status_code == 200:
        token_data = response.json()
    elif isinstance(response, dict):
        token_data = response
    
    if token_data and "access_token" in token_data:
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        _cache_token(cache_key, access_token, expires_in)
        return access_token
    
    return None


async def get_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for NZBN API requests with OAuth token and subscription key."""
    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    access_token = await get_oauth_token(context)
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    
    return headers


async def make_request(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make a request to the NZBN API."""
    headers = await get_headers(context)
    url = f"{PRODUCTION_BASE_URL}{endpoint}"
    
    response = await context.fetch(
        url,
        method=method,
        headers=headers,
        params=params
    )
    
    if hasattr(response, 'status_code'):
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        elif response.status_code == 304:
            return {"success": True, "data": None, "not_modified": True}
        elif response.status_code == 400:
            error_data = response.json() if hasattr(response, 'json') else {}
            return {
                "success": False,
                "error": error_data.get("errorDescription", "Bad request - validation failed")
            }
        elif response.status_code == 401:
            return {"success": False, "error": "Unauthorized - invalid credentials"}
        elif response.status_code == 403:
            return {"success": False, "error": "Forbidden - insufficient permissions"}
        elif response.status_code == 404:
            return {"success": False, "error": "Entity not found"}
        else:
            return {"success": False, "error": f"API error: {response.status_code}"}
    
    return {"success": True, "data": response}


# =============================================================================
# Action Handlers
# =============================================================================

@nzbn.action("search_entities")
class SearchEntitiesAction(ActionHandler):
    """Search the NZBN directory by name or identifier."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            search_term = inputs.get("search_term", "")
            if not search_term:
                return ActionResult(
                    data={"result": False, "error": "search_term is required"},
                    cost_usd=0.0
                )
            
            params = {"search-term": search_term}
            
            if inputs.get("entity_status"):
                params["entity-status"] = inputs["entity_status"]
            if inputs.get("entity_type"):
                params["entity-type"] = inputs["entity_type"]
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size"):
                params["page-size"] = inputs["page_size"]
            
            result = await make_request(context, "GET", "/entities", params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "items": []},
                    cost_usd=0.0
                )
            
            data = result["data"]
            return ActionResult(
                data={
                    "result": True,
                    "items": data.get("items", []),
                    "totalItems": data.get("totalItems", 0),
                    "page": data.get("page", 0),
                    "pageSize": data.get("pageSize", 25)
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "items": []},
                cost_usd=0.0
            )


@nzbn.action("get_entity")
class GetEntityAction(ActionHandler):
    """Get detailed information about a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required"},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "entity": result["data"]},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@nzbn.action("get_entity_addresses")
class GetEntityAddressesAction(ActionHandler):
    """Get addresses for a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required", "addresses": []},
                    cost_usd=0.0
                )
            
            params = {}
            if inputs.get("address_type"):
                params["address-type"] = inputs["address_type"]
            
            result = await make_request(
                context, "GET", f"/entities/{nzbn_id}/addresses", params if params else None
            )
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "addresses": []},
                    cost_usd=0.0
                )
            
            addresses = result["data"] if isinstance(result["data"], list) else result["data"].get("items", [])
            return ActionResult(
                data={"result": True, "addresses": addresses},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "addresses": []},
                cost_usd=0.0
            )


@nzbn.action("get_entity_roles")
class GetEntityRolesAction(ActionHandler):
    """Get roles/officers for a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required", "roles": []},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}/roles")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "roles": []},
                    cost_usd=0.0
                )
            
            roles = result["data"] if isinstance(result["data"], list) else result["data"].get("items", [])
            return ActionResult(
                data={"result": True, "roles": roles},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "roles": []},
                cost_usd=0.0
            )


@nzbn.action("get_entity_trading_names")
class GetEntityTradingNamesAction(ActionHandler):
    """Get trading names for a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required", "tradingNames": []},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}/trading-names")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "tradingNames": []},
                    cost_usd=0.0
                )
            
            trading_names = result["data"] if isinstance(result["data"], list) else result["data"].get("items", [])
            return ActionResult(
                data={"result": True, "tradingNames": trading_names},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "tradingNames": []},
                cost_usd=0.0
            )


@nzbn.action("get_company_details")
class GetCompanyDetailsAction(ActionHandler):
    """Get company-specific details for NZ companies."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required"},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}/company-details")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"]},
                    cost_usd=0.0
                )
            
            return ActionResult(
                data={"result": True, "companyDetails": result["data"]},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@nzbn.action("get_entity_gst_numbers")
class GetEntityGstNumbersAction(ActionHandler):
    """Get GST numbers for a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required", "gstNumbers": []},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}/gst-numbers")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "gstNumbers": []},
                    cost_usd=0.0
                )
            
            gst_numbers = result["data"] if isinstance(result["data"], list) else result["data"].get("items", [])
            return ActionResult(
                data={"result": True, "gstNumbers": gst_numbers},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "gstNumbers": []},
                cost_usd=0.0
            )


@nzbn.action("get_entity_industry_classifications")
class GetEntityIndustryClassificationsAction(ActionHandler):
    """Get industry classifications for a specific entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            nzbn_id = inputs.get("nzbn", "")
            if not nzbn_id:
                return ActionResult(
                    data={"result": False, "error": "nzbn is required", "industryClassifications": []},
                    cost_usd=0.0
                )
            
            result = await make_request(context, "GET", f"/entities/{nzbn_id}/industry-classifications")
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "industryClassifications": []},
                    cost_usd=0.0
                )
            
            classifications = result["data"] if isinstance(result["data"], list) else result["data"].get("items", [])
            return ActionResult(
                data={"result": True, "industryClassifications": classifications},
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "industryClassifications": []},
                cost_usd=0.0
            )


@nzbn.action("get_changes")
class GetChangesAction(ActionHandler):
    """Get recent changes to entities."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            change_event_type = inputs.get("change_event_type", "")
            if not change_event_type:
                return ActionResult(
                    data={"result": False, "error": "change_event_type is required", "changes": []},
                    cost_usd=0.0
                )
            
            params = {"change-event-type": change_event_type}
            
            if inputs.get("start_date"):
                params["start-date"] = inputs["start_date"]
            if inputs.get("end_date"):
                params["end-date"] = inputs["end_date"]
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size"):
                params["page-size"] = inputs["page_size"]
            
            result = await make_request(context, "GET", "/entities/changes", params)
            
            if not result["success"]:
                return ActionResult(
                    data={"result": False, "error": result["error"], "changes": []},
                    cost_usd=0.0
                )
            
            data = result["data"]
            changes = data.get("items", []) if isinstance(data, dict) else data
            return ActionResult(
                data={
                    "result": True,
                    "changes": changes,
                    "totalItems": data.get("totalItems", len(changes)) if isinstance(data, dict) else len(changes)
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e), "changes": []},
                cost_usd=0.0
            )

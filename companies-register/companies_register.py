from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional
import aiohttp
import json
import base64
import re
import os

# Create the integration using the config.json
companies_register = Integration.load()

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================
# The Companies Register API has two environments:
#
# SANDBOX (Testing): https://api.business.govt.nz/sandbox/{{resource path}}
# PRODUCTION: https://api.business.govt.nz/gateway/{{resource path}}
#
# Currently using SANDBOX. To switch to production after approval:
# 1. Change "sandbox" to "gateway" in BASE_URL_V2 below
# 2. Change "sandbox" to "services/v4" in BASE_URL below
# 3. Update your API subscription key to use production key
# =============================================================================

# CURRENT: SANDBOX Environment
BASE_URL_V2 = "https://api.business.govt.nz/sandbox/companies-office/companies-register/companies/v2"
BASE_URL = "https://api.business.govt.nz/sandbox/companies-register"

# FOR PRODUCTION (after approval), uncomment these and comment out sandbox URLs above:
# BASE_URL_V2 = "https://api.business.govt.nz/gateway/companies-office/companies-register/companies/v2"
# BASE_URL = "https://api.business.govt.nz/services/v4/companies-register"

# =============================================================================
# CREDENTIALS CONFIGURATION
#
# IMPORTANT: These placeholders MUST be replaced at deployment time.
# Secrets should be injected via environment variables or secrets management.
# DO NOT commit actual secrets to this file.
# =============================================================================

# Azure API Management Subscription Key (Autohive's registered subscription)
# Users do not need to configure this — it is injected server-side at deployment.
SUBSCRIPTION_KEY = os.environ.get("COMPANIES_REGISTER_SUBSCRIPTION_KEY", "")

# ---- Helper Functions ----

def to_camel_case(snake_str: str) -> str:
    """Convert snake_case string to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def get_input_value(inputs: Dict[str, Any], camel_key: str, snake_key: str = None, default: Any = None) -> Any:
    """
    Get input value supporting both camelCase and snake_case keys for backward compatibility.
    Prefers camelCase (per schema), falls back to snake_case if provided.

    Args:
        inputs: Input dictionary
        camel_key: CamelCase key name (preferred, matches schema)
        snake_key: Optional snake_case key name for backward compatibility
        default: Default value if neither key is found

    Returns:
        Value from inputs, or default if not found
    """
    # First try camelCase (preferred per schema)
    if camel_key in inputs:
        return inputs[camel_key]

    # Fall back to snake_case for backward compatibility
    if snake_key and snake_key in inputs:
        return inputs[snake_key]

    # If no snake_key provided, try auto-converting camelCase to snake_case
    if not snake_key:
        # Convert camelCase to snake_case for backward compatibility check
        snake_key = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_key).lower()
        if snake_key in inputs:
            return inputs[snake_key]

    return default


def get_api_headers(context: ExecutionContext, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
    """
    Build headers for API requests.
    - Subscription key is read from the COMPANIES_REGISTER_SUBSCRIPTION_KEY env variable (server-side).
    - OAuth access token is read from context.auth (user's RealMe OAuth token).
    """
    headers = {}

    # Subscription key — injected server-side via environment variable
    if SUBSCRIPTION_KEY:
        headers["Ocp-Apim-Subscription-Key"] = SUBSCRIPTION_KEY

    # OAuth access token — from user's RealMe authentication
    if hasattr(context, 'auth') and isinstance(context.auth, dict):
        credentials = context.auth.get('credentials', {})
        if isinstance(credentials, dict):
            access_token = credentials.get('access_token')
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

    if additional_headers:
        headers.update(additional_headers)

    return headers


async def fetch_with_headers(url: str, method: str = "GET", headers: Dict[str, str] = None,
                             params: Dict[str, Any] = None, payload: Dict[str, Any] = None) -> tuple[Any, Dict[str, str]]:
    """
    Make an HTTP request using aiohttp and return both the response body and headers.
    This is needed because context.fetch() doesn't provide access to response headers.

    Returns: (response_body, response_headers)
    """
    async with aiohttp.ClientSession() as session:
        # Make a copy of headers to avoid modifying the original
        request_headers = dict(headers) if headers else {}

        kwargs = {
            "method": method,
            "url": url,
            "headers": request_headers,
            "ssl": True
        }

        if params:
            kwargs["params"] = params

        if payload:
            kwargs["data"] = json.dumps(payload)
            if "Content-Type" not in request_headers:
                request_headers["Content-Type"] = "application/json"

        async with session.request(**kwargs) as response:
            # Extract ETag before converting headers (use case-insensitive get from aiohttp)
            etag = response.headers.get('ETag')

            # Extract headers - aiohttp headers are case-insensitive
            response_headers = {}
            for key, value in response.headers.items():
                response_headers[key] = value

            # Add ETag to response_headers dict with standardized key
            if etag:
                response_headers['ETag'] = etag

            # Check if response is successful
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text}")

            # Parse JSON response
            try:
                response_body = await response.json()
            except (ValueError, aiohttp.ContentTypeError):
                response_body = await response.text()

            return response_body, response_headers

# ---- Action Handlers ----

@companies_register.action("search_company")
class SearchCompanyAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_00: Company search to check if a name is available and valid.
        Supports two-legged authentication for guest users.
        Returns 200 with empty items if available, or warning codes if name needs review.
        """
        try:
            query = inputs["query"]
            search_type = inputs.get("searchType", "name")
            entity_type = inputs.get("entityType")
            usage = inputs.get("usage", "name-check")

            if search_type == "name":
                # Search by company name using v2 endpoint
                url = f"{BASE_URL_V2}/"

                params = {
                    "company-name": query,
                    "usage": usage
                }

                # Add optional entity type filter
                if entity_type:
                    params["entity-type"] = entity_type

                # Build headers with subscription key
                headers = get_api_headers(context)

                response = await context.fetch(
                    url,
                    method="GET",
                    params=params,
                    headers=headers
                )

                # Extract items and metadata from response
                items = response.get("items", []) if isinstance(response, dict) else []
                metadata = {k: v for k, v in response.items() if k != "items"} if isinstance(response, dict) else {}

                # Check if name is available
                is_available = len(items) == 0

                return ActionResult(
                    data={
                        "items": items,
                        "metadata": metadata,
                        "isAvailable": is_available,
                        "result": True,
                        "count": len(items),
                        "message": "Name is available" if is_available else "Name already exists or is similar to existing company"
                    },
                    cost_usd=None
                )
            else:
                # Search by company number/UUID - get specific company
                url = f"{BASE_URL_V2}/{query}"

                # Build headers with subscription key
                headers = get_api_headers(context)

                response = await context.fetch(
                    url,
                    method="GET",
                    headers=headers
                )

                # Single company result wrapped in items array
                items = [response] if response else []

                return ActionResult(
                    data={
                        "items": items,
                        "metadata": {},
                        "isAvailable": False,
                        "result": True,
                        "count": len(items)
                    },
                    cost_usd=None
                )

        except Exception as e:
            error_str = str(e)

            # Check for warning codes that indicate name is available with conditions
            if "WARNING_" in error_str:
                is_available_with_warning = True
                if "WARNING_NAME_CONTAINS_PROBABLE_RESTRICTED" in error_str:
                    warning_message = "Name is available but contains a word that may cause rejection. Approval required."
                elif "WARNING_NAME_CONVERTED_GEOGRAPHIC_NAME" in error_str:
                    warning_message = "Name is available but contains a geographic name that will be converted to official format."
                else:
                    warning_message = "Name is available but requires review."

                return ActionResult(
                    data={
                        "items": [],
                        "metadata": {},
                        "isAvailable": True,
                        "hasWarning": True,
                        "warningMessage": warning_message,
                        "result": True,
                        "count": 0
                    },
                    cost_usd=None
                )

            # Other errors
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error searching companies: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("get_company_details")
class GetCompanyDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_03: Get company details using companyUuid (can also be NZBN).
        Returns full Company object with all details including status, contacts, links.
        Supports ETag optimization with If-None-Match header.
        """
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "companyUuid": response.get("companyUuid"),
                    "companyName": response.get("companyName"),
                    "nzbn": response.get("nzbn"),
                    "entityType": response.get("entityType"),
                    "companyStatusCode": response.get("companyStatusCode"),
                    "companyStatusDescription": response.get("companyStatusDescription"),
                    "companyStatusExpiryDate": response.get("companyStatusExpiryDate"),
                    "registrationDate": response.get("registrationDate"),
                    "isUltimateHoldingCompany": response.get("isUltimateHoldingCompany"),
                    "annualReturnFilingMonth": response.get("annualReturnFilingMonth"),
                    "annualReturnLastFiled": response.get("annualReturnLastFiled"),
                    "isConstitutionFiled": response.get("isConstitutionFiled"),
                    "website": response.get("website"),
                    "contacts": response.get("contacts"),
                    "link": response.get("link"),
                    "directorLinks": response.get("directorLinks"),
                    "shareholdingLink": response.get("shareholdingLink"),
                    "constitutionLink": response.get("constitutionLink"),
                    "taxRegistrationLink": response.get("taxRegistrationLink"),
                    "ultimateHoldingCompany": response.get("ultimateHoldingCompany"),
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Handle 304 Not Modified
            if "304" in error_str:
                return ActionResult(
                    data={
                        "result": True,
                        "notModified": True,
                        "message": "Company data not modified since last request"
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving company details: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("get_company_directors")
class GetCompanyDirectorsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get company directors using companyUuid. Supports optional headers."""
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            # Extract directors list from response
            directors = response.get("items", []) if isinstance(response, dict) else response

            return ActionResult(
                data={
                    "directors": directors,
                    "result": True,
                    "count": len(directors) if isinstance(directors, list) else 0
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving directors: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("add_company_director")
class AddCompanyDirectorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_01: Add a new director to the company.
        Checks for banned directors or undischarged bankrupts.
        Sends consent form to director email (must be returned within 20 working days).
        """
        try:
            company_uuid = inputs["companyUuid"]
            appointed_date = inputs["appointedDate"]
            person_in_role = inputs["personInRole"]
            contacts = inputs["contacts"]
            is_person_in_role_myself = inputs.get("isPersonInRoleMyself", False)
            ird_number = inputs.get("irdNumber")
            director_not_one_of = inputs.get("directorNotOneOf", [])
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors"

            # Build payload with nested structure matching API
            # Use camelCase format for nested objects:
            # personInRole = {"name": {"firstName": "...", "middleNames": "...", "lastName": "..."},
            #                 "birthInfo": {"dateOfBirth": "...", "countryOfBirth": "...", "townCityOfBirth": "..."}}
            # contacts = {"physicalOrPostalAddresses": [...], "phoneContacts": [...], "emailAddresses": [...]}
            payload = {
                "appointedDate": appointed_date,
                "personInRole": person_in_role,
                "contacts": contacts
            }

            # Add optional fields
            if is_person_in_role_myself:
                payload["isPersonInRoleMyself"] = is_person_in_role_myself

            if ird_number:
                payload["irdNumber"] = ird_number

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Add directorNotOneOf as query parameter if provided
            params = {}
            if director_not_one_of:
                params["directorNotOneOf"] = director_not_one_of

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to get response headers (for potential ETag)
            response, response_headers = await fetch_with_headers(
                url=url,
                method="POST",
                headers=headers,
                params=params if params else None,
                payload=payload
            )

            # Get director name for message (try camelCase first, then snake_case for backward compatibility)
            director_name = "Director"
            if "name" in person_in_role:
                name_parts = []
                name_obj = person_in_role["name"]
                first_name = name_obj.get("firstName") or name_obj.get("first_name")
                last_name = name_obj.get("lastName") or name_obj.get("last_name")
                if first_name:
                    name_parts.append(first_name)
                if last_name:
                    name_parts.append(last_name)
                director_name = " ".join(name_parts) if name_parts else "Director"

            return ActionResult(
                data={
                    "director": response,
                    "consentFormEmailed": True,
                    "consentDeadline": "20 working days from today",
                    "result": True,
                    "message": f"Director {director_name} added successfully. Consent form has been emailed."
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Check for banned director matches
            if "probable match" in error_str.lower() or "disqualified" in error_str.lower():
                return ActionResult(
                    data={
                        "success": False,
                        "message": f"Director addition failed: Probable match with disqualified director found. {error_str}",
                        "error": error_str,
                        "banned_director_matches": []
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error adding director: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("get_director_details")
class GetDirectorDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_08: Get director details by directorId.
        Birth information is not returned.
        Supports ETag optimization.
        """
        try:
            company_uuid = inputs["companyUuid"]
            director_id = inputs["directorId"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors/{director_id}"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "director": response,
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Handle 304 Not Modified
            if "304" in error_str:
                return ActionResult(
                    data={
                        "result": True,
                        "notModified": True,
                        "message": "Director data not modified since last request"
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving director details: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("update_company_director")
class UpdateCompanyDirectorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_07: Update a director's details.
        Allows updating contact details including residential address.
        Birth information cannot be updated.
        Director name can only be updated for pre-incorporated companies.
        """
        try:
            company_uuid = inputs["companyUuid"]
            director_id = inputs["directorId"]
            etag = inputs["etag"]
            role_id = inputs.get("roleId")
            appointed_date = inputs.get("appointedDate")
            person_in_role = inputs.get("personInRole")
            contacts = inputs.get("contacts")
            ird_number = inputs.get("irdNumber")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors/{director_id}"

            # Build payload with only provided fields
            payload = {}

            if role_id:
                payload["roleId"] = role_id

            if appointed_date:
                payload["appointedDate"] = appointed_date

            # Use camelCase format for nested objects:
            # personInRole = {"name": {"firstName": "...", "middleNames": "...", "lastName": "..."},
            #                 "birthInfo": {"dateOfBirth": "...", "countryOfBirth": "...", "townCityOfBirth": "..."}}
            # contacts = {"physicalOrPostalAddresses": [...], "phoneContacts": [...], "emailAddresses": [...]}
            if person_in_role:
                payload["personInRole"] = person_in_role

            if contacts:
                payload["contacts"] = contacts

            if ird_number:
                payload["irdNumber"] = ird_number

            # Build optional headers including If-Match for concurrency control
            optional_headers = {
                "If-Match": etag
            }
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="PUT",
                headers=headers,
                payload=payload
            )

            # Extract ETag from response headers
            new_etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "director": response,
                    "etag": new_etag,
                    "result": True,
                    "message": "Director details updated successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error updating director: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("remove_company_director")
class RemoveCompanyDirectorAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_09: Remove a director (soft delete).
        Active directors are marked as Ceased, Pending directors as Withdrawn.
        At least one eligible director must remain.
        """
        try:
            company_uuid = inputs["companyUuid"]
            director_id = inputs["directorId"]
            etag = inputs["etag"]
            effective_date = inputs.get("effectiveDate")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors/{director_id}"

            # Build payload
            payload = {}
            if effective_date:
                payload["ceasedDate"] = effective_date

            # Build optional headers including If-Match for concurrency control
            optional_headers = {
                "If-Match": etag
            }
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers
            response, response_headers = await fetch_with_headers(
                url=url,
                method="DELETE",
                headers=headers,
                payload=payload if payload else None
            )

            return ActionResult(
                data={
                    "directorId": director_id,
                    "status": response.get("roleStatus", "Ceased/Withdrawn"),
                    "effectiveDate": effective_date,
                    "result": True,
                    "message": "Director removed successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error removing director: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_director_documents")
class GetDirectorDocumentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_49: Get document references associated with a director (e.g., consent forms).
        """
        try:
            company_uuid = inputs["companyUuid"]
            director_id = inputs["directorId"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors/{director_id}/document-associations"

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            # Extract documents list from response
            documents = response.get("items", []) if isinstance(response, dict) else response

            return ActionResult(
                data={
                    "documents": documents,
                    "result": True,
                    "count": len(documents) if isinstance(documents, list) else 0
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving director documents: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("associate_director_document")
class AssociateDirectorDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_50: Associate consent document to a director.
        Documents must be uploaded first.
        Processed within 1 hour during business hours.
        """
        try:
            company_uuid = inputs["companyUuid"]
            director_id = inputs["directorId"]
            consent_document_ref = inputs["consentDocumentRef"]
            supporting_document_ref = inputs.get("supportingDocumentRef")
            statutory_declaration_document_ref = inputs.get("statutoryDeclarationDocumentRef")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/directors/{director_id}/document-associations"

            # Build payload
            payload = {
                "consentDocumentRef": consent_document_ref
            }

            if supporting_document_ref:
                payload["supportingDocumentRef"] = supporting_document_ref

            if statutory_declaration_document_ref:
                payload["statutoryDeclarationDocumentRef"] = statutory_declaration_document_ref

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "consentDocumentRef": response.get("consentDocumentRef"),
                    "consentDocumentStatus": response.get("consentDocumentStatus", "Awaiting Approval"),
                    "consentDocumentId": response.get("consentDocumentId"),
                    "supportingDocumentRef": response.get("supportingDocumentRef"),
                    "supportingDocumentId": response.get("supportingDocumentId"),
                    "statutoryDeclarationDocumentRef": response.get("statutoryDeclarationDocumentRef"),
                    "statutoryDeclarationId": response.get("statutoryDeclarationId"),
                    "processingTime": "within 1 hour during business hours",
                    "result": True,
                    "message": "Document associated with director successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error associating document to director: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_company_addresses")
class GetCompanyAddressesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get company addresses using companyUuid. Supports optional headers."""
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/addresses"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "addresses": response,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving addresses: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_company_shareholding")
class GetCompanyShareholdingAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Get company shareholding using companyUuid. Supports optional headers. Returns ETag for updates."""
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholding"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "shareholding": response,
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving shareholding information: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("update_company_shareholding")
class UpdateCompanyShareholdingAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_14: Update the shareholding in the company.
        Supports: adding/updating/deleting shareholders, share allocations, and shareholderInAllocations.
        Can increase/decrease total number of shares.
        """
        try:
            company_uuid = inputs["companyUuid"]
            etag = inputs["etag"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholding"

            # Build payload with only provided fields
            payload = {}

            # Add number of shares if provided (support both camelCase and snake_case)
            number_of_shares = get_input_value(inputs, "numberOfShares", "number_of_shares")
            if number_of_shares is not None:
                payload["numberOfShares"] = number_of_shares

            # Add share allocations if provided (support both camelCase and snake_case)
            share_allocations = inputs.get("shareAllocations") or inputs.get("share_allocations")
            if share_allocations:
                payload["shareAllocations"] = []
                for allocation in share_allocations:
                    alloc_obj = {}
                    allocation_id = allocation.get("allocationId") or allocation.get("allocation_id")
                    if allocation_id:
                        alloc_obj["allocationId"] = allocation_id
                    allocation_seq_num = allocation.get("allocationSeqNum") or allocation.get("allocation_seq_num")
                    if allocation_seq_num:
                        alloc_obj["allocationSeqNum"] = allocation_seq_num
                    num_shares = allocation.get("numSharesInAllocation") if "numSharesInAllocation" in allocation else allocation.get("num_shares_in_allocation")
                    if num_shares is not None:
                        alloc_obj["numSharesInAllocation"] = num_shares
                    # Note: shareClassName is NOT supported by the API's ShareAllocation schema
                    # ShareAllocation only supports: allocationId, allocationSeqNum, numSharesInAllocation
                    payload["shareAllocations"].append(alloc_obj)

            # Add shareholders if provided (support both camelCase and snake_case)
            shareholders = inputs.get("shareholders")
            if shareholders:
                payload["shareholders"] = []
                for shareholder in shareholders:
                    sh_obj = {}

                    # Support both camelCase (schema) and snake_case (backward compatibility)
                    shareholder_id = shareholder.get("shareholderId") or shareholder.get("shareholder_id")
                    if shareholder_id:
                        sh_obj["shareholderId"] = shareholder_id

                    shareholder_seq_num = shareholder.get("shareholderSeqNum") or shareholder.get("shareholder_seq_num")
                    if shareholder_seq_num:
                        sh_obj["shareholderSeqNum"] = shareholder_seq_num

                    shareholder_type = shareholder.get("shareholderType") or shareholder.get("shareholder_type")
                    if shareholder_type:
                        sh_obj["shareholderType"] = shareholder_type

                    # appointmentDate is readonly and must NOT be present in update requests
                    # Only include it when ADDING new shareholders (no shareholder_id present)
                    if not shareholder_id:
                        appointment_date = shareholder.get("appointmentDate") or shareholder.get("appointment_date")
                        if appointment_date:
                            sh_obj["appointmentDate"] = appointment_date

                    vacation_date = shareholder.get("vacationDate") or shareholder.get("vacation_date")
                    if vacation_date:
                        sh_obj["vacationDate"] = vacation_date

                    ird_number = shareholder.get("irdNumber") or shareholder.get("ird_number")
                    if ird_number:
                        sh_obj["irdNumber"] = ird_number

                    # Transform contacts object to ensure all keys are camelCase
                    if "contacts" in shareholder:
                        contacts = shareholder["contacts"]
                        sh_obj["contacts"] = {}

                        # Handle phone contacts
                        phone_contacts = contacts.get("phoneContacts") or contacts.get("phone_contacts")
                        if phone_contacts:
                            sh_obj["contacts"]["phoneContacts"] = []
                            for phone in phone_contacts:
                                phone_obj = {
                                    "phoneNumber": phone.get("phoneNumber") or phone.get("phone_number"),
                                    "areaCode": phone.get("areaCode") or phone.get("area_code"),
                                    "countryCode": phone.get("countryCode") or phone.get("country_code"),
                                    "phonePurpose": phone.get("phonePurpose") or phone.get("phone_purpose")
                                }
                                # Remove None values
                                sh_obj["contacts"]["phoneContacts"].append({k: v for k, v in phone_obj.items() if v is not None})

                        # Handle email addresses
                        email_addresses = contacts.get("emailAddresses") or contacts.get("email_addresses")
                        if email_addresses:
                            sh_obj["contacts"]["emailAddresses"] = []
                            for email in email_addresses:
                                email_obj = {
                                    "emailAddress": email.get("emailAddress") or email.get("email_address"),
                                    "emailPurpose": email.get("emailPurpose") or email.get("email_purpose", "Email")
                                }
                                # Remove None values
                                sh_obj["contacts"]["emailAddresses"].append({k: v for k, v in email_obj.items() if v is not None})

                        # Handle physical or postal addresses
                        addresses = contacts.get("physicalOrPostalAddresses") or contacts.get("physical_or_postal_addresses")
                        if addresses:
                            sh_obj["contacts"]["physicalOrPostalAddresses"] = []
                            for addr in addresses:
                                addr_obj = {
                                    "addressType": addr.get("addressType") or addr.get("address_type"),
                                    "addressPurpose": addr.get("addressPurpose") or addr.get("address_purpose"),
                                    "careOf": addr.get("careOf") or addr.get("care_of"),
                                    "address1": addr.get("address1"),
                                    "address2": addr.get("address2"),
                                    "address3": addr.get("address3"),
                                    "address4": addr.get("address4"),
                                    "postCode": addr.get("postCode") or addr.get("post_code"),
                                    "countryCode": addr.get("countryCode") or addr.get("country_code"),
                                    "dpid": addr.get("dpid"),
                                    "effectiveDate": addr.get("effectiveDate") or addr.get("effective_date")
                                }
                                # Remove None values
                                sh_obj["contacts"]["physicalOrPostalAddresses"].append({k: v for k, v in addr_obj.items() if v is not None})

                    # Add person shareholder details (support both camelCase and snake_case)
                    person_shareholder = shareholder.get("personShareholder") or shareholder.get("person_shareholder")
                    if person_shareholder:
                        sh_obj["personShareholder"] = {}

                        # Add name structure
                        if "name" in person_shareholder:
                            name = person_shareholder["name"]
                            sh_obj["personShareholder"]["name"] = {}
                            first_name = name.get("firstName") or name.get("first_name")
                            if first_name:
                                sh_obj["personShareholder"]["name"]["firstName"] = first_name
                            middle_names = name.get("middleNames") or name.get("middle_names")
                            if middle_names:
                                sh_obj["personShareholder"]["name"]["middleNames"] = middle_names
                            last_name = name.get("lastName") or name.get("last_name")
                            if last_name:
                                sh_obj["personShareholder"]["name"]["lastName"] = last_name

                        # Add birth info structure
                        birth_info = person_shareholder.get("birthInfo") or person_shareholder.get("birth_info")
                        if birth_info:
                            sh_obj["personShareholder"]["birthInfo"] = {}
                            date_of_birth = birth_info.get("dateOfBirth") or birth_info.get("date_of_birth")
                            if date_of_birth:
                                sh_obj["personShareholder"]["birthInfo"]["dateOfBirth"] = date_of_birth
                            country_of_birth = birth_info.get("countryOfBirth") or birth_info.get("country_of_birth")
                            if country_of_birth:
                                sh_obj["personShareholder"]["birthInfo"]["countryOfBirth"] = country_of_birth
                            town_city_of_birth = birth_info.get("townCityOfBirth") or birth_info.get("town_city_of_birth")
                            if town_city_of_birth:
                                sh_obj["personShareholder"]["birthInfo"]["townCityOfBirth"] = town_city_of_birth

                    # Add organisation shareholder details (support both camelCase and snake_case)
                    organisation_shareholder = shareholder.get("organisationShareholder") or shareholder.get("organisation_shareholder")
                    if organisation_shareholder:
                        sh_obj["organisationShareholder"] = {}
                        if "nzbn" in organisation_shareholder:
                            sh_obj["organisationShareholder"]["nzbn"] = organisation_shareholder["nzbn"]
                        if "name" in organisation_shareholder:
                            sh_obj["organisationShareholder"]["name"] = organisation_shareholder["name"]
                        registration_number = organisation_shareholder.get("registrationNumber") or organisation_shareholder.get("registration_number")
                        if registration_number:
                            sh_obj["organisationShareholder"]["registrationNumber"] = registration_number
                        entity_type = organisation_shareholder.get("entityType") or organisation_shareholder.get("entity_type")
                        if entity_type:
                            sh_obj["organisationShareholder"]["entityType"] = entity_type
                        country_of_origin = organisation_shareholder.get("countryOfOrigin") or organisation_shareholder.get("country_of_origin")
                        if country_of_origin:
                            sh_obj["organisationShareholder"]["countryOfOrigin"] = country_of_origin

                    payload["shareholders"].append(sh_obj)

            # Add shareholders in allocations if provided (support both camelCase and snake_case)
            shareholders_in_allocations = inputs.get("shareholdersInAllocations") or inputs.get("shareholders_in_allocations")
            if shareholders_in_allocations:
                payload["shareholdersInAllocations"] = []
                for mapping in shareholders_in_allocations:
                    map_obj = {}
                    shareholder_id = mapping.get("shareholderId") or mapping.get("shareholder_id")
                    if shareholder_id:
                        map_obj["shareholderId"] = shareholder_id
                    shareholder_seq_num_ref = mapping.get("shareholderSeqNumRef") or mapping.get("shareholder_seq_num_ref")
                    if shareholder_seq_num_ref:
                        map_obj["shareholderSeqNumRef"] = shareholder_seq_num_ref
                    allocation_id = mapping.get("allocationId") or mapping.get("allocation_id")
                    if allocation_id:
                        map_obj["allocationId"] = allocation_id
                    allocation_seq_num_ref = mapping.get("allocationSeqNumRef") or mapping.get("allocation_seq_num_ref")
                    if allocation_seq_num_ref:
                        map_obj["allocationSeqNumRef"] = allocation_seq_num_ref
                    payload["shareholdersInAllocations"].append(map_obj)

            # Add number of shares change info if provided (support both camelCase and snake_case)
            change_info = inputs.get("numberOfSharesChangeInfo") or inputs.get("number_of_shares_change_info")
            if change_info:
                payload["numberOfSharesChangeInfo"] = {}

                change_type = change_info.get("changeType") or change_info.get("change_type")
                if change_type:
                    payload["numberOfSharesChangeInfo"]["changeType"] = change_type

                date_of_event = change_info.get("dateOfShareChangeEvent") or change_info.get("date_of_share_change_event")
                if date_of_event:
                    payload["numberOfSharesChangeInfo"]["dateOfShareChangeEvent"] = date_of_event

                change_in_shares = change_info.get("changeInNumberOfShares") if "changeInNumberOfShares" in change_info else change_info.get("change_in_number_of_shares")
                if change_in_shares is not None:
                    payload["numberOfSharesChangeInfo"]["changeInNumberOfShares"] = change_in_shares

                increase_specific = change_info.get("increaseSpecific") or change_info.get("increase_specific")
                if increase_specific:
                    payload["numberOfSharesChangeInfo"]["increaseSpecific"] = {}
                    directors_cert = increase_specific.get("directorsCertificateDocumentRef") or increase_specific.get("directors_certificate_document_ref")
                    if directors_cert:
                        payload["numberOfSharesChangeInfo"]["increaseSpecific"]["directorsCertificateDocumentRef"] = directors_cert
                    date_of_approval = increase_specific.get("dateOfApproval") or increase_specific.get("date_of_approval")
                    if date_of_approval:
                        payload["numberOfSharesChangeInfo"]["increaseSpecific"]["dateOfApproval"] = date_of_approval
                    terms_of_approval = increase_specific.get("termsOfApproval") or increase_specific.get("terms_of_approval")
                    if terms_of_approval:
                        payload["numberOfSharesChangeInfo"]["increaseSpecific"]["termsOfApproval"] = terms_of_approval

                decrease_specific = change_info.get("decreaseSpecific") or change_info.get("decrease_specific")
                if decrease_specific:
                    payload["numberOfSharesChangeInfo"]["decreaseSpecific"] = {}
                    is_treasury = decrease_specific.get("isTreasuryStock") or decrease_specific.get("is_treasury_stock")
                    if is_treasury is not None:
                        payload["numberOfSharesChangeInfo"]["decreaseSpecific"]["isTreasuryStock"] = is_treasury

            # Build optional headers including If-Match for concurrency control
            optional_headers = {
                "If-Match": etag
            }
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="PUT",
                headers=headers,
                payload=payload
            )

            # Extract ETag from response headers
            new_etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "shareholding": response,
                    "etag": new_etag,
                    "result": True,
                    "message": "Shareholding updated successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error updating shareholding: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("update_company_details")
class UpdateCompanyDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_15: Update details of the company with the given company identifier.
        Allows updating website, contacts, annual return filing month, and ultimate holding company.
        Returns updated company details with ETag in response headers.
        """
        try:
            company_uuid = inputs["companyUuid"]
            etag = inputs["etag"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}"

            # Build payload with only provided fields
            payload = {}

            if "website" in inputs:
                payload["website"] = inputs["website"]

            if "contacts" in inputs:
                payload["contacts"] = inputs["contacts"]

            # Support both camelCase (schema) and snake_case (backward compatibility)
            annual_return = get_input_value(inputs, "annualReturnFilingMonth", "annual_return_filing_month")
            if annual_return is not None:
                payload["annualReturnFilingMonth"] = annual_return

            ultimate_holding = get_input_value(inputs, "ultimateHoldingCompany", "ultimate_holding_company")
            if ultimate_holding is not None:
                payload["ultimateHoldingCompany"] = ultimate_holding

            # Build optional headers including If-Match for concurrency control
            optional_headers = {
                "If-Match": etag
            }
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="PUT",
                headers=headers,
                payload=payload
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "companyUuid": response.get("companyUuid"),
                    "companyName": response.get("companyName"),
                    "entityType": response.get("entityType"),
                    "website": response.get("website"),
                    "contacts": response.get("contacts"),
                    "annualReturnFilingMonth": response.get("annualReturnFilingMonth"),
                    "ultimateHoldingCompany": response.get("ultimateHoldingCompany"),
                    "etag": etag,
                    "result": True,
                    "message": f"Company details updated successfully for {response.get('companyName')}"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error updating company details: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("add_company_contact")
class AddCompanyContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_19: Adds a new contact to the company with the given company identifier.
        Only one contact can be added at a time.
        Supports phone contacts, email addresses, and physical/postal addresses.
        """
        try:
            company_uuid = inputs["companyUuid"]
            contact_type = inputs["contactType"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/contacts"

            # Build payload based on contact type
            payload = {}

            # Try both camelCase (schema) and snake_case (backward compatibility) for contact object keys
            phone_contact = inputs.get("phoneContact") or inputs.get("phone_contact")
            email_address_obj = inputs.get("emailAddress") or inputs.get("email_address")
            address_obj = inputs.get("physicalOrPostalAddress") or inputs.get("physical_or_postal_address")

            if contact_type == "phone" and phone_contact:
                phone = phone_contact
                # Try camelCase first (schema), then snake_case (backward compatibility)
                payload["phoneContact"] = {
                    "phoneNumber": phone.get("phoneNumber") or phone.get("phone_number"),
                    "areaCode": phone.get("areaCode") or phone.get("area_code"),
                    "countryCode": phone.get("countryCode") or phone.get("country_code"),
                    "phonePurpose": phone.get("phonePurpose") or phone.get("phone_purpose")
                }
                # Remove None values
                payload["phoneContact"] = {k: v for k, v in payload["phoneContact"].items() if v is not None}

            elif contact_type == "email" and email_address_obj:
                email = email_address_obj
                # Try camelCase first (schema), then snake_case (backward compatibility)
                payload["emailAddress"] = {
                    "emailAddress": email.get("email") or email.get("emailAddress"),
                    "emailPurpose": email.get("emailPurpose") or email.get("email_purpose", "Email")
                }
                # Remove None values
                payload["emailAddress"] = {k: v for k, v in payload["emailAddress"].items() if v is not None}

            elif contact_type == "address" and address_obj:
                address = address_obj

                # Try camelCase first (schema), then snake_case (backward compatibility)
                # Validate NZ address requirements: Either dpid OR (address1 + address3)
                has_dpid = address.get("dpid")
                has_address1 = address.get("address1")
                has_address3 = address.get("address3")

                if not has_dpid and not (has_address1 and has_address3):
                    raise ValueError(
                        "For NZ addresses, you must provide either: (1) dpid, OR (2) address1 + address3. "
                        f"Received: dpid={has_dpid}, address1={has_address1}, address3={has_address3}"
                    )

                # Build payload with camelCase keys (for API), reading from either camelCase or snake_case input
                payload["physicalOrPostalAddress"] = {
                    "addressType": address.get("addressType") or address.get("address_type"),
                    "addressPurpose": address.get("addressPurpose") or address.get("address_purpose"),
                    "careOf": address.get("careOf") or address.get("care_of"),
                    "address1": address.get("address1"),
                    "address2": address.get("address2"),
                    "address3": address.get("address3"),
                    "address4": address.get("address4"),
                    "postCode": address.get("postCode") or address.get("post_code"),
                    "countryCode": address.get("countryCode") or address.get("country_code"),
                    "description": address.get("description"),
                    "dpid": address.get("dpid"),
                    "effectiveDate": address.get("effectiveDate") or address.get("effective_date")
                }
                # Remove None values
                payload["physicalOrPostalAddress"] = {k: v for k, v in payload["physicalOrPostalAddress"].items() if v is not None}

            else:
                raise ValueError(f"Invalid contact_type '{contact_type}' or missing contact data")

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Make the POST request
            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            # Map response to output format
            result_data = {
                "phoneContact": response.get("phoneContact"),
                "emailAddress": response.get("emailAddress"),
                "physicalOrPostalAddress": response.get("physicalOrPostalAddress"),
                "result": True,
                "message": "Contact added successfully to company"
            }

            return ActionResult(
                data=result_data,
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error adding company contact: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("create_company")
class CreateCompanyAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_26: Create a new company with proposed name and entity type.
        Only these 2 fields are required. Returns shell company with status 0 (Initialised).
        If name is not available or invalid, this call will error.
        """
        try:
            company_name = inputs["companyName"]
            entity_type = inputs["entityType"]

            url = f"{BASE_URL_V2}/"

            payload = {
                "companyName": company_name,
                "entityType": entity_type
            }

            # Build headers with subscription key
            headers = get_api_headers(context)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="POST",
                headers=headers,
                payload=payload
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "companyUuid": response.get("companyUuid"),
                    "companyName": response.get("companyName"),
                    "entityType": response.get("entityType"),
                    "nzbn": response.get("nzbn"),
                    "companyStatusCode": response.get("companyStatusCode"),
                    "companyStatusDescription": response.get("companyStatusDescription"),
                    "companyStatusExpiryDate": response.get("companyStatusExpiryDate"),
                    "annualReturnFilingMonth": response.get("annualReturnFilingMonth"),
                    "link": response.get("link"),
                    "etag": etag,
                    "result": True,
                    "message": f"Company created with UUID: {response.get('companyUuid')}. Status: {response.get('companyStatusDescription')}"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error creating company: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("reserve_company_name")
class ReserveCompanyNameAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_27: Reserve the name for a company created via create_company.

        IMPORTANT: This is the second step after initialization (create_company).
        The ETag from initialization must be included in:
        1. Request body as companyDetailsConfirmedCorrectAsOfETag
        2. Request header as If-Match (for concurrency control)

        Endpoint: POST to /{companyUuid}/reserve-name
        Processed within 2 hours during business hours (8:30am-5pm Mon-Fri).

        For sandbox testing:
        - Use organisationId: "137860"
        - Payment info is required: defaults to creditCard with API portal redirect
        - redirectURL is automatically base64 encoded (per API requirement)
        - In sandbox, use test card: 4111 1111 1111 1111 (any expiry/CVC)
        """
        try:
            company_uuid = inputs["companyUuid"]
            etag = inputs["etag"]
            organisation_id = inputs.get("organisationId")
            organisation_name = inputs.get("organisationName")
            # Payment info - read from inputs (defaults applied later)
            payment_method = inputs.get("paymentMethod")
            redirect_url = inputs.get("redirectUrl")
            billing_reference = inputs.get("billingReference")
            comments = inputs.get("comments")
            supporting_document_ref = inputs.get("supportingDocumentRef")

            # Endpoint: POST to /{companyUuid}/reserve-name (per documentation)
            # Note: API team's example showed /{companyUuid} but that returns 404
            url = f"{BASE_URL_V2}/{company_uuid}/reserve-name"

            # Build payload as per API documentation
            payload = {
                "companyDetailsConfirmedCorrectAsOfETag": etag
            }

            # Add optional organisation (nested in reserveForOrganisation object)
            # This determines whether authority is held by org account or user account
            # For sandbox: use organisationId "137860"
            if organisation_id:
                payload["reserveForOrganisation"] = {
                    "name": organisation_name or "TESTING LTD",
                    "organisationId": organisation_id
                }

            # Build payment info object with camelCase values: "directDebit" or "creditCard"
            # IMPORTANT: Sandbox API requires paymentInfo to avoid "Direct Debit not enabled" error
            # Even though sandbox won't charge, the API needs payment method specified
            # Default to creditCard if not provided
            payment_info = {}

            # Use provided payment_method or default to CREDIT_CARD
            if not payment_method:
                payment_method = "CREDIT_CARD"

            # Use provided redirect_url or default to API portal for sandbox
            if not redirect_url:
                redirect_url = "https://portal.api.business.govt.nz/"

            if payment_method in ["CREDIT_CARD", "credit_card", "creditCard"]:
                payment_info["paymentMethod"] = "creditCard"  # camelCase!
                # IMPORTANT: redirectURL must be base64 encoded (per API team)
                redirect_url_bytes = redirect_url.encode('utf-8')
                redirect_url_base64 = base64.b64encode(redirect_url_bytes).decode('utf-8')
                payment_info["redirectURL"] = redirect_url_base64
            elif payment_method in ["DIRECT_DEBIT", "direct_debit", "directDebit"]:
                payment_info["paymentMethod"] = "directDebit"  # camelCase!
                # Direct Debit doesn't need redirectURL
            else:
                # Unknown payment method - pass through
                payment_info["paymentMethod"] = payment_method
                if redirect_url:
                    # Also base64 encode for custom payment methods
                    redirect_url_bytes = redirect_url.encode('utf-8')
                    redirect_url_base64 = base64.b64encode(redirect_url_bytes).decode('utf-8')
                    payment_info["redirectURL"] = redirect_url_base64

            if billing_reference:
                payment_info["billingReference"] = billing_reference

            # Always add paymentInfo to payload (required even in sandbox)
            payload["paymentInfo"] = payment_info

            # Add optional fields
            if comments:
                payload["comments"] = comments
            if supporting_document_ref:
                payload["supportingDocumentRef"] = supporting_document_ref

            # Build headers with subscription key AND If-Match header for concurrency control
            optional_headers = {
                "If-Match": etag
            }
            headers = get_api_headers(context, optional_headers)

            # Use context.fetch with json parameter (not fetch_with_headers)
            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "reservationId": response.get("reservationId") or response.get("nameReservationId"),
                    "paymentUrl": response.get("paymentURL") or response.get("paymentUrl"),
                    "paymentId": response.get("paymentId"),
                    "billingReference": response.get("billingReference"),
                    "status": response.get("status"),
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Check for specific payment errors
            if "Direct Debit not enabled" in error_str:
                return ActionResult(
                    data={
                        "success": False,
                        "message": "Direct Debit is not enabled for this account. Please use CREDIT_CARD payment method with a redirect_url, or enable Direct Debit in your Companies Register account.",
                        "error": error_str
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error reserving company name: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("incorporate_company")
class IncorporateCompanyAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            reservation_id = inputs["reservationId"]
            company_name = inputs["companyName"]
            company_type = inputs.get("companyType", "limited")
            registered_office = inputs["registeredOffice"]
            address_for_service = inputs["addressForService"]
            directors = inputs["directors"]
            shareholders = inputs["shareholders"]
            share_allocation = inputs.get("shareAllocation", {})
            constitution = inputs.get("constitution")
            payment_method = inputs.get("paymentMethod", "credit_card")
            redirect_url = inputs.get("redirectUrl")

            url = f"{BASE_URL}/companies"

            payload = {
                "reservationId": reservation_id,
                "companyName": company_name,
                "companyType": company_type,
                "registeredOffice": registered_office,
                "addressForService": address_for_service,
                "directors": directors,
                "shareholders": shareholders,
                "shareAllocation": share_allocation
            }

            # Add optional constitution
            if constitution:
                payload["constitution"] = constitution

            # Add payment parameters
            if payment_method:
                payload["paymentMethod"] = payment_method
            if redirect_url:
                payload["redirectURL"] = redirect_url

            # Build headers with subscription key
            headers = get_api_headers(context)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            # Extract incorporation details from response
            company_number = response.get("companyNumber") or response.get("number")
            incorporation_date = response.get("incorporationDate") or response.get("registeredDate")
            payment_url = response.get("paymentURL") or response.get("paymentUrl")

            return ActionResult(
                data={
                    "companyNumber": company_number,
                    "companyName": company_name,
                    "incorporationDate": incorporation_date,
                    "paymentUrl": payment_url,
                    "result": True,
                    "message": "Company incorporation initiated. Complete payment to finalize."
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error incorporating company: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_shareholder_details")
class GetShareholderDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_46: Get details of a specific shareholder by shareholderId.
        Supports ETag optimization with If-None-Match header.
        """
        try:
            company_uuid = inputs["companyUuid"]
            shareholder_id = inputs["shareholderId"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholders/{shareholder_id}"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "shareholder": response,
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Handle 304 Not Modified
            if "304" in error_str:
                return ActionResult(
                    data={
                        "result": True,
                        "notModified": True,
                        "message": "Shareholder data not modified since last request"
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving shareholder details: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("get_shareholder_documents")
class GetShareholderDocumentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_47_GET: Retrieve document references associated with shareholder allocation.
        Returns consent and document references (e.g., consent, supporting documents).
        NOTE: supportingDocumentRef and supportingDocumentId are not returned with this resource.
        """
        try:
            company_uuid = inputs["companyUuid"]
            shareholder_allocation_id = inputs["shareholderAllocationId"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholder-allocations/{shareholder_allocation_id}/document-associations"

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            # Extract documents list from response
            documents = response.get("items", []) if isinstance(response, dict) else response

            return ActionResult(
                data={
                    "documents": documents,
                    "result": True,
                    "count": len(documents) if isinstance(documents, list) else 0
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving shareholder documents: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_shareholders_special_resolution")
class GetShareholdersSpecialResolutionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_51: Retrieve details of the Shareholders Special Resolution document associated with shareholders.
        Only applicable for pre-incorporated company.
        """
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholding/document-associations"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            return ActionResult(
                data={
                    "specialResolutionDocumentRef": response.get("specialResolutionDocumentRef"),
                    "specialResolutionDocumentId": response.get("specialResolutionDocumentId"),
                    "link": response.get("link"),
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving special resolution document associations: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("associate_shareholder_document")
class AssociateShareholderDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_47: Associate consent document and optionally supporting document to shareholder allocation.
        Documents must be uploaded first using POST /{companyUuid}/documents with document types:
        - "ConsentOfShareholder"
        - "ConsentOfShareholderSupportDocument"

        NOTE: Shareholder consents are NOT required post-registration.
        Processed within 1 hour during business hours.

        On Acceptance:
        - Email confirmation sent
        - Particulars of shareholder document added to document history
        - Certificate of Incorporation sent once last consent accepted (for incorporation)

        On Rejection:
        - Email sent with reason
        - Common rejections: poor image quality, details don't match application
        """
        try:
            company_uuid = inputs["companyUuid"]
            shareholder_allocation_id = inputs["shareholderAllocationId"]
            consent_document_ref = inputs["consentDocumentRef"]
            supporting_document_ref = inputs.get("supportingDocumentRef")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholder-allocations/{shareholder_allocation_id}/document-associations"

            # Build payload
            payload = {
                "consentDocumentRef": consent_document_ref
            }

            if supporting_document_ref:
                payload["supportingDocumentRef"] = supporting_document_ref

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "consentDocumentRef": response.get("consentDocumentRef"),
                    "consentDocumentStatus": response.get("consentDocumentStatus", "Awaiting Approval"),
                    "consentDocumentId": response.get("consentDocumentId"),
                    "supportingDocumentRef": response.get("supportingDocumentRef"),
                    "supportingDocumentId": response.get("supportingDocumentId"),
                    "processingTime": "within 1 hour during business hours",
                    "result": True,
                    "message": "Document associated with shareholder successfully. Note: Shareholder consents are not required post-registration."
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error associating document to shareholder: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("associate_shareholders_special_resolution")
class AssociateShareholdersSpecialResolutionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_52: Associate the uploaded Special Resolution document to shareholders.
        Only applicable and mandatory for pre-incorporated NZ Co-operative Company.
        Document must be uploaded first using POST /{companyUuid}/documents with document type:
        - "ShareholdersSpecialResolutionDocument"

        Calling this resource a subsequent time will replace the associated Special Resolution document.
        """
        try:
            company_uuid = inputs["companyUuid"]
            special_resolution_document_ref = inputs["specialResolutionDocumentRef"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/shareholding/document-associations"

            # Build payload
            payload = {
                "specialResolutionDocumentRef": special_resolution_document_ref
            }

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "specialResolutionDocumentRef": response.get("specialResolutionDocumentRef"),
                    "specialResolutionDocumentId": response.get("specialResolutionDocumentId"),
                    "result": True,
                    "message": "Special Resolution document associated successfully. Note: Only applicable for pre-incorporated NZ Co-operative Company."
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error associating special resolution: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("upload_company_constitution")
class UploadCompanyConstitutionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_39: Upload a constitution for the company under incorporation.
        You can incorporate a company in New Zealand with or without a constitution.
        A constitution sets out the rights, powers and duties of the company, the board,
        each director and each shareholder.

        MANDATORY for Co-operative Company or Unlimited Company.
        Optional for other company types.

        NOTE: This call can be made again to replace a previously uploaded constitution.
        """
        try:
            company_uuid = inputs["companyUuid"]
            constitution_document_ref = inputs["constitutionDocumentRef"]
            declaration = inputs["declaration"]
            resolution_date = inputs.get("resolutionDate")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/constitution"

            # Build payload
            payload = {
                "constitutionDocumentRef": constitution_document_ref,
                "declaration": declaration
            }

            # Add resolution date if provided (required for registered companies)
            if resolution_date:
                payload["resolutionDate"] = resolution_date

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "constitutionDocumentRef": response.get("constitutionDocumentRef"),
                    "constitutionDocumentId": response.get("constitutionDocumentId"),
                    "declaration": response.get("declaration"),
                    "resolutionDate": response.get("resolutionDate"),
                    "link": response.get("link"),
                    "result": True,
                    "message": "Constitution uploaded successfully. Note: This call can be made again to replace the constitution."
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error uploading constitution: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("get_company_constitution")
class GetCompanyConstitutionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_40: Retrieve constitution document metadata for the company under registration.
        Returns information about the constitution that has been uploaded for the company.
        """
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/constitution"

            # Build optional headers
            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            # Use fetch_with_headers to access response headers for ETag
            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            # Extract ETag from response headers
            etag = response_headers.get("ETag")

            return ActionResult(
                data={
                    "constitutionDocumentRef": response.get("constitutionDocumentRef"),
                    "constitutionDocumentId": response.get("constitutionDocumentId"),
                    "declaration": response.get("declaration"),
                    "resolutionDate": response.get("resolutionDate"),
                    "link": response.get("link"),
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

            # Handle 304 Not Modified
            if "304" in error_str:
                return ActionResult(
                    data={
                        "result": True,
                        "notModified": True,
                        "message": "Constitution data not modified since last request"
                    },
                    cost_usd=None
                )

            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving constitution: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("search_nz_address")
class SearchNZAddressAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_30: NZ Post address search by query string or Delivery Point Identifier (DPID).

        Performs an NZ Post address file search. The search results are by default filtered
        on physical addresses. Postal addresses (e.g., PO Boxes) can be searched by specifying
        postal=true.

        Note: Specification of a DPID overrides any other query parameter.

        Query String Search Process:
        1. Input data is split on whitespace and commas into individual tokens
           (e.g., "23 Wellington road" → tokens: 23, Wellington, road)
        2. All tokens are treated equally and matched against the full address
        3. Tokens are position-independent
        """
        try:
            dpid = inputs.get("dpid")
            find = inputs.get("find")
            limit = inputs.get("limit", 10)
            postal = inputs.get("postal", False)
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/addresses"

            # Build query parameters
            params = {}

            # DPID overrides all other parameters
            if dpid:
                params["dpid"] = dpid
            elif find:
                params["find"] = find

            # Add limit (1-100)
            if limit:
                # Validate limit range
                if limit < 1 or limit > 100:
                    raise ValueError("limit must be between 1 and 100")
                params["limit"] = limit

            # Add postal filter
            if postal:
                params["postal"] = "true"

            # Build optional headers
            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            # Build headers with subscription key
            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                params=params,
                headers=headers
            )

            # Extract addresses from response
            addresses = response.get("items", []) if isinstance(response, dict) else response

            return ActionResult(
                data={
                    "addresses": addresses,
                    "count": len(addresses) if isinstance(addresses, list) else 0,
                    "searchType": "dpid" if dpid else "query",
                    "postalOnly": postal,
                    "result": True
                },
                cost_usd=None
            )

        except ValueError as ve:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Validation error: {str(ve)}",
                    "error": str(ve)
                },
                cost_usd=None
            )
        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error searching NZ addresses: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("file_annual_return")
class FileAnnualReturnAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            company_number = inputs["companyNumber"]
            return_date = inputs["returnDate"]
            total_shares = inputs.get("totalShares")
            share_details = inputs.get("shareDetails", {})
            directors_confirmed = inputs.get("directorsConfirmed", True)
            addresses_confirmed = inputs.get("addressesConfirmed", True)
            shareholding_confirmed = inputs.get("shareholdingConfirmed", True)
            payment_method = inputs.get("paymentMethod", "credit_card")
            redirect_url = inputs.get("redirectUrl")

            url = f"{BASE_URL}/companies/{company_number}/annual-returns"

            payload = {
                "returnDate": return_date,
                "confirmations": {
                    "directors": directors_confirmed,
                    "addresses": addresses_confirmed,
                    "shareholding": shareholding_confirmed
                }
            }

            # Add share information if provided
            if total_shares:
                payload["totalShares"] = total_shares
            if share_details:
                payload["shareDetails"] = share_details

            # Add payment parameters
            if payment_method:
                payload["paymentMethod"] = payment_method
            if redirect_url:
                payload["redirectURL"] = redirect_url

            # Build headers with subscription key
            headers = get_api_headers(context)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            # Extract filing details from response
            filing_id = response.get("filingId") or response.get("id")
            status = response.get("status")
            payment_url = response.get("paymentURL") or response.get("paymentUrl")

            return ActionResult(
                data={
                    "filingId": filing_id,
                    "companyNumber": company_number,
                    "returnDate": return_date,
                    "paymentUrl": payment_url,
                    "status": status,
                    "result": True,
                    "message": "Annual return filing initiated. Complete payment to finalize."
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error filing annual return: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )



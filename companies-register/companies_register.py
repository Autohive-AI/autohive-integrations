from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any
import aiohttp
import json
import base64
import os

# Create the integration using the config.json
companies_register = Integration.load()

# =============================================================================
# ENVIRONMENT CONFIGURATION
# SANDBOX:    https://api.business.govt.nz/sandbox/{{resource path}}
# PRODUCTION: https://api.business.govt.nz/gateway/{{resource path}}
# =============================================================================

# BASE_URL_V2 = "https://api.business.govt.nz/sandbox/companies-office/companies-register/companies/v2"
BASE_URL_V2 = "https://api.business.govt.nz/gateway/companies-office/companies-register/companies/v2"

# Azure API Management Subscription Key (injected server-side at deployment)
SUBSCRIPTION_KEY = os.environ.get("COMPANIES_REGISTER_SUBSCRIPTION_KEY", "")


# ---- Helper Functions ----

def get_api_headers(context: ExecutionContext, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
    """Build headers for API requests."""
    headers = {}

    if SUBSCRIPTION_KEY:
        headers["Ocp-Apim-Subscription-Key"] = SUBSCRIPTION_KEY

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
                             params: Dict[str, Any] = None, payload: Dict[str, Any] = None) -> tuple:
    """
    Make an HTTP request using aiohttp and return both the response body and headers.
    Needed because context.fetch() doesn't expose response headers (required for ETag).
    """
    async with aiohttp.ClientSession() as session:
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
            etag = response.headers.get('ETag')

            response_headers = {}
            for key, value in response.headers.items():
                response_headers[key] = value
            if etag:
                response_headers['ETag'] = etag

            if response.status == 304:
                return None, response_headers

            if not response.ok:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text}")

            try:
                response_body = await response.json()
            except (ValueError, aiohttp.ContentTypeError):
                response_body = await response.text()

            return response_body, response_headers


# ---- Action Handlers ----

@companies_register.action("get_company_details")
class GetCompanyDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_03: Get company details.
        For registered companies (status 50), use NZBN as the identifier.
        For pre-incorporated companies, use the UUID.
        Returns ETag in response — store this for filing annual returns or updating contacts.
        """
        try:
            company_uuid = inputs["companyUuid"]
            if_none_match = inputs.get("ifNoneMatch")
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}"

            optional_headers = {}
            if if_none_match:
                optional_headers["If-None-Match"] = if_none_match
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            etag = response_headers.get("ETag")

            if response is None:
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
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)

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


@companies_register.action("get_company_contacts")
class GetCompanyContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Get all contacts for a company (addresses, phone, email).
        Contacts are embedded in the company GET response — this action calls
        GET /{companyUuid} and extracts the contacts field.
        For registered companies (status 50), use NZBN as companyUuid.
        Returns addressId/phoneContactId/emailAddressId values needed to update contacts.
        """
        try:
            company_uuid = inputs["companyUuid"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}"

            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response, response_headers = await fetch_with_headers(
                url=url,
                method="GET",
                headers=headers
            )

            etag = response_headers.get("ETag")
            raw_contacts = response.get("contacts") if isinstance(response, dict) else None
            contacts = raw_contacts if isinstance(raw_contacts, dict) else {}

            return ActionResult(
                data={
                    "contacts": contacts,
                    "physicalOrPostalAddresses": contacts.get("physicalOrPostalAddresses", []),
                    "phoneContacts": contacts.get("phoneContacts", []),
                    "emailAddresses": contacts.get("emailAddresses", []),
                    "etag": etag,
                    "result": True
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error retrieving company contacts: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("update_company_contact")
class UpdateCompanyContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_21: Update an existing contact (address, phone, or email) for a company.
        For registered companies (status 50), use NZBN as companyUuid.
        Requires the contactId (addressId/phoneContactId/emailAddressId) from get_company_contacts.
        Requires etag from get_company_contacts for concurrency control.

        To update an address:
        1. Call get_company_contacts to get the contactId and etag
        2. Call this action with address lines (NOT dpid) and a future effectiveDate
        NOTE: Do NOT include dpid in address updates — use address lines only.
        effectiveDate is required for all address updates.
        """
        try:
            company_uuid = inputs["companyUuid"]
            contact_id = inputs["contactId"]
            etag = inputs["etag"]
            contact_type = inputs["contactType"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/contacts/{contact_id}"

            # Build payload based on contact type
            payload = {}

            if contact_type == "address":
                address = inputs.get("physicalOrPostalAddress", {})

                # Validate: address1 + address3 required (do NOT use dpid for updates)
                if not address.get("address1") or not address.get("address3"):
                    raise ValueError(
                        "address1 and address3 are required for address updates. "
                        "Do not use dpid — provide address lines directly."
                    )

                if not address.get("effectiveDate"):
                    raise ValueError(
                        "effectiveDate is required for all address updates. "
                        "Use a future date in ISO 8601 format e.g. '2026-03-05T00:00:00Z'."
                    )

                # Build payload with address lines only — exclude dpid
                addr_payload = {}
                for field in ["addressId", "addressType", "addressPurpose", "careOf",
                              "address1", "address2", "address3", "address4",
                              "postCode", "countryCode", "description", "effectiveDate"]:
                    if address.get(field) is not None:
                        addr_payload[field] = address[field]

                payload["physicalOrPostalAddress"] = addr_payload

            elif contact_type == "phone":
                phone = inputs.get("phoneContact", {})
                phone_payload = {}
                for field in ["phoneContactId", "phoneNumber", "areaCode", "countryCode", "phonePurpose"]:
                    if phone.get(field) is not None:
                        phone_payload[field] = phone[field]
                payload["phoneContact"] = phone_payload

            elif contact_type == "email":
                email = inputs.get("emailAddress", {})
                email_payload = {}
                for field in ["emailAddressId", "emailAddress", "emailPurpose"]:
                    if email.get(field) is not None:
                        email_payload[field] = email[field]
                payload["emailAddress"] = email_payload

            else:
                raise ValueError(f"Invalid contactType '{contact_type}'. Use: address, phone, or email")

            optional_headers = {
                "If-Match": etag
            }
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response, response_headers = await fetch_with_headers(
                url=url,
                method="PUT",
                headers=headers,
                payload=payload
            )

            new_etag = response_headers.get("ETag")

            # API returns empty string body on some successful updates (phone/email)
            contact = response if isinstance(response, dict) else None

            return ActionResult(
                data={
                    "contact": contact,
                    "etag": new_etag,
                    "result": True,
                    "message": "Contact updated successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error updating company contact: {str(e)}",
                    "error": str(e)
                },
                cost_usd=None
            )


@companies_register.action("add_company_contact")
class AddCompanyContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_19: Add a new contact to the company.
        For registered companies (status 50), use NZBN as companyUuid.
        Only one contact can be added at a time.
        Required address purposes: Registered Office Address, Address for Service, Address for Communication.
        Use search_nz_address first to get a valid dpid for NZ addresses.
        """
        try:
            company_uuid = inputs["companyUuid"]
            contact_type = inputs["contactType"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/contacts"

            payload = {}

            if contact_type == "address":
                address = inputs.get("physicalOrPostalAddress", {})

                has_dpid = address.get("dpid")
                has_address1 = address.get("address1")
                has_address3 = address.get("address3")

                if not has_dpid and not (has_address1 and has_address3):
                    raise ValueError(
                        "For NZ addresses provide either: dpid, OR address1 + address3. "
                        f"Got: dpid={has_dpid}, address1={has_address1}, address3={has_address3}"
                    )

                addr_payload = {}
                for field in ["addressType", "addressPurpose", "dpid", "careOf",
                              "address1", "address2", "address3", "address4",
                              "postCode", "countryCode", "description", "effectiveDate"]:
                    if address.get(field) is not None:
                        addr_payload[field] = address[field]

                payload["physicalOrPostalAddress"] = addr_payload

            elif contact_type == "phone":
                phone = inputs.get("phoneContact", {})
                phone_payload = {}
                for field in ["phoneNumber", "areaCode", "countryCode", "phonePurpose"]:
                    if phone.get(field) is not None:
                        phone_payload[field] = phone[field]
                payload["phoneContact"] = phone_payload

            elif contact_type == "email":
                email = inputs.get("emailAddress", {})
                payload["emailAddress"] = {
                    "emailAddress": email.get("emailAddress"),
                    "emailPurpose": email.get("emailPurpose", "Email")
                }

            else:
                raise ValueError(f"Invalid contactType '{contact_type}'. Use: address, phone, or email")

            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            return ActionResult(
                data={
                    "contact": response,
                    "result": True,
                    "message": "Contact added successfully"
                },
                cost_usd=None
            )

        except Exception as e:
            error_str = str(e)
            if "ERR_CANNOT_BE_ADDED" in error_str or "already present" in error_str:
                return ActionResult(
                    data={
                        "success": False,
                        "alreadyExists": True,
                        "message": (
                            "This contact already exists and cannot be added again. "
                            "To change an existing address, use update_company_contact instead. "
                            "Call get_company_contacts first to get the addressId and etag, "
                            "then call update_company_contact with that contactId and etag."
                        ),
                        "error": error_str
                    },
                    cost_usd=None
                )
            return ActionResult(
                data={
                    "success": False,
                    "message": f"Error adding company contact: {error_str}",
                    "error": error_str
                },
                cost_usd=None
            )


@companies_register.action("search_nz_address")
class SearchNZAddressAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        COMP_30: NZ Post address lookup by query string or DPID.
        Use this before add_company_contact or update_company_contact to get the dpid
        for a valid NZ address. DPID overrides all other query parameters.
        """
        try:
            dpid = inputs.get("dpid")
            find = inputs.get("find")
            limit = inputs.get("limit", 10)
            postal = inputs.get("postal", False)
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/addresses"

            params = {}
            if dpid:
                params["dpid"] = dpid
            elif find:
                params["find"] = find

            if limit:
                if limit < 1 or limit > 100:
                    raise ValueError("limit must be between 1 and 100")
                params["limit"] = limit

            if postal:
                params["postal"] = "true"

            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="GET",
                params=params,
                headers=headers
            )

            addresses = response.get("items", []) if isinstance(response, dict) else response

            return ActionResult(
                data={
                    "addresses": addresses,
                    "count": len(addresses) if isinstance(addresses, list) else 0,
                    "searchType": "dpid" if dpid else "query",
                    "result": True
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
        """
        COMP_23: File an annual return for a registered company.
        Use NZBN as companyUuid for registered companies (status 50).
        Requires the ETag from a recent get_company_details call — this confirms
        you have reviewed and confirmed the company details are correct.
        Phone contact must be Mobile type (used for next year's SMS reminders).
        Payment: directDebit (default) or creditCard (requires redirectUrl).
        """
        try:
            company_uuid = inputs["companyUuid"]
            declaration = inputs["declaration"]
            name = inputs["name"]
            email_address = inputs["emailAddress"]
            designation = inputs["designation"]
            etag = inputs["companyDetailsConfirmedCorrectAsOfETag"]
            request_id = inputs.get("requestId")

            url = f"{BASE_URL_V2}/{company_uuid}/annual-returns"

            payload = {
                "declaration": declaration,
                "name": name,
                "emailAddress": email_address,
                "designation": designation,
                "companyDetailsConfirmedCorrectAsOfETag": etag
            }

            # Optional: mobile phone for next year's SMS reminders
            phone_contact = inputs.get("phoneContact")
            if phone_contact:
                payload["phoneContact"] = phone_contact

            # Payment info
            payment_method = inputs.get("paymentMethod", "directDebit")
            payment_info = {"paymentMethod": payment_method}

            if inputs.get("billingReference"):
                payment_info["billingReference"] = inputs["billingReference"]

            if payment_method == "creditCard" and inputs.get("redirectUrl"):
                payment_info["redirectURL"] = base64.b64encode(
                    inputs["redirectUrl"].encode()
                ).decode()

            payload["paymentInfo"] = payment_info

            # Optional: Co-operative consent document
            if inputs.get("annualReturnConsentDocumentRef"):
                payload["annualReturnConsentDocumentRef"] = inputs["annualReturnConsentDocumentRef"]

            # Optional: Shareholder list document (required for extensive shareholding)
            if inputs.get("annualReturnShareholderListDocumentRef"):
                payload["annualReturnShareholderListDocumentRef"] = inputs["annualReturnShareholderListDocumentRef"]

            # Optional: charge to organisation account
            if inputs.get("organisationId"):
                payload["fileAnnualReturnForOrganisation"] = {
                    "organisationId": inputs["organisationId"],
                    "name": inputs.get("organisationName", "")
                }

            optional_headers = {}
            if request_id:
                optional_headers["api-business-govt-nz-Request-Id"] = request_id

            headers = get_api_headers(context, optional_headers)

            response = await context.fetch(
                url,
                method="POST",
                json=payload,
                headers=headers
            )

            is_credit_card = payment_method == "creditCard"
            payment_info_resp = response.get("paymentInfo", {}) if isinstance(response, dict) else {}

            return ActionResult(
                data={
                    "documentId": response.get("documentId") if not is_credit_card else None,
                    "documentType": response.get("documentType") if not is_credit_card else None,
                    "status": response.get("status") if not is_credit_card else None,
                    "startDate": response.get("startDate") if not is_credit_card else None,
                    "paymentUrl": payment_info_resp.get("paymentUrl") if is_credit_card else None,
                    "billingReference": payment_info_resp.get("billingReference"),
                    "paymentMethod": payment_method,
                    "result": True,
                    "message": (
                        "Annual return filed. Complete payment at the paymentUrl to finalise."
                        if is_credit_card
                        else "Annual return filed successfully via direct debit."
                    )
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

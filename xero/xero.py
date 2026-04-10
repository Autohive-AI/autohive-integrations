from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult,
    ConnectedAccountHandler, ConnectedAccountInfo
)
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import base64
import io
import os
import aiohttp

# Create the integration using the config.json
config_path = os.path.join(os.path.dirname(__file__), "config.json")
xero = Integration.load(config_path)


# ---- Connected Account Handler ----

@xero.connected_account()
class XeroConnectedAccountHandler(ConnectedAccountHandler):
    """
    Handler for fetching connected Xero account information.
    This is called once when a user authorizes the integration and the
    information is cached for display in the UI.
    """

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch Xero organization information for the connected account.
        Uses the first connected tenant/organization.

        Returns:
            ConnectedAccountInfo with organization name as username.
        """
        response = await context.fetch(
            "https://api.xero.com/connections",
            method="GET",
            headers={"Accept": "application/json"}
        )

        if not response or not isinstance(response, list) or len(response) == 0:
            return ConnectedAccountInfo(username="Unknown Organization")

        first_connection = response[0]
        tenant_name = first_connection.get("tenantName", "Unknown Organization")

        return ConnectedAccountInfo(
            username=tenant_name,
            user_id=first_connection.get("tenantId")
        )


# ---- Rate Limiting ----

class XeroRateLimitExceededException(Exception):
    """
    Exception raised when Xero API rate limit wait time exceeds maximum threshold.
    Provides structured info for LLM.
    """
    def __init__(self, requested_delay: int, max_wait_time: int, tenant_id: str):
        self.requested_delay = requested_delay
        self.max_wait_time = max_wait_time
        self.tenant_id = tenant_id
        
        super().__init__(
            f"Xero API rate limit for tenant {tenant_id} requires waiting {requested_delay}s, "
            f"exceeds maximum wait time of {max_wait_time}s"
        )

class XeroRateLimiter:
    def __init__(self, default_retry_delay: int = 60, max_retries: int = 3, max_wait_time: int = 60):
        """
        Handles Xero API rate limiting by retrying requests on 429 errors.
        Prevents lambda from waiting too long by setting maximum wait time.
        """
        self.default_retry_delay = default_retry_delay
        self.max_retries = max_retries
        self.max_wait_time = max_wait_time
    
    def _extract_retry_delay(self, error_response) -> int:
        """Extract retry delay from error response headers"""
        if hasattr(error_response, 'headers'):
            retry_after = error_response.headers.get('Retry-After')
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
        return self.default_retry_delay
    
    async def make_request(self, context: ExecutionContext, url: str, tenant_id: str, **kwargs) -> Any:
        """Make request to Xero API with automatic retry on rate limit errors"""
        # Add tenant header to the request
        headers = kwargs.get('headers', {})
        headers['xero-tenant-id'] = tenant_id
        kwargs['headers'] = headers
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await context.fetch(url, **kwargs)
                return response
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a rate limit error (HTTP 429)
                if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
                    # Don't retry on the last attempt
                    if attempt >= self.max_retries:
                        break
                        
                    # Get delay from response headers or use default
                    delay = self._extract_retry_delay(e)
                    
                    # Check if delay exceeds maximum wait time
                    if delay > self.max_wait_time:
                        # Don't wait - inform LLM about rate limit immediately
                        raise XeroRateLimitExceededException(delay, self.max_wait_time, tenant_id)
                    
                    # Short delay - proceed with waiting and retry
                    await asyncio.sleep(delay)
                    continue
                
                # For non-rate-limit errors, fail immediately
                raise e
        
        # All retries exhausted, raise the last error
        raise last_error


# Global rate limiter instance
rate_limiter = XeroRateLimiter()

# ---- Helper Functions ----


async def get_all_connections(context: ExecutionContext) -> list:
    """
    Gets all tenant connections from Xero connections API
    """
    try:
        response = await context.fetch(
            "https://api.xero.com/connections",
            method="GET",
            headers={"Accept": "application/json"}
        )
        
        if not response or not isinstance(response, list) or len(response) == 0:
            raise ValueError("No Xero connections found")
        
        return response
        
    except Exception as e:
        raise Exception(f"Failed to get connections: {str(e)}")



# ---- Action Handlers ----


@xero.action("get_available_connections")
class GetAvailableConnectionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Gets all available Xero tenant connections and returns company names
        """
        try:
            # Get all connections from Xero
            connections = await get_all_connections(context)
            
            # Extract company information
            companies = []
            for connection in connections:
                tenant_name = connection.get("tenantName")
                tenant_id = connection.get("tenantId")
                if tenant_name and tenant_id:
                    companies.append({
                        "tenant_id": tenant_id,
                        "company_name": tenant_name
                    })
            
            return ActionResult(data={
                "success": True,
                "companies": companies
            })
                
        except Exception as e:
            return ActionResult(data={
                "success": False,
                "message": f"Failed to get connections: {str(e)}",
                "companies": []
            })




@xero.action("find_contact_by_name")
class FindContactByNameAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Finds contact ID by filtering contacts with matching name in Xero
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact_name = inputs.get("contact_name")
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact_name:
            raise ValueError("contact_name is required")
        
        try:
            
            # Build URL with where filter for contact name
            url = "https://api.xero.com/api.xro/2.0/Contacts"
            params = {
                "where": f'Name.Contains("{contact_name}")'
            }
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            if not response or not response.get("Contacts"):
                return ActionResult(data={"contacts": []})
            
            # Extract comprehensive contact information
            contacts = []
            for contact in response["Contacts"]:
                contacts.append({
                    "contact_id": contact.get("ContactID"),
                    "name": contact.get("Name"),
                    "contact_number": contact.get("ContactNumber"),
                    "account_number": contact.get("AccountNumber"),
                    "contact_status": contact.get("ContactStatus"),
                    "first_name": contact.get("FirstName"),
                    "last_name": contact.get("LastName"),
                    "email_address": contact.get("EmailAddress"),
                    "skype_user_name": contact.get("SkypeUserName"),
                    "bank_account_details": contact.get("BankAccountDetails"),
                    "tax_number": contact.get("TaxNumber"),
                    "accounts_receivable_tax_type": contact.get("AccountsReceivableTaxType"),
                    "accounts_payable_tax_type": contact.get("AccountsPayableTaxType"),
                    "addresses": contact.get("Addresses"),
                    "phones": contact.get("Phones"),
                    "updated_date_utc": contact.get("UpdatedDateUTC"),
                    "contact_groups": contact.get("ContactGroups"),
                    "website": contact.get("Website"),
                    "branding_theme": contact.get("BrandingTheme"),
                    "batch_payments": contact.get("BatchPayments"),
                    "discount": contact.get("Discount"),
                    "balances": contact.get("Balances"),
                    "attachments": contact.get("Attachments"),
                    "has_attachments": contact.get("HasAttachments"),
                    "contact_persons": contact.get("ContactPersons")
                })
            
            return ActionResult(data={"contacts": contacts})
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay,
                "contacts": []
            })
        except Exception as e:
            raise Exception(f"Failed to find contact by name: {str(e)}")


@xero.action("get_aged_payables")
class GetAgedPayablesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches aged payables report from Xero API for a specific contact
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact_id = inputs.get("contact_id")
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact_id:
            raise ValueError("contact_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Reports/AgedPayablesByContact"
            params = {
                "contactId": contact_id
            }
            
            # Add optional date parameter
            if inputs.get("date"):
                params["date"] = inputs["date"]
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch aged payables report: {str(e)}")


@xero.action("get_aged_receivables")
class GetAgedReceivablesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches aged receivables report from Xero API for a specific contact
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact_id = inputs.get("contact_id")
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact_id:
            raise ValueError("contact_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Reports/AgedReceivablesByContact"
            params = {
                "contactId": contact_id
            }
            
            # Add optional date parameter
            if inputs.get("date"):
                params["date"] = inputs["date"]
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch aged receivables report: {str(e)}")


@xero.action("get_balance_sheet")
class GetBalanceSheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches balance sheet report from Xero API
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Reports/BalanceSheet"
            params = {}
            
            # Add optional date parameter
            if inputs.get("date"):
                params["date"] = inputs["date"]
            
            # Add optional periods parameter
            if inputs.get("periods"):
                params["periods"] = str(inputs["periods"])
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch balance sheet report: {str(e)}")


@xero.action("get_profit_and_loss")
class GetProfitAndLossAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches profit and loss report from Xero API
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss"
            params = {}
            
            # Add optional date parameter
            if inputs.get("date"):
                params["date"] = inputs["date"]
            
            # Add optional from_date parameter
            if inputs.get("from_date"):
                params["fromDate"] = inputs["from_date"]
            
            # Add optional to_date parameter
            if inputs.get("to_date"):
                params["toDate"] = inputs["to_date"]
            
            # Add optional timeframe parameter
            if inputs.get("timeframe"):
                params["timeframe"] = inputs["timeframe"]
            
            # Add optional periods parameter
            if inputs.get("periods"):
                params["periods"] = str(inputs["periods"])
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch profit and loss report: {str(e)}")


@xero.action("get_trial_balance")
class GetTrialBalanceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches trial balance report from Xero API
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Reports/TrialBalance"
            params = {}
            
            # Add optional date parameter
            if inputs.get("date"):
                params["date"] = inputs["date"]
            
            # Add optional payments_only parameter
            if inputs.get("payments_only") is not None:
                params["paymentsOnly"] = str(inputs["payments_only"]).lower()
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch trial balance report: {str(e)}")


@xero.action("get_accounts")
class GetAccountsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches accounts from Xero API to classify line items (revenue, expenses, fixed assets, loans, equity/dividends, GST)
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Accounts"
            params = {}
            
            # Add optional where parameter for filtering
            if inputs.get("where"):
                params["where"] = inputs["where"]
            
            # Add optional order parameter
            if inputs.get("order"):
                params["order"] = inputs["order"]
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch accounts: {str(e)}")


@xero.action("get_payments")
class GetPaymentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches payments from Xero API for cash on invoices/bills (customer receipts, supplier payments, cash refunds)
        Supports date filtering with where clause
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        try:
            
            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/Payments"
            params = {}
            
            # Add optional where parameter for date filtering
            if inputs.get("where"):
                params["where"] = inputs["where"]
            
            # Add optional order parameter
            if inputs.get("order"):
                params["order"] = inputs["order"]
            
            # Add optional pagination parameters
            if inputs.get("page"):
                params["page"] = str(inputs["page"])
            
            if inputs.get("pageSize"):
                params["pageSize"] = str(inputs["pageSize"])
            
            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )
            
            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")
            
            return ActionResult(data=response)
                
        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch payments: {str(e)}")


@xero.action("get_invoices")
class GetInvoicesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches invoices from Xero API. Can retrieve all invoices with optimized filtering
        or fetch a specific invoice by ID

        Supports optimized where filtering with range operators and list filtering:
        - Range operators: >, >=, <, <=, ==, !=
        - Date filtering: Date>=DateTime(2020,01,01) AND Date<=DateTime(2020,12,31)
        - Status filtering: Status=="DRAFT" OR Status=="AUTHORISED"
        - Contact filtering: Contact.ContactID==guid("contact-id")
        - Type filtering: Type=="ACCREC" (sales) or Type=="ACCPAY" (purchase)
        - Amount filtering: Total>=100.00 AND Total<=1000.00
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        try:
            # Build URL - check if specific invoice ID is provided
            invoice_id = inputs.get("invoice_id")
            if invoice_id:
                # Fetch specific invoice by ID
                url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}"
                params = {}
            else:
                # Fetch all invoices with optional filtering
                url = "https://api.xero.com/api.xro/2.0/Invoices"
                params = {}

                # Add optional where parameter for optimized filtering
                # Examples: Status=="AUTHORISED", Date>=DateTime(2020,01,01), Contact.ContactID==guid("id")
                if inputs.get("where"):
                    params["where"] = inputs["where"]

                # Add optional order parameter for optimized ordering
                # Optimized fields: InvoiceNumber, Date, DueDate, Total, UpdatedDateUTC
                # Examples: "Date DESC", "InvoiceNumber ASC", "Total DESC,Date ASC"
                if inputs.get("order"):
                    params["order"] = inputs["order"]

                # Add optional page parameter for pagination
                if inputs.get("page"):
                    params["page"] = str(inputs["page"])

                # Add optional pageSize parameter (max 100)
                if inputs.get("pageSize"):
                    params["pageSize"] = str(inputs["pageSize"])

                # Add optional statuses for filtering multiple statuses
                # Examples: "DRAFT,SUBMITTED,AUTHORISED"
                if inputs.get("statuses"):
                    params["statuses"] = inputs["statuses"]

                # Add optional invoice numbers for bulk retrieval
                if inputs.get("invoice_numbers"):
                    params["InvoiceNumbers"] = inputs["invoice_numbers"]

                # Add optional contact IDs for filtering by contact
                if inputs.get("contact_ids"):
                    params["ContactIDs"] = inputs["contact_ids"]

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch invoices: {str(e)}")


@xero.action("get_invoice_pdf")
class GetInvoicePdfAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Retrieves a specific invoice as PDF from Xero API

        Required fields:
        - tenant_id: Xero tenant ID
        - invoice_id: ID of the invoice to retrieve as PDF (GUID)

        Returns:
        - file: Object containing content (base64), contentType, and name
        - success: Boolean indicating if the download was successful
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        invoice_id = inputs.get("invoice_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not invoice_id:
            raise ValueError("invoice_id is required")

        try:
            # Build URL for specific invoice
            url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}"

            # Set Accept header to application/pdf to get PDF format
            headers = {
                "Accept": "application/pdf",
                "xero-tenant-id": tenant_id
            }

            # Need to handle binary data manually for PDF download
            # Get auth token from context
            auth_token = None
            if context.auth and "credentials" in context.auth:
                credentials = context.auth["credentials"]
                if "access_token" in credentials:
                    auth_token = credentials["access_token"]

            if not auth_token:
                raise ValueError("No authentication token available")

            headers["Authorization"] = f"Bearer {auth_token}"

            # Use aiohttp to download the PDF
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ActionResult(data={
                            "file": {"name": f"invoice_{invoice_id}.pdf", "content": "", "contentType": ""},
                            "success": False,
                            "error": f"Xero API error: {response.status} - {error_text}"
                        })

                    # Read binary content and encode as base64
                    pdf_content = await response.read()
                    content_base64 = base64.b64encode(pdf_content).decode('utf-8')

                    # Determine content type from response headers
                    content_type = response.headers.get('content-type', 'application/pdf')

                    return ActionResult(data={
                        "file": {
                            "name": f"invoice_{invoice_id}.pdf",
                            "content": content_base64,
                            "contentType": content_type
                        },
                        "success": True
                    })

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            return ActionResult(data={
                "file": {"name": f"invoice_{invoice_id}.pdf", "content": "", "contentType": ""},
                "success": False,
                "error": str(e)
            })


@xero.action("get_bank_transactions")
class GetBankTransactionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches bank transactions from Xero API for Receive/Spend Money not tied to invoices (CapEx, financing, other operating)
        Supports date filtering with where clause and pagination
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        try:

            # Build URL with parameters
            url = "https://api.xero.com/api.xro/2.0/BankTransactions"
            params = {}

            # Add optional where parameter for date filtering
            if inputs.get("where"):
                params["where"] = inputs["where"]

            # Add optional order parameter
            if inputs.get("order"):
                params["order"] = inputs["order"]

            # Add optional page parameter for pagination
            if inputs.get("page"):
                params["page"] = str(inputs["page"])

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch bank transactions: {str(e)}")


@xero.action("create_sales_invoice")
class CreateSalesInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Creates a new sales invoice (ACCREC) in Xero

        Required fields:
        - tenant_id: Xero tenant ID
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects
        - type: "ACCREC" for sales invoices

        Optional fields:
        - date: Invoice date (defaults to today)
        - due_date: Due date for payment
        - invoice_number: Custom invoice number
        - reference: Invoice reference
        - branding_theme_id: Branding theme ID
        - currency_code: Currency (defaults to organization currency)
        - status: "DRAFT", "SUBMITTED", or "AUTHORISED"
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact = inputs.get("contact")
        line_items = inputs.get("line_items")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact:
            raise ValueError("contact is required")
        if not line_items or not isinstance(line_items, list):
            raise ValueError("line_items is required and must be a list")

        try:
            # Build invoice payload
            invoice_data = {
                "Type": "ACCREC",  # Sales invoice
                "Contact": contact,
                "LineItems": line_items
            }

            # Add optional fields
            if inputs.get("date"):
                invoice_data["Date"] = inputs["date"]
            if inputs.get("due_date"):
                invoice_data["DueDate"] = inputs["due_date"]
            if inputs.get("invoice_number"):
                invoice_data["InvoiceNumber"] = inputs["invoice_number"]
            if inputs.get("reference"):
                invoice_data["Reference"] = inputs["reference"]
            if inputs.get("branding_theme_id"):
                invoice_data["BrandingThemeID"] = inputs["branding_theme_id"]
            if inputs.get("currency_code"):
                invoice_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                invoice_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                invoice_data["LineAmountTypes"] = inputs["line_amount_types"]

            # Build request payload
            payload = {"Invoices": [invoice_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                "https://api.xero.com/api.xro/2.0/Invoices",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to create sales invoice: {str(e)}")


@xero.action("create_purchase_bill")
class CreatePurchaseBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Creates a new purchase bill (ACCPAY) in Xero

        Required fields:
        - tenant_id: Xero tenant ID
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects
        - type: "ACCPAY" for purchase bills

        Optional fields:
        - date: Bill date (defaults to today)
        - due_date: Due date for payment
        - invoice_number: Supplier's invoice/bill number
        - reference: Bill reference
        - currency_code: Currency (defaults to organization currency)
        - status: "DRAFT", "SUBMITTED", or "AUTHORISED"
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact = inputs.get("contact")
        line_items = inputs.get("line_items")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact:
            raise ValueError("contact is required")
        if not line_items or not isinstance(line_items, list):
            raise ValueError("line_items is required and must be a list")

        try:
            # Build bill payload
            bill_data = {
                "Type": "ACCPAY",  # Purchase bill
                "Contact": contact,
                "LineItems": line_items
            }

            # Add optional fields
            if inputs.get("date"):
                bill_data["Date"] = inputs["date"]
            if inputs.get("due_date"):
                bill_data["DueDate"] = inputs["due_date"]
            if inputs.get("invoice_number"):
                bill_data["InvoiceNumber"] = inputs["invoice_number"]
            if inputs.get("reference"):
                bill_data["Reference"] = inputs["reference"]
            if inputs.get("currency_code"):
                bill_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                bill_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                bill_data["LineAmountTypes"] = inputs["line_amount_types"]

            # Build request payload
            payload = {"Invoices": [bill_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                "https://api.xero.com/api.xro/2.0/Invoices",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to create purchase bill: {str(e)}")


@xero.action("update_sales_invoice")
class UpdateSalesInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Updates an existing sales invoice (ACCREC) in Xero
        Only DRAFT and SUBMITTED invoices can be updated

        Required fields:
        - tenant_id: Xero tenant ID
        - invoice_id: ID of the invoice to update

        Optional fields (provide only fields you want to update):
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects (replaces all existing line items)
        - date: Invoice date
        - due_date: Due date for payment
        - invoice_number: Custom invoice number
        - reference: Invoice reference
        - branding_theme_id: Branding theme ID
        - currency_code: Currency code
        - status: "DRAFT", "SUBMITTED", or "AUTHORISED"
        - line_amount_types: "Exclusive", "Inclusive", or "NoTax"
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        invoice_id = inputs.get("invoice_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not invoice_id:
            raise ValueError("invoice_id is required")

        try:
            # Build invoice update payload
            invoice_data = {
                "InvoiceID": invoice_id,
                "Type": "ACCREC"  # Sales invoice
            }

            # Add optional fields only if provided
            if inputs.get("contact"):
                invoice_data["Contact"] = inputs["contact"]
            if inputs.get("line_items"):
                invoice_data["LineItems"] = inputs["line_items"]
            if inputs.get("date"):
                invoice_data["Date"] = inputs["date"]
            if inputs.get("due_date"):
                invoice_data["DueDate"] = inputs["due_date"]
            if inputs.get("invoice_number"):
                invoice_data["InvoiceNumber"] = inputs["invoice_number"]
            if inputs.get("reference"):
                invoice_data["Reference"] = inputs["reference"]
            if inputs.get("branding_theme_id"):
                invoice_data["BrandingThemeID"] = inputs["branding_theme_id"]
            if inputs.get("currency_code"):
                invoice_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                invoice_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                invoice_data["LineAmountTypes"] = inputs["line_amount_types"]

            # Build request payload
            payload = {"Invoices": [invoice_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to update sales invoice: {str(e)}")


@xero.action("update_purchase_bill")
class UpdatePurchaseBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Updates an existing purchase bill (ACCPAY) in Xero
        Only DRAFT and SUBMITTED bills can be updated

        Required fields:
        - tenant_id: Xero tenant ID
        - invoice_id: ID of the bill to update (bills use InvoiceID in Xero API)

        Optional fields (provide only fields you want to update):
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects (replaces all existing line items)
        - date: Bill date
        - due_date: Due date for payment
        - invoice_number: Supplier's invoice/bill number
        - reference: Bill reference
        - currency_code: Currency code
        - status: "DRAFT", "SUBMITTED", or "AUTHORISED"
        - line_amount_types: "Exclusive", "Inclusive", or "NoTax"
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        invoice_id = inputs.get("invoice_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not invoice_id:
            raise ValueError("invoice_id is required")

        try:
            # Build bill update payload
            bill_data = {
                "InvoiceID": invoice_id,
                "Type": "ACCPAY"  # Purchase bill
            }

            # Add optional fields only if provided
            if inputs.get("contact"):
                bill_data["Contact"] = inputs["contact"]
            if inputs.get("line_items"):
                bill_data["LineItems"] = inputs["line_items"]
            if inputs.get("date"):
                bill_data["Date"] = inputs["date"]
            if inputs.get("due_date"):
                bill_data["DueDate"] = inputs["due_date"]
            if inputs.get("invoice_number"):
                bill_data["InvoiceNumber"] = inputs["invoice_number"]
            if inputs.get("reference"):
                bill_data["Reference"] = inputs["reference"]
            if inputs.get("currency_code"):
                bill_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                bill_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                bill_data["LineAmountTypes"] = inputs["line_amount_types"]

            # Build request payload
            payload = {"Invoices": [bill_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to update purchase bill: {str(e)}")


@xero.action("attach_file_to_invoice")
class AttachFileToInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Attaches a file to an existing sales invoice or purchase bill in Xero
        Uses standard file object format

        Required fields:
        - tenant_id: Xero tenant ID
        - invoice_id: ID of the invoice/bill to attach file to
        - file: {content: "base64_data", contentType: "mime/type", name: "filename"}
          or
        - files: [{content: "base64_data", contentType: "mime/type", name: "filename"}]

        Optional fields:
        - include_online: Whether to include the attachment in online invoice (default: true)
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        invoice_id = inputs.get("invoice_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not invoice_id:
            raise ValueError("invoice_id is required")

        try:
            # Debug: Log what inputs we're receiving
            print(f"DEBUG attach_file_to_invoice: Received inputs keys: {list(inputs.keys())}")
            for key, value in inputs.items():
                if 'file' in key.lower():
                    print(f"DEBUG attach_file_to_invoice: {key} = {type(value)} - {value}")

            # Get file object from inputs
            file_obj = inputs.get('file')
            files_arr = inputs.get('files')
            if not file_obj and isinstance(files_arr, list) and files_arr:
                file_obj = files_arr[0]

            if not file_obj or not isinstance(file_obj, dict):
                # Debug: Show what we actually received
                available_keys = [k for k in inputs.keys() if 'file' in k.lower()]
                raise ValueError(f"file object is required. Available file-related keys: {available_keys}. file={inputs.get('file')}, files={inputs.get('files')}")

            # Extract file data from file object
            content_b64 = file_obj.get('content')
            if not content_b64:
                raise ValueError("file object missing content")

            # Decode the base64 file content
            file_bytes = base64.b64decode(content_b64)
            file_name = file_obj.get('name', 'attachment')
            content_type = file_obj.get('contentType', 'application/octet-stream')

            # Prepare the attachment payload
            # Xero expects file data as raw bytes, not JSON
            headers = {
                "Accept": "application/json",
                "Content-Type": content_type
            }

            # Add optional include_online parameter
            params = {}
            if inputs.get("include_online") is not None:
                params["IncludeOnline"] = str(inputs["include_online"]).lower()

            # Build the URL for attaching file to invoice
            url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}"

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="POST",
                data=file_bytes,  # Send decoded file bytes
                params=params,
                headers=headers
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to attach file to invoice: {str(e)}")


@xero.action("attach_file_to_bill")
class AttachFileToBillAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Attaches a file to an existing purchase bill in Xero
        Uses standard file object format

        Required fields:
        - tenant_id: Xero tenant ID
        - bill_id: ID of the bill to attach file to (same as invoice_id in Xero API)
        - file: {content: "base64_data", contentType: "mime/type", name: "filename"}
          or
        - files: [{content: "base64_data", contentType: "mime/type", name: "filename"}]

        Optional fields:
        - include_online: Whether to include the attachment in online bill (default: true)
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        bill_id = inputs.get("bill_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not bill_id:
            raise ValueError("bill_id is required")

        try:
            # Get file object from inputs
            file_obj = inputs.get('file')
            files_arr = inputs.get('files')
            if not file_obj and isinstance(files_arr, list) and files_arr:
                file_obj = files_arr[0]

            if not file_obj or not isinstance(file_obj, dict):
                raise ValueError("file object is required")

            # Extract file data from file object
            content_b64 = file_obj.get('content')
            if not content_b64:
                raise ValueError("file object missing content")

            # Decode the base64 file content
            file_bytes = base64.b64decode(content_b64)
            file_name = file_obj.get('name', 'attachment')
            content_type = file_obj.get('contentType', 'application/octet-stream')

            # Prepare the attachment payload
            # Xero expects file data as raw bytes, not JSON
            headers = {
                "Accept": "application/json",
                "Content-Type": content_type
            }

            # Add optional include_online parameter
            params = {}
            if inputs.get("include_online") is not None:
                params["IncludeOnline"] = str(inputs["include_online"]).lower()

            # Build the URL for attaching file to bill (uses same Invoice endpoint)
            url = f"https://api.xero.com/api.xro/2.0/Invoices/{bill_id}/Attachments/{file_name}"

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="POST",
                data=file_bytes,  # Send decoded file bytes
                params=params,
                headers=headers
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to attach file to bill: {str(e)}")


@xero.action("get_attachments")
class GetAttachmentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Gets all attachments for a specific invoice or bill from Xero API

        Required fields:
        - tenant_id: Xero tenant ID
        - endpoint: The endpoint type (e.g., "Invoices", "Bills", "BankTransactions")
        - guid: The GUID of the invoice/bill/transaction

        Returns attachment metadata including:
        - attachment_id: Unique ID of the attachment
        - file_name: Name of the attached file
        - url: URL to retrieve the attachment content
        - mime_type: MIME type of the attachment
        - content_length: Size of the attachment in bytes
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        endpoint = inputs.get("endpoint")
        guid = inputs.get("guid")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not endpoint:
            raise ValueError("endpoint is required (e.g., 'Invoices', 'Bills')")
        if not guid:
            raise ValueError("guid is required")

        try:
            # Build URL for getting attachments list
            url = f"https://api.xero.com/api.xro/2.0/{endpoint}/{guid}/Attachments"

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                headers={"Accept": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to get attachments: {str(e)}")


@xero.action("get_attachment_content")
class GetAttachmentContentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Downloads the actual content of a specific attachment from Xero API

        Required fields:
        - tenant_id: Xero tenant ID
        - endpoint: The endpoint type (e.g., "Invoices", "Bills", "BankTransactions")
        - guid: The GUID of the invoice/bill/transaction
        - file_name: The filename of the attachment to download

        Returns:
        - file: Object containing content (base64), contentType, and name
        - success: Boolean indicating if the download was successful
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        endpoint = inputs.get("endpoint")
        guid = inputs.get("guid")
        file_name = inputs.get("file_name")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not endpoint:
            raise ValueError("endpoint is required (e.g., 'Invoices', 'Bills')")
        if not guid:
            raise ValueError("guid is required")
        if not file_name:
            raise ValueError("file_name is required")

        try:
            # Build URL for getting attachment content
            url = f"https://api.xero.com/api.xro/2.0/{endpoint}/{guid}/Attachments/{file_name}"

            # For attachment content download, we need to handle binary data manually
            # Similar to how Box integration handles file content
            headers = {
                "Accept": "application/octet-stream",
                "xero-tenant-id": tenant_id
            }

            # Add authorization header if available
            async with context:  # Use context as async context manager
                session = context._session

                # Copy auth headers from context
                if context.auth and "credentials" in context.auth:
                    credentials = context.auth["credentials"]
                    if "access_token" in credentials:
                        headers["Authorization"] = f"Bearer {credentials['access_token']}"

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ActionResult(data={
                            "file": {"name": file_name, "content": "", "contentType": ""},
                            "success": False,
                            "error": f"Xero API error getting attachment content: {response.status} - {error_text}"
                        })

                    # Read binary content and encode as base64
                    file_content = await response.read()
                    content_base64 = base64.b64encode(file_content).decode('utf-8')

                    # Determine content type from response headers
                    content_type = response.headers.get('content-type', 'application/octet-stream')

            return ActionResult(data={
                "file": {
                    "name": file_name,
                    "content": content_base64,
                    "contentType": content_type
                },
                "success": True
            })

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            return ActionResult(data={
                "file": {"name": file_name, "content": "", "contentType": ""},
                "success": False,
                "error": str(e)
            })


@xero.action("get_purchase_orders")
class GetPurchaseOrdersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Fetches purchase orders from Xero API. Can retrieve all purchase orders with filtering
        or fetch a specific purchase order by ID

        Supports optimized where filtering with range operators:
        - Range operators: >, >=, <, <=, ==, !=
        - Date filtering: Date>=DateTime(2020,01,01) AND Date<=DateTime(2020,12,31)
        - Status filtering: Status=="DRAFT" OR Status=="AUTHORISED"
        - Contact filtering: Contact.ContactID==guid("contact-id")
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        try:
            # Build URL - check if specific purchase order ID is provided
            purchase_order_id = inputs.get("purchase_order_id")
            if purchase_order_id:
                # Fetch specific purchase order by ID
                url = f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{purchase_order_id}"
                params = {}
            else:
                # Fetch all purchase orders with optional filtering
                url = "https://api.xero.com/api.xro/2.0/PurchaseOrders"
                params = {}

                # Add optional where parameter for filtering
                if inputs.get("where"):
                    params["where"] = inputs["where"]

                # Add optional order parameter
                if inputs.get("order"):
                    params["order"] = inputs["order"]

                # Add optional page parameter for pagination
                if inputs.get("page"):
                    params["page"] = str(inputs["page"])

                # Add optional statuses for filtering multiple statuses
                if inputs.get("statuses"):
                    params["statuses"] = inputs["statuses"]

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                params=params,
                headers={"Accept": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to fetch purchase orders: {str(e)}")


@xero.action("create_purchase_order")
class CreatePurchaseOrderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Creates a new purchase order in Xero

        Required fields:
        - tenant_id: Xero tenant ID
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects

        Optional fields:
        - date: Purchase order date (defaults to today)
        - delivery_date: Expected delivery date
        - purchase_order_number: Custom purchase order number
        - reference: Purchase order reference
        - currency_code: Currency (defaults to organization currency)
        - status: "DRAFT", "SUBMITTED", "AUTHORISED", "BILLED", or "DELETED"
        - delivery_address: Delivery address (string)
        - attention_to: Name of person to be contacted
        - telephone: Phone number for contact
        - delivery_instructions: Delivery instructions
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        contact = inputs.get("contact")
        line_items = inputs.get("line_items")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not contact:
            raise ValueError("contact is required")
        if not line_items or not isinstance(line_items, list):
            raise ValueError("line_items is required and must be a list")

        try:
            # Build purchase order payload
            po_data = {
                "Contact": contact,
                "LineItems": line_items
            }

            # Add optional fields
            if inputs.get("date"):
                po_data["Date"] = inputs["date"]
            if inputs.get("delivery_date"):
                po_data["DeliveryDate"] = inputs["delivery_date"]
            if inputs.get("purchase_order_number"):
                po_data["PurchaseOrderNumber"] = inputs["purchase_order_number"]
            if inputs.get("reference"):
                po_data["Reference"] = inputs["reference"]
            if inputs.get("currency_code"):
                po_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                po_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                po_data["LineAmountTypes"] = inputs["line_amount_types"]
            if inputs.get("delivery_address"):
                po_data["DeliveryAddress"] = inputs["delivery_address"]
            if inputs.get("attention_to"):
                po_data["AttentionTo"] = inputs["attention_to"]
            if inputs.get("telephone"):
                po_data["Telephone"] = inputs["telephone"]
            if inputs.get("delivery_instructions"):
                po_data["DeliveryInstructions"] = inputs["delivery_instructions"]

            # Build request payload
            payload = {"PurchaseOrders": [po_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                "https://api.xero.com/api.xro/2.0/PurchaseOrders",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to create purchase order: {str(e)}")


@xero.action("update_purchase_order")
class UpdatePurchaseOrderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Updates an existing purchase order in Xero
        Only DRAFT and SUBMITTED purchase orders can be updated

        Required fields:
        - tenant_id: Xero tenant ID
        - purchase_order_id: ID of the purchase order to update

        Optional fields (provide only fields you want to update):
        - contact: Contact object with ContactID or Name
        - line_items: List of line item objects (replaces all existing line items)
        - date: Purchase order date
        - delivery_date: Expected delivery date
        - purchase_order_number: Custom purchase order number
        - reference: Purchase order reference
        - currency_code: Currency code
        - status: "DRAFT", "SUBMITTED", "AUTHORISED", "BILLED", or "DELETED"
        - delivery_address: Delivery address (string)
        - attention_to: Name of person to be contacted
        - telephone: Phone number for contact
        - delivery_instructions: Delivery instructions
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        purchase_order_id = inputs.get("purchase_order_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not purchase_order_id:
            raise ValueError("purchase_order_id is required")

        try:
            # Build purchase order update payload
            po_data = {
                "PurchaseOrderID": purchase_order_id
            }

            # Add optional fields only if provided
            if inputs.get("contact"):
                po_data["Contact"] = inputs["contact"]
            if inputs.get("line_items"):
                po_data["LineItems"] = inputs["line_items"]
            if inputs.get("date"):
                po_data["Date"] = inputs["date"]
            if inputs.get("delivery_date"):
                po_data["DeliveryDate"] = inputs["delivery_date"]
            if inputs.get("purchase_order_number"):
                po_data["PurchaseOrderNumber"] = inputs["purchase_order_number"]
            if inputs.get("reference"):
                po_data["Reference"] = inputs["reference"]
            if inputs.get("currency_code"):
                po_data["CurrencyCode"] = inputs["currency_code"]
            if inputs.get("status"):
                po_data["Status"] = inputs["status"]
            if inputs.get("line_amount_types"):
                po_data["LineAmountTypes"] = inputs["line_amount_types"]
            if inputs.get("delivery_address"):
                po_data["DeliveryAddress"] = inputs["delivery_address"]
            if inputs.get("attention_to"):
                po_data["AttentionTo"] = inputs["attention_to"]
            if inputs.get("telephone"):
                po_data["Telephone"] = inputs["telephone"]
            if inputs.get("delivery_instructions"):
                po_data["DeliveryInstructions"] = inputs["delivery_instructions"]

            # Build request payload
            payload = {"PurchaseOrders": [po_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{purchase_order_id}",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to update purchase order: {str(e)}")


@xero.action("delete_purchase_order")
class DeletePurchaseOrderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Deletes a purchase order in Xero by updating its status to DELETED

        Required fields:
        - tenant_id: Xero tenant ID
        - purchase_order_id: ID of the purchase order to delete
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        purchase_order_id = inputs.get("purchase_order_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not purchase_order_id:
            raise ValueError("purchase_order_id is required")

        try:
            # Build purchase order delete payload (sets status to DELETED)
            po_data = {
                "PurchaseOrderID": purchase_order_id,
                "Status": "DELETED"
            }

            # Build request payload
            payload = {"PurchaseOrders": [po_data]}

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{purchase_order_id}",
                tenant_id,
                method="POST",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to delete purchase order: {str(e)}")


@xero.action("get_purchase_order_history")
class GetPurchaseOrderHistoryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Retrieves the history and notes for a specific purchase order from Xero API

        Required fields:
        - tenant_id: Xero tenant ID
        - purchase_order_id: ID of the purchase order to get history for
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        purchase_order_id = inputs.get("purchase_order_id")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not purchase_order_id:
            raise ValueError("purchase_order_id is required")

        try:
            # Build URL for getting purchase order history
            url = f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{purchase_order_id}/History"

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="GET",
                headers={"Accept": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to get purchase order history: {str(e)}")


@xero.action("add_note_to_purchase_order")
class AddNoteToPurchaseOrderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Adds a note to a purchase order's history in Xero

        Required fields:
        - tenant_id: Xero tenant ID
        - purchase_order_id: ID of the purchase order to add note to
        - note: The note text to add
        """
        # Validate required inputs
        tenant_id = inputs.get("tenant_id")
        purchase_order_id = inputs.get("purchase_order_id")
        note = inputs.get("note")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not purchase_order_id:
            raise ValueError("purchase_order_id is required")
        if not note:
            raise ValueError("note is required")

        try:
            # Build URL for adding note to purchase order history
            url = f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{purchase_order_id}/History"

            # Build payload with note
            payload = {
                "HistoryRecords": [
                    {
                        "Details": note
                    }
                ]
            }

            # Make rate-limited authenticated request to Xero API
            response = await rate_limiter.make_request(
                context,
                url,
                tenant_id,
                method="PUT",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

            # Return raw API response
            if not response:
                raise ValueError("Empty response from Xero API")

            return ActionResult(data=response)

        except XeroRateLimitExceededException as e:
            return ActionResult(data={
                "success": False,
                "error_type": "rate_limit_exceeded",
                "message": f"Xero API rate limit exceeded for tenant {e.tenant_id}. Required wait time: {e.requested_delay}s exceeds maximum: {e.max_wait_time}s. Please try again later.",
                "tenant_id": e.tenant_id,
                "retry_delay_seconds": e.requested_delay
            })
        except Exception as e:
            raise Exception(f"Failed to add note to purchase order: {str(e)}")

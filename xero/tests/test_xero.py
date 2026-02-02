# Test for Xero Accounting integration
import asyncio
import pytest
import base64
from unittest.mock import Mock, AsyncMock, patch
from context import xero
from autohive_integrations_sdk import ExecutionContext
from xero import XeroRateLimiter, XeroRateLimitExceededException

async def test_get_available_connections():
    """
    Test the get_available_connections action
    """
    # Import xero integration lazily to avoid config issues during module import
    from context import xero
    
    # Setup mock auth object (platform auth for Xero)
    auth = {}  # Platform auth tokens are handled automatically by ExecutionContext

    inputs = {}  # No inputs required for get_available_connections

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await xero.execute_action("get_available_connections", inputs, context)
            data = result.result.data
            print(f"Success: Retrieved {len(data.get('companies', []))} available connections")
            if data.get('companies'):
                for company in data['companies']:
                    print(f"  - ID: {company.get('tenant_id')}, Name: {company.get('company_name')}")
            return result
        except Exception as e:
            print(f"Error testing get_available_connections: {str(e)}")
            return None

async def test_get_invoices_with_specific_tenant():
    """
    Test fetching invoices with a specific tenant ID
    """
    # First get available connections
    connections_result = await test_get_available_connections()
    if not connections_result or not connections_result.result.data.get('companies'):
        print("Cannot test invoices without tenant information")
        return

    # Use the first available tenant
    tenant_id = connections_result.result.data['companies'][0]['tenant_id']
    print(f"Using tenant ID: {tenant_id}")

    auth = {}
    inputs = {
        "tenant_id": tenant_id,
        "where": "Status==\"AUTHORISED\"",
        "order": "Date DESC",
        "pageSize": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await xero.execute_action("get_invoices", inputs, context)
            data = result.result.data
            print(f"Success: Retrieved {len(data.get('Invoices', []))} invoices")
            if data.get('Invoices'):
                for invoice in data['Invoices'][:3]:  # Show first 3
                    print(f"  - Invoice: {invoice.get('InvoiceNumber')} - Status: {invoice.get('Status')} - Total: {invoice.get('Total')}")
            return result
        except Exception as e:
            print(f"Error testing invoices: {str(e)}")
            return None

async def test_get_specific_invoice():
    """
    Test fetching a specific invoice by ID
    """
    # First get available connections
    connections_result = await test_get_available_connections()
    if not connections_result or not connections_result.result.data.get('companies'):
        print("Cannot test specific invoice without tenant information")
        return

    # Use the first available tenant
    tenant_id = connections_result.result.data['companies'][0]['tenant_id']
    print(f"Using tenant ID: {tenant_id}")

    auth = {}
    inputs = {
        "tenant_id": tenant_id,
        "invoice_id": "243216c5-369e-4056-ac67-05388f86dc81"  # Example invoice ID from API docs
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await xero.execute_action("get_invoices", inputs, context)
            data = result.result.data
            print(f"Success: Retrieved specific invoice")
            if data.get('Invoices'):
                invoice = data['Invoices'][0]
                print(f"  - Invoice: {invoice.get('InvoiceNumber')} - Status: {invoice.get('Status')}")
            return result
        except Exception as e:
            print(f"Error testing specific invoice: {str(e)}")
            return None

async def test_get_invoice_pdf_with_specific_tenant():
    """
    Test downloading invoice as PDF
    """
    # First get available connections
    connections_result = await test_get_available_connections()
    if not connections_result or not connections_result.result.data.get('companies'):
        print("Cannot test invoice PDF without tenant information")
        return

    # Use the first available tenant
    tenant_id = connections_result.result.data['companies'][0]['tenant_id']
    print(f"Using tenant ID: {tenant_id}")

    # First get some invoices to get a valid invoice ID
    invoices_result = await test_get_invoices_with_specific_tenant()
    if not invoices_result or not invoices_result.result.data.get('Invoices'):
        print("Cannot test PDF download without invoice information")
        return

    # Use the first invoice
    invoice_id = invoices_result.result.data['Invoices'][0]['InvoiceID']
    print(f"Using invoice ID: {invoice_id}")

    auth = {}
    inputs = {
        "tenant_id": tenant_id,
        "invoice_id": invoice_id
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await xero.execute_action("get_invoice_pdf", inputs, context)
            data = result.result.data
            if data.get("success"):
                print(f"Success: Downloaded invoice PDF")
                print(f"  - File name: {data['file']['name']}")
                print(f"  - Content type: {data['file']['contentType']}")
                print(f"  - Content size: {len(data['file']['content'])} characters (base64)")
            else:
                print(f"Failed: {data.get('error')}")
            return result
        except Exception as e:
            print(f"Error testing invoice PDF download: {str(e)}")
            return None

async def test_get_aged_payables_with_specific_tenant():
    """
    Test fetching aged payables with a specific tenant ID
    """
    # First get available connections
    connections_result = await test_get_available_connections()
    if not connections_result or not connections_result.result.data.get('companies'):
        print("Cannot test aged payables without tenant information")
        return

    # Use the first available tenant
    tenant_id = connections_result.result.data['companies'][0]['tenant_id']
    print(f"Using tenant ID: {tenant_id}")

    auth = {}
    inputs = {
        "tenant_id": tenant_id,
        "contact_id": "test-contact-id-123"  # Replace with actual contact ID
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await xero.execute_action("get_aged_payables", inputs, context)
            print(f"Success: Retrieved aged payables report")
            return result
        except Exception as e:
            print(f"Error testing aged payables: {str(e)}")
            return None

async def main():
    print("Testing Xero Integration")
    print("==================================")

    print("\n1. Testing get_available_connections...")
    await test_get_available_connections()

    print("\n2. Testing get_invoices with filtering...")
    await test_get_invoices_with_specific_tenant()

    print("\n3. Testing get specific invoice by ID...")
    await test_get_specific_invoice()

    print("\n4. Testing invoice PDF download...")
    await test_get_invoice_pdf_with_specific_tenant()

    print("\n5. Testing aged payables with tenant ID...")
    await test_get_aged_payables_with_specific_tenant()

    print("\n6. Running rate limiting tests...")
    print("To run rate limiting tests, use: pytest tests/test_xero.py -v")

# ---- Rate Limiting Tests ----

class MockResponse:
    """Mock response object for testing"""
    def __init__(self, headers=None):
        self.headers = headers or {}


class MockRateLimitError(Exception):
    """Mock exception that simulates a 429 rate limit error"""
    def __init__(self, message="429 Rate limit exceeded", headers=None):
        super().__init__(message)
        self.headers = headers or {}


@pytest.mark.asyncio
async def test_rate_limiter_successful_request():
    """Test that successful requests work normally"""
    limiter = XeroRateLimiter()
    context = Mock()
    context.fetch = AsyncMock(return_value={"success": True})
    
    result = await limiter.make_request(
        context, 
        "https://api.xero.com/test", 
        "tenant-123",
        method="GET"
    )
    
    assert result == {"success": True}
    context.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_short_delay_retry():
    """Test that short rate limit delays result in retry and success"""
    limiter = XeroRateLimiter(max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    # First call raises rate limit, second succeeds
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "5"}
    )
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    assert context.fetch.call_count == 2
    mock_sleep.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_rate_limiter_long_delay_exception():
    """Test that long rate limit delays raise XeroRateLimitExceededException"""
    limiter = XeroRateLimiter(max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "120"}  # Exceeds max_wait_time of 60
    )
    context.fetch = AsyncMock(side_effect=rate_limit_error)
    
    with pytest.raises(XeroRateLimitExceededException) as exc_info:
        await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    exception = exc_info.value
    assert exception.requested_delay == 120
    assert exception.max_wait_time == 60
    assert exception.tenant_id == "tenant-123"
    assert "exceeds maximum wait time" in str(exception)


@pytest.mark.asyncio
async def test_rate_limiter_exhausted_retries():
    """Test that exhausted retries raise the last error"""
    limiter = XeroRateLimiter(max_retries=2, max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "5"}
    )
    context.fetch = AsyncMock(side_effect=rate_limit_error)
    
    with patch('asyncio.sleep'):
        with pytest.raises(MockRateLimitError):
            await limiter.make_request(
                context,
                "https://api.xero.com/test",
                "tenant-123",
                method="GET"
            )
    
    # Should call fetch max_retries + 1 times (initial + retries)
    assert context.fetch.call_count == 3


@pytest.mark.asyncio
async def test_rate_limiter_non_rate_limit_error():
    """Test that non-rate-limit errors are raised immediately without retries"""
    limiter = XeroRateLimiter()
    context = Mock()
    
    other_error = Exception("500 Internal Server Error")
    context.fetch = AsyncMock(side_effect=other_error)
    
    with pytest.raises(Exception) as exc_info:
        await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert str(exc_info.value) == "500 Internal Server Error"
    context.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_default_delay_no_header():
    """Test that default delay is used when Retry-After header is missing"""
    limiter = XeroRateLimiter(default_retry_delay=30, max_wait_time=60)
    context = Mock()
    
    # Rate limit error without Retry-After header
    rate_limit_error = MockRateLimitError("429 Too Many Requests")
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    mock_sleep.assert_called_once_with(30)  # Should use default_retry_delay


@pytest.mark.asyncio
async def test_rate_limiter_invalid_retry_after_header():
    """Test that invalid Retry-After header falls back to default delay"""
    limiter = XeroRateLimiter(default_retry_delay=25, max_wait_time=60)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "invalid-value"}
    )
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    mock_sleep.assert_called_once_with(25)  # Should use default_retry_delay


@pytest.mark.asyncio
async def test_rate_limiter_tenant_header_added():
    """Test that xero-tenant-id header is properly added to requests"""
    limiter = XeroRateLimiter()
    context = Mock()
    context.fetch = AsyncMock(return_value={"success": True})
    
    await limiter.make_request(
        context,
        "https://api.xero.com/test",
        "tenant-123",
        method="GET",
        headers={"Accept": "application/json"}
    )
    
    # Verify the call was made with tenant header added
    context.fetch.assert_called_once_with(
        "https://api.xero.com/test",
        method="GET",
        headers={
            "Accept": "application/json",
            "xero-tenant-id": "tenant-123"
        }
    )


@pytest.mark.asyncio
async def test_find_contact_rate_limit_exception_handling():
    """Test that action handlers properly handle XeroRateLimitExceededException"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero
    
    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "contact_name": "Test Contact"
    }
    
    # Mock the rate limiter to raise XeroRateLimitExceededException
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=120,
                max_wait_time=60,
                tenant_id="test-tenant"
            )
        )
        
        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("find_contact_by_name", inputs, context)
            data = result.result.data
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant"
            assert data["retry_delay_seconds"] == 120
            assert "exceeds maximum" in data["message"]


class MockRateLimitError(Exception):
    """Mock exception that simulates a 429 rate limit error"""
    def __init__(self, message="429 Rate limit exceeded", headers=None):
        super().__init__(message)
        self.headers = headers or {}


@pytest.mark.asyncio
async def test_rate_limiter_successful_request():
    """Test that successful requests work normally"""
    limiter = XeroRateLimiter()
    context = Mock()
    context.fetch = AsyncMock(return_value={"success": True})
    
    result = await limiter.make_request(
        context, 
        "https://api.xero.com/test", 
        "tenant-123",
        method="GET"
    )
    
    assert result == {"success": True}
    context.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_short_delay_retry():
    """Test that short rate limit delays result in retry and success"""
    limiter = XeroRateLimiter(max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    # First call raises rate limit, second succeeds
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "5"}
    )
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    assert context.fetch.call_count == 2
    mock_sleep.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_rate_limiter_long_delay_exception():
    """Test that long rate limit delays raise XeroRateLimitExceededException"""
    limiter = XeroRateLimiter(max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "120"}  # Exceeds max_wait_time of 60
    )
    context.fetch = AsyncMock(side_effect=rate_limit_error)
    
    with pytest.raises(XeroRateLimitExceededException) as exc_info:
        await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    exception = exc_info.value
    assert exception.requested_delay == 120
    assert exception.max_wait_time == 60
    assert exception.tenant_id == "tenant-123"
    assert "exceeds maximum wait time" in str(exception)


@pytest.mark.asyncio
async def test_rate_limiter_exhausted_retries():
    """Test that exhausted retries raise the last error"""
    limiter = XeroRateLimiter(max_retries=2, max_wait_time=60, default_retry_delay=10)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "5"}
    )
    context.fetch = AsyncMock(side_effect=rate_limit_error)
    
    with patch('asyncio.sleep'):
        with pytest.raises(MockRateLimitError):
            await limiter.make_request(
                context,
                "https://api.xero.com/test",
                "tenant-123",
                method="GET"
            )
    
    # Should call fetch max_retries + 1 times (initial + retries)
    assert context.fetch.call_count == 3


@pytest.mark.asyncio
async def test_rate_limiter_non_rate_limit_error():
    """Test that non-rate-limit errors are raised immediately without retries"""
    limiter = XeroRateLimiter()
    context = Mock()
    
    other_error = Exception("500 Internal Server Error")
    context.fetch = AsyncMock(side_effect=other_error)
    
    with pytest.raises(Exception) as exc_info:
        await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert str(exc_info.value) == "500 Internal Server Error"
    context.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_default_delay_no_header():
    """Test that default delay is used when Retry-After header is missing"""
    limiter = XeroRateLimiter(default_retry_delay=30, max_wait_time=60)
    context = Mock()
    
    # Rate limit error without Retry-After header
    rate_limit_error = MockRateLimitError("429 Too Many Requests")
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    mock_sleep.assert_called_once_with(30)  # Should use default_retry_delay


@pytest.mark.asyncio
async def test_rate_limiter_invalid_retry_after_header():
    """Test that invalid Retry-After header falls back to default delay"""
    limiter = XeroRateLimiter(default_retry_delay=25, max_wait_time=60)
    context = Mock()
    
    rate_limit_error = MockRateLimitError(
        "429 Too Many Requests",
        headers={"Retry-After": "invalid-value"}
    )
    context.fetch = AsyncMock(side_effect=[rate_limit_error, {"success": True}])
    
    with patch('asyncio.sleep') as mock_sleep:
        result = await limiter.make_request(
            context,
            "https://api.xero.com/test",
            "tenant-123",
            method="GET"
        )
    
    assert result == {"success": True}
    mock_sleep.assert_called_once_with(25)  # Should use default_retry_delay


@pytest.mark.asyncio
async def test_rate_limiter_tenant_header_added():
    """Test that xero-tenant-id header is properly added to requests"""
    limiter = XeroRateLimiter()
    context = Mock()
    context.fetch = AsyncMock(return_value={"success": True})
    
    await limiter.make_request(
        context,
        "https://api.xero.com/test",
        "tenant-123",
        method="GET",
        headers={"Accept": "application/json"}
    )
    
    # Verify the call was made with tenant header added
    context.fetch.assert_called_once_with(
        "https://api.xero.com/test",
        method="GET",
        headers={
            "Accept": "application/json",
            "xero-tenant-id": "tenant-123"
        }
    )


@pytest.mark.asyncio
async def test_find_contact_rate_limit_exception_handling():
    """Test that action handlers properly handle XeroRateLimitExceededException"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "contact_name": "Test Contact"
    }

    # Mock the rate limiter to raise XeroRateLimitExceededException
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=120,
                max_wait_time=60,
                tenant_id="test-tenant"
            )
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("find_contact_by_name", inputs, context)
            data = result.result.data
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant"
            assert data["retry_delay_seconds"] == 120
            assert "exceeds maximum" in data["message"]


@pytest.mark.asyncio
async def test_get_invoices_rate_limit_exception_handling():
    """Test that get_invoices action properly handles XeroRateLimitExceededException"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "where": "Status==\"AUTHORISED\"",
        "pageSize": 10
    }

    # Mock the rate limiter to raise XeroRateLimitExceededException
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=180,
                max_wait_time=60,
                tenant_id="test-tenant"
            )
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_invoices", inputs, context)
            data = result.result.data
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant"
            assert data["retry_delay_seconds"] == 180
            assert "exceeds maximum" in data["message"]


@pytest.mark.asyncio
async def test_get_specific_invoice_rate_limit_exception_handling():
    """Test that get_invoices with specific invoice ID properly handles XeroRateLimitExceededException"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "invoice_id": "243216c5-369e-4056-ac67-05388f86dc81"
    }

    # Mock the rate limiter to raise XeroRateLimitExceededException
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=90,
                max_wait_time=60,
                tenant_id="test-tenant"
            )
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_invoices", inputs, context)
            data = result.result.data
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant"
            assert data["retry_delay_seconds"] == 90
            assert "exceeds maximum" in data["message"]


@pytest.mark.asyncio
async def test_attach_file_to_invoice_with_base64():
    """Test that attach_file_to_invoice properly handles base64 encoded file data"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero

    # Create test file content and encode as base64
    test_content = b"Test PDF content - this is a mock PDF file"
    base64_content = base64.b64encode(test_content).decode('utf-8')

    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "invoice_id": "test-invoice-123",
        "file_name": "test-attachment.pdf",
        "file_data": base64_content,
        "content_type": "application/pdf",
        "include_online": True
    }

    # Mock the rate limiter to return a successful response
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            return_value={
                "Attachments": [{
                    "AttachmentID": "test-attachment-id",
                    "FileName": "test-attachment.pdf",
                    "Url": "https://api.xero.com/api.xro/2.0/Invoices/test-invoice-123/Attachments/test-attachment.pdf",
                    "MimeType": "application/pdf",
                    "ContentLength": len(test_content)
                }]
            }
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("attach_file_to_invoice", inputs, context)
            data = result.result.data
            # Verify the attachment was successful
            assert "Attachments" in data
            assert len(data["Attachments"]) == 1
            assert data["Attachments"][0]["FileName"] == "test-attachment.pdf"
            assert data["Attachments"][0]["MimeType"] == "application/pdf"
            assert data["Attachments"][0]["ContentLength"] == len(test_content)

            # Verify the rate limiter was called with decoded bytes
            mock_limiter.make_request.assert_called_once()
            call_args = mock_limiter.make_request.call_args

            # Check that the data parameter contains the decoded bytes
            assert call_args[1]["data"] == test_content
            assert call_args[1]["method"] == "POST"
            assert "application/pdf" in call_args[1]["headers"]["Content-Type"]


@pytest.mark.asyncio
async def test_attach_file_to_bill_with_base64():
    """Test that attach_file_to_bill properly handles base64 encoded file data"""
    # Import xero integration lazily to avoid config issues during module import
    from context import xero

    # Create test file content and encode as base64
    test_content = b"Test invoice content - this is a mock invoice file"
    base64_content = base64.b64encode(test_content).decode('utf-8')

    auth = {}
    inputs = {
        "tenant_id": "test-tenant",
        "bill_id": "test-bill-456",
        "file_name": "supplier-invoice.pdf",
        "file_data": base64_content,
        "content_type": "application/pdf"
    }

    # Mock the rate limiter to return a successful response
    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            return_value={
                "Attachments": [{
                    "AttachmentID": "test-bill-attachment-id",
                    "FileName": "supplier-invoice.pdf",
                    "Url": "https://api.xero.com/api.xro/2.0/Invoices/test-bill-456/Attachments/supplier-invoice.pdf",
                    "MimeType": "application/pdf",
                    "ContentLength": len(test_content)
                }]
            }
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("attach_file_to_bill", inputs, context)
            data = result.result.data
            # Verify the attachment was successful
            assert "Attachments" in data
            assert len(data["Attachments"]) == 1
            assert data["Attachments"][0]["FileName"] == "supplier-invoice.pdf"
            assert data["Attachments"][0]["ContentLength"] == len(test_content)

            # Verify the rate limiter was called with decoded bytes
            mock_limiter.make_request.assert_called_once()
            call_args = mock_limiter.make_request.call_args

            # Check that the data parameter contains the decoded bytes
            assert call_args[1]["data"] == test_content
            assert call_args[1]["method"] == "POST"


@pytest.mark.asyncio
async def test_get_invoice_pdf_success():
    """Test that get_invoice_pdf successfully downloads a PDF invoice"""
    from context import xero

    # Create mock PDF content
    mock_pdf_content = b"%PDF-1.4\n%Mock PDF content for testing"
    base64_pdf = base64.b64encode(mock_pdf_content).decode('utf-8')

    auth = {
        "credentials": {
            "access_token": "test-access-token-123"
        }
    }
    inputs = {
        "tenant_id": "test-tenant-456",
        "invoice_id": "test-invoice-789"
    }

    # Mock aiohttp response for PDF download
    mock_response = Mock()
    mock_response.status = 200
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.read = AsyncMock(return_value=mock_pdf_content)

    mock_session = Mock()
    mock_session.get = Mock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_invoice_pdf", inputs, context)
            data = result.result.data
            # Verify the PDF was successfully downloaded
            assert data["success"] is True
            assert data["file"]["name"] == "invoice_test-invoice-789.pdf"
            assert data["file"]["contentType"] == "application/pdf"
            assert data["file"]["content"] == base64_pdf
            assert "error" not in data or data.get("error") is None


@pytest.mark.asyncio
async def test_get_invoice_pdf_not_found():
    """Test that get_invoice_pdf handles 404 errors correctly"""
    from context import xero

    auth = {
        "credentials": {
            "access_token": "test-access-token-123"
        }
    }
    inputs = {
        "tenant_id": "test-tenant-456",
        "invoice_id": "non-existent-invoice"
    }

    # Mock aiohttp response for 404 error
    mock_response = Mock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="Invoice not found")

    mock_session = Mock()
    mock_session.get = Mock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_invoice_pdf", inputs, context)
            data = result.result.data
            # Verify the error is properly handled
            assert data["success"] is False
            assert "error" in data
            assert "404" in data["error"]
            assert data["file"]["content"] == ""


@pytest.mark.asyncio
async def test_get_purchase_orders_success():
    """Test that get_purchase_orders successfully retrieves purchase orders"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "where": "Status==\"AUTHORISED\"",
        "order": "Date DESC",
        "page": 1
    }

    # Mock successful response
    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "po-123",
                "PurchaseOrderNumber": "PO-001",
                "Status": "AUTHORISED",
                "Date": "2024-01-15",
                "DeliveryDate": "2024-01-20",
                "Contact": {
                    "ContactID": "contact-456",
                    "Name": "Test Supplier"
                },
                "LineItems": [
                    {
                        "Description": "Test Item",
                        "Quantity": 10,
                        "UnitAmount": 50.00,
                        "LineAmount": 500.00
                    }
                ],
                "Total": 500.00
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_purchase_orders", inputs, context)
            data = result.result.data
            # Verify the purchase orders were retrieved
            assert "PurchaseOrders" in data
            assert len(data["PurchaseOrders"]) == 1
            assert data["PurchaseOrders"][0]["PurchaseOrderNumber"] == "PO-001"
            assert data["PurchaseOrders"][0]["Status"] == "AUTHORISED"
            assert data["PurchaseOrders"][0]["Total"] == 500.00

            # Verify the rate limiter was called correctly
            mock_limiter.make_request.assert_called_once()
            call_args = mock_limiter.make_request.call_args
            assert call_args[0][1] == "https://api.xero.com/api.xro/2.0/PurchaseOrders"
            assert call_args[0][2] == "test-tenant-123"
            assert call_args[1]["method"] == "GET"
            assert call_args[1]["params"]["where"] == "Status==\"AUTHORISED\""
            assert call_args[1]["params"]["order"] == "Date DESC"


@pytest.mark.asyncio
async def test_get_purchase_orders_by_id():
    """Test that get_purchase_orders can retrieve a specific purchase order by ID"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-specific-789"
    }

    # Mock successful response for specific purchase order
    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "po-specific-789",
                "PurchaseOrderNumber": "PO-789",
                "Status": "DRAFT",
                "Reference": "REF-001"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_purchase_orders", inputs, context)
            data = result.result.data
            # Verify the specific purchase order was retrieved
            assert "PurchaseOrders" in data
            assert data["PurchaseOrders"][0]["PurchaseOrderID"] == "po-specific-789"

            # Verify the URL includes the purchase order ID
            call_args = mock_limiter.make_request.call_args
            assert "po-specific-789" in call_args[0][1]


@pytest.mark.asyncio
async def test_get_purchase_orders_rate_limit_handling():
    """Test that get_purchase_orders properly handles rate limit exceptions"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123"
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=150,
                max_wait_time=60,
                tenant_id="test-tenant-123"
            )
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_purchase_orders", inputs, context)
            data = result.result.data
            # Verify the error is properly handled
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant-123"
            assert data["retry_delay_seconds"] == 150


@pytest.mark.asyncio
async def test_create_purchase_order_success():
    """Test that create_purchase_order successfully creates a purchase order"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "contact": {
            "ContactID": "contact-456"
        },
        "line_items": [
            {
                "Description": "Office Supplies",
                "Quantity": 5,
                "UnitAmount": 25.00,
                "AccountCode": "200"
            }
        ],
        "date": "2024-01-15",
        "delivery_date": "2024-01-25",
        "reference": "PO-REF-001",
        "status": "DRAFT"
    }

    # Mock successful response
    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "new-po-123",
                "PurchaseOrderNumber": "PO-NEW-001",
                "Status": "DRAFT",
                "Date": "2024-01-15",
                "DeliveryDate": "2024-01-25",
                "Reference": "PO-REF-001",
                "Contact": {
                    "ContactID": "contact-456",
                    "Name": "Test Supplier"
                },
                "LineItems": [
                    {
                        "Description": "Office Supplies",
                        "Quantity": 5,
                        "UnitAmount": 25.00,
                        "LineAmount": 125.00,
                        "AccountCode": "200"
                    }
                ],
                "SubTotal": 125.00,
                "Total": 125.00
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("create_purchase_order", inputs, context)
            data = result.result.data
            # Verify the purchase order was created
            assert "PurchaseOrders" in data
            assert len(data["PurchaseOrders"]) == 1
            po = data["PurchaseOrders"][0]
            assert po["PurchaseOrderNumber"] == "PO-NEW-001"
            assert po["Status"] == "DRAFT"
            assert po["Reference"] == "PO-REF-001"
            assert po["Total"] == 125.00

            # Verify the rate limiter was called correctly
            mock_limiter.make_request.assert_called_once()
            call_args = mock_limiter.make_request.call_args
            assert call_args[0][1] == "https://api.xero.com/api.xro/2.0/PurchaseOrders"
            assert call_args[0][2] == "test-tenant-123"
            assert call_args[1]["method"] == "POST"

            # Verify the payload structure
            payload = call_args[1]["json"]
            assert "PurchaseOrders" in payload
            assert payload["PurchaseOrders"][0]["Contact"]["ContactID"] == "contact-456"
            assert len(payload["PurchaseOrders"][0]["LineItems"]) == 1


@pytest.mark.asyncio
async def test_create_purchase_order_missing_required_fields():
    """Test that create_purchase_order raises error when required fields are missing"""
    from context import xero

    auth = {}

    # Test missing tenant_id
    inputs_no_tenant = {
        "contact": {"ContactID": "contact-456"},
        "line_items": [{"Description": "Test"}]
    }

    async with ExecutionContext(auth=auth) as context:
        with pytest.raises(ValueError, match="tenant_id is required"):
            await xero.execute_action("create_purchase_order", inputs_no_tenant, context)

    # Test missing contact
    inputs_no_contact = {
        "tenant_id": "test-tenant-123",
        "line_items": [{"Description": "Test"}]
    }

    async with ExecutionContext(auth=auth) as context:
        with pytest.raises(ValueError, match="contact is required"):
            await xero.execute_action("create_purchase_order", inputs_no_contact, context)

    # Test missing line_items
    inputs_no_items = {
        "tenant_id": "test-tenant-123",
        "contact": {"ContactID": "contact-456"}
    }

    async with ExecutionContext(auth=auth) as context:
        with pytest.raises(ValueError, match="line_items is required"):
            await xero.execute_action("create_purchase_order", inputs_no_items, context)


@pytest.mark.asyncio
async def test_create_purchase_order_with_optional_fields():
    """Test that create_purchase_order handles optional fields correctly"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "contact": {"ContactID": "contact-456"},
        "line_items": [
            {
                "Description": "Test Item",
                "Quantity": 1,
                "UnitAmount": 100.00
            }
        ],
        "delivery_address": "123 Test St, Test City",
        "attention_to": "John Doe",
        "telephone": "+1-555-1234",
        "delivery_instructions": "Leave at reception"
    }

    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "po-456",
                "PurchaseOrderNumber": "PO-456",
                "DeliveryAddress": "123 Test St, Test City",
                "AttentionTo": "John Doe",
                "Telephone": "+1-555-1234",
                "DeliveryInstructions": "Leave at reception"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("create_purchase_order", inputs, context)
            data = result.result.data
            # Verify optional fields were included
            po = data["PurchaseOrders"][0]
            assert po["DeliveryAddress"] == "123 Test St, Test City"
            assert po["AttentionTo"] == "John Doe"
            assert po["Telephone"] == "+1-555-1234"
            assert po["DeliveryInstructions"] == "Leave at reception"

            # Verify the payload included optional fields
            call_args = mock_limiter.make_request.call_args
            payload = call_args[1]["json"]
            po_data = payload["PurchaseOrders"][0]
            assert po_data["DeliveryAddress"] == "123 Test St, Test City"
            assert po_data["AttentionTo"] == "John Doe"


@pytest.mark.asyncio
async def test_create_purchase_order_rate_limit_handling():
    """Test that create_purchase_order properly handles rate limit exceptions"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "contact": {"ContactID": "contact-456"},
        "line_items": [{"Description": "Test"}]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(
            side_effect=XeroRateLimitExceededException(
                requested_delay=200,
                max_wait_time=60,
                tenant_id="test-tenant-123"
            )
        )

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("create_purchase_order", inputs, context)
            data = result.result.data
            # Verify the error is properly handled
            assert data["success"] is False
            assert data["error_type"] == "rate_limit_exceeded"
            assert data["tenant_id"] == "test-tenant-123"
            assert data["retry_delay_seconds"] == 200


@pytest.mark.asyncio
async def test_update_purchase_order_success():
    """Test that update_purchase_order successfully updates a purchase order"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-789",
        "status": "AUTHORISED",
        "reference": "UPDATED-REF"
    }

    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "po-789",
                "Status": "AUTHORISED",
                "Reference": "UPDATED-REF"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("update_purchase_order", inputs, context)
            data = result.result.data
            # Verify the purchase order was updated
            po = data["PurchaseOrders"][0]
            assert po["Status"] == "AUTHORISED"
            assert po["Reference"] == "UPDATED-REF"

            # Verify the URL includes the purchase order ID
            call_args = mock_limiter.make_request.call_args
            assert "po-789" in call_args[0][1]
            assert call_args[1]["method"] == "POST"


@pytest.mark.asyncio
async def test_add_note_to_purchase_order_success():
    """Test that add_note_to_purchase_order successfully adds a note"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-999",
        "note": "This is a test note for the purchase order"
    }

    mock_response = {
        "HistoryRecords": [
            {
                "Details": "This is a test note for the purchase order",
                "DateUTC": "2024-01-15T10:30:00"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("add_note_to_purchase_order", inputs, context)
            data = result.result.data
            # Verify the note was added
            assert "HistoryRecords" in data
            assert data["HistoryRecords"][0]["Details"] == "This is a test note for the purchase order"

            # Verify the rate limiter was called with PUT method
            mock_limiter.make_request.assert_called_once()
            call_args = mock_limiter.make_request.call_args
            assert "po-999/History" in call_args[0][1]
            assert call_args[1]["method"] == "PUT"

            # Verify the payload structure
            payload = call_args[1]["json"]
            assert "HistoryRecords" in payload
            assert payload["HistoryRecords"][0]["Details"] == "This is a test note for the purchase order"


@pytest.mark.asyncio
async def test_add_note_to_purchase_order_missing_fields():
    """Test that add_note_to_purchase_order raises error when required fields are missing"""
    from context import xero

    auth = {}

    # Test missing note
    inputs_no_note = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-999"
    }

    async with ExecutionContext(auth=auth) as context:
        with pytest.raises(ValueError, match="note is required"):
            await xero.execute_action("add_note_to_purchase_order", inputs_no_note, context)


@pytest.mark.asyncio
async def test_get_purchase_order_history_success():
    """Test that get_purchase_order_history successfully retrieves history"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-111"
    }

    mock_response = {
        "HistoryRecords": [
            {
                "Details": "Purchase order created",
                "DateUTC": "2024-01-10T09:00:00",
                "User": "Test User"
            },
            {
                "Details": "Purchase order approved",
                "DateUTC": "2024-01-11T14:30:00",
                "User": "Manager"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("get_purchase_order_history", inputs, context)
            data = result.result.data
            # Verify the history was retrieved
            assert "HistoryRecords" in data
            assert len(data["HistoryRecords"]) == 2
            assert data["HistoryRecords"][0]["Details"] == "Purchase order created"
            assert data["HistoryRecords"][1]["Details"] == "Purchase order approved"

            # Verify the correct endpoint was called
            call_args = mock_limiter.make_request.call_args
            assert "po-111/History" in call_args[0][1]
            assert call_args[1]["method"] == "GET"


@pytest.mark.asyncio
async def test_delete_purchase_order_success():
    """Test that delete_purchase_order successfully deletes (marks as DELETED) a purchase order"""
    from context import xero

    auth = {}
    inputs = {
        "tenant_id": "test-tenant-123",
        "purchase_order_id": "po-to-delete"
    }

    mock_response = {
        "PurchaseOrders": [
            {
                "PurchaseOrderID": "po-to-delete",
                "Status": "DELETED"
            }
        ]
    }

    with patch('xero.rate_limiter') as mock_limiter:
        mock_limiter.make_request = AsyncMock(return_value=mock_response)

        async with ExecutionContext(auth=auth) as context:
            result = await xero.execute_action("delete_purchase_order", inputs, context)
            data = result.result.data
            # Verify the purchase order was deleted
            po = data["PurchaseOrders"][0]
            assert po["Status"] == "DELETED"

            # Verify the payload sets status to DELETED
            call_args = mock_limiter.make_request.call_args
            payload = call_args[1]["json"]
            assert payload["PurchaseOrders"][0]["Status"] == "DELETED"


if __name__ == "__main__":
    asyncio.run(main())

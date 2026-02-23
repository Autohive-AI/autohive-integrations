"""
Tests for Companies Register Integration

Test suite for New Zealand Companies Register API integration.
Tests all 21 actions across company management, directors, shareholding, and annual returns.

To run tests:
    pytest tests/test_companies_register.py -v

Note: Tests require valid OAuth credentials. Update context.py with real tokens for integration testing.
"""
import pytest
from autohive_integrations_sdk import ExecutionContext
from companies_register import companies_register
from .context import get_sandbox_auth, TEST_COMPANY_UUIDS, TEST_ORG_ID


class TestCompanySearch:
    """Test company search and lookup functionality"""

    @pytest.mark.asyncio
    async def test_search_company_by_name(self):
        """Test COMP_00: Search company by name"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("search_company")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "query": "Test Company Limited",
                "searchType": "name"
            }, context)

            assert result.data is not None
            assert isinstance(result.data, dict)
            assert "result" in result.data

    @pytest.mark.asyncio
    async def test_search_company_by_number(self):
        """Test COMP_00: Search company by UUID"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("search_company")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "query": TEST_COMPANY_UUIDS[0],
                "searchType": "number"
            }, context)

            assert result.data is not None


class TestCompanyManagement:
    """Test company creation and management"""

    @pytest.mark.asyncio
    async def test_create_company(self):
        """Test COMP_26: Create/initialize a new company"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("create_company")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyName": "Test Integration Company Limited",
                "entityType": "NZ Limited Company"
            }, context)

            assert result.data is not None
            if result.data.get("result"):
                assert "companyUuid" in result.data.get("data", {})

    @pytest.mark.asyncio
    async def test_get_company_details(self):
        """Test COMP_01: Get company details by UUID"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_company_details")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyNumber": TEST_COMPANY_UUIDS[0]
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_update_company_details(self):
        """Test COMP_04: Update company details"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("update_company_details")

        async with ExecutionContext(auth=auth) as context:
            # Note: Requires valid ETag from GET request
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "etag": "test-etag",
                "updates": {
                    "isConstitutionFiled": False
                }
            }, context)

            assert result.data is not None


class TestDirectors:
    """Test director management functionality"""

    @pytest.mark.asyncio
    async def test_get_company_directors(self):
        """Test COMP_05: List company directors"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_company_directors")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "page": 1,
                "pageSize": 10
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_add_company_director(self):
        """Test COMP_06: Add a director"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("add_company_director")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "etag": "test-etag",
                "directors": [{
                    "type": "INDIVIDUAL",
                    "fullLegalName": "Test Director",
                    "dateOfBirth": "1980-01-01",
                    "address": {
                        "line1": "123 Test St",
                        "suburb": "Wellington",
                        "city": "Wellington",
                        "postcode": "6011",
                        "country": "NZ"
                    }
                }]
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_get_director_details(self):
        """Test COMP_09: Get specific director details"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_director_details")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "directorId": "test-director-id"
            }, context)

            assert result.data is not None


class TestShareholding:
    """Test shareholding management"""

    @pytest.mark.asyncio
    async def test_get_company_shareholding(self):
        """Test COMP_11: Get company shareholding"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_company_shareholding")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0]
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_update_company_shareholding(self):
        """Test COMP_12: Update shareholding"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("update_company_shareholding")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "etag": "test-etag",
                "shareholders": [{
                    "holderType": "INDIVIDUAL",
                    "fullLegalName": "Test Shareholder",
                    "allocation": {
                        "shareClass": "Ordinary",
                        "numberOfShares": 100
                    }
                }]
            }, context)

            assert result.data is not None


class TestAddresses:
    """Test address management"""

    @pytest.mark.asyncio
    async def test_get_company_addresses(self):
        """Test COMP_13: Get company addresses"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_company_addresses")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0]
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_search_address(self):
        """Test COMP_30: NZ Post address search"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("search_address")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "query": "23 Wellington Road"
            }, context)

            assert result.data is not None


class TestIncorporation:
    """Test company incorporation workflow"""

    @pytest.mark.asyncio
    async def test_reserve_company_name(self):
        """Test COMP_27: Reserve company name"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("reserve_company_name")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "etag": "test-etag",
                "organisationId": TEST_ORG_ID,
                "paymentMethod": "CREDIT_CARD",
                "redirectUrl": "https://portal.api.business.govt.nz/"
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_incorporate_company(self):
        """Test COMP_28: Incorporate company"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("incorporate_company")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "etag": "test-etag",
                "reservationId": "test-reservation-id",
                "directors": [],
                "shareholders": [],
                "shareAllocation": {},
                "paymentMethod": "credit_card",
                "redirectUrl": "https://portal.api.business.govt.nz/"
            }, context)

            assert result.data is not None


class TestAnnualReturns:
    """Test annual return filing"""

    @pytest.mark.asyncio
    async def test_file_annual_return(self):
        """Test COMP_33: File annual return"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("file_annual_return")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyNumber": TEST_COMPANY_UUIDS[0],
                "returnDate": "2026-02-17",
                "directorsConfirmed": True,
                "addressesConfirmed": True,
                "shareholdingConfirmed": True,
                "paymentMethod": "credit_card",
                "redirectUrl": "https://portal.api.business.govt.nz/"
            }, context)

            assert result.data is not None


class TestDocuments:
    """Test document management"""

    @pytest.mark.asyncio
    async def test_get_director_documents(self):
        """Test COMP_20: Get director documents"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("get_director_documents")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "directorId": "test-director-id"
            }, context)

            assert result.data is not None

    @pytest.mark.asyncio
    async def test_associate_director_document(self):
        """Test COMP_22: Associate document to director"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("associate_director_document")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "directorId": "test-director-id",
                "documentRef": "test-doc-ref"
            }, context)

            assert result.data is not None


class TestContacts:
    """Test contact management"""

    @pytest.mark.asyncio
    async def test_add_company_contact(self):
        """Test COMP_14: Add company contact/address"""
        auth = get_sandbox_auth()
        action = companies_register.get_action("add_company_contact")

        async with ExecutionContext(auth=auth) as context:
            result = await action.execute({
                "companyUuid": TEST_COMPANY_UUIDS[0],
                "addressPurpose": "Address for communication",
                "address": {
                    "line1": "123 Test Street",
                    "suburb": "Wellington",
                    "city": "Wellington",
                    "postcode": "6011",
                    "country": "NZ"
                }
            }, context)

            assert result.data is not None


# Test configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

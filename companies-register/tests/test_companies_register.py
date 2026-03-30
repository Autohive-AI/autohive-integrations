# Testbed for Companies Register integration
import asyncio
from context import companies_register
from autohive_integrations_sdk import ExecutionContext

# ---------------------------------------------------------------------------
# Configuration — replace with real credentials before running
# ---------------------------------------------------------------------------
# Subscription key from https://portal.api.business.govt.nz/
SUBSCRIPTION_KEY = "your_subscription_key_here"  # nosec B105

# OAuth access token from RealMe authentication (sandbox: use L_testuser)
ACCESS_TOKEN = "your_oauth_token_here"  # nosec B105

# NZBN of a registered company to test against (status 50)
# Example NZBN from MBIE sandbox data
TEST_NZBN = "9429038677085"

# UUID of a pre-incorporated company (status < 50) to test against
TEST_UUID = "b65f62b6-65c5-4141-9cbf-094c4573878c"

# A contact ID (addressId) from the above company for update tests
TEST_CONTACT_ID = "your_contact_id_here"

# ETag from a recent get_company_details call (required for annual return)
TEST_ETAG = "your_etag_here"

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def make_auth():
    return {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_company_details():
    """Get company by NZBN (registered company, status 50)."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action("get_company_details", {"companyUuid": TEST_NZBN}, context)
            print(f"\n[get_company_details] {result.data}")
            assert result.data.get("result") is True
            assert result.data.get("etag") is not None, "ETag missing — required for annual return"
            print(f"  companyName     : {result.data.get('companyName')}")
            print(f"  nzbn            : {result.data.get('nzbn')}")
            print(f"  statusCode      : {result.data.get('companyStatusCode')}")
            print(f"  statusDesc      : {result.data.get('companyStatusDescription')}")
            print(f"  etag            : {result.data.get('etag')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_get_company_details_by_uuid():
    """Get company by UUID (pre-incorporated company)."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action("get_company_details", {"companyUuid": TEST_UUID}, context)
            print(
                f"\n[get_company_details by UUID] {result.data.get('companyName')}"
                f" — status {result.data.get('companyStatusCode')}"
            )
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_get_company_contacts():
    """Get all contacts (addresses, phones, emails) for a company."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "get_company_contacts", {"companyUuid": TEST_NZBN}, context
            )
            print("\n[get_company_contacts]")
            assert result.data.get("result") is True
            addresses = result.data.get("physicalOrPostalAddresses", [])
            phones = result.data.get("phoneContacts", [])
            emails = result.data.get("emailAddresses", [])
            print(f"  addresses       : {len(addresses)}")
            print(f"  phones          : {len(phones)}")
            print(f"  emails          : {len(emails)}")
            print(f"  etag            : {result.data.get('etag')}")
            for addr in addresses:
                print(
                    f"    [{addr.get('addressPurpose')}] {addr.get('address1')},"
                    f" {addr.get('address3')} — id: {addr.get('addressId')}"
                )
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_search_nz_address():
    """Search NZ Post address file by query string to get a DPID."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "search_nz_address",
                {"find": "Level 1 15 Stout Street Wellington", "limit": 5},
                context,
            )
            print("\n[search_nz_address]")
            assert result.data.get("result") is True
            addresses = result.data.get("addresses", [])
            print(f"  found           : {result.data.get('count')} addresses")
            for addr in addresses[:3]:
                print(
                    f"    dpid={addr.get('dpid')} — {addr.get('address1')},"
                    f" {addr.get('address3')} {addr.get('postCode')}"
                )
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_search_nz_address_by_dpid():
    """Look up a specific NZ Post address by DPID."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action("search_nz_address", {"dpid": "1889019"}, context)
            print("\n[search_nz_address by DPID]")
            addresses = result.data.get("addresses", [])
            if addresses:
                a = addresses[0]
                print(f"  dpid={a.get('dpid')} — {a.get('address1')}, {a.get('address3')} {a.get('postCode')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_add_company_contact_address():
    """Add a new physical address contact to a company."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "add_company_contact",
                {
                    "companyUuid": TEST_NZBN,
                    "contactType": "address",
                    "physicalOrPostalAddress": {
                        "addressType": "Physical",
                        "addressPurpose": "Address for Communication",
                        "address1": "Level 1, 15 Stout Street",
                        "address3": "Wellington",
                        "postCode": "6011",
                        "countryCode": "NZ",
                    },
                },
                context,
            )
            print("\n[add_company_contact — address]")
            print(f"  result          : {result.data.get('result')}")
            print(f"  contact         : {result.data.get('contact')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_add_company_contact_address_with_dpid():
    """Add a new address using a DPID (preferred for NZ addresses)."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "add_company_contact",
                {
                    "companyUuid": TEST_NZBN,
                    "contactType": "address",
                    "physicalOrPostalAddress": {
                        "addressType": "Physical",
                        "addressPurpose": "Registered Office Address",
                        "dpid": "1889019",
                    },
                },
                context,
            )
            print("\n[add_company_contact — address with dpid]")
            print(f"  result          : {result.data.get('result')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_add_company_contact_email():
    """Add an email contact to a company."""
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "add_company_contact",
                {
                    "companyUuid": TEST_NZBN,
                    "contactType": "email",
                    "emailAddress": {
                        "emailAddress": "admin@testcompany.co.nz",
                        "emailPurpose": "Email",
                    },
                },
                context,
            )
            print("\n[add_company_contact — email]")
            print(f"  result          : {result.data.get('result')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_update_company_contact():
    """
    Update an existing address contact.
    Requires TEST_CONTACT_ID and TEST_ETAG from get_company_contacts.

    Workflow:
    1. get_company_details  →  store etag
    2. get_company_contacts →  store addressId + contacts etag
    3. update_company_contact with addressId + etag + new address
    """
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "update_company_contact",
                {
                    "companyUuid": TEST_NZBN,
                    "contactId": TEST_CONTACT_ID,
                    "etag": TEST_ETAG,
                    "contactType": "address",
                    "physicalOrPostalAddress": {
                        "addressId": TEST_CONTACT_ID,
                        "addressType": "Physical",
                        "addressPurpose": "Registered Office Address",
                        "dpid": "1889019",
                    },
                },
                context,
            )
            print("\n[update_company_contact]")
            print(f"  result          : {result.data.get('result')}")
            print(f"  message         : {result.data.get('message')}")
            print(f"  new etag        : {result.data.get('etag')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_file_annual_return_direct_debit():
    """
    File an annual return using direct debit.
    Requires TEST_ETAG from a recent get_company_details call.
    """
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "file_annual_return",
                {
                    "companyUuid": TEST_NZBN,
                    "declaration": "I certify that the information contained in this annual return is correct.",
                    "name": {"firstName": "Jane", "lastName": "Smith"},
                    "emailAddress": {"emailAddress": "jane.smith@testcompany.co.nz"},
                    "designation": "Director",
                    "companyDetailsConfirmedCorrectAsOfETag": TEST_ETAG,
                    "paymentMethod": "directDebit",
                },
                context,
            )
            print("\n[file_annual_return — directDebit]")
            print(f"  result          : {result.data.get('result')}")
            print(f"  message         : {result.data.get('message')}")
            print(f"  documentId      : {result.data.get('documentId')}")
            print(f"  status          : {result.data.get('status')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_file_annual_return_credit_card():
    """
    File an annual return using credit card payment.
    Returns a paymentUrl to redirect the user to complete payment.
    In sandbox, use test card 4111 1111 1111 1111.
    """
    async with ExecutionContext(auth=make_auth()) as context:
        try:
            result = await companies_register.execute_action(
                "file_annual_return",
                {
                    "companyUuid": TEST_NZBN,
                    "declaration": "I certify that the information contained in this annual return is correct.",
                    "name": {"firstName": "Jane", "lastName": "Smith"},
                    "emailAddress": {"emailAddress": "jane.smith@testcompany.co.nz"},
                    "designation": "Director",
                    "companyDetailsConfirmedCorrectAsOfETag": TEST_ETAG,
                    "paymentMethod": "creditCard",
                    "redirectUrl": "https://portal.api.business.govt.nz/",
                    "phoneContact": {
                        "phoneNumber": "211234567",
                        "countryCode": "64",
                        "phonePurpose": "Mobile",
                    },
                },
                context,
            )
            print("\n[file_annual_return — creditCard]")
            print(f"  result          : {result.data.get('result')}")
            print(f"  message         : {result.data.get('message')}")
            print(f"  paymentUrl      : {result.data.get('paymentUrl')}")
            return result
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


# ---------------------------------------------------------------------------
# Full workflow test — get company → get contacts → update address
# ---------------------------------------------------------------------------


async def test_address_update_workflow():
    """
    End-to-end workflow:
    1. Get company details (store etag)
    2. Search for new address (get dpid)
    3. Get company contacts (get addressId + contacts etag)
    4. Update the registered office address
    """
    print(f"\n{'=' * 60}")
    print("WORKFLOW: Update Registered Office Address")
    print("=" * 60)

    async with ExecutionContext(auth=make_auth()) as context:
        try:
            # Step 1: Get company details
            print("\nStep 1: Get company details...")
            details = await companies_register.execute_action(
                "get_company_details", {"companyUuid": TEST_NZBN}, context
            )
            company_name = details.data.get("companyName")
            print(f"  Company: {company_name}")

            # Step 2: Search for new address
            print("\nStep 2: Search NZ Post for new address...")
            addr_search = await companies_register.execute_action(
                "search_nz_address",
                {"find": "15 Stout Street Wellington", "limit": 3},
                context,
            )
            addresses = addr_search.data.get("addresses", [])
            if not addresses:
                print("  No addresses found — skipping update")
                return None
            addr = addresses[0]
            addr_line = f"{addr.get('address1')}, {addr.get('address3')}"
            print(f"  Selected: {addr_line}")

            # Step 3: Get contacts to find addressId
            print("\nStep 3: Get company contacts...")
            contacts_result = await companies_register.execute_action(
                "get_company_contacts", {"companyUuid": TEST_NZBN}, context
            )
            contacts_etag = contacts_result.data.get("etag")
            physical_addresses = contacts_result.data.get("physicalOrPostalAddresses", [])
            registered_office = next(
                (a for a in physical_addresses if a.get("addressPurpose") == "Registered Office Address"),
                None,
            )
            if not registered_office:
                print("  No Registered Office Address found — skipping update")
                return None
            address_id = registered_office.get("addressId")
            print(f"  Found Registered Office addressId: {address_id}")
            print(f"  Contacts ETag: {contacts_etag}")

            # Step 4: Update the address
            print("\nStep 4: Updating address...")
            update_result = await companies_register.execute_action(
                "update_company_contact",
                {
                    "companyUuid": TEST_NZBN,
                    "contactId": address_id,
                    "etag": contacts_etag,
                    "contactType": "address",
                    "physicalOrPostalAddress": {
                        "addressId": address_id,
                        "addressType": "Physical",
                        "addressPurpose": "Registered Office Address",
                        "address1": addr.get("address1"),
                        "address3": addr.get("address3"),
                        "postCode": addr.get("postCode"),
                        "countryCode": "NZ",
                        "effectiveDate": "2026-03-10T00:00:00Z",
                    },
                },
                context,
            )
            print(f"  result  : {update_result.data.get('result')}")
            print(f"  message : {update_result.data.get('message')}")
            return update_result

        except Exception as e:
            print(f"  ERROR: {e}")
            return None


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


async def run_all_tests():
    print("=" * 60)
    print("Companies Register Integration Tests")
    print("Sandbox: https://api.business.govt.nz/sandbox/")
    print("=" * 60)

    passed = 0
    failed = 0

    tests = [
        ("Get Company Details (NZBN)", test_get_company_details),
        ("Get Company Details (UUID)", test_get_company_details_by_uuid),
        ("Get Company Contacts", test_get_company_contacts),
        ("Search NZ Address (query)", test_search_nz_address),
        ("Search NZ Address (DPID)", test_search_nz_address_by_dpid),
        ("Add Contact — address (lines)", test_add_company_contact_address),
        ("Add Contact — address (dpid)", test_add_company_contact_address_with_dpid),
        ("Add Contact — email", test_add_company_contact_email),
        ("Update Contact", test_update_company_contact),
        ("File Annual Return (directDebit)", test_file_annual_return_direct_debit),
        ("File Annual Return (creditCard)", test_file_annual_return_credit_card),
        ("Workflow: Address Update", test_address_update_workflow),
    ]

    for name, fn in tests:
        try:
            result = await fn()
            if result is not None:
                print(f"  PASS  {name}")
                passed += 1
            else:
                print(f"  SKIP  {name}  (returned None — check credentials/test data)")
                failed += 1
        except Exception as e:
            print(f"  FAIL  {name}  — {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

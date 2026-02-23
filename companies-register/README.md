# Companies Register Integration

Comprehensive integration for the New Zealand Companies Register API (MBIE) to manage company information, directors, shareholding details, and file annual returns.

## Overview

This integration provides access to the Companies Office API for managing New Zealand companies, including:
- Company search and registration
- Director management
- Shareholding information
- Address management
- Annual return filing
- Document management

## Features

### Company Management
- **Search Company**: Check company name availability or search by number
- **Get Company Details**: Retrieve detailed company information
- **Create Company**: Incorporate a new company
- **Update Company Details**: Modify existing company information
- **Reserve Company Name**: Reserve a company name before incorporation

### Director Management
- **Get Company Directors**: List all directors with pagination
- **Add Company Director**: Appoint a new director
- **Update Company Director**: Modify director details
- **Remove Company Director**: Remove a director from the company
- **Get Director Details**: Retrieve specific director information
- **Get Director Documents**: Access director-related documents
- **Associate Director Document**: Link documents to directors

### Shareholding
- **Get Company Shareholding**: View shareholding structure
- **Update Company Shareholding**: Modify share allocations
- **Get Shareholder Details**: Retrieve shareholder information
- **Get Shareholder Documents**: Access shareholding documents
- **Get Shareholders Special Resolution**: View special resolutions

### Addresses
- **Get Company Addresses**: Retrieve registered addresses
- **Search Address**: NZ Post address search with DPID support

### Annual Returns
- **File Annual Return**: Submit annual returns with payment

### Contact Management
- **Add Company Contact**: Add contact information to a company

## Authentication

This integration uses **dual authentication**:

### 1. Azure API Management Subscription Key
Required for all API calls.

**How to get it:**
1. Visit https://portal.api.business.govt.nz/
2. Sign up or log in
3. Subscribe to the Companies Register API product
4. Copy your subscription key from the profile page

### 2. RealMe OAuth 2.0 Access Token
Required for authenticated actions (creating companies, filing returns, etc.)

**How it works:**
- Users authenticate via RealMe (New Zealand's identity verification service)
- Autohive platform handles the OAuth flow automatically
- Access token is injected into requests by the platform

**RealMe OAuth Configuration:**
- **Authorization URL**: `https://api.business.govt.nz/oauth/authorize`
- **Token URL**: `https://api.business.govt.nz/oauth/token`
- **Required Scopes**:
  - `NZBNCO:manage` - Full access to manage companies, directors, shareholding, and file returns

## Setup & Authentication

### Step 1: Get API Subscription Key
1. Go to https://portal.api.business.govt.nz/
2. Create an account or sign in
3. Navigate to "Products" and subscribe to "Companies Register API"
4. Copy your **Primary Key** (this is your `subscription_key`)

### Step 2: Connect via Autohive
1. In Autohive, click "Connect" for Companies Register integration
2. You'll be redirected to **RealMe login**
3. Log in with your RealMe credentials (business or personal account)
4. Authorize Autohive to access Companies Register on your behalf
5. Enter your **API Subscription Key** when prompted

### Step 3: Start Using Actions
Once connected, all API calls will include both:
- `Ocp-Apim-Subscription-Key` header (subscription key)
- `Authorization: Bearer {token}` header (OAuth access token)

## Environment Configuration

### Sandbox (Default - Testing)
```python
BASE_URL_V2 = "https://api.business.govt.nz/sandbox/companies-office/companies-register/companies/v2"
BASE_URL = "https://api.business.govt.nz/sandbox/companies-register"
```

**Sandbox Test Data:**
- Test Company Number: `137860`
- Test Organisation ID: `137860`
- Test Payment: Credit Card `4111 1111 1111 1111` (any expiry/CVC)

### Production (After Approval)
To switch to production:
1. Update URLs in `companies_register.py`:
   ```python
   BASE_URL_V2 = "https://api.business.govt.nz/gateway/companies-office/companies-register/companies/v2"
   BASE_URL = "https://api.business.govt.nz/services/v4/companies-register"
   ```
2. Use your **production subscription key**
3. Ensure RealMe OAuth is configured for production environment

## Available Actions

| Action | Description | Auth Required |
|--------|-------------|---------------|
| `search_company` | Search by name or number | Subscription Key |
| `get_company_details` | Get detailed company info | Both |
| `get_company_directors` | List company directors | Both |
| `add_company_director` | Appoint new director | Both |
| `update_company_director` | Modify director details | Both |
| `remove_company_director` | Remove a director | Both |
| `get_director_details` | Get specific director info | Both |
| `get_director_documents` | List director documents | Both |
| `associate_director_document` | Link documents | Both |
| `get_company_addresses` | Get registered addresses | Both |
| `get_company_shareholding` | View shareholding structure | Both |
| `update_company_shareholding` | Modify share allocations | Both |
| `update_company_details` | Update company information | Both |
| `add_company_contact` | Add contact information | Both |
| `reserve_company_name` | Reserve a company name | Both |
| `incorporate_company` | Create a new company | Both |
| `get_shareholder_details` | Get shareholder info | Both |
| `get_shareholder_documents` | List shareholder documents | Both |
| `get_shareholders_special_resolution` | View special resolutions | Both |
| `search_address` | NZ Post address search | Subscription Key |
| `file_annual_return` | Submit annual return | Both |

## Usage Examples

### Search for a Company
```python
{
  "action": "search_company",
  "inputs": {
    "query": "My Company Ltd",
    "searchType": "name"
  }
}
```

### Get Company Details
```python
{
  "action": "get_company_details",
  "inputs": {
    "companyNumber": "137860"
  }
}
```

### Add a Director
```python
{
  "action": "add_company_director",
  "inputs": {
    "companyUuid": "company-uuid-here",
    "etag": "etag-from-get-request",
    "directors": [
      {
        "type": "INDIVIDUAL",
        "fullLegalName": "John Smith",
        "dateOfBirth": "1980-01-15",
        "address": {
          "line1": "123 Main St",
          "suburb": "Wellington",
          "city": "Wellington",
          "postcode": "6011",
          "country": "NZ"
        }
      }
    ]
  }
}
```

### Reserve Company Name
```python
{
  "action": "reserve_company_name",
  "inputs": {
    "companyUuid": "new-company-uuid",
    "etag": "etag-value",
    "organisationId": "137860",
    "paymentMethod": "CREDIT_CARD",
    "redirectUrl": "https://portal.api.business.govt.nz/"
  }
}
```

## Testing

### Running Tests
```bash
# Install dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_companies_register.py::TestCompanySearch -v
```

### Test Configuration
Update `tests/test_companies_register.py` with your credentials:
```python
SANDBOX_AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {
        "subscription_key": "your_sandbox_subscription_key",
        "access_token": "your_sandbox_access_token"
    }
}
```

## Error Handling

The integration includes comprehensive error handling:
- Network errors (timeouts, connection issues)
- API errors (400, 401, 403, 404, 409, 500)
- Validation errors (missing required fields, invalid formats)
- Concurrency errors (ETag mismatches)
- Payment errors (Direct Debit not enabled, invalid payment methods)

## Rate Limits

Companies Register API rate limits apply:
- **Standard**: 100 requests per minute
- **Burst**: Up to 200 requests per minute for short periods

## Important Notes

### Concurrency Control
Many write operations require an **ETag** value:
1. First, perform a GET request to retrieve the current ETag
2. Include this ETag in your update/delete request
3. If another update occurred, you'll receive a 409 Conflict error

### Payment Requirements
Operations like name reservation and incorporation require payment:
- **Sandbox**: Use test card `4111 1111 1111 1111`
- **Production**: Real payment methods required
- Supported: Credit Card, Direct Debit

### RealMe Identity Verification
Some operations require specific RealMe identity strength:
- **Verified identity**: Company incorporation, director appointments
- **Guest access**: Company search (two-legged authentication)

## API Documentation

- **Companies Register API**: https://api.business.govt.nz/companies-register
- **API Portal**: https://portal.api.business.govt.nz/
- **RealMe Information**: https://www.realme.govt.nz/

## Support

For issues with:
- **This integration**: Contact Autohive support
- **API access**: Contact MBIE at support@api.business.govt.nz
- **RealMe login**: Visit https://www.realme.govt.nz/support

## Version

- **Version**: 1.0.0
- **Last Updated**: February 2025
- **API Version**: V2 (Companies), V4 (Legacy endpoints)

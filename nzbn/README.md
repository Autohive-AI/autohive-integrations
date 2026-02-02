# NZBN Integration

Integration with the New Zealand Business Number (NZBN) API for searching and retrieving business entity information from the NZBN Register.

## Overview

The NZBN (New Zealand Business Number) is a unique 13-digit identifier for NZ businesses. This integration provides access to the NZBN Register API, allowing you to:

- Search for businesses by name, trading name, or NZBN
- Retrieve detailed entity information
- Get addresses, roles, trading names, and GST numbers
- Track changes to business registrations

## Authentication

This integration uses Autohive's pre-configured NZBN API credentials with 2-legged OAuth (Client Credentials flow). **No user configuration required** - credentials are managed by Autohive.

### Deployment Configuration

The following environment variables must be set at deployment time:

| Variable | Description |
|----------|-------------|
| `NZBN_CLIENT_ID` | OAuth Client ID (Autohive's registered NZBN app) |
| `NZBN_CLIENT_SECRET` | OAuth Client Secret |
| `NZBN_SUBSCRIPTION_KEY` | NZBN API Subscription Key |

### Security Model

- OAuth credentials are injected server-side at deployment, not distributed to users
- Tokens are cached with automatic refresh before expiry (60-second buffer)
- Zero-config experience for end users

## Actions

### search_entities

Search the NZBN directory by name, trading name, NZBN, or company number.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `search_term` | string | Yes | Text to search for |
| `entity_status` | string | No | Filter by status (Registered, InLiquidation, etc.) |
| `entity_type` | string | No | Filter by type (NZCompany, SoleTrader, Partnership, etc.) |
| `page` | integer | No | Page number (zero-indexed, default: 0) |
| `page_size` | integer | No | Results per page (default: 25, max: 100) |

**Example:**
```json
{
  "search_term": "Xero",
  "entity_type": "NZCompany",
  "page_size": 10
}
```

### get_entity

Retrieve detailed information about a specific business entity.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

**Example:**
```json
{
  "nzbn": "9429041525746"
}
```

### get_entity_addresses

Retrieve addresses for a business entity.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |
| `address_type` | string | No | Filter by type (RegisteredOffice, Physical, Postal) |

### get_entity_roles

Retrieve roles/officers (directors, shareholders) for an entity.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

### get_entity_trading_names

Retrieve trading names for a business entity.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

### get_company_details

Retrieve company-specific details for NZ companies.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

### get_entity_gst_numbers

Retrieve GST numbers registered to a business.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

### get_entity_industry_classifications

Retrieve industry classification codes (ANZSIC) for an entity.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nzbn` | string | Yes | The 13-digit NZBN identifier |

### get_changes

Search for entities that have changed within a time period.

**Inputs:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `change_event_type` | string | Yes | Type of change (NewRegistration, NameChange, StatusChange, etc.) |
| `start_date` | string | No | Start date (ISO format: YYYY-MM-DD) |
| `end_date` | string | No | End date (ISO format: YYYY-MM-DD) |
| `page` | integer | No | Page number (zero-indexed) |
| `page_size` | integer | No | Results per page (max: 100) |

## Entity Types

| Code | Description |
|------|-------------|
| LTD | NZ Limited Company |
| ULTD | NZ Unlimited Company |
| COOP | NZ Co-operative Company |
| ASIC | Overseas ASIC Company |
| NON_ASIC | Overseas Non-ASIC Company |
| Sole_Trader | Sole Trader |
| Partnership | Partnership |
| Trading_Trust | Trust |
| B | Building Society |
| I | Incorporated Society |
| D | Credit Union |
| F | Friendly Society |
| N | Industrial & Provident Society |
| S | Special Body |
| T | Charitable Trust |
| Y | Limited Partnership (NZ) |
| Z | Limited Partnership (Overseas) |

## Entity Status Codes

| Code | Description |
|------|-------------|
| Registered | Active and registered |
| VoluntaryAdministration | In voluntary administration |
| InReceivership | In receivership |
| InLiquidation | In liquidation |
| InStatutoryAdministration | In statutory administration |
| Inactive | Inactive |
| RemovedClosed | Removed or closed |

## Testing

```bash
# Run validation tests only (no API credentials needed)
cd nzbn/tests
python test_nzbn.py --quick

# Run full test suite (requires API credentials)
cd nzbn/tests
python test_nzbn.py
```

## API Documentation

- [NZBN API Portal](https://portal.api.business.govt.nz/api/nzbn)
- [NZBN Website](https://www.nzbn.govt.nz/)
- [API Support](https://support.api.business.govt.nz/)

## Rate Limits

The NZBN API is free to use but may have rate limits. Check the API portal for current limits.

## Notes

- Some PBD (Primary Business Data) may be private if set by the business
- ETags can be used for efficient data retrieval (If-None-Match header)

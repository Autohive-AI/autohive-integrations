# Retail Express Integration

Integration with the Retail Express POS and retail management platform REST API.

## Overview

Retail Express is an Australian-based point-of-sale (POS) and retail management system. This integration allows you to manage products, customers, orders, and outlets through the Retail Express REST API v2.1.

## Authentication

This integration uses **API Key + Bearer Token** authentication:

1. Obtain an API Key from your Retail Express client
2. The integration automatically exchanges the API key for a Bearer token
3. Tokens expire after 60 minutes and are automatically refreshed

### Getting Your API Key

Contact the Retail Express client you wish to integrate with to request an API Key. Each API Key is unique to a specific client and only provides access to that client's data.

For sandbox/testing access, contact:
- **Sales**: 1300 732 618 (Australia)
- **Support**: support@retailexpress.com.au

## Actions

### Products

| Action | Description |
|--------|-------------|
| `list_products` | Retrieve a paginated list of products |
| `get_product` | Get details of a specific product by ID |

### Customers

| Action | Description |
|--------|-------------|
| `list_customers` | Retrieve a paginated list of customers |
| `get_customer` | Get details of a specific customer by ID |
| `create_customer` | Create a new customer |
| `update_customer` | Update an existing customer |

### Orders

| Action | Description |
|--------|-------------|
| `list_orders` | Retrieve a paginated list of orders |
| `get_order` | Get details of a specific order by ID |

### Outlets

| Action | Description |
|--------|-------------|
| `list_outlets` | Retrieve a list of all store outlets |
| `get_outlet` | Get details of a specific outlet by ID |

## Rate Limits

The Retail Express API has the following rate limits:

- **Per minute**: 300 requests (average 5 requests/second)
- **Daily**: 100,000 requests per client/API key

## Pagination

All list endpoints support pagination with the following parameters:

- `page_number`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 250)

## API Reference

- [Retail Express API Documentation](https://developer.retailexpress.com.au/getting-started)
- API Version: v2.1 (Latest)
- Base URL: `https://api.retailexpress.com.au/v2.1/`

## Example Usage

### List Products with Filtering

```python
# List products updated since a specific date
inputs = {
    "page_size": 50,
    "updated_since": "2024-01-01T00:00:00+10:00"
}
```

### Create a Customer

```python
inputs = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+61 2 1234 5678",
    "billing_address": {
        "address_line_1": "123 Main St",
        "suburb": "Sydney",
        "state": "NSW",
        "postcode": "2000",
        "country": "Australia"
    }
}
```

## Notes

- All date/time values are in Sydney (AEST/ADST) timezone
- Date format: `yyyy-mm-ddThh:mm:ss+TZD` (e.g., `2024-01-15T14:30:00+10:00`)
- The API returns JSON responses with `data` containing the actual payload

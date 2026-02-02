# Viator Integration

## Overview
This integration provides access to the Viator Partner API, allowing you to search, book, and manage tours and experiences from Viator's extensive catalog of over 300,000+ products worldwide.

## Authentication
This integration uses API key authentication. You'll need to obtain an API key from Viator:

1. Sign up for a Viator Partner account
2. Request API access through the Viator Partner Portal
3. Generate your API key (exp-api-key)
4. Update the `API_KEY` constant in `viator.py` with your actual API key

**Note**: Replace `YOUR_VIATOR_API_KEY_HERE` in the `viator.py` file with your actual Viator Partner API key before using this integration.

## Available Actions

### 1. Search Products
Search for tours and experiences by destination and filters.
- **Input**: destination_id (required), start_date, end_date, currency, pagination
- **Output**: List of products with pricing, ratings, and basic details

### 2. Get Product Details
Retrieve comprehensive information about a specific product.
- **Input**: product_code (required), currency
- **Output**: Full product details including description, images, inclusions, exclusions, meeting point, and cancellation policy

### 3. Check Availability
Check real-time availability and pricing for a product on a specific date.
- **Input**: product_code, travel_date (required), currency, adult_count, child_count
- **Output**: Available product options with pricing and start times

### 4. Calculate Price
Calculate the exact price for a booking based on travelers and options.
- **Input**: product_code, product_option_code, travel_date (required), currency, traveler counts
- **Output**: Detailed price breakdown including subtotal, total, and per-traveler pricing

### 5. Create Booking
Create a new booking for a tour or experience.
- **Input**: product details, travel date, traveler information, booker details (required)
- **Output**: Booking reference, status, voucher URL, and confirmation details

### 6. Get Booking
Retrieve details of an existing booking.
- **Input**: booking_reference (required)
- **Output**: Complete booking information including status, travelers, and voucher

### 7. Cancel Booking
Cancel an existing booking and get refund information.
- **Input**: booking_reference (required), cancellation_reason_code
- **Output**: Cancellation status, refund amount, and fees

### 8. Get Destinations
Retrieve the list of available destinations in the Viator catalog.
- **Input**: parent_destination_id (optional)
- **Output**: List of destinations with IDs, names, types, and timezone information

### 9. Get Product Reviews
Retrieve customer reviews and ratings for a specific product.
- **Input**: product_code (required), pagination options
- **Output**: Reviews with ratings, text, reviewer information, and dates

## API Environment
- **Production**: `https://api.viator.com/partner`
- **Sandbox**: `https://api.sandbox.viator.com/partner` (for testing)

The integration is currently configured to use the production environment. To switch to sandbox for testing, update the `BASE_URL` in `viator.py`.

## Common Use Cases

### Travel Booking Platforms
- Integrate tours and experiences into your travel booking website
- Provide customers with activity options at their destination
- Handle complete booking lifecycle from search to cancellation

### Travel Agencies
- Search and book activities for clients
- Manage bookings and retrieve vouchers
- Access real-time availability and pricing

### Destination Marketing
- Showcase available tours and experiences
- Display reviews and ratings to build trust
- Redirect users to complete bookings

## Error Handling
The integration handles various API errors including:
- Invalid API keys (401 Unauthorized)
- Product not found (404)
- Availability issues
- Booking failures

## Rate Limits
Please refer to Viator's API documentation for current rate limits and best practices for API usage.

## Support
For API access, technical support, or questions:
- Email: affiliateapi@tripadvisor.com
- Documentation: https://docs.viator.com/partner-api/
- Partner Resources: https://partnerresources.viator.com/

## Version
Current version: 1.0.0

## Notes
- All dates should be in YYYY-MM-DD format
- Prices are returned in the requested currency
- Bookings require complete traveler information
- Always check availability before creating a booking
- Review cancellation policies before booking

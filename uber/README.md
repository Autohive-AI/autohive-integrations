# Uber Ride Requests Integration

Uber Ride Requests integration for Autohive, enabling ride booking, price estimates, tracking, and receipt retrieval.

## Features

- **Get Products**: List available Uber products (UberX, UberXL, Black, etc.) at a location
- **Price Estimates**: Get fare estimates for trips between two locations
- **Time Estimates**: Get ETA for driver arrival at pickup location
- **Request Rides**: Book Uber rides on behalf of users
- **Track Rides**: Monitor ride status and driver location
- **Receipts**: Retrieve receipts for completed rides
- **User Profile**: Access user profile and ride history

## Authentication

This integration uses OAuth 2.0 Authorization Code flow. Users must authorize the application to access their Uber account.

### Required Scopes

| Scope | Description | Type |
|-------|-------------|------|
| `profile` | Access user's basic profile information | General |
| `history` | Access user's ride history | General |
| `places` | Access saved places (home, work) | General |
| `request` | Request rides on behalf of user | Privileged |
| `request_receipt` | Get receipts for rides | Privileged |
| `offline_access` | Refresh tokens for offline use | General |

> **Note**: The `request` and `request_receipt` scopes are privileged and require Uber approval for production use.

## Actions

### get_products

Get available Uber products at a given location.

**Inputs:**
- `latitude` (required): Location latitude
- `longitude` (required): Location longitude

**Outputs:**
- `products`: Array of available Uber products with pricing details

---

### get_price_estimate

Get price estimates for a trip.

**Inputs:**
- `start_latitude` (required): Pickup latitude
- `start_longitude` (required): Pickup longitude
- `end_latitude` (required): Destination latitude
- `end_longitude` (required): Destination longitude
- `seat_count` (optional): Seats for POOL (max 2)

**Outputs:**
- `prices`: Array of price estimates per product

---

### get_time_estimate

Get ETA estimates for products at a location.

**Inputs:**
- `start_latitude` (required): Pickup latitude
- `start_longitude` (required): Pickup longitude
- `product_id` (optional): Filter by specific product

**Outputs:**
- `times`: Array of ETA estimates per product

---

### get_ride_estimate

Get detailed fare estimate before booking.

**Inputs:**
- `product_id` (required): Product ID (e.g., UberX)
- `start_latitude` (required): Pickup latitude
- `start_longitude` (required): Pickup longitude
- `end_latitude` (required): Destination latitude
- `end_longitude` (required): Destination longitude
- `seat_count` (optional): Seats for POOL

**Outputs:**
- `estimate`: Detailed fare estimate with fare_id for upfront pricing

---

### request_ride

Request an Uber ride.

**Inputs:**
- `product_id` (required): Product ID
- `start_latitude` (required): Pickup latitude
- `start_longitude` (required): Pickup longitude
- `end_latitude` (required): Destination latitude
- `end_longitude` (required): Destination longitude
- `start_address` (optional): Pickup address string
- `end_address` (optional): Destination address string
- `fare_id` (optional): Fare ID for upfront pricing
- `payment_method_id` (optional): Payment method ID

**Outputs:**
- `request_id`: Unique ride request ID
- `status`: Current status (processing, accepted, arriving, etc.)
- `eta`: Driver ETA in minutes
- `driver`: Driver details when assigned
- `vehicle`: Vehicle details when assigned

---

### get_ride_status

Get current status of an active ride.

**Inputs:**
- `request_id` (required): Ride request ID

**Outputs:**
- `ride`: Full ride details including status, driver, vehicle, location

---

### get_ride_map

Get tracking map URL for active ride.

**Inputs:**
- `request_id` (required): Ride request ID

**Outputs:**
- `href`: URL to real-time tracking map

---

### cancel_ride

Cancel an active ride request.

**Inputs:**
- `request_id` (required): Ride request ID

**Outputs:**
- `result`: Success/failure status

---

### get_ride_receipt

Get receipt for completed ride.

**Inputs:**
- `request_id` (required): Completed ride request ID

**Outputs:**
- `receipt`: Receipt details (charges, distance, duration, etc.)

---

### get_user_profile

Get authenticated user's profile.

**Outputs:**
- `user`: User profile (first name, email, picture, etc.)

---

### get_ride_history

Get user's past rides.

**Inputs:**
- `limit` (optional): Number of rides (max 50, default 10)
- `offset` (optional): Pagination offset

**Outputs:**
- `history`: Array of past rides
- `count`: Total ride count

---

### get_payment_methods

Get user's payment methods.

**Outputs:**
- `payment_methods`: Array of payment methods
- `last_used`: ID of last used method

## Ride Statuses

| Status | Description |
|--------|-------------|
| `processing` | Request is being processed |
| `no_drivers_available` | No drivers available |
| `accepted` | Driver accepted the request |
| `arriving` | Driver is arriving at pickup |
| `in_progress` | Ride is in progress |
| `driver_canceled` | Driver canceled |
| `rider_canceled` | Rider canceled |
| `completed` | Ride completed |

## Example Workflow

```
1. get_products (latitude, longitude)
   → Get available products at pickup location

2. get_price_estimate (start, end)
   → Show user price options

3. get_ride_estimate (product_id, start, end)
   → Get upfront fare and fare_id

4. request_ride (product_id, start, end, fare_id)
   → Book the ride, get request_id

5. get_ride_status (request_id)
   → Poll for status updates

6. get_ride_receipt (request_id)
   → Get receipt after completion
```

## Sandbox Testing

Use the sandbox environment for testing:
- Base URL: `https://sandbox-api.uber.com/v1.2`
- Rides auto-progress through statuses

## API Documentation

- [Uber Riders API](https://developer.uber.com/docs/riders/introduction)
- [API Reference](https://developer.uber.com/docs/riders/references/api)
- [Authentication Guide](https://developer.uber.com/docs/riders/guides/authentication/introduction)

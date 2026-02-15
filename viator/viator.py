from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any, List
import os
from pathlib import Path

# Load config from the integration directory
config_path = Path(__file__).parent / "config.json"
viator = Integration.load(config_path)


def get_viator_api(context: ExecutionContext) -> 'ViatorAPI':
    """Get ViatorAPI instance with credentials from context"""
    if not hasattr(context, 'auth') or not context.auth:
        raise ValueError("No authentication credentials provided in context")

    # Try to get api_key from credentials first (for backwards compatibility), then directly
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key") or context.auth.get("api_key")

    if not api_key:
        raise ValueError("Missing required api_key in credentials")

    return ViatorAPI(api_key)


class ViatorAPI:
    """Helper class for Viator Partner API operations"""
    # Production base URL: "https://api.viator.com/partner"
    # Sandbox base URL for testing
    BASE_URL = "https://api.sandbox.viator.com/partner"

    def __init__(self, api_key: str):
        """Initialize with API key from context"""
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Viator API requests"""
        return {
            "exp-api-key": self.api_key,
            "Accept": "application/json;version=2.0",
            "Accept-Language": "en-US",
            "Content-Type": "application/json"
        }

    async def search_products(self, context: ExecutionContext, destination_id: int,
                             start_date: str = None, end_date: str = None,
                             currency: str = "USD", page: int = 1,
                             page_size: int = 20) -> Dict[str, Any]:
        """Search for products by destination and filters"""
        url = f"{self.BASE_URL}/products/search"

        data = {
            "currency": currency,
            "pagination": {
                "offset": (page - 1) * page_size,
                "limit": page_size
            },
            "filtering": {
                "destination": destination_id
            }
        }

        if start_date:
            data["filtering"]["startDate"] = start_date
        if end_date:
            data["filtering"]["endDate"] = end_date

        return await context.fetch(url, method="POST", json=data, headers=self._get_headers())

    async def get_product_details(self, context: ExecutionContext, product_code: str,
                                  currency: str = "USD") -> Dict[str, Any]:
        """Get detailed information about a specific product"""
        url = f"{self.BASE_URL}/products/{product_code}"
        params = {"currency": currency}
        return await context.fetch(url, params=params, headers=self._get_headers())

    async def check_availability(self, context: ExecutionContext, product_code: str,
                                travel_date: str, currency: str = "USD",
                                adult_count: int = 1, child_count: int = 0) -> Dict[str, Any]:
        """Check real-time availability and pricing for a product"""
        url = f"{self.BASE_URL}/availability/check"

        data = {
            "productCode": product_code,
            "travelDate": travel_date,
            "currency": currency,
            "paxMix": []
        }

        if adult_count > 0:
            data["paxMix"].append({
                "ageBand": "ADULT",
                "numberOfTravelers": adult_count
            })

        if child_count > 0:
            data["paxMix"].append({
                "ageBand": "CHILD",
                "numberOfTravelers": child_count
            })

        return await context.fetch(url, method="POST", json=data, headers=self._get_headers())

    async def calculate_price(self, context: ExecutionContext, product_code: str,
                             product_option_code: str, travel_date: str,
                             currency: str = "USD", adult_count: int = 1,
                             child_count: int = 0, infant_count: int = 0) -> Dict[str, Any]:
        """Calculate the total price for a booking"""
        url = f"{self.BASE_URL}/booking/calculateprice"

        data = {
            "productCode": product_code,
            "productOptionCode": product_option_code,
            "travelDate": travel_date,
            "currency": currency,
            "paxMix": []
        }

        if adult_count > 0:
            data["paxMix"].append({
                "ageBand": "ADULT",
                "numberOfTravelers": adult_count
            })

        if child_count > 0:
            data["paxMix"].append({
                "ageBand": "CHILD",
                "numberOfTravelers": child_count
            })

        if infant_count > 0:
            data["paxMix"].append({
                "ageBand": "INFANT",
                "numberOfTravelers": infant_count
            })

        return await context.fetch(url, method="POST", json=data, headers=self._get_headers())

    async def create_booking(self, context: ExecutionContext, product_code: str,
                           product_option_code: str, travel_date: str,
                           traveler_details: List[Dict[str, Any]],
                           booker_details: Dict[str, Any],
                           start_time: str = None, currency: str = "USD") -> Dict[str, Any]:
        """Create a new booking"""
        url = f"{self.BASE_URL}/booking/book"

        data = {
            "productCode": product_code,
            "productOptionCode": product_option_code,
            "travelDate": travel_date,
            "currency": currency,
            "travelers": traveler_details,
            "booker": booker_details
        }

        if start_time:
            data["startTime"] = start_time

        return await context.fetch(url, method="POST", json=data, headers=self._get_headers())

    async def get_booking(self, context: ExecutionContext, booking_reference: str) -> Dict[str, Any]:
        """Get booking details"""
        url = f"{self.BASE_URL}/bookings/{booking_reference}"
        return await context.fetch(url, headers=self._get_headers())

    async def cancel_booking(self, context: ExecutionContext, booking_reference: str,
                           cancellation_reason_code: str = None) -> Dict[str, Any]:
        """Cancel a booking"""
        # First get cancellation quote
        quote_url = f"{self.BASE_URL}/bookings/{booking_reference}/cancel-quote"
        quote_data = {}

        if cancellation_reason_code:
            quote_data["reasonCode"] = cancellation_reason_code

        quote = await context.fetch(quote_url, method="POST", json=quote_data, headers=self._get_headers())

        # Then perform the cancellation
        cancel_url = f"{self.BASE_URL}/bookings/{booking_reference}/cancel"
        cancel_data = {
            "cancellationReasonCode": cancellation_reason_code or "Customer Request"
        }

        return await context.fetch(cancel_url, method="POST", json=cancel_data, headers=self._get_headers())

    async def get_destinations(self, context: ExecutionContext,
                              parent_destination_id: int = None) -> Dict[str, Any]:
        """Get list of destinations"""
        url = f"{self.BASE_URL}/taxonomy/destinations"
        params = {}

        if parent_destination_id:
            params["parentId"] = parent_destination_id

        return await context.fetch(url, params=params, headers=self._get_headers())

    async def get_product_reviews(self, context: ExecutionContext, product_code: str,
                                 page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Get reviews for a product"""
        url = f"{self.BASE_URL}/products/{product_code}/reviews"
        params = {
            "page": page,
            "pageSize": page_size
        }
        return await context.fetch(url, params=params, headers=self._get_headers())


@viator.action("search_products")
class SearchProducts(ActionHandler):
    """
    Action that searches for tours and experiences products.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        destination_id = inputs['destination_id']
        start_date = inputs.get('start_date')
        end_date = inputs.get('end_date')
        currency = inputs.get('currency', 'USD')
        page = inputs.get('page', 1)
        page_size = inputs.get('page_size', 20)

        result = await api.search_products(
            context, destination_id, start_date, end_date,
            currency, page, page_size
        )

        # Transform the response
        products = []
        for product in result.get('products', []):
            # Convert duration object to string
            duration = product.get('duration', {})
            if isinstance(duration, dict):
                if 'fixedDurationInMinutes' in duration:
                    duration_str = f"{duration['fixedDurationInMinutes']} minutes"
                elif 'variableDurationFromMinutes' in duration:
                    duration_str = f"{duration['variableDurationFromMinutes']}-{duration['variableDurationToMinutes']} minutes"
                else:
                    duration_str = "Duration not specified"
            else:
                duration_str = str(duration) if duration else "Duration not specified"

            # Get image URL with fallback
            images = product.get('images', [])
            if images and len(images) > 0:
                image_url = images[0].get('imageUrl') or ""
            else:
                image_url = ""

            # Get rating with fallback
            rating = product.get('reviews', {}).get('averageRating')
            if rating is None:
                rating = 0.0

            products.append({
                'product_code': product.get('productCode'),
                'title': product.get('title'),
                'description': product.get('description'),
                'duration': duration_str,
                'price': {
                    'amount': product.get('pricing', {}).get('summary', {}).get('fromPrice'),
                    'currency': product.get('pricing', {}).get('currency')
                },
                'rating': rating,
                'reviews_count': product.get('reviews', {}).get('totalReviews'),
                'image_url': image_url
            })

        return ActionResult(data={
            'products': products,
            'total_count': result.get('totalCount', len(products)),
            'page': page
        })


@viator.action("get_product_details")
class GetProductDetails(ActionHandler):
    """
    Action that retrieves detailed information about a product.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        product_code = inputs['product_code']
        currency = inputs.get('currency', 'USD')

        result = await api.get_product_details(context, product_code, currency)

        # Transform the response
        return ActionResult(data={
            'product_code': result.get('productCode'),
            'title': result.get('title'),
            'description': result.get('description'),
            'duration': result.get('duration'),
            'price': {
                'amount': result.get('pricing', {}).get('summary', {}).get('fromPrice'),
                'currency': result.get('pricing', {}).get('currency')
            },
            'rating': result.get('reviews', {}).get('averageRating'),
            'reviews_count': result.get('reviews', {}).get('totalReviews'),
            'images': [img.get('imageUrl') for img in result.get('images', [])],
            'inclusions': result.get('inclusions', []),
            'exclusions': result.get('exclusions', []),
            'meeting_point': result.get('itinerary', {}).get('meetingPoint', {}).get('description'),
            'cancellation_policy': result.get('cancellationPolicy', {}).get('description')
        })


@viator.action("check_availability")
class CheckAvailability(ActionHandler):
    """
    Action that checks real-time availability for a product.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        product_code = inputs['product_code']
        travel_date = inputs['travel_date']
        currency = inputs.get('currency', 'USD')
        adult_count = inputs.get('adult_count', 1)
        child_count = inputs.get('child_count', 0)

        result = await api.check_availability(
            context, product_code, travel_date, currency, adult_count, child_count
        )

        # Transform the response
        product_options = []
        for option in result.get('productOptions', []):
            product_options.append({
                'option_code': option.get('productOptionCode'),
                'title': option.get('title'),
                'price': {
                    'amount': option.get('pricing', {}).get('totalPrice'),
                    'currency': option.get('pricing', {}).get('currency')
                },
                'available_start_times': [time.get('startTime') for time in option.get('startTimes', [])]
            })

        return ActionResult(data={
            'available': result.get('available', False),
            'product_options': product_options
        })


@viator.action("calculate_price")
class CalculatePrice(ActionHandler):
    """
    Action that calculates the total price for a booking.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        product_code = inputs['product_code']
        product_option_code = inputs['product_option_code']
        travel_date = inputs['travel_date']
        currency = inputs.get('currency', 'USD')
        adult_count = inputs.get('adult_count', 1)
        child_count = inputs.get('child_count', 0)
        infant_count = inputs.get('infant_count', 0)

        result = await api.calculate_price(
            context, product_code, product_option_code, travel_date,
            currency, adult_count, child_count, infant_count
        )

        # Transform the response
        return ActionResult(data={
            'subtotal': result.get('price', {}).get('subtotal'),
            'total': result.get('price', {}).get('total'),
            'currency': result.get('price', {}).get('currency'),
            'breakdown': {
                'adult_price': result.get('price', {}).get('adultPrice'),
                'child_price': result.get('price', {}).get('childPrice'),
                'infant_price': result.get('price', {}).get('infantPrice')
            }
        })


@viator.action("create_booking")
class CreateBooking(ActionHandler):
    """
    Action that creates a new booking.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        product_code = inputs['product_code']
        product_option_code = inputs['product_option_code']
        travel_date = inputs['travel_date']
        traveler_details = inputs['traveler_details']
        booker_details = inputs['booker_details']
        start_time = inputs.get('start_time')
        currency = inputs.get('currency', 'USD')

        result = await api.create_booking(
            context, product_code, product_option_code, travel_date,
            traveler_details, booker_details, start_time, currency
        )

        # Transform the response
        return ActionResult(data={
            'booking_reference': result.get('bookingRef'),
            'booking_status': result.get('bookingStatus'),
            'voucher_url': result.get('voucherURL'),
            'total_price': result.get('totalPrice'),
            'currency': result.get('currency'),
            'confirmation_email_sent': result.get('emailSent', False)
        })


@viator.action("get_booking")
class GetBooking(ActionHandler):
    """
    Action that retrieves booking details.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        booking_reference = inputs['booking_reference']

        result = await api.get_booking(context, booking_reference)

        # Transform the response
        return ActionResult(data={
            'booking_reference': result.get('bookingRef'),
            'booking_status': result.get('bookingStatus'),
            'product_code': result.get('productCode'),
            'product_title': result.get('productTitle'),
            'travel_date': result.get('travelDate'),
            'total_price': result.get('totalPrice'),
            'currency': result.get('currency'),
            'voucher_url': result.get('voucherURL'),
            'travelers': [
                {
                    'first_name': t.get('firstName'),
                    'last_name': t.get('lastName')
                }
                for t in result.get('travelers', [])
            ]
        })


@viator.action("cancel_booking")
class CancelBooking(ActionHandler):
    """
    Action that cancels a booking.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        booking_reference = inputs['booking_reference']
        cancellation_reason_code = inputs.get('cancellation_reason_code')

        result = await api.cancel_booking(
            context, booking_reference, cancellation_reason_code
        )

        # Transform the response
        return ActionResult(data={
            'booking_reference': result.get('bookingRef'),
            'cancellation_status': result.get('status'),
            'refund_amount': result.get('refundAmount'),
            'currency': result.get('currency'),
            'cancellation_fee': result.get('cancellationFee'),
            'refund_eligible': result.get('refundEligible', False)
        })


@viator.action("get_destinations")
class GetDestinations(ActionHandler):
    """
    Action that retrieves available destinations.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        parent_destination_id = inputs.get('parent_destination_id')

        result = await api.get_destinations(context, parent_destination_id)

        # Transform the response
        destinations = []
        for dest in result.get('destinations', []):
            destinations.append({
                'destination_id': dest.get('destinationId'),
                'destination_name': dest.get('destinationName'),
                'destination_type': dest.get('destinationType'),
                'parent_id': dest.get('parentId'),
                'time_zone': dest.get('timeZone')
            })

        return ActionResult(data={
            'destinations': destinations
        })


@viator.action("get_product_reviews")
class GetProductReviews(ActionHandler):
    """
    Action that retrieves product reviews.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api = get_viator_api(context)

        product_code = inputs['product_code']
        page = inputs.get('page', 1)
        page_size = inputs.get('page_size', 10)

        result = await api.get_product_reviews(context, product_code, page, page_size)

        # Transform the response
        reviews = []
        for review in result.get('reviews', []):
            reviews.append({
                'review_id': review.get('reviewId'),
                'rating': review.get('rating'),
                'title': review.get('title'),
                'review_text': review.get('text'),
                'reviewer_name': review.get('reviewerName'),
                'review_date': review.get('publishedDate'),
                'travel_date': review.get('travelDate')
            })

        return ActionResult(data={
            'product_code': product_code,
            'average_rating': result.get('averageRating'),
            'total_reviews': result.get('totalReviews'),
            'reviews': reviews
        })

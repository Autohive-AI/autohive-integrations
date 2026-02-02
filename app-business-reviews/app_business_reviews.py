from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
app_business_reviews = Integration.load()

# ---- Apple App Store Actions ----

@app_business_reviews.action("search_apps_ios")
class SearchAppsIOS(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Build SerpApi request parameters for app search
        params = {
            "api_key": api_key,
            "engine": "apple_app_store",
            "term": inputs["term"]
        }

        # Add optional parameters
        if inputs.get("country"):
            params["country"] = inputs["country"]

        if inputs.get("num"):
            params["num"] = inputs["num"]

        if inputs.get("property"):
            params["property"] = inputs["property"]

        # Make API request to SerpApi
        response = await context.fetch(
            "https://serpapi.com/search",
            method="GET",
            params=params
        )

        # Extract apps from organic results
        organic_results = response.get("organic_results", [])
        limit = inputs.get("num", 10)
        apps = []

        for result in organic_results[:limit]:
            app = {
                "id": result.get("id", 0),
                "title": result.get("title", ""),
                "bundle_id": result.get("bundle_id", ""),
                "developer": {
                    "name": result.get("developer", {}).get("name", ""),
                    "id": result.get("developer", {}).get("id", 0)
                },
                "rating": result.get("rating", []),
                "price": result.get("price", {}),
                "link": result.get("link", "")
            }
            apps.append(app)

        return {
            "apps": apps,
            "total_results": len(apps)
        }

@app_business_reviews.action("get_reviews_app_store")
class GetReviewsAppStore(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Get product_id - either provided directly or search by app name
        product_id = inputs.get("product_id")
        app_name = inputs.get("app_name")

        if not product_id and not app_name:
            raise ValueError("Either product_id or app_name must be provided")

        # If app_name is provided but no product_id, search for the app first
        if app_name and not product_id:
            search_params = {
                "api_key": api_key,
                "engine": "apple_app_store",
                "term": app_name,
                "num": 1
            }

            # Add country if provided
            if inputs.get("country"):
                search_params["country"] = inputs["country"]

            search_response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=search_params
            )

            organic_results = search_response.get("organic_results", [])
            if not organic_results:
                raise ValueError(f"No apps found for search term: {app_name}")

            # Get the first result's product ID
            first_result = organic_results[0]
            product_id = str(first_result.get("id"))

            if not product_id:
                raise ValueError(f"Could not extract product ID for app: {app_name}")

        # Build SerpApi request parameters for reviews
        params = {
            "api_key": api_key,
            "engine": "apple_reviews",
            "product_id": product_id
        }

        # Add optional filters
        if inputs.get("country"):
            params["country"] = inputs["country"]

        if inputs.get("sort"):
            params["sort"] = inputs["sort"]

        # Get pagination parameters
        max_pages = inputs.get("max_pages", 3)
        all_reviews = []
        current_page = 1
        app_title = ""

        # Fetch reviews with pagination
        while current_page <= max_pages:
            # Add page parameter for subsequent pages
            if current_page > 1:
                params["page"] = current_page

            # Make API request to SerpApi
            response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=params
            )

            # Extract reviews data from current page
            page_reviews = response.get("reviews", [])
            if not page_reviews:
                break

            # Extract app title from first page if not set
            if current_page == 1:
                # Try to get app title from search parameters or response
                app_title = app_name or f"App ID: {product_id}"

            # Format reviews according to output schema
            for review in page_reviews:
                formatted_review = {
                    "id": review.get("id", ""),
                    "title": review.get("title", ""),
                    "text": review.get("text", ""),
                    "rating": review.get("rating", 0),
                    "author": {
                        "name": review.get("author", {}).get("name", ""),
                        "author_id": review.get("author", {}).get("author_id", "")
                    },
                    "review_date": review.get("review_date", ""),
                    "reviewed_version": review.get("reviewed_version", ""),
                    "helpfulness_vote_information": review.get("helpfulness_vote_information", "")
                }
                all_reviews.append(formatted_review)

            current_page += 1

            # Check if there are more pages using pagination info
            pagination_info = response.get("serpapi_pagination", {})
            if not pagination_info.get("next"):
                break

        return {
            "reviews": all_reviews,
            "total_reviews": len(all_reviews),
            "app_name": app_title,
            "product_id": product_id
        }

# ---- Google Play Store Actions ----

@app_business_reviews.action("search_apps_android")
class SearchAppsAndroid(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Build SerpApi request parameters for app search
        params = {
            "api_key": api_key,
            "engine": "google_play",
            "store": "apps",
            "q": inputs["query"]
        }

        # Make API request to SerpApi
        response = await context.fetch(
            "https://serpapi.com/search",
            method="GET",
            params=params
        )

        # Extract apps from organic results
        organic_results = response.get("organic_results", [])
        limit = inputs.get("limit", 10)
        apps = []

        # When searching with 'q', results are nested under 'items'
        for section in organic_results:
            items = section.get("items", [])
            for result in items[:limit]:
                app = {
                    "product_id": result.get("product_id", ""),
                    "title": result.get("title", ""),
                    "developer": result.get("author", ""),
                    "rating": result.get("rating"),
                    "price": result.get("price", "Free"),
                    "thumbnail": result.get("thumbnail", ""),
                    "link": result.get("link", "")
                }
                apps.append(app)
                if len(apps) >= limit:
                    break
            if len(apps) >= limit:
                break

        return {
            "apps": apps,
            "total_results": len(apps)
        }

@app_business_reviews.action("get_reviews_google_play")
class GetReviewsGooglePlay(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Get product_id - either provided directly or search by app name
        product_id = inputs.get("product_id")
        app_name = inputs.get("app_name")

        if not product_id and not app_name:
            raise ValueError("Either product_id or app_name must be provided")

        # If app_name is provided but no product_id, search for the app first
        if app_name and not product_id:
            search_params = {
                "api_key": api_key,
                "engine": "google_play",
                "store": "apps",
                "q": app_name
            }

            search_response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=search_params
            )

            organic_results = search_response.get("organic_results", [])
            if not organic_results:
                raise ValueError(f"No apps found for search term: {app_name}")

            # Get the first result's product ID from nested items structure
            product_id = None
            for section in organic_results:
                items = section.get("items", [])
                if items:
                    first_result = items[0]
                    product_id = first_result.get("product_id")
                    break

            if not product_id:
                raise ValueError(f"Could not extract product ID for app: {app_name}")

        # Build SerpApi request parameters
        params = {
            "api_key": api_key,
            "engine": "google_play_product",
            "store": "apps",
            "product_id": product_id,
            "all_reviews": "true"  # Required to get reviews
        }

        # Add optional filters
        if inputs.get("rating"):
            params["rating"] = inputs["rating"]

        if inputs.get("platform"):
            params["platform"] = inputs["platform"]

        if inputs.get("sort_by"):
            params["sort_by"] = inputs["sort_by"]

        # Get pagination parameters
        reviews_per_page = inputs.get("num_reviews", 40)
        max_pages = inputs.get("max_pages", 3)
        all_reviews = []
        next_page_token = None
        pages_fetched = 0

        # Fetch reviews with pagination
        while pages_fetched < max_pages:
            # Add pagination token and num parameter for subsequent pages
            if next_page_token:
                params["next_page_token"] = next_page_token

            # Add num parameter (can be used on all pages for this API)
            params["num"] = reviews_per_page

            # Make API request to SerpApi
            response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=params
            )

            # Extract reviews data from current page
            page_reviews = response.get("reviews", [])
            if not page_reviews:
                break

            # Format reviews according to output schema
            for review in page_reviews:
                formatted_review = {
                    "id": review.get("id", ""),
                    "rating": review.get("rating"),
                    "text": review.get("snippet", ""),
                    "author": review.get("user", {}).get("name", ""),
                    "date": review.get("date", ""),
                    "likes": review.get("likes", 0),
                    "avatar": review.get("user", {}).get("avatar", "")
                }
                all_reviews.append(formatted_review)

            pages_fetched += 1

            # Check if there's a next page
            pagination_info = response.get("serpapi_pagination", {})
            next_page_token = pagination_info.get("next_page_token")
            if not next_page_token:
                break

        # Extract app information from the response
        app_info = response.get("product_info", {})

        return {
            "reviews": all_reviews,
            "total_reviews": len(all_reviews),
            "app_name": app_info.get("title", ""),
            "app_rating": app_info.get("rating") or 0.0,
            "product_id": product_id
        }

# ---- Google Maps Actions ----

@app_business_reviews.action("search_places_google_maps")
class SearchPlacesGoogleMaps(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Build SerpApi request parameters for place search
        query_string = inputs["query"]

        # Add location to query if provided (text location format)
        if inputs.get("location"):
            query_string = f"{query_string} in {inputs['location']}"

        params = {
            "api_key": api_key,
            "engine": "google_maps",
            "type": "search",
            "q": query_string
        }

        # Make API request to SerpApi
        response = await context.fetch(
            "https://serpapi.com/search",
            method="GET",
            params=params
        )

        # Extract places from local results
        local_results = response.get("local_results", [])
        limit = inputs.get("num_results", 5)
        places = []

        for result in local_results[:limit]:
            place = {
                "place_id": result.get("place_id", ""),
                "data_id": result.get("data_id", ""),
                "title": result.get("title", ""),
                "address": result.get("address", ""),
                "rating": result.get("rating", 0.0),
                "reviews": result.get("reviews", 0),
                "type": result.get("type", ""),
                "phone": result.get("phone", "")
            }
            places.append(place)

        return {
            "places": places,
            "total_results": len(places)
        }

@app_business_reviews.action("get_reviews_google_maps")
class GetReviewsGoogleMaps(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        api_key = context.auth.get("credentials", {}).get("api_key", {})

        # Get place_id and data_id - either provided directly or search by business name
        place_id = inputs.get("place_id")
        data_id = inputs.get("data_id")
        query = inputs.get("query")
        local_results = []  # Initialize to store search results

        if not place_id and not data_id and not query:
            raise ValueError("Either place_id, data_id, or query (business name) must be provided")

        # If query is provided but no place_id/data_id, search for the place first
        if query and not place_id and not data_id:
            # Build query string with location if provided
            search_query = query
            if inputs.get("location"):
                search_query = f"{query} in {inputs['location']}"

            search_params = {
                "api_key": api_key,
                "engine": "google_maps",
                "type": "search",
                "q": search_query
            }

            # Search for the place to get place_id and data_id
            search_response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=search_params
            )

            local_results = search_response.get("local_results", [])
            if not local_results:
                # Provide helpful error message
                suggestion = f"No businesses found for search query: '{search_query}'. Use place_id instead. Visit: https://developers.google.com/maps/documentation/places/web-service/place-id to find Place ID manually."
                raise ValueError(suggestion)

            # Get the first result's place_id and data_id
            first_result = local_results[0]
            place_id = first_result.get("place_id")
            data_id = first_result.get("data_id")

            if not place_id and not data_id:
                raise ValueError(f"Could not extract place_id or data_id for business: {search_query}. The search returned results but they don't contain required identifiers.")

        # Build SerpApi request parameters for reviews
        params = {
            "api_key": api_key,
            "engine": "google_maps_reviews"
        }

        # Use place_id or data_id (prefer place_id if both available)
        if place_id:
            params["place_id"] = place_id
        elif data_id:
            params["data_id"] = data_id
        else:
            raise ValueError("Could not resolve place_id or data_id from the provided query")

        # Add sort parameter if provided
        if inputs.get("sort_by"):
            params["sort_by"] = inputs["sort_by"]

        # Get pagination parameters
        reviews_per_page = inputs.get("num_reviews", 10)  # Default 10 per page
        max_pages = inputs.get("max_pages", 5)  # Default 5 pages
        all_reviews = []
        next_page_token = None
        pages_fetched = 0

        # Fetch reviews with pagination
        while pages_fetched < max_pages:
            # Add pagination token and num parameter for subsequent pages
            if next_page_token:
                params["next_page_token"] = next_page_token
                params["num"] = reviews_per_page
            # First page: only add num if we have other parameters that allow it
            elif "q" in params or "topic_id" in params:
                params["num"] = reviews_per_page

            # Make API request to SerpApi
            response = await context.fetch(
                "https://serpapi.com/search",
                method="GET",
                params=params
            )

            # Extract reviews data from current page
            page_reviews = response.get("reviews", [])
            if not page_reviews:
                break

            # Format reviews according to output schema
            for review in page_reviews:
                formatted_review = {
                    "rating": review.get("rating"),
                    "text": review.get("snippet", ""),
                    "author": review.get("user", {}).get("name", ""),
                    "date": review.get("date", ""),
                    "likes": review.get("likes", 0)
                }
                all_reviews.append(formatted_review)

            pages_fetched += 1

            # Check if there's a next page
            next_page_token = response.get("serpapi_pagination", {}).get("next_page_token")
            if not next_page_token:
                break

        # Extract business information from the last response
        place_info = response.get("place_info", {})

        # Use business name from search result if we searched, otherwise from place_info
        business_name = place_info.get("title", "")
        if query and not inputs.get("place_id") and not inputs.get("data_id"):
            # If we searched by query, the business name should be more accurate
            if local_results:
                business_name = local_results[0].get("title", business_name)

        return {
            "reviews": all_reviews,
            "total_reviews": len(all_reviews),
            "average_rating": place_info.get("rating") or 0.0,
            "business_name": business_name,
            "place_id": place_id or place_info.get("place_id", inputs.get("place_id", ""))
        }

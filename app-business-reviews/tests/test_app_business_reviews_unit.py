import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "app_business_reviews_mod", os.path.join(_parent, "app_business_reviews.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app_business_reviews = _mod.app_business_reviews

pytestmark = pytest.mark.unit

# ---- Shared sample data ----

SAMPLE_IOS_APP = {
    "id": 310633997,
    "title": "WhatsApp Messenger",
    "bundle_id": "net.whatsapp.WhatsApp",
    "developer": {"name": "WhatsApp Inc.", "id": 310633998},
    "rating": [{"rating": 4.7}],
    "price": {"value": 0},
    "link": "https://apps.apple.com/us/app/whatsapp/id310633997",
}

SAMPLE_IOS_REVIEW = {
    "id": "rev_001",
    "title": "Great app",
    "text": "Works perfectly",
    "rating": 5,
    "author": {"name": "JohnDoe", "author_id": "a1"},
    "review_date": "2024-01-15",
    "reviewed_version": "24.1",
    "helpfulness_vote_information": "",
}

SAMPLE_ANDROID_APP_SECTION = {
    "items": [
        {
            "product_id": "com.whatsapp",
            "title": "WhatsApp Messenger",
            "author": "WhatsApp LLC",
            "rating": 4.3,
            "price": "Free",
            "thumbnail": "https://example.com/thumb.png",
            "link": "https://play.google.com/store/apps/details?id=com.whatsapp",
        }
    ]
}

SAMPLE_ANDROID_REVIEW = {
    "id": "gp_rev_001",
    "rating": 5,
    "snippet": "Excellent app",
    "user": {"name": "Jane", "avatar": "https://example.com/avatar.png"},
    "date": "2024-02-01",
    "likes": 12,
}

SAMPLE_MAPS_PLACE = {
    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "data_id": "0xdata123",
    "title": "Starbucks Reserve Roastery",
    "address": "1124 Pike St, Seattle, WA",
    "rating": 4.5,
    "reviews": 1234,
    "type": "Coffee shop",
    "phone": "+1-206-123-4567",
}

SAMPLE_MAPS_REVIEW = {
    "rating": 5,
    "snippet": "Best coffee ever",
    "user": {"name": "Alice"},
    "date": "January 2024",
    "likes": 3,
}


# ---- Fixtures ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    # custom auth — flat object matching config.json auth.fields
    ctx.auth = {
        "api_key": "test_serpapi_key",  # nosec B105
    }
    return ctx


# ---- iOS App Store: Search Apps ----


class TestSearchAppsIOS:
    @pytest.mark.asyncio
    async def test_happy_path_returns_apps(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"organic_results": [SAMPLE_IOS_APP]},
        )

        result = await app_business_reviews.execute_action("search_apps_ios", {"term": "WhatsApp"}, mock_context)

        assert result.result.data["total_results"] == 1
        assert result.result.data["apps"][0]["title"] == "WhatsApp Messenger"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        await app_business_reviews.execute_action("search_apps_ios", {"term": "WhatsApp"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://serpapi.com/search"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_request_params_include_term(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        await app_business_reviews.execute_action(
            "search_apps_ios", {"term": "Instagram", "country": "uk"}, mock_context
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["term"] == "Instagram"
        assert params["engine"] == "apple_app_store"
        assert params["country"] == "uk"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        result = await app_business_reviews.execute_action("search_apps_ios", {"term": "NonExistent"}, mock_context)

        assert result.result.data["apps"] == []
        assert result.result.data["total_results"] == 0

    @pytest.mark.asyncio
    async def test_num_limit_applied(self, mock_context):
        apps = [dict(SAMPLE_IOS_APP, id=i, title=f"App {i}") for i in range(5)]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": apps})

        result = await app_business_reviews.execute_action("search_apps_ios", {"term": "App", "num": 3}, mock_context)

        assert result.result.data["total_results"] == 3

    @pytest.mark.asyncio
    async def test_developer_property_search(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        await app_business_reviews.execute_action(
            "search_apps_ios",
            {"term": "WhatsApp", "property": "developer"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["property"] == "developer"


# ---- iOS App Store: Get Reviews ----


class TestGetReviewsAppStore:
    @pytest.mark.asyncio
    async def test_happy_path_with_product_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [SAMPLE_IOS_REVIEW], "serpapi_pagination": {}},
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_app_store", {"product_id": "310633997"}, mock_context
        )

        assert result.result.data["total_reviews"] == 1
        assert result.result.data["reviews"][0]["title"] == "Great app"
        assert result.result.data["product_id"] == "310633997"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"reviews": [], "serpapi_pagination": {}}
        )

        await app_business_reviews.execute_action("get_reviews_app_store", {"product_id": "310633997"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://serpapi.com/search"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_request_params_apple_reviews_engine(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"reviews": [], "serpapi_pagination": {}}
        )

        await app_business_reviews.execute_action(
            "get_reviews_app_store",
            {"product_id": "310633997", "sort": "mostrecent"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["engine"] == "apple_reviews"
        assert params["product_id"] == "310633997"
        assert params["sort"] == "mostrecent"

    @pytest.mark.asyncio
    async def test_auto_resolve_app_name(self, mock_context):
        mock_context.fetch.side_effect = [
            # Search response
            FetchResponse(
                status=200,
                headers={},
                data={"organic_results": [SAMPLE_IOS_APP]},
            ),
            # Reviews response
            FetchResponse(
                status=200,
                headers={},
                data={"reviews": [SAMPLE_IOS_REVIEW], "serpapi_pagination": {}},
            ),
        ]

        result = await app_business_reviews.execute_action(
            "get_reviews_app_store", {"app_name": "WhatsApp"}, mock_context
        )

        assert result.result.data["app_name"] == "WhatsApp"
        assert result.result.data["total_reviews"] == 1

    @pytest.mark.asyncio
    async def test_error_no_product_id_or_app_name(self, mock_context):
        result = await app_business_reviews.execute_action("get_reviews_app_store", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "product_id" in result.result.message or "app_name" in result.result.message

    @pytest.mark.asyncio
    async def test_error_app_name_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        result = await app_business_reviews.execute_action(
            "get_reviews_app_store", {"app_name": "NonExistentApp"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "NonExistentApp" in result.result.message

    @pytest.mark.asyncio
    async def test_pagination_stops_when_no_next(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_IOS_REVIEW],
                "serpapi_pagination": {},
            },  # no "next" key
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_app_store",
            {"product_id": "310633997", "max_pages": 5},
            mock_context,
        )

        # Should only make 1 call since there's no next page
        assert mock_context.fetch.call_count == 1
        assert result.result.data["total_reviews"] == 1

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [SAMPLE_IOS_REVIEW], "serpapi_pagination": {}},
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_app_store", {"product_id": "310633997"}, mock_context
        )

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert "app_name" in data
        assert "product_id" in data


# ---- Android: Search Apps ----


class TestSearchAppsAndroid:
    @pytest.mark.asyncio
    async def test_happy_path_returns_apps(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"organic_results": [SAMPLE_ANDROID_APP_SECTION]},
        )

        result = await app_business_reviews.execute_action("search_apps_android", {"query": "WhatsApp"}, mock_context)

        assert result.result.data["total_results"] == 1
        assert result.result.data["apps"][0]["product_id"] == "com.whatsapp"

    @pytest.mark.asyncio
    async def test_request_url_and_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        await app_business_reviews.execute_action("search_apps_android", {"query": "Spotify"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://serpapi.com/search"
        params = call_args.kwargs["params"]
        assert params["engine"] == "google_play"
        assert params["q"] == "Spotify"
        assert params["store"] == "apps"

    @pytest.mark.asyncio
    async def test_limit_applied(self, mock_context):
        items = [dict(product_id=f"com.app{i}", title=f"App {i}") for i in range(10)]
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"organic_results": [{"items": items}]},
        )

        result = await app_business_reviews.execute_action(
            "search_apps_android", {"query": "App", "limit": 3}, mock_context
        )

        assert result.result.data["total_results"] == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        result = await app_business_reviews.execute_action(
            "search_apps_android", {"query": "NonExistent"}, mock_context
        )

        assert result.result.data["apps"] == []
        assert result.result.data["total_results"] == 0


# ---- Android: Get Reviews Google Play ----


class TestGetReviewsGooglePlay:
    @pytest.mark.asyncio
    async def test_happy_path_with_product_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_ANDROID_REVIEW],
                "product_info": {"title": "WhatsApp", "rating": 4.3},
                "serpapi_pagination": {},
            },
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_google_play", {"product_id": "com.whatsapp"}, mock_context
        )

        assert result.result.data["total_reviews"] == 1
        assert result.result.data["product_id"] == "com.whatsapp"
        assert result.result.data["app_name"] == "WhatsApp"

    @pytest.mark.asyncio
    async def test_request_uses_google_play_product_engine(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [], "product_info": {}, "serpapi_pagination": {}},
        )

        await app_business_reviews.execute_action(
            "get_reviews_google_play", {"product_id": "com.whatsapp"}, mock_context
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["engine"] == "google_play_product"
        assert params["product_id"] == "com.whatsapp"
        assert params["all_reviews"] == "true"

    @pytest.mark.asyncio
    async def test_auto_resolve_app_name(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"organic_results": [SAMPLE_ANDROID_APP_SECTION]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "reviews": [SAMPLE_ANDROID_REVIEW],
                    "product_info": {"title": "WhatsApp", "rating": 4.3},
                    "serpapi_pagination": {},
                },
            ),
        ]

        result = await app_business_reviews.execute_action(
            "get_reviews_google_play", {"app_name": "WhatsApp"}, mock_context
        )

        assert result.result.data["product_id"] == "com.whatsapp"

    @pytest.mark.asyncio
    async def test_error_no_product_id_or_app_name(self, mock_context):
        result = await app_business_reviews.execute_action("get_reviews_google_play", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_error_app_name_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"organic_results": []})

        result = await app_business_reviews.execute_action(
            "get_reviews_google_play", {"app_name": "NonExistentApp"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "NonExistentApp" in result.result.message

    @pytest.mark.asyncio
    async def test_optional_filters_included_in_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [], "product_info": {}, "serpapi_pagination": {}},
        )

        await app_business_reviews.execute_action(
            "get_reviews_google_play",
            {
                "product_id": "com.instagram.android",
                "rating": 5,
                "platform": "phone",
                "sort_by": 2,
            },
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["rating"] == 5
        assert params["platform"] == "phone"
        assert params["sort_by"] == 2

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_ANDROID_REVIEW],
                "product_info": {"title": "App", "rating": 4.0},
                "serpapi_pagination": {},
            },
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_google_play", {"product_id": "com.whatsapp"}, mock_context
        )

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert "app_name" in data
        assert "app_rating" in data
        assert "product_id" in data


# ---- Google Maps: Search Places ----


class TestSearchPlacesGoogleMaps:
    @pytest.mark.asyncio
    async def test_happy_path_returns_places(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"local_results": [SAMPLE_MAPS_PLACE]},
        )

        result = await app_business_reviews.execute_action(
            "search_places_google_maps", {"query": "Starbucks"}, mock_context
        )

        assert result.result.data["total_results"] == 1
        assert result.result.data["places"][0]["title"] == "Starbucks Reserve Roastery"

    @pytest.mark.asyncio
    async def test_request_url_and_engine(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"local_results": []})

        await app_business_reviews.execute_action("search_places_google_maps", {"query": "Pizza"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://serpapi.com/search"
        params = call_args.kwargs["params"]
        assert params["engine"] == "google_maps"
        assert params["type"] == "search"

    @pytest.mark.asyncio
    async def test_location_appended_to_query(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"local_results": []})

        await app_business_reviews.execute_action(
            "search_places_google_maps",
            {"query": "Pizza", "location": "New York, NY"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["q"] == "Pizza in New York, NY"

    @pytest.mark.asyncio
    async def test_num_results_limit(self, mock_context):
        places = [dict(SAMPLE_MAPS_PLACE, place_id=f"place_{i}", title=f"Place {i}") for i in range(10)]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"local_results": places})

        result = await app_business_reviews.execute_action(
            "search_places_google_maps",
            {"query": "Coffee", "num_results": 3},
            mock_context,
        )

        assert result.result.data["total_results"] == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"local_results": []})

        result = await app_business_reviews.execute_action(
            "search_places_google_maps", {"query": "NonExistent"}, mock_context
        )

        assert result.result.data["places"] == []

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"local_results": [SAMPLE_MAPS_PLACE]}
        )

        result = await app_business_reviews.execute_action(
            "search_places_google_maps", {"query": "Starbucks"}, mock_context
        )

        place = result.result.data["places"][0]
        assert "place_id" in place
        assert "data_id" in place
        assert "title" in place
        assert "address" in place
        assert "rating" in place


# ---- Google Maps: Get Reviews ----


class TestGetReviewsGoogleMaps:
    @pytest.mark.asyncio
    async def test_happy_path_with_place_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_MAPS_REVIEW],
                "place_info": {
                    "title": "Starbucks",
                    "rating": 4.5,
                    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                },
                "serpapi_pagination": {},
            },
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"},
            mock_context,
        )

        assert result.result.data["total_reviews"] == 1
        assert result.result.data["average_rating"] == 4.5

    @pytest.mark.asyncio
    async def test_request_uses_google_maps_reviews_engine(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [], "place_info": {}, "serpapi_pagination": {}},
        )

        await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["engine"] == "google_maps_reviews"
        assert params["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"

    @pytest.mark.asyncio
    async def test_uses_data_id_when_no_place_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [], "place_info": {}, "serpapi_pagination": {}},
        )

        await app_business_reviews.execute_action("get_reviews_google_maps", {"data_id": "0xdata123"}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["data_id"] == "0xdata123"
        assert "place_id" not in params

    @pytest.mark.asyncio
    async def test_auto_resolve_by_query(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"local_results": [SAMPLE_MAPS_PLACE]},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "reviews": [SAMPLE_MAPS_REVIEW],
                    "place_info": {
                        "title": "Starbucks Reserve Roastery",
                        "rating": 4.5,
                    },
                    "serpapi_pagination": {},
                },
            ),
        ]

        result = await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"query": "Starbucks Reserve Roastery", "location": "Seattle, WA"},
            mock_context,
        )

        assert result.result.data["total_reviews"] == 1
        assert result.result.data["business_name"] == "Starbucks Reserve Roastery"

    @pytest.mark.asyncio
    async def test_error_no_identifiers(self, mock_context):
        result = await app_business_reviews.execute_action("get_reviews_google_maps", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "place_id" in result.result.message or "query" in result.result.message

    @pytest.mark.asyncio
    async def test_error_query_no_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"local_results": []})

        result = await app_business_reviews.execute_action(
            "get_reviews_google_maps", {"query": "NonExistentBusiness"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "NonExistentBusiness" in result.result.message

    @pytest.mark.asyncio
    async def test_sort_by_included_in_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"reviews": [], "place_info": {}, "serpapi_pagination": {}},
        )

        await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4", "sort_by": "newestFirst"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["sort_by"] == "newestFirst"

    @pytest.mark.asyncio
    async def test_pagination_stops_when_no_next_token(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_MAPS_REVIEW],
                "place_info": {"title": "Starbucks", "rating": 4.5},
                "serpapi_pagination": {},  # no next_page_token
            },
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4", "max_pages": 5},
            mock_context,
        )

        assert mock_context.fetch.call_count == 1
        assert result.result.data["total_reviews"] == 1

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "reviews": [SAMPLE_MAPS_REVIEW],
                "place_info": {"title": "Cafe", "rating": 4.2},
                "serpapi_pagination": {},
            },
        )

        result = await app_business_reviews.execute_action(
            "get_reviews_google_maps",
            {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"},
            mock_context,
        )

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "business_name" in data
        assert "place_id" in data

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from bitly.bitly import bitly, normalize_bitlink, encode_bitlink_for_url

pytestmark = pytest.mark.unit

BITLY_API_BASE_URL = "https://api-ssl.bitly.com/v4"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Pure Function Tests ----


class TestNormalizeBitlink:
    def test_full_http_url(self):
        assert normalize_bitlink("http://bit.ly/abc123") == "bit.ly/abc123"

    def test_full_https_url(self):
        assert normalize_bitlink("https://bit.ly/abc123") == "bit.ly/abc123"

    def test_domain_slash_path_format(self):
        assert normalize_bitlink("bit.ly/abc123") == "bit.ly/abc123"

    def test_custom_domain(self):
        assert normalize_bitlink("https://custom.short/xyz") == "custom.short/xyz"

    def test_hash_only(self):
        assert normalize_bitlink("abc123") == "bit.ly/abc123"

    def test_url_with_trailing_path(self):
        assert normalize_bitlink("https://bit.ly/abc/def") == "bit.ly/abc/def"


class TestEncodeBitlinkForUrl:
    def test_encodes_slash(self):
        assert encode_bitlink_for_url("bit.ly/abc123") == "bit.ly%2Fabc123"

    def test_encodes_special_characters(self):
        result = encode_bitlink_for_url("bit.ly/a b")
        assert "%2F" in result
        assert "%20" in result

    def test_no_slash(self):
        assert encode_bitlink_for_url("abc123") == "abc123"


# ---- Action Tests ----


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self, mock_context):
        mock_context.fetch.return_value = {"login": "testuser", "name": "Test"}

        result = await bitly.execute_action("get_user", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["user"] == {"login": "testuser", "name": "Test"}
        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/user", method="GET")


class TestShortenUrl:
    @pytest.mark.asyncio
    async def test_shorten_basic(self, mock_context):
        mock_context.fetch.return_value = {
            "link": "https://bit.ly/short",
            "id": "bit.ly/short",
        }
        inputs = {"long_url": "https://example.com/long"}

        result = await bitly.execute_action("shorten_url", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["bitlink"]["link"] == "https://bit.ly/short"
        mock_context.fetch.assert_called_once_with(
            f"{BITLY_API_BASE_URL}/shorten",
            method="POST",
            json={"long_url": "https://example.com/long"},
        )

    @pytest.mark.asyncio
    async def test_shorten_with_domain_and_group(self, mock_context):
        mock_context.fetch.return_value = {"link": "https://cstm.ly/x"}
        inputs = {
            "long_url": "https://example.com",
            "domain": "cstm.ly",
            "group_guid": "Ga1b2c",
        }

        result = await bitly.execute_action("shorten_url", inputs, mock_context)

        assert result.result.data["result"] is True
        call_kwargs = mock_context.fetch.call_args
        body = call_kwargs.kwargs["json"]
        assert body["domain"] == "cstm.ly"
        assert body["group_guid"] == "Ga1b2c"


class TestCreateBitlink:
    @pytest.mark.asyncio
    async def test_create_minimal(self, mock_context):
        mock_context.fetch.return_value = {
            "link": "https://bit.ly/new",
            "id": "bit.ly/new",
        }
        inputs = {"long_url": "https://example.com/page"}

        result = await bitly.execute_action("create_bitlink", inputs, mock_context)

        assert result.result.data["result"] is True
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["json"] == {"long_url": "https://example.com/page"}

    @pytest.mark.asyncio
    async def test_create_with_all_options(self, mock_context):
        mock_context.fetch.return_value = {"link": "https://bit.ly/custom"}
        inputs = {
            "long_url": "https://example.com",
            "domain": "bit.ly",
            "group_guid": "Ga1b2c",
            "title": "My Link",
            "tags": ["test", "demo"],
            "custom_back_half": "mylink",
        }

        result = await bitly.execute_action("create_bitlink", inputs, mock_context)

        assert result.result.data["result"] is True
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["long_url"] == "https://example.com"
        assert body["domain"] == "bit.ly"
        assert body["group_guid"] == "Ga1b2c"
        assert body["title"] == "My Link"
        assert body["tags"] == ["test", "demo"]
        assert body["custom_back_half"] == "mylink"


class TestGetBitlink:
    @pytest.mark.asyncio
    async def test_get_by_domain_path(self, mock_context):
        mock_context.fetch.return_value = {
            "id": "bit.ly/abc",
            "long_url": "https://example.com",
        }
        inputs = {"bitlink": "bit.ly/abc"}

        result = await bitly.execute_action("get_bitlink", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["bitlink"]["id"] == "bit.ly/abc"
        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/bitlinks/bit.ly%2Fabc", method="GET")

    @pytest.mark.asyncio
    async def test_get_by_full_url(self, mock_context):
        mock_context.fetch.return_value = {"id": "bit.ly/abc"}
        inputs = {"bitlink": "https://bit.ly/abc"}

        await bitly.execute_action("get_bitlink", inputs, mock_context)

        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/bitlinks/bit.ly%2Fabc", method="GET")


class TestUpdateBitlink:
    @pytest.mark.asyncio
    async def test_update_title(self, mock_context):
        mock_context.fetch.return_value = {"id": "bit.ly/abc", "title": "New Title"}
        inputs = {"bitlink": "bit.ly/abc", "title": "New Title"}

        result = await bitly.execute_action("update_bitlink", inputs, mock_context)

        assert result.result.data["result"] is True
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["json"] == {"title": "New Title"}
        assert call_kwargs.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, mock_context):
        mock_context.fetch.return_value = {"id": "bit.ly/abc"}
        inputs = {
            "bitlink": "bit.ly/abc",
            "title": "T",
            "tags": ["a"],
            "archived": True,
        }

        await bitly.execute_action("update_bitlink", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body == {"title": "T", "tags": ["a"], "archived": True}


class TestExpandBitlink:
    @pytest.mark.asyncio
    async def test_expand(self, mock_context):
        mock_context.fetch.return_value = {"long_url": "https://example.com/original"}
        inputs = {"bitlink": "bit.ly/abc"}

        result = await bitly.execute_action("expand_bitlink", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["long_url"] == "https://example.com/original"
        mock_context.fetch.assert_called_once_with(
            f"{BITLY_API_BASE_URL}/expand",
            method="POST",
            json={"bitlink_id": "bit.ly/abc"},
        )

    @pytest.mark.asyncio
    async def test_expand_normalizes_full_url(self, mock_context):
        mock_context.fetch.return_value = {"long_url": "https://example.com"}
        inputs = {"bitlink": "https://bit.ly/abc"}

        await bitly.execute_action("expand_bitlink", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["bitlink_id"] == "bit.ly/abc"


class TestGetClicks:
    @pytest.mark.asyncio
    async def test_get_clicks_with_params(self, mock_context):
        mock_context.fetch.return_value = {
            "link_clicks": [{"clicks": 5, "date": "2025-01-01"}],
        }
        inputs = {"bitlink": "bit.ly/abc", "unit": "day", "units": 7}

        result = await bitly.execute_action("get_clicks", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["clicks"] == [{"clicks": 5, "date": "2025-01-01"}]
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["params"] == {"unit": "day", "units": 7}

    @pytest.mark.asyncio
    async def test_get_clicks_defaults(self, mock_context):
        mock_context.fetch.return_value = {"link_clicks": []}
        inputs = {"bitlink": "bit.ly/abc"}

        await bitly.execute_action("get_clicks", inputs, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["unit"] == "day"
        assert params["units"] == -1


class TestGetClicksSummary:
    @pytest.mark.asyncio
    async def test_get_summary(self, mock_context):
        mock_context.fetch.return_value = {
            "total_clicks": 42,
            "unit": "day",
            "units": 30,
        }
        inputs = {"bitlink": "bit.ly/abc", "unit": "day", "units": 30}

        result = await bitly.execute_action("get_clicks_summary", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["total_clicks"] == 42
        assert result.result.data["unit"] == "day"
        assert result.result.data["units"] == 30

    @pytest.mark.asyncio
    async def test_get_summary_defaults(self, mock_context):
        mock_context.fetch.return_value = {
            "total_clicks": 0,
            "unit": "day",
            "units": -1,
        }
        inputs = {"bitlink": "bit.ly/abc"}

        await bitly.execute_action("get_clicks_summary", inputs, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["unit"] == "day"
        assert params["units"] == -1


class TestListBitlinks:
    @pytest.mark.asyncio
    async def test_with_group_guid(self, mock_context):
        mock_context.fetch.return_value = {
            "links": [{"id": "bit.ly/a"}, {"id": "bit.ly/b"}],
            "pagination": {"total": 2, "page": 1, "size": 50},
        }
        inputs = {"group_guid": "Gabcdef"}

        result = await bitly.execute_action("list_bitlinks", inputs, mock_context)

        assert result.result.data["result"] is True
        assert len(result.result.data["bitlinks"]) == 2
        assert result.result.data["total"] == 2
        mock_context.fetch.assert_called_once()
        call_url = mock_context.fetch.call_args.args[0]
        assert "groups/Gabcdef/bitlinks" in call_url

    @pytest.mark.asyncio
    async def test_without_group_guid_fetches_user(self, mock_context):
        mock_context.fetch.side_effect = [
            {"default_group_guid": "Gauto123"},
            {
                "links": [{"id": "bit.ly/x"}],
                "pagination": {"total": 1, "page": 1, "size": 50},
            },
        ]
        inputs = {}

        result = await bitly.execute_action("list_bitlinks", inputs, mock_context)

        assert result.result.data["result"] is True
        assert len(result.result.data["bitlinks"]) == 1
        assert mock_context.fetch.call_count == 2
        first_call = mock_context.fetch.call_args_list[0]
        assert first_call.args[0] == f"{BITLY_API_BASE_URL}/user"

    @pytest.mark.asyncio
    async def test_without_group_guid_no_default(self, mock_context):
        mock_context.fetch.return_value = {"default_group_guid": None}
        inputs = {}

        result = await bitly.execute_action("list_bitlinks", inputs, mock_context)

        assert result.result.data["result"] is False
        assert "No default_group_guid" in result.result.data["error"]

    @pytest.mark.asyncio
    async def test_with_pagination_params(self, mock_context):
        mock_context.fetch.return_value = {
            "links": [],
            "pagination": {"total": 0, "page": 2, "size": 10},
        }
        inputs = {"group_guid": "Gabcdef", "size": 10, "page": 2, "keyword": "test"}

        await bitly.execute_action("list_bitlinks", inputs, mock_context)

        call_kwargs = mock_context.fetch.call_args
        params = call_kwargs.kwargs["params"]
        assert params["size"] == 10
        assert params["page"] == 2
        assert params["keyword"] == "test"


class TestListGroups:
    @pytest.mark.asyncio
    async def test_list_groups(self, mock_context):
        mock_context.fetch.return_value = {
            "groups": [{"guid": "G1", "name": "Default"}],
        }

        result = await bitly.execute_action("list_groups", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["groups"] == [{"guid": "G1", "name": "Default"}]
        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/groups", method="GET")


class TestGetGroup:
    @pytest.mark.asyncio
    async def test_get_group(self, mock_context):
        mock_context.fetch.return_value = {"guid": "G1", "name": "My Group"}
        inputs = {"group_guid": "G1"}

        result = await bitly.execute_action("get_group", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["group"]["guid"] == "G1"
        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/groups/G1", method="GET")


class TestListOrganizations:
    @pytest.mark.asyncio
    async def test_list_organizations(self, mock_context):
        mock_context.fetch.return_value = {
            "organizations": [{"guid": "O1", "name": "Org"}],
        }

        result = await bitly.execute_action("list_organizations", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["organizations"] == [{"guid": "O1", "name": "Org"}]
        mock_context.fetch.assert_called_once_with(f"{BITLY_API_BASE_URL}/organizations", method="GET")


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_get_user_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await bitly.execute_action("get_user", {}, mock_context)

        assert result.result.data["result"] is False
        assert "Network error" in result.result.data["error"]

    @pytest.mark.asyncio
    async def test_shorten_url_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API failure")

        result = await bitly.execute_action("shorten_url", {"long_url": "https://example.com"}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["bitlink"] == {}

    @pytest.mark.asyncio
    async def test_get_clicks_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await bitly.execute_action("get_clicks", {"bitlink": "bit.ly/abc"}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["clicks"] == []

    @pytest.mark.asyncio
    async def test_list_bitlinks_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await bitly.execute_action("list_bitlinks", {"group_guid": "G1"}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["bitlinks"] == []

    @pytest.mark.asyncio
    async def test_expand_bitlink_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad request")

        result = await bitly.execute_action("expand_bitlink", {"bitlink": "bit.ly/abc"}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["long_url"] == ""

    @pytest.mark.asyncio
    async def test_get_clicks_summary_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await bitly.execute_action("get_clicks_summary", {"bitlink": "bit.ly/abc"}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["total_clicks"] == 0

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from autohive_integrations_sdk import FetchResponse

from hubspot.hubspot import (
    parse_response,
    parse_date_string_to_utc,
    convert_hubspot_timestamp_to_utc_string,
    convert_deal_dates_to_utc,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- parse_response ----


class TestParseResponse:
    @pytest.mark.asyncio
    async def test_dict_data(self):
        response = FetchResponse(status=200, headers={}, data={"results": [], "total": 0})
        result = await parse_response(response)
        assert result == {"results": [], "total": 0}

    @pytest.mark.asyncio
    async def test_list_data(self):
        response = FetchResponse(status=200, headers={}, data=[{"id": "1"}, {"id": "2"}])
        result = await parse_response(response)
        assert result == [{"id": "1"}, {"id": "2"}]

    @pytest.mark.asyncio
    async def test_string_data(self):
        response = FetchResponse(status=200, headers={}, data="raw text")
        result = await parse_response(response)
        assert result == "raw text"

    @pytest.mark.asyncio
    async def test_none_data(self):
        response = FetchResponse(status=204, headers={}, data=None)
        result = await parse_response(response)
        assert result is None

    @pytest.mark.asyncio
    async def test_nested_dict(self):
        data = {"contact": {"id": "123", "properties": {"email": "test@example.com"}}}
        response = FetchResponse(status=200, headers={}, data=data)
        result = await parse_response(response)
        assert result["contact"]["properties"]["email"] == "test@example.com"


# ---- parse_date_string_to_utc ----


class TestParseDateStringToUtc:
    def test_iso_date(self):
        result = parse_date_string_to_utc("2025-08-22")
        assert result == datetime(2025, 8, 22)

    def test_date_with_time_am_pm(self):
        result = parse_date_string_to_utc("22 Aug 2025 3:46 PM")
        assert result == datetime(2025, 8, 22, 15, 46)

    def test_date_day_month_year(self):
        result = parse_date_string_to_utc("22 Aug 2025")
        assert result == datetime(2025, 8, 22)

    def test_datetime_with_seconds(self):
        result = parse_date_string_to_utc("2025-08-22 15:46:00")
        assert result == datetime(2025, 8, 22, 15, 46, 0)

    def test_us_date_format(self):
        result = parse_date_string_to_utc("08/22/2025")
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_eu_date_format(self):
        result = parse_date_string_to_utc("22/08/2025")
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_whitespace_trimmed(self):
        result = parse_date_string_to_utc("  2025-08-22  ")
        assert result == datetime(2025, 8, 22)

    def test_none_returns_none(self):
        assert parse_date_string_to_utc(None) is None

    def test_empty_string_returns_none(self):
        assert parse_date_string_to_utc("") is None

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_date_string_to_utc("not-a-date")

    def test_relative_date_raises_value_error(self):
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_date_string_to_utc("yesterday")


# ---- convert_hubspot_timestamp_to_utc_string ----


class TestConvertHubspotTimestampToUtcString:
    def test_millisecond_timestamp(self):
        # 1693785917790 ms = 2023-09-03T23:45:17.790Z
        result = convert_hubspot_timestamp_to_utc_string("1693785917790")
        assert result is not None
        assert "UTC" in result
        assert "2023" in result

    def test_iso_z_string(self):
        result = convert_hubspot_timestamp_to_utc_string("2025-09-03T23:45:17.790Z")
        assert result is not None
        assert "UTC" in result
        assert "03 Sep 2025" in result

    def test_none_returns_none(self):
        assert convert_hubspot_timestamp_to_utc_string(None) is None

    def test_empty_string_returns_none(self):
        assert convert_hubspot_timestamp_to_utc_string("") is None

    def test_invalid_data_returns_none(self):
        assert convert_hubspot_timestamp_to_utc_string("not-a-timestamp") is None

    def test_zero_returns_none(self):
        assert convert_hubspot_timestamp_to_utc_string(0) is None

    def test_integer_timestamp(self):
        result = convert_hubspot_timestamp_to_utc_string(1693785917790)
        assert result is not None
        assert "UTC" in result

    def test_output_format(self):
        # Known timestamp: 2025-01-15T10:30:00.000Z
        result = convert_hubspot_timestamp_to_utc_string("2025-01-15T10:30:00.000Z")
        assert result == "15 Jan 2025 10:30 AM UTC"


# ---- convert_deal_dates_to_utc ----


class TestConvertDealDatesToUtc:
    def test_converts_date_fields(self):
        deal = {
            "id": "123",
            "properties": {
                "dealname": "Test Deal",
                "closedate": "1735689600000",  # 2025-01-01 00:00:00 UTC
                "createdate": "2025-06-15T10:00:00.000Z",
            },
        }
        result = convert_deal_dates_to_utc(deal)
        assert "UTC" in result["properties"]["closedate"]
        assert "UTC" in result["properties"]["createdate"]
        # Non-date fields unchanged
        assert result["properties"]["dealname"] == "Test Deal"

    def test_none_deal_returns_none(self):
        assert convert_deal_dates_to_utc(None) is None

    def test_empty_dict_returns_empty(self):
        result = convert_deal_dates_to_utc({})
        assert result == {}

    def test_non_dict_returns_as_is(self):
        assert convert_deal_dates_to_utc("not a deal") == "not a deal"

    def test_no_properties_key(self):
        deal = {"id": "123"}
        result = convert_deal_dates_to_utc(deal)
        assert result == {"id": "123"}

    def test_empty_date_fields_skipped(self):
        deal = {
            "properties": {
                "closedate": None,
                "createdate": "",
                "dealname": "Test",
            }
        }
        result = convert_deal_dates_to_utc(deal)
        assert result["properties"]["closedate"] is None
        assert result["properties"]["createdate"] == ""
        assert result["properties"]["dealname"] == "Test"

    def test_all_date_fields_converted(self):
        deal = {
            "properties": {
                "closedate": "1735689600000",
                "createdate": "1735689600000",
                "hs_lastmodifieddate": "1735689600000",
                "notes_last_contacted": "1735689600000",
                "hs_last_sales_activity_timestamp": "1735689600000",
                "hs_latest_meeting_activity": "1735689600000",
                "hs_last_email_activity": "1735689600000",
                "hs_last_call_activity": "1735689600000",
                "hs_last_sales_activity_date": "1735689600000",
            }
        }
        result = convert_deal_dates_to_utc(deal)
        for field in result["properties"]:
            assert "UTC" in result["properties"][field]

    def test_invalid_timestamp_not_converted(self):
        deal = {
            "properties": {
                "closedate": "not-a-timestamp",
                "dealname": "Test",
            }
        }
        result = convert_deal_dates_to_utc(deal)
        # Invalid timestamp returns None from converter, so field stays unchanged
        assert result["properties"]["closedate"] == "not-a-timestamp"

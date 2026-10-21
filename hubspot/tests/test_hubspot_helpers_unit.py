import asyncio

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError

from hubspot.hubspot import (
    parse_response,
    parse_date_string_to_utc,
    convert_hubspot_timestamp_to_utc_string,
    convert_deal_dates_to_utc,
    fetch_with_rate_limit_retries,
    is_rate_limit_error,
    _error_text,
    _outcome_unknown,
    _property_value,
    _timestamp_ms,
    _unfinished_batch_reason,
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


# ---- fetch_with_rate_limit_retries ----


class TestFetchWithRateLimitRetries:
    @pytest.mark.asyncio
    async def test_caps_retry_after_when_available(self, mock_context, monkeypatch):
        mock_sleep = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", mock_sleep)

        class RateLimitLikeError(Exception):
            status = 429
            retry_after = 60

        mock_context.fetch.side_effect = [
            RateLimitLikeError("HTTP 429: Rate limit exceeded"),
            FetchResponse(status=200, headers={}, data={"ok": True}),
        ]

        result = await fetch_with_rate_limit_retries(mock_context, "https://example.test")

        assert result.data == {"ok": True}
        mock_sleep.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_rejects_negative_max_retries(self, mock_context):
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            await fetch_with_rate_limit_retries(mock_context, "https://example.test", max_retries=-1)

    @pytest.mark.asyncio
    async def test_enforces_cumulative_sleep_budget(self, mock_context, monkeypatch):
        mock_sleep = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", mock_sleep)

        class RateLimitLikeError(Exception):
            status = 429
            retry_after = 60

        mock_context.fetch.side_effect = RateLimitLikeError("HTTP 429: Rate limit exceeded")

        with pytest.raises(RateLimitLikeError):
            await fetch_with_rate_limit_retries(mock_context, "https://example.test")

        assert mock_context.fetch.await_count == 2
        mock_sleep.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_shared_sleep_budget_applies_across_calls(self, mock_context, monkeypatch):
        mock_sleep = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", mock_sleep)

        class RateLimitLikeError(Exception):
            status = 429
            retry_after = 8

        retry_sleep_budget = {"remaining": 10}
        mock_context.fetch.side_effect = [
            RateLimitLikeError("HTTP 429: Rate limit exceeded"),
            FetchResponse(status=200, headers={}, data={"first": True}),
            RateLimitLikeError("HTTP 429: Rate limit exceeded"),
            FetchResponse(status=200, headers={}, data={"second": True}),
        ]

        first = await fetch_with_rate_limit_retries(
            mock_context,
            "https://example.test/first",
            retry_sleep_budget=retry_sleep_budget,
        )
        second = await fetch_with_rate_limit_retries(
            mock_context,
            "https://example.test/second",
            retry_sleep_budget=retry_sleep_budget,
        )

        assert first.data == {"first": True}
        assert second.data == {"second": True}
        assert retry_sleep_budget["remaining"] == 0
        assert [call.args[0] for call in mock_sleep.await_args_list] == [8, 2]

    @pytest.mark.asyncio
    async def test_rejects_negative_total_sleep_budget(self, mock_context):
        with pytest.raises(ValueError, match="max_total_sleep_seconds must be >= 0"):
            await fetch_with_rate_limit_retries(
                mock_context,
                "https://example.test",
                max_total_sleep_seconds=-1,
            )


# ---- parse_date_string_to_utc ----


class TestFetchWithoutConnectionResend:
    @pytest.mark.asyncio
    async def test_write_starts_sdk_at_its_retry_limit(self, mock_context):
        mock_context.config = {"max_retries": 3}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await fetch_with_rate_limit_retries(mock_context, "https://example.test", resend_on_connection_error=False)

        assert mock_context.fetch.call_args.kwargs["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_reads_keep_sdk_resends(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await fetch_with_rate_limit_retries(mock_context, "https://example.test")

        assert "retry_count" not in mock_context.fetch.call_args.kwargs

    @pytest.mark.asyncio
    async def test_write_still_retries_rate_limits(self, mock_context, monkeypatch):
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", AsyncMock())
        mock_context.config = {"max_retries": 3}
        mock_context.fetch.side_effect = [
            RateLimitError(1, 429, "Rate limit exceeded"),
            FetchResponse(status=200, headers={}, data={"ok": True}),
        ]

        response = await fetch_with_rate_limit_retries(
            mock_context, "https://example.test", resend_on_connection_error=False
        )

        assert response.data == {"ok": True}
        assert mock_context.fetch.call_count == 2


# ---- Error and value helpers ----


class TestIsRateLimitError:
    @pytest.mark.parametrize(
        "error,expected",
        [
            (RateLimitError(60, 429, "Rate limit exceeded"), True),
            (HTTPError(429, "Too many requests"), True),
            (HTTPError(500, "Internal error, correlationId 4291"), False),
            (Exception("HTTP 429: Rate limit exceeded"), False),
            (asyncio.TimeoutError(), False),
        ],
    )
    def test_matches_on_status_not_text(self, error, expected):
        assert is_rate_limit_error(error) is expected


class TestOutcomeUnknown:
    @pytest.mark.parametrize(
        "error,expected",
        [
            (HTTPError(400, "Bad request"), False),
            (HTTPError(404, "Not found"), False),
            (RateLimitError(60, 429, "Rate limit exceeded"), False),
            (HTTPError(500, "Server error"), True),
            (HTTPError(504, "Gateway timeout"), True),
            (asyncio.TimeoutError(), True),
            (aiohttp.ServerDisconnectedError(), True),
        ],
    )
    def test_only_server_and_connection_errors_are_ambiguous(self, error, expected):
        assert _outcome_unknown(error) is expected


class TestErrorText:
    def test_uses_error_message(self):
        assert _error_text(HTTPError(400, "Bad request")) == "HTTP 400: Bad request"

    def test_falls_back_to_type_name_for_blank_errors(self):
        assert _error_text(asyncio.TimeoutError()) == "TimeoutError"


class TestPropertyValue:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, ""),
            (True, "true"),
            (False, "false"),
            (50, "50"),
            ("CTO", "CTO"),
            (["BUDGET_HOLDER", "END_USER"], "BUDGET_HOLDER;END_USER"),
            (["ONLY"], "ONLY"),
            ([], ""),
        ],
    )
    def test_converts_to_hubspot_string_form(self, value, expected):
        assert _property_value(value) == expected


class TestUnfinishedBatchReason:
    @pytest.mark.parametrize(
        "status,expected",
        [
            ("PENDING", "is still processing"),
            ("PROCESSING", "is still processing"),
            ("CANCELED", "canceled"),
            ("COMPLETE", None),
            (None, None),
        ],
    )
    def test_reason_for_each_status(self, status, expected):
        assert _unfinished_batch_reason({"status": status}) == expected


class TestTimestampMs:
    def test_float_milliseconds_truncated(self):
        assert _timestamp_ms(1700000000000.7) == "1700000000000"

    def test_int_milliseconds_kept(self):
        assert _timestamp_ms(1700000000000) == "1700000000000"

    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            ("2026-10-21T00:00:00Z", "1792540800000"),
            ("2026-10-21", "1792540800000"),
            ("2026-10-21T13:00:00+13:00", "1792540800000"),
            ("2026-10-21T00:00:00.250Z", "1792540800250"),
            (" 1700000000000 ", "1700000000000"),
            ("2026-10-21T00:00:00z", "1792540800000"),
        ],
    )
    def test_strings_converted_to_utc_milliseconds(self, timestamp, expected):
        assert _timestamp_ms(timestamp) == expected

    @pytest.mark.parametrize(
        "timestamp",
        [
            "yesterday",
            "1969-12-31T23:59:59Z",
            "99999999999999999999",
            "9" * 5000,
            10**400,
            1e20,
            -1,
            float("nan"),
            float("inf"),
            True,
        ],
    )
    def test_unreadable_or_out_of_range_is_none(self, timestamp):
        assert _timestamp_ms(timestamp) is None

    @pytest.mark.parametrize("timestamp", [None, ""])
    def test_missing_defaults_to_now(self, timestamp):
        before = int(datetime.now().timestamp() * 1000)

        value = int(_timestamp_ms(timestamp))

        assert before <= value <= int(datetime.now().timestamp() * 1000)


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

import os
import sys
import importlib

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "test_developer_token")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_ID", "test_client_id")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "test_client_secret")  # nosec B105

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "google_ads_mod", os.path.join(_parent, "google_ads.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_date_range = _mod.parse_date_range
micros_to_currency = _mod.micros_to_currency
_calculate_safe_rate = _mod._calculate_safe_rate
_get_ad_text_assets = _mod._get_ad_text_assets

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_date_range
# ---------------------------------------------------------------------------


class TestParseDateRange:
    def test_last_7_days_spaced(self):
        result = parse_date_range("last 7 days")
        today = datetime.now().date()
        expected_end = today - timedelta(days=1)
        expected_start = expected_end - timedelta(days=6)
        assert result == {
            "start_date": expected_start.strftime("%Y-%m-%d"),
            "end_date": expected_end.strftime("%Y-%m-%d"),
        }

    def test_last_7_days_underscored(self):
        # "last_7_days" is treated the same as "last 7 days"
        result_spaced = parse_date_range("last 7 days")
        result_underscored = parse_date_range("last_7_days")
        assert result_spaced == result_underscored

    def test_explicit_date_range_with_underscore(self):
        result = parse_date_range("2025-05-14_2025-05-20")
        assert result == {"start_date": "2025-05-14", "end_date": "2025-05-20"}

    def test_single_date_slash_format(self):
        result = parse_date_range("14/05/2025")
        assert result == {"start_date": "2025-05-14", "end_date": "2025-05-14"}

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid date range format"):
            parse_date_range("not-a-date")

    def test_invalid_slash_date_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date_range("99/99/9999")

    def test_last_7_days_returns_dict_keys(self):
        result = parse_date_range("last 7 days")
        assert "start_date" in result
        assert "end_date" in result

    def test_explicit_range_start_before_end(self):
        result = parse_date_range("2025-01-01_2025-01-31")
        assert result["start_date"] <= result["end_date"]


# ---------------------------------------------------------------------------
# micros_to_currency
# ---------------------------------------------------------------------------


class TestMicrosToCurrency:
    def test_one_million_micros_equals_one_dollar(self):
        assert micros_to_currency(1_000_000) == 1.0

    def test_partial_micros(self):
        assert micros_to_currency(2_500_000) == 2.5

    def test_zero_micros(self):
        assert micros_to_currency(0) == 0.0

    def test_none_returns_na_string(self):
        assert micros_to_currency(None) == "N/A"

    def test_returns_float_type(self):
        result = micros_to_currency(1_000_000)
        assert isinstance(result, float)

    def test_large_value(self):
        assert micros_to_currency(10_000_000) == 10.0


# ---------------------------------------------------------------------------
# _calculate_safe_rate
# ---------------------------------------------------------------------------


class TestCalculateSafeRate:
    def test_basic_division(self):
        assert _calculate_safe_rate(10, 100) == pytest.approx(0.1)

    def test_zero_numerator(self):
        assert _calculate_safe_rate(0, 100) == 0.0

    def test_zero_denominator_returns_zero(self):
        assert _calculate_safe_rate(10, 0) == 0.0

    def test_non_numeric_numerator_returns_zero(self):
        assert _calculate_safe_rate("abc", 100) == 0.0

    def test_non_numeric_denominator_returns_zero(self):
        assert _calculate_safe_rate(10, "abc") == 0.0

    def test_both_non_numeric_returns_zero(self):
        assert _calculate_safe_rate("x", "y") == 0.0

    def test_float_inputs(self):
        assert _calculate_safe_rate(1.5, 3.0) == pytest.approx(0.5)

    def test_string_numeric_inputs_are_coerced(self):
        # Numeric strings should be coerced to floats successfully
        assert _calculate_safe_rate("10", "100") == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# _get_ad_text_assets
# ---------------------------------------------------------------------------


class TestGetAdTextAssets:
    def test_rsa_extracts_headlines_and_descriptions(self):
        ad_data = {
            "type": "RESPONSIVE_SEARCH_AD",
            "responsive_search_ad": {
                "headlines": [
                    {"text": "Headline One"},
                    {"text": "Headline Two"},
                    {"text": "Headline Three"},
                ],
                "descriptions": [
                    {"text": "Description One"},
                    {"text": "Description Two"},
                ],
            },
        }
        result = _get_ad_text_assets(ad_data)
        assert result["headlines"] == ["Headline One", "Headline Two", "Headline Three"]
        assert result["descriptions"] == ["Description One", "Description Two"]

    def test_rsa_skips_empty_text_entries(self):
        ad_data = {
            "type": "RESPONSIVE_SEARCH_AD",
            "responsive_search_ad": {
                "headlines": [{"text": "Real Headline"}, {"text": ""}, {}],
                "descriptions": [{"text": "Real Desc"}, {}],
            },
        }
        result = _get_ad_text_assets(ad_data)
        assert result["headlines"] == ["Real Headline"]
        assert result["descriptions"] == ["Real Desc"]

    def test_expanded_text_ad_extracts_parts(self):
        ad_data = {
            "type": "EXPANDED_TEXT_AD",
            "expanded_text_ad": {
                "headline_part1": "Part One",
                "headline_part2": "Part Two",
                "headline_part3": "Part Three",
                "description": "Main description",
                "description2": "Second description",
            },
        }
        result = _get_ad_text_assets(ad_data)
        assert "Part One" in result["headlines"]
        assert "Part Two" in result["headlines"]
        assert "Part Three" in result["headlines"]
        assert "Main description" in result["descriptions"]
        assert "Second description" in result["descriptions"]

    def test_expanded_text_ad_partial_parts(self):
        ad_data = {
            "type": "EXPANDED_TEXT_AD",
            "expanded_text_ad": {
                "headline_part1": "Only Headline",
                "description": "Only Description",
            },
        }
        result = _get_ad_text_assets(ad_data)
        assert result["headlines"] == ["Only Headline"]
        assert result["descriptions"] == ["Only Description"]

    def test_unknown_type_returns_empty_lists(self):
        ad_data = {"type": "SOME_UNKNOWN_TYPE"}
        result = _get_ad_text_assets(ad_data)
        assert result["headlines"] == []
        assert result["descriptions"] == []

    def test_missing_type_returns_empty_lists(self):
        result = _get_ad_text_assets({})
        assert result["headlines"] == []
        assert result["descriptions"] == []

    def test_return_type_is_dict_with_expected_keys(self):
        result = _get_ad_text_assets({"type": "RESPONSIVE_SEARCH_AD"})
        assert isinstance(result, dict)
        assert "headlines" in result
        assert "descriptions" in result
        assert isinstance(result["headlines"], list)
        assert isinstance(result["descriptions"], list)

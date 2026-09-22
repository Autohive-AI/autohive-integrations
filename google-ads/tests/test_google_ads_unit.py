import importlib
import os
import sys

import pytest

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "test-developer-token")
os.environ.setdefault("ADWORDS_CLIENT_ID", "test-client-id")
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "test-client-secret")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

google_ads_module = importlib.import_module("google_ads")


pytestmark = pytest.mark.unit


class MockGoogleAdsService:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def search(self, customer_id, query):
        self.queries.append({"customer_id": customer_id, "query": query})
        return self.rows


class MockGoogleAdsClient:
    def __init__(self, service):
        self.service = service

    def get_service(self, name):
        assert name == "GoogleAdsService"
        return self.service


def test_fetch_keyword_data_selects_and_maps_keyword_identifiers(monkeypatch):
    row = {
        "campaign": {"id": "111222333", "name": "Brand Search"},
        "ad_group": {"id": "123456789", "name": "Core Keywords"},
        "ad_group_criterion": {
            "criterion_id": "987654321",
            "status": "ENABLED",
            "keyword": {"text": "autohive", "match_type": "EXACT"},
            "quality_info": {"quality_score": 9},
        },
        "metrics": {
            "impressions": 100,
            "clicks": 12,
            "cost_micros": 3450000,
            "all_conversions": 2.0,
            "interaction_rate": 0.12,
            "average_cpc": 287500,
        },
    }
    service = MockGoogleAdsService([row])
    client = MockGoogleAdsClient(service)

    monkeypatch.setattr(google_ads_module.proto.Message, "to_dict", lambda row, **_: row)

    results = google_ads_module.fetch_keyword_data(
        client,
        "444555666",
        ["2026-06-30_2026-06-30"],
        campaign_ids=["111222333"],
        ad_group_ids=["123456789"],
    )

    query = service.queries[0]["query"]
    for selected_field in (
        "campaign.id",
        "campaign.name",
        "ad_group.id",
        "ad_group.name",
        "ad_group_criterion.criterion_id",
        "ad_group_criterion.keyword.match_type",
        "ad_group_criterion.status",
        "ad_group_criterion.quality_info.quality_score",
        "metrics.all_conversions",
        "metrics.interaction_rate",
        "metrics.average_cpc",
    ):
        assert selected_field in query

    keyword = results[0]["data"][0]
    assert keyword["Campaign ID"] == "111222333"
    assert keyword["Campaign"] == "Brand Search"
    assert keyword["Ad Group ID"] == "123456789"
    assert keyword["Ad Group"] == "Core Keywords"
    assert keyword["Keyword ID"] == "987654321"
    assert keyword["Keyword"] == "autohive"
    assert keyword["Match Type"] == "EXACT"
    assert keyword["Status"] == "ENABLED"
    assert keyword["Quality Score"] == 9
    assert keyword["Conversions"] == 2.0
    assert keyword["Interaction Rate"] == 0.12
    assert keyword["Avg. CPC"] == 0.2875

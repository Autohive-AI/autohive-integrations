"""Unit tests for the LinkedIn Community Management integration."""

import importlib.util
import os
import sys

import pytest
import yarl
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location(
    "linkedin_community_management_mod", os.path.join(_parent, "linkedin_community_management.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

linkedin_community_management = _mod.linkedin_community_management

pytestmark = pytest.mark.unit


def response(data=None, status=200, headers=None):
    return FetchResponse(status=status, headers=headers or {}, data=data)


class TestHelpers:
    @pytest.mark.parametrize(
        "value, actor_type, expected",
        [
            ("abc", "PERSON", "urn:li:person:abc"),
            ("123", "ORGANIZATION", "urn:li:organization:123"),
            ("urn:li:organization:99", "PERSON", "urn:li:organization:99"),
        ],
    )
    def test_actor_urn(self, value, actor_type, expected):
        assert _mod.actor_urn(value, actor_type) == expected

    def test_date_range(self):
        assert (
            _mod.restli_date_range({"year": 2026, "month": 9, "day": 1}, {"year": 2026, "month": 10, "day": 1})
            == "(start:(year:2026,month:9,day:1),end:(year:2026,month:10,day:1))"
        )

    def test_headers_use_current_version(self):
        headers = _mod.linkedin_headers()
        assert headers["LinkedIn-Version"] == "202610"
        assert headers["X-Restli-Protocol-Version"] == "2.0.0"

    def test_resource_url_preserves_encoded_urn(self):
        url = _mod.resource_url("/rest/posts", "urn:li:share:1")
        assert isinstance(url, yarl.URL)
        assert str(url) == "https://api.linkedin.com/rest/posts/urn%3Ali%3Ashare%3A1"

    def test_restli_query_url_preserves_structure_and_encoded_urn(self):
        url = _mod.restli_query_url(
            "/rest/example",
            {
                "organizationalEntity": _mod.encode_urn("urn:li:organization:42"),
                "timeIntervals": "(timeRange:(start:1,end:2),timeGranularityType:DAY)",
            },
        )
        assert str(url) == (
            "https://api.linkedin.com/rest/example?organizationalEntity=urn%3Ali%3Aorganization%3A42"
            "&timeIntervals=(timeRange:(start:1,end:2),timeGranularityType:DAY)"
        )


class TestProfileAndOrganizations:
    async def test_get_profile(self, mock_context):
        mock_context.fetch.return_value = response({"id": "member-1", "localizedFirstName": "Ada"})
        result = await linkedin_community_management.execute_action("get_profile", {}, mock_context)
        assert result.result.data["profile"]["id"] == "member-1"
        assert mock_context.fetch.call_args.args[0] == "https://api.linkedin.com/v2/me"

    async def test_get_profile_api_error(self, mock_context):
        mock_context.fetch.return_value = response({"message": "denied"}, status=403)
        result = await linkedin_community_management.execute_action("get_profile", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

    async def test_list_managed_organizations(self, mock_context):
        mock_context.fetch.return_value = response(
            {"elements": [{"organization": "urn:li:organization:1"}], "paging": {"total": 1}}
        )
        result = await linkedin_community_management.execute_action(
            "list_managed_organizations", {"role": "ADMINISTRATOR", "count": 25}, mock_context
        )
        assert len(result.result.data["organizations"]) == 1
        assert mock_context.fetch.call_args.kwargs["params"] == {
            "q": "roleAssignee",
            "state": "APPROVED",
            "role": "ADMINISTRATOR",
            "start": 0,
            "count": 25,
        }


class TestPosts:
    async def test_get_post_encodes_urn(self, mock_context):
        mock_context.fetch.return_value = response({"id": "urn:li:share:1"})
        result = await linkedin_community_management.execute_action(
            "get_post", {"post_urn": "urn:li:share:1"}, mock_context
        )
        assert result.result.data["post"]["id"] == "urn:li:share:1"
        url = mock_context.fetch.call_args.args[0]
        assert isinstance(url, yarl.URL)
        assert str(url).endswith("urn%3Ali%3Ashare%3A1")

    async def test_list_organization_posts(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"id": "p1"}], "paging": {}})
        result = await linkedin_community_management.execute_action("list_posts", {"author": "42"}, mock_context)
        assert result.result.data["posts"] == [{"id": "p1"}]
        assert "author=urn%3Ali%3Aorganization%3A42" in str(mock_context.fetch.call_args.args[0])
        assert "params" not in mock_context.fetch.call_args.kwargs

    async def test_create_post_as_organization(self, mock_context):
        mock_context.fetch.return_value = response(None, status=201, headers={"x-restli-id": "urn:li:share:9"})
        result = await linkedin_community_management.execute_action(
            "create_post",
            {"text": "Hello community", "author": "42", "actor_type": "ORGANIZATION"},
            mock_context,
        )
        assert result.result.data["post_id"] == "urn:li:share:9"
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["author"] == "urn:li:organization:42"
        assert payload["commentary"] == "Hello community"

    async def test_create_post_resolves_member(self, mock_context):
        mock_context.fetch.side_effect = [
            response({"id": "member-1"}),
            response(None, status=201, headers={"X-RestLi-Id": "urn:li:share:2"}),
        ]
        result = await linkedin_community_management.execute_action(
            "create_post", {"text": "Member post"}, mock_context
        )
        assert result.result.data["post_id"] == "urn:li:share:2"
        assert mock_context.fetch.call_args_list[1].kwargs["json"]["author"] == "urn:li:person:member-1"

    async def test_create_post_api_error(self, mock_context):
        mock_context.fetch.return_value = response({"message": "forbidden"}, status=403)
        result = await linkedin_community_management.execute_action(
            "create_post", {"text": "Nope", "author": "urn:li:organization:42"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "post creation failed" in result.result.message

    async def test_share_article_payload(self, mock_context):
        mock_context.fetch.return_value = response(None, status=201, headers={"x-restli-id": "urn:li:share:3"})
        await linkedin_community_management.execute_action(
            "share_article",
            {
                "article_url": "https://example.com/story",
                "article_title": "Story",
                "author": "urn:li:organization:42",
            },
            mock_context,
        )
        article = mock_context.fetch.call_args.kwargs["json"]["content"]["article"]
        assert article == {"source": "https://example.com/story", "title": "Story", "description": ""}

    async def test_reshare_payload(self, mock_context):
        mock_context.fetch.return_value = response(None, status=201, headers={"x-restli-id": "urn:li:share:4"})
        await linkedin_community_management.execute_action(
            "reshare_post",
            {"original_post_urn": "urn:li:share:1", "author": "urn:li:person:m1"},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["json"]["reshareContext"] == {"parent": "urn:li:share:1"}

    async def test_update_post(self, mock_context):
        mock_context.fetch.return_value = response(None, status=204)
        result = await linkedin_community_management.execute_action(
            "update_post", {"post_urn": "urn:li:share:1", "commentary": "Updated"}, mock_context
        )
        assert result.result.data["post_urn"] == "urn:li:share:1"
        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"

    async def test_delete_post(self, mock_context):
        mock_context.fetch.return_value = response(None, status=204)
        result = await linkedin_community_management.execute_action(
            "delete_post", {"post_urn": "urn:li:ugcPost:1"}, mock_context
        )
        assert result.result.data["result"] == "Post deleted successfully."
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"


class TestComments:
    async def test_list_comments(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"id": "c1"}], "paging": {}})
        result = await linkedin_community_management.execute_action(
            "list_comments", {"entity_urn": "urn:li:share:1", "count": 20}, mock_context
        )
        assert result.result.data["comments"] == [{"id": "c1"}]
        assert "count=20" in str(mock_context.fetch.call_args.args[0])

    async def test_create_organization_comment(self, mock_context):
        mock_context.fetch.return_value = response({"id": "c1"}, status=201)
        result = await linkedin_community_management.execute_action(
            "create_comment",
            {
                "root_urn": "urn:li:share:1",
                "text": "Thanks!",
                "actor": "42",
                "actor_type": "ORGANIZATION",
            },
            mock_context,
        )
        assert result.result.data["comment"]["id"] == "c1"
        assert mock_context.fetch.call_args.kwargs["json"]["actor"] == "urn:li:organization:42"

    async def test_create_reply_targets_parent(self, mock_context):
        mock_context.fetch.return_value = response({"id": "c2"}, status=201)
        await linkedin_community_management.execute_action(
            "create_comment",
            {
                "root_urn": "urn:li:share:1",
                "parent_comment_urn": "urn:li:comment:(urn:li:activity:1,2)",
                "text": "Reply",
                "actor": "urn:li:person:m1",
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert "urn%3Ali%3Acomment" in str(call.args[0])
        assert call.kwargs["json"]["parentComment"].startswith("urn:li:comment:")

    async def test_update_comment(self, mock_context):
        mock_context.fetch.return_value = response(None, status=204)
        await linkedin_community_management.execute_action(
            "update_comment",
            {"root_urn": "urn:li:share:1", "comment_id": "99", "text": "Edited"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.kwargs["json"]["patch"]["message"]["$set"]["text"] == "Edited"
        assert call.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"

    async def test_delete_organization_comment(self, mock_context):
        mock_context.fetch.return_value = response(None, status=204)
        result = await linkedin_community_management.execute_action(
            "delete_comment",
            {"root_urn": "urn:li:share:1", "comment_id": "99", "actor": "42"},
            mock_context,
        )
        assert result.result.data["comment_id"] == "99"
        assert "actor=urn%3Ali%3Aorganization%3A42" in str(mock_context.fetch.call_args.args[0])


class TestReactionsAndMetadata:
    async def test_list_reactions(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"reactionType": "LIKE"}], "paging": {}})
        result = await linkedin_community_management.execute_action(
            "list_reactions", {"entity_urn": "urn:li:share:1"}, mock_context
        )
        assert result.result.data["reactions"][0]["reactionType"] == "LIKE"
        assert "q=entity" in str(mock_context.fetch.call_args.args[0])

    async def test_create_reaction(self, mock_context):
        mock_context.fetch.return_value = response({"reactionType": "PRAISE"}, status=201)
        result = await linkedin_community_management.execute_action(
            "create_reaction",
            {"entity_urn": "urn:li:share:1", "reaction_type": "PRAISE", "actor": "42", "actor_type": "ORGANIZATION"},
            mock_context,
        )
        assert result.result.data["reaction"]["reactionType"] == "PRAISE"
        assert "actor=urn%3Ali%3Aorganization%3A42" in str(mock_context.fetch.call_args.args[0])

    async def test_delete_reaction(self, mock_context):
        mock_context.fetch.return_value = response(None, status=204)
        result = await linkedin_community_management.execute_action(
            "delete_reaction", {"entity_urn": "urn:li:share:1", "actor": "urn:li:person:m1"}, mock_context
        )
        assert result.result.data["entity_urn"] == "urn:li:share:1"
        assert "actor:urn%3Ali%3Aperson%3Am1" in str(mock_context.fetch.call_args.args[0])

    async def test_get_social_metadata(self, mock_context):
        mock_context.fetch.return_value = response({"commentsState": "OPEN", "commentSummary": {"count": 2}})
        result = await linkedin_community_management.execute_action(
            "get_social_metadata", {"entity_urn": "urn:li:share:1"}, mock_context
        )
        assert result.result.data["metadata"]["commentSummary"]["count"] == 2
        url = mock_context.fetch.call_args.args[0]
        assert isinstance(url, yarl.URL)
        assert str(url).endswith("urn%3Ali%3Ashare%3A1")

    async def test_close_comments_warned_action_payload(self, mock_context):
        mock_context.fetch.return_value = response(None, status=202)
        result = await linkedin_community_management.execute_action(
            "set_comments_state",
            {
                "entity_urn": "urn:li:share:1",
                "comments_state": "CLOSED",
                "actor": "urn:li:organization:42",
            },
            mock_context,
        )
        assert result.result.data["comments_state"] == "CLOSED"
        assert mock_context.fetch.call_args.kwargs["json"]["patch"]["$set"]["commentsState"] == "CLOSED"


class TestFollowersAndAnalytics:
    async def test_search_organization_followers(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"member": "urn:li:person:1"}], "paging": {}})
        result = await linkedin_community_management.execute_action(
            "search_organization_followers", {"organization": "42", "keywords": "ann"}, mock_context
        )
        assert result.result.data["followers"][0]["member"] == "urn:li:person:1"
        assert "organization=urn%3Ali%3Aorganization%3A42" in str(mock_context.fetch.call_args.args[0])

    async def test_organization_follower_statistics_lifetime(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"followerCountsByGeoCountry": []}], "paging": {}})
        result = await linkedin_community_management.execute_action(
            "get_organization_follower_statistics", {"organization": "42"}, mock_context
        )
        assert len(result.result.data["statistics"]) == 1
        url = str(mock_context.fetch.call_args.args[0])
        assert "organizationalEntity=urn%3Ali%3Aorganization%3A42" in url
        assert "timeIntervals" not in url

    async def test_organization_follower_statistics_time_bound(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [], "paging": {}})
        await linkedin_community_management.execute_action(
            "get_organization_follower_statistics",
            {"organization": "42", "start_ms": 1000, "end_ms": 2000, "granularity": "DAY"},
            mock_context,
        )
        assert "timeIntervals=(timeRange:(start:1000,end:2000),timeGranularityType:DAY)" in str(
            mock_context.fetch.call_args.args[0]
        )

    async def test_organization_post_statistics_specific_share(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"totalShareStatistics": {}}], "paging": {}})
        await linkedin_community_management.execute_action(
            "get_organization_post_statistics",
            {"organization": "42", "post_urn": "urn:li:share:1"},
            mock_context,
        )
        assert "shares=List(urn%3Ali%3Ashare%3A1)" in str(mock_context.fetch.call_args.args[0])

    async def test_member_post_analytics_for_post(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"count": 10}], "paging": {}})
        result = await linkedin_community_management.execute_action(
            "get_member_post_analytics",
            {"metric": "IMPRESSION", "post_urn": "urn:li:ugcPost:1"},
            mock_context,
        )
        assert result.result.data["analytics"][0]["count"] == 10
        url = str(mock_context.fetch.call_args.args[0])
        assert "q=entity" in url
        assert "entity=(ugcPost:urn%3Ali%3AugcPost%3A1)" in url

    async def test_member_post_analytics_aggregate_with_dates(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [], "paging": {}})
        await linkedin_community_management.execute_action(
            "get_member_post_analytics",
            {
                "metric": "REACTION",
                "aggregation": "DAILY",
                "start_date": {"year": 2026, "month": 9, "day": 1},
                "end_date": {"year": 2026, "month": 9, "day": 30},
            },
            mock_context,
        )
        url = str(mock_context.fetch.call_args.args[0])
        assert "q=me" in url
        assert "dateRange=(start:" in url

    async def test_member_follower_statistics_lifetime(self, mock_context):
        mock_context.fetch.return_value = response({"elements": [{"memberFollowersCount": 100}], "paging": {}})
        result = await linkedin_community_management.execute_action("get_member_follower_statistics", {}, mock_context)
        assert result.result.data["statistics"][0]["memberFollowersCount"] == 100
        assert str(mock_context.fetch.call_args.args[0]).endswith("?q=me")


class TestConnections:
    async def test_connection_count_with_person_id(self, mock_context):
        mock_context.fetch.return_value = response({"firstDegreeSize": 504})
        result = await linkedin_community_management.execute_action(
            "get_connection_count", {"person_id": "member-1"}, mock_context
        )
        assert result.result.data["first_degree_size"] == 504
        assert str(mock_context.fetch.call_args.args[0]).endswith("urn:li:person:member-1")

    async def test_connection_count_accepts_person_urn(self, mock_context):
        mock_context.fetch.return_value = response({"firstDegreeSize": 504})
        await linkedin_community_management.execute_action(
            "get_connection_count", {"person_id": "urn:li:person:member-1"}, mock_context
        )
        assert str(mock_context.fetch.call_args.args[0]).endswith("urn:li:person:member-1")
        assert "urn:li:person:urn:li:person:" not in str(mock_context.fetch.call_args.args[0])

    async def test_connection_count_resolves_profile(self, mock_context):
        mock_context.fetch.side_effect = [response({"id": "member-1"}), response({"firstDegreeSize": 12})]
        result = await linkedin_community_management.execute_action("get_connection_count", {}, mock_context)
        assert result.result.data["first_degree_size"] == 12
        assert mock_context.fetch.call_count == 2

    async def test_connection_count_error(self, mock_context):
        mock_context.fetch.return_value = response({"message": "forbidden"}, status=403)
        result = await linkedin_community_management.execute_action(
            "get_connection_count", {"person_id": "member-1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

"""LinkedIn Community Management integration for Autohive."""

from typing import Any
from urllib.parse import quote

import yarl
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

linkedin_community_management = Integration.load()

API_ROOT = "https://api.linkedin.com"
LINKEDIN_VERSION = "202610"
REACTION_TYPES = {"LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION", "ENTERTAINMENT"}
MEMBER_POST_METRICS = {
    "IMPRESSION",
    "MEMBERS_REACHED",
    "RESHARE",
    "REACTION",
    "COMMENT",
    "POST_SAVE",
    "POST_SEND",
    "LINK_CLICKS",
    "PREMIUM_CTA_CLICKS",
    "FOLLOWER_GAINED_FROM_CONTENT",
    "PROFILE_VIEW_FROM_CONTENT",
}


def linkedin_headers(**extra: str) -> dict[str, str]:
    """Headers required by LinkedIn's versioned Community Management APIs."""
    return {
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
        **extra,
    }


def encode_urn(urn: str) -> str:
    return quote(urn, safe="")


def preencoded_url(path: str) -> yarl.URL:
    """Create a URL without allowing yarl to normalize encoded Rest.li values."""
    return yarl.URL(f"{API_ROOT}{path}", encoded=True)


def resource_url(path: str, urn: str, suffix: str = "") -> yarl.URL:
    """Create a LinkedIn resource URL whose URN remains percent-encoded."""
    return preencoded_url(f"{path}/{encode_urn(urn)}{suffix}")


def restli_query_url(path: str, params: dict[str, Any]) -> yarl.URL:
    """Build a Rest.li 2.0 query while preserving its structural characters."""
    query = "&".join(f"{key}={quote(str(value), safe='(),:%')}" for key, value in params.items() if value is not None)
    return preencoded_url(f"{path}?{query}")


def actor_urn(actor: str, actor_type: str = "PERSON") -> str:
    """Accept either a complete LinkedIn URN or a bare member/organization ID."""
    if actor.startswith("urn:li:"):
        return actor
    namespace = "organization" if actor_type == "ORGANIZATION" else "person"
    return f"urn:li:{namespace}:{actor}"


def restli_date_range(start: dict[str, int] | None, end: dict[str, int] | None) -> str | None:
    """Build a Rest.li date range value from JSON-friendly date objects."""
    if not start and not end:
        return None
    parts = []
    for name, value in (("start", start), ("end", end)):
        if value:
            parts.append(f"{name}:(year:{value['year']},month:{value['month']},day:{value['day']})")
    return f"({','.join(parts)})"


def restli_time_intervals(start_ms: int | None, end_ms: int | None, granularity: str) -> str:
    """Build a Rest.li time interval from whichever bounds were supplied."""
    bounds = []
    if start_ms is not None:
        bounds.append(f"start:{start_ms}")
    if end_ms is not None:
        bounds.append(f"end:{end_ms}")
    return f"(timeRange:({','.join(bounds)}),timeGranularityType:{granularity})"


def api_error(operation: str, response: Any) -> ActionError | None:
    if response.status < 400:
        return None
    return ActionError(message=f"LinkedIn {operation} failed: HTTP {response.status} {response.data}")


async def current_person_urn(context: ExecutionContext) -> str:
    response = await context.fetch(f"{API_ROOT}/v2/me", method="GET", headers=linkedin_headers())
    if response.status >= 400 or not isinstance(response.data, dict) or not response.data.get("id"):
        raise ValueError(f"Could not determine the authenticated member: HTTP {response.status} {response.data}")
    return f"urn:li:person:{response.data['id']}"


async def resolve_actor(value: str | None, actor_type: str, context: ExecutionContext) -> str:
    if value:
        return actor_urn(value, actor_type)
    return await current_person_urn(context)


async def create_post_request(context: ExecutionContext, payload: dict[str, Any], success_message: str):
    response = await context.fetch(f"{API_ROOT}/rest/posts", method="POST", json=payload, headers=linkedin_headers())
    if error := api_error("post creation", response):
        return error
    headers = response.headers or {}
    post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
    return ActionResult(
        data={
            "result": success_message,
            "post_id": post_id,
            "post_url": f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None,
        }
    )


@linkedin_community_management.action("get_profile")
class GetProfileAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        response = await context.fetch(f"{API_ROOT}/v2/me", method="GET", headers=linkedin_headers())
        if error := api_error("profile retrieval", response):
            return error
        return ActionResult(data={"result": "Profile retrieved successfully.", "profile": response.data})


@linkedin_community_management.action("list_managed_organizations")
class ListManagedOrganizationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {"q": "roleAssignee", "state": inputs.get("state", "APPROVED")}
        if inputs.get("role"):
            params["role"] = inputs["role"]
        params.update({"start": inputs.get("start", 0), "count": inputs.get("count", 10)})
        response = await context.fetch(
            f"{API_ROOT}/rest/organizationAcls", method="GET", params=params, headers=linkedin_headers()
        )
        if error := api_error("organization access retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Managed organizations retrieved successfully.",
                "organizations": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_post")
class GetPostAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        response = await context.fetch(
            resource_url("/rest/posts", inputs["post_urn"]), method="GET", headers=linkedin_headers()
        )
        if error := api_error("post retrieval", response):
            return error
        return ActionResult(data={"result": "Post retrieved successfully.", "post": response.data})


@linkedin_community_management.action("list_posts")
class ListPostsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {
            "q": "author",
            "author": encode_urn(actor_urn(inputs["author"], inputs.get("actor_type", "ORGANIZATION"))),
            "start": inputs.get("start", 0),
            "count": inputs.get("count", 10),
        }
        response = await context.fetch(
            restli_query_url("/rest/posts", params),
            method="GET",
            headers=linkedin_headers(**{"X-RestLi-Method": "FINDER"}),
        )
        if error := api_error("post listing", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Posts retrieved successfully.",
                "posts": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            author = await resolve_actor(inputs.get("author"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        payload = {
            "author": author,
            "commentary": inputs["text"],
            "visibility": inputs.get("visibility", "PUBLIC"),
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": inputs.get("disable_reshare", False),
        }
        return await create_post_request(context, payload, "Post created successfully.")


@linkedin_community_management.action("share_article")
class ShareArticleAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            author = await resolve_actor(inputs.get("author"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        payload = {
            "author": author,
            "commentary": inputs.get("commentary", ""),
            "visibility": inputs.get("visibility", "PUBLIC"),
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "article": {
                    "source": inputs["article_url"],
                    "title": inputs["article_title"],
                    "description": inputs.get("article_description", ""),
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": inputs.get("disable_reshare", False),
        }
        return await create_post_request(context, payload, "Article shared successfully.")


@linkedin_community_management.action("reshare_post")
class ResharePostAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            author = await resolve_actor(inputs.get("author"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        payload = {
            "author": author,
            "commentary": inputs.get("commentary", ""),
            "visibility": inputs.get("visibility", "PUBLIC"),
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": inputs.get("disable_reshare", False),
            "reshareContext": {"parent": inputs["original_post_urn"]},
        }
        return await create_post_request(context, payload, "Post reshared successfully.")


@linkedin_community_management.action("update_post")
class UpdatePostAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        response = await context.fetch(
            resource_url("/rest/posts", inputs["post_urn"]),
            method="POST",
            json={"patch": {"$set": {"commentary": inputs["commentary"]}}},
            headers=linkedin_headers(**{"X-RestLi-Method": "PARTIAL_UPDATE"}),
        )
        if error := api_error("post update", response):
            return error
        return ActionResult(data={"result": "Post updated successfully.", "post_urn": inputs["post_urn"]})


@linkedin_community_management.action("delete_post")
class DeletePostAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        response = await context.fetch(
            resource_url("/rest/posts", inputs["post_urn"]), method="DELETE", headers=linkedin_headers()
        )
        if error := api_error("post deletion", response):
            return error
        return ActionResult(data={"result": "Post deleted successfully.", "post_urn": inputs["post_urn"]})


@linkedin_community_management.action("list_comments")
class ListCommentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        url = resource_url("/rest/socialActions", inputs["entity_urn"], "/comments")
        url = restli_query_url(url.raw_path, {"start": inputs.get("start", 0), "count": inputs.get("count", 10)})
        response = await context.fetch(url, method="GET", headers=linkedin_headers())
        if error := api_error("comment retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Comments retrieved successfully.",
                "comments": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("create_comment")
class CreateCommentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            actor = await resolve_actor(inputs.get("actor"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        payload = {"actor": actor, "message": {"text": inputs["text"]}, "object": inputs["root_urn"]}
        if inputs.get("parent_comment_urn"):
            payload["parentComment"] = inputs["parent_comment_urn"]
        target = inputs.get("parent_comment_urn") or inputs["root_urn"]
        response = await context.fetch(
            resource_url("/rest/socialActions", target, "/comments"),
            method="POST",
            json=payload,
            headers=linkedin_headers(),
        )
        if error := api_error("comment creation", response):
            return error
        return ActionResult(data={"result": "Comment created successfully.", "comment": response.data})


@linkedin_community_management.action("update_comment")
class UpdateCommentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        payload = {"patch": {"message": {"$set": {"text": inputs["text"]}}}}
        params = {}
        if inputs.get("actor"):
            params["actor"] = actor_urn(inputs["actor"], inputs.get("actor_type", "ORGANIZATION"))
        path = f"/rest/socialActions/{encode_urn(inputs['root_urn'])}/comments/{inputs['comment_id']}"
        url = restli_query_url(path, {"actor": encode_urn(params["actor"])}) if params else preencoded_url(path)
        response = await context.fetch(
            url,
            method="POST",
            json=payload,
            headers=linkedin_headers(**{"X-RestLi-Method": "PARTIAL_UPDATE"}),
        )
        if error := api_error("comment update", response):
            return error
        return ActionResult(data={"result": "Comment updated successfully.", "comment_id": inputs["comment_id"]})


@linkedin_community_management.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {}
        if inputs.get("actor"):
            params["actor"] = actor_urn(inputs["actor"], inputs.get("actor_type", "ORGANIZATION"))
        path = f"/rest/socialActions/{encode_urn(inputs['root_urn'])}/comments/{inputs['comment_id']}"
        url = restli_query_url(path, {"actor": encode_urn(params["actor"])}) if params else preencoded_url(path)
        response = await context.fetch(url, method="DELETE", headers=linkedin_headers())
        if error := api_error("comment deletion", response):
            return error
        return ActionResult(data={"result": "Comment deleted successfully.", "comment_id": inputs["comment_id"]})


@linkedin_community_management.action("list_reactions")
class ListReactionsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {
            "q": "entity",
            "sort": f"(value:{inputs.get('sort', 'REVERSE_CHRONOLOGICAL')})",
            "start": inputs.get("start", 0),
            "count": inputs.get("count", 10),
        }
        path = f"/rest/reactions/(entity:{encode_urn(inputs['entity_urn'])})"
        response = await context.fetch(restli_query_url(path, params), method="GET", headers=linkedin_headers())
        if error := api_error("reaction retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Reactions retrieved successfully.",
                "reactions": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("create_reaction")
class CreateReactionAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        if inputs["reaction_type"] not in REACTION_TYPES:
            return ActionError(message=f"Unsupported reaction type: {inputs['reaction_type']}")
        try:
            actor = await resolve_actor(inputs.get("actor"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        response = await context.fetch(
            restli_query_url("/rest/reactions", {"actor": encode_urn(actor)}),
            method="POST",
            json={"root": inputs["entity_urn"], "reactionType": inputs["reaction_type"]},
            headers=linkedin_headers(),
        )
        if error := api_error("reaction creation", response):
            return error
        return ActionResult(data={"result": "Reaction created successfully.", "reaction": response.data})


@linkedin_community_management.action("delete_reaction")
class DeleteReactionAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            actor = await resolve_actor(inputs.get("actor"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        key = f"(actor:{encode_urn(actor)},entity:{encode_urn(inputs['entity_urn'])})"
        response = await context.fetch(
            preencoded_url(f"/rest/reactions/{key}"), method="DELETE", headers=linkedin_headers()
        )
        if error := api_error("reaction deletion", response):
            return error
        return ActionResult(data={"result": "Reaction deleted successfully.", "entity_urn": inputs["entity_urn"]})


@linkedin_community_management.action("get_social_metadata")
class GetSocialMetadataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        response = await context.fetch(
            resource_url("/rest/socialMetadata", inputs["entity_urn"]),
            method="GET",
            headers=linkedin_headers(),
        )
        if error := api_error("social metadata retrieval", response):
            return error
        return ActionResult(data={"result": "Social metadata retrieved successfully.", "metadata": response.data})


@linkedin_community_management.action("set_comments_state")
class SetCommentsStateAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            actor = await resolve_actor(inputs.get("actor"), inputs.get("actor_type", "PERSON"), context)
        except ValueError as exc:
            return ActionError(message=str(exc))
        path = f"/rest/socialMetadata/{encode_urn(inputs['entity_urn'])}"
        response = await context.fetch(
            restli_query_url(path, {"actor": encode_urn(actor)}),
            method="POST",
            json={"patch": {"$set": {"commentsState": inputs["comments_state"]}}},
            headers=linkedin_headers(**{"X-RestLi-Method": "PARTIAL_UPDATE"}),
        )
        if error := api_error("comments state update", response):
            return error
        return ActionResult(
            data={"result": "Comments state updated successfully.", "comments_state": inputs["comments_state"]}
        )


@linkedin_community_management.action("search_organization_followers")
class SearchOrganizationFollowersAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {
            "q": "organizationFollowers",
            "keywords": inputs["keywords"],
            "organization": encode_urn(actor_urn(inputs["organization"], "ORGANIZATION")),
        }
        response = await context.fetch(
            restli_query_url("/rest/peopleTypeahead", params), method="GET", headers=linkedin_headers()
        )
        if error := api_error("organization follower search", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Organization followers retrieved successfully.",
                "followers": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_organization_follower_statistics")
class GetOrganizationFollowerStatisticsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": encode_urn(actor_urn(inputs["organization"], "ORGANIZATION")),
        }
        start_ms = inputs.get("start_ms")
        end_ms = inputs.get("end_ms")
        if start_ms is not None:
            params["timeIntervals"] = restli_time_intervals(start_ms, end_ms, inputs.get("granularity", "DAY"))
        elif end_ms is not None:
            return ActionError(message="start_ms is required when end_ms is provided for follower statistics")
        response = await context.fetch(
            restli_query_url("/rest/organizationalEntityFollowerStatistics", params),
            method="GET",
            headers=linkedin_headers(),
        )
        if error := api_error("organization follower statistics retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Organization follower statistics retrieved successfully.",
                "statistics": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_organization_post_statistics")
class GetOrganizationPostStatisticsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        params: dict[str, Any] = {
            "q": "organizationalEntity",
            "organizationalEntity": encode_urn(actor_urn(inputs["organization"], "ORGANIZATION")),
        }
        if inputs.get("post_urn"):
            key = "ugcPosts" if ":ugcPost:" in inputs["post_urn"] else "shares"
            params[key] = f"List({encode_urn(inputs['post_urn'])})"
        elif inputs.get("start_ms") is not None or inputs.get("end_ms") is not None:
            params["timeIntervals"] = restli_time_intervals(
                inputs.get("start_ms"), inputs.get("end_ms"), inputs.get("granularity", "DAY")
            )
        response = await context.fetch(
            restli_query_url("/rest/organizationalEntityShareStatistics", params),
            method="GET",
            headers=linkedin_headers(),
        )
        if error := api_error("organization post statistics retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Organization post statistics retrieved successfully.",
                "statistics": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_member_post_analytics")
class GetMemberPostAnalyticsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        metric = inputs["metric"]
        if metric not in MEMBER_POST_METRICS:
            return ActionError(message=f"Unsupported member post metric: {metric}")
        post_urn = inputs.get("post_urn")
        params: dict[str, Any] = {
            "q": "entity" if post_urn else "me",
            "queryType": metric,
            "aggregation": inputs.get("aggregation", "TOTAL"),
        }
        if post_urn:
            urn_type = "ugc" if ":ugcPost:" in post_urn else "share"
            params["entity"] = f"({urn_type}:{encode_urn(post_urn)})"
        if date_range := restli_date_range(inputs.get("start_date"), inputs.get("end_date")):
            params["dateRange"] = date_range
        response = await context.fetch(
            restli_query_url("/rest/memberCreatorPostAnalytics", params), method="GET", headers=linkedin_headers()
        )
        if error := api_error("member post analytics retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Member post analytics retrieved successfully.",
                "analytics": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_member_follower_statistics")
class GetMemberFollowerStatisticsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        date_range = restli_date_range(inputs.get("start_date"), inputs.get("end_date"))
        params = {"q": "dateRange", "dateRange": date_range} if date_range else {"q": "me"}
        response = await context.fetch(
            restli_query_url("/rest/memberFollowersCount", params), method="GET", headers=linkedin_headers()
        )
        if error := api_error("member follower statistics retrieval", response):
            return error
        body = response.data if isinstance(response.data, dict) else {}
        return ActionResult(
            data={
                "result": "Member follower statistics retrieved successfully.",
                "statistics": body.get("elements", []),
                "paging": body.get("paging", {}),
            }
        )


@linkedin_community_management.action("get_connection_count")
class GetConnectionCountAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        person_id = inputs.get("person_id")
        if not person_id:
            try:
                person_id = (await current_person_urn(context)).rsplit(":", 1)[1]
            except ValueError as exc:
                return ActionError(message=str(exc))
        person_urn = actor_urn(person_id, "PERSON")
        response = await context.fetch(
            resource_url("/v2/connections", person_urn), method="GET", headers=linkedin_headers()
        )
        if error := api_error("connection count retrieval", response):
            return error
        count = response.data.get("firstDegreeSize") if isinstance(response.data, dict) else None
        return ActionResult(data={"result": "Connection count retrieved successfully.", "first_degree_size": count})

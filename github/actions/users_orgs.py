"""
GitHub integration - User and organization actions.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("get_user")
class GetUser(ActionHandler):
    """Get user information"""

    @handle_github_errors("get_user")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        user = await GitHubAPI.get_user(context, username=inputs.get("username"))

        return ActionResult(
            data={
                "login": user["login"],
                "id": user["id"],
                "name": user.get("name"),
                "company": user.get("company"),
                "blog": user.get("blog"),
                "location": user.get("location"),
                "email": user.get("email"),
                "bio": user.get("bio"),
                "public_repos": user["public_repos"],
                "public_gists": user["public_gists"],
                "followers": user["followers"],
                "following": user["following"],
                "created_at": user["created_at"],
                "updated_at": user["updated_at"],
                "avatar_url": user["avatar_url"],
                "html_url": user["html_url"],
            },
            cost_usd=0.0,
        )


@github.action("list_organization_members")
class ListOrganizationMembers(ActionHandler):
    """List organization members"""

    @handle_github_errors("list_organization_members")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        members = await GitHubAPI.list_organization_members(context, inputs["org"], role=inputs.get("role", "all"))

        return ActionResult(
            data=[
                {
                    "login": member["login"],
                    "id": member["id"],
                    "type": member["type"],
                    "site_admin": member["site_admin"],
                    "avatar_url": member["avatar_url"],
                    "url": member["html_url"],
                }
                for member in members
            ],
            cost_usd=0.0,
        )


# =============================================================================
# TEAMS
# =============================================================================
#
# Teams belong to an organization and are addressed by their *slug*, never by
# their numeric id (the id-based team endpoints are deprecated). Both endpoints
# below need the `read:org` scope.
#
# GitHub deliberately hides private organization structure: when the token is
# missing `read:org`, or the authenticated user simply is not a member of the
# organization, these endpoints answer **404, not 403**. A 404 here therefore
# does not mean the organization or team has been deleted.
#
# Reference: https://docs.github.com/en/rest/teams/teams
#            https://docs.github.com/en/rest/teams/members


async def _list_org_teams(context: ExecutionContext, org: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """GET /orgs/{org}/teams — every team in one organization that the caller can see."""
    url = f"{GitHubAPI.BASE_URL}/orgs/{org}/teams"
    return await GitHubAPI.paginated_fetch(context, url, limit=limit)


async def _list_authenticated_user_teams(
    context: ExecutionContext, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """GET /user/teams — teams across every organization the authenticated user belongs to.

    Returns "full team" objects, which carry ``organization``, ``members_count``
    and ``repos_count`` on top of what ``GET /orgs/{org}/teams`` returns.
    """
    url = f"{GitHubAPI.BASE_URL}/user/teams"
    return await GitHubAPI.paginated_fetch(context, url, limit=limit)


async def _list_team_members(
    context: ExecutionContext,
    org: str,
    team_slug: str,
    role: str = "all",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """GET /orgs/{org}/teams/{team_slug}/members — team members, including those of child teams."""
    url = f"{GitHubAPI.BASE_URL}/orgs/{org}/teams/{team_slug}/members"
    return await GitHubAPI.paginated_fetch(context, url, params={"role": role}, limit=limit)


def _team_summary(team: Dict[str, Any]) -> Dict[str, Any]:
    """Shape one team into the response body, tolerating the two response schemas."""
    parent = team.get("parent")
    organization = team.get("organization")

    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "slug": team.get("slug"),
        "description": team.get("description"),
        "privacy": team.get("privacy"),
        "notification_setting": team.get("notification_setting"),
        "permission": team.get("permission"),
        "parent": (
            {
                "id": parent.get("id"),
                "name": parent.get("name"),
                "slug": parent.get("slug"),
            }
            if parent
            else None
        ),
        # Only /user/teams returns these three — they stay None for /orgs/{org}/teams.
        "organization": organization.get("login") if organization else None,
        "members_count": team.get("members_count"),
        "repos_count": team.get("repos_count"),
        "url": team.get("html_url"),
    }


@github.action("get_teams")
class GetTeams(ActionHandler):
    """List an organization's teams, or every team the authenticated user belongs to"""

    @handle_github_errors("get_teams")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        org = inputs.get("org")
        limit = inputs.get("limit")

        if org:
            teams = await _list_org_teams(context, org, limit=limit)
        else:
            teams = await _list_authenticated_user_teams(context, limit=limit)

        return ActionResult(data=[_team_summary(team) for team in teams], cost_usd=0.0)


@github.action("get_team_members")
class GetTeamMembers(ActionHandler):
    """List the members of a team, identified by its slug"""

    @handle_github_errors("get_team_members")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        members = await _list_team_members(
            context,
            inputs["org"],
            inputs["team_slug"],
            role=inputs.get("role", "all"),
            limit=inputs.get("limit"),
        )

        return ActionResult(
            data=[
                {
                    "login": member.get("login"),
                    "id": member.get("id"),
                    "type": member.get("type"),
                    "site_admin": member.get("site_admin"),
                    "avatar_url": member.get("avatar_url"),
                    "url": member.get("html_url"),
                }
                for member in members
            ],
            cost_usd=0.0,
        )

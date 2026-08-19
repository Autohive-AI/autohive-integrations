"""
GitHub integration - Release and tag actions.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("list_tags")
class ListTags(ActionHandler):
    """List tags for a repository"""

    @handle_github_errors("list_tags")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        tags = await GitHubAPI.list_tags(
            context,
            inputs["owner"],
            inputs["repo"],
            per_page=inputs.get("per_page", 30),
            page=inputs.get("page", 1),
        )

        return ActionResult(
            data=[
                {
                    "name": tag["name"],
                    "commit": {
                        "sha": tag["commit"]["sha"],
                        "url": tag["commit"]["url"],
                    },
                    "zipball_url": tag.get("zipball_url"),
                    "tarball_url": tag.get("tarball_url"),
                    "node_id": tag.get("node_id"),
                }
                for tag in tags
            ],
            cost_usd=0.0,
        )


@github.action("list_releases")
class ListReleases(ActionHandler):
    """List releases for a repository"""

    @handle_github_errors("list_releases")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        releases = await GitHubAPI.list_releases(
            context,
            inputs["owner"],
            inputs["repo"],
            per_page=inputs.get("per_page", 30),
            page=inputs.get("page", 1),
        )

        return ActionResult(
            data=[
                {
                    "id": release["id"],
                    "tag_name": release["tag_name"],
                    "name": release.get("name"),
                    "body": release.get("body"),
                    "draft": release.get("draft", False),
                    "prerelease": release.get("prerelease", False),
                    "created_at": release["created_at"],
                    "published_at": release.get("published_at"),
                    "html_url": release["html_url"],
                    "tarball_url": release.get("tarball_url"),
                    "zipball_url": release.get("zipball_url"),
                    "author": {
                        "login": release["author"]["login"],
                        "id": release["author"]["id"],
                        "avatar_url": release["author"]["avatar_url"],
                    }
                    if release.get("author")
                    else None,
                    "assets": [
                        {
                            "id": asset["id"],
                            "name": asset["name"],
                            "size": asset["size"],
                            "download_count": asset["download_count"],
                            "browser_download_url": asset["browser_download_url"],
                        }
                        for asset in release.get("assets", [])
                    ],
                }
                for release in releases
            ],
            cost_usd=0.0,
        )


@github.action("get_release")
class GetRelease(ActionHandler):
    """Get a specific release by ID"""

    @handle_github_errors("get_release")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_release(context, inputs["owner"], inputs["repo"], inputs["release_id"])

        return ActionResult(
            data={
                "id": release["id"],
                "tag_name": release["tag_name"],
                "target_commitish": release.get("target_commitish"),
                "name": release.get("name"),
                "body": release.get("body"),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "created_at": release["created_at"],
                "published_at": release.get("published_at"),
                "html_url": release["html_url"],
                "tarball_url": release.get("tarball_url"),
                "zipball_url": release.get("zipball_url"),
                "author": {
                    "login": release["author"]["login"],
                    "id": release["author"]["id"],
                    "avatar_url": release["author"]["avatar_url"],
                }
                if release.get("author")
                else None,
                "assets": [
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "label": asset.get("label"),
                        "state": asset["state"],
                        "content_type": asset["content_type"],
                        "size": asset["size"],
                        "download_count": asset["download_count"],
                        "browser_download_url": asset["browser_download_url"],
                        "created_at": asset["created_at"],
                        "updated_at": asset["updated_at"],
                    }
                    for asset in release.get("assets", [])
                ],
            },
            cost_usd=0.0,
        )


@github.action("get_latest_release")
class GetLatestRelease(ActionHandler):
    """Get the latest release for a repository"""

    @handle_github_errors("get_latest_release")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_latest_release(context, inputs["owner"], inputs["repo"])

        return ActionResult(
            data={
                "id": release["id"],
                "tag_name": release["tag_name"],
                "target_commitish": release.get("target_commitish"),
                "name": release.get("name"),
                "body": release.get("body"),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "created_at": release["created_at"],
                "published_at": release.get("published_at"),
                "html_url": release["html_url"],
                "tarball_url": release.get("tarball_url"),
                "zipball_url": release.get("zipball_url"),
                "author": {
                    "login": release["author"]["login"],
                    "id": release["author"]["id"],
                    "avatar_url": release["author"]["avatar_url"],
                }
                if release.get("author")
                else None,
                "assets": [
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "size": asset["size"],
                        "download_count": asset["download_count"],
                        "browser_download_url": asset["browser_download_url"],
                    }
                    for asset in release.get("assets", [])
                ],
            },
            cost_usd=0.0,
        )


@github.action("get_release_by_tag")
class GetReleaseByTag(ActionHandler):
    """Get a release by tag name"""

    @handle_github_errors("get_release_by_tag")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_release_by_tag(context, inputs["owner"], inputs["repo"], inputs["tag"])

        return ActionResult(
            data={
                "id": release["id"],
                "tag_name": release["tag_name"],
                "target_commitish": release.get("target_commitish"),
                "name": release.get("name"),
                "body": release.get("body"),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "created_at": release["created_at"],
                "published_at": release.get("published_at"),
                "html_url": release["html_url"],
                "tarball_url": release.get("tarball_url"),
                "zipball_url": release.get("zipball_url"),
                "author": {
                    "login": release["author"]["login"],
                    "id": release["author"]["id"],
                    "avatar_url": release["author"]["avatar_url"],
                }
                if release.get("author")
                else None,
                "assets": [
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "size": asset["size"],
                        "download_count": asset["download_count"],
                        "browser_download_url": asset["browser_download_url"],
                    }
                    for asset in release.get("assets", [])
                ],
            },
            cost_usd=0.0,
        )

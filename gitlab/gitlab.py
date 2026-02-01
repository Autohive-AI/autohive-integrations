from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any
from urllib.parse import quote

# Create the integration
gitlab = Integration.load()

# Base URL for GitLab API (gitlab.com only - self-hosted GitLab is not supported)
GITLAB_API_BASE_URL = "https://gitlab.com/api/v4"

# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.
#
# This integration uses read-only scopes:
# - read_api: Read access to the API
# - read_user: Read user profile data
# - read_repository: Read repository data
# - read_registry: Read container registry images


def encode_project_id(project_id: str) -> str:
    """URL-encode project ID if it's a path (contains /)."""
    if "/" in str(project_id):
        return quote(str(project_id), safe="")
    return str(project_id)


# ---- User Handlers ----

@gitlab.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Get information about the authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/user",
                method="GET"
            )

            return ActionResult(
                data={"user": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Project Handlers ----

@gitlab.action("list_projects")
class ListProjectsAction(ActionHandler):
    """List projects accessible by the authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["owned", "membership", "starred", "search", "visibility",
                        "order_by", "sort", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects",
                method="GET",
                params=params if params else None
            )

            projects = response if isinstance(response, list) else []

            return ActionResult(
                data={"projects": projects, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"projects": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_project")
class GetProjectAction(ActionHandler):
    """Get details of a specific project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("statistics"):
                params["statistics"] = "true"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"project": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"project": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Issue Handlers ----

@gitlab.action("list_issues")
class ListIssuesAction(ActionHandler):
    """List issues for a project or globally."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["state", "labels", "milestone", "scope", "assignee_id",
                        "author_id", "search", "created_after", "created_before",
                        "updated_after", "updated_before", "order_by", "sort",
                        "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            if inputs.get("project_id"):
                project_id = encode_project_id(inputs["project_id"])
                url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/issues"
            else:
                url = f"{GITLAB_API_BASE_URL}/issues"

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            issues = response if isinstance(response, list) else []

            return ActionResult(
                data={"issues": issues, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"issues": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_issue")
class GetIssueAction(ActionHandler):
    """Get details of a specific issue."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            issue_iid = inputs["issue_iid"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/issues/{issue_iid}",
                method="GET"
            )

            return ActionResult(
                data={"issue": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"issue": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Merge Request Handlers ----

@gitlab.action("list_merge_requests")
class ListMergeRequestsAction(ActionHandler):
    """List merge requests for a project or globally."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["state", "labels", "milestone", "scope", "author_id",
                        "assignee_id", "reviewer_id", "source_branch", "target_branch",
                        "search", "created_after", "created_before", "updated_after",
                        "updated_before", "order_by", "sort", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            if inputs.get("project_id"):
                project_id = encode_project_id(inputs["project_id"])
                url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests"
            else:
                url = f"{GITLAB_API_BASE_URL}/merge_requests"

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            merge_requests = response if isinstance(response, list) else []

            return ActionResult(
                data={"merge_requests": merge_requests, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"merge_requests": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_merge_request")
class GetMergeRequestAction(ActionHandler):
    """Get details of a specific merge request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            mr_iid = inputs["merge_request_iid"]

            params = {}
            if inputs.get("include_diverged_commits_count"):
                params["include_diverged_commits_count"] = "true"
            if inputs.get("include_rebase_in_progress"):
                params["include_rebase_in_progress"] = "true"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"merge_request": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"merge_request": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_merge_request_changes")
class GetMergeRequestChangesAction(ActionHandler):
    """Get the changes (diff) of a merge request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            mr_iid = inputs["merge_request_iid"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes",
                method="GET"
            )

            changes = response.get("changes", []) if isinstance(response, dict) else []

            return ActionResult(
                data={"changes": changes, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"changes": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("list_merge_request_commits")
class ListMergeRequestCommitsAction(ActionHandler):
    """Get commits associated with a merge request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            mr_iid = inputs["merge_request_iid"]

            params = {}
            for key in ["per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/commits",
                method="GET",
                params=params if params else None
            )

            commits = response if isinstance(response, list) else []

            return ActionResult(
                data={"commits": commits, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"commits": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Branch Handlers ----

@gitlab.action("list_branches")
class ListBranchesAction(ActionHandler):
    """List repository branches."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            for key in ["search", "regex", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/branches",
                method="GET",
                params=params if params else None
            )

            branches = response if isinstance(response, list) else []

            return ActionResult(
                data={"branches": branches, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"branches": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_branch")
class GetBranchAction(ActionHandler):
    """Get details of a specific branch."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            branch = quote(inputs["branch"], safe="")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/branches/{branch}",
                method="GET"
            )

            return ActionResult(
                data={"branch": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"branch": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Commit Handlers ----

@gitlab.action("list_commits")
class ListCommitsAction(ActionHandler):
    """List repository commits."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            for key in ["ref_name", "since", "until", "path", "author", "all",
                        "with_stats", "first_parent", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits",
                method="GET",
                params=params if params else None
            )

            commits = response if isinstance(response, list) else []

            return ActionResult(
                data={"commits": commits, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"commits": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_commit")
class GetCommitAction(ActionHandler):
    """Get details of a specific commit."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            sha = quote(inputs["sha"], safe="")

            params = {}
            if inputs.get("stats"):
                params["stats"] = "true"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits/{sha}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"commit": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"commit": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_commit_diff")
class GetCommitDiffAction(ActionHandler):
    """Get the diff of a commit."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            sha = quote(inputs["sha"], safe="")

            params = {}
            for key in ["per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits/{sha}/diff",
                method="GET",
                params=params if params else None
            )

            diffs = response if isinstance(response, list) else []

            return ActionResult(
                data={"diffs": diffs, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"diffs": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Pipeline Handlers ----

@gitlab.action("list_pipelines")
class ListPipelinesAction(ActionHandler):
    """List pipelines for a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            for key in ["status", "ref", "sha", "source", "username",
                        "updated_after", "updated_before", "order_by", "sort",
                        "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines",
                method="GET",
                params=params if params else None
            )

            pipelines = response if isinstance(response, list) else []

            return ActionResult(
                data={"pipelines": pipelines, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"pipelines": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_pipeline")
class GetPipelineAction(ActionHandler):
    """Get details of a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            pipeline_id = inputs["pipeline_id"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines/{pipeline_id}",
                method="GET"
            )

            return ActionResult(
                data={"pipeline": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"pipeline": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("list_pipeline_jobs")
class ListPipelineJobsAction(ActionHandler):
    """List jobs for a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            pipeline_id = inputs["pipeline_id"]

            params = {}
            for key in ["scope", "include_retried", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                method="GET",
                params=params if params else None
            )

            jobs = response if isinstance(response, list) else []

            return ActionResult(
                data={"jobs": jobs, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"jobs": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Repository Handlers ----

@gitlab.action("list_repository_tree")
class ListRepositoryTreeAction(ActionHandler):
    """List files and directories in a repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            for key in ["path", "ref", "recursive", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/tree",
                method="GET",
                params=params if params else None
            )

            tree = response if isinstance(response, list) else []

            return ActionResult(
                data={"tree": tree, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"tree": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_file")
class GetFileAction(ActionHandler):
    """Get a file's metadata and content from the repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            file_path = quote(inputs["file_path"], safe="")
            ref = inputs["ref"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/files/{file_path}",
                method="GET",
                params={"ref": ref}
            )

            return ActionResult(
                data={"file": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"file": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_file_raw")
class GetFileRawAction(ActionHandler):
    """Get a file's raw content from the repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            file_path = quote(inputs["file_path"], safe="")
            ref = inputs["ref"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/files/{file_path}/raw",
                method="GET",
                params={"ref": ref}
            )

            # Response may be string or bytes depending on content type
            if isinstance(response, bytes):
                content = response.decode("utf-8", errors="replace")
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            return ActionResult(
                data={"content": content, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"content": "", "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("compare_branches")
class CompareBranchesAction(ActionHandler):
    """Compare two branches, tags, or commits."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {
                "from": inputs["from"],
                "to": inputs["to"]
            }
            if inputs.get("straight") is not None:
                params["straight"] = "true" if inputs["straight"] else "false"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/compare",
                method="GET",
                params=params
            )

            return ActionResult(
                data={"comparison": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comparison": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Container Registry Handlers ----

@gitlab.action("list_container_registry_repositories")
class ListContainerRegistryRepositoriesAction(ActionHandler):
    """List container registry repositories for a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            for key in ["tags", "tags_count", "per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories",
                method="GET",
                params=params if params else None
            )

            repositories = response if isinstance(response, list) else []

            return ActionResult(
                data={"repositories": repositories, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"repositories": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_container_registry_repository")
class GetContainerRegistryRepositoryAction(ActionHandler):
    """Get details of a specific container registry repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            repository_id = inputs["repository_id"]

            params = {}
            for key in ["tags", "tags_count"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories/{repository_id}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"repository": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"repository": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("list_container_registry_tags")
class ListContainerRegistryTagsAction(ActionHandler):
    """List tags for a container registry repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            repository_id = inputs["repository_id"]

            params = {}
            for key in ["per_page", "page"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories/{repository_id}/tags",
                method="GET",
                params=params if params else None
            )

            tags = response if isinstance(response, list) else []

            return ActionResult(
                data={"tags": tags, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"tags": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@gitlab.action("get_container_registry_tag")
class GetContainerRegistryTagAction(ActionHandler):
    """Get details of a specific container registry tag."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            repository_id = inputs["repository_id"]
            tag_name = quote(inputs["tag_name"], safe="")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories/{repository_id}/tags/{tag_name}",
                method="GET"
            )

            return ActionResult(
                data={"tag": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"tag": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
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
            response = await context.fetch(f"{GITLAB_API_BASE_URL}/user", method="GET")

            return ActionResult(data={"user": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Project Handlers ----


@gitlab.action("list_projects")
class ListProjectsAction(ActionHandler):
    """List projects accessible by the authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("owned") is not None:
                params["owned"] = "true" if inputs.get("owned") else "false"
            if inputs.get("membership") is not None:
                params["membership"] = "true" if inputs.get("membership") else "false"
            if inputs.get("starred") is not None:
                params["starred"] = "true" if inputs.get("starred") else "false"
            if inputs.get("search") is not None:
                params["search"] = inputs.get("search")
            if inputs.get("visibility") is not None:
                params["visibility"] = inputs.get("visibility")
            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")
            if inputs.get("sort") is not None:
                params["sort"] = inputs.get("sort")
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects",
                method="GET",
                params=params if params else None,
            )

            projects = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"projects": projects}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params=params if params else None,
            )

            return ActionResult(data={"project": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Issue Handlers ----


@gitlab.action("list_issues")
class ListIssuesAction(ActionHandler):
    """List issues for a project or globally."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("state") is not None:
                params["state"] = inputs.get("state")
            if inputs.get("labels") is not None:
                params["labels"] = inputs.get("labels")
            if inputs.get("milestone") is not None:
                params["milestone"] = inputs.get("milestone")
            if inputs.get("scope") is not None:
                params["scope"] = inputs.get("scope")
            if inputs.get("assignee_id") is not None:
                params["assignee_id"] = inputs.get("assignee_id")
            if inputs.get("author_id") is not None:
                params["author_id"] = inputs.get("author_id")
            if inputs.get("search") is not None:
                params["search"] = inputs.get("search")
            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")
            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")
            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")
            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")
            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")
            if inputs.get("sort") is not None:
                params["sort"] = inputs.get("sort")
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("project_id"):
                project_id = encode_project_id(inputs["project_id"])
                url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/issues"
            else:
                url = f"{GITLAB_API_BASE_URL}/issues"

            response = await context.fetch(url, method="GET", params=params if params else None)

            issues = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"issues": issues}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_issue")
class GetIssueAction(ActionHandler):
    """Get details of a specific issue."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            issue_iid = inputs["issue_iid"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/issues/{issue_iid}",
                method="GET",
            )

            return ActionResult(data={"issue": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Merge Request Handlers ----


@gitlab.action("list_merge_requests")
class ListMergeRequestsAction(ActionHandler):
    """List merge requests for a project or globally."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("state") is not None:
                params["state"] = inputs.get("state")
            if inputs.get("labels") is not None:
                params["labels"] = inputs.get("labels")
            if inputs.get("milestone") is not None:
                params["milestone"] = inputs.get("milestone")
            if inputs.get("scope") is not None:
                params["scope"] = inputs.get("scope")
            if inputs.get("author_id") is not None:
                params["author_id"] = inputs.get("author_id")
            if inputs.get("assignee_id") is not None:
                params["assignee_id"] = inputs.get("assignee_id")
            if inputs.get("reviewer_id") is not None:
                params["reviewer_id"] = inputs.get("reviewer_id")
            if inputs.get("source_branch") is not None:
                params["source_branch"] = inputs.get("source_branch")
            if inputs.get("target_branch") is not None:
                params["target_branch"] = inputs.get("target_branch")
            if inputs.get("search") is not None:
                params["search"] = inputs.get("search")
            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")
            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")
            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")
            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")
            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")
            if inputs.get("sort") is not None:
                params["sort"] = inputs.get("sort")
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("project_id"):
                project_id = encode_project_id(inputs["project_id"])
                url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests"
            else:
                url = f"{GITLAB_API_BASE_URL}/merge_requests"

            response = await context.fetch(url, method="GET", params=params if params else None)

            merge_requests = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"merge_requests": merge_requests}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params=params if params else None,
            )

            return ActionResult(data={"merge_request": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_merge_request_changes")
class GetMergeRequestChangesAction(ActionHandler):
    """Get the changes (diff) of a merge request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            mr_iid = inputs["merge_request_iid"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes",
                method="GET",
            )

            changes = response.data.get("changes", []) if isinstance(response.data, dict) else []

            return ActionResult(data={"changes": changes}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("list_merge_request_commits")
class ListMergeRequestCommitsAction(ActionHandler):
    """Get commits associated with a merge request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            mr_iid = inputs["merge_request_iid"]

            params = {}
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/commits",
                method="GET",
                params=params if params else None,
            )

            commits = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"commits": commits}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Branch Handlers ----


@gitlab.action("list_branches")
class ListBranchesAction(ActionHandler):
    """List repository branches."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("search") is not None:
                params["search"] = inputs.get("search")
            if inputs.get("regex") is not None:
                params["regex"] = inputs.get("regex")
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/branches",
                method="GET",
                params=params if params else None,
            )

            branches = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"branches": branches}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_branch")
class GetBranchAction(ActionHandler):
    """Get details of a specific branch."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            branch = quote(inputs["branch"], safe="")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/branches/{branch}",
                method="GET",
            )

            return ActionResult(data={"branch": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Commit Handlers ----


@gitlab.action("list_commits")
class ListCommitsAction(ActionHandler):
    """List repository commits."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("ref_name") is not None:
                params["ref_name"] = inputs.get("ref_name")
            if inputs.get("since") is not None:
                params["since"] = inputs.get("since")
            if inputs.get("until") is not None:
                params["until"] = inputs.get("until")
            if inputs.get("path") is not None:
                params["path"] = inputs.get("path")
            if inputs.get("author") is not None:
                params["author"] = inputs.get("author")
            if inputs.get("all") is not None:
                params["all"] = "true" if inputs.get("all") else "false"
            if inputs.get("with_stats") is not None:
                params["with_stats"] = "true" if inputs.get("with_stats") else "false"
            if inputs.get("first_parent") is not None:
                params["first_parent"] = "true" if inputs.get("first_parent") else "false"
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits",
                method="GET",
                params=params if params else None,
            )

            commits = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"commits": commits}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params=params if params else None,
            )

            return ActionResult(data={"commit": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_commit_diff")
class GetCommitDiffAction(ActionHandler):
    """Get the diff of a commit."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            sha = quote(inputs["sha"], safe="")

            params = {}
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits/{sha}/diff",
                method="GET",
                params=params if params else None,
            )

            diffs = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"diffs": diffs}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Pipeline Handlers ----


@gitlab.action("list_pipelines")
class ListPipelinesAction(ActionHandler):
    """List pipelines for a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("status") is not None:
                params["status"] = inputs.get("status")
            if inputs.get("ref") is not None:
                params["ref"] = inputs.get("ref")
            if inputs.get("sha") is not None:
                params["sha"] = inputs.get("sha")
            if inputs.get("source") is not None:
                params["source"] = inputs.get("source")
            if inputs.get("username") is not None:
                params["username"] = inputs.get("username")
            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")
            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")
            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")
            if inputs.get("sort") is not None:
                params["sort"] = inputs.get("sort")
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines",
                method="GET",
                params=params if params else None,
            )

            pipelines = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"pipelines": pipelines}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_pipeline")
class GetPipelineAction(ActionHandler):
    """Get details of a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            pipeline_id = inputs["pipeline_id"]

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines/{pipeline_id}",
                method="GET",
            )

            return ActionResult(data={"pipeline": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("list_pipeline_jobs")
class ListPipelineJobsAction(ActionHandler):
    """List jobs for a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            pipeline_id = inputs["pipeline_id"]

            params = {}
            if inputs.get("scope") is not None:
                params["scope"] = inputs.get("scope")
            if inputs.get("include_retried") is not None:
                params["include_retried"] = "true" if inputs.get("include_retried") else "false"
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                method="GET",
                params=params if params else None,
            )

            jobs = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"jobs": jobs}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Repository Handlers ----


@gitlab.action("list_repository_tree")
class ListRepositoryTreeAction(ActionHandler):
    """List files and directories in a repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("path") is not None:
                params["path"] = inputs.get("path")
            if inputs.get("ref") is not None:
                params["ref"] = inputs.get("ref")
            if inputs.get("recursive") is not None:
                params["recursive"] = "true" if inputs.get("recursive") else "false"
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/tree",
                method="GET",
                params=params if params else None,
            )

            tree = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"tree": tree}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params={"ref": ref},
            )

            return ActionResult(data={"file": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params={"ref": ref},
            )

            # Response body may be string or bytes depending on content type
            body = response.data
            if isinstance(body, bytes):
                content = body.decode("utf-8", errors="replace")
            elif isinstance(body, str):
                content = body
            else:
                content = str(body)

            return ActionResult(data={"content": content}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("compare_branches")
class CompareBranchesAction(ActionHandler):
    """Compare two branches, tags, or commits."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {"from": inputs["from"], "to": inputs["to"]}
            if inputs.get("straight") is not None:
                params["straight"] = "true" if inputs["straight"] else "false"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/compare",
                method="GET",
                params=params,
            )

            return ActionResult(data={"comparison": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Container Registry Handlers ----


@gitlab.action("list_container_registry_repositories")
class ListContainerRegistryRepositoriesAction(ActionHandler):
    """List container registry repositories for a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])

            params = {}
            if inputs.get("tags") is not None:
                params["tags"] = "true" if inputs.get("tags") else "false"
            if inputs.get("tags_count") is not None:
                params["tags_count"] = "true" if inputs.get("tags_count") else "false"
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories",
                method="GET",
                params=params if params else None,
            )

            repositories = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"repositories": repositories}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("get_container_registry_repository")
class GetContainerRegistryRepositoryAction(ActionHandler):
    """Get details of a specific container registry repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            repository_id = inputs["repository_id"]

            params = {}
            if inputs.get("tags") is not None:
                params["tags"] = "true" if inputs.get("tags") else "false"
            if inputs.get("tags_count") is not None:
                params["tags_count"] = "true" if inputs.get("tags_count") else "false"

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories/{repository_id}",
                method="GET",
                params=params if params else None,
            )

            return ActionResult(data={"repository": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@gitlab.action("list_container_registry_tags")
class ListContainerRegistryTagsAction(ActionHandler):
    """List tags for a container registry repository."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = encode_project_id(inputs["project_id"])
            repository_id = inputs["repository_id"]

            params = {}
            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{GITLAB_API_BASE_URL}/projects/{project_id}/registry/repositories/{repository_id}/tags",
                method="GET",
                params=params if params else None,
            )

            tags = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"tags": tags}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                method="GET",
            )

            return ActionResult(data={"tag": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))

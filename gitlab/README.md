# GitLab Integration for Autohive

Connects Autohive to the GitLab API v4 for read-only access to projects, issues, merge requests, CI/CD pipelines, repositories, and container registry.

## Description

This integration provides read-only access to GitLab's DevOps platform capabilities. It allows users to view projects, track issues, review merge requests, monitor CI/CD pipelines, browse repository contents, and access container registry information programmatically.

The integration uses GitLab REST API v4 with OAuth 2.0 authentication and implements 25 read-only actions covering all major GitLab read operations.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your GitLab account.

### Authentication Method

The integration uses OAuth 2.0 with the following scopes:
- `read_api` - Read-only access to the API
- `read_user` - Read access to authenticated user profile data
- `read_repository` - Read-only access to repository files
- `read_registry` - Read access to container registry images
- `profile` - Read-only access to user's personal information via OpenID Connect
- `email` - Read-only access to user's primary email via OpenID Connect

### Setup Steps in Autohive

1. Add GitLab integration in Autohive
2. Click "Connect to GitLab" to authorize the integration
3. Sign in to your GitLab account when prompted
4. Review and authorize the requested permissions
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh (tokens expire after 2 hours and are automatically refreshed).

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

## Actions (25 Total)

### User (1 action)

#### `get_current_user`
Get information about the authenticated user including profile and email.

**Inputs:** None

**Outputs:**
- `user`: User information including id, username, email, name, state, avatar_url
- `result`: Success status

---

### Projects (2 actions)

#### `list_projects`
List projects accessible by the authenticated user.

**Inputs:**
- `owned` (optional): Limit to projects owned by user
- `membership` (optional): Limit to projects user is member of
- `starred` (optional): Limit to starred projects
- `search` (optional): Search by name
- `visibility` (optional): public, internal, or private
- `order_by` (optional): id, name, path, created_at, updated_at, last_activity_at
- `sort` (optional): asc or desc
- `per_page` (optional): Results per page (max 100)
- `page` (optional): Page number

**Outputs:**
- `projects`: Array of project objects
- `result`: Success status

---

#### `get_project`
Get details of a specific project including statistics.

**Inputs:**
- `project_id` (required): ID or URL-encoded path (e.g., '123' or 'namespace/project')
- `statistics` (optional): Include project statistics (commit count, storage size, etc.)

**Outputs:**
- `project`: Project details
- `result`: Success status

---

### Issues (2 actions)

#### `list_issues`
List issues for a project or globally with filtering options.

**Inputs:**
- `project_id` (optional): ID or path (omit for global issues)
- `state` (optional): opened, closed, or all
- `labels` (optional): Comma-separated labels
- `milestone` (optional): Milestone title
- `scope` (optional): created_by_me, assigned_to_me, or all
- `assignee_id` (optional): Filter by assignee user ID
- `author_id` (optional): Filter by author user ID
- `search` (optional): Search title/description
- `created_after`, `created_before` (optional): ISO 8601 date filters
- `updated_after`, `updated_before` (optional): ISO 8601 date filters
- `order_by` (optional): created_at, updated_at, priority, due_date
- `sort` (optional): asc or desc
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `issues`: Array of issues
- `result`: Success status

---

#### `get_issue`
Get details of a specific issue including labels, assignees, and milestone.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `issue_iid` (required): Internal issue ID (shown in URL as #123)

**Outputs:**
- `issue`: Issue details including title, description, state, labels, assignees
- `result`: Success status

---

### Merge Requests (4 actions)

#### `list_merge_requests`
List merge requests for a project or globally with filtering options.

**Inputs:**
- `project_id` (optional): ID or path
- `state` (optional): opened, closed, merged, or all
- `labels`, `milestone`, `scope`, `author_id`, `assignee_id`, `reviewer_id` (optional)
- `source_branch`, `target_branch` (optional): Filter by branch
- `search` (optional): Search title/description
- `created_after`, `created_before` (optional): ISO 8601 date filters
- `updated_after`, `updated_before` (optional): ISO 8601 date filters
- `order_by`, `sort`, `per_page`, `page` (optional)

**Outputs:**
- `merge_requests`: Array of merge requests
- `result`: Success status

---

#### `get_merge_request`
Get details of a specific merge request including changes and approvals.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `merge_request_iid` (required): Internal MR ID (shown in URL as !123)
- `include_diverged_commits_count` (optional): Include count of commits behind target
- `include_rebase_in_progress` (optional): Include rebase status

**Outputs:**
- `merge_request`: MR details including source/target branches, state, approvals
- `result`: Success status

---

#### `get_merge_request_changes`
Get the changes (diff) of a merge request.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `merge_request_iid` (required): Internal MR ID

**Outputs:**
- `changes`: List of file changes with diffs
- `result`: Success status

---

#### `list_merge_request_commits`
Get commits associated with a merge request.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `merge_request_iid` (required): Internal MR ID
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `commits`: List of commits in the merge request
- `result`: Success status

---

### Branches (2 actions)

#### `list_branches`
List repository branches sorted alphabetically by name.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `search` (optional): Search by name
- `regex` (optional): Filter by regex
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `branches`: Array of branches with name, commit info, and protection status
- `result`: Success status

---

#### `get_branch`
Get details of a specific branch including latest commit and protection status.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `branch` (required): Branch name

**Outputs:**
- `branch`: Branch details including commit, protected status, and merge status
- `result`: Success status

---

### Commits (3 actions)

#### `list_commits`
List repository commits with optional filtering by branch, date, and path.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `ref_name` (optional): Branch, tag, or SHA
- `since`, `until` (optional): ISO 8601 date filters
- `path` (optional): Filter by file path
- `author` (optional): Filter by author
- `all` (optional): Retrieve every commit
- `with_stats` (optional): Include commit stats
- `first_parent` (optional): Follow only first parent on merge commits
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `commits`: Array of commits with id, message, author, date
- `result`: Success status

---

#### `get_commit`
Get details of a specific commit including stats and parent commits.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `sha` (required): Commit SHA (full or short)
- `stats` (optional): Include commit stats (additions, deletions, total)

**Outputs:**
- `commit`: Commit details including message, author, stats, parent_ids
- `result`: Success status

---

#### `get_commit_diff`
Get the diff of a commit showing all file changes.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `sha` (required): Commit SHA
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `diffs`: List of file diffs with old_path, new_path, diff content
- `result`: Success status

---

### Pipelines (3 actions)

#### `list_pipelines`
List CI/CD pipelines for a project with filtering options.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `status` (optional): created, pending, running, success, failed, canceled, skipped, manual, scheduled
- `ref` (optional): Branch or tag
- `sha` (optional): Commit SHA
- `source` (optional): push, web, trigger, schedule, api, external, etc.
- `username` (optional): Filter by username who triggered the pipeline
- `updated_after`, `updated_before` (optional): ISO 8601 date filters
- `order_by` (optional): id, status, ref, updated_at, user_id
- `sort`, `per_page`, `page` (optional)

**Outputs:**
- `pipelines`: Array of pipelines with id, status, ref, sha, created_at
- `result`: Success status

---

#### `get_pipeline`
Get details of a specific pipeline including duration and coverage.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `pipeline_id` (required): Pipeline ID

**Outputs:**
- `pipeline`: Pipeline details including status, duration, coverage, user
- `result`: Success status

---

#### `list_pipeline_jobs`
List jobs for a specific pipeline.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `pipeline_id` (required): Pipeline ID
- `scope` (optional): created, pending, running, failed, success, canceled, skipped, manual
- `include_retried` (optional): Include retried jobs
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `jobs`: List of jobs with name, stage, status, duration
- `result`: Success status

---

### Repository (4 actions)

#### `list_repository_tree`
List files and directories in a repository at a specific path and ref.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `path` (optional): Path inside repository (root if not specified)
- `ref` (optional): Branch, tag, or SHA (default branch if not specified)
- `recursive` (optional): List recursively
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `tree`: Array of files/directories with id, name, type, path, mode
- `result`: Success status

---

#### `get_file`
Get a file's metadata and content (base64 encoded) from the repository.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `file_path` (required): Path to file (e.g., 'src/main.py')
- `ref` (required): Branch, tag, or SHA

**Outputs:**
- `file`: File metadata (file_name, file_path, size, encoding) and base64-encoded content
- `result`: Success status

---

#### `get_file_raw`
Get a file's raw content as plain text from the repository.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `file_path` (required): Path to file
- `ref` (required): Branch, tag, or SHA

**Outputs:**
- `content`: Raw file content as text
- `result`: Success status

---

#### `compare_branches`
Compare two branches, tags, or commits showing commits and diffs between them.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `from` (required): Source branch name, tag, or commit SHA
- `to` (required): Target branch name, tag, or commit SHA
- `straight` (optional): Compare directly (true) or via merge-base (false, default)

**Outputs:**
- `comparison`: Comparison result with commits array and diffs array
- `result`: Success status

---

### Container Registry (4 actions)

#### `list_container_registry_repositories`
List container registry repositories for a project.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `tags` (optional): Include tags in response
- `tags_count` (optional): Include tags count
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `repositories`: List of container registry repositories
- `result`: Success status

---

#### `get_container_registry_repository`
Get details of a specific container registry repository.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `repository_id` (required): Registry repository ID
- `tags` (optional): Include tags in response
- `tags_count` (optional): Include tags count

**Outputs:**
- `repository`: Container registry repository details
- `result`: Success status

---

#### `list_container_registry_tags`
List tags for a container registry repository.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `repository_id` (required): Registry repository ID
- `per_page`, `page` (optional): Pagination

**Outputs:**
- `tags`: List of container image tags
- `result`: Success status

---

#### `get_container_registry_tag`
Get details of a specific container registry tag including manifest digest.

**Inputs:**
- `project_id` (required): ID or URL-encoded path
- `repository_id` (required): Registry repository ID
- `tag_name` (required): Name of the tag (e.g., 'latest', 'v1.0.0')

**Outputs:**
- `tag`: Tag details including name, path, location, digest, created_at
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v4
- **Base URL**: `https://gitlab.com/api/v4`
- **Authentication**: OAuth 2.0
- **Documentation**: https://docs.gitlab.com/api/
- **Rate Limits**: Varies by GitLab tier

## Project ID Formats

GitLab accepts project identifiers in two formats:
- **Numeric ID**: `12345`
- **URL-encoded path**: `namespace%2Fproject-name` (the integration handles encoding automatically)

## Important Notes

- OAuth tokens expire after 2 hours and are automatically refreshed
- This integration provides **read-only** access - no create, update, or delete operations
- GitLab uses `iid` (internal ID) for issues and merge requests within projects
- Pagination defaults to 20 results per page, max 100
- This integration only supports gitlab.com - self-hosted GitLab instances are not supported

## Common Use Cases

**Project Monitoring:**
- List and search projects
- View project details and statistics
- Monitor project activity

**Issue Tracking:**
- List and filter issues by state, labels, milestone
- View issue details and discussions
- Track issue status across projects

**Code Review:**
- List and review merge requests
- View merge request changes and diffs
- Check commit history in merge requests

**CI/CD Monitoring:**
- List and monitor pipeline status
- View pipeline details and duration
- Check individual job status in pipelines

**Repository Access:**
- Browse repository file tree
- Read file contents (base64 or raw)
- Compare branches and commits

**Container Registry:**
- List container registry repositories
- View available image tags
- Check tag details and manifests

## Version History

- **1.0.0** - Initial release with 25 read-only actions
  - User: get_current_user (1 action)
  - Projects: list_projects, get_project (2 actions)
  - Issues: list_issues, get_issue (2 actions)
  - Merge Requests: list, get, get_changes, list_commits (4 actions)
  - Branches: list_branches, get_branch (2 actions)
  - Commits: list_commits, get_commit, get_commit_diff (3 actions)
  - Pipelines: list, get, list_jobs (3 actions)
  - Repository: list_tree, get_file, get_file_raw, compare_branches (4 actions)
  - Container Registry: list_repositories, get_repository, list_tags, get_tag (4 actions)

## Sources

- [GitLab REST API Documentation](https://docs.gitlab.com/api/rest/)
- [GitLab OAuth Provider](https://docs.gitlab.com/ee/integration/oauth_provider.html)
- [GitLab API Resources](https://docs.gitlab.com/api/api_resources/)
- [Projects API](https://docs.gitlab.com/api/projects/)
- [Issues API](https://docs.gitlab.com/api/issues/)
- [Merge Requests API](https://docs.gitlab.com/api/merge_requests/)
- [Branches API](https://docs.gitlab.com/api/branches/)
- [Commits API](https://docs.gitlab.com/api/commits/)
- [Pipelines API](https://docs.gitlab.com/api/pipelines/)
- [Container Registry API](https://docs.gitlab.com/api/container_registry/)

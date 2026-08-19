# GitHub Integration for Autohive

A comprehensive GitHub integration for the Autohive platform covering repositories, files, branches, commits, issues, pull requests, search, GitHub Actions, security alerts, releases, organizations, gists, and webhooks.

## Description

This integration wraps the GitHub REST API (version `2022-11-28`), exposing **111 actions** for automating GitHub workflows from Autohive.

### Key Features

- **Repositories** — create, read, update, delete, list, and fork; browse the git tree; list collaborators
- **Files** — read, create, update, and delete single files, browse directory listings, and commit many files atomically with `push_files`
- **Branches** — list, get, create, delete, read protection rules, and compare branches
- **Commits** — commit history and individual commit details
- **Issues** — full CRUD plus comments, labels, sub-issue hierarchies, and organization issue types/fields
- **Pull requests** — create, read, update, merge, list files/commits/statuses, manage reviewers, and drive the full review lifecycle including pending reviews
- **Search** — seven search actions covering code, commits, issues, pull requests, repositories, users, and organizations
- **GitHub Actions** — list workflows and runs, dispatch workflows, re-run, cancel, inspect jobs, read job logs, and list artifacts
- **Security** — code scanning, Dependabot, secret scanning, code quality findings, and security advisories
- **Releases & tags** — list and retrieve releases by ID, tag, or latest
- **Users, organizations & teams** — authenticated user, org members and repositories, teams and team members
- **Gists** — create, read, list, and update
- **Webhooks** — create, list, and delete repository webhooks

## Setup & Authentication

This integration uses GitHub's OAuth2 platform authentication.

### Authentication Type

**OAuth2 Platform Authentication** via GitHub. The Autohive platform injects the bearer token into every request — the integration never reads or stores credentials itself.

### Required Scopes

The integration requests exactly these six scopes, and every one is needed by actions that ship today:

| Scope | Why it is needed |
|---|---|
| `repo` | Repository, file, branch, commit, issue, pull request, label, release and tag actions, and private-repository visibility for search |
| `read:org` | `list_organization_members`, `list_organization_repositories`, `get_teams`, `get_team_members`, `list_issue_types`, `list_issue_fields` |
| `gist` | `create_gist`, `get_gist`, `list_gists`, `update_gist` |
| `admin:repo_hook` | `create_webhook`, `list_webhooks`, `delete_webhook` |
| `workflow` | `run_workflow`, `rerun_workflow_run`, `rerun_failed_jobs`, `cancel_workflow_run`, `delete_workflow_run_logs` |
| `security_events` | The Dependabot, code scanning, and secret scanning alert actions |

> **Note for maintainers:** `security_events` was added in `3.0.0`. Because `auth.type` is `platform`, this scope is requested against Autohive's shared GitHub OAuth application. Confirm that application is configured to grant `security_events` before release — if it is not, the eleven actions under [Security](#security) will return `403`, and the scope should be removed from `config.json`. No other action is affected.

### Setup Steps

1. In Autohive, navigate to Integrations
2. Select the "GitHub" integration
3. Click "Connect"
4. Authorize the requested permissions on GitHub's OAuth page
5. You are redirected back to Autohive with the integration connected

## Actions

All 111 actions are listed below, grouped by domain. Inputs marked `required` must be supplied; everything else is optional.

### Repositories

#### `create_repository`

Create a new repository

**Inputs:**

- `name` (string, required): Repository name
- `description` (string, optional): Repository description
- `private` (boolean, optional): Whether the repository is private Default: `False`.
- `auto_init` (boolean, optional): Initialize with README Default: `False`.
- `gitignore_template` (string, optional): Gitignore template name
- `license_template` (string, optional): License template name
- `org` (string, optional): Organization name (if creating in an org)
- `homepage` (string, optional): Home page URL
- `has_issues` (boolean, optional): Enable issues Default: `True`.
- `has_projects` (boolean, optional): Enable projects Default: `True`.
- `has_wiki` (boolean, optional): Enable wiki Default: `True`.

**Outputs:**

- `id` (integer)
- `name` (string)
- `full_name` (string)
- `description` (string, nullable)
- `private` (boolean)
- `default_branch` (string)
- `created_at` (string)
- `updated_at` (string)
- `pushed_at` (string, nullable)
- `clone_url` (string)
- `ssh_url` (string)
- `html_url` (string)

#### `delete_repository`

Delete a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**

- `deleted` (boolean)
- `repository` (string)

#### `fork_repository`

Create your own copy of someone else's repository, so you can push changes and open a pull request back to it. Forking runs in the background at GitHub: the fork is returned immediately but its files and branches may take a few seconds to become readable, so check the repository exists before pushing to it.

**Inputs:**

- `owner` (string, required): Owner of the repository being forked
- `repo` (string, required): Name of the repository being forked
- `organization` (string, optional): Organization to create the fork in. Defaults to the authenticated user's account.
- `name` (string, optional): New name for the fork. Defaults to the source repository's name.
- `default_branch_only` (boolean, optional): Fork only the default branch instead of every branch

**Outputs:**

- `id` (integer)
- `name` (string)
- `full_name` (string)
- `owner` (object)
- `private` (boolean)
- `fork` (boolean)
- `default_branch` (string, nullable)
- `created_at` (string, nullable)
- `clone_url` (string, nullable)
- `ssh_url` (string, nullable)
- `url` (string, nullable): Web URL of the new fork
- `source` (string): The repository that was forked, as owner/name
- `pending` (boolean): Always true — GitHub accepted the fork request and is still creating it in the background

#### `get_repository`

Get detailed information about a repository

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name

**Outputs:**

- `name` (string)
- `full_name` (string)
- `description` (string, nullable)
- `default_branch` (string)
- `created_at` (string)
- `updated_at` (string)
- `pushed_at` (string, nullable)
- `language` (string, nullable)
- `visibility` (string)
- `private` (boolean)
- `fork` (boolean)
- `forks_count` (integer)
- `stargazers_count` (integer)
- `watchers_count` (integer)
- `open_issues_count` (integer)
- `url` (string)

#### `get_repository_tree`

List the files and folders stored in a repository at a given branch, tag, or commit. Use recursive to walk the whole repository in one call. GitHub caps a tree at 100,000 entries / 7 MB, so always check 'truncated' — when it is true the listing is incomplete and you should read one folder at a time instead.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `tree_sha` (string, required): Branch name, tag, commit SHA, or tree SHA to read
- `recursive` (boolean, optional): Include the contents of every subfolder instead of just the top level

**Outputs:**

- `sha` (string)
- `url` (string, nullable)
- `truncated` (boolean): True when GitHub cut the listing short — the entries below are only part of the tree
- `entry_count` (integer): Number of entries returned
- `tree` (array)

#### `list_organization_repositories`

List repositories for a specific organization

**Inputs:**

- `org` (string, required): Organization name
- `type` (string, optional) One of: `all`, `public`, `private`, `forks`, `sources`, `member`. Default: `all`.
- `sort` (string, optional) One of: `created`, `updated`, `pushed`, `full_name`. Default: `updated`.
- `direction` (string, optional) One of: `asc`, `desc`. Default: `desc`.

**Outputs:**

Array of objects, each with: `id`, `name`, `full_name`, `description`, `private`, `fork`, `html_url`, `created_at`, `updated_at`, `language`, `stargazers_count`, `forks_count`, `open_issues_count`, `default_branch`

#### `list_repositories`

List repositories for a user or organization

**Inputs:**

- `username` (string, optional): Username to list repos for
- `org` (string, optional): Organization to list repos for
- `type` (string, optional) One of: `all`, `owner`, `public`, `private`, `member`. Default: `all`.
- `sort` (string, optional) One of: `created`, `updated`, `pushed`, `full_name`. Default: `updated`.
- `direction` (string, optional) One of: `asc`, `desc`. Default: `desc`.

**Outputs:**

Array of objects, each with: `id`, `name`, `full_name`, `description`, `private`, `fork`, `created_at`, `updated_at`, `pushed_at`, `language`, `default_branch`, `visibility`, `url`

#### `list_repository_collaborators`

See who has access to a repository and what each person is allowed to do, so you can audit permissions or find the right reviewer.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `affiliation` (string, optional): Which collaborators to include: 'direct' for people added to the repository, 'outside' for people outside the organization, 'all' for everyone visible (default) One of: `outside`, `direct`, `all`.
- `permission` (string, optional): Only return collaborators with this permission level One of: `pull`, `triage`, `push`, `maintain`, `admin`.
- `limit` (integer, optional): Maximum number of collaborators to return

**Outputs:**

Array of objects, each with: `login`, `id`, `avatar_url`, `url`, `role_name`, `permissions`

#### `list_user_repositories`

List repositories for a specific user or authenticated user

**Inputs:**

- `username` (string, optional): Username (omit for authenticated user)
- `type` (string, optional) One of: `all`, `owner`, `member`. Default: `all`.
- `sort` (string, optional) One of: `created`, `updated`, `pushed`, `full_name`. Default: `updated`.
- `direction` (string, optional) One of: `asc`, `desc`. Default: `desc`.

**Outputs:**

Array of objects, each with: `id`, `name`, `full_name`, `description`, `private`, `fork`, `html_url`, `created_at`, `updated_at`, `language`, `stargazers_count`, `forks_count`, `open_issues_count`, `default_branch`

#### `update_repository`

Update repository settings

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, optional): New repository name
- `description` (string, optional): New description
- `private` (boolean, optional): Make private/public
- `has_issues` (boolean, optional): Enable issues
- `has_wiki` (boolean, optional): Enable wiki

**Outputs:**

- `name` (string)
- `full_name` (string)
- `description` (string, nullable)
- `private` (boolean)
- `has_issues` (boolean)
- `has_wiki` (boolean)
- `updated_at` (string)
- `url` (string)

### Files & Contents

#### `create_file`

Create a new file in repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path
- `message` (string, required): Commit message
- `content` (string, required): File content
- `branch` (string, optional): Branch name

**Outputs:**

- `content` (object)
- `commit` (object)

#### `delete_file`

Delete a file from repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path
- `message` (string, required): Commit message
- `sha` (string, required): Current file SHA
- `branch` (string, optional): Branch name

**Outputs:**

- `deleted` (boolean)
- `path` (string)
- `commit` (object)

#### `get_file_content`

Get the content of a file in a repository, or list the entries of a directory when path points to a folder. When path is a directory, 'type' is 'dir', 'content' is empty, and 'entries' holds the files and subfolders.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path, or directory path to list its entries
- `ref` (string, optional): Branch/commit/tag reference

**Outputs:**

- `type` (string): 'file' for a single file, 'dir' for a directory listing
- `content` (string): Decoded file content. Empty when path is a directory.
- `sha` (string)
- `size` (integer)
- `name` (string)
- `path` (string)
- `entries` (array): Directory entries when path is a directory. Empty for a single file.

#### `push_files`

Commit several files to a branch in one single commit, instead of one commit per file. Creates or overwrites each file given, and can delete files in the same commit. File content is plain text by default; set a file's encoding to base64 to push an image or other binary. If a step fails, the error says which step and whether anything was committed.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Existing branch to commit to. The branch must already exist.
- `message` (string, required): Commit message
- `files` (array, required): Files to create or overwrite. Each path may appear only once across files and delete_paths.
- `delete_paths` (array, optional): Files to delete in the same commit. Each path must already exist on the branch.
- `force` (boolean, optional): Move the branch even if the commit is not a fast-forward. Off by default; leaving it off protects work pushed by someone else while this commit was being built.

**Outputs:**

- `commit` (object)
- `branch` (string)
- `tree_sha` (string, nullable): SHA of the tree the new commit points at
- `parent_sha` (string, nullable): The commit the branch pointed at before this push
- `written_paths` (array): Paths created or overwritten
- `deleted_paths` (array): Paths deleted
- `files_changed` (integer)

#### `update_file`

Update an existing file in repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path
- `message` (string, required): Commit message
- `content` (string, required): New file content
- `sha` (string, required): Current file SHA
- `branch` (string, optional): Branch name

**Outputs:**

- `content` (object)
- `commit` (object)

### Branches

#### `create_branch`

Create a new branch

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch_name` (string, required): New branch name
- `sha` (string, required): SHA to create branch from

**Outputs:**

- `ref` (string)
- `url` (string)
- `object` (object)

#### `delete_branch`

Delete a branch

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Branch name to delete

**Outputs:**

- `deleted` (boolean)
- `branch` (string)

#### `diff_branch_to_branch`

Compare two branches

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `base_branch` (string, required): Base branch
- `head_branch` (string, required): Head branch

**Outputs:**

- `status` (string, nullable)
- `ahead_by` (integer, nullable)
- `behind_by` (integer, nullable)
- `total_commits` (integer, nullable)
- `commits` (array)
- `files` (array)

#### `get_branch`

Get branch details

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Branch name

**Outputs:**

- `name` (string)
- `protected` (boolean)
- `commit` (object)
- `protection` (object)

#### `get_branch_protection`

Get branch protection rules

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Branch name

**Outputs:**

- `enabled` (boolean)
- `required_status_checks` (array)
- `enforce_admins` (boolean)
- `required_pull_request_reviews` (object)
- `restrictions` (object)

#### `list_branches`

List branches for a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**

Array of objects, each with: `name`, `protected`, `commit`

### Commits

#### `get_commit`

Get a specific commit

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `sha` (string, required): Commit SHA

**Outputs:**

- `sha` (string)
- `author` (object)
- `committer` (object)
- `message` (string)
- `stats` (object)
- `files` (array)
- `url` (string)

#### `list_commits`

List commits for a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `sha` (string, optional): SHA or branch to start listing commits from
- `path` (string, optional): Only commits containing this file path
- `since` (string, optional): ISO 8601 timestamp to filter commits after
- `until` (string, optional): ISO 8601 timestamp to filter commits before
- `max_pages` (integer, optional): Maximum number of pages (100 commits per page) to fetch before stopping. Prevents Lambda timeouts on large repos. Narrow with sha/path/since/until for full coverage. Default: `10`.

**Outputs:**

Array of objects, each with: `sha`, `author`, `committer`, `message`, `url`

### Issues

#### `create_issue`

Create a new issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `title` (string, required): Issue title
- `body` (string, optional): Issue body
- `assignees` (array, optional): Usernames to assign
- `labels` (array, optional): Labels to add
- `milestone` (integer, optional): Milestone number

**Outputs:**

- `number` (integer)
- `title` (string)
- `description` (string, nullable)
- `state` (string)
- `created_at` (string)
- `updated_at` (string)
- `author` (object)
- `assignees` (array)
- `labels` (array)
- `url` (string)

#### `create_issue_comment`

Create a comment on an issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number
- `body` (string, required): Comment body

**Outputs:**

- `id` (integer)
- `body` (string, nullable)
- `created_at` (string)
- `updated_at` (string)
- `author` (object)
- `url` (string)

#### `get_issue`

Get a specific issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number

**Outputs:**

- `number` (integer)
- `title` (string)
- `description` (string, nullable)
- `state` (string)
- `created_at` (string)
- `updated_at` (string)
- `closed_at` (string, nullable)
- `author` (object)
- `assignees` (array)
- `labels` (array)
- `comments` (integer)
- `url` (string)

#### `get_issue_comments`

Get comments for an issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number

**Outputs:**

Array of objects, each with: `id`, `body`, `created_at`, `updated_at`, `author`, `url`

#### `list_issue_fields`

List the custom issue fields an organization has defined, including the choices available on select fields

**Inputs:**

- `org` (string, required): Organization login (for example 'autohive-ai')

**Outputs:**

Array of objects, each with: `id`, `node_id`, `name`, `description`, `data_type`, `visibility`, `options`, `created_at`, `updated_at`

#### `list_issue_types`

List the issue types an organization has defined, so issues can be classified as Bug, Feature, Task and so on

**Inputs:**

- `org` (string, required): Organization login (for example 'autohive-ai')

**Outputs:**

Array of objects, each with: `id`, `node_id`, `name`, `description`, `color`, `is_enabled`, `created_at`, `updated_at`

#### `list_issues`

List issues for a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `state` (string, optional) One of: `open`, `closed`, `all`. Default: `all`.
- `sort` (string, optional) One of: `created`, `updated`, `comments`. Default: `created`.
- `direction` (string, optional) One of: `asc`, `desc`. Default: `desc`.
- `since` (string, optional): ISO 8601 timestamp
- `labels` (string, optional): Comma-separated list of label names

**Outputs:**

Array of objects, each with: `number`, `title`, `description`, `state`, `created_at`, `updated_at`, `closed_at`, `author`, `assignees`, `labels`, `url`

#### `update_issue`

Update an existing issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number
- `title` (string, optional): New title
- `body` (string, optional): New body
- `state` (string, optional) One of: `open`, `closed`.
- `assignees` (array, optional)
- `labels` (array, optional)
- `milestone` (integer, optional)

**Outputs:**

- `number` (integer)
- `title` (string)
- `description` (string, nullable)
- `state` (string)
- `created_at` (string)
- `updated_at` (string)
- `closed_at` (string, nullable)
- `author` (object)
- `assignees` (array)
- `labels` (array)
- `url` (string)

### Labels

#### `create_label`

Create a new label in a repository so it can be applied to issues and pull requests

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, required): Label name. Spaces and slashes are fine (for example 'good first issue').
- `color` (string, optional): Six-character hex colour code without the leading '#' (for example 'd73a4a')
- `description` (string, optional): Short description of the label, up to 100 characters

**Outputs:**

- `id` (integer)
- `node_id` (string)
- `name` (string)
- `color` (string, nullable)
- `description` (string, nullable)
- `default` (boolean)
- `url` (string)

#### `delete_label`

Delete a label from a repository, removing it from every issue and pull request it was applied to

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, required): Label name to delete

**Outputs:**

- `deleted` (boolean)
- `name` (string)

#### `get_label`

Look up a single label by name to check its colour and description

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, required): Label name, exactly as it appears in GitHub. Spaces and slashes are fine (for example 'good first issue').

**Outputs:**

- `id` (integer)
- `node_id` (string)
- `name` (string)
- `color` (string, nullable)
- `description` (string, nullable)
- `default` (boolean)
- `url` (string)

#### `list_issue_labels`

List the labels currently applied to an issue or pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number as shown in the issue's URL (not the issue id)
- `limit` (integer, optional): Maximum number of labels to return. Leave empty to return all of them.

**Outputs:**

Array of objects, each with: `id`, `node_id`, `name`, `color`, `description`, `default`, `url`

#### `list_labels`

List every label available in a repository, to see which labels can be applied to issues and pull requests

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `limit` (integer, optional): Maximum number of labels to return. Leave empty to return all of them.

**Outputs:**

Array of objects, each with: `id`, `node_id`, `name`, `color`, `description`, `default`, `url`

#### `update_label`

Rename a label or change its colour or description across every issue it is applied to

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, required): Current label name
- `new_name` (string, optional): New name for the label. Leave empty to keep the current name.
- `color` (string, optional): Six-character hex colour code without the leading '#' (for example 'd73a4a')
- `description` (string, optional): Short description of the label, up to 100 characters

**Outputs:**

- `id` (integer)
- `node_id` (string)
- `name` (string)
- `color` (string, nullable)
- `description` (string, nullable)
- `default` (boolean)
- `url` (string)

### Sub-Issues

#### `add_sub_issue`

Nest an existing issue underneath a parent issue to build out an issue hierarchy

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Number of the parent issue as shown in its URL (not the issue id)
- `sub_issue_id` (integer, required): The 'id' of the issue to nest — GitHub's numeric issue id, NOT its issue number. Read it from the 'id' field of a Get Issue or List Issues result. The issue must belong to the same repository owner as the parent.
- `replace_parent` (boolean, optional): Set to true to move the issue when it already has a different parent. Leave off and the request fails if it is already nested elsewhere.

**Outputs:**

- `added` (boolean)
- `sub_issue_id` (integer)
- `parent` (object)

#### `list_sub_issues`

List the sub-issues nested under a parent issue, to see how a piece of work breaks down

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Number of the parent issue as shown in its URL (not the issue id)
- `limit` (integer, optional): Maximum number of sub-issues to return. Leave empty to return all of them.

**Outputs:**

Array of objects, each with: `id`, `number`, `title`, `description`, `state`, `created_at`, `updated_at`, `closed_at`, `author`, `assignees`, `labels`, `sub_issues_summary`, `url`

#### `remove_sub_issue`

Detach a sub-issue from its parent issue. The issue itself is not deleted, only the parent link.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Number of the parent issue as shown in its URL (not the issue id)
- `sub_issue_id` (integer, required): The 'id' of the sub-issue to detach — GitHub's numeric issue id, NOT its issue number. Read it from the 'id' field of a List Sub-Issues or Get Issue result.

**Outputs:**

- `removed` (boolean)
- `sub_issue_id` (integer)
- `parent` (object)

#### `reprioritize_sub_issue`

Reorder a sub-issue within its parent's list by placing it after or before another sub-issue

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Number of the parent issue as shown in its URL (not the issue id)
- `sub_issue_id` (integer, required): The 'id' of the sub-issue to move — GitHub's numeric issue id, NOT its issue number. Read it from the 'id' field of a List Sub-Issues result.
- `after_id` (integer, optional): The 'id' (not issue number) of the sub-issue to place this one after. Supply exactly one of after_id or before_id.
- `before_id` (integer, optional): The 'id' (not issue number) of the sub-issue to place this one before. Supply exactly one of after_id or before_id.

**Outputs:**

- `reprioritized` (boolean)
- `sub_issue_id` (integer)
- `parent` (object)

### Pull Requests

#### `add_pull_request_reviewers`

Add reviewers to a pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `reviewers` (array, optional): User logins to request
- `team_reviewers` (array, optional): Team slugs to request

**Outputs:**

- `requested_reviewers` (array)
- `requested_teams` (array)

#### `add_reply_to_pull_request_comment`

Reply to an existing inline review comment so the response threads underneath it rather than starting a new conversation on the diff.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `comment_id` (integer, required): ID of the review comment being replied to. Obtain it from get_pull_request_comments.
- `body` (string, required): Reply text, in Markdown

**Outputs:**

- `id` (integer)
- `body` (string, nullable)
- `path` (string, nullable)
- `line` (integer, nullable)
- `start_line` (integer, nullable)
- `side` (string, nullable)
- `start_side` (string, nullable)
- `diff_hunk` (string, nullable)
- `commit_id` (string, nullable)
- `in_reply_to_id` (integer, nullable)
- `pull_request_review_id` (integer, nullable)
- `author_association` (string, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `author` (object, nullable)
- `url` (string, nullable)

#### `create_pull_request`

Create a new pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `title` (string, required): PR title
- `head` (string, required): Branch with changes
- `base` (string, required): Branch to merge into
- `body` (string, optional): PR description
- `draft` (boolean, optional): Create as draft Default: `False`.
- `maintainer_can_modify` (boolean, optional): Allow maintainer edits Default: `True`.

**Outputs:**

- `id` (integer)
- `node_id` (string)
- `number` (integer)
- `title` (string)
- `body` (string, nullable)
- `state` (string)
- `html_url` (string)
- `url` (string)
- `diff_url` (string)
- `patch_url` (string)
- `created_at` (string)
- `updated_at` (string)
- `closed_at` (string, nullable)
- `merged_at` (string, nullable)
- `draft` (boolean)
- `merged` (boolean, nullable)
- `mergeable` (boolean, nullable)
- `mergeable_state` (string, nullable)
- `merge_commit_sha` (string, nullable)
- `user` (object)
- `author_association` (string)
- `assignee` (object, nullable)
- `assignees` (array)
- `requested_reviewers` (array)
- `requested_teams` (array)
- `labels` (array)
- `milestone` (object, nullable)
- `head` (object)
- `base` (object)
- `comments` (integer)
- `review_comments` (integer)
- `commits` (integer)
- `additions` (integer)
- `deletions` (integer)
- `changed_files` (integer)

#### `get_pull_request`

Get detailed information about a pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number

**Outputs:**

- `number` (integer)
- `title` (string)
- `description` (string, nullable)
- `state` (string)
- `created_at` (string)
- `updated_at` (string)
- `merged_at` (string, nullable)
- `closed_at` (string, nullable)
- `draft` (boolean)
- `mergeable` (boolean, nullable)
- `mergeable_state` (string, nullable)
- `merged` (boolean)
- `author` (object)
- `assignees` (array)
- `requested_reviewers` (array)
- `labels` (array)
- `head` (object): The head branch info. head.sha is the latest commit SHA — pass this as commit_id when calling create_pull_request_review.
- `base` (object)
- `url` (string)

#### `get_pull_request_comments`

List the inline review comments left on a pull request's diff, including which file and line each one is anchored to and what it replies to.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `sort` (string, optional): Field to sort the comments by One of: `created`, `updated`.
- `direction` (string, optional): Sort direction. Defaults to ascending when sorting by created. One of: `asc`, `desc`.
- `since` (string, optional): ISO 8601 timestamp; only return comments updated at or after this time.
- `limit` (integer, optional): Maximum number of comments to return
- `max_pages` (integer, optional): Maximum number of pages (100 comments per page) to fetch before stopping. Default: `10`.

**Outputs:**

Array of objects, each with: `id`, `body`, `path`, `line`, `start_line`, `side`, `start_side`, `diff_hunk`, `commit_id`, `in_reply_to_id`, `pull_request_review_id`, `author_association`, `created_at`, `updated_at`, `author`, `url`

#### `get_pull_request_diff`

Get the complete unified diff (or git patch) for a pull request as text, so it can be read or reviewed in full without fetching each file separately.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `format` (string, optional): 'diff' returns a unified diff of the whole pull request; 'patch' returns a git-format patch series with one commit message header per commit. One of: `diff`, `patch`. Default: `diff`.

**Outputs:**

- `pull_number` (integer)
- `format` (string)
- `content` (string): The raw diff or patch text
- `length` (integer): Character count of the returned text

#### `get_pull_request_files`

List every file a pull request touches, with its status, added/removed line counts, and per-file patch - the fastest way to see the shape of a change before reviewing it.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `include_patch` (boolean, optional): Include the per-file patch text. Set false to get just the file list and line counts on very large pull requests. Default: `True`.
- `limit` (integer, optional): Maximum number of files to return
- `max_pages` (integer, optional): Maximum number of pages (100 files per page) to fetch before stopping. GitHub itself returns at most 3000 files for a pull request. Default: `10`.

**Outputs:**

Array of objects, each with: `filename`, `previous_filename`, `status`, `additions`, `deletions`, `changes`, `sha`, `patch`, `url`, `raw_url`

#### `get_pull_request_status`

Check whether a pull request's CI is passing by rolling up every commit status reported against its head commit into a single state.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number

**Outputs:**

- `pull_number` (integer)
- `sha` (string): The head commit the statuses belong to
- `state` (string, nullable): Combined state: success, pending or failure
- `total_count` (integer)
- `statuses` (array)
- `url` (string, nullable)

#### `list_pull_request_commits`

List the commits a pull request contributes, with author, committer and message - useful for writing release notes or checking commit hygiene before merging.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `limit` (integer, optional): Maximum number of commits to return
- `max_pages` (integer, optional): Maximum number of pages (100 commits per page) to fetch before stopping. GitHub itself returns at most 250 commits for a pull request. Default: `10`.

**Outputs:**

Array of objects, each with: `sha`, `author`, `committer`, `message`, `url`

#### `list_pull_request_reviewers`

List reviewers for a pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number

**Outputs:**

- `users` (array)
- `teams` (array)

#### `list_pull_requests`

List pull requests for a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `state` (string, optional) One of: `open`, `closed`, `all`. Default: `all`.
- `sort` (string, optional) One of: `created`, `updated`, `popularity`, `long-running`. Default: `updated`.
- `direction` (string, optional) One of: `asc`, `desc`. Default: `desc`.
- `after` (string, optional): ISO 8601 date or timestamp; keep PRs created at or after this point. A bare date (YYYY-MM-DD) is inclusive from the start of that day.
- `before` (string, optional): ISO 8601 date or timestamp; keep PRs created at or before this point. A bare date (YYYY-MM-DD) is inclusive through the end of that day.
- `author` (string, optional): Filter by PR author username
- `limit` (integer, optional): Maximum number of PRs to return
- `max_pages` (integer, optional): Maximum number of pages (100 PRs per page) to fetch before stopping. Prevents Lambda timeouts on large repos. Narrow with state/author/after/before for full coverage. Default: `10`.

**Outputs:**

Array of objects, each with: `number`, `title`, `description`, `state`, `created_at`, `updated_at`, `closed_at`, `merged_at`, `draft`, `merged`, `author`, `url`

#### `merge_pull_request`

Merge a pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `commit_title` (string, optional): Custom merge commit title
- `commit_message` (string, optional): Custom merge commit message
- `merge_method` (string, optional) One of: `merge`, `squash`, `rebase`. Default: `merge`.

**Outputs:**

- `merged` (boolean)
- `message` (string, nullable)
- `sha` (string, nullable)
- `commit_title` (string, nullable)
- `commit_message` (string, nullable)

#### `remove_pull_request_reviewers`

Remove reviewers from a pull request

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `reviewers` (array, optional): User logins to remove
- `team_reviewers` (array, optional): Team slugs to remove

**Outputs:**

- `requested_reviewers` (array)
- `requested_teams` (array)

#### `update_pull_request`

Edit an open pull request - retitle it, rewrite its description, retarget it at a different base branch, or close/reopen it without merging.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `title` (string, optional): New pull request title. Leave unset to keep the current title.
- `body` (string, optional): New pull request description in Markdown. Replaces the existing body entirely.
- `state` (string, optional): Set to 'closed' to close the pull request without merging, or 'open' to reopen it. One of: `open`, `closed`.
- `base` (string, optional): Name of an existing branch to retarget the pull request at (e.g. 'main'). Cannot be the same as the head branch.
- `maintainer_can_modify` (boolean, optional): Whether maintainers of the base repository may push to the head branch. Only settable on pull requests from a fork.

**Outputs:**

- `number` (integer)
- `title` (string)
- `description` (string, nullable)
- `state` (string)
- `draft` (boolean)
- `merged` (boolean)
- `mergeable` (boolean, nullable)
- `mergeable_state` (string, nullable)
- `maintainer_can_modify` (boolean, nullable)
- `created_at` (string)
- `updated_at` (string)
- `closed_at` (string, nullable)
- `merged_at` (string, nullable)
- `author` (object, nullable)
- `head` (object)
- `base` (object)
- `url` (string)

#### `update_pull_request_branch`

Bring a pull request's branch up to date with its base branch by merging the base into it - the equivalent of clicking 'Update branch' on GitHub. Useful when a branch protection rule requires branches to be current before merging.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `expected_head_sha` (string, optional): The SHA the head branch is expected to be at. If the branch has moved on since, GitHub rejects the update instead of merging over someone else's push. Obtain it from get_pull_request as head.sha.

**Outputs:**

- `pull_number` (integer)
- `queued` (boolean): GitHub accepted the request and runs the merge as a background job; the branch may take a moment to reflect it.
- `message` (string, nullable)
- `url` (string, nullable)

### Pull Request Reviews

#### `add_comment_to_pending_review`

Attach another inline comment to a draft review that already exists, so a review can be built up one file at a time before being submitted. Uses GitHub's GraphQL API because the REST API only accepts inline comments when the review is first created.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `path` (string, required): File path relative to the repository root (e.g. 'src/main.py')
- `body` (string, required): Comment text, in Markdown
- `review_id` (integer, optional): ID of the pending review to add the comment to, as returned by create_pending_pull_request_review. Omit to use the single pending review you already have open on this pull request.
- `line` (integer, optional): Line number in the file to comment on. Must be a line that appears in the pull request diff. Omit together with subject_type FILE to comment on the file as a whole.
- `side` (string, optional): RIGHT for the new version (added or unchanged lines), LEFT for the old version (removed lines). Use RIGHT in almost all cases. One of: `LEFT`, `RIGHT`.
- `start_line` (integer, optional): First line of a multi-line comment. Set together with line, which then acts as the last line.
- `start_side` (string, optional): Diff side of start_line for a multi-line comment One of: `LEFT`, `RIGHT`.
- `subject_type` (string, optional): What the comment is anchored to. Defaults to LINE; use FILE to comment on the whole file rather than a specific line. One of: `LINE`, `FILE`.

**Outputs:**

- `thread_id` (string, nullable): GraphQL node ID of the new review thread
- `review_node_id` (string): GraphQL node ID of the pending review the comment was added to
- `path` (string, nullable)
- `line` (integer, nullable)
- `start_line` (integer, nullable)
- `side` (string, nullable)
- `is_resolved` (boolean, nullable)
- `is_outdated` (boolean, nullable)
- `comment` (object, nullable)

#### `create_pending_pull_request_review`

Start a draft review on a pull request without publishing it, so comments can be gathered over several steps and submitted together as one review. Nothing is visible to the author until the review is submitted.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `commit_id` (string, optional): SHA of the commit the review applies to. Defaults to the most recent commit; required when posting inline comments. Obtain it from get_pull_request as head.sha.
- `body` (string, optional): Overall review body text, in Markdown
- `comments` (array, optional): Inline comments to seed the draft review with. Each must target a line that appears in the pull request diff - use get_pull_request_files or get_pull_request_diff to find valid lines. Further comments can be added later with add_comment_to_pending_review.

**Outputs:**

- `id` (integer): Review ID to pass to add_comment_to_pending_review, submit_pending_pull_request_review or delete_pending_pull_request_review
- `node_id` (string, nullable)
- `body` (string, nullable)
- `state` (string, nullable): PENDING for a newly created draft
- `commit_id` (string, nullable)
- `submitted_at` (string, nullable)
- `author_association` (string, nullable)
- `author` (object, nullable)
- `url` (string, nullable)

#### `create_pull_request_review`

Create a review for a pull request, optionally with inline comments on specific lines of changed files. Use get_pull_request first to obtain the head commit SHA (head.sha) required for commit_id.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `commit_id` (string, optional): The SHA of the latest commit on the PR head branch. Required when posting inline comments. Obtain this from get_pull_request → head.sha.
- `body` (string, optional): Overall review body text. Required when event is REQUEST_CHANGES or COMMENT.
- `event` (string, optional): Review action: APPROVE, REQUEST_CHANGES, or COMMENT. One of: `APPROVE`, `REQUEST_CHANGES`, `COMMENT`.
- `comments` (array, optional): Inline comments to post on specific lines of the diff. Each comment must target a line that actually appears in the PR diff — use diff_branch_to_branch or the patch field from get_pull_request to find valid line numbers.

**Outputs:**

- `id` (integer)
- `body` (string, nullable)
- `state` (string, nullable)
- `submitted_at` (string, nullable)
- `author` (object)
- `url` (string, nullable)

#### `delete_pending_pull_request_review`

Discard a draft review and all of its unpublished comments. Only works while the review is still pending - a submitted review cannot be deleted.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `review_id` (integer, required): ID of the pending review to discard, as returned by create_pending_pull_request_review

**Outputs:**

- `deleted` (boolean)
- `review_id` (integer)
- `pull_number` (integer)
- `state` (string, nullable): State of the review as it was deleted

#### `get_pull_request_reviews`

List the reviews submitted on a pull request in chronological order, showing who approved, who requested changes, and what they said.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `limit` (integer, optional): Maximum number of reviews to return
- `max_pages` (integer, optional): Maximum number of pages (100 reviews per page) to fetch before stopping. Default: `10`.

**Outputs:**

Array of objects, each with: `id`, `node_id`, `body`, `state`, `commit_id`, `submitted_at`, `author_association`, `author`, `url`

#### `submit_pending_pull_request_review`

Publish a draft review, delivering all of its inline comments at once as an approval, a change request, or a plain comment.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `review_id` (integer, required): ID of the pending review to submit, as returned by create_pending_pull_request_review
- `event` (string, required): How to submit the review. APPROVE and REQUEST_CHANGES cannot be used on your own pull request. One of: `APPROVE`, `REQUEST_CHANGES`, `COMMENT`.
- `body` (string, optional): Review summary text, in Markdown. Required by GitHub when event is REQUEST_CHANGES or COMMENT and the draft has no body yet.

**Outputs:**

- `id` (integer)
- `node_id` (string, nullable)
- `body` (string, nullable)
- `state` (string, nullable)
- `commit_id` (string, nullable)
- `submitted_at` (string, nullable)
- `author_association` (string, nullable)
- `author` (object, nullable)
- `url` (string, nullable)

### Search

#### `search_code`

Find source files anywhere on GitHub by their contents — locate every usage of a function, config key, or dependency across an organisation. The query must contain at least one search term (a bare 'language:go' is rejected); narrow it with qualifiers like 'repo:owner/name', 'org:acme', 'path:src/', 'language:python', 'filename:Dockerfile'. Only default branches are indexed, only files under 384 KB, and forks only when they out-star their parent. Code search is the most tightly rate limited GitHub endpoint: 10 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Code search query, e.g. 'addClass org:autohive-ai language:python'. Must include at least one search term alongside any qualifiers.
- `sort` (string, optional): Sort field. 'indexed' orders by when the file was last indexed and is being closed down by GitHub; omit for best match. One of: `indexed`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of files to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_commits`

Find commits across GitHub by message, author, or date — useful for tracing when a change landed or auditing what someone shipped. Narrow with qualifiers like 'repo:owner/name', 'org:acme', 'author:octocat', 'committer-date:>2024-01-01', 'merge:false'. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Commit search query, e.g. 'repo:octocat/Hello-World fix author:octocat'.
- `sort` (string, optional): Sort field for commit search. Only 'author-date' and 'committer-date' are valid here — any other value is rejected by GitHub. Omit for best match. One of: `author-date`, `committer-date`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of commits to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_issues`

Find issues across GitHub — triage everything labelled 'bug' in an org, or every issue assigned to someone across repositories. Pull requests are excluded automatically ('is:issue' is added unless the query already says which type it wants). Narrow with qualifiers like 'repo:owner/name', 'org:acme', 'author:octocat', 'assignee:octocat', 'label:bug', 'state:open', 'created:>2024-01-01'. Spaces between qualifiers combine with AND. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Issue search query, e.g. 'org:autohive-ai label:bug state:open'. 'is:issue' is appended automatically unless the query already sets the type.
- `sort` (string, optional): Sort field for issue search. Repository sort values such as 'stars' are rejected by GitHub here. Omit for best match. One of: `comments`, `reactions`, `reactions-+1`, `reactions--1`, `reactions-smile`, `reactions-thinking_face`, `reactions-heart`, `reactions-tada`, `interactions`, `created`, `updated`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of issues to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_orgs`

Find GitHub organizations by name, description, or location. GitHub has no dedicated organization search endpoint, so this runs the account search with 'type:org' added (unless the query already sets a type) — the same index Search Users reads, filtered to organizations. Narrow with qualifiers like 'in:login', 'in:name', 'location:london', 'repos:>50'. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Organization search query, e.g. 'autohive in:name'. 'type:org' is appended automatically unless the query already sets a type.
- `sort` (string, optional): Sort field for account search. Only 'followers', 'repositories' and 'joined' are valid here. Omit for best match. One of: `followers`, `repositories`, `joined`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of organizations to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_pull_requests`

Find pull requests across GitHub — review queues, everything a person opened this quarter, or every PR touching a repository. Uses the same index as issue search, with 'is:pr' added unless the query already says which type it wants. Narrow with qualifiers like 'repo:owner/name', 'org:acme', 'author:octocat', 'review-requested:octocat', 'state:open', 'draft:false', 'merged:>2024-01-01'. Spaces between qualifiers combine with AND. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Pull request search query, e.g. 'org:autohive-ai review-requested:octocat state:open'. 'is:pr' is appended automatically unless the query already sets the type.
- `sort` (string, optional): Sort field. Pull request search runs on the issues endpoint, so it accepts the issue sort values — not repository ones like 'stars'. Omit for best match. One of: `comments`, `reactions`, `reactions-+1`, `reactions--1`, `reactions-smile`, `reactions-thinking_face`, `reactions-heart`, `reactions-tada`, `interactions`, `created`, `updated`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of pull requests to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_repositories`

Find repositories across GitHub by name, description, topic, language, or popularity — discover what an organisation owns, or shortlist libraries by stars. Narrow with qualifiers like 'org:acme', 'user:octocat', 'language:python', 'topic:cli', 'stars:>100', 'pushed:>2024-01-01', 'archived:false'. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): Repository search query, e.g. 'org:autohive-ai language:python stars:>10'.
- `sort` (string, optional): Sort field for repository search. Only 'stars', 'forks', 'help-wanted-issues' and 'updated' are valid here — issue sort values such as 'comments' are rejected. Omit for best match. One of: `stars`, `forks`, `help-wanted-issues`, `updated`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of repositories to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

#### `search_users`

Find people on GitHub by username, name, email, location, or activity — for example every contributor in a city, or the account behind an email address. Organizations are filtered out ('type:user' is added unless the query already sets a type; use Search Organizations for those). Narrow with qualifiers like 'in:login', 'in:email', 'location:berlin', 'language:python', 'followers:>100', 'repos:>10'. Rate limited to 30 requests per minute, and no query returns more than 1000 results.

**Inputs:**

- `query` (string, required): User search query, e.g. 'octocat in:login location:london'. 'type:user' is appended automatically unless the query already sets a type.
- `sort` (string, optional): Sort field for account search. Only 'followers', 'repositories' and 'joined' are valid here. Omit for best match. One of: `followers`, `repositories`, `joined`.
- `order` (string, optional): Sort direction. Only meaningful alongside sort. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of accounts to return (GitHub caps any search at 1000).

**Outputs:**

- `total_count` (integer): Total matches GitHub found, which may exceed the 1000 results the API will return
- `incomplete_results` (boolean): True when GitHub timed out and returned only part of the matches
- `capped` (boolean): True when total_count exceeds the 1000-result ceiling, so items is a prefix of the matches
- `items` (array)

### Actions & Workflows

#### `cancel_workflow_run`

Cancel a queued or in-progress workflow run to stop it consuming runner minutes

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID

**Outputs:**

- `cancelled` (boolean)
- `run_id` (integer)
- `url` (string)
- `message` (string)

#### `delete_workflow_run_logs`

Permanently delete all log files for a workflow run, for example to purge logs that captured sensitive output

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID

**Outputs:**

- `deleted` (boolean)
- `run_id` (integer)

#### `download_workflow_run_artifact`

Resolve one artifact's download URL, size, digest and expiry. GitHub only serves artifacts as ZIP files, so this returns an authenticated download link rather than the file itself

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `artifact_id` (integer, required): The artifact's numeric ID, from List Workflow Run Artifacts

**Outputs:**

- `id` (integer)
- `name` (string)
- `size_in_bytes` (integer)
- `expired` (boolean)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `expires_at` (string, nullable)
- `digest` (string, nullable)
- `archive_download_url` (string)
- `url` (string)
- `workflow_run` (object, nullable)
- `archive_returned` (boolean)
- `note` (string)

#### `get_job_logs`

Read the log output of a single workflow job as text. Job logs can run to millions of lines, so only the last tail_lines lines are returned

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `job_id` (integer, required): The job's numeric ID, from List Workflow Jobs
- `tail_lines` (integer, optional): How many lines from the end of the log to return. Defaults to 500, capped at 10000

**Outputs:**

- `job_id` (integer)
- `tail_lines` (integer)
- `logs` (string)
- `total_lines` (integer)
- `returned_lines` (integer)
- `truncated` (boolean)

#### `get_workflow_run`

Get the full detail of one GitHub Actions run — status, conclusion, branch, commit and who triggered it

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID
- `exclude_pull_requests` (boolean, optional): Omit the pull requests attached to the run, which makes the response smaller

**Outputs:**

- `id` (integer)
- `name` (string, nullable)
- `display_title` (string, nullable)
- `workflow_id` (integer, nullable)
- `path` (string, nullable)
- `head_branch` (string, nullable)
- `head_sha` (string, nullable)
- `run_number` (integer, nullable)
- `run_attempt` (integer)
- `event` (string, nullable)
- `status` (string, nullable)
- `conclusion` (string, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `run_started_at` (string, nullable)
- `actor` (object, nullable)
- `triggering_actor` (object, nullable)
- `head_commit` (object, nullable)
- `logs_archive_url` (string, nullable)
- `url` (string)

#### `get_workflow_run_logs`

Locate a workflow run's log archive and list its jobs. GitHub only serves whole-run logs as a ZIP file, so this returns the download URL plus the job IDs you can read as text with Get Job Logs — it does not return the archive

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID

**Outputs:**

- `run_id` (integer)
- `name` (string, nullable)
- `status` (string, nullable)
- `conclusion` (string, nullable)
- `run_attempt` (integer)
- `url` (string)
- `logs_archive_url` (string)
- `archive_returned` (boolean)
- `jobs` (array)
- `note` (string)

#### `get_workflow_run_usage`

Get the billable runner minutes a workflow run consumed, broken down by operating system. Billable time only accrues on private repositories using GitHub-hosted runners, and excludes the macOS and Windows cost multipliers. GitHub has announced this endpoint is closing down

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID

**Outputs:**

- `run_id` (integer)
- `run_duration_ms` (integer, nullable)
- `run_duration_minutes` (number)
- `total_billable_ms` (integer)
- `total_billable_minutes` (number)
- `billable` (array)

#### `get_workflow_runs`

Get runs for a workflow

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `workflow_id` (string, required): Workflow ID or filename
- `status` (string, optional) One of: `queued`, `in_progress`, `completed`, `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`.
- `branch` (string, optional): Filter by branch

**Outputs:**

Array of objects, each with: `id`, `name`, `workflow_id`, `head_branch`, `head_sha`, `run_number`, `event`, `status`, `conclusion`, `created_at`, `updated_at`, `run_started_at`, `run_attempt`, `actor`, `url`

#### `list_workflow_jobs`

List the jobs in a workflow run with each job's step-by-step outcome, to pinpoint what failed

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID
- `filter` (string, optional): 'latest' returns jobs from the most recent attempt only; 'all' includes every attempt One of: `latest`, `all`.
- `limit` (integer, optional): Maximum number of jobs to return

**Outputs:**

Array of objects, each with: `id`, `run_id`, `run_attempt`, `name`, `workflow_name`, `head_branch`, `head_sha`, `status`, `conclusion`, `created_at`, `started_at`, `completed_at`, `runner_name`, `labels`, `steps`, `url`

#### `list_workflow_run_artifacts`

List the build artifacts a workflow run uploaded, with their sizes, expiry dates and download URLs

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID
- `name` (string, optional): Return only artifacts with this exact name
- `limit` (integer, optional): Maximum number of artifacts to return

**Outputs:**

Array of objects, each with: `id`, `name`, `size_in_bytes`, `expired`, `created_at`, `updated_at`, `expires_at`, `digest`, `archive_download_url`, `url`, `workflow_run`

#### `list_workflows`

List GitHub Actions workflows

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**

Array of objects, each with: `id`, `name`, `path`, `state`, `created_at`, `updated_at`, `url`

#### `rerun_failed_jobs`

Re-run only the failed jobs of a workflow run, leaving jobs that already succeeded alone

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID
- `enable_debug_logging` (boolean, optional): Turn on runner and step debug logging for the re-run

**Outputs:**

- `rerun_requested` (boolean)
- `run_id` (integer)
- `scope` (string)
- `url` (string)

#### `rerun_workflow_run`

Re-run every job in a workflow run, for example after fixing a flaky test or an expired credential

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `run_id` (integer, required): The workflow run's numeric ID
- `enable_debug_logging` (boolean, optional): Turn on runner and step debug logging for the re-run

**Outputs:**

- `rerun_requested` (boolean)
- `run_id` (integer)
- `scope` (string)
- `url` (string)

#### `run_workflow`

Trigger a workflow on a branch or tag. The workflow must declare a workflow_dispatch trigger

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `workflow_id` (string/integer, required): The workflow's numeric ID or its filename, for example 'ci.yml'
- `ref` (string, required): Branch or tag name to run the workflow against
- `inputs` (object, optional): Values for the workflow's own inputs, keyed by input name. At most 25 keys
- `return_run_details` (boolean, optional): Ask GitHub to return the new run's ID and URL. Off by default, in which case GitHub confirms the dispatch without identifying the run

**Outputs:**

- `dispatched` (boolean)
- `workflow_id` (string)
- `ref` (string)
- `inputs` (object)
- `run_id` (integer, nullable)
- `run_api_url` (string, nullable)
- `url` (string, nullable)
- `message` (string)

### Security

#### `get_code_quality_finding`

Fetch one GitHub Code Quality finding with its rule, message and source location. Public preview: available on github.com only, not on GitHub Enterprise Server. Needs the repo scope and Code Quality enabled on the repository; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `finding_number` (integer, required): The finding number, as shown in GitHub and in the list action's output.

**Outputs:**

- `number` (integer, nullable)
- `state` (string, nullable)
- `severity` (string, nullable)
- `created_at` (string, nullable)
- `url` (string, nullable)
- `message` (string, nullable)
- `rule` (object, nullable)
- `location` (object, nullable)

#### `get_code_scanning_alert`

Fetch the full detail of one code scanning alert — the rule that fired, the tool that found it and the exact file and line of the most recent occurrence. Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `alert_number` (integer, required): The alert number, as shown in GitHub and in the list action's output.

**Outputs:**

- `number` (integer, nullable)
- `state` (string, nullable)
- `severity` (string, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `url` (string, nullable)
- `fixed_at` (string, nullable)
- `dismissed_at` (string, nullable)
- `dismissed_reason` (string, nullable)
- `dismissed_comment` (string, nullable)
- `dismissed_by` (object, nullable)
- `rule` (object, nullable)
- `tool` (object, nullable)
- `most_recent_instance` (object, nullable)
- `repository` (string, nullable)

#### `get_dependabot_alert`

Fetch one Dependabot alert with the affected package, the vulnerable version range and the first patched version, so a workflow can decide whether to open an upgrade PR. Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `alert_number` (integer, required): The alert number, as shown in GitHub and in the list action's output.

**Outputs:**

- `number` (integer, nullable)
- `state` (string, nullable)
- `severity` (string, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `url` (string, nullable)
- `fixed_at` (string, nullable)
- `auto_dismissed_at` (string, nullable)
- `dismissed_at` (string, nullable)
- `dismissed_reason` (string, nullable)
- `dismissed_comment` (string, nullable)
- `dismissed_by` (object, nullable)
- `package` (string, nullable)
- `ecosystem` (string, nullable)
- `manifest_path` (string, nullable)
- `scope` (string, nullable)
- `ghsa_id` (string, nullable)
- `cve_id` (string, nullable)
- `summary` (string, nullable)
- `vulnerable_version_range` (string, nullable)
- `first_patched_version` (string, nullable)
- `repository` (string, nullable)

#### `get_global_security_advisory`

Look up one advisory in the GitHub Advisory Database by GHSA ID to get its description, CVSS score, CWEs and the affected package version ranges. Needs no special scope.

**Inputs:**

- `ghsa_id` (string, required): The GHSA ID of the advisory, e.g. GHSA-abcd-1234-efgh.

**Outputs:**

- `ghsa_id` (string, nullable)
- `cve_id` (string, nullable)
- `summary` (string, nullable)
- `description` (string, nullable)
- `type` (string, nullable)
- `severity` (string, nullable)
- `url` (string, nullable)
- `source_code_location` (string, nullable)
- `repository_advisory_url` (string, nullable)
- `published_at` (string, nullable)
- `updated_at` (string, nullable)
- `github_reviewed_at` (string, nullable)
- `nvd_published_at` (string, nullable)
- `withdrawn_at` (string, nullable)
- `identifiers` (array)
- `references` (array)
- `cwes` (array)
- `cvss` (object, nullable)
- `vulnerabilities` (array)

#### `get_secret_scanning_alert`

Fetch one leaked-credential alert: its type, validity, resolution and first detected location. The leaked secret itself is never requested or returned. Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `alert_number` (integer, required): The alert number, as shown in GitHub and in the list action's output.

**Outputs:**

- `number` (integer, nullable)
- `state` (string, nullable)
- `resolution` (string, nullable)
- `secret_type` (string, nullable)
- `secret_type_display_name` (string, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `url` (string, nullable)
- `validity` (string, nullable)
- `push_protection_bypassed` (boolean, nullable)
- `has_more_locations` (boolean, nullable)
- `first_location` (object, nullable)
- `repository` (string, nullable)

#### `list_code_quality_findings`

List GitHub Code Quality findings for a repository — maintainability and reliability issues with the rule, file and line that triggered them. Public preview: available on github.com only, not on GitHub Enterprise Server. Needs the repo scope and Code Quality enabled on the repository; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `state` (string, optional): Only return findings in this state. One of: `open`, `dismissed`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-100, default 100). This endpoint is cursor-paginated and does not honour page numbers, so a single request of at most 100 results is made.

**Outputs:**

Array of objects, each with: `number`, `state`, `severity`, `created_at`, `url`, `message`, `rule`, `location`

#### `list_code_scanning_alerts`

Triage open CodeQL and third-party static-analysis alerts across a repository, or across every repository in an organization, filtered by state, severity, tool or branch. Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, optional): Repository owner. Provide with 'repo' to scope the query to one repository.
- `repo` (string, optional): Repository name. Provide with 'owner' to scope the query to one repository.
- `org` (string, optional): Organization login. Use instead of owner/repo to scan every repository in the organization.
- `state` (string, optional): Only return alerts in this state. One of: `open`, `closed`, `dismissed`, `fixed`.
- `severity` (string, optional): Only return alerts at this severity. One of: `critical`, `high`, `medium`, `low`, `warning`, `note`, `error`.
- `tool_name` (string, optional): Only return alerts raised by this analysis tool, e.g. CodeQL.
- `ref` (string, optional): Git reference to report on, e.g. refs/heads/main. Repository-level queries only.
- `pr` (integer, optional): Only return alerts for this pull request number. Repository-level queries only.
- `sort` (string, optional): Property to sort by. Defaults to created. One of: `created`, `updated`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-1000, default 100). Results are fetched in pages of 100.

**Outputs:**

Array of objects, each with: `number`, `state`, `severity`, `created_at`, `updated_at`, `url`, `fixed_at`, `dismissed_at`, `dismissed_reason`, `dismissed_comment`, `dismissed_by`, `rule`, `tool`, `most_recent_instance`, `repository`

#### `list_dependabot_alerts`

Review vulnerable dependencies flagged by Dependabot for a repository or a whole organization, filtered by state, severity, ecosystem, package or dependency scope. Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, optional): Repository owner. Provide with 'repo' to scope the query to one repository.
- `repo` (string, optional): Repository name. Provide with 'owner' to scope the query to one repository.
- `org` (string, optional): Organization login. Use instead of owner/repo to scan every repository in the organization.
- `state` (string, optional): Only return alerts in this state. One of: `auto_dismissed`, `dismissed`, `fixed`, `open`.
- `severity` (string, optional): Only return alerts at this severity. One of: `low`, `medium`, `high`, `critical`.
- `ecosystem` (string, optional): Comma-separated package ecosystems to include, e.g. npm,pip. One of composer, go, maven, npm, nuget, pip, pub, rubygems, rust.
- `package` (string, optional): Comma-separated package names to include.
- `scope` (string, optional): Only return alerts for dependencies of this scope. One of: `development`, `runtime`.
- `manifest` (string, optional): Comma-separated manifest paths to include, e.g. package.json.
- `sort` (string, optional): Property to sort by. Defaults to created. One of: `created`, `updated`, `epss_percentage`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-100, default 100). This endpoint is cursor-paginated and does not honour page numbers, so a single request of at most 100 results is made.

**Outputs:**

Array of objects, each with: `number`, `state`, `severity`, `created_at`, `updated_at`, `url`, `fixed_at`, `auto_dismissed_at`, `dismissed_at`, `dismissed_reason`, `dismissed_comment`, `dismissed_by`, `package`, `ecosystem`, `manifest_path`, `scope`, `ghsa_id`, `cve_id`, `summary`, `vulnerable_version_range`, `first_patched_version`, `repository`

#### `list_global_security_advisories`

Search the public GitHub Advisory Database — for example, every critical npm advisory published this month, or the advisories affecting a specific package version. Needs no special scope.

**Inputs:**

- `ghsa_id` (string, optional): Return only the advisory with this GHSA ID.
- `cve_id` (string, optional): Return only advisories carrying this CVE ID.
- `type` (string, optional): Advisory type. Defaults to reviewed. One of: `reviewed`, `malware`, `unreviewed`.
- `ecosystem` (string, optional): Package ecosystem to filter by: actions, composer, erlang, go, maven, npm, nuget, other, pip, pub, rubygems, rust, swift.
- `severity` (string, optional): Only return advisories at this severity. One of: `unknown`, `low`, `medium`, `high`, `critical`.
- `cwes` (string, optional): Comma-separated CWE IDs, e.g. 79,284,22.
- `affects` (string, optional): Comma-separated packages, optionally pinned to a version, e.g. package1,package2@1.0.0.
- `published` (string, optional): Published date filter, e.g. 2024-01-01 or a 2024-01-01..2024-06-30 range.
- `updated` (string, optional): Last-updated date filter, e.g. >2024-01-01 or a date range.
- `modified` (string, optional): Published-or-updated date filter, e.g. >=2024-01-01 or a date range.
- `is_withdrawn` (boolean, optional): Set true to return only withdrawn advisories.
- `sort` (string, optional): Property to sort by. Defaults to published. One of: `updated`, `published`, `epss_percentage`, `epss_percentile`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-100, default 100). This endpoint is cursor-paginated and does not honour page numbers, so a single request of at most 100 results is made.

**Outputs:**

Array of objects, each with: `ghsa_id`, `cve_id`, `summary`, `description`, `type`, `severity`, `url`, `source_code_location`, `repository_advisory_url`, `published_at`, `updated_at`, `github_reviewed_at`, `nvd_published_at`, `withdrawn_at`, `identifiers`, `references`, `cwes`, `cvss`, `vulnerabilities`

#### `list_repository_security_advisories`

List the security advisories your team has drafted or published on a repository, or across every repository in an organization — useful for tracking embargoed advisories still in triage or draft. Needs the repo scope; organization-wide queries additionally require owner or security manager access, otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, optional): Repository owner. Provide with 'repo' to scope the query to one repository.
- `repo` (string, optional): Repository name. Provide with 'owner' to scope the query to one repository.
- `org` (string, optional): Organization login. Use instead of owner/repo to scan every repository in the organization.
- `state` (string, optional): Only return advisories in this state. One of: `triage`, `draft`, `published`, `closed`.
- `sort` (string, optional): Property to sort by. Defaults to created. One of: `created`, `updated`, `published`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-100, default 100). This endpoint is cursor-paginated and does not honour page numbers, so a single request of at most 100 results is made.

**Outputs:**

Array of objects, each with: `ghsa_id`, `cve_id`, `summary`, `description`, `severity`, `state`, `url`, `created_at`, `updated_at`, `published_at`, `closed_at`, `withdrawn_at`, `author`, `publisher`, `identifiers`, `cwe_ids`, `cvss`, `vulnerabilities`

#### `list_secret_scanning_alerts`

Review leaked-credential alerts for a repository or a whole organization. The leaked secret itself is never requested or returned — only the alert metadata (type, state, validity and where it was found). Requires GitHub Advanced Security to be enabled on the target and a token with the security_events scope; otherwise GitHub returns 403.

**Inputs:**

- `owner` (string, optional): Repository owner. Provide with 'repo' to scope the query to one repository.
- `repo` (string, optional): Repository name. Provide with 'owner' to scope the query to one repository.
- `org` (string, optional): Organization login. Use instead of owner/repo to scan every repository in the organization.
- `state` (string, optional): Only return alerts in this state. One of: `open`, `resolved`.
- `secret_type` (string, optional): Comma-separated secret type slugs to include, e.g. github_personal_access_token.
- `resolution` (string, optional): Only return resolved alerts closed for this reason. One of: `false_positive`, `wont_fix`, `revoked`, `used_in_tests`.
- `validity` (string, optional): Comma-separated validity states to include: active, inactive, unknown. Active means GitHub confirmed the credential still works.
- `sort` (string, optional): Property to sort by. Defaults to created. One of: `created`, `updated`.
- `direction` (string, optional): Sort direction. Defaults to desc. One of: `asc`, `desc`.
- `limit` (integer, optional): Maximum number of results to return (1-1000, default 100). Results are fetched in pages of 100.

**Outputs:**

Array of objects, each with: `number`, `state`, `resolution`, `secret_type`, `secret_type_display_name`, `created_at`, `updated_at`, `url`, `validity`, `push_protection_bypassed`, `has_more_locations`, `first_location`, `repository`

### Releases & Tags

#### `get_latest_release`

Get the latest published release for a repository

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name

**Outputs:**

- `id` (integer)
- `tag_name` (string)
- `target_commitish` (string, nullable)
- `name` (string, nullable)
- `body` (string, nullable)
- `draft` (boolean)
- `prerelease` (boolean)
- `created_at` (string)
- `published_at` (string, nullable)
- `html_url` (string)
- `tarball_url` (string, nullable)
- `zipball_url` (string, nullable)
- `author` (object, nullable)
- `assets` (array)

#### `get_release`

Get a specific release by ID

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name
- `release_id` (integer, required): The unique identifier of the release

**Outputs:**

- `id` (integer)
- `tag_name` (string)
- `target_commitish` (string, nullable)
- `name` (string, nullable)
- `body` (string, nullable)
- `draft` (boolean)
- `prerelease` (boolean)
- `created_at` (string)
- `published_at` (string, nullable)
- `html_url` (string)
- `tarball_url` (string, nullable)
- `zipball_url` (string, nullable)
- `author` (object, nullable)
- `assets` (array)

#### `get_release_by_tag`

Get a release by tag name

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name
- `tag` (string, required): Tag name (e.g., 'v1.0.0')

**Outputs:**

- `id` (integer)
- `tag_name` (string)
- `target_commitish` (string, nullable)
- `name` (string, nullable)
- `body` (string, nullable)
- `draft` (boolean)
- `prerelease` (boolean)
- `created_at` (string)
- `published_at` (string, nullable)
- `html_url` (string)
- `tarball_url` (string, nullable)
- `zipball_url` (string, nullable)
- `author` (object, nullable)
- `assets` (array)

#### `list_releases`

List releases for a repository

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name
- `per_page` (integer, optional): Results per page (max 100) Default: `30`.
- `page` (integer, optional): Page number Default: `1`.

**Outputs:**

Array of objects, each with: `id`, `tag_name`, `name`, `body`, `draft`, `prerelease`, `created_at`, `published_at`, `html_url`, `tarball_url`, `zipball_url`, `author`, `assets`

#### `list_tags`

List all tags for a repository

**Inputs:**

- `owner` (string, required): Repository owner (user or organization)
- `repo` (string, required): Repository name
- `per_page` (integer, optional): Results per page (max 100) Default: `30`.
- `page` (integer, optional): Page number Default: `1`.

**Outputs:**

Array of objects, each with: `name`, `commit`, `zipball_url`, `tarball_url`, `node_id`

### Users, Organizations & Teams

#### `get_team_members`

List the people on a team so you can notify them, assign reviewers, or check who has access. Members of the team's child teams are included. Note that GitHub hides private team structure: an organization or team the connected account cannot see returns a 404 rather than a permission error.

**Inputs:**

- `org` (string, required): Organization login (e.g. 'autohive-ai')
- `team_slug` (string, required): The team's slug, NOT its numeric id — the URL-safe name from the team's page (github.com/orgs/<org>/teams/<team_slug>), e.g. 'platform-engineering'. Use Get Teams to look one up.
- `role` (string, optional): Which members to return One of: `member`, `maintainer`, `all`. Default: `all`.
- `limit` (integer, optional): Maximum number of members to return

**Outputs:**

Array of objects, each with: `login`, `id`, `type`, `site_admin`, `avatar_url`, `url`

#### `get_teams`

List the teams in an organization so you can route work, look up a team slug, or audit team structure. Omit the organization to list every team the connected account belongs to, across all of its organizations. Note that GitHub hides private team structure: if the connected account is not a member of the organization, this returns a 404 rather than a permission error, even for an organization you know exists.

**Inputs:**

- `org` (string, optional): Organization login (e.g. 'autohive-ai'). Omit to list the connected account's teams across every organization it belongs to.
- `limit` (integer, optional): Maximum number of teams to return

**Outputs:**

Array of objects, each with: `id`, `name`, `slug`, `description`, `privacy`, `notification_setting`, `permission`, `parent`, `organization`, `members_count`, `repos_count`, `url`

#### `get_user`

Get user information

**Inputs:**

- `username` (string, optional): Username (omit for authenticated user)

**Outputs:**

- `login` (string)
- `id` (integer)
- `name` (string, nullable)
- `company` (string, nullable)
- `blog` (string, nullable)
- `location` (string, nullable)
- `email` (string, nullable)
- `bio` (string, nullable)
- `public_repos` (integer)
- `public_gists` (integer)
- `followers` (integer)
- `following` (integer)
- `created_at` (string)
- `updated_at` (string)
- `avatar_url` (string)
- `html_url` (string)

#### `list_organization_members`

List organization members

**Inputs:**

- `org` (string, required): Organization name
- `role` (string, optional) One of: `all`, `admin`, `member`. Default: `all`.

**Outputs:**

Array of objects, each with: `login`, `id`, `type`, `site_admin`, `avatar_url`, `url`

### Gists

#### `create_gist`

Create a new gist

**Inputs:**

- `description` (string, optional): Gist description
- `files` (object, required): Files in the gist
- `public` (boolean, optional): Make gist public Default: `True`.

**Outputs:**

- `id` (string)
- `description` (string, nullable)
- `public` (boolean)
- `files` (object)
- `created_at` (string)
- `updated_at` (string)
- `url` (string)

#### `get_gist`

Fetch one gist with the full text of every file in it, for reading a shared snippet, config or note. GitHub inlines at most 1 MB per file: when a file was cut short its 'truncated' flag is true and the whole file has to be downloaded from its raw_url, or cloned from git_pull_url once it passes 10 MB.

**Inputs:**

- `gist_id` (string, required): The gist's id — the hex string at the end of its URL (e.g. '6cad326836d38bd3a7ae')

**Outputs:**

- `id` (string)
- `description` (string, nullable)
- `public` (boolean)
- `owner` (object, nullable)
- `files` (object): Files keyed by filename. Each holds filename, type, language, size, raw_url, truncated, content and encoding.
- `truncated` (boolean, nullable): True when the gist holds more than 300 files and only the first 300 are listed
- `comments` (integer, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `git_pull_url` (string, nullable): Clone URL, needed to retrieve files larger than 10 MB
- `url` (string, nullable)

#### `list_gists`

List the connected account's gists, or another user's public gists, to find a snippet or track what someone has published recently. File content is not included — GitHub returns only file metadata when listing — so use Get Gist to read a file's text.

**Inputs:**

- `username` (string, optional): List this user's public gists. Omit to list the connected account's own gists, secret ones included.
- `since` (string, optional): ISO 8601 date or timestamp; only return gists updated at or after this point (e.g. '2024-01-31' or '2024-01-31T00:00:00Z')
- `limit` (integer, optional): Maximum number of gists to return

**Outputs:**

Array of objects, each with: `id`, `description`, `public`, `owner`, `files`, `truncated`, `comments`, `created_at`, `updated_at`, `git_pull_url`, `url`

#### `update_gist`

Edit an existing gist: change its description, rewrite or rename a file, add a new file, or remove one. Only the files you name are touched; everything else in the gist is left alone. Deleting is deliberately kept separate from editing, in 'delete_files', so a malformed edit cannot destroy a file by accident.

**Inputs:**

- `gist_id` (string, required): The gist's id — the hex string at the end of its URL
- `description` (string, optional): New description for the gist. Omit to leave it unchanged.
- `files` (object, optional): Files to add or change, keyed by the file's CURRENT filename. Each value is an object with 'content' (the file's new full text) and/or 'filename' (a new name, which renames the file). Use a filename that is not in the gist yet to add a file. Example: {"notes.md": {"content": "# Notes"}, "old.py": {"filename": "new.py"}}. An entry with neither key is rejected rather than sent, because GitHub would read it as a deletion.
- `delete_files` (array, optional): Filenames to delete from the gist. Deleting a gist's last remaining file deletes the gist itself.

**Outputs:**

- `id` (string)
- `description` (string, nullable)
- `public` (boolean)
- `owner` (object, nullable)
- `files` (object): The gist's files after the update, keyed by filename, metadata only
- `truncated` (boolean, nullable)
- `comments` (integer, nullable)
- `created_at` (string, nullable)
- `updated_at` (string, nullable)
- `git_pull_url` (string, nullable)
- `url` (string, nullable)

### Webhooks

#### `create_webhook`

Create a webhook

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `url` (string, required): Webhook URL
- `events` (array, required): Events to trigger webhook
- `content_type` (string, optional) One of: `json`, `form`. Default: `json`.
- `secret` (string, optional): Webhook secret
- `active` (boolean, optional) Default: `True`.

**Outputs:**

- `id` (integer)
- `name` (string)
- `active` (boolean)
- `events` (array)
- `config` (object)
- `created_at` (string)
- `updated_at` (string)
- `url` (string)

#### `delete_webhook`

Delete a webhook

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `hook_id` (integer, required): Webhook ID

**Outputs:**

- `deleted` (boolean)
- `hook_id` (integer)

#### `list_webhooks`

List webhooks for a repository

**Inputs:**

- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**

Array of objects, each with: `id`, `name`, `active`, `events`, `config`, `created_at`, `updated_at`, `url`

### Platform

#### `get_rate_limit`

Get current rate limit status

**Inputs:**

- _None_

**Outputs:**

- `core` (object, nullable)
- `search` (object, nullable)
- `graphql` (object, nullable)
## Not included

The following GitHub capabilities are deliberately out of scope. They are listed here so a future maintainer does not have to rediscover why.

| Area | Reason |
|---|---|
| Notifications | Outside the domains this integration targets |
| Discussions | GraphQL-only — GitHub exposes no REST API for repository discussions |
| Projects v2 | Outside the targeted domains (REST endpoints do now exist, so this is a scope decision, not a technical one) |
| Stars | Outside the targeted domains |
| Copilot (assign to issue, request review) | Outside the targeted domains; assigning Copilot is GraphQL-only |
| Creating a PR with Copilot | No public API — the GitHub MCP server implements this against its own hosted service |
| Deleting gists, gist comments | Not part of the targeted capability set |
| Enterprise-tier endpoints, billing, migrations, GitHub Apps | Require enterprise or app tokens rather than the OAuth user token this integration holds |

## API version

GitHub REST API `2022-11-28`.

One action uses GitHub's GraphQL API: `add_comment_to_pending_review`. REST can only attach comments to a pending review at creation time, so adding one to an existing pending review has no REST equivalent. It uses the `addPullRequestReviewThread` mutation (`addPullRequestReviewComment` is deprecated).

## Rate limiting

| Limit | Value |
|---|---|
| Authenticated REST requests | 5,000 per hour |
| Search API | 30 requests per minute |
| Code search (`search_code`) | **10 requests per minute** |
| GraphQL | 5,000 points per hour |

Search additionally caps **every** query at 1,000 results no matter how far you paginate. The search actions return `total_count` (GitHub's true match count), `incomplete_results`, and a `capped` flag so a workflow can distinguish "1,000 results" from "the first 1,000 of 50,000".

Use `get_rate_limit` to check current usage. GitHub also applies undocumented secondary rate limits to rapid write bursts; space out loops that create or update resources.

## Pagination

Most list actions paginate automatically, bounded by a `max_pages` cap (default 10) that raises rather than looping until the platform kills the request. Narrow with filters if you hit it.

Some GitHub endpoints are **cursor-paginated** rather than page-numbered, and silently ignore a `page` parameter — Dependabot alerts, code quality findings, and both advisory endpoints behave this way. Those actions return a single page of up to 100 items and their `limit` input is capped accordingly, rather than appearing to paginate while returning the same page repeatedly.

## Error handling

Actions return an `ActionError` on failure, surfaced to the workflow with a message. They do **not** return `result`/`error` fields in their data.

| Status | Meaning |
|---|---|
| `401` | Invalid or expired OAuth token — reconnect the integration |
| `403` | Insufficient scope, rate limit exceeded, or a feature (e.g. GitHub Advanced Security) not enabled on the repository |
| `404` | Resource not found. For organization and team actions, GitHub returns `404` rather than `403` when the token lacks `read:org`, to avoid disclosing private org structure |
| `409` | Conflict — e.g. creating a file that already exists |
| `422` | Validation failure. Common with search when a `sort` value is not valid for that endpoint |

Inputs are validated against each action's schema before the handler runs; a schema violation returns a validation error rather than an `ActionError`.

## Security considerations

- **Secret scanning never returns the leaked credential.** `list_secret_scanning_alerts` and `get_secret_scanning_alert` always send `hide_secret=true`, and their output is a strict allow-list — `secret`, `resolution_comment`, `metadata` and blob URLs are never emitted. There is no input to disable this. Alert metadata (type, state, resolution, file path and line numbers) is returned so triage workflows still work.
- OAuth tokens are held and injected by the Autohive platform; the integration never reads or logs them.
- Webhook secrets are write-only — supply them on `create_webhook`; GitHub does not return them.
- `push_files`, `delete_file`, `delete_branch`, `delete_repository` and `delete_webhook` are destructive and irreversible. `delete_repository` requires the token to own the repository.
- Review granted scopes periodically; see [Required Scopes](#required-scopes) for why each is requested.

## Known limitations

- **Workflow run logs and artifacts cannot be downloaded through this integration.** Both endpoints `302` to a signed ZIP URL. The platform's HTTP client follows redirects automatically and decodes bodies as text, which raises `UnicodeDecodeError` on a ZIP. `get_workflow_run_logs` and `download_workflow_run_artifact` therefore return metadata and the `archive_download_url` for you to fetch separately, and never request the archive. `get_job_logs` is unaffected — its redirect target is plain text — and returns log content directly, tail-trimmed via `tail_lines`.
- `get_workflow_run_usage` wraps an endpoint GitHub has marked as closing down. It still returns data. Billable time only accrues for private repositories on GitHub-hosted runners, and excludes macOS/Windows cost multipliers.
- Code quality findings are a **public preview** API, available on github.com only — not GitHub Enterprise Server.
- GitHub returns at most 3,000 files and 250 commits for a single pull request regardless of pagination.
- `fork_repository` is asynchronous. It returns `202` and the fork's git objects may not be readable immediately.
- `search_code` requires at least one search term — `language:go` alone is rejected, `parser language:go` is valid. It indexes default branches only, skips files over 384 KB, and excludes most forks.

## Development

```bash
# Setup (Python 3.13+)
uv venv --python 3.13 .venv && source .venv/bin/activate
uv pip install -r requirements-test.txt
uv pip install -r github/requirements.txt

# Unit tests
pytest github/

# Live tests (read-only, needs GITHUB_ACCESS_TOKEN in .env)
pytest github/tests/test_github_integration.py -m "integration and not destructive"

# Live write tests — CREATE/MODIFY/DELETE real data in the repo you nominate
export GITHUB_TEST_REPO=my-org/my-scratch-repo
pytest github/tests/test_github_integration.py -m "integration and destructive"

# Validation (mirrors CI)
python ../autohive-integrations-tooling/scripts/validate_integration.py github
python ../autohive-integrations-tooling/scripts/check_code.py github
ruff check --fix github && ruff format github
```

Run tests **per integration** (`pytest github/`), not from the repository root. Action handlers live in an `actions/` package and import shared code as the top-level module `helpers`; that name is shared by every modular integration in this repository, so collecting several of them in one pytest process causes import collisions.

## Structure

```
github/
  github.py          # entry point: Integration.load() + imports actions, connected-account handler
  helpers.py         # GitHubAPI client, error decorator, response shaping
  config.json        # 111 action definitions
  actions/           # one module per domain; importing the package registers every handler
  tests/
```

## Troubleshooting

**401 Unauthorized** — re-authenticate the integration in Autohive.

**403 on security actions** — the token may lack `security_events`, GitHub Advanced Security may not be enabled on the repository, or org-level alert listing may require you to be an organization owner or security manager.

**404 on an organization or team that exists** — the token lacks `read:org`, or you are not a member. GitHub hides private org structure behind a 404.

**422 on a search action** — the `sort` value is probably not valid for that endpoint. Valid values differ per search type and are listed in each action's `sort` description.

**Pagination stopped with a timeout message** — the `max_pages` cap was hit. Narrow the request with filters (`sha`, `path`, `since`, `until`, `state`) or raise `max_pages`.

**`run_workflow` returns no run ID** — the dispatch endpoint returns `204 No Content` by default. Set `return_run_details` to `true` to get the run ID back.

## Support

- [GitHub REST API documentation](https://docs.github.com/en/rest)
- Contact Autohive support for platform issues

## Version history

- **3.0.0**
  - Added 64 actions: search (7), issue labels and sub-issues (12), pull request review lifecycle and diff/files/status (13), repository fork/tree/collaborators and atomic multi-file `push_files` (4), GitHub Actions run/re-run/cancel/jobs/logs/artifacts (12), security alerts and advisories (11), teams (2), gist read/list/update (3)
  - Added the `security_events` OAuth scope for the Dependabot, code scanning, and secret scanning actions
  - Restructured from a single `github.py` into an `actions/` package with shared `helpers.py`; all existing action behaviour is unchanged
  - Corrected the documented OAuth scopes — this README previously listed fourteen scopes, eight of which the integration never requested
  - Corrected the documented action outputs, which described a `result`/`error` envelope the actions do not return
  - Fixed `diff_branch_to_branch` crashing on commits with a null author (deleted accounts and some bot commits) — the same fix `list_commits` received in 2.4.0
  - Fixed `get_rate_limit` crashing when GitHub omits the `graphql` resource block

- **2.6.0**
  - `get_file_content` now handles directory paths, returning a `type` field and an `entries` array instead of failing on GitHub's array response shape

- **1.0.0** (Initial release)
  - GitHub REST API integration with OAuth2 platform authentication

# GitHub Integration for Autohive

A comprehensive GitHub integration for the Autohive platform that enables full repository management, issue tracking, pull request workflows, commit operations, branch management, webhooks, gists, and file operations.

## Description

This integration provides complete access to GitHub's REST API (v2022-11-28), allowing you to automate your entire GitHub workflow through Autohive. Whether you're managing repositories, tracking issues, reviewing pull requests, or automating deployments with webhooks, this integration has you covered.

### Key Features

- **Repository Management**: Create, read, update, and delete repositories
- **Issue Tracking**: Full CRUD operations for issues and comments
- **Pull Request Workflows**: Create, review, merge, and manage pull requests
- **Commit Operations**: Access commit history and details
- **Branch Management**: Create, delete, and manage branches
- **Webhook Integration**: Set up automated workflows with webhooks
- **File Operations**: Read, create, update, and delete files directly in repositories
- **Gist Management**: Create and manage code snippets
- **Rate Limiting**: Built-in rate limit monitoring and handling

## Setup & Authentication

This integration uses GitHub's OAuth2 platform authentication for secure access to your GitHub account.

### Authentication Type

**OAuth2 Platform Authentication** via GitHub

### Required Scopes

The integration requests the following OAuth2 scopes:

- `repo` - Full access to repositories (public and private)
- `admin:repo_hook` - Full control of repository webhooks
- `admin:org_hook` - Full control of organization webhooks
- `gist` - Create and manage gists
- `user` - Access user profile information
- `read:user` - Read user profile data
- `user:email` - Access user email addresses
- `user:follow` - Follow and unfollow users
- `admin:org` - Full control of organizations and teams
- `workflow` - Manage GitHub Actions workflows
- `admin:public_key` - Manage public SSH keys
- `admin:gpg_key` - Manage GPG keys
- `write:packages` - Upload and publish packages
- `read:packages` - Download and read packages

### Setup Steps

1. In Autohive, navigate to Integrations
2. Select "GitHub" integration
3. Click "Connect" or "Authenticate"
4. You'll be redirected to GitHub's OAuth authorization page
5. Review the requested permissions and click "Authorize"
6. You'll be redirected back to Autohive with the integration connected

## Actions

### Repository Actions

#### `create_repository`

Creates a new GitHub repository in your account or an organization.

**Inputs:**
- `name` (string, required): Repository name
- `org` (string, optional): Organization name (leave empty for personal account)
- `description` (string, optional): Repository description
- `private` (boolean, optional): Whether repository is private (default: false)
- `auto_init` (boolean, optional): Initialize with README (default: true)
- `gitignore_template` (string, optional): Gitignore template (e.g., 'Python', 'Node', 'Java')
- `license_template` (string, optional): License template (e.g., 'mit', 'apache-2.0', 'gpl-3.0')
- `homepage` (string, optional): Home page URL
- `has_issues` (boolean, optional): Enable issues (default: true)
- `has_projects` (boolean, optional): Enable projects (default: true)
- `has_wiki` (boolean, optional): Enable wiki (default: true)

**Outputs:**
- `repository` (object): Created repository details including id, name, url, clone_url, etc.
- `result` (boolean): Operation success status
- `error` (string): Error message if operation failed

**Example:**
```json
{
  "name": "my-awesome-project",
  "description": "An awesome new project",
  "private": false,
  "auto_init": true,
  "gitignore_template": "Python",
  "license_template": "mit"
}
```

#### `get_repository`

Retrieves detailed information about a specific repository.

**Inputs:**
- `owner` (string, required): Repository owner (username or organization)
- `repo` (string, required): Repository name

**Outputs:**
- `repository` (object): Full repository details
- `result` (boolean): Operation success status

#### `list_repositories`

Lists repositories for authenticated user, specific user, or organization.

**Inputs:**
- `type` (string, optional): Type filter - "all", "owner", "public", "private", "member" (default: "all")
- `sort` (string, optional): Sort field - "created", "updated", "pushed", "full_name" (default: "updated")
- `direction` (string, optional): Sort direction - "asc" or "desc" (default: "desc")
- `username` (string, optional): Username to list repos for (leave empty for authenticated user)
- `org` (string, optional): Organization name to list repos for
- `per_page` (integer, optional): Results per page, 1-100 (default: 30)

**Outputs:**
- `repositories` (array): List of repository objects
- `result` (boolean): Operation success status

#### `update_repository`

Updates repository settings and configuration.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `name` (string, optional): New repository name
- `description` (string, optional): New description
- `private` (boolean, optional): Update visibility
- `has_issues` (boolean, optional): Enable/disable issues
- `has_wiki` (boolean, optional): Enable/disable wiki

**Outputs:**
- `repository` (object): Updated repository details
- `result` (boolean): Operation success status

#### `delete_repository`

Permanently deletes a repository. **Use with extreme caution!**

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**
- `result` (boolean): Operation success status
- `error` (string): Error message if operation failed

---

### Issue Actions

#### `create_issue`

Creates a new issue in a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `title` (string, required): Issue title
- `body` (string, optional): Issue description (supports markdown)
- `assignees` (array, optional): Array of usernames to assign
- `labels` (array, optional): Array of label names

**Outputs:**
- `issue` (object): Created issue details including number, url, state, etc.
- `result` (boolean): Operation success status

**Example:**
```json
{
  "owner": "myusername",
  "repo": "my-project",
  "title": "Bug: Application crashes on startup",
  "body": "## Description\nThe application crashes when...\n\n## Steps to Reproduce\n1. Launch app\n2. Click...",
  "labels": ["bug", "priority-high"],
  "assignees": ["developer1"]
}
```

#### `get_issue`

Retrieves details of a specific issue.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number

**Outputs:**
- `issue` (object): Issue details
- `result` (boolean): Operation success status

#### `list_issues`

Lists issues in a repository with powerful filtering options.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `state` (string, optional): "open", "closed", or "all" (default: "open")
- `labels` (string, optional): Comma-separated label names
- `sort` (string, optional): "created", "updated", or "comments" (default: "created")
- `per_page` (integer, optional): Results per page, 1-100 (default: 30)

**Outputs:**
- `issues` (array): List of issue objects
- `result` (boolean): Operation success status

#### `update_issue`

Updates an existing issue.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number
- `title` (string, optional): Updated title
- `body` (string, optional): Updated description
- `state` (string, optional): "open" or "closed"
- `labels` (array, optional): Updated label array

**Outputs:**
- `issue` (object): Updated issue details
- `result` (boolean): Operation success status

#### `create_issue_comment`

Adds a comment to an issue.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `issue_number` (integer, required): Issue number
- `body` (string, required): Comment text (supports markdown)

**Outputs:**
- `comment` (object): Created comment details
- `result` (boolean): Operation success status

---

### Pull Request Actions

#### `create_pull_request`

Creates a new pull request.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `title` (string, required): Pull request title
- `body` (string, optional): Pull request description (supports markdown)
- `head` (string, required): Branch to merge from (e.g., 'username:feature-branch')
- `base` (string, required): Branch to merge into (e.g., 'main' or 'master')
- `draft` (boolean, optional): Create as draft PR (default: false)

**Outputs:**
- `pull_request` (object): Created pull request details
- `result` (boolean): Operation success status

**Example:**
```json
{
  "owner": "myusername",
  "repo": "my-project",
  "title": "Add new authentication feature",
  "body": "## Changes\n- Implemented OAuth2\n- Added tests\n\n## Testing\nTested on...",
  "head": "myusername:feature/oauth",
  "base": "main",
  "draft": false
}
```

#### `get_pull_request`

Retrieves details of a specific pull request.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number

**Outputs:**
- `pull_request` (object): Pull request details
- `result` (boolean): Operation success status

#### `list_pull_requests`

Lists pull requests in a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `state` (string, optional): "open", "closed", or "all" (default: "open")
- `sort` (string, optional): "created", "updated", "popularity", "long-running" (default: "created")
- `per_page` (integer, optional): Results per page, 1-100 (default: 30)

**Outputs:**
- `pull_requests` (array): List of pull request objects
- `result` (boolean): Operation success status

#### `merge_pull_request`

Merges a pull request.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `pull_number` (integer, required): Pull request number
- `commit_title` (string, optional): Merge commit title
- `commit_message` (string, optional): Merge commit message
- `merge_method` (string, optional): "merge", "squash", or "rebase" (default: "merge")

**Outputs:**
- `merge_result` (object): Merge operation result
- `result` (boolean): Operation success status

---

### Commit Actions

#### `get_commit`

Retrieves details of a specific commit.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `sha` (string, required): Commit SHA

**Outputs:**
- `commit` (object): Commit details including files changed, stats, etc.
- `result` (boolean): Operation success status

#### `list_commits`

Lists commits in a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `sha` (string, optional): Branch, tag, or SHA to start from
- `path` (string, optional): Filter by file path
- `per_page` (integer, optional): Results per page, 1-100 (default: 30)

**Outputs:**
- `commits` (array): List of commit objects
- `result` (boolean): Operation success status

---

### Branch Actions

#### `get_branch`

Retrieves details of a specific branch.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Branch name

**Outputs:**
- `branch` (object): Branch details including protection status
- `result` (boolean): Operation success status

#### `list_branches`

Lists all branches in a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `per_page` (integer, optional): Results per page, 1-100 (default: 30)

**Outputs:**
- `branches` (array): List of branch objects
- `result` (boolean): Operation success status

#### `create_branch`

Creates a new branch from a commit SHA.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): New branch name
- `sha` (string, required): Commit SHA to branch from

**Outputs:**
- `ref` (object): Created branch reference details
- `result` (boolean): Operation success status

#### `delete_branch`

Deletes a branch from the repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `branch` (string, required): Branch name to delete

**Outputs:**
- `result` (boolean): Operation success status

#### `diff_branch_to_branch`

Compare two branches to see commits and file changes.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `base_branch` (string, required): Base branch (e.g., 'main')
- `head_branch` (string, required): Head branch (e.g., 'feature-branch')

**Outputs:**
- `status` (string): Comparison status (e.g., 'ahead', 'diverged')
- `ahead_by` (integer): Number of commits ahead
- `behind_by` (integer): Number of commits behind
- `total_commits` (integer): Total distinct commits
- `commits` (array): List of commit objects
- `files` (array): List of changed files with stats

---

### Webhook Actions

#### `create_webhook`

Creates a new webhook for a repository to receive real-time events.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `url` (string, required): Webhook URL to receive POST requests
- `events` (array, required): Events to trigger webhook (e.g., ['push', 'pull_request', 'issues'])
- `content_type` (string, optional): "json" or "form" (default: "json")
- `secret` (string, optional): Secret for webhook signature validation

**Outputs:**
- `webhook` (object): Created webhook details
- `result` (boolean): Operation success status

**Example:**
```json
{
  "owner": "myusername",
  "repo": "my-project",
  "url": "https://myapp.com/webhooks/github",
  "events": ["push", "pull_request", "issues", "issue_comment"],
  "content_type": "json",
  "secret": "my-webhook-secret"
}
```

**Common Webhook Events:**
- `push` - Git push to a repository
- `pull_request` - Pull request opened, closed, or synchronized
- `issues` - Issue opened, edited, deleted, etc.
- `issue_comment` - Comment added to an issue or PR
- `create` - Branch or tag created
- `delete` - Branch or tag deleted
- `release` - Release published
- `watch` - Repository starred
- `fork` - Repository forked
- `status` - Commit status updated
- `deployment` - Deployment created
- `deployment_status` - Deployment status updated

#### `list_webhooks`

Lists all webhooks for a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Outputs:**
- `webhooks` (array): List of webhook objects
- `result` (boolean): Operation success status

#### `delete_webhook`

Deletes a webhook from a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `hook_id` (integer, required): Webhook ID

**Outputs:**
- `result` (boolean): Operation success status

---

### File Operation Actions

#### `get_file_content`

Retrieves the content of a file from a repository.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path in repository (e.g., 'src/main.py')
- `ref` (string, optional): Branch, tag, or commit SHA (defaults to default branch)

**Outputs:**
- `content` (string): Decoded file content
- `sha` (string): File SHA for updates
- `result` (boolean): Operation success status

#### `create_file`

Creates a new file in a repository via commit.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path in repository
- `message` (string, required): Commit message
- `content` (string, required): File content (will be base64 encoded automatically)
- `branch` (string, optional): Branch name (defaults to default branch)

**Outputs:**
- `commit` (object): Commit details
- `result` (boolean): Operation success status

**Example:**
```json
{
  "owner": "myusername",
  "repo": "my-project",
  "path": "src/new_feature.py",
  "message": "Add new feature implementation",
  "content": "def new_feature():\n    return 'Hello World'",
  "branch": "main"
}
```

#### `update_file`

Updates an existing file in a repository via commit.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path in repository
- `message` (string, required): Commit message
- `content` (string, required): New file content
- `sha` (string, required): Current file SHA (get from `get_file_content`)
- `branch` (string, optional): Branch name

**Outputs:**
- `commit` (object): Commit details
- `result` (boolean): Operation success status

#### `delete_file`

Deletes a file from a repository via commit.

**Inputs:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name
- `path` (string, required): File path in repository
- `message` (string, required): Commit message
- `sha` (string, required): Current file SHA
- `branch` (string, optional): Branch name

**Outputs:**
- `commit` (object): Commit details
- `result` (boolean): Operation success status

---

### Gist Actions

#### `create_gist`

Creates a new gist (code snippet).

**Inputs:**
- `description` (string, optional): Gist description
- `public` (boolean, optional): Whether gist is public (default: true)
- `files` (object, required): Files object with filename as key and content object as value

**Outputs:**
- `gist` (object): Created gist details including url
- `result` (boolean): Operation success status

**Example:**
```json
{
  "description": "Example Python script",
  "public": true,
  "files": {
    "example.py": {
      "content": "print('Hello, World!')"
    },
    "README.md": {
      "content": "# Example\nThis is a sample script."
    }
  }
}
```

---

### Utility Actions

#### `get_rate_limit`

Retrieves current rate limit information for the authenticated user.

**Inputs:** None

**Outputs:**
- `rate_limit` (object): Rate limit details including remaining requests, reset time, etc.
- `result` (boolean): Operation success status

**Rate Limit Information:**
- Authenticated requests: 5,000 requests per hour
- Search API: 30 requests per minute
- The response includes:
  - `limit`: Maximum requests per hour
  - `remaining`: Remaining requests in current window
  - `reset`: Unix timestamp when limit resets
  - `used`: Number of requests used

---

## Requirements

- `autohive-integrations-sdk`

## API Version

This integration uses GitHub REST API version `2022-11-28`.

## Rate Limiting

GitHub enforces rate limits to ensure API stability:

- **Authenticated requests**: 5,000 requests per hour
- **Search API**: 30 requests per minute (authenticated)
- **Unauthenticated requests**: 60 requests per hour (not applicable with OAuth)

The integration includes built-in rate limit monitoring. Use the `get_rate_limit` action to check your current usage.

## Error Handling

All actions include comprehensive error handling and return:
- `result`: Boolean indicating success/failure
- `error`: Detailed error message if operation failed

Common error scenarios:
- **401 Unauthorized**: Invalid or expired OAuth token
- **403 Forbidden**: Insufficient permissions or rate limit exceeded
- **404 Not Found**: Repository, issue, or resource not found
- **422 Unprocessable Entity**: Validation error in request data

## Usage Examples

### Example 1: Automated Issue Creation from Form Submission

```json
{
  "action": "create_issue",
  "inputs": {
    "owner": "myorg",
    "repo": "customer-feedback",
    "title": "Customer Feedback: {{form.subject}}",
    "body": "**Customer:** {{form.name}}\n**Email:** {{form.email}}\n\n{{form.feedback}}",
    "labels": ["customer-feedback", "needs-triage"]
  }
}
```

### Example 2: Automated PR Workflow

```json
[
  {
    "action": "create_pull_request",
    "inputs": {
      "owner": "myorg",
      "repo": "main-app",
      "title": "Feature: {{feature_name}}",
      "body": "## Changes\n{{changes_description}}\n\n## Testing\n{{test_results}}",
      "head": "feature/{{feature_branch}}",
      "base": "develop"
    }
  },
  {
    "action": "create_issue_comment",
    "inputs": {
      "owner": "myorg",
      "repo": "main-app",
      "issue_number": "{{previous_step.pull_request.number}}",
      "body": "Automated tests passed! Ready for review. cc @reviewers"
    }
  }
]
```

### Example 3: Repository Backup Workflow

```json
{
  "action": "create_webhook",
  "inputs": {
    "owner": "myorg",
    "repo": "production-app",
    "url": "https://backup-service.myorg.com/github-webhook",
    "events": ["push", "release"],
    "secret": "{{env.WEBHOOK_SECRET}}"
  }
}
```

### Example 4: File Management via API

```json
[
  {
    "action": "get_file_content",
    "inputs": {
      "owner": "myorg",
      "repo": "config-repo",
      "path": "config/production.json"
    }
  },
  {
    "action": "update_file",
    "inputs": {
      "owner": "myorg",
      "repo": "config-repo",
      "path": "config/production.json",
      "message": "Update production config",
      "content": "{{updated_config}}",
      "sha": "{{previous_step.sha}}"
    }
  }
]
```

## Best Practices

1. **Use Specific Scopes**: Only request OAuth scopes you actually need
2. **Monitor Rate Limits**: Check rate limits periodically, especially for high-volume workflows
3. **Handle Errors Gracefully**: Always check the `result` field and handle errors appropriately
4. **Use Webhooks**: For real-time updates, use webhooks instead of polling
5. **Validate File SHAs**: Always use the correct SHA when updating or deleting files
6. **Secure Webhook Secrets**: Store webhook secrets securely and validate signatures
7. **Branch Protection**: Use branch protection rules to prevent accidental deletions
8. **Test in Development**: Test workflows in development repositories before production

## Security Considerations

- OAuth tokens are stored securely by Autohive platform
- Never expose webhook secrets in logs or error messages
- Use HTTPS for all webhook URLs
- Validate webhook signatures on your endpoint
- Regularly rotate OAuth tokens if possible
- Review granted scopes periodically

## Troubleshooting

### Common Issues

**Issue: 401 Unauthorized**
- Solution: Re-authenticate the integration in Autohive

**Issue: 404 Not Found**
- Solution: Verify repository owner, name, and resource identifiers are correct

**Issue: 422 Validation Failed**
- Solution: Check input parameters match the required format and constraints

**Issue: 409 Conflict (when creating files)**
- Solution: File already exists, use `update_file` instead or check path

**Issue: Rate limit exceeded**
- Solution: Use `get_rate_limit` to check status, wait for reset, or optimize requests

## Support

For integration issues or questions:
- Check the [GitHub API Documentation](https://docs.github.com/en/rest)
- Review this README for action details
- Contact Autohive support for platform-related issues

## Version History

- **1.0.0** (Initial Release)
  - Complete GitHub REST API integration
  - OAuth2 platform authentication
  - 30+ actions covering repositories, issues, PRs, commits, branches, webhooks, files, and gists
  - Built-in rate limit handling
  - Comprehensive error handling

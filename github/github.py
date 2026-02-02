"""
GitHub Integration for Autohive Platform

This module provides comprehensive GitHub API integration including:
- Repository management (CRUD operations)
- Issues and Pull Requests
- Branches, Tags, and Releases
- Workflows and Actions
- File operations and Gists

Author: Tamil
GitHub API Version: 2022-11-28
Reference: https://docs.github.com/en/rest
"""

from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ConnectedAccountHandler, ConnectedAccountInfo
from typing import Dict, Any, List, Callable, TypeVar
from urllib.parse import quote
from functools import wraps
import base64
import os

# Load integration using config.json in the same directory as this file
_config_path = os.path.join(os.path.dirname(__file__), 'config.json')
github = Integration.load(_config_path)

T = TypeVar('T')


# =============================================================================
# ERROR HANDLING
# Author: Tamil
# =============================================================================

class GitHubAPIError(Exception):
    """
    Custom exception for GitHub API errors.
    
    Attributes:
        message: Human-readable error description
        status_code: HTTP status code from GitHub API
        response_data: Raw response data from the API
    """
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}


def handle_github_errors(action_name: str):
    """
    Decorator that wraps action execute methods with error handling.
    
    Catches exceptions and returns ActionResult.failure() with proper error messages.
    Handles common GitHub API error codes (401, 403, 404, 422) with user-friendly messages.
    
    Args:
        action_name: Name of the action for error context
        
    Returns:
        Decorated async function with error handling
        
    Author: Tamil
    Reference: https://docs.github.com/en/rest/overview/troubleshooting
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
            try:
                # Validate token is present
                credentials = context.auth.get("credentials", {})
                token = credentials.get("access_token")
                if not token:
                    return ActionResult.failure(
                        error="GitHub authentication failed: No access token found. Please reconnect your GitHub account."
                    )
                
                return await func(self, inputs, context)
                
            except GitHubAPIError as e:
                error_msg = e.message
                if e.status_code == 401:
                    error_msg = "GitHub authentication failed: Invalid or expired token. Please reconnect your GitHub account."
                elif e.status_code == 403:
                    error_msg = f"GitHub access denied: {e.message}. Check your token permissions."
                elif e.status_code == 404:
                    error_msg = f"GitHub resource not found: {e.message}"
                elif e.status_code == 422:
                    error_msg = f"GitHub validation error: {e.message}"
                
                return ActionResult.failure(error=error_msg)
                
            except Exception as e:
                error_message = str(e)
                
                # Parse common HTTP error patterns
                if "401" in error_message:
                    return ActionResult.failure(
                        error="GitHub authentication failed: Invalid or expired token. Please reconnect your GitHub account."
                    )
                elif "403" in error_message:
                    return ActionResult.failure(
                        error=f"GitHub access denied: {error_message}. Check your token permissions or rate limits."
                    )
                elif "404" in error_message:
                    return ActionResult.failure(
                        error=f"GitHub resource not found: The requested {action_name} resource does not exist."
                    )
                elif "422" in error_message:
                    return ActionResult.failure(
                        error=f"GitHub validation error: {error_message}"
                    )
                
                return ActionResult.failure(
                    error=f"GitHub API error in {action_name}: {error_message}"
                )
        
        return wrapper
    return decorator


class GitHubAPI:
    """Helper class for GitHub API operations with comprehensive functionality"""
    BASE_URL = "https://api.github.com"

    @staticmethod
    def get_headers(context: ExecutionContext) -> Dict[str, str]:
        """
        Build authentication headers for GitHub API requests.
        GitHub uses Bearer token authentication with OAuth2 tokens.
        """
        credentials = context.auth.get("credentials", {})
        token = credentials.get("access_token", "")

        return {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json"
}

    @staticmethod
    async def paginated_fetch(context: ExecutionContext, url: str, params: Dict[str, Any] = None,
                              data_key: str = None) -> List[Dict[str, Any]]:
        """
        Generic paginated fetch that handles GitHub's pagination automatically.

        Args:
            context: ExecutionContext
            url: API endpoint URL
            params: Query parameters
            data_key: Key to extract from response (e.g., 'workflows', 'workflow_runs')
        """
        if params is None:
            params = {}

        params.setdefault('per_page', 100)
        params.setdefault('page', 1)

        all_items = []
        headers = GitHubAPI.get_headers(context)
        while True:
            response = await context.fetch(url, params=params, headers=headers)

            # Extract items from response
            if data_key and isinstance(response, dict):
                items = response.get(data_key, [])
            elif isinstance(response, list):
                items = response
            else:
                items = [response] if response else []

            if not items:
                break

            all_items.extend(items)

            # Check if we got less than per_page items, meaning this is the last page
            if len(items) < params['per_page']:
                break

            params['page'] += 1

        return all_items

    # ---- Repository Operations ----

    @staticmethod
    async def create_repository(context: ExecutionContext, name: str, description: str = None,
                               private: bool = False, auto_init: bool = False,
                               gitignore_template: str = None, license_template: str = None,
                               org: str = None, homepage: str = None, has_issues: bool = True,
                               has_projects: bool = True, has_wiki: bool = True) -> Dict[str, Any]:
        """Create a new repository"""
        if org:
            url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        data = {
            'name': name,
            'private': private,
            'auto_init': auto_init,
            'has_issues': has_issues,
            'has_projects': has_projects,
            'has_wiki': has_wiki
        }

        if description:
            data['description'] = description
        if homepage:
            data['homepage'] = homepage
        if gitignore_template:
            data['gitignore_template'] = gitignore_template
        if license_template:
            data['license_template'] = license_template

        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_repository(context: ExecutionContext, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository details"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def list_repositories(context: ExecutionContext, username: str = None, org: str = None,
                               type: str = 'all', sort: str = 'updated',
                               direction: str = 'desc') -> List[Dict[str, Any]]:
        """List repositories for user or organization"""
        if org:
            url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        elif username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        params = {'type': type, 'sort': sort, 'direction': direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def list_user_repositories(context: ExecutionContext, username: str = None,
                                     type: str = 'all', sort: str = 'updated',
                                     direction: str = 'desc') -> List[Dict[str, Any]]:
        """List repositories for a specific user or authenticated user"""
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/repos"
        else:
            url = f"{GitHubAPI.BASE_URL}/user/repos"

        params = {'type': type, 'sort': sort, 'direction': direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def list_organization_repositories(context: ExecutionContext, org: str,
                                             type: str = 'all', sort: str = 'updated',
                                             direction: str = 'desc') -> List[Dict[str, Any]]:
        """List repositories for a specific organization"""
        url = f"{GitHubAPI.BASE_URL}/orgs/{org}/repos"
        params = {'type': type, 'sort': sort, 'direction': direction}
        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def update_repository(context: ExecutionContext, owner: str, repo: str,
                               **kwargs) -> Dict[str, Any]:
        """Update repository settings"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        data = {k: v for k, v in kwargs.items() if v is not None}
        return await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def delete_repository(context: ExecutionContext, owner: str, repo: str) -> None:
        """Delete a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    # ---- Commit Operations ----

    @staticmethod
    async def get_commits(context: ExecutionContext, owner: str, repo: str,
                         sha: str = None, path: str = None, since: str = None,
                         until: str = None) -> List[Dict[str, Any]]:
        """Get commits for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {}

        if sha:
            params['sha'] = sha
        if path:
            params['path'] = path
        if since:
            params['since'] = since
        if until:
            params['until'] = until

        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def get_commit(context: ExecutionContext, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Get a specific commit"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/commits/{sha}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def compare_branches(context: ExecutionContext, owner: str, repo: str,
                              base: str, head: str) -> Dict[str, Any]:
        """Compare two branches"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/compare/{base}...{head}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    # ---- Issue Operations ----

    @staticmethod
    async def get_issues(context: ExecutionContext, owner: str, repo: str,
                        state: str = 'all', sort: str = 'created',
                        direction: str = 'desc', since: str = None,
                        labels: str = None) -> List[Dict[str, Any]]:
        """Get issues for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {'state': state, 'sort': sort, 'direction': direction}

        if since:
            params['since'] = since
        if labels:
            params['labels'] = labels

        return await GitHubAPI.paginated_fetch(context, url, params)

    @staticmethod
    async def get_issue(context: ExecutionContext, owner: str, repo: str,
                       issue_number: int) -> Dict[str, Any]:
        """Get a specific issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def create_issue(context: ExecutionContext, owner: str, repo: str, title: str,
                          body: str = None, assignees: List[str] = None,
                          labels: List[str] = None, milestone: int = None) -> Dict[str, Any]:
        """Create a new issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues"
        data = {'title': title}

        if body:
            data['body'] = body
        if assignees:
            data['assignees'] = assignees
        if labels:
            data['labels'] = labels
        if milestone:
            data['milestone'] = milestone

        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def update_issue(context: ExecutionContext, owner: str, repo: str,
                          issue_number: int, title: str = None, body: str = None,
                          state: str = None, assignees: List[str] = None,
                          labels: List[str] = None, milestone: int = None) -> Dict[str, Any]:
        """Update an existing issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        data = {}

        if title:
            data['title'] = title
        if body:
            data['body'] = body
        if state:
            data['state'] = state
        if assignees:
            data['assignees'] = assignees
        if labels:
            data['labels'] = labels
        if milestone is not None:
            data['milestone'] = milestone

        return await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_issue_comments(context: ExecutionContext, owner: str, repo: str,
                                issue_number: int) -> List[Dict[str, Any]]:
        """Get comments for an issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def create_issue_comment(context: ExecutionContext, owner: str, repo: str,
                                   issue_number: int, body: str) -> Dict[str, Any]:
        """Create a comment on an issue"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = {'body': body}
        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    # ---- Pull Request Operations ----

    @staticmethod
    async def get_pull_requests(context: ExecutionContext, owner: str, repo: str,
                               state: str = 'all', sort: str = 'updated',
                               direction: str = 'desc', after: str = None,
                               before: str = None, author: str = None,
                               limit: int = None) -> List[Dict[str, Any]]:
        """Get pull requests for a repository using GitHub Search API"""
        url = f"{GitHubAPI.BASE_URL}/search/issues"
        
        q_parts = [f"is:pr repo:{owner}/{repo}"]
        if state == 'open':
            q_parts.append("is:open")
        elif state == 'closed':
            q_parts.append("is:closed")
        if author:
            q_parts.append(f"author:{author}")
        if after:
            q_parts.append(f"created:>={after}")
        if before:
            q_parts.append(f"created:<={before}")

        sort_map = {'updated': 'updated', 'created': 'created', 'popularity': 'comments', 'long-running': 'created'}
        params = {
            'q': ' '.join(q_parts),
            'sort': sort_map.get(sort, 'updated'),
            'order': direction,
            'per_page': min(limit, 100) if limit else 100,
            'page': 1,
        }

        headers = GitHubAPI.get_headers(context)
        all_prs: List[Dict[str, Any]] = []

        while True:
            response = await context.fetch(url, params=params, headers=headers)
            items = response.get('items', [])
            if not items:
                break

            all_prs.extend(items)

            if limit and len(all_prs) >= limit:
                return all_prs[:limit]

            if len(items) < params['per_page']:
                break

            params['page'] += 1

        return all_prs

    @staticmethod
    async def get_pull_request(context: ExecutionContext, owner: str, repo: str,
                              pull_number: int) -> Dict[str, Any]:
        """Get detailed information about a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def create_pull_request(context: ExecutionContext, owner: str, repo: str,
                                 title: str, head: str, base: str, body: str = None,
                                 draft: bool = False,
                                 maintainer_can_modify: bool = True) -> Dict[str, Any]:
        """Create a new pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls"
        data = {
            'title': title,
            'head': head,
            'base': base,
            'draft': draft,
            'maintainer_can_modify': maintainer_can_modify
        }

        if body:
            data['body'] = body

        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def update_pull_request(context: ExecutionContext, owner: str, repo: str,
                                 pull_number: int, **kwargs) -> Dict[str, Any]:
        """Update a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
        data = {k: v for k, v in kwargs.items() if v is not None}
        return await context.fetch(url, method="PATCH", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def merge_pull_request(context: ExecutionContext, owner: str, repo: str,
                                pull_number: int, commit_title: str = None,
                                commit_message: str = None,
                                merge_method: str = 'merge') -> Dict[str, Any]:
        """Merge a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/merge"
        data = {'merge_method': merge_method}

        if commit_title:
            data['commit_title'] = commit_title
        if commit_message:
            data['commit_message'] = commit_message

        return await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def add_pull_request_reviewers(context: ExecutionContext, owner: str, repo: str,
                                        pull_number: int, reviewers: List[str] = None,
                                        team_reviewers: List[str] = None) -> Dict[str, Any]:
        """Request reviewers for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        data = {}

        if reviewers:
            data['reviewers'] = reviewers
        if team_reviewers:
            data['team_reviewers'] = team_reviewers

        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def remove_pull_request_reviewers(context: ExecutionContext, owner: str, repo: str,
                                           pull_number: int, reviewers: List[str] = None,
                                           team_reviewers: List[str] = None) -> Dict[str, Any]:
        """Remove reviewers from a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        data = {}

        if reviewers:
            data['reviewers'] = reviewers
        if team_reviewers:
            data['team_reviewers'] = team_reviewers

        return await context.fetch(url, method="DELETE", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def list_pull_request_reviewers(context: ExecutionContext, owner: str, repo: str,
                                         pull_number: int) -> Dict[str, Any]:
        """List reviewers for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def create_pull_request_review(context: ExecutionContext, owner: str, repo: str,
                                        pull_number: int, body: str = None,
                                        event: str = None,
                                        comments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a review for a pull request"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        data = {}

        if body:
            data['body'] = body
        if event:
            data['event'] = event
        if comments:
            data['comments'] = comments

        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    # ---- Branch Operations ----

    @staticmethod
    async def list_branches(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List branches for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def get_branch(context: ExecutionContext, owner: str, repo: str,
                        branch: str) -> Dict[str, Any]:
        """Get branch details"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches/{branch}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def create_branch(context: ExecutionContext, owner: str, repo: str,
                          branch_name: str, sha: str) -> Dict[str, Any]:
        """Create a new branch"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/refs"
        data = {
            'ref': f'refs/heads/{branch_name}',
            'sha': sha
        }
        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def delete_branch(context: ExecutionContext, owner: str, repo: str,
                          branch: str) -> None:
        """Delete a branch"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_branch_protection(context: ExecutionContext, owner: str, repo: str,
                                   branch: str) -> Dict[str, Any]:
        """Get branch protection rules"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/branches/{branch}/protection"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    # ---- Webhook Operations ----

    @staticmethod
    async def create_webhook(context: ExecutionContext, owner: str, repo: str,
                           url: str, events: List[str], content_type: str = 'json',
                           secret: str = None, active: bool = True) -> Dict[str, Any]:
        """Create a webhook"""
        webhook_url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks"

        config = {
            'url': url,
            'content_type': content_type
        }

        if secret:
            config['secret'] = secret

        data = {
            'name': 'web',
            'active': active,
            'events': events,
            'config': config
        }

        return await context.fetch(webhook_url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def list_webhooks(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List webhooks for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks"
        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def get_webhook(context: ExecutionContext, owner: str, repo: str,
                         hook_id: int) -> Dict[str, Any]:
        """Get webhook details"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks/{hook_id}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def delete_webhook(context: ExecutionContext, owner: str, repo: str,
                           hook_id: int) -> None:
        """Delete a webhook"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/hooks/{hook_id}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    # ---- File Operations ----

    @staticmethod
    async def get_file_content(context: ExecutionContext, owner: str, repo: str,
                              path: str, ref: str = None) -> Dict[str, Any]:
        """Get file content from repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"
        params = {}

        if ref:
            params['ref'] = ref

        response = await context.fetch(url, params=params if params else None, headers=GitHubAPI.get_headers(context))

        # Decode base64 content
        content = base64.b64decode(response.get('content', '').replace('\n', '')).decode('utf-8')

        return {
            'content': content,
            'sha': response.get('sha', ''),
            'size': response.get('size', 0),
            'name': response.get('name', ''),
            'path': response.get('path', '')
        }

    @staticmethod
    async def create_file(context: ExecutionContext, owner: str, repo: str, path: str,
                         message: str, content: str, branch: str = None) -> Dict[str, Any]:
        """Create a new file in repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        # Encode content to base64
        content_bytes = content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')

        data = {
            'message': message,
            'content': content_base64
        }

        if branch:
            data['branch'] = branch

        return await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def update_file(context: ExecutionContext, owner: str, repo: str, path: str,
                         message: str, content: str, sha: str,
                         branch: str = None) -> Dict[str, Any]:
        """Update an existing file in repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        # Encode content to base64
        content_bytes = content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')

        data = {
            'message': message,
            'content': content_base64,
            'sha': sha
        }

        if branch:
            data['branch'] = branch

        return await context.fetch(url, method="PUT", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def delete_file(context: ExecutionContext, owner: str, repo: str, path: str,
                         message: str, sha: str, branch: str = None) -> Dict[str, Any]:
        """Delete a file from repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/contents/{path}"

        data = {
            'message': message,
            'sha': sha
        }

        if branch:
            data['branch'] = branch

        return await context.fetch(url, method="DELETE", json=data, headers=GitHubAPI.get_headers(context))

    # ---- Gist Operations ----

    @staticmethod
    async def create_gist(context: ExecutionContext, description: str, files: Dict[str, Any],
                         public: bool = True) -> Dict[str, Any]:
        """Create a gist"""
        url = f"{GitHubAPI.BASE_URL}/gists"
        data = {
            'description': description,
            'public': public,
            'files': files
        }
        return await context.fetch(url, method="POST", json=data, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_gist(context: ExecutionContext, gist_id: str) -> Dict[str, Any]:
        """Get gist details"""
        url = f"{GitHubAPI.BASE_URL}/gists/{gist_id}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def list_gists(context: ExecutionContext, username: str = None) -> List[Dict[str, Any]]:
        """List gists"""
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}/gists"
        else:
            url = f"{GitHubAPI.BASE_URL}/gists"

        return await GitHubAPI.paginated_fetch(context, url)

    @staticmethod
    async def delete_gist(context: ExecutionContext, gist_id: str) -> None:
        """Delete a gist"""
        url = f"{GitHubAPI.BASE_URL}/gists/{gist_id}"
        await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))

    # ---- User Operations ----

    @staticmethod
    async def get_user(context: ExecutionContext, username: str = None) -> Dict[str, Any]:
        """Get user information"""
        if username:
            url = f"{GitHubAPI.BASE_URL}/users/{username}"
        else:
            url = f"{GitHubAPI.BASE_URL}/user"

        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    # ---- Organization Operations ----

    @staticmethod
    async def list_organization_members(context: ExecutionContext, org: str,
                                       role: str = 'all') -> List[Dict[str, Any]]:
        """List organization members"""
        url = f"{GitHubAPI.BASE_URL}/orgs/{org}/members"
        params = {'role': role}
        return await GitHubAPI.paginated_fetch(context, url, params)

    # ---- GitHub Actions/Workflows ----

    @staticmethod
    async def list_workflows(context: ExecutionContext, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List workflows for a repository"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
        return await GitHubAPI.paginated_fetch(context, url, params={}, data_key='workflows')

    @staticmethod
    async def get_workflow_runs(context: ExecutionContext, owner: str, repo: str,
                               workflow_id: str, status: str = None,
                               branch: str = None) -> List[Dict[str, Any]]:
        """Get workflow runs"""
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        params = {}

        if status:
            params['status'] = status
        if branch:
            params['branch'] = branch

        return await GitHubAPI.paginated_fetch(context, url, params, 'workflow_runs')

    # -------------------------------------------------------------------------
    # Tag Operations
    # Author: Tamil
    # Reference: https://docs.github.com/en/rest/repos/repos#list-repository-tags
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_tags(context: ExecutionContext, owner: str, repo: str,
                       per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        """
        List tags for a repository (single page fetch).
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            per_page: Number of results per page (max 100)
            page: Page number to fetch
            
        Returns:
            List of tag objects with name, commit SHA, and download URLs
            
        Author: Tamil
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/tags"
        params = {'per_page': per_page, 'page': page}
        return await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))

    # -------------------------------------------------------------------------
    # Release Operations
    # Author: Tamil
    # Reference: https://docs.github.com/en/rest/releases/releases
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_releases(context: ExecutionContext, owner: str, repo: str,
                           per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        """
        List releases for a repository (single page fetch).
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            per_page: Number of results per page (max 100)
            page: Page number to fetch
            
        Returns:
            List of release objects (does not include regular Git tags)
            
        Author: Tamil
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases"
        params = {'per_page': per_page, 'page': page}
        return await context.fetch(url, params=params, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_release(context: ExecutionContext, owner: str, repo: str,
                         release_id: int) -> Dict[str, Any]:
        """
        Get a specific release by ID.
        
        Args:
            owner: Repository owner
            repo: Repository name
            release_id: The unique identifier of the release
            
        Returns:
            Release object with full details including assets
            
        Author: Tamil
        Reference: https://docs.github.com/en/rest/releases/releases#get-a-release
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/{release_id}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_latest_release(context: ExecutionContext, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get the latest published release for a repository.
        
        The latest release is the most recent non-prerelease, non-draft release.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Latest release object
            
        Author: Tamil
        Reference: https://docs.github.com/en/rest/releases/releases#get-the-latest-release
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/latest"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    @staticmethod
    async def get_release_by_tag(context: ExecutionContext, owner: str, repo: str,
                                tag: str) -> Dict[str, Any]:
        """
        Get a release by tag name.
        
        Note: Tag is URL-encoded to handle special characters like '/' or spaces.
        
        Args:
            owner: Repository owner
            repo: Repository name
            tag: Tag name (e.g., 'v1.0.0', 'release/2024-01')
            
        Returns:
            Release object matching the tag
            
        Author: Tamil
        Reference: https://docs.github.com/en/rest/releases/releases#get-a-release-by-tag-name
        """
        encoded_tag = quote(tag, safe='')
        url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/releases/tags/{encoded_tag}"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))

    # ---- Rate Limiting ----

    @staticmethod
    async def get_rate_limit(context: ExecutionContext) -> Dict[str, Any]:
        """Get current rate limit status"""
        url = f"{GitHubAPI.BASE_URL}/rate_limit"
        return await context.fetch(url, headers=GitHubAPI.get_headers(context))


# ============================================================================
# ACTION HANDLERS
# ============================================================================

# Note: All actions return data directly (dict or list) as GitHub API is free
# If you implement rate-limit-aware caching or premium features, update costs accordingly

# ---- Repository Actions ----

@github.action("create_repository")
class CreateRepository(ActionHandler):
    """Create a new repository"""

    @handle_github_errors("create_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repo = await GitHubAPI.create_repository(
            context,
            name=inputs['name'],
            description=inputs.get('description'),
            private=inputs.get('private', False),
            auto_init=inputs.get('auto_init', False),
            gitignore_template=inputs.get('gitignore_template'),
            license_template=inputs.get('license_template'),
            org=inputs.get('org'),
            homepage=inputs.get('homepage'),
            has_issues=inputs.get('has_issues', True),
            has_projects=inputs.get('has_projects', True),
            has_wiki=inputs.get('has_wiki', True)
        )

        return ActionResult(
            data={
                'id': repo['id'],
                'name': repo['name'],
                'full_name': repo['full_name'],
                'description': repo['description'],
                'private': repo['private'],
                'default_branch': repo['default_branch'],
                'created_at': repo['created_at'],
                'updated_at': repo['updated_at'],
                'pushed_at': repo['pushed_at'],
                'clone_url': repo['clone_url'],
                'ssh_url': repo['ssh_url'],
                'html_url': repo['html_url']
            },
            cost_usd=0.0
        )


@github.action("get_repository")
class GetRepository(ActionHandler):
    """Get repository details"""

    @handle_github_errors("get_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repo_data = await GitHubAPI.get_repository(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data={
            'name': repo_data['name'],
            'full_name': repo_data['full_name'],
            'description': repo_data.get('description'),
            'default_branch': repo_data['default_branch'],
            'created_at': repo_data['created_at'],
            'updated_at': repo_data['updated_at'],
            'pushed_at': repo_data['pushed_at'],
            'language': repo_data.get('language'),
            'visibility': repo_data['visibility'],
            'private': repo_data['private'],
            'fork': repo_data['fork'],
            'forks_count': repo_data['forks_count'],
            'stargazers_count': repo_data['stargazers_count'],
            'watchers_count': repo_data['watchers_count'],
            'open_issues_count': repo_data['open_issues_count'],
            'url': repo_data['html_url']
        },
            cost_usd=0.0
        )


@github.action("list_repositories")
class ListRepositories(ActionHandler):
    """List repositories"""

    @handle_github_errors("list_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_repositories(
            context,
            username=inputs.get('username'),
            org=inputs.get('org'),
            type=inputs.get('type', 'all'),
            sort=inputs.get('sort', 'updated'),
            direction=inputs.get('direction', 'desc')
        )

        return ActionResult(
            data=[{
            'id': repo['id'],
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo['description'],
            'private': repo['private'],
            'fork': repo['fork'],
            'created_at': repo['created_at'],
            'updated_at': repo['updated_at'],
            'pushed_at': repo['pushed_at'],
            'language': repo.get('language'),
            'default_branch': repo['default_branch'],
            'visibility': repo.get('visibility'),
            'url': repo['html_url']
        } for repo in repos],
            cost_usd=0.0
        )


@github.action("update_repository")
class UpdateRepository(ActionHandler):
    """Update repository settings"""

    @handle_github_errors("update_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        update_data = {
            'name': inputs.get('name'),
            'description': inputs.get('description'),
            'private': inputs.get('private'),
            'has_issues': inputs.get('has_issues'),
            'has_wiki': inputs.get('has_wiki')
        }

        repo = await GitHubAPI.update_repository(
            context,
            inputs['owner'],
            inputs['repo'],
            **update_data
        )

        return ActionResult(
            data={
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo['description'],
            'private': repo['private'],
            'has_issues': repo['has_issues'],
            'has_wiki': repo['has_wiki'],
            'updated_at': repo['updated_at'],
            'url': repo['html_url']
        },
            cost_usd=0.0
        )


@github.action("delete_repository")
class DeleteRepository(ActionHandler):
    """Delete a repository"""

    @handle_github_errors("delete_repository")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_repository(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data={
            'deleted': True,
            'repository': f"{inputs['owner']}/{inputs['repo']}"
        },
            cost_usd=0.0
        )


# ---- Commit Actions ----

@github.action("list_commits")
class ListCommits(ActionHandler):
    """List commits for a repository"""

    @handle_github_errors("list_commits")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        commits = await GitHubAPI.get_commits(
            context,
            inputs['owner'],
            inputs['repo'],
            sha=inputs.get('sha'),
            path=inputs.get('path'),
            since=inputs.get('since'),
            until=inputs.get('until')
        )

        return ActionResult(
            data=[{
            'sha': commit['sha'],
            'author': {
                'name': commit['commit']['author']['name'],
                'email': commit['commit']['author']['email'],
                'date': commit['commit']['author']['date']
            },
            'committer': {
                'name': commit['commit']['committer']['name'],
                'email': commit['commit']['committer']['email'],
                'date': commit['commit']['committer']['date']
            },
            'message': commit['commit']['message'],
            'url': commit['html_url']
        } for commit in commits],
            cost_usd=0.0
        )


@github.action("get_commit")
class GetCommit(ActionHandler):
    """Get a specific commit"""

    @handle_github_errors("get_commit")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        commit = await GitHubAPI.get_commit(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['sha']
        )

        return ActionResult(
            data={
            'sha': commit['sha'],
            'author': {
                'name': commit['commit']['author']['name'],
                'email': commit['commit']['author']['email'],
                'date': commit['commit']['author']['date']
            },
            'committer': {
                'name': commit['commit']['committer']['name'],
                'email': commit['commit']['committer']['email'],
                'date': commit['commit']['committer']['date']
            },
            'message': commit['commit']['message'],
            'stats': commit.get('stats', {}),
            'files': commit.get('files', []),
            'url': commit['html_url']
        },
            cost_usd=0.0
        )


# ---- Issue Actions ----

@github.action("list_issues")
class ListIssues(ActionHandler):
    """List issues for a repository"""

    @handle_github_errors("list_issues")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issues = await GitHubAPI.get_issues(
            context,
            inputs['owner'],
            inputs['repo'],
            state=inputs.get('state', 'all'),
            sort=inputs.get('sort', 'created'),
            direction=inputs.get('direction', 'desc'),
            since=inputs.get('since'),
            labels=inputs.get('labels')
        )

        return ActionResult(
            data=[{
            'number': issue['number'],
            'title': issue['title'],
            'description': issue['body'],
            'state': issue['state'],
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'closed_at': issue['closed_at'],
            'author': {
                'login': issue['user']['login'],
                'avatar_url': issue['user']['avatar_url']
            },
            'assignees': [{'login': assignee['login']} for assignee in issue.get('assignees', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in issue.get('labels', [])],
            'url': issue['html_url']
        } for issue in issues],
            cost_usd=0.0
        )


@github.action("get_issue")
class GetIssue(ActionHandler):
    """Get a specific issue"""

    @handle_github_errors("get_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.get_issue(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['issue_number']
        )

        return ActionResult(
            data={
            'number': issue['number'],
            'title': issue['title'],
            'description': issue['body'],
            'state': issue['state'],
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'closed_at': issue['closed_at'],
            'author': {
                'login': issue['user']['login'],
                'avatar_url': issue['user']['avatar_url']
            },
            'assignees': [{'login': assignee['login']} for assignee in issue.get('assignees', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in issue.get('labels', [])],
            'comments': issue.get('comments', 0),
            'url': issue['html_url']
        },
            cost_usd=0.0
        )


@github.action("create_issue")
class CreateIssue(ActionHandler):
    """Create a new issue"""

    @handle_github_errors("create_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.create_issue(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['title'],
            body=inputs.get('body'),
            assignees=inputs.get('assignees'),
            labels=inputs.get('labels'),
            milestone=inputs.get('milestone')
        )

        return ActionResult(
            data={
            'number': issue['number'],
            'title': issue['title'],
            'description': issue['body'],
            'state': issue['state'],
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'author': {
                'login': issue['user']['login'],
                'avatar_url': issue['user']['avatar_url']
            },
            'assignees': [{'login': assignee['login']} for assignee in issue.get('assignees', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in issue.get('labels', [])],
            'url': issue['html_url']
        },
            cost_usd=0.0
        )


@github.action("update_issue")
class UpdateIssue(ActionHandler):
    """Update an existing issue"""

    @handle_github_errors("update_issue")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        issue = await GitHubAPI.update_issue(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['issue_number'],
            title=inputs.get('title'),
            body=inputs.get('body'),
            state=inputs.get('state'),
            assignees=inputs.get('assignees'),
            labels=inputs.get('labels'),
            milestone=inputs.get('milestone')
        )

        return ActionResult(
            data={
            'number': issue['number'],
            'title': issue['title'],
            'description': issue['body'],
            'state': issue['state'],
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'closed_at': issue['closed_at'],
            'author': {
                'login': issue['user']['login'],
                'avatar_url': issue['user']['avatar_url']
            },
            'assignees': [{'login': assignee['login']} for assignee in issue.get('assignees', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in issue.get('labels', [])],
            'url': issue['html_url']
        },
            cost_usd=0.0
        )


@github.action("create_issue_comment")
class CreateIssueComment(ActionHandler):
    """Create a comment on an issue"""

    @handle_github_errors("create_issue_comment")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comment = await GitHubAPI.create_issue_comment(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['issue_number'],
            inputs['body']
        )

        return ActionResult(
            data={
            'id': comment['id'],
            'body': comment['body'],
            'created_at': comment['created_at'],
            'updated_at': comment['updated_at'],
            'author': {
                'login': comment['user']['login'],
                'avatar_url': comment['user']['avatar_url']
            },
            'url': comment['html_url']
        },
            cost_usd=0.0
        )


@github.action("get_issue_comments")
class GetIssueComments(ActionHandler):
    """Get comments for an issue"""

    @handle_github_errors("get_issue_comments")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comments = await GitHubAPI.get_issue_comments(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['issue_number']
        )

        return ActionResult(
            data=[{
            'id': comment['id'],
            'body': comment['body'],
            'created_at': comment['created_at'],
            'updated_at': comment['updated_at'],
            'author': {
                'login': comment['user']['login'],
                'avatar_url': comment['user']['avatar_url']
            },
            'url': comment['html_url']
        } for comment in comments],
            cost_usd=0.0
        )


# ---- Pull Request Actions ----

@github.action("list_pull_requests")
class ListPullRequests(ActionHandler):
    """List pull requests for a repository"""

    @handle_github_errors("list_pull_requests")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        prs = await GitHubAPI.get_pull_requests(
            context,
            inputs['owner'],
            inputs['repo'],
            state=inputs.get('state', 'all'),
            sort=inputs.get('sort', 'updated'),
            direction=inputs.get('direction', 'desc'),
            after=inputs.get('after'),
            before=inputs.get('before'),
            author=inputs.get('author'),
            limit=inputs.get('limit')
        )

        return ActionResult(
            data=[{
            'number': pr['number'],
            'title': pr['title'],
            'description': pr.get('body'),
            'state': pr['state'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'closed_at': pr.get('closed_at'),
            'draft': pr.get('draft', False),
            'author': {
                'login': pr['user']['login'],
                'avatar_url': pr['user']['avatar_url']
            },
            'url': pr['html_url']
        } for pr in prs],
            cost_usd=0.0
        )


@github.action("get_pull_request")
class GetPullRequest(ActionHandler):
    """Get detailed information about a pull request"""

    @handle_github_errors("get_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        pr = await GitHubAPI.get_pull_request(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number']
        )

        return ActionResult(
            data={
            'number': pr['number'],
            'title': pr['title'],
            'description': pr.get('body'),
            'state': pr['state'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'merged_at': pr.get('merged_at'),
            'closed_at': pr.get('closed_at'),
            'draft': pr.get('draft', False),
            'mergeable': pr.get('mergeable'),
            'mergeable_state': pr.get('mergeable_state'),
            'merged': pr.get('merged', False),
            'author': {
                'login': pr['user']['login'],
                'avatar_url': pr['user']['avatar_url']
            },
            'assignees': [{'login': assignee['login']} for assignee in pr.get('assignees', [])],
            'requested_reviewers': [{'login': reviewer['login']} for reviewer in pr.get('requested_reviewers', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in pr.get('labels', [])],
            'head': {
                'ref': pr['head']['ref'],
                'sha': pr['head']['sha'],
                'repo': {
                    'name': pr['head']['repo']['name'],
                    'full_name': pr['head']['repo']['full_name']
                }
            },
            'base': {
                'ref': pr['base']['ref'],
                'sha': pr['base']['sha'],
                'repo': {
                    'name': pr['base']['repo']['name'],
                    'full_name': pr['base']['repo']['full_name']
                }
            },
            'url': pr['html_url']
        },
            cost_usd=0.0
        )


@github.action("create_pull_request")
class CreatePullRequest(ActionHandler):
    """Create a new pull request"""

    @handle_github_errors("create_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        pr = await GitHubAPI.create_pull_request(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['title'],
            inputs['head'],
            inputs['base'],
            body=inputs.get('body'),
            draft=inputs.get('draft', False),
            maintainer_can_modify=inputs.get('maintainer_can_modify', True)
        )

        return ActionResult(
            data={
            'id': pr['id'],
            'node_id': pr['node_id'],
            'number': pr['number'],
            'title': pr['title'],
            'body': pr['body'],
            'state': pr['state'],
            'html_url': pr['html_url'],
            'url': pr.get('url', pr['html_url']),
            'diff_url': pr['diff_url'],
            'patch_url': pr['patch_url'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'closed_at': pr.get('closed_at'),
            'merged_at': pr.get('merged_at'),
            'draft': pr['draft'],
            'merged': pr.get('merged'),
            'mergeable': pr.get('mergeable'),
            'mergeable_state': pr.get('mergeable_state'),
            'merge_commit_sha': pr.get('merge_commit_sha'),
            'user': {
                'avatar_url': pr['user']['avatar_url'],
                'login': pr['user']['login'],
                'id': pr['user']['id']
            },
            'author_association': pr.get('author_association'),
            'assignee': {
                'login': pr['assignee']['login'],
                'id': pr['assignee']['id'],
                'avatar_url': pr['assignee']['avatar_url']
            } if pr.get('assignee') else None,
            'assignees': [{'login': a['login'], 'id': a['id'], 'avatar_url': a['avatar_url']} for a in pr.get('assignees', [])],
            'requested_reviewers': [{'login': r['login'], 'id': r['id'], 'avatar_url': r['avatar_url']} for r in pr.get('requested_reviewers', [])],
            'requested_teams': [{'id': t['id'], 'name': t['name'], 'slug': t['slug']} for t in pr.get('requested_teams', [])],
            'labels': [{'name': label['name'], 'color': label['color']} for label in pr.get('labels', [])],
            'milestone': {
                'id': pr['milestone']['id'],
                'number': pr['milestone']['number'],
                'title': pr['milestone']['title'],
                'state': pr['milestone']['state']
            } if pr.get('milestone') else None,
            'head': {
                'ref': pr['head']['ref'],
                'sha': pr['head']['sha'],
                'repo': {
                    'name': pr['head']['repo']['name'],
                    'full_name': pr['head']['repo']['full_name'],
                    'id': pr['head']['repo']['id']
                }
            },
            'base': {
                'ref': pr['base']['ref'],
                'sha': pr['base']['sha'],
                'repo': {
                    'name': pr['base']['repo']['name'],
                    'full_name': pr['base']['repo']['full_name'],
                    'id': pr['base']['repo']['id']
                }
            },
            'comments': pr.get('comments', 0),
            'review_comments': pr.get('review_comments', 0),
            'commits': pr.get('commits', 0),
            'additions': pr.get('additions', 0),
            'deletions': pr.get('deletions', 0),
            'changed_files': pr.get('changed_files', 0)
        },
            cost_usd=0.0
        )


@github.action("merge_pull_request")
class MergePullRequest(ActionHandler):
    """Merge a pull request"""

    @handle_github_errors("merge_pull_request")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.merge_pull_request(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number'],
            commit_title=inputs.get('commit_title'),
            commit_message=inputs.get('commit_message'),
            merge_method=inputs.get('merge_method', 'merge')
        )

        return ActionResult(
            data={
            'merged': True,
            'message': result.get('message'),
            'sha': result.get('sha'),
            'commit_title': inputs.get('commit_title') or result.get('commit_title'),
            'commit_message': inputs.get('commit_message') or result.get('commit_message')
        },
            cost_usd=0.0
        )


@github.action("add_pull_request_reviewers")
class AddPullRequestReviewers(ActionHandler):
    """Add reviewers to a pull request"""

    @handle_github_errors("add_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.add_pull_request_reviewers(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number'],
            reviewers=inputs.get('reviewers'),
            team_reviewers=inputs.get('team_reviewers')
        )

        return ActionResult(
            data={
            'requested_reviewers': [{'login': reviewer['login'], 'id': reviewer['id']}
                                   for reviewer in result.get('requested_reviewers', [])],
            'requested_teams': [{'slug': team['slug'], 'id': team['id'], 'name': team['name']}
                               for team in result.get('requested_teams', [])]
        },
            cost_usd=0.0
        )


@github.action("remove_pull_request_reviewers")
class RemovePullRequestReviewers(ActionHandler):
    """Remove reviewers from a pull request"""

    @handle_github_errors("remove_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.remove_pull_request_reviewers(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number'],
            reviewers=inputs.get('reviewers'),
            team_reviewers=inputs.get('team_reviewers')
        )

        return ActionResult(
            data={
            'requested_reviewers': [{'login': reviewer['login'], 'id': reviewer['id']}
                                   for reviewer in result.get('requested_reviewers', [])],
            'requested_teams': [{'slug': team['slug'], 'id': team['id'], 'name': team['name']}
                               for team in result.get('requested_teams', [])]
        },
            cost_usd=0.0
        )


@github.action("list_pull_request_reviewers")
class ListPullRequestReviewers(ActionHandler):
    """List reviewers for a pull request"""

    @handle_github_errors("list_pull_request_reviewers")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.list_pull_request_reviewers(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number']
        )

        return ActionResult(
            data={
            'users': [{'login': user['login'], 'id': user['id'], 'avatar_url': user['avatar_url']}
                     for user in result.get('users', [])],
            'teams': [{'slug': team['slug'], 'id': team['id'], 'name': team['name']}
                     for team in result.get('teams', [])]
        },
            cost_usd=0.0
        )


@github.action("create_pull_request_review")
class CreatePullRequestReview(ActionHandler):
    """Create a review for a pull request"""

    @handle_github_errors("create_pull_request_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        review = await GitHubAPI.create_pull_request_review(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['pull_number'],
            body=inputs.get('body'),
            event=inputs.get('event'),
            comments=inputs.get('comments')
        )

        return ActionResult(
            data={
            'id': review['id'],
            'body': review.get('body'),
            'state': review.get('state'),
            'submitted_at': review.get('submitted_at'),
            'author': {
                'login': review['user']['login'],
                'avatar_url': review['user']['avatar_url']
            },
            'url': review.get('html_url')
        },
            cost_usd=0.0
        )


# ---- Branch Actions ----

@github.action("list_branches")
class ListBranches(ActionHandler):
    """List branches for a repository"""

    @handle_github_errors("list_branches")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        branches = await GitHubAPI.list_branches(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data=[{
            'name': branch['name'],
            'protected': branch['protected'],
            'commit': {
                'sha': branch['commit']['sha'],
                'url': branch['commit']['url']
            }
        } for branch in branches],
            cost_usd=0.0
        )


@github.action("get_branch")
class GetBranch(ActionHandler):
    """Get branch details"""

    @handle_github_errors("get_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        branch = await GitHubAPI.get_branch(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['branch']
        )

        return ActionResult(
            data={
            'name': branch['name'],
            'protected': branch['protected'],
            'commit': {
                'sha': branch['commit']['sha'],
                'url': branch['commit']['url']
            },
            'protection': branch.get('protection', {})
        },
            cost_usd=0.0
        )


@github.action("create_branch")
class CreateBranch(ActionHandler):
    """Create a new branch"""

    @handle_github_errors("create_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.create_branch(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['branch_name'],
            inputs['sha']
        )

        return ActionResult(
            data={
            'ref': result['ref'],
            'url': result['url'],
            'object': {
                'sha': result['object']['sha'],
                'type': result['object']['type'],
                'url': result['object']['url']
            }
        },
            cost_usd=0.0
        )


@github.action("delete_branch")
class DeleteBranch(ActionHandler):
    """Delete a branch"""

    @handle_github_errors("delete_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_branch(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['branch']
        )

        return ActionResult(
            data={
            'deleted': True,
            'branch': inputs['branch']
        },
            cost_usd=0.0
        )


@github.action("get_branch_protection")
class GetBranchProtection(ActionHandler):
    """Get branch protection rules"""

    @handle_github_errors("get_branch_protection")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            protection = await GitHubAPI.get_branch_protection(
                context,
                inputs['owner'],
                inputs['repo'],
                inputs['branch']
            )

            return ActionResult(
                data={
                    'enabled': True,
                    'required_status_checks': protection.get('required_status_checks', {}).get('contexts', []) if protection.get('required_status_checks') else [],
                    'enforce_admins': protection.get('enforce_admins', {}).get('enabled', False) if protection.get('enforce_admins') else False,
                    'required_pull_request_reviews': {
                        'required_approving_review_count': protection.get('required_pull_request_reviews', {}).get('required_approving_review_count', 0) if protection.get('required_pull_request_reviews') else 0,
                        'dismiss_stale_reviews': protection.get('required_pull_request_reviews', {}).get('dismiss_stale_reviews', False) if protection.get('required_pull_request_reviews') else False,
                        'require_code_owner_reviews': protection.get('required_pull_request_reviews', {}).get('require_code_owner_reviews', False) if protection.get('required_pull_request_reviews') else False
                    },
                    'restrictions': {
                        'users': [user['login'] for user in protection.get('restrictions', {}).get('users', [])] if protection.get('restrictions') else [],
                        'teams': [team['slug'] for team in protection.get('restrictions', {}).get('teams', [])] if protection.get('restrictions') else []
                    }
                },
                cost_usd=0.0
            )
        except Exception as e:
            # Branch protection not enabled
            return ActionResult(
                data={
                    'enabled': False,
                    'error': str(e)
                },
                cost_usd=0.0
            )


@github.action("diff_branch_to_branch")
class DiffBranchToBranch(ActionHandler):
    """Compare two branches"""

    @handle_github_errors("diff_branch_to_branch")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        diff_data = await GitHubAPI.compare_branches(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['base_branch'],
            inputs['head_branch']
        )

        return ActionResult(
            data={
            'status': diff_data.get('status'),
            'ahead_by': diff_data.get('ahead_by'),
            'behind_by': diff_data.get('behind_by'),
            'total_commits': diff_data.get('total_commits'),
            'commits': [{
                'sha': commit['sha'],
                'author': {
                    'name': commit['commit']['author']['name'],
                    'email': commit['commit']['author']['email'],
                    'date': commit['commit']['author']['date']
                },
                'message': commit['commit']['message'],
                'url': commit['html_url']
            } for commit in diff_data.get('commits', [])],
            'files': [{
                'filename': file['filename'],
                'status': file['status'],
                'additions': file['additions'],
                'deletions': file['deletions'],
                'changes': file['changes'],
                'patch': file.get('patch') or ""
            } for file in diff_data.get('files', [])]
        },
            cost_usd=0.0
        )


# ---- Webhook Actions ----

@github.action("create_webhook")
class CreateWebhook(ActionHandler):
    """Create a webhook"""

    @handle_github_errors("create_webhook")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webhook = await GitHubAPI.create_webhook(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['url'],
            inputs['events'],
            content_type=inputs.get('content_type', 'json'),
            secret=inputs.get('secret'),
            active=inputs.get('active', True)
        )

        return ActionResult(
            data={
            'id': webhook['id'],
            'name': webhook['name'],
            'active': webhook['active'],
            'events': webhook['events'],
            'config': {
                'url': webhook['config']['url'],
                'content_type': webhook['config']['content_type']
            },
            'created_at': webhook['created_at'],
            'updated_at': webhook['updated_at'],
            'url': webhook['url']
        },
            cost_usd=0.0
        )


@github.action("list_webhooks")
class ListWebhooks(ActionHandler):
    """List webhooks for a repository"""

    @handle_github_errors("list_webhooks")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webhooks = await GitHubAPI.list_webhooks(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data=[{
            'id': webhook['id'],
            'name': webhook['name'],
            'active': webhook['active'],
            'events': webhook['events'],
            'config': {
                'url': webhook['config']['url'],
                'content_type': webhook['config']['content_type']
            },
            'created_at': webhook['created_at'],
            'updated_at': webhook['updated_at'],
            'url': webhook['url']
        } for webhook in webhooks],
            cost_usd=0.0
        )


@github.action("delete_webhook")
class DeleteWebhook(ActionHandler):
    """Delete a webhook"""

    @handle_github_errors("delete_webhook")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await GitHubAPI.delete_webhook(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['hook_id']
        )

        return ActionResult(
            data={
            'deleted': True,
            'hook_id': inputs['hook_id']
        },
            cost_usd=0.0
        )


# ---- File Operation Actions ----

@github.action("get_file_content")
class GetFileContent(ActionHandler):
    """Get file content from repository"""

    @handle_github_errors("get_file_content")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        file_data = await GitHubAPI.get_file_content(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['path'],
            ref=inputs.get('ref')
        )

        return ActionResult(
            data={
            'content': file_data['content'],
            'sha': file_data['sha'],
            'size': file_data['size'],
            'name': file_data['name'],
            'path': file_data['path']
        },
            cost_usd=0.0
        )


@github.action("create_file")
class CreateFile(ActionHandler):
    """Create a new file in repository"""

    @handle_github_errors("create_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.create_file(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['path'],
            inputs['message'],
            inputs['content'],
            branch=inputs.get('branch')
        )

        return ActionResult(
            data={
            'content': {
                'name': result['content']['name'],
                'path': result['content']['path'],
                'sha': result['content']['sha'],
                'size': result['content']['size']
            },
            'commit': {
                'sha': result['commit']['sha'],
                'message': result['commit']['message']
            }
        },
            cost_usd=0.0
        )


@github.action("update_file")
class UpdateFile(ActionHandler):
    """Update an existing file in repository"""

    @handle_github_errors("update_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.update_file(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['path'],
            inputs['message'],
            inputs['content'],
            inputs['sha'],
            branch=inputs.get('branch')
        )

        return ActionResult(
            data={
            'content': {
                'name': result['content']['name'],
                'path': result['content']['path'],
                'sha': result['content']['sha'],
                'size': result['content']['size']
            },
            'commit': {
                'sha': result['commit']['sha'],
                'message': result['commit']['message']
            }
        },
            cost_usd=0.0
        )


@github.action("delete_file")
class DeleteFile(ActionHandler):
    """Delete a file from repository"""

    @handle_github_errors("delete_file")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        result = await GitHubAPI.delete_file(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['path'],
            inputs['message'],
            inputs['sha'],
            branch=inputs.get('branch')
        )

        return ActionResult(
            data={
            'deleted': True,
            'path': inputs['path'],
            'commit': {
                'sha': result['commit']['sha'],
                'message': result['commit']['message']
            }
        },
            cost_usd=0.0
        )


# ---- Gist Actions ----

@github.action("create_gist")
class CreateGist(ActionHandler):
    """Create a new gist"""

    @handle_github_errors("create_gist")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        gist = await GitHubAPI.create_gist(
            context,
            inputs.get('description', ''),
            inputs['files'],
            public=inputs.get('public', True)
        )

        return ActionResult(
            data={
            'id': gist['id'],
            'description': gist['description'],
            'public': gist['public'],
            'files': {name: {'size': file['size'], 'type': file['type']}
                     for name, file in gist['files'].items()},
            'created_at': gist['created_at'],
            'updated_at': gist['updated_at'],
            'url': gist['html_url']
        },
            cost_usd=0.0
        )


# ---- User Actions ----

@github.action("get_user")
class GetUser(ActionHandler):
    """Get user information"""

    @handle_github_errors("get_user")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        user = await GitHubAPI.get_user(
            context,
            username=inputs.get('username')
        )

        return ActionResult(
            data={
            'login': user['login'],
            'id': user['id'],
            'name': user.get('name'),
            'company': user.get('company'),
            'blog': user.get('blog'),
            'location': user.get('location'),
            'email': user.get('email'),
            'bio': user.get('bio'),
            'public_repos': user['public_repos'],
            'public_gists': user['public_gists'],
            'followers': user['followers'],
            'following': user['following'],
            'created_at': user['created_at'],
            'updated_at': user['updated_at'],
            'avatar_url': user['avatar_url'],
            'html_url': user['html_url']
        },
            cost_usd=0.0
        )


# ---- Organization Actions ----

@github.action("list_organization_members")
class ListOrganizationMembers(ActionHandler):
    """List organization members"""

    @handle_github_errors("list_organization_members")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        members = await GitHubAPI.list_organization_members(
            context,
            inputs['org'],
            role=inputs.get('role', 'all')
        )

        return ActionResult(
            data=[{
            'login': member['login'],
            'id': member['id'],
            'type': member['type'],
            'site_admin': member['site_admin'],
            'avatar_url': member['avatar_url'],
            'url': member['html_url']
        } for member in members],
            cost_usd=0.0
        )


# ---- GitHub Actions/Workflows ----

@github.action("list_workflows")
class ListWorkflows(ActionHandler):
    """List GitHub Actions workflows"""

    @handle_github_errors("list_workflows")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        workflows = await GitHubAPI.list_workflows(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data=[{
            'id': workflow['id'],
            'name': workflow['name'],
            'path': workflow['path'],
            'state': workflow['state'],
            'created_at': workflow['created_at'],
            'updated_at': workflow['updated_at'],
            'url': workflow['html_url']
        } for workflow in workflows],
            cost_usd=0.0
        )


@github.action("get_workflow_runs")
class GetWorkflowRuns(ActionHandler):
    """Get workflow runs"""

    @handle_github_errors("get_workflow_runs")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        runs = await GitHubAPI.get_workflow_runs(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['workflow_id'],
            status=inputs.get('status'),
            branch=inputs.get('branch')
        )

        return ActionResult(
            data=[{
            'id': run['id'],
            'name': run['name'],
            'workflow_id': run['workflow_id'],
            'head_branch': run['head_branch'],
            'head_sha': run['head_sha'],
            'run_number': run['run_number'],
            'event': run['event'],
            'status': run['status'],
            'conclusion': run['conclusion'],
            'created_at': run['created_at'],
            'updated_at': run['updated_at'],
            'run_started_at': run.get('run_started_at'),
            'run_attempt': run.get('run_attempt', 1),
            'actor': {
                'login': run['actor']['login'],
                'avatar_url': run['actor']['avatar_url']
            },
            'url': run['html_url']
        } for run in runs],
            cost_usd=0.0
        )


# ---- Rate Limit Action ----

@github.action("get_rate_limit")
class GetRateLimit(ActionHandler):
    """Get current rate limit status"""

    @handle_github_errors("get_rate_limit")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        rate_limit = await GitHubAPI.get_rate_limit(context)

        return ActionResult(
            data={
            'core': {
                'limit': rate_limit['resources']['core']['limit'],
                'remaining': rate_limit['resources']['core']['remaining'],
                'reset': rate_limit['resources']['core']['reset'],
                'used': rate_limit['resources']['core']['used']
            },
            'search': {
                'limit': rate_limit['resources']['search']['limit'],
                'remaining': rate_limit['resources']['search']['remaining'],
                'reset': rate_limit['resources']['search']['reset'],
                'used': rate_limit['resources']['search']['used']
            },
            'graphql': {
                'limit': rate_limit['resources']['graphql']['limit'],
                'remaining': rate_limit['resources']['graphql']['remaining'],
                'reset': rate_limit['resources']['graphql']['reset'],
                'used': rate_limit['resources']['graphql']['used']
            }
        },
            cost_usd=0.0
        )


@github.action("list_user_repositories")
class ListUserRepositories(ActionHandler):
    """List repositories for a specific user or authenticated user"""

    @handle_github_errors("list_user_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_user_repositories(
            context,
            username=inputs.get('username'),
            type=inputs.get('type', 'all'),
            sort=inputs.get('sort', 'updated'),
            direction=inputs.get('direction', 'desc')
        )

        return ActionResult(
            data=[{
            'id': repo['id'],
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo.get('description'),
            'private': repo['private'],
            'fork': repo['fork'],
            'html_url': repo['html_url'],
            'created_at': repo['created_at'],
            'updated_at': repo['updated_at'],
            'language': repo.get('language'),
            'stargazers_count': repo['stargazers_count'],
            'forks_count': repo['forks_count'],
            'open_issues_count': repo['open_issues_count'],
            'default_branch': repo['default_branch']
        } for repo in repos],
            cost_usd=0.0
        )


@github.action("list_organization_repositories")
class ListOrganizationRepositories(ActionHandler):
    """List repositories for a specific organization"""

    @handle_github_errors("list_organization_repositories")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        repos = await GitHubAPI.list_organization_repositories(
            context,
            org=inputs['org'],
            type=inputs.get('type', 'all'),
            sort=inputs.get('sort', 'updated'),
            direction=inputs.get('direction', 'desc')
        )

        return ActionResult(
            data=[{
            'id': repo['id'],
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo.get('description'),
            'private': repo['private'],
            'fork': repo['fork'],
            'html_url': repo['html_url'],
            'created_at': repo['created_at'],
            'updated_at': repo['updated_at'],
            'language': repo.get('language'),
            'stargazers_count': repo['stargazers_count'],
            'forks_count': repo['forks_count'],
            'open_issues_count': repo['open_issues_count'],
            'default_branch': repo['default_branch']
        } for repo in repos],
            cost_usd=0.0
        )


# ---- Tag Actions ----

@github.action("list_tags")
class ListTags(ActionHandler):
    """List tags for a repository"""

    @handle_github_errors("list_tags")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        tags = await GitHubAPI.list_tags(
            context,
            inputs['owner'],
            inputs['repo'],
            per_page=inputs.get('per_page', 30),
            page=inputs.get('page', 1)
        )

        return ActionResult(
            data=[{
                'name': tag['name'],
                'commit': {
                    'sha': tag['commit']['sha'],
                    'url': tag['commit']['url']
                },
                'zipball_url': tag.get('zipball_url'),
                'tarball_url': tag.get('tarball_url'),
                'node_id': tag.get('node_id')
            } for tag in tags],
            cost_usd=0.0
        )


# ---- Release Actions ----

@github.action("list_releases")
class ListReleases(ActionHandler):
    """List releases for a repository"""

    @handle_github_errors("list_releases")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        releases = await GitHubAPI.list_releases(
            context,
            inputs['owner'],
            inputs['repo'],
            per_page=inputs.get('per_page', 30),
            page=inputs.get('page', 1)
        )

        return ActionResult(
            data=[{
                'id': release['id'],
                'tag_name': release['tag_name'],
                'name': release.get('name'),
                'body': release.get('body'),
                'draft': release.get('draft', False),
                'prerelease': release.get('prerelease', False),
                'created_at': release['created_at'],
                'published_at': release.get('published_at'),
                'html_url': release['html_url'],
                'tarball_url': release.get('tarball_url'),
                'zipball_url': release.get('zipball_url'),
                'author': {
                    'login': release['author']['login'],
                    'id': release['author']['id'],
                    'avatar_url': release['author']['avatar_url']
                } if release.get('author') else None,
                'assets': [{
                    'id': asset['id'],
                    'name': asset['name'],
                    'size': asset['size'],
                    'download_count': asset['download_count'],
                    'browser_download_url': asset['browser_download_url']
                } for asset in release.get('assets', [])]
            } for release in releases],
            cost_usd=0.0
        )


@github.action("get_release")
class GetRelease(ActionHandler):
    """Get a specific release by ID"""

    @handle_github_errors("get_release")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_release(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['release_id']
        )

        return ActionResult(
            data={
                'id': release['id'],
                'tag_name': release['tag_name'],
                'target_commitish': release.get('target_commitish'),
                'name': release.get('name'),
                'body': release.get('body'),
                'draft': release.get('draft', False),
                'prerelease': release.get('prerelease', False),
                'created_at': release['created_at'],
                'published_at': release.get('published_at'),
                'html_url': release['html_url'],
                'tarball_url': release.get('tarball_url'),
                'zipball_url': release.get('zipball_url'),
                'author': {
                    'login': release['author']['login'],
                    'id': release['author']['id'],
                    'avatar_url': release['author']['avatar_url']
                } if release.get('author') else None,
                'assets': [{
                    'id': asset['id'],
                    'name': asset['name'],
                    'label': asset.get('label'),
                    'state': asset['state'],
                    'content_type': asset['content_type'],
                    'size': asset['size'],
                    'download_count': asset['download_count'],
                    'browser_download_url': asset['browser_download_url'],
                    'created_at': asset['created_at'],
                    'updated_at': asset['updated_at']
                } for asset in release.get('assets', [])]
            },
            cost_usd=0.0
        )


@github.action("get_latest_release")
class GetLatestRelease(ActionHandler):
    """Get the latest release for a repository"""

    @handle_github_errors("get_latest_release")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_latest_release(
            context,
            inputs['owner'],
            inputs['repo']
        )

        return ActionResult(
            data={
                'id': release['id'],
                'tag_name': release['tag_name'],
                'target_commitish': release.get('target_commitish'),
                'name': release.get('name'),
                'body': release.get('body'),
                'draft': release.get('draft', False),
                'prerelease': release.get('prerelease', False),
                'created_at': release['created_at'],
                'published_at': release.get('published_at'),
                'html_url': release['html_url'],
                'tarball_url': release.get('tarball_url'),
                'zipball_url': release.get('zipball_url'),
                'author': {
                    'login': release['author']['login'],
                    'id': release['author']['id'],
                    'avatar_url': release['author']['avatar_url']
                } if release.get('author') else None,
                'assets': [{
                    'id': asset['id'],
                    'name': asset['name'],
                    'size': asset['size'],
                    'download_count': asset['download_count'],
                    'browser_download_url': asset['browser_download_url']
                } for asset in release.get('assets', [])]
            },
            cost_usd=0.0
        )


@github.action("get_release_by_tag")
class GetReleaseByTag(ActionHandler):
    """Get a release by tag name"""

    @handle_github_errors("get_release_by_tag")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        release = await GitHubAPI.get_release_by_tag(
            context,
            inputs['owner'],
            inputs['repo'],
            inputs['tag']
        )

        return ActionResult(
            data={
                'id': release['id'],
                'tag_name': release['tag_name'],
                'target_commitish': release.get('target_commitish'),
                'name': release.get('name'),
                'body': release.get('body'),
                'draft': release.get('draft', False),
                'prerelease': release.get('prerelease', False),
                'created_at': release['created_at'],
                'published_at': release.get('published_at'),
                'html_url': release['html_url'],
                'tarball_url': release.get('tarball_url'),
                'zipball_url': release.get('zipball_url'),
                'author': {
                    'login': release['author']['login'],
                    'id': release['author']['id'],
                    'avatar_url': release['author']['avatar_url']
                } if release.get('author') else None,
                'assets': [{
                    'id': asset['id'],
                    'name': asset['name'],
                    'size': asset['size'],
                    'download_count': asset['download_count'],
                    'browser_download_url': asset['browser_download_url']
                } for asset in release.get('assets', [])]
            },
            cost_usd=0.0
        )


# ============================================================================
# CONNECTED ACCOUNT HANDLER
# ============================================================================

@github.connected_account()
class GitHubConnectedAccountHandler(ConnectedAccountHandler):
    """
    Handler for fetching connected GitHub account information.
    This is called once when a user authorizes the integration and the
    information is cached for display in the UI.
    """

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch GitHub user information for the connected account.

        Returns:
            ConnectedAccountInfo with user's email, username, name, avatar, etc.
        """
        # Fetch authenticated user info
        user_data = await GitHubAPI.get_user(context)

        # Parse name into first/last
        name = user_data.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []

        return ConnectedAccountInfo(
            email=user_data.get("email"),
            username=user_data.get("login"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=user_data.get("avatar_url"),
            organization=user_data.get("company"),
            user_id=str(user_data.get("id")) if user_data.get("id") else None
        )


# ============================================================================

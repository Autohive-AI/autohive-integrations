"""
GitHub integration - Pull request review actions.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any, List, Optional

from github import github
from helpers import GitHubAPI, handle_github_errors


@github.action("create_pull_request_review")
class CreatePullRequestReview(ActionHandler):
    """Create a review for a pull request"""

    @handle_github_errors("create_pull_request_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        review = await GitHubAPI.create_pull_request_review(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            commit_id=inputs.get("commit_id"),
            body=inputs.get("body"),
            event=inputs.get("event"),
            comments=inputs.get("comments"),
        )

        return ActionResult(
            data={
                "id": review["id"],
                "body": review.get("body"),
                "state": review.get("state"),
                "submitted_at": review.get("submitted_at"),
                "author": {
                    "login": review["user"]["login"],
                    "avatar_url": review["user"]["avatar_url"],
                },
                "url": review.get("html_url"),
            },
            cost_usd=0.0,
        )


# =============================================================================
# GRAPHQL DOCUMENTS
# =============================================================================

# REST exposes a review's integer id but the GraphQL mutations key off the
# global node id, so the pending review has to be looked up before it can be
# commented on. PENDING reviews are only visible to their own author, so this
# query never returns another user's draft.
_PENDING_REVIEWS_QUERY = """
query PendingReviews($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      id
      reviews(states: [PENDING], first: 20) {
        nodes {
          id
          databaseId
        }
      }
    }
  }
}
"""

# ``addPullRequestReviewComment`` still exists but GitHub has deprecated every
# one of its meaningful input fields (body, path, position, commitOID,
# inReplyTo, pullRequestId, pullRequestReviewId) in favour of this mutation.
# Optional variables that are left out of the variables map are dropped from the
# coerced input object, so a file-level comment can omit ``line``/``side``.
_ADD_REVIEW_THREAD_MUTATION = """
mutation AddReviewThread(
  $reviewId: ID!
  $path: String!
  $body: String!
  $line: Int
  $side: DiffSide
  $startLine: Int
  $startSide: DiffSide
  $subjectType: PullRequestReviewThreadSubjectType
) {
  addPullRequestReviewThread(input: {
    pullRequestReviewId: $reviewId
    path: $path
    body: $body
    line: $line
    side: $side
    startLine: $startLine
    startSide: $startSide
    subjectType: $subjectType
  }) {
    thread {
      id
      path
      line
      startLine
      diffSide
      isResolved
      isOutdated
      comments(first: 1) {
        nodes {
          id
          databaseId
          body
          url
          createdAt
          author {
            login
            avatarUrl
          }
        }
      }
    }
  }
}
"""


# =============================================================================
# API HELPERS
# =============================================================================


async def _submit_pull_request_review(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    review_id: int,
    event: str,
    body: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit a pending review (POST .../reviews/{review_id}/events)."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events"
    request_body: Dict[str, Any] = {"event": event}
    if body:
        request_body["body"] = body

    fetch_result = await context.fetch(url, method="POST", json=request_body, headers=GitHubAPI.get_headers(context))
    return fetch_result.data or {}


async def _delete_pending_pull_request_review(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    review_id: int,
) -> Dict[str, Any]:
    """Delete an unsubmitted review (DELETE .../reviews/{review_id}). Submitted reviews cannot be deleted."""
    url = f"{GitHubAPI.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}"
    fetch_result = await context.fetch(url, method="DELETE", headers=GitHubAPI.get_headers(context))
    return fetch_result.data or {}


async def _resolve_pending_review_node_id(
    context: ExecutionContext,
    owner: str,
    repo: str,
    pull_number: int,
    review_id: Optional[int] = None,
) -> str:
    """Resolve the GraphQL node id of the caller's pending review on a pull request.

    When ``review_id`` (the REST integer id) is given, the matching draft is
    selected; otherwise the pull request's single pending review is used.
    """
    graph_data = await GitHubAPI.graphql(
        context,
        _PENDING_REVIEWS_QUERY,
        {"owner": owner, "repo": repo, "number": pull_number},
    )
    pull_request = ((graph_data.get("repository") or {}).get("pullRequest")) or {}
    nodes: List[Dict[str, Any]] = ((pull_request.get("reviews") or {}).get("nodes")) or []

    if review_id is not None:
        for node in nodes:
            if node.get("databaseId") == review_id:
                return node["id"]
        raise ValueError(
            f"No pending review with id {review_id} on pull request #{pull_number}. "
            "Only unsubmitted reviews can take new comments."
        )

    if not nodes:
        raise ValueError(
            f"No pending review found on pull request #{pull_number}. "
            "Create one with create_pending_pull_request_review first."
        )

    return nodes[0]["id"]


def _review_summary(review: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a pull request review. ``submitted_at`` is absent while a review is PENDING."""
    author = review.get("user")
    return {
        "id": review.get("id"),
        "node_id": review.get("node_id"),
        "body": review.get("body"),
        "state": review.get("state"),
        "commit_id": review.get("commit_id"),
        "submitted_at": review.get("submitted_at"),
        "author_association": review.get("author_association"),
        "author": {"login": author.get("login"), "avatar_url": author.get("avatar_url")} if author else None,
        "url": review.get("html_url"),
    }


# =============================================================================
# ACTIONS
# =============================================================================


@github.action("get_pull_request_reviews")
class GetPullRequestReviews(ActionHandler):
    """List the reviews left on a pull request, in chronological order"""

    @handle_github_errors("get_pull_request_reviews")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = f"{GitHubAPI.BASE_URL}/repos/{inputs['owner']}/{inputs['repo']}/pulls/{inputs['pull_number']}/reviews"
        reviews: List[Dict[str, Any]] = await GitHubAPI.paginated_fetch(
            context,
            url,
            limit=inputs.get("limit"),
            max_pages=inputs.get("max_pages", 10),
        )

        return ActionResult(
            data=[_review_summary(review) for review in reviews],
            cost_usd=0.0,
        )


@github.action("create_pending_pull_request_review")
class CreatePendingPullRequestReview(ActionHandler):
    """Start a draft (pending) review on a pull request without submitting it"""

    @handle_github_errors("create_pending_pull_request_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        # `event` is deliberately never sent: omitting it is what leaves the
        # review in the PENDING state so more comments can be added before it is
        # submitted. Inline comments may still be supplied up front.
        review = await GitHubAPI.create_pull_request_review(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            commit_id=inputs.get("commit_id"),
            body=inputs.get("body"),
            comments=inputs.get("comments"),
        )

        return ActionResult(data=_review_summary(review), cost_usd=0.0)


@github.action("submit_pending_pull_request_review")
class SubmitPendingPullRequestReview(ActionHandler):
    """Submit a pending review as an approval, a change request, or a comment"""

    @handle_github_errors("submit_pending_pull_request_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        review = await _submit_pull_request_review(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            inputs["review_id"],
            inputs["event"],
            body=inputs.get("body"),
        )

        return ActionResult(data=_review_summary(review), cost_usd=0.0)


@github.action("delete_pending_pull_request_review")
class DeletePendingPullRequestReview(ActionHandler):
    """Discard a pending review that has not been submitted"""

    @handle_github_errors("delete_pending_pull_request_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        review = await _delete_pending_pull_request_review(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            inputs["review_id"],
        )

        return ActionResult(
            data={
                "deleted": True,
                "review_id": inputs["review_id"],
                "pull_number": inputs["pull_number"],
                "state": review.get("state"),
            },
            cost_usd=0.0,
        )


@github.action("add_comment_to_pending_review")
class AddCommentToPendingReview(ActionHandler):
    """Add an inline comment to a review that is already pending, without submitting it

    REST has no equivalent: ``POST /pulls/{n}/reviews`` only accepts inline
    comments at creation time, and there is no endpoint for appending one to an
    existing draft. This runs a two-step GraphQL flow instead:

    1. Query the pull request's PENDING reviews to turn the REST review id (or
       the implicit "my one open draft") into the review's GraphQL node id.
    2. Call ``addPullRequestReviewThread`` with that node id to attach the
       comment thread to the draft.

    ``addPullRequestReviewThread`` supersedes ``addPullRequestReviewComment``,
    whose input fields GitHub has deprecated wholesale.
    """

    @handle_github_errors("add_comment_to_pending_review")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        review_node_id = await _resolve_pending_review_node_id(
            context,
            inputs["owner"],
            inputs["repo"],
            inputs["pull_number"],
            review_id=inputs.get("review_id"),
        )

        variables: Dict[str, Any] = {
            "reviewId": review_node_id,
            "path": inputs["path"],
            "body": inputs["body"],
        }
        # Left out of the variables map rather than sent as null — GraphQL drops
        # unprovided variables from the input object, and an explicit null line
        # is rejected for LINE-subject threads.
        optional_variables = {
            "line": inputs.get("line"),
            "side": inputs.get("side"),
            "startLine": inputs.get("start_line"),
            "startSide": inputs.get("start_side"),
            "subjectType": inputs.get("subject_type"),
        }
        for variable_name, variable_value in optional_variables.items():
            if variable_value is not None:
                variables[variable_name] = variable_value

        graph_data = await GitHubAPI.graphql(context, _ADD_REVIEW_THREAD_MUTATION, variables)
        thread = ((graph_data.get("addPullRequestReviewThread") or {}).get("thread")) or {}
        comment_nodes: List[Dict[str, Any]] = ((thread.get("comments") or {}).get("nodes")) or []
        comment = comment_nodes[0] if comment_nodes else {}
        author = comment.get("author")

        return ActionResult(
            data={
                "thread_id": thread.get("id"),
                "review_node_id": review_node_id,
                "path": thread.get("path"),
                "line": thread.get("line"),
                "start_line": thread.get("startLine"),
                "side": thread.get("diffSide"),
                "is_resolved": thread.get("isResolved"),
                "is_outdated": thread.get("isOutdated"),
                "comment": {
                    "id": comment.get("databaseId"),
                    "node_id": comment.get("id"),
                    "body": comment.get("body"),
                    "created_at": comment.get("createdAt"),
                    "author": {"login": author.get("login"), "avatar_url": author.get("avatarUrl")} if author else None,
                    "url": comment.get("url"),
                }
                if comment
                else None,
            },
            cost_usd=0.0,
        )

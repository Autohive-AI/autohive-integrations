from urllib.parse import urlencode
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, Optional

grammarly = Integration.load()

GRAMMARLY_TOKEN_URL = "https://auth.grammarly.com/v4/api/oauth2/token"  # nosec B105
GRAMMARLY_WRITING_SCORE_URL = "https://api.grammarly.com/ecosystem/api/v2/scores"
GRAMMARLY_ANALYTICS_URL = "https://api.grammarly.com/ecosystem/api/v2/analytics/users"
GRAMMARLY_AI_DETECTION_URL = "https://api.grammarly.com/ecosystem/api/v1/ai-detection"
GRAMMARLY_PLAGIARISM_URL = "https://api.grammarly.com/ecosystem/api/v1/plagiarism"

GRAMMARLY_SCOPES = (
    "scores-api:read scores-api:write analytics-api:read "
    "ai-detection-api:read ai-detection-api:write plagiarism-api:read plagiarism-api:write"
)


async def get_access_token(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {}) or {}
    client_id = credentials.get("client_id") or context.auth.get("client_id", "")
    client_secret = credentials.get("client_secret") or context.auth.get("client_secret", "")

    form_body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": GRAMMARLY_SCOPES,
        }
    )

    resp = await context.fetch(
        GRAMMARLY_TOKEN_URL,
        method="POST",
        data=form_body,
        content_type="application/x-www-form-urlencoded",
    )
    token_data = resp.data
    if not isinstance(token_data, dict) or "access_token" not in token_data:
        raise Exception("Failed to obtain Grammarly access token")
    return token_data["access_token"]


async def api_request(
    context: ExecutionContext,
    method: str,
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    access_token = await get_access_token(context)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    resp = await context.fetch(url, method=method, headers=headers, json=json_data, params=params)
    return resp.data


async def upload_file(context: ExecutionContext, upload_url: str, file_content: str) -> bool:
    await context.fetch(
        upload_url,
        method="PUT",
        data=file_content,
        content_type="text/plain",
    )
    return True


@grammarly.action("analyze_writing_score")
class AnalyzeWritingScoreAction(ActionHandler):
    """Submit a document for writing quality analysis."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            filename = inputs["filename"]
            file_content = inputs["file_content"]

            response = await api_request(context, "POST", GRAMMARLY_WRITING_SCORE_URL, json_data={"filename": filename})
            score_request_id = response.get("score_request_id")
            upload_url = response.get("file_upload_url")

            await upload_file(context, upload_url, file_content)

            return ActionResult(data={"score_request_id": score_request_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("get_writing_score_results")
class GetWritingScoreResultsAction(ActionHandler):
    """Get the writing score results for a score request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            score_request_id = inputs["score_request_id"]
            url = f"{GRAMMARLY_WRITING_SCORE_URL}/{score_request_id}"

            response = await api_request(context, "GET", url)

            result: Dict[str, Any] = {"status": response.get("status")}

            if response.get("status") == "COMPLETED" and "score" in response:
                score_data = response["score"]
                result["general_score"] = score_data.get("generalScore")
                result["engagement"] = score_data.get("engagement")
                result["correctness"] = score_data.get("correctness")
                result["delivery"] = score_data.get("delivery")
                result["clarity"] = score_data.get("clarity")

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("get_user_analytics")
class GetUserAnalyticsAction(ActionHandler):
    """Get user analytics data for a date range."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params: Dict[str, Any] = {"date_from": inputs["date_from"], "date_to": inputs["date_to"]}

            if inputs.get("cursor"):
                params["cursor"] = inputs["cursor"]
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await api_request(context, "GET", GRAMMARLY_ANALYTICS_URL, params=params)

            return ActionResult(
                data={"data": response.get("data", []), "paging": response.get("paging", {})},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("analyze_ai_detection")
class AnalyzeAIDetectionAction(ActionHandler):
    """Submit a document for AI content detection analysis."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            filename = inputs["filename"]
            file_content = inputs["file_content"]

            response = await api_request(context, "POST", GRAMMARLY_AI_DETECTION_URL, json_data={"filename": filename})
            score_request_id = response.get("score_request_id")
            upload_url = response.get("file_upload_url")

            await upload_file(context, upload_url, file_content)

            return ActionResult(data={"score_request_id": score_request_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("get_ai_detection_results")
class GetAIDetectionResultsAction(ActionHandler):
    """Get the AI detection results for a score request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            score_request_id = inputs["score_request_id"]
            url = f"{GRAMMARLY_AI_DETECTION_URL}/{score_request_id}"

            response = await api_request(context, "GET", url)

            result: Dict[str, Any] = {"status": response.get("status")}

            if response.get("status") == "COMPLETED" and "score" in response:
                score_data = response["score"]
                result["average_confidence"] = score_data.get("average_confidence")
                result["ai_generated_percentage"] = score_data.get("ai_generated_percentage")
                result["updated_at"] = response.get("updated_at")

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("analyze_plagiarism_detection")
class AnalyzePlagiarismDetectionAction(ActionHandler):
    """Submit a document for plagiarism detection analysis."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            filename = inputs["filename"]
            file_content = inputs["file_content"]

            response = await api_request(context, "POST", GRAMMARLY_PLAGIARISM_URL, json_data={"filename": filename})
            score_request_id = response.get("score_request_id")
            upload_url = response.get("file_upload_url")

            await upload_file(context, upload_url, file_content)

            return ActionResult(data={"score_request_id": score_request_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@grammarly.action("get_plagiarism_detection_results")
class GetPlagiarismDetectionResultsAction(ActionHandler):
    """Get the plagiarism detection results for a score request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            score_request_id = inputs["score_request_id"]
            url = f"{GRAMMARLY_PLAGIARISM_URL}/{score_request_id}"

            response = await api_request(context, "GET", url)

            result: Dict[str, Any] = {"status": response.get("status")}

            if response.get("status") == "COMPLETED" and "score" in response:
                score_data = response["score"]
                originality = score_data.get("originality_score", 100)
                result["originality_score"] = originality
                result["plagiarism_percentage"] = max(0, 100 - originality)
                result["updated_at"] = response.get("updated_at")

            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))

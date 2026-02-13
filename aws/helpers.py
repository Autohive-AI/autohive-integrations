import asyncio
import functools
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict

import boto3
from autohive_integrations_sdk import ActionResult, ExecutionContext


def create_boto3_client(context: ExecutionContext, service_name: str):
    credentials = context.auth.get("credentials", {})
    return boto3.client(
        service_name,
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
        region_name=credentials.get("aws_region", "us-east-1")
    )


async def run_sync(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(func, *args, **kwargs)
    )


def serialize_response(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: serialize_response(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_response(i) for i in obj]
    return obj


def success_result(data: Dict[str, Any]) -> ActionResult:
    return ActionResult(data={"result": True, **serialize_response(data)})


def error_result(e: Exception) -> ActionResult:
    error_msg = str(e)
    error_code = ""
    if hasattr(e, "response"):
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", error_msg)
    return ActionResult(data={
        "result": False,
        "error": error_msg,
        "error_code": error_code
    })

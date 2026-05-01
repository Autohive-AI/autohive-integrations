import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------------------------------------------------------------------------
# SDK v1 compatibility shims
# SDK v2 has FetchResponse, ActionError, and ResultType.ACTION_ERROR natively.
# When running against SDK v1 we inject lightweight equivalents so that
# heartbeat.py (written for SDK v2) and the unit tests can be imported and
# executed without modification.
# ---------------------------------------------------------------------------
import autohive_integrations_sdk as _sdk
from autohive_integrations_sdk.integration import (
    ActionResult,
    ResultType,
)

# -- FetchResponse shim --
if not hasattr(_sdk, "FetchResponse"):

    @dataclass
    class FetchResponse:
        status: int
        headers: Dict[str, str] = field(default_factory=dict)
        data: Any = None

    _sdk.FetchResponse = FetchResponse
    sys.modules["autohive_integrations_sdk"].FetchResponse = FetchResponse

# -- ActionError shim --
# ActionError is an ActionResult subclass so SDK v1's isinstance check passes.
# It carries a `message` attribute and sets result_type to ACTION_ERROR.
if not hasattr(_sdk, "ActionError"):
    # Add ACTION_ERROR to ResultType enum if missing
    if not hasattr(ResultType, "ACTION_ERROR"):
        # Extend the enum dynamically
        import enum

        ResultType._value2member_map_["action_error"] = enum.Enum(
            "ResultType", {"ACTION_ERROR": "action_error"}
        ).ACTION_ERROR
        ResultType.ACTION_ERROR = ResultType._value2member_map_["action_error"]  # type: ignore

    @dataclass
    class ActionError(ActionResult):
        """SDK v2-style error return; compatible with SDK v1 ActionResult."""

        message: str = ""
        data: Any = field(default_factory=dict)
        cost_usd: float = None

        def __init__(self, message: str = "", **kwargs):
            self.message = message
            self.data = kwargs.get("data", {"error": message})
            self.cost_usd = kwargs.get("cost_usd", None)

    _sdk.ActionError = ActionError
    sys.modules["autohive_integrations_sdk"].ActionError = ActionError

# Patch IntegrationResult to expose result_type for ACTION_ERROR results
_orig_execute_action = None

# ---------------------------------------------------------------------------
# Patch Integration.execute_action to handle ActionError returns gracefully.
# In SDK v1 the method raises ValidationError when result is not ActionResult,
# but ActionError IS an ActionResult subclass, so the isinstance check passes.
# We additionally wrap the return to expose result.type == ResultType.ACTION_ERROR
# so tests can assert on it.
# ---------------------------------------------------------------------------
from autohive_integrations_sdk.integration import Integration as _Integration  # noqa: E402

_orig_execute_action = _Integration.execute_action


async def _patched_execute_action(self, name, inputs, context):
    from autohive_integrations_sdk.integration import (
        IntegrationResult as _IR,
        ResultType as _RT,
    )

    # Run the handler directly to intercept ActionError before SDK validates it
    if name not in self._action_handlers:
        from autohive_integrations_sdk.integration import ValidationError

        raise ValidationError(f"Action '{name}' not registered")

    handler = self._action_handlers[name]()
    result = await handler.execute(inputs, context)

    # If it's an ActionError (our shim), return a specially typed IntegrationResult
    if hasattr(_sdk, "ActionError") and isinstance(result, _sdk.ActionError):
        if not hasattr(_RT, "ACTION_ERROR"):
            _RT.ACTION_ERROR = _RT.ERROR  # fallback
        return _IR(
            version=getattr(_sdk, "__version__", "1.0.2"),
            type=_RT.ACTION_ERROR,
            result=result,
        )

    # Normal path
    return await _orig_execute_action(self, name, inputs, context)


_Integration.execute_action = _patched_execute_action

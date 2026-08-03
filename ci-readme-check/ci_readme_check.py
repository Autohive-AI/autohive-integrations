from pathlib import Path
from typing import Any

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext, Integration

ci_readme_check = Integration.load(Path(__file__).with_name("config.json"))


@ci_readme_check.action("get_data")
class GetDataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        return ActionResult(data={"message": "hello from ci_readme_check"}, cost_usd=0.0)

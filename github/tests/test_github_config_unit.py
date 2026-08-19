"""
Config/code sync tests.

These guard the invariant that CI's check_config_sync enforces: every action
declared in config.json has a registered handler, and vice versa. With handlers
split across actions/*.py, a forgotten import line in actions/__init__.py would
silently leave actions unregistered — this catches that at test time rather than
in production.
"""

import json
import os

import pytest

from github import github

pytestmark = pytest.mark.unit

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def _config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestConfigValidation:
    def test_actions_match_handlers(self):
        """Every config.json action has a handler and vice versa."""
        defined_actions = set(_config().get("actions", {}).keys())
        registered_actions = set(github._action_handlers.keys())

        missing_handlers = defined_actions - registered_actions
        extra_handlers = registered_actions - defined_actions

        assert not missing_handlers, f"Missing handlers for actions: {sorted(missing_handlers)}"
        assert not extra_handlers, f"Extra handlers without config: {sorted(extra_handlers)}"

    def test_every_action_declares_a_schema(self):
        """Each action carries the four keys the validator and UI rely on."""
        missing = {
            name: [key for key in ("display_name", "description", "input_schema", "output_schema") if key not in action]
            for name, action in _config().get("actions", {}).items()
        }
        incomplete = {name: keys for name, keys in missing.items() if keys}

        assert not incomplete, f"Actions missing schema keys: {incomplete}"

    def test_required_inputs_are_declared_properties(self):
        """An action cannot require an input it never declares."""
        offenders = {}
        for name, action in _config().get("actions", {}).items():
            schema = action.get("input_schema", {})
            undeclared = set(schema.get("required", [])) - set(schema.get("properties", {}))
            if undeclared:
                offenders[name] = sorted(undeclared)

        assert not offenders, f"Actions requiring undeclared inputs: {offenders}"


class TestAuthConfig:
    def test_uses_platform_oauth(self):
        auth = _config().get("auth", {})
        assert auth.get("type") == "platform"
        assert auth.get("provider") == "github"

    def test_scopes_are_unique_and_sorted_stable(self):
        """No duplicate scopes — a duplicate silently widens the consent screen."""
        scopes = _config().get("auth", {}).get("scopes", [])
        assert len(scopes) == len(set(scopes)), f"Duplicate scopes: {scopes}"

#!/usr/bin/env python3
"""
dev.py -- local developer CLI for autohive-integrations

Usage:
    python dev.py test <name>              Run unit tests for an integration
    python dev.py live <name>              Run live integration tests (needs .env)
    python dev.py validate <name>          Run full pipeline: validate + check + unit tests
    python dev.py fix <name>               Auto-fix lint and formatting issues
    python dev.py test-all                 Run unit tests for ALL integrations

Examples:
    python dev.py test bitly
    python dev.py live hubspot
    python dev.py validate clickup
    python dev.py fix notion
    python dev.py test-all
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TOOLING = ROOT.parent / "autohive-integrations-tooling"
RUFF_CONFIG = TOOLING / "ruff.toml"


def run(cmd: list[str], **kwargs) -> int:
    print(f"\n$ {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, **kwargs)
    return result.returncode


def check_venv():
    if sys.prefix == sys.base_prefix:
        print("[WARN] No virtualenv active. Run: source .venv/bin/activate")
        print("       (or: python -m venv .venv && source .venv/bin/activate && pip install -r requirements-test.txt)")


def check_tooling():
    validate_script = TOOLING / "scripts" / "validate_integration.py"
    if not validate_script.exists():
        print(f"[ERROR] Tooling repo not found at: {TOOLING}")
        print("        Clone it: git clone https://github.com/autohive-ai/autohive-integrations-tooling.git ../autohive-integrations-tooling")
        return False
    return True


def check_integration(name: str) -> bool:
    path = ROOT / name
    if not path.is_dir():
        print(f"[ERROR] Integration '{name}' not found at {path}")
        return False
    return True


def _ruff_flags() -> list[str]:
    """Return --config or --line-length flags depending on what's available."""
    if RUFF_CONFIG.exists():
        return ["--config", str(RUFF_CONFIG)]
    # Tooling repo not cloned locally -- enforce CI line length directly
    return ["--line-length", "120"]


def cmd_test(name: str) -> int:
    """Run unit tests for a single integration."""
    if not check_integration(name):
        return 1
    check_venv()

    req = ROOT / name / "requirements.txt"
    if req.exists():
        code = run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
        if code != 0:
            return code

    return run([sys.executable, "-m", "pytest", name, "-v"])


def cmd_live(name: str) -> int:
    """Run live integration tests -- read-only (requires .env credentials)."""
    if not check_integration(name):
        return 1
    check_venv()

    env_file = ROOT / ".env"
    if not env_file.exists():
        print("[WARN] No .env file found. Copy .env.example and fill in credentials:")
        print("       cp .env.example .env")

    test_file = ROOT / name / "tests" / f"test_{name.replace('-', '_')}_integration.py"
    if not test_file.exists():
        tests_dir = ROOT / name / "tests"
        candidates = list(tests_dir.glob("test_*_integration.py")) if tests_dir.exists() else []
        if not candidates:
            print(f"[ERROR] No integration test file found in {name}/tests/")
            return 1
        test_file = candidates[0]

    req = ROOT / name / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])

    return run([
        sys.executable, "-m", "pytest",
        str(test_file),
        "-m", "integration and not destructive",
        "-v",
    ])


def cmd_live_destructive(name: str) -> int:
    """Run ALL live tests including destructive writes (create/update/delete)."""
    if not check_integration(name):
        return 1

    test_file = ROOT / name / "tests" / f"test_{name.replace('-', '_')}_integration.py"
    if not test_file.exists():
        tests_dir = ROOT / name / "tests"
        candidates = list(tests_dir.glob("test_*_integration.py")) if tests_dir.exists() else []
        if not candidates:
            print(f"[ERROR] No integration test file found in {name}/tests/")
            return 1
        test_file = candidates[0]

    req = ROOT / name / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])

    return run([
        sys.executable, "-m", "pytest",
        str(test_file),
        "-m", "integration",
        "-v",
    ])


def cmd_validate(name: str) -> int:
    """Run full pipeline: install deps -> validate structure -> check code -> unit tests."""
    if not check_integration(name):
        return 1
    if not check_tooling():
        return 1
    check_venv()

    steps = [
        ("Installing dependencies", [sys.executable, "-m", "pip", "install", "-q", "-r", f"{name}/requirements.txt"]),
        ("Validating structure", [sys.executable, str(TOOLING / "scripts" / "validate_integration.py"), name]),
        ("Checking code quality", [sys.executable, str(TOOLING / "scripts" / "check_code.py"), name]),
        ("Running unit tests", [sys.executable, "-m", "pytest", name, "-v"]),
    ]

    failed = []
    for label, cmd in steps:
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")
        code = run(cmd)
        if code != 0:
            failed.append(label)
            print(f"\n[FAIL] {label} (exit {code})")

    print(f"\n{'=' * 60}")
    if failed:
        print(f"[FAIL] Failed steps: {', '.join(failed)}")
        return 1
    else:
        print(f"[PASS] All checks passed for '{name}'")
        return 0


def cmd_fix(name: str) -> int:
    """Auto-fix lint and formatting issues with ruff (line-length 120)."""
    if not check_integration(name):
        return 1

    flags = _ruff_flags()
    run([sys.executable, "-m", "ruff", "check", "--fix", name] + flags)
    run([sys.executable, "-m", "ruff", "format", name] + flags)
    print(f"\n[OK] Lint and format fixes applied to '{name}'")
    return 0


def cmd_test_all() -> int:
    """Run unit tests for all integrations that have test files."""
    check_venv()

    integrations = sorted([
        d.name for d in ROOT.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and not d.name.startswith("__")
        and (d / "tests").exists()
        and list((d / "tests").glob("test_*_unit.py"))
    ])

    print(f"Found {len(integrations)} integrations with unit tests\n")

    passed, failed = [], []
    for name in integrations:
        req = ROOT / name / "requirements.txt"
        if req.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                capture_output=True,
            )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", name, "--tb=short", "-q"],
            capture_output=True, text=True,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"  [{status}] {name}")
        if result.returncode == 0:
            passed.append(name)
        else:
            failed.append(name)

    print(f"\n{'=' * 60}")
    print(f"Results: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print("\nFailed integrations:")
        for name in failed:
            print(f"  - {name}")
        return 1
    return 0


COMMANDS = {
    "test": (cmd_test, 1, "<name>"),
    "live": (cmd_live, 1, "<name>"),
    "live-destructive": (cmd_live_destructive, 1, "<name>"),
    "validate": (cmd_validate, 1, "<name>"),
    "fix": (cmd_fix, 1, "<name>"),
    "test-all": (cmd_test_all, 0, ""),
}

HELP = {
    "test": "Run unit tests (mocked, no credentials needed)",
    "live": "Run live integration tests -- read-only (requires .env)",
    "live-destructive": "Run ALL live tests including destructive writes (requires .env)",
    "validate": "Full pipeline: validate structure + check code + unit tests",
    "fix": "Auto-fix lint and formatting issues (line-length 120)",
    "test-all": "Run unit tests for ALL integrations",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        print("Commands:")
        for cmd, desc in HELP.items():
            fn, nargs, arg = COMMANDS[cmd]
            print(f"  {cmd:<22} {arg:<8}  {desc}")
        return

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"[ERROR] Unknown command: '{cmd}'")
        print(f"        Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    fn, nargs, _ = COMMANDS[cmd]
    args = sys.argv[2:]

    if len(args) != nargs:
        if nargs == 1:
            print(f"[ERROR] '{cmd}' requires an integration name, e.g.: python dev.py {cmd} bitly")
        sys.exit(1)

    os.chdir(ROOT)
    sys.exit(fn(*args))


if __name__ == "__main__":
    main()

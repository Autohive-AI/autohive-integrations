"""Verify an actual HiveUp ZIP imports using only its bundled dependencies."""

import os

# Isolate imports using the current Python executable.
import subprocess  # nosec B404
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

pytestmark = pytest.mark.integration


def test_deployment_zip_contains_importable_sdk(tmp_path):
    package = os.environ.get("PROCORE_PACKAGE_PATH")
    if not package:
        pytest.skip("Build with hiveup package and set PROCORE_PACKAGE_PATH to the resulting ZIP")
    with ZipFile(Path(package)) as archive:
        assert archive.testzip() is None
        assert {"config.json", "procore.py", "dependencies/autohive_integrations_sdk/__init__.py"} <= set(
            archive.namelist()
        )
        # Test only trusted artifacts built from this checkout, never downloaded ZIPs.
        archive.extractall(tmp_path)
    check = (
        "import sys; "
        "sys.path[:0] = [sys.argv[1], sys.argv[1] + '/dependencies']; "
        "from procore import procore; "
        "from autohive_integrations_sdk import ExecutionContext; "
        "assert procore is not None and ExecutionContext is not None"
    )
    # Fixed executable and arguments, no shell.
    result = subprocess.run(  # nosec B603
        [sys.executable, "-I", "-S", "-c", check, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr

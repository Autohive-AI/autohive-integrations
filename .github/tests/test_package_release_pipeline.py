"""Run release selection against real Git history without GitHub or cloud writes."""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class PackageReleasePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "release-test@example.com")
        self.integration("first", "1.0.0")
        self.integration("second", "1.0.0")
        self.integration("unchanged", "1.0.0")
        self.base = self.commit("baseline")
        self.integration("first", "1.0.1")
        self.before = self.commit("first bump; packaging run skipped")
        self.integration("second", "1.0.1")
        self.current = self.commit("second bump")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake_gh = self.bin / "gh"
        fake_gh.write_text('#!/bin/bash\nprintf "%s\\n" "$GH_HISTORY"\nexit "${GH_HISTORY_EXIT:-0}"\n')
        fake_gh.chmod(0o755)
        # Extract the real workflow's selection step. No copy of its logic is tested.
        workflow = Path(__file__).resolve().parents[1] / "workflows" / "package-and-release.yml"
        source = workflow.read_text()
        start = source.index("        run: |", source.index("      - name: Resolve release contents"))
        script = source[start:].split("\n", 1)[1].split("\n      - name:", 1)[0]
        self.script = textwrap.dedent(script)
        hiveup = shutil.which("hiveup")
        if not hiveup:
            raise RuntimeError("Install HiveUp and add its virtualenv bin directory to PATH.")
        self.environment = dict(
            os.environ,
            PATH=f"{self.bin}:{Path(hiveup).resolve().parent}:{os.environ['PATH']}",
            EVENT_NAME="push",
            EVENT_BEFORE=self.before,
            GITHUB_SHA=self.current,
            GITHUB_REF_NAME="master",
            GITHUB_REPOSITORY="example/integrations",
            GH_HISTORY=f"{self.base}\tsuccess",
            RUNNER_TEMP=str(self.root),
            GITHUB_OUTPUT=str(self.root / "outputs"),
        )

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.repository, check=True, capture_output=True, text=True
        ).stdout.strip()

    def integration(self, name, version):
        path = self.repository / name
        path.mkdir(exist_ok=True)
        (path / "config.json").write_text(json.dumps({"name": name, "version": version}))

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_selection(self):
        return subprocess.run(
            ["bash", "-c", self.script],
            cwd=self.repository,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_surviving_run_includes_bumps_from_skipped_intermediate_merge(self):
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["first", "second"])
        self.assertIn(f"previous_commit_sha={self.base}", (self.root / "outputs").read_text())

    def test_history_api_failure_blocks_incomplete_release(self):
        self.environment.update(GH_HISTORY="", GH_HISTORY_EXIT="1")
        result = self.run_selection()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "integration-paths.txt").exists())
        self.assertFalse((self.root / "outputs").exists())

    def test_first_successful_run_includes_earlier_failed_merge(self):
        self.environment["GH_HISTORY"] = f"{self.current}\tpending\n{self.before}\tfailure"
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["first", "second"])
        self.assertIn(f"previous_commit_sha={self.base}", (self.root / "outputs").read_text())

    def test_manual_selection_creates_snapshot_without_reading_push_history(self):
        self.environment.update(EVENT_NAME="workflow_dispatch", MANUAL_SELECTION="second", GH_HISTORY_EXIT="1")
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["second"])
        self.assertIn("release_kind=snapshot", (self.root / "outputs").read_text())

    def test_no_version_bumps_creates_no_release(self):
        self.environment["GH_HISTORY"] = ""
        self.environment["EVENT_BEFORE"] = self.current
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("has_changes=false", (self.root / "outputs").read_text())


if __name__ == "__main__":
    if not shutil.which("hiveup"):
        raise SystemExit("Install the release tooling checkout and add its virtualenv bin directory to PATH.")
    unittest.main()

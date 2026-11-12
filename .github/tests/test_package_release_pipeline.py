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
        self.before = self.commit("first bump")
        self.integration("second", "1.0.1")
        self.current = self.commit("second bump")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake_gh = self.bin / "gh"
        fake_gh.write_text("#!/bin/bash\nprintf 'gh should not be called for release selection\\n' >&2\nexit 1\n")
        fake_gh.chmod(0o755)
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

    def test_push_selects_only_version_bumps_in_current_push_range(self):
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["second"])
        outputs = (self.root / "outputs").read_text()
        self.assertIn(f"previous_commit_sha={self.before}", outputs)
        self.assertIn("release_kind=incremental", outputs)

    def test_push_can_package_multiple_bumps_from_current_push_range(self):
        self.environment["EVENT_BEFORE"] = self.base
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["first", "second"])

    def test_no_version_bumps_creates_no_release(self):
        self.git("commit", "--allow-empty", "-q", "-m", "no version bumps")
        nochange = self.git("rev-parse", "HEAD")
        self.environment.update(GITHUB_SHA=nochange, EVENT_BEFORE=self.current)
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("has_changes=false", (self.root / "outputs").read_text())

    def test_manual_selection_creates_snapshot_without_reading_push_history(self):
        self.environment.update(EVENT_NAME="workflow_dispatch", MANUAL_SELECTION="second")
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "integration-paths.txt").read_text().splitlines(), ["second"])
        outputs = (self.root / "outputs").read_text()
        self.assertIn(f"previous_commit_sha={self.before}", outputs)
        self.assertIn("release_kind=snapshot", outputs)

    def test_manual_all_selection_stays_snapshot(self):
        self.environment.update(EVENT_NAME="workflow_dispatch", MANUAL_SELECTION="all")
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "integration-paths.txt").read_text().splitlines(),
            ["first", "second", "unchanged"],
        )
        self.assertIn("release_kind=snapshot", (self.root / "outputs").read_text())


class ReleaseTitleTests(unittest.TestCase):
    def test_publish_limits_title_and_keeps_all_assets(self):
        workflow = Path(__file__).resolve().parents[1] / "workflows" / "package-and-release.yml"
        publish = workflow.read_text().split("      - name: Publish GitHub Release\n", 1)[1]
        script = textwrap.dedent(publish.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0])
        names = [f"Integration {index}" for index in range(7)]
        cases = [
            (names[:5], ", ".join(names[:5])),
            (names, ", ".join(names[:5]) + " and 2 more"),
            (["A" * 160, "B" * 160], "A" * 160 + " and 1 more"),
            (["A" * 300], None),
        ]
        for display_names, expected_summary in cases:
            with self.subTest(expected_summary=expected_summary), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [f"package-{index}" for index in range(len(display_names))]
                for path, name in zip(paths, display_names):
                    (root / path).mkdir()
                    (root / path / "config.json").write_text(json.dumps({"display_name": name}))
                (root / "integration-paths.txt").write_text("\n".join(paths) + "\n")
                fake_gh = root / "gh"
                fake_gh.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
                fake_gh.chmod(0o755)
                result = subprocess.run(
                    ["bash", "-c", script],
                    cwd=root,
                    env=dict(
                        os.environ,
                        PATH=f"{root}:{os.environ['PATH']}",
                        RUNNER_TEMP=directory,
                        GITHUB_OUTPUT=str(root / "outputs"),
                        GITHUB_STEP_SUMMARY=str(root / "summary"),
                        GITHUB_RUN_ID="123",
                        GITHUB_RUN_ATTEMPT="1",
                        GITHUB_SHA="0123456789abcdef",
                        GITHUB_SERVER_URL="https://github.com",
                        GITHUB_REPOSITORY="example/integrations",
                        GITHUB_ACTOR="test",
                        RELEASE_AUTHOR="Test Author",
                        RELEASE_KIND="snapshot",
                    ),
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                args = result.stdout.splitlines()
                title = args[args.index("--title") + 1]
                if expected_summary is None:
                    expected_title = f"Integration releases - {len(paths)} integrations - 0123456789ab"
                else:
                    expected_title = f"Integration releases - Test Author - {expected_summary} - 0123456789ab"
                self.assertEqual(title, expected_title)
                self.assertLessEqual(len(title), 256)
                self.assertEqual(
                    args[3 : args.index("--repo")],
                    ["dist/autohive-manifest.json", *[f"dist/{path}.zip" for path in paths]],
                )


if __name__ == "__main__":
    if not shutil.which("hiveup"):
        raise SystemExit("Install the release tooling checkout and add its virtualenv bin directory to PATH.")
    unittest.main()

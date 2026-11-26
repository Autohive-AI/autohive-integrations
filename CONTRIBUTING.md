# Contributing

Guide for integration authors submitting PRs to this repository.

## SDK baseline

For new integrations and explicit SDK upgrades, use released `autohive-integrations-sdk~=2.1.0` (`>=2.1.0,<2.2.0`). Existing integrations keep their own `requirements.txt`; documentation work and private-to-public moves do not implicitly upgrade them. The SDK's `master` branch tracks 3.x development. Use the [maintained 2.1.0 guides and samples](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0) and [canonical SDK skills](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0/skills) for released-contract guidance.

Successful SDK 2.x HTTP calls return `FetchResponse`; read its `.data`, `.status`, and `.headers`. Configured auth uses `{"auth_type": "Custom", "credentials": {...}}`, with `auth.fields` describing the inner credentials. SDK 2.0.1 corrected that validation boundary; keep required credential fields. SDK 2.1.0 adds `.headers` to `HTTPError` and `RateLimitError`, not new retries. Match exception-header names case-insensitively and disclose only selected provider values, not the full mapping. See the [HTTP error guidance](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md).

## CI/CD Checks

Pull requests run integration validation and PR-title checks; a companion workflow posts validation comments from the base repository so fork PRs do not need write permissions.

### 1. Validate Integration (`validate-integration.yml`)

Uses the [autohive-integrations-tooling](https://github.com/autohive-ai/autohive-integrations-tooling) composite action to validate changed integrations, with each integration's dependencies isolated. Its five result groups are:

| Check | What It Does |
|-------|-------------|
| **Structure** | Folder name, required files, `config.json` schema, `__init__.py`, `requirements.txt`, `tests/`, icon size, unused scopes |
| **Code** | `pip install`, Python syntax, import resolution, JSON validity, ruff lint, ruff format, bandit security scan, pip-audit, config-code sync |
| **Tests** | Discovers canonical `test_*_unit.py` files and runs mocked unit tests with coverage; live tests are excluded |
| **README** | Verifies the main `README.md` was updated when a new integration is added |
| **Version** | Checks integration version changes against the PR base; documentation-only changes do not require a version bump |

The Code group also checks SDK fetch-response usage. Structure/schema and fetch checks are bounded checks, not proof of every runtime contract. Review skipped checks and warnings as well as failures. Results are posted as a sticky PR comment with a summary table:

- ✅ **Passed** — all checks passed
- ⚠️ **Passed with warnings** — no errors, but issues to review
- ❌ **Failed** — errors that must be fixed before merge

Each check includes expandable output with full details.

### 2. Pull Request Title (`pr.yml`)

Validates that PR titles follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope)?: description
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Examples:**
```
feat: add Netlify integration
fix(netlify): handle rate limit errors
docs: update Netlify README with auth setup
```

## Local Validation

Install the Python **HiveUp** CLI with Python 3.13+ using the [Tooling local-build instructions](https://github.com/autohive-ai/autohive-integrations-tooling#install-hiveup-from-a-local-build). HiveUp is not published to PyPI. Installing only Tooling's development dependencies does not install the CLI. The legacy scripts and .NET CLI are compatibility paths, not the default workflow.

From this repository root:

```bash
hiveup --version
hiveup validate --base-ref <base-ref> my-integration
hiveup test my-integration
```

Replace `<base-ref>` with the actual fetched PR target ref, such as `origin/master` for a PR targeting this repository's `master`. A supplied ref must resolve locally. `validate` includes unit tests; `test` is the focused unit-test command. For non-PR work, omit `--base-ref` and report that history-aware README/version checks were skipped.

For changed integrations or a focused check:

```bash
hiveup validate --changed --base-ref <base-ref>
hiveup check fetch my-integration
```

HiveUp prepares isolated environments from each integration's existing `requirements.txt`. A successful exit can include warnings or skipped tests, so inspect the actual test counts and skipped checks. Do not install all integrations into one shared environment to validate them.

### Quick fixes

```bash
hiveup validate --only lint,format --fix my-integration
hiveup validate --base-ref <base-ref> my-integration
```

HiveUp uses its bundled CI Ruff configuration. If using standalone Ruff with a sibling Tooling checkout, pass `--config ../autohive-integrations-tooling/ruff.toml` to both lint and format.

## Running Tests

Unit tests and integration tests are **run separately** — they use different file naming, markers, and discovery rules so they never interfere with each other.

| | Unit tests | Integration tests |
|---|---|---|
| **File naming** | `test_*_unit.py` | `test_*_integration.py` |
| **Marker** | `@pytest.mark.unit` | `@pytest.mark.integration` |
| **Auto-discovered** | Yes (via `python_files` in `pyproject.toml`) | No — must pass the file path explicitly |
| **Runs in CI** | Yes | No |
| **Needs credentials** | No (fully mocked) | Yes (real API calls) |
| **Default `pytest`** | ✅ Selected by `-m unit` in `addopts` | ❌ Excluded by `-m unit` in `addopts` |

Tests use [pytest](https://docs.pytest.org/) and run from the repo root. Prefer `hiveup test <integration>` for isolated unit tests. Direct pytest and live tests need a separately prepared environment with that integration's pinned requirements, as below; the CLI's own environment is not a shared integration environment.

### Prerequisites

Python 3.13+ is required (the SDK depends on it). Create a venv and install test dependencies:

```bash
cd autohive-integrations
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -r requirements-test.txt
```

Each integration pins its own SDK version in its `requirements.txt`. Install the dependencies for the integration you want to test:

```bash
uv pip install -r hackernews/requirements.txt
```

If you don't have [uv](https://docs.astral.sh/uv/), you can use any Python 3.13+ interpreter directly:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
pip install -r hackernews/requirements.txt
```

### Running unit tests

Unit tests are mocked — no API credentials or network access needed. They are auto-discovered by pytest from `test_*_unit.py` files.

```bash
# Run isolated unit tests, using each integration's own requirements
hiveup test hackernews
hiveup test bitly notion

# Run a specific file in the prepared hackernews environment
python -m pytest hackernews/tests/test_hackernews_unit.py -v
```

The default `pytest` command only runs tests marked `unit` (configured in `pyproject.toml`). Avoid a repository-wide direct pytest run unless all selected integrations' dependencies are compatible; sharing an SDK range alone is not sufficient. HiveUp warns and skips integrations without canonical unit files; a zero exit code is not evidence that those tests ran.

### Running integration tests

Integration tests call real APIs and require credentials. They are **not** auto-discovered — you must pass the test file path explicitly and override the marker filter.

Set up a `.env` file in the repo root (see `.env.example` for the template):

```bash
cp .env.example .env
# Edit .env and add your test credentials
```

With Perplexity's existing requirements and the repository test dependencies installed, pass the file path and exclude destructive tests by default:

```bash
# Run integration tests for one integration
python -m pytest perplexity/tests/test_perplexity_integration.py -m "integration and not destructive"
```

> **Why the explicit file path?** `pyproject.toml` restricts `python_files` to `test_*_unit.py`, so `pytest -m integration perplexity/` will **not** discover `test_*_integration.py` files. You must name the file directly.

To run both unit and read-only integration tests together in that prepared environment:

```bash
python -m pytest perplexity/tests/test_perplexity_unit.py perplexity/tests/test_perplexity_integration.py -m "(unit or integration) and not destructive"
```

Integration tests should `pytest.skip()` when required credentials are missing. Run destructive tests only deliberately against a dedicated test account, with an explicit file and `-m "integration and destructive"`. Keep secrets in an uncommitted `.env`, not tracked test files. Add blank entries for every credential or optional test-resource environment variable to root `.env.example` when adding or changing live tests.

### Coverage

`hiveup test <integration>` includes coverage in the integration's isolated environment. For a targeted direct run, use the prepared environment for that integration:

```bash
# Coverage for a single integration (unit tests only)
python -m pytest --cov=hackernews --cov-report=term-missing hackernews/
```

Coverage is configured in `pyproject.toml` to exclude test files — only integration source code is measured.

### Writing tests for a new integration

#### Unit tests

Unit test files go in `<integration>/tests/test_<name>_unit.py`. This naming is required for auto-discovery.

```python
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from my_integration import my_integration

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context(make_context):
    return make_context(auth={"auth_type": "Custom", "credentials": {"api_key": "test_key"}})


class TestMyAction:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": "value"})
        result = await my_integration.execute_action("my_action", {"input": "x"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["data"] == "value"
```

Adapt the action, inputs, output body, and credential names to `config.json`. This example assumes a required custom `api_key`; `auth.fields` validates the inner credentials, not the envelope. Pair it with a missing-required-credential test asserting `VALIDATION_ERROR`, `result.result["source"] == "auth"`, and `ctx.fetch.assert_not_awaited()`. For HTTP failures, use `HTTPError` or `RateLimitError` as the mock's `side_effect`, not a successful `FetchResponse` with an error status.

#### Integration tests (optional)

Integration test files go in `<integration>/tests/test_<name>_integration.py`. They are excluded from CI by both naming and marker.

```python
import pytest
import pytest_asyncio
from autohive_integrations_sdk import ExecutionContext, ResultType

from my_integration import my_integration

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_context(env_credentials):
    api_key = env_credentials("MY_API_KEY")
    if not api_key:
        pytest.skip("MY_API_KEY not set")
    auth = {"auth_type": "Custom", "credentials": {"api_key": api_key}}
    async with ExecutionContext(auth=auth) as context:
        yield context


class TestMyAction:
    async def test_real_api_call(self, live_context):
        result = await my_integration.execute_action("my_action", {"input": "x"}, live_context)
        assert result.type == ResultType.ACTION
        assert "data" in result.result.data
```

The real SDK context preserves HTTP errors, response parsing, OAuth injection, and session cleanup. `make_context` is a mock factory, not a live transport. Use `{}` for no auth, or `{"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}` for platform OAuth, and adapt credential keys to the integration's config.

#### Shared conventions

- Use `pytestmark = pytest.mark.unit` at module level for mocked tests
- Use `pytestmark = pytest.mark.integration` for tests that hit real APIs
- Mock successful SDK 2.x fetches with `FetchResponse`; inspect the integration's pinned contract for SDK 1.x
- Test both success and error paths
- Also add a `conftest.py` in the integration's `tests/` dir:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

Keep the integration-root `__init__.py` empty, except where an existing layout intentionally requires otherwise. When copying the standalone SDK sample into this repository, omit its local `pytest.ini`: inherit root `pyproject.toml` so shared `make_context` and `env_credentials` fixtures remain discoverable. See the [unit-test skill](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/skills/writing-unit-tests/SKILL.md) and [live-test skill](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/skills/writing-integration-tests/SKILL.md) for full conventions.

### Test markers

| Marker | Purpose | Needs credentials? | Runs in CI? | Auto-discovered? |
|--------|---------|-------------------|-------------|-----------------|
| `unit` | Mocked tests, no network | No | Yes | Yes (`test_*_unit.py`) |
| `integration` | Real API calls | Yes (via `.env`) | No | No (explicit file path) |
| `destructive` | Live tests that create, update, or delete data; explicit opt-in | Yes (dedicated test account) | No | No (explicit file path and marker filter) |

## SDK Upgrades

For an explicitly scoped SDK upgrade, use the SDK's [upgrade skill](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/skills/upgrading-sdk-v2/SKILL.md). The [skills directory](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0/skills) contains setup instructions and the canonical build, test, migration, and review guidance. Do not change an existing pin just to reconcile README prose.

## Integration Structure

See the SDK's [Integration Structure Reference](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/integration_structure.md) for directory layouts, required files, and the full `config.json` schema. The [Building Your First Integration](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/building_your_first_integration.md) tutorial covers the development workflow end-to-end, and [samples/template/](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0/samples/template) provides a starter.

## Pull Request Process

1. **Create a branch** following `<type>/<issue-number>/<short-description>` (for example, `feat/42/my-integration`)
2. **Add your integration** following the structure in the SDK docs
3. **Read and follow the [Integration Engineering Charter](integration-engineering-charter.md)**
4. **Run validation locally** before pushing
5. **Update the main README.md** — add your integration to the list
6. **Complete the [pull request template](.github/PULL_REQUEST_TEMPLATE.md)**
7. **Use a conventional commit PR title**
8. **Keep PRs focused** — integration feature work normally changes one integration; a dependency refresh may bump several integrations in one PR for bulk deployment.

All CI checks must pass before merge.

## Deployment packages

Every merge to `master` runs `Package integrations for Autohive`. The workflow
compares `config.json` versions in the current push range and creates a GitHub
Release only when at least one integration is new or has a higher semantic
version. The release contains only those changed integration ZIPs plus an
integrity manifest. Manual workflow runs remain available for a selected or
full snapshot repackage.

Each push gets its own packaging run so rapid merges do not replace pending
release jobs. If packaging fails, rerun the failed workflow run for that merge.
The next merge packages only the versions changed by that next push; it does not
create or require a full bootstrap release.
Pull-request validation uses the floating Tooling action `@v2`; release
packaging checks out the same floating `v2` ref. These are not immutable
`2.5.0` pins. See the workflow files for the configured refs and the
[Tooling versioning policy](https://github.com/autohive-ai/autohive-integrations-tooling#versioning).

Runtime dependency changes, including SDK updates in `requirements.txt`, alter
the deployable ZIP and therefore require a matching `config.json` version bump.
Documentation-only and test-only changes do not require a release version bump.

A release is a monorepo deployment batch, not an integration version tag. Each
manifest entry retains its own `config.json` version and repository folder
path. Autohive stores a release cursor, pulls every later batch, and keeps the
newest entry if the same repository path occurs in multiple releases.

The workflow has GitHub `contents: write` for releases. It does not contain
an Autohive URL or deploy credential. Autohive must pull, verify, and deploy the
assets from its authenticated Admin UI, and deployment never publishes a
version to end users.

Pull-request validation remains the quality gate. Release packaging deliberately
uses HiveUp's `--skip-validate` mode so a later lint-rule change cannot prevent
repackaging an integration that is already on the protected default branch;
package structure and entry-point safety checks still run during the build.

The top-level integration folder is the repository identity; no separate source
ID is maintained. A config-name change within the same folder is shown as a
reviewed rename in Autohive Admin and deploys the next version to a newly named
Lambda. Moving the folder requires a one-time reviewed rebind. Release
configuration is only needed to request `zip`, `container`, or the default
`preserve` package type; Autohive applies its server-side conversion policy
before deployment. A reviewed folder move also creates a new Lambda for the
existing Autohive backend.

For the dependency-refresh procedure, release cursor behavior, and how Admin
handles manually renamed integrations, see [Integration release workflow](docs/integration-release-workflow.md).

# Contributing

Guide for integration authors submitting PRs to this repository.

## CI/CD Checks

Every pull request runs two automated workflows:

### 1. Validate Integration (`validate-integration.yml`)

Uses the [autohive-integrations-tooling](https://github.com/autohive-ai/autohive-integrations-tooling) composite action to validate changed integrations. Runs three checks:

| Check | What It Does |
|-------|-------------|
| **Structure** | Folder name, required files, `config.json` schema, `__init__.py`, `requirements.txt`, `tests/`, icon size, unused scopes |
| **Code** | `pip install`, Python syntax, import resolution, JSON validity, ruff lint, ruff format, bandit security scan, pip-audit, config-code sync |
| **README** | Verifies the main `README.md` was updated when a new integration is added |

Results are posted as a sticky PR comment with a summary table:

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

You can run the same checks locally before pushing. Install the tooling repo and run:

Clone both repos side by side:

```
parent-dir/
├── autohive-integrations-tooling/
└── autohive-integrations/
```

Set up a Python 3.13+ environment in the tooling repo and install dev dependencies. For example, using [uv](https://docs.astral.sh/uv/):

```bash
cd autohive-integrations-tooling
uv python install 3.13
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

Any other Python environment manager (venv, pyenv, conda, etc.) works too — just ensure Python 3.13+ and the packages from `requirements-dev.txt` are installed.

Then run the checks from the integrations repo root:

```bash
cd ../autohive-integrations
python ../autohive-integrations-tooling/scripts/validate_integration.py my-integration
python ../autohive-integrations-tooling/scripts/check_code.py my-integration
```

### Quick fixes

```bash
# Auto-fix lint issues
ruff check --fix my-integration

# Auto-format code
ruff format my-integration
```

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

Tests use [pytest](https://docs.pytest.org/) and run from the repo root. They use the same Python environment as the tooling (see [Local Validation](#local-validation) above).

### Prerequisites

Python 3.13+ is required (the SDK depends on it). Create a venv and install test dependencies:

```bash
cd autohive-integrations
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -r requirements-test.txt
```

Each integration pins its own SDK version in its `requirements.txt`. Install the dependencies for the integration(s) you want to test:

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
# Run unit tests for a single integration
pytest hackernews/

# Run a specific test file
pytest hackernews/tests/test_hackernews_unit.py

# Run all unit tests (only if all integrations share the same SDK version)
pytest

# Verbose output
pytest hackernews/ -v
```

If integrations pin different SDK versions, run them separately to ensure each uses its own pinned version:

```bash
uv pip install -r bitly/requirements.txt
pytest bitly/

uv pip install -r notion/requirements.txt
pytest notion/
```

The default `pytest` command only runs tests marked `unit` (configured in `pyproject.toml`).

### Running integration tests

Integration tests call real APIs and require credentials. They are **not** auto-discovered — you must pass the test file path explicitly and override the marker filter.

Set up a `.env` file in the repo root (see `.env.example` for the template):

```bash
cp .env.example .env
# Edit .env and add your test credentials
```

Then run by passing the file path directly with `-m integration`:

```bash
# Run integration tests for one integration
pytest perplexity/tests/test_perplexity_integration.py -m integration
```

> **Why the explicit file path?** `pyproject.toml` restricts `python_files` to `test_*_unit.py`, so `pytest -m integration perplexity/` will **not** discover `test_*_integration.py` files. You must name the file directly.

To run both unit and integration tests together:

```bash
pytest perplexity/tests/test_perplexity_unit.py perplexity/tests/test_perplexity_integration.py -m "unit or integration"
```

Integration tests will `pytest.skip()` if the required environment variables are missing.

### Coverage

```bash
# Coverage for a single integration (unit tests only)
pytest --cov=hackernews hackernews/

# Coverage for multiple integrations
pytest --cov=hackernews --cov=bitly hackernews/ bitly/

# All tested integrations with line-level detail
pytest --cov=hackernews --cov=bitly --cov=nzbn --cov=notion --cov=shopify-customer
```

Coverage is configured in `pyproject.toml` to exclude test files — only integration source code is measured.

### Writing tests for a new integration

#### Unit tests

Unit test files go in `<integration>/tests/test_<name>_unit.py`. This naming is required for auto-discovery.

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from my_integration.my_integration import my_integration

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test_key"}}
    return ctx


class TestMyAction:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {"data": "value"}
        result = await my_integration.execute_action("my_action", {"input": "x"}, mock_context)
        assert result.result.data["data"] == "value"
```

#### Integration tests (optional)

Integration test files go in `<integration>/tests/test_<name>_integration.py`. They are excluded from CI by both naming and marker.

```python
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context():
    api_key = os.environ.get("MY_API_KEY", "")
    if not api_key:
        pytest.skip("MY_API_KEY not set")
    # ... set up context with real credentials ...


class TestMyAction:
    async def test_real_api_call(self, live_context):
        result = await my_integration.execute_action("my_action", {"input": "x"}, live_context)
        assert "data" in result.result.data
```

#### Shared conventions

- Use `pytestmark = pytest.mark.unit` at module level for mocked tests
- Use `pytestmark = pytest.mark.integration` for tests that hit real APIs
- Mock `context.fetch` return values to simulate API responses
- Test both success and error paths
- Also add a `conftest.py` in the integration's `tests/` dir:

```python
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
```

### Test markers

| Marker | Purpose | Needs credentials? | Runs in CI? | Auto-discovered? |
|--------|---------|-------------------|-------------|-----------------|
| `unit` | Mocked tests, no network | No | Yes | Yes (`test_*_unit.py`) |
| `integration` | Real API calls | Yes (via `.env`) | No | No (explicit file path) |

## SDK Upgrades

When upgrading an integration to a new SDK major version, the SDK repo provides agent skills to automate the migration. See the [skills directory](https://github.com/autohive-ai/integrations-sdk/tree/master/skills) in the SDK repo for setup instructions and available skills.

## Integration Structure

See the SDK's [Integration Structure Reference](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/integration_structure.md) for directory layouts, required files, and the full `config.json` schema. The [Building Your First Integration](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/building_your_first_integration.md) tutorial covers the development workflow end-to-end, and [samples/template/](https://github.com/autohive-ai/integrations-sdk/tree/master/samples/template) provides a ready-to-copy starter.

## Pull Request Process

1. **Create a branch** following conventional naming (`feat/my-integration`)
2. **Add your integration** following the structure in the SDK docs
3. **Run validation locally** before pushing
4. **Update the main README.md** — add your integration to the list
5. **Use a conventional commit PR title**
6. **One integration per PR** — keep PRs focused

All CI checks must pass before merge.

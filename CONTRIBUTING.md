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

Unit tests are mocked — no API credentials or network access needed.

```bash
# Run all unit tests (if all integrations share the same SDK version)
pytest

# Run tests for a single integration
pytest hackernews/
```

If integrations pin different SDK versions, run them separately to ensure each uses its own pinned version:

```bash
uv pip install -r bitly/requirements.txt
pytest bitly/

uv pip install -r notion/requirements.txt
pytest notion/
```

Other useful commands:

```bash
# Run a specific test file
pytest hackernews/tests/test_hackernews_unit.py

# Verbose output
pytest hackernews/ -v
```

The default `pytest` command only runs tests marked `unit` (configured in `pyproject.toml`).

### Running integration tests

Integration tests call real APIs and require credentials. Set up a `.env` file in the repo root (see `.env.example` for the template):

```bash
cp .env.example .env
# Edit .env and add your test credentials
```

Then run with the `integration` marker:

```bash
# Run integration tests for one integration
pytest -m integration hackernews/

# Run both unit and integration tests
pytest -m "unit or integration" hackernews/
```

Integration tests will `pytest.skip()` if the required environment variables are missing.

### Coverage

```bash
# Coverage for a single integration
pytest --cov=hackernews hackernews/

# Coverage for multiple integrations
pytest --cov=hackernews --cov=bitly hackernews/ bitly/

# All tested integrations with line-level detail
pytest --cov=hackernews --cov=bitly --cov=nzbn --cov=notion --cov=shopify-customer
```

Coverage is configured in `pyproject.toml` to exclude test files — only integration source code is measured.

### Writing tests for a new integration

New test files go in `<integration>/tests/test_<name>_unit.py`. Follow this template:

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

Key conventions:
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

| Marker | Purpose | Needs credentials? | Runs by default? |
|--------|---------|-------------------|-----------------|
| `unit` | Mocked tests, no network | No | Yes |
| `integration` | Real API calls | Yes (via `.env`) | No |

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

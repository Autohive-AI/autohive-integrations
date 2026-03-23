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

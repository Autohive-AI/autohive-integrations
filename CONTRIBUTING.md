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

### Basic structure

```
my-integration/
├── __init__.py              # Minimal — only import and __all__
├── config.json              # Integration configuration
├── my_integration.py        # Main implementation (entry_point)
├── icon.png or icon.svg     # Integration icon (512x512 pixels)
├── requirements.txt         # Dependencies (must include autohive-integrations-sdk)
├── README.md                # Documentation
└── tests/
    ├── __init__.py          # Can be empty
    ├── context.py           # Import setup
    └── test_my_integration.py
```

### Modular structure

For integrations with many actions, split them into an `actions/` directory. The `__init__.py` in the root is optional for modular integrations.

```
my-integration/
├── config.json
├── my_integration.py        # Main entry point — registers actions
├── helpers.py               # Shared utilities (optional)
├── icon.png or icon.svg
├── requirements.txt
├── README.md
├── actions/
│   ├── __init__.py
│   ├── posts.py             # Action group
│   ├── comments.py          # Action group
│   └── insights.py          # Action group
└── tests/
    ├── __init__.py
    ├── context.py
    └── test_my_integration.py
```

See the [tooling repo's INTEGRATION_CHECKLIST.md](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/INTEGRATION_CHECKLIST.md) for the full checklist with examples.

## Pull Request Process

1. **Create a branch** following conventional naming (`feat/my-integration`)
2. **Add your integration** following the folder structure above
3. **Run validation locally** before pushing
4. **Update the main README.md** — add your integration to the list
5. **Use a conventional commit PR title**
6. **One integration per PR** — keep PRs focused

All CI checks must pass before merge.

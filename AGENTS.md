# Agent Instructions for Autohive Integrations

## Documentation — read before writing code

Do NOT guess the integration structure or conventions. Read the existing documentation first:

- **[Building Your First Integration](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/building_your_first_integration.md)** — end-to-end tutorial and development workflow
- **[Integration Structure Reference](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/integration_structure.md)** — directory layout, required files, `config.json` schema
- **[Patterns](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/patterns.md)** — common patterns and best practices
- **[Starter Template](https://github.com/autohive-ai/integrations-sdk/tree/master/samples/template)** — copy this as the starting point for any new integration
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — PR process, local validation setup, and CI details for this repo
- **[Tooling README](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/README.md)** — validation scripts and CI pipeline
- **[Local Development](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/LOCAL_DEVELOPMENT.md)** — local development workflow and documentation map
- **[Integration Checklist](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/INTEGRATION_CHECKLIST.md)** — manual review checklist

## Local validation — run before every push

Run the tooling validation scripts locally before pushing. The CI will run the same checks, but catching issues locally is faster.

Set up the tooling repo side by side (see [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions), then run:

```bash
python ../autohive-integrations-tooling/scripts/validate_integration.py <integration-name>
python ../autohive-integrations-tooling/scripts/check_code.py <integration-name>
```

Auto-fix lint and formatting issues:

```bash
ruff check --fix <integration-name>
ruff format <integration-name>
```

## Git workflow

### Commits

- Use **[Conventional Commits](https://www.conventionalcommits.org/)** for all commit messages and PR titles.
- Format: `type(scope): description` — e.g. `feat(slack): add reaction support`, `fix(gmail): handle empty attachments`
- Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### Branching

- Branch names must follow the format: `<type>/<issue-number>/<short-description>`
  - Examples: `feat/42/add-slack-reactions`, `fix/108/gmail-empty-attachments`, `docs/55/update-readme`
  - The `<type>` prefix should match conventional commit types.

### Issues

- Every task must have a corresponding GitHub issue in this repo. If one does not exist, create it before starting work.
- Reference the issue in your PR description (e.g. `Closes #42`).

### History

- **Do not force-push** unless absolutely necessary. Add new commits to the branch instead of rewriting history.
- Keep commits focused — one logical change per commit.

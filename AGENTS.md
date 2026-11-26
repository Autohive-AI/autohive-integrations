# Agent Instructions for Autohive Integrations

## Documentation — read before writing code

Do NOT guess the integration structure or conventions. Read the existing documentation first:

- **[Building Your First Integration](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/building_your_first_integration.md)** — end-to-end tutorial and development workflow for released SDK 2.1.0
- **[Integration Structure Reference](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/integration_structure.md)** — directory layout, required files, `config.json` schema
- **[Patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md)** — common patterns and best practices
- **[Starter Template](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0/samples/template)** — starting point for a new integration; omit its standalone `pytest.ini` here so repository-root fixtures remain discoverable
- **[SDK Skills](https://github.com/autohive-ai/integrations-sdk/tree/release/2.1.0/skills)** — canonical build, test, upgrade, migration, and review guidance; do not duplicate these skills in this repo
- **[Integration Engineering Charter](integration-engineering-charter.md)** — engineering principles, author commitment, and reviewer standard for integration PRs
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — PR process, local validation setup, and CI details for this repo
- **[Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md)** — author commitment and review standard that must be completed for PRs
- **[Tooling README](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/README.md)** — Python HiveUp installation and CI pipeline
- **[Local Development](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/LOCAL_DEVELOPMENT.md)** — local development workflow and documentation map
- **[Integration Checklist](https://github.com/autohive-ai/autohive-integrations-tooling/blob/master/INTEGRATION_CHECKLIST.md)** — manual review checklist

For new integrations and explicitly scoped SDK upgrades, use `autohive-integrations-sdk~=2.1.0`. Preserve existing pins and behavior during documentation-only work or private-to-public moves. SDK `master` tracks 3.x development, not the released 2.1.0 contract.

## Local validation — run before every push

Install the Python 3.13+ HiveUp CLI using the [local-build instructions](https://github.com/autohive-ai/autohive-integrations-tooling#install-hiveup-from-a-local-build); HiveUp is not published to PyPI. Legacy scripts and the .NET CLI are compatibility paths, not the default workflow.

From this repository root, run the following with the actual fetched PR target ref in place of `<base-ref>`:

```bash
hiveup --version
hiveup validate --base-ref <base-ref> <integration-name>
hiveup test <integration-name>
```

`validate` includes isolated unit tests. Check counts, warnings, and skips; a zero exit code can include skipped tests. Use `hiveup check <check-name> <integration-name>` for a focused check. For non-PR work, omit `--base-ref` and report skipped history-aware checks. See [CONTRIBUTING.md](CONTRIBUTING.md#local-validation).

Apply supported lint/format fixes, then rerun validation:

```bash
hiveup validate --only lint,format --fix <integration-name>
hiveup validate --base-ref <base-ref> <integration-name>
```

HiveUp uses its bundled Ruff configuration. For standalone Ruff, pass `--config ../autohive-integrations-tooling/ruff.toml` to both lint and format when the Tooling checkout is a sibling. Live tests need a separately prepared environment using the integration's existing requirements; exclude `destructive` by default and keep credentials in an uncommitted `.env`.

## Git workflow

### Commits

- Use **[Conventional Commits](https://www.conventionalcommits.org/)** for all commit messages and PR titles.
- Format: `type(scope): description` — e.g. `feat(slack): add reaction support`, `fix(gmail): handle empty attachments`
- Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### Branching

- Branch names must follow the format: `<type>/<issue-number>/<short-description>`
  - Examples: `feat/42/add-slack-reactions`, `fix/108/gmail-empty-attachments`, `docs/55/update-readme`
  - The `<type>` prefix should match conventional commit types.

### History

- **Do not force-push** unless absolutely necessary. Add new commits to the branch instead of rewriting history.
- Keep commits focused — one logical change per commit.

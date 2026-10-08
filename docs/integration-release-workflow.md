# Bulk integration dependency refresh

Use one PR to refresh several integrations instead of manually packaging and
uploading each Lambda.

## Three steps

1. Bump each affected `config.json.version`, for example `1.2.3` to `1.2.4`,
   check its requirements, validate it, and merge the PR to `master`.
2. In **Autohive Admin > Integrations > GitHub Sync**, select **Sync new releases**.
   Bind unmatched packages to existing integrations, or explicitly create new ones.
3. Upload the checked integrations. After successful deployment, review and
   publish through the existing integration publishing page.

GitHub Actions runs HiveUp and creates
`integration-packages-<run-id>-<attempt>` with the selected ZIPs and
`autohive-manifest.json`. There is no packaging job to start or monitor in Admin.

## Responsibilities

| Repository | Job |
| --- | --- |
| `autohive-integrations` | Source, dependency requirements, version bumps, and merge-triggered Actions workflow. |
| `autohive-integrations-tooling` | HiveUp selects changed versions, builds fresh ZIPs, and writes the integrity manifest. |
| `autohive` | Admin pulls releases, reviews bindings, and deploys unpublished versions. |

Compatible dependency ranges can resolve newer packages on each fresh build.
Exact pins remain pinned; update requirements when the security fix requires it.
Packaging targets Python 3.13 / Linux x86_64 and ignores local `dependencies/`.
Check resolved dependencies and AWS findings after deployment.

The workflow selects new folders and version increases since the last successful
ancestral push run, including bumps from skipped/failed merges. Before the first
success, earlier attempted merges are included. History-read failures stop the
workflow. Commits without bumps create no release.

Admin keeps the newest ZIP per folder across unseen releases. Folder bindings
point to backend IDs, so database name changes do not create duplicates after
binding. An unbound manual rename needs an explicit Bind decision. Reviewed
repository/config renames retain the backend and create a replacement Lambda.

## Setup and recovery

Publish the companion HiveUp `2.5.0` tag before merging this workflow. Follow the
[Admin rollout guide](https://github.com/Autohive-AI/autohive/blob/feat/github-integration-sync/docs/Integrations/GitHub%20integration%20release%20sync.md)
for the existing migrations and environment prerequisites. Manual snapshot
packaging is available directly in GitHub Actions for recovery.

Release selection checks run in CI. With the companion tooling installed locally:

```bash
PATH="$(pwd)/../autohive-integrations-tooling/.venv/bin:$PATH" python -m unittest discover -s .github/tests -v
```

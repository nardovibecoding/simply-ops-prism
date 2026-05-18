# Dependency Policy

`simply-ops-prism` intentionally has a small dependency surface.

## Runtime

- Python 3.10 or newer.
- Bash.
- macOS `launchctl` only if you use the LaunchAgent template.

The core template uses only Python standard-library modules. There are no
required third-party Python packages in this release.

## Updating

- Keep the public template local-first and dependency-light.
- Prefer standard-library code unless a third-party package clearly reduces
  real complexity.
- If a third-party dependency is added later, add a pinned manifest, explain why
  it is needed, and enable dependency update monitoring for that manifest.

## Supply Chain

- Do not add install commands that pipe remote code into privileged shells.
- Do not add GitHub Actions that use unpinned third-party actions.
- Do not add release artifacts without a matching SBOM or written
  not-applicable decision.

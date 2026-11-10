# Public launch checklist

This is the maintainer's release gate for the first public npm and PyPI distributions. Nothing in this checklist authorizes publication.

## Completed in this preparation branch

- [x] Created an isolated `release/public-launch-prep` branch from `main`.
- [x] Rewrote the root README around the supported CLI product and removed stale Nexus command examples and unsupported feature claims from the landing page.
- [x] Added a security guide that documents provider-data flows, plaintext saved credentials, and MCP execution permissions.
- [x] Clarified the build-only and explicit-publishing process in the release guide.
- [x] Confirmed the Python and npm package directories already contain MIT license files.

## Must be completed before release

- [ ] Run CI for this branch and resolve every failing job.
- [ ] Build both distributions from a clean checkout and inspect their actual contents.
- [ ] Install both built artifacts in clean environments and smoke-test their entry points.
- [ ] Confirm the npm package name `vonk` is controlled by the maintainer and available for this release.
- [ ] Confirm the PyPI project name `vonk-ai-terminal` is controlled by the maintainer and available for this release.
- [ ] Verify GitHub environments and registry credentials: npm environment with a scoped `NPM_TOKEN`, PyPI Trusted Publisher with OIDC.
- [ ] Review and confirm the copyright/attribution line in the MIT license before distributing binaries. The current notice reads `Copyright (c) 2026 opencode-llm contributors`; do not change it without confirming the project's rights holders.
- [ ] Decide whether the current plaintext local credential storage is acceptable for an initial release, or implement and test OS keychain integration first.
- [ ] Confirm provider names, model aliases, model access, pricing caveats, and links are still accurate.
- [ ] Confirm the version is intentionally `0.4.0` in both package metadata and CLI version constants, or bump all version declarations together.
- [ ] Maintainer explicitly authorizes publishing both registries.

## Release sequence after approval

1. Run the `Publish Vonk CLI` workflow with `build-only`.
2. Download and inspect the workflow artifacts.
3. Verify npm and PyPI package ownership and version availability.
4. Obtain explicit maintainer approval for the exact version and both registries.
5. Only then dispatch the workflow with target `both`.
6. Verify registry installs in clean Windows and Linux environments.
7. Update README status and publish release notes only after both registry installs work.

## Current release status

**Not published.** No npm or PyPI upload, Git tag, or public GitHub release is part of this preparation branch.

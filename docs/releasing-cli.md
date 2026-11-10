# Releasing Vonk CLI

This document describes how to prepare and publish the npm and Python CLI distributions. **Do not publish until the maintainer explicitly authorizes the release.** A source-code push or GitHub release is not the same as publishing to npm or PyPI.

## Current candidate

- npm distribution: `vonk`
- Python distribution: `vonk-ai-terminal`
- Executable: `vonk`
- Candidate version: `0.4.0`
- Minimum Node.js: `20.3`
- Minimum Python: `3.10`

The Python distribution intentionally uses the name `vonk-ai-terminal`; `pip install vonk` may resolve to an unrelated project. Do not change the agreed name without maintainer approval.

## Pre-release validation

1. Confirm the npm package name is available to and publishable by the maintainer's npm account. A registry lookup alone does not establish ownership.
2. Confirm the PyPI project name `vonk-ai-terminal` is available or already controlled by the maintainer.
3. Review package metadata, included files, license notices, and README content in both built distributions.
4. Run the Python and npm test suites on Windows and Linux.
5. Build the Python wheel and source distribution; run `twine check`.
6. Run `npm pack --dry-run` and inspect the resulting tarball.
7. Install each built package into a clean environment and smoke-test `vonk --version`, `vonk`, provider setup, and plain chat.
8. Confirm all version declarations match before creating a release tag.
9. Review the launch checklist and resolve every blocking item.

```bash
python -m pip install build twine pytest
python -m pytest tests/test_assistant_cli.py tests/test_providers.py tests/test_workspace.py tests/test_tui.py -q
npm --prefix packages/npm-cli test
python -m build --outdir dist/python ./packages/python-cli
python -m twine check dist/python/*
npm pack ./packages/npm-cli --pack-destination dist/npm
```

## GitHub Actions

The `Publish Vonk CLI` workflow validates the Python and npm clients on Windows and Linux, then builds distribution artifacts on Linux.

Run it manually with `build-only` first. This creates artifacts but does not publish. The publishing jobs require an explicit target of `npm`, `pypi`, or `both` and the corresponding GitHub environment authorization.

### PyPI

Configure a Trusted Publisher for project `vonk-ai-terminal`:

- Owner: `UkohEmmanuel1`
- Repository: `Vonk`
- Workflow: `publish-cli.yml`
- Environment: `pypi`

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/). The workflow uses OIDC and does not require a PyPI password in GitHub secrets.

### npm

Configure the GitHub environment named `npm` and add an `NPM_TOKEN` secret for an account authorized to publish the `vonk` package. Consider requiring an environment reviewer. Never commit the token or put it in source files.

## Publish only after approval

The maintainer must explicitly authorize the registry and version to publish. Before that authorization:

- Do not dispatch the workflow with `npm`, `pypi`, or `both`.
- Do not run `npm publish` or `twine upload`.
- Do not create a public announcement claiming registry installation is available.

Never overwrite an existing version. If release contents change, increment the version in both package metadata and CLI version constants, then rebuild and revalidate.

## Post-publication verification

```bash
npm view vonk version
python -m pip index versions vonk-ai-terminal
```

Install both packages in clean environments and verify the `vonk` entry point. Only then update the README's registry status and announce public installation.

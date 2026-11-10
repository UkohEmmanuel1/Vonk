# Vonk

**Your AI. Your Terminal. Your Workflow.**

Vonk is an open-source, multi-provider AI developer terminal. It provides an interactive workspace for chatting with supported AI providers, selecting models, attaching files for read-only review, enabling local skills, and invoking stdio MCP tools with explicit user authorization.

Vonk is not currently an autonomous coding agent: core chat does not edit files or run shell commands. MCP tools are separate, explicitly authorized actions and are not sandboxed.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-20.3%2B-green.svg)](https://nodejs.org/)

## Features

- Full-screen terminal workspace with a command palette and persistent composer.
- Multiple provider integrations, including DeepSeek, OpenAI-compatible services, Hugging Face, Google, Anthropic, and local Ollama.
- Bring your own provider credentials; Vonk does not provide subsidized anonymous hosted inference.
- Read-only review of explicitly attached UTF-8 text files.
- Optional local skills that add instructions to model context; skills do not execute code.
- Stdio Model Context Protocol (MCP) server support with explicit confirmation before launching servers or calling tools.
- Python and Node.js CLI distributions that share the `vonk` command and user configuration.

See the [terminal guide](docs/terminal.md) for supported providers, model setup, commands, file limits, credential handling, and MCP limitations.

## Requirements

- Python CLI: Python 3.10 or newer.
- npm CLI: Node.js 20.3 or newer.
- An API key for hosted providers, or a locally installed Ollama service and downloaded model weights for local inference.
- A terminal that supports interactive input. Windows CMD, PowerShell, macOS, and Linux are supported; use `vonk chat --plain` where a full-screen terminal is unavailable.

## Install

### npm

```bash
npm install -g vonk
vonk
```

### Python

```bash
python -m pip install vonk-ai-terminal
vonk
```

**Registry publication is not complete yet.** Until the first public release is authorized and published, install from a local clone:

Python:

```bash
git clone https://github.com/UkohEmmanuel1/Vonk.git
cd Vonk
python -m pip install ./packages/python-cli
vonk
```

npm:

```bash
git clone https://github.com/UkohEmmanuel1/Vonk.git
cd Vonk
npm install -g ./packages/npm-cli
vonk
```

Both distributions expose a `vonk` executable. Install only one distribution in a given environment to avoid command-name conflicts.

## First run

Launch the interactive workspace:

```bash
vonk
```

Connect a hosted provider, then choose a model:

```bash
vonk login deepseek
vonk use deepseek deepseek-chat
vonk chat
```

For local inference, install [Ollama](https://ollama.com/), download a model, and select it in Vonk. For example:

```bash
ollama pull qwen2.5-coder:1.5b
vonk
```

For Hugging Face Inference Providers, configure your own token and select a preset:

```bash
vonk login huggingface
vonk use huggingface qwen
vonk chat
```

Provider availability, model access, pricing, quotas, and licenses are controlled by the relevant provider and model publisher. An open-weight model does not automatically mean hosted inference is free or available offline.

## Security and data handling

- Provider credentials are stored locally only when you use the login command. Saved credentials are plaintext in `~/.config/vonk/keys.json`; POSIX permissions are restricted, while Windows relies on the current account's directory permissions. Environment variables or an OS credential manager are preferable on shared devices.
- Prompts and attached file contents are sent to the provider you select. Attach only content you are authorized to share.
- Attached files are read-only inputs. Vonk does not modify their originals.
- MCP servers execute with your operating-system user's permissions. Only configure trusted servers; Vonk does not sandbox their filesystem or network access.
- Never commit API keys, credential files, or private configuration to source control.

Read the [security notes](docs/security.md) before using Vonk with sensitive projects.

## Development and tests

```bash
python -m pip install -e ./packages/python-cli pytest
python -m pytest tests/test_assistant_cli.py tests/test_providers.py tests/test_workspace.py tests/test_tui.py -q
npm --prefix packages/npm-cli test
npm pack ./packages/npm-cli --dry-run
```

Build and inspect the Python distribution:

```bash
python -m pip install build twine
python -m build --outdir dist/python ./packages/python-cli
python -m twine check dist/python/*
```

GitHub Actions runs cross-platform CLI tests and package validation. Passing automated tests does not guarantee that every third-party provider is currently available; live provider checks require valid credentials and may incur charges.

## Documentation

- [Terminal guide](docs/terminal.md) — user guide, providers, commands, skills, MCP, configuration.
- [Security notes](docs/security.md) — credential storage, prompt/file handling, and MCP trust boundaries.
- [Release guide](docs/releasing-cli.md) — build-only validation and the controlled npm/PyPI publishing process.
- [API guide](docs/api.md) — hosted API deployment and integration, separate from the CLI distributions.

## Project status

Vonk's CLI is a public source-code project undergoing preparation for its first npm and PyPI registry release. Registry publication is deliberately gated and will not happen until the maintainer authorizes it. Some research-framework and model-training components in this repository are experimental and are not implied to be part of the supported CLI product.

## License

Vonk is distributed under the MIT License. See [LICENSE](LICENSE).

# Vonk

An interactive developer terminal with model selection, provider connections,
skills, and on-demand stdio MCP tools. Run `vonk` or `vonk chat` to open the
full-screen green-and-amber workspace. Type directly into the composer; `/` or
Ctrl+P opens commands, F2 selects models, F3 connects providers, Esc cancels a
request, and Ctrl+D exits. The terminal tab shows `Vonk · PROJECT`. No API key
is needed to browse the interface. Plain chat: `vonk chat --plain`.

Python installation: `pip install vonk-ai-terminal` after registry publication.
For the current source release, clone the repository and run
`python -m pip install ./packages/python-cli`.

The default CLI route uses Vonk's managed inference gateway, with OpenCode as
the preferred model and automatic fallback to other eligible FreeLLM catalogue
models. Configure `VONK_BASE_URL` and `VONK_API_KEY`. You can still connect
direct provider accounts for BYOK; provider access, quotas and pricing are set
by each provider. Ollama/local model hosting is not part of Vonk.

Commands:

```text
vonk
vonk connect
vonk models
vonk skills add ./SKILL.md --name review
vonk skills disable review
vonk mcp add demo -- python ./server.py
vonk mcp tools demo --yes
vonk mcp call demo tool_name '{"argument":"value"}' --yes
```

Skills add user-selected instructions to model context. MCP support currently
covers legacy 2024/2025 stdio servers. Starting an MCP program or invoking a tool
requires confirmation, or explicit `--yes` authorization for scripts. Trusted
MCP programs run with your OS user permissions; this is not a sandbox.

Core chat reviews explicitly attached files and does not edit source files or
run autonomous tool loops. MCP tools are explicit user actions. API credentials
are stored only when you use login; saved local keys are plaintext. Never put
keys in source control. See the [full guide](https://github.com/UkohEmmanuel1/Vonk/blob/main/docs/terminal.md).

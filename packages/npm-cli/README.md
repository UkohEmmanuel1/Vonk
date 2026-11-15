# Vonk

Interactive developer terminal: model selection, Vonk-managed inference, direct
provider connections (BYOK), skills, and stdio MCP tools.

The interactive UI fills the terminal with a green-and-amber theme, Vonk
wordmark, conversation history, and persistent composer. Type a prompt directly.
`/` or Ctrl+P opens commands; F2 selects models, F3 connects providers, Esc
cancels a request, and Ctrl+D exits. The terminal tab shows `Vonk · PROJECT`.
Plain chat remains available with `vonk chat --plain`.

After publication: `npm install -g vonk`, then run `vonk` or `vonk chat`.
For the current source candidate, clone the repository and run
`npm install -g ./packages/npm-cli`. Node.js 20.3+ is required.

The CLI defaults to Vonk's managed inference gateway. Configure
`VONK_BASE_URL` and `VONK_API_KEY`; OpenCode models are preferred and Vonk
automatically falls back to other eligible FreeLLM catalogue models. Direct
provider connections remain available through BYOK. Provider quotas and access
restrictions still apply.

```text
vonk connect
vonk models
vonk skills add ./SKILL.md --name review
vonk skills disable review
vonk mcp add demo node ./server.js
vonk mcp tools demo --yes
vonk mcp call demo tool_name '{"argument":"value"}' --yes
```

Skills add instructions, not executable code. MCP currently supports legacy
2024/2025 stdio servers and requires confirmation or explicit `--yes` permission
to launch programs/call tools. MCP programs run with your OS user permissions;
this is not a sandbox. Core chat does not autonomously edit files or run tools.

Credentials are saved locally only when you use login; saved keys are plaintext.
See the [full guide](https://github.com/UkohEmmanuel1/Vonk/blob/main/docs/terminal.md).

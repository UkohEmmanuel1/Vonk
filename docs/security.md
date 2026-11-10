# Security notes

Vonk is an early-stage developer tool. Review these boundaries before connecting accounts, attaching source code, or enabling MCP servers.

## Provider credentials

The CLI can read credentials from provider-specific environment variables or save them through the interactive login command. Saved credentials are currently stored as plaintext in `~/.config/vonk/keys.json`. On POSIX systems the CLI restricts credential-file permissions; on Windows it relies on the current user's directory permissions.

For shared machines, CI, and production environments, prefer environment variables or an operating-system secret manager. Do not commit credentials or paste them into issue reports. If a key is exposed, revoke it with its provider.

## Prompts and attached files

Prompts and explicitly attached file contents are sent to the configured provider. Attach only files you are authorized to disclose. The CLI rejects several common credential-file patterns and limits the number and combined size of attachments, but these checks are not a substitute for reviewing the content yourself.

Core chat is read-only. The CLI does not edit local source files or execute shell commands as part of ordinary chat.

## MCP trust boundary

MCP support currently targets stdio servers. Starting a server and invoking its tools require explicit confirmation (or an explicit `--yes` flag). The server process runs with the permissions of the operating-system account running Vonk and is not sandboxed by Vonk. It may be able to read or modify files and access the network according to those permissions.

Only configure MCP servers from sources you trust. Inspect the executable and arguments before approving them. Do not assume that adding a server is harmless merely because Vonk does not automatically start it.

Remote HTTP MCP, OAuth, and autonomous model-selected tool execution are not supported by the current CLI release.

## Reporting a vulnerability

Do not publish secrets or exploit details in a public issue. Contact the repository maintainer privately through GitHub's security reporting feature if it is enabled for this repository. If private reporting is unavailable, open a minimal issue asking for a secure contact channel without including exploit details.

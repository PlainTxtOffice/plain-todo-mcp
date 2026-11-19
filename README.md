<!-- last_updated: 2026-11-19 -->
<!-- Authoring guidance: dev-docs/specs/README_SPEC.instructions.md -->
<!-- rumdl-disable MD033 MD041 -->
<h1 align="center">Plain Todo</h1>

<p align="center">
  An MCP server that lets AI coding agents turn a conversation into tasks in
  a plain Markdown <code>AGENT_TODO.md</code> file kept in your repo.
</p>

<p align="center">
  <a href="https://pypi.org/project/plain-todo-mcp/"><img src="https://img.shields.io/pypi/v/plain-todo-mcp?label=pypi" alt="Latest version on PyPI"></a>
  <a href="https://pypi.org/project/plain-todo-mcp/"><img src="https://img.shields.io/pypi/pyversions/plain-todo-mcp" alt="Supported Python versions"></a>
  <a href="https://github.com/PlainTxtOffice/plain-todo-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-informational" alt="License: MIT"></a>
</p>
<!-- rumdl-enable MD033 MD041 -->

---

## About

Work agreed with an agent in one chat is easy to lose by the next session.
Plain Todo (`plain-todo-mcp`) gives the agents you run in Claude Code, Codex,
Cursor, or VS Code a shared to-do list for the repo: when you ask,
the agent pulls the concrete tasks out of the conversation and merges them
into `AGENT_TODO.md`, so you or another agent can pick up where it left off.
The list is ordinary Markdown that you can read, edit, and keep in git. The
server only reads and safely writes the file; the agent, which can see the
conversation, decides what goes in it.

## Features

- Export agreed tasks from the current conversation into `AGENT_TODO.md`,
  merged with the tasks already there and keeping what is done or open.
- Keep a short Working Memory snapshot of what is in progress and what comes
  next at the top of the file.
- Mark open tasks done using commits made since the file was last saved as
  evidence.
- Schedule tasks to revisit with `Check after:` dates, and park blocked work
  in a Waiting section that comes back when its date arrives.
- Give a subfolder its own `AGENT_TODO.md`, linked from the repo's root file.
- Mark each saved file with front matter telling agents that open it directly
  to go through the server, while you stay free to edit it by hand.
- Write safely: an export based on an out-of-date read is rejected rather
  than overwriting someone else's changes, and malformed lists are refused.

## Tools

| Tool | What it does | Changes files |
| --- | --- | --- |
| `read_todo` | Reads `AGENT_TODO.md` with its revision, tasks that are due, and commits since it was last saved. | No |
| `export_todo` | Saves the merged list, refusing it if the file changed since `read_todo`. | Yes |

## Quick Start

The server needs [uv](https://docs.astral.sh/uv/) and Python 3.12 or later;
`uvx` downloads and starts it on demand:

```shell
uvx plain-todo-mcp
```

Started by hand, it waits for an MCP client on stdin; press Ctrl+C to stop.
Normally your client starts it. For Claude Code, add `.mcp.json` to the repo:

```json
{
  "mcpServers": {
    "plain-todo": {
      "command": "uvx",
      "args": ["plain-todo-mcp"]
    }
  }
}
```

Then ask the agent to export the conversation to `AGENT_TODO.md`. The user
manual covers Codex, Cursor, VS Code, and the settings.

## User Manual

See the
[User Manual](https://github.com/PlainTxtOffice/plain-todo-mcp/blob/main/docs/USER_MANUAL.md)
for installation, client configuration, tools, settings, and troubleshooting.

## Feedback

Report bugs and request features in
[GitHub Issues](https://github.com/PlainTxtOffice/plain-todo-mcp/issues).

## License

[MIT](https://github.com/PlainTxtOffice/plain-todo-mcp/blob/main/LICENSE)

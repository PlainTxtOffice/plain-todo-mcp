---
last_updated: 2026-10-28
---

<!-- Authoring guidance: dev-docs/specs/README_SPEC.instructions.md -->
<!-- rumdl-disable MD033 MD041 -->
<h1 align="center">Plain Todo</h1>

<p align="center">
  An MCP server that lets AI coding agents turn a conversation into tasks in
  a plain Markdown <code>AGENT_TODO.md</code> file kept in your repo.
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
- Write safely: an export based on an out-of-date read is rejected rather
  than overwriting someone else's changes, and malformed lists are refused.

## User Manual

See the [User Manual](docs/USER_MANUAL.md) for installation, setup, usage,
and troubleshooting.

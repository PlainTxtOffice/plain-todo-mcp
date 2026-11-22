---
last_updated: 2026-11-19
version: 1.3.0
product_version: "0.5.0"
generated_from: "dev-docs/specs/USER_MANUAL_SPEC.instructions.md"
---

# User Manual

## Overview

Plain Todo (`plain-todo-mcp`) is an MCP server that lets AI coding agents
save the tasks agreed in a conversation to a Markdown file named
`AGENT_TODO.md` in your repo. When you ask, the agent reads the file, merges
the conversation's tasks into it, and saves the whole list back. The next
session, or another agent, reads the same file and carries on.
<!-- Verified from: pyproject.toml [project.description]; src/plain_todo_mcp/server.py [INSTRUCTIONS, EXPORT_WORKFLOW] -->

It is for people who work with agents in Claude Code, Codex, Cursor, VS Code,
or another MCP client and want a to-do list that outlives a single chat. The
list is plain text: you can read and edit it yourself and keep it in git.

Checked with: Claude Code and Codex. Cursor and VS Code use the same command
with each client's documented configuration format; whether they have been
checked is Unknown.
<!-- Verified from: .mcp.json; .codex/config.toml -->

The server cannot see your conversation. The agent decides which tasks to
save; the server reads the file, checks what the agent sends, and writes it
safely. Connecting the server never writes anything by itself.
<!-- Verified from: src/plain_todo_mcp/server.py [INSTRUCTIONS] -->

Supported systems: Windows, macOS, and Linux.
<!-- Verified from: pyproject.toml [project.classifiers]; .github/workflows/ci.yml [test.matrix.os] -->

You reach Plain Todo in three ways, all through your agent:

- **Tools** the agent calls: **Read repository todos** (`read_todo`) and
  **Export conversation todos** (`export_todo`). See [Tools](#tools).
- A prompt, **Export conversation as todos** (`export`), that you can invoke
  in clients that list MCP prompts.
- The `AGENT_TODO.md` file itself, which you can open in any text editor.
<!-- Verified from: src/plain_todo_mcp/server.py [build_server] -->

The agent always works in the same order: it calls `read_todo` to get the
file and its revision, merges the conversation's tasks into the text, then
calls `export_todo` with the full merged file and that revision.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

## Installation and Setup

### Check the Requirements

- [uv](https://docs.astral.sh/uv/), which downloads the server and a
  suitable Python on demand. The server needs Python 3.12 or later.
- An MCP client, such as Claude Code, Codex, Cursor, or VS Code.
- Optional: Git. Without it, the agent gets no list of recent commits to
  check finished tasks against; everything else works.
<!-- Verified from: pyproject.toml [project.requires-python]; src/plain_todo_mcp/storage.py [TodoStore.recent_commits] -->

### Install the Published Server

The server is published on PyPI as `plain-todo-mcp`, and `uvx` runs it
without a separate install step. There is nothing to install beyond uv: add
the server to your client as shown in
[Connecting Clients](#connecting-clients), and the client runs
`uvx plain-todo-mcp` when it starts the server.
<!-- Verified from: pyproject.toml [project.name, project.scripts]; .github/workflows/publish.yml -->

`uvx` downloads the latest release the first time it runs the server, then
keeps reusing that cached copy. A newer release on PyPI is not picked up on
its own. To update, run this once, then restart the server in your client:

```shell
uvx plain-todo-mcp@latest
```

To check for a new release every time the server starts, use
`plain-todo-mcp@latest` instead of `plain-todo-mcp` in your client's `args`.
Running `uv cache clean` also removes the cached copy; the next start
downloads the latest release again.
<!-- Verified from: https://docs.astral.sh/uv/concepts/tools/ [Tool versions, Tool environments] -->

### Install a Local Copy

To run a checked-out copy of the server rather than the published package,
install that copy once as an editable command:

```shell
uv tool install --editable path/to/plain_todo_mcp
```

Your clients then run `plain-todo-mcp` as the command, with no arguments
(see [Use a Local Copy in Any Client](#use-a-local-copy-in-any-client)).

Code changes in the copy take effect when the client restarts the server.
After changing the version in its `pyproject.toml`, close every client using
the server and reinstall:

```shell
uv tool install --editable --reinstall path/to/plain_todo_mcp
```

On Windows, a running `plain-todo-mcp.exe` blocks the reinstall, and clients
then show the server as failed or "Connection closed".
<!-- Verified from: pyproject.toml [project.scripts]; .mcp.json -->

While the local copy is installed, `uvx plain-todo-mcp` also runs it instead
of the published package. Use `uvx --isolated plain-todo-mcp` to run the
published package, or `uv tool uninstall plain-todo-mcp` to remove the local
copy.
<!-- Verified from: https://docs.astral.sh/uv/concepts/tools/ [Tool versions] -->

### Confirm the Command Runs

From inside your repo, start the server by hand:

```shell
uvx plain-todo-mcp
```

With a local copy installed as a command:

```shell
plain-todo-mcp
```
<!-- Verified from: pyproject.toml [project.scripts]; src/plain_todo_mcp/server.py [main] -->

What to expect on startup:

1. The server picks the repo: the nearest folder, at or above the folder it
   was started in, that contains a `.git` folder or file. Outside Git, it
   uses the start folder itself. `TODO_REPO_PATH` overrides this (see
   [Settings](#settings)).
1. It prints nothing and waits for an MCP client on standard input. Started
   by hand, it keeps waiting until you press **Ctrl+C**.
1. When an agent connects, the server sends it the export workflow, so the
   agent needs no extra instructions.
<!-- Verified from: src/plain_todo_mcp/storage.py [resolve_repo]; src/plain_todo_mcp/server.py [main, INSTRUCTIONS] -->

If the command stops at once with an error instead of waiting, see
[Troubleshooting](#troubleshooting).

Normally you do not start the server yourself: your client starts it when a
session begins and stops it when the session ends.

## Connecting Clients

Each client starts the server with the same command, `uvx plain-todo-mcp`,
under the server name `plain-todo`. Merge the entry into any servers already
in the client's configuration file.
<!-- Verified from: pyproject.toml [project.scripts]; src/plain_todo_mcp/server.py [build_server] -->

Per-project configuration lives in a file inside the repo, so it applies only
there and can be shared through Git. Per-user configuration applies to every
project you open. The same entry works in every repo, because the server
finds the repo from the folder your client starts it in. Whichever you use,
check that `read_todo` reports `AGENT_TODO.md` in your repo; if it does not,
set `TODO_REPO_PATH` (see [Settings](#settings)).
<!-- Verified from: src/plain_todo_mcp/storage.py [resolve_repo]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

### Configure Each Client

#### Connect Claude Code

Per project, `.mcp.json` in the repo:

```json
{
  "mcpServers": {
    "plain-todo": {
      "type": "stdio",
      "command": "uvx",
      "args": ["plain-todo-mcp"]
    }
  }
}
```

Per user, run `claude mcp add --scope user plain-todo -- uvx plain-todo-mcp`,
which stores the entry in `.claude.json` in your home folder.

To confirm the connection:

1. Start a new session. In an interactive session, Claude Code asks you to
   approve a server defined in `.mcp.json` before using it.
1. Run `/mcp` and check that `plain-todo` is connected and lists `read_todo`
   and `export_todo`.
1. Ask the agent to call `read_todo` and check that the reported path is
   `AGENT_TODO.md` in your repo.
<!-- Verified from: https://code.claude.com/docs/en/mcp [MCP installation scopes, Project scope] -->

#### Connect Codex

Per project, `.codex/config.toml` in the repo. Codex reads it only in
projects you have marked as trusted.

```toml
[mcp_servers.plain-todo]
command = "uvx"
args = ["plain-todo-mcp"]
```

Per user, put the same entry in `~/.codex/config.toml`.

To confirm the connection, run `/mcp` in a Codex session to see the active
servers, or run `codex mcp list` to see the configured ones. Then ask the
agent to call `read_todo` and check the reported path.
<!-- Verified from: https://learn.chatgpt.com/docs/extend/mcp?surface=cli -->

#### Connect Cursor

Per project, `.cursor/mcp.json` in the repo:

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

Per user, put the same entry in `~/.cursor/mcp.json`.

To confirm the connection, find `plain-todo` under **Customize** in the
sidebar and check that it is enabled, then ask the agent to call `read_todo`
and check the reported path. Connection errors appear under **MCP Logs** in
the Output panel.
<!-- Verified from: https://cursor.com/docs/context/mcp -->

#### Connect VS Code

Per project, `.vscode/mcp.json` in the repo. VS Code uses a `servers` key
rather than `mcpServers`.

```json
{
  "servers": {
    "plain-todo": {
      "type": "stdio",
      "command": "uvx",
      "args": ["plain-todo-mcp"]
    }
  }
}
```

Per user, put the same entry in the `mcp.json` of your VS Code user profile.

To confirm the connection, run **MCP: List Servers** from the Command
Palette, select `plain-todo`, and choose **Show Output** to see it start.
Then ask the agent to call `read_todo` and check the reported path. After
changing the configuration, choose **Restart Server** from the same list.
<!-- Verified from: https://code.visualstudio.com/docs/copilot/customization/mcp-servers; https://code.visualstudio.com/docs/agents/run/manage-mcp-servers -->

### Use a Local Copy in Any Client

After [installing a local copy](#install-a-local-copy), replace the
`command` and `args` in any of the entries above with the single command
`plain-todo-mcp` and no arguments. For example, in `.mcp.json`:

```json
{
  "mcpServers": {
    "plain-todo": {
      "type": "stdio",
      "command": "plain-todo-mcp"
    }
  }
}
```

In Codex:

```toml
[mcp_servers.plain-todo]
command = "plain-todo-mcp"
```
<!-- Verified from: pyproject.toml [project.scripts]; .mcp.json; .codex/config.toml -->

## Tools

| Tool | What it does | Changes files |
| --- | --- | --- |
| `read_todo` | Returns the todo file, its revision, recent commits, and due tasks | No |
| `export_todo` | Checks and saves the full merged todo file | Yes: `AGENT_TODO.md`, and the root `AGENT_TODO.md` when it adds a subfolder link |
<!-- Verified from: src/plain_todo_mcp/server.py [read_todo, export_todo]; src/plain_todo_mcp/storage.py [TodoStore.export, TodoStore.link] -->

When a tool fails, its message starts with `Cannot read AGENT_TODO.md:` or
`Cannot export AGENT_TODO.md:`, followed by the reason listed in
[Troubleshooting](#troubleshooting).
<!-- Verified from: src/plain_todo_mcp/server.py [read_todo, export_todo] -->

### read_todo

Shown as **Read repository todos**. It is marked read-only and safe to
repeat.

| Parameter | Required | What to pass |
| --- | --- | --- |
| `directory` | No | A subfolder, relative to the repo root, whose own `AGENT_TODO.md` to use. Leave empty for the repo's root file. |

It returns:

| Field | Contents |
| --- | --- |
| `path` | The absolute path of the `AGENT_TODO.md` it read |
| `exists` | Whether the file exists yet |
| `content` | The file's full text without the front matter the server writes, or empty when it does not exist |
| `revision` | A fingerprint of the file's exact content, or `missing` when it does not exist |
| `recent_commits` | Up to 30 commits made since the file was last saved, newest first, each as a short hash and subject |
| `due_tasks` | Open tasks whose `Check after:` date has arrived |
<!-- Verified from: src/plain_todo_mcp/server.py [read_todo]; src/plain_todo_mcp/storage.py [TodoSnapshot, TodoContext, TodoStore.read, TodoStore.recent_commits, MAX_RECENT_COMMITS, due_tasks] -->

It changes nothing. The commit list is empty when the repo does not use Git,
Git is not installed, or the file does not exist yet. For a subfolder file it
covers only commits that touched that folder. Due tasks use your computer's
local date.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.recent_commits]; src/plain_todo_mcp/server.py [read_todo] -->

### export_todo

Shown as **Export conversation todos**. It is marked as able to overwrite
existing content.

| Parameter | Required | What to pass |
| --- | --- | --- |
| `content` | Yes | The full Markdown after merging the conversation's tasks with the existing file, preserving unrelated items and checkboxes |
| `expected_revision` | Yes | The exact `revision` returned by `read_todo` |
| `directory` | No | The same subfolder passed to `read_todo`, or empty for the root file |

It returns the saved file's `path`, `exists`, `content`, and new `revision`.
<!-- Verified from: src/plain_todo_mcp/server.py [export_todo]; src/plain_todo_mcp/storage.py [TodoSnapshot, TodoStore.export] -->

How an export is checked and written:

1. The file must contain at least one task line starting at the left margin,
   `- [ ] text` or `- [x] text`.
1. The Working Memory, Done, Waiting, and `Check after:` rules in
   [AGENT_TODO.md Format](#agent_todomd-format) are checked.
1. The revision the agent read must still match the file on disk. If anyone
   changed the file since, the export is rejected and nothing is written.
1. A root export must keep every link to a subfolder `AGENT_TODO.md` that
   still exists.
1. The server's front matter block is written at the top of the file. Any
   front matter in `content` is dropped and replaced, so it never doubles.
1. The whole file is replaced in one step, so a failed write never leaves a
   half-written file. Saving identical content changes nothing.
1. For a subfolder file, the server then adds a link to it in the root
   `AGENT_TODO.md`, creating the root file if needed.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.export, TodoStore._replace, TodoStore.link, check_kept_links, strip_front_matter, FRONT_MATTER] -->

The export always replaces the whole file; it never appends. A missing file
is created. Line endings are saved as `\n` and the file ends with one
newline.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.export, TodoStore._replace] -->

### export Prompt

Shown as **Export conversation as todos**. It takes no inputs and gives the
agent the export workflow described in
[Export the Conversation as Tasks](#export-the-conversation-as-tasks). It
changes nothing by itself.
<!-- Verified from: src/plain_todo_mcp/server.py [export_prompt] -->

## Everyday Tasks

### Export the Conversation as Tasks

Prerequisite: the server is connected to your agent.

1. Ask the agent, for example: "Export this conversation as a todo list in
   AGENT_TODO.md." In clients that list MCP prompts you can instead run the
   **Export conversation as todos** prompt; Claude Code typically shows it as
   `/mcp__plain-todo__export`.
1. The agent calls `read_todo`, picks out the concrete tasks you asked for or
   agreed to, and merges them with the tasks already there.
1. The agent calls `export_todo` and reports the saved path and what it
   added, updated, marked done, or rescheduled.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW, export_prompt] -->

What the agent is told to do when merging:

- Keep unrelated tasks, notes, headings, and completion status.
- Combine tasks that mean the same thing, even if worded differently.
- Use `- [ ]` for open tasks and `- [x]` only for work it verified is done.
- Leave out suggestions you rejected or never approved, and never save
  secrets.
- Leave the file untouched when there is nothing new, and say so.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

Exporting tasks saves them; it does not carry them out.

### Check What Is Left

1. Ask the agent, for example: "What is left in AGENT_TODO.md?"
1. The agent calls `read_todo` and summarizes the open tasks, including any
   whose `Check after:` date has arrived.
1. Nothing is written.
<!-- Verified from: src/plain_todo_mcp/server.py [read_todo] -->

### Mark Tasks Done from Recent Work

Tasks are often finished in another session or by hand.

1. Ask the agent to export, for example: "Update AGENT_TODO.md with what we
   finished."
1. The agent calls `read_todo`, which also returns up to 30 commits made
   since the file was last saved.
1. It marks an open task `- [x]` only with evidence it checked, such as a
   commit, a file, or a command result, and cites the commit when there is
   one. It leaves tasks open when unsure and does not audit unrelated tasks.
1. It saves with `export_todo` and lists the tasks it marked done.
<!-- Verified from: src/plain_todo_mcp/storage.py [MAX_RECENT_COMMITS, TodoStore.recent_commits]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

### Schedule a Task to Revisit

1. Ask the agent, for example: "Revisit the pricing task after 2026-12-01,"
   or add `Check after: YYYY-MM-DD` to an open task yourself, on its line or
   an indented line below it.
1. Until that date, the agent does not treat the task as next work.
1. From that date on, `read_todo` lists the task as due. On the next export
   the agent checks it again and marks it done with evidence, sets a new
   date, or removes the date when it is ready to work on.
<!-- Verified from: src/plain_todo_mcp/storage.py [CHECK_AFTER, due_tasks]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

The date must be a real date written as `YYYY-MM-DD`; anything else, such as
`Check after: next week`, is rejected on export. Due dates use your
computer's local date.
<!-- Verified from: src/plain_todo_mcp/storage.py [check_task_sections]; src/plain_todo_mcp/server.py [read_todo] -->

### Park a Blocked Task Under Waiting

Ask the agent, for example: "Park the App Store link task until Apple
approves the app." It calls `read_todo`, then `export_todo` with the task
under a `## Waiting` heading, with what it waits on and a check date. The
agent uses a date two weeks out unless you give one.

```markdown
## Waiting

- [ ] Add the App Store link once the app is listed.
      Waiting on: Apple review. Check after: 2026-11-09
```

An open task under Waiting without a `Check after:` date is rejected, so
nothing waits forever.
<!-- Verified from: src/plain_todo_mcp/storage.py [check_task_sections]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

### Keep the Working Memory Snapshot Current

The top of the file holds a short snapshot of what is in progress and what
comes next, between a `## Working Memory` heading directly under the title
and a `---` line. You do not need to ask for it: on every export the agent
rewrites it instead of adding to it. Finished work moves into the tasks as
`- [x]`, open follow-ups become `- [ ]` tasks, and anything no longer current
is dropped. The rules it must follow are in
[AGENT_TODO.md Format](#agent_todomd-format).
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

### Give a Subfolder Its Own Todo List

A subfolder can keep its own `AGENT_TODO.md` for tasks only about that
folder, such as one component of a larger repo.

1. Ask the agent, for example: "Keep the custom_pdf_engine tasks in their
   own AGENT_TODO.md in platform/windows/custom_pdf_engine."

1. The agent passes the folder, relative to the repo root, as `directory` to
   both `read_todo` and `export_todo`. The folder must already exist inside
   the repo.

1. On the first export, the server adds a link to the new file in the root
   `AGENT_TODO.md`, creating the root file if needed:

   ```markdown
   ## Subdirectory Todos

   - [platform/windows/custom_pdf_engine](platform/windows/custom_pdf_engine/AGENT_TODO.md)
   ```

<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.__init__, TodoStore.link, with_link]; src/plain_todo_mcp/server.py [read_todo, export_todo] -->

After that, the agent puts tasks about that folder in its file and keeps all
other tasks in the root file. It starts a subfolder file only when you ask
for one. For a subfolder file, the recent commit list covers only commits
that touched that folder.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW]; src/plain_todo_mcp/storage.py [TodoStore.recent_commits] -->

Agents find subfolder files through the root file's links, so a root export
that drops a link to a file that still exists is rejected. To retire a
subfolder list, delete its `AGENT_TODO.md`; the link can then be removed.
<!-- Verified from: src/plain_todo_mcp/storage.py [check_kept_links] -->

### Edit the List by Hand

Open `AGENT_TODO.md` in any editor, change it, and save. The next time an
agent calls `read_todo` it sees your changes. If you save while an agent is
between reading and exporting, its export is rejected and it reads the file
again and redoes the merge, so your edit is not overwritten.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.export, TodoConflictError] -->

The front matter block at the top tells agents that open the file directly
to change it only through the server. Edit below it: the server rewrites the
block on every save, so changes to it, or keys you add to it, are replaced.
<!-- Verified from: src/plain_todo_mcp/storage.py [FRONT_MATTER, TodoStore._replace] -->

## Settings

Plain Todo has one setting, an environment variable set in the server's
entry in your client configuration. It takes no command-line options.
<!-- Verified from: src/plain_todo_mcp/server.py [main]; src/plain_todo_mcp/storage.py [resolve_repo] -->

| Setting | Default | Accepted values | Where to set it |
| --- | --- | --- | --- |
| `TODO_REPO_PATH` | Not set: the nearest folder with `.git` at or above the start folder, or the start folder itself | A path to an existing folder, absolute or relative to the start folder; must not be empty | The entry's `env` (`[mcp_servers.plain-todo.env]` in Codex) |
<!-- Verified from: src/plain_todo_mcp/storage.py [resolve_repo] -->

Example for Claude Code, Cursor, or VS Code, inside the `plain-todo` entry:

```json
"env": { "TODO_REPO_PATH": "path/to/your/repo" }
```

Example for Codex:

```toml
[mcp_servers.plain-todo.env]
TODO_REPO_PATH = "path/to/your/repo"
```

Example for VS Code, saving to the open workspace folder:

```json
"env": { "TODO_REPO_PATH": "${workspaceFolder}" }
```

The setting is read when the server starts, so restart or reconnect the
server after changing it. An empty value or a missing folder stops the
server from starting.
<!-- Verified from: src/plain_todo_mcp/server.py [main]; src/plain_todo_mcp/storage.py [resolve_repo] -->

## Your Data Files

### Files the Server Uses

| File | Where | Purpose | Edit by hand? | In Git? |
| --- | --- | --- | --- | --- |
| `AGENT_TODO.md` | Repo root, or a subfolder you chose | The task list | Yes | Your choice |
| `AGENT_TODO.md.lock` | Next to each `AGENT_TODO.md` | Keeps two agents from writing at once | No; leave it in place | No; add it to `.gitignore` |
| `.AGENT_TODO-*.tmp` | Next to each `AGENT_TODO.md` | Temporary file during a write, removed afterward | No | No |
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.__init__, TodoStore._replace] -->

`AGENT_TODO.md` is UTF-8 Markdown and must not be a symbolic link. It is not
ignored in git automatically: decide whether to share it. Never put secrets
in the list, because it may be committed.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.read]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

The server writes no logs and keeps no files outside your repo.
<!-- Verified from: src/plain_todo_mcp/server.py; src/plain_todo_mcp/storage.py -->

### AGENT_TODO.md Format

A typical file looks like this:

```markdown
---
managed_by: plain-todo-mcp
agent_instructions: >-
  Agents change this file only through the plain-todo MCP server: call
  read_todo, merge, then export_todo with the revision it returned.
  People may edit it by hand. The server rewrites this block.
---

# Agent Todo

## Working Memory

- Now: Add retry handling to the export tool
- Next: Document the retry behavior in the README
- Blockers: None

---

## Export

- [ ] Add retry handling to the export tool
- [x] Validate checkbox formatting

## Waiting

- [ ] Add the App Store link once the app is listed.
      Waiting on: Apple review. Check after: 2026-11-09
```

File rules at a glance:

| Part | Rule |
| --- | --- |
| Front matter | Written by the server above the title on every save; left out of `read_todo` content |
| Title | `# Agent Todo` for a new file |
| `## Working Memory` | Optional; directly under the title, closed by `---`; only `Now:`, `Next:`, `Blockers:` bullets; at most 12 lines |
| Task | `- [ ] text` (open) or `- [x] text` (done); indented lines below belong to it |
| `Check after: YYYY-MM-DD` | Optional on any task; a real date |
| A heading named Done | Only `- [x]` tasks, including under its subheadings |
| `## Waiting` | Each open task needs a `Check after:` date, and should say what it is `Waiting on:` |
| `## Subdirectory Todos` | Links to subfolder files; added by the server |
<!-- Verified from: src/plain_todo_mcp/storage.py [FRONT_MATTER, TodoStore.read, check_working_memory, parse_tasks, check_task_sections, with_link]; src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

When present, the Working Memory section must follow these rules:

- Only bullets starting `- Now:`, `- Next:`, or `- Blockers:`. Indented
  continuation lines are fine.
- No `- [ ]` or `- [x]` tasks.
- At most 12 non-blank lines.
- Closed by a `---` line before the next heading.
<!-- Verified from: src/plain_todo_mcp/storage.py [check_working_memory, MAX_WORKING_MEMORY_LINES] -->

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| The server fails to start with `TODO_REPO_PATH must not be empty.` or `Todo repository directory does not exist` | The setting is blank or names a missing folder | Set it to an existing folder, or remove it |
| The client shows the server as failed or "Connection closed" after an update | On Windows, a running copy of `plain-todo-mcp.exe` locked the file while it was being reinstalled | Close every client using the server, reinstall, then reconnect |
| The agent still behaves like an older version after a new release | `uvx` keeps reusing its cached copy of the server, or a local copy installed with `uv tool install` runs instead | Run `uvx plain-todo-mcp@latest`, or remove the local copy with `uv tool uninstall plain-todo-mcp`, then restart the server in your client |
| `read_todo` and `export_todo` are not listed | The client has not loaded the new configuration | Start a new session or reload the client, then check its MCP server list (`/mcp` in Claude Code) |
| `read_todo` reports a path outside your repo | The client starts the server in another folder, or `TODO_REPO_PATH` points at the wrong folder | Set `TODO_REPO_PATH` to your repo, then reconnect |
| `AGENT_TODO.md changed. Read it again...` | The file changed after the agent read it | Nothing to fix: the agent rereads and merges again |
| `Provide Markdown with at least one '- [ ]' or '- [x]' task.` | The export has no task at the left margin | Add at least one task line |
| `Close Working Memory with a '---' line...` | The snapshot runs into the next heading or the tasks | Add a `---` line after the snapshot |
| `Working Memory holds plain bullets only...` or `...must start with 'Now:', 'Next:', or 'Blockers:'...` | The snapshot contains tasks or other text | Move tasks below the `---` line and drop other text |
| `Working Memory has N lines; keep it to 12...` | The snapshot became a log | Move finished work into the tasks and drop old entries |
| `A Done section holds only '- [x]' tasks...` | An open task sits under a Done heading | Move it to the open tasks or under Waiting |
| `Each Waiting task needs 'Waiting on:' and 'Check after: YYYY-MM-DD'...` | A Waiting task has no date | Add a check date |
| `Write the revisit date as 'Check after: YYYY-MM-DD'...` | The date is not a real `YYYY-MM-DD` date | Correct the date |
| `Keep the link to <path>...` | A root export dropped a link to a subfolder list that still exists | Keep the link, or delete that subfolder's `AGENT_TODO.md` first |
| `Todo directory must be inside the repo` or `Todo directory does not exist` | The `directory` points outside the repo or at a missing folder | Use an existing folder inside the repo, relative to its root |
| `AGENT_TODO.md must not be a symbolic link.` | The file is a link to another file | Replace the link with a regular file |
| `The file lock ... could not be acquired.` | Another write held the lock for more than 10 seconds | Try the export again; if it persists, check no other process is stuck writing |
| `recent_commits` is always empty | The repo does not use Git, Git is not installed, or the file is new | Install Git or initialize the repo; the list fills after the first save |
<!-- Verified from: src/plain_todo_mcp/storage.py [resolve_repo, TodoStore, check_working_memory, check_task_sections, check_kept_links]; src/plain_todo_mcp/server.py [main, read_todo, export_todo] -->

## FAQ

### Does connecting the server change my files?

No. The agent writes only when you ask for an export.
<!-- Verified from: src/plain_todo_mcp/server.py [INSTRUCTIONS] -->

### Can the server read my conversation?

No. The agent reads the conversation and sends the merged file; the server
only checks and saves it.
<!-- Verified from: src/plain_todo_mcp/server.py [INSTRUCTIONS] -->

### Can two agents use the same file at once?

Yes. A lock lets one write at a time, and an export based on an out-of-date
read is rejected so the second agent rereads and merges. An editor that
ignores the lock can still race a write.
<!-- Verified from: src/plain_todo_mcp/storage.py [TodoStore.export] -->

### Does the server check that a task is really done?

No. The agent is told to mark tasks done only with evidence; the server
checks the file's format, not the work.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW] -->

### Does it work without Git?

Yes. The server uses the folder it was started in, and `read_todo` returns
no recent commits; everything else works.
<!-- Verified from: src/plain_todo_mcp/storage.py [resolve_repo, TodoStore.recent_commits] -->

### Should I commit AGENT_TODO.md?

That is up to you. Commit it to share the list, or ignore it to keep it
local. Always ignore `AGENT_TODO.md.lock`.
<!-- Verified from: src/plain_todo_mcp/server.py [EXPORT_WORKFLOW]; src/plain_todo_mcp/storage.py [TodoStore.__init__] -->

### How do I report a bug or request a feature?

Send bug reports and feature requests to
[support@plaintxtoffice.com](mailto:support@plaintxtoffice.com), through the
[contact page](https://plaintxtoffice.com/contact/), or in
[GitHub Issues](https://github.com/PlainTxtOffice/plain-todo-mcp/issues).
Include the server version, your MCP client, and the steps that led to the
problem.
<!-- Verified from: pyproject.toml [project.urls, project.maintainers]; https://plaintxtoffice.com/contact/ -->

## Glossary

| Term | Meaning |
| --- | --- |
| MCP | Model Context Protocol, the standard agents use to call tools such as Plain Todo |
| MCP server | A program that offers tools to agents; Plain Todo is one |
| MCP client | The program that runs your agent and starts MCP servers, such as Claude Code or VS Code |
| Tool | An action a server offers that the agent can call, such as `read_todo` |
| Prompt | A ready-made instruction a server offers that you can run from your client, such as `export` |
| Export | The agent saving the merged task list to `AGENT_TODO.md` |
| Revision | A fingerprint of the file's exact content, used to detect changes since the agent read it |
| Working Memory | The short Now, Next, and Blockers snapshot at the top of the file |
| Check after | A date before which a task is not treated as next work |
| Due task | An open task whose `Check after:` date has arrived |
| Waiting | The section for tasks blocked by something outside the repo |
| Subfolder list | An `AGENT_TODO.md` inside a subfolder, linked from the root file |

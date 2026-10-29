import asyncio
import os
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError

from plain_todo_mcp.server import EXPORT_WORKFLOW, build_server
from plain_todo_mcp.storage import (
    TodoConflictError,
    TodoStore,
    due_tasks,
    resolve_repo,
)


def test_repo_resolution(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src"
    nested.mkdir()
    assert resolve_repo({}, nested) == tmp_path
    (tmp_path / ".git").rmdir()
    (tmp_path / ".git").write_text("gitdir: elsewhere")
    assert resolve_repo({}, nested) == tmp_path
    assert resolve_repo({"TODO_REPO_PATH": "src"}, tmp_path) == nested
    (tmp_path / ".git").unlink()
    assert resolve_repo({}, nested) == nested
    with pytest.raises(ValueError):
        resolve_repo({"TODO_REPO_PATH": ""}, tmp_path)
    with pytest.raises(ValueError):
        resolve_repo({"TODO_REPO_PATH": "missing"}, tmp_path)


def test_create_and_merge(tmp_path: Path) -> None:
    store = TodoStore(tmp_path)
    first = store.read()
    assert first["exists"] is False
    assert first["revision"] == "missing"
    original = "# Agent Todo\n\n- [x] Verified task\n- [ ] Existing task\n"
    saved = store.export(original, first["revision"])
    merged = saved["content"] + "- [ ] New conversation task\n"
    updated = store.export(merged, saved["revision"])
    assert updated["path"] == str(tmp_path / "AGENT_TODO.md")
    assert updated["content"] == merged
    assert updated["exists"] is True
    assert "- [x] Verified task" in updated["content"]
    assert "- [ ] Existing task" in updated["content"]
    assert store.export(merged, updated["revision"]) == updated


def test_stale_revision_preserves_file(tmp_path: Path) -> None:
    store = TodoStore(tmp_path)
    saved = store.export("- [ ] First\n", "missing")
    with pytest.raises(TodoConflictError, match="Read it again"):
        store.export("- [ ] Stale\n", "missing")
    assert store.read() == saved
    store.path.write_text("- [x] Edited outside MCP\n")
    with pytest.raises(TodoConflictError):
        store.export("- [ ] New\n", saved["revision"])
    assert store.path.read_text() == "- [x] Edited outside MCP\n"


def test_empty_file_is_not_missing(tmp_path: Path) -> None:
    store = TodoStore(tmp_path)
    store.path.touch()
    assert store.read()["revision"] != "missing"
    with pytest.raises(TodoConflictError):
        store.export("- [ ] Task\n", "missing")


@pytest.mark.parametrize("content", ["", "# Todo\n", "- [ ] \n", "- [z] Bad"])
def test_invalid_content_does_not_write(
    tmp_path: Path, content: str,
) -> None:
    store = TodoStore(tmp_path)
    with pytest.raises(ValueError, match="at least one"):
        store.export(content, "missing")
    assert not store.path.exists()


MEMORY = "# Agent Todo\n\n## Working Memory\n\n{body}\n---\n\n- [ ] Task\n"


def test_working_memory_snapshot_saves(tmp_path: Path) -> None:
    body = (
        "- Now: Validate the snapshot\n"
        "  across two lines\n\n"
        "- Next: Update the README\n"
        "- Blockers: None\n"
    )
    saved = TodoStore(tmp_path).export(MEMORY.format(body=body), "missing")
    assert "across two lines" in saved["content"]


@pytest.mark.parametrize(("content", "error"), [
    ("## Working Memory\n\n- Now: a\n\n## Tasks\n\n- [ ] Task\n", "before"),
    ("- [ ] Task\n\n## Working Memory\n\n- Now: a\n", "above the tasks"),
    ("## Working Memory\n\n- Now: a\n- [ ] Task\n", "plain bullets"),
    (MEMORY.format(body="- [x] Done\n"), "plain bullets"),
    (MEMORY.format(body="- Done: shipped it\n"), "Done: shipped"),
    (MEMORY.format(body="Some intro text.\n"), "must start with"),
    (MEMORY.format(body="- Next: x\n" * 13), "13 lines"),
])
def test_working_memory_log_is_rejected(
    tmp_path: Path, content: str, error: str,
) -> None:
    store = TodoStore(tmp_path)
    with pytest.raises(ValueError, match=error):
        store.export(content, "missing")
    assert not store.path.exists()


SCHEDULED = """# Agent Todo

## Tasks

- [ ] Re-run the audit
      Check after: 2026-11-01
- [ ] Revisit later. Check after: 2026-12-01
- [x] Old revisit. Check after: 2026-01-01
- [ ] Undated task

## Waiting

- [ ] List the app. Waiting on: enrollment.
  - Check after: 2026-10-20

## Done

- [x] Shipped
"""


def test_due_tasks_and_scheduled_sections(tmp_path: Path) -> None:
    assert due_tasks(SCHEDULED, date(2026, 11, 1)) == [
        "Re-run the audit Check after: 2026-11-01",
        "List the app. Waiting on: enrollment. - Check after: 2026-10-20",
    ]
    assert due_tasks(SCHEDULED, date(2026, 10, 1)) == []
    TodoStore(tmp_path).export(SCHEDULED, "missing")


@pytest.mark.parametrize(("content", "error"), [
    ("## Done\n\n- [x] Shipped\n- [ ] Not yet\n", "Not yet"),
    ("## Done\n\n### text_csv\n\n- [ ] Nested open\n", "Nested open"),
    ("## Waiting\n\n- [ ] Blocked\n      Waiting on: Apple\n", "Waiting on: Apple"),
    ("- [ ] Revisit. Check after: next week\n", "YYYY-MM-DD"),
    ("- [ ] Revisit. Check after: 2026-02-30\n", "YYYY-MM-DD"),
])
def test_misplaced_open_tasks_are_rejected(
    tmp_path: Path, content: str, error: str,
) -> None:
    store = TodoStore(tmp_path)
    with pytest.raises(ValueError, match=error):
        store.export(content, "missing")
    assert not store.path.exists()


def test_recent_commits_since_last_save(tmp_path: Path) -> None:
    def git(*args: str, date: str | None = None) -> None:
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        if date:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = date
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                       env=env, capture_output=True)

    store = TodoStore(tmp_path)
    assert store.recent_commits() == []  # no file and no repository
    store.export("- [ ] Ship it\n", "missing")
    assert store.recent_commits() == []  # not a repository
    git("init")
    git("commit", "--allow-empty", "-m", "old work", date="2000-01-01T00:00:00+00:00")
    hour_ago = time.time() - 3600
    os.utime(store.path, (hour_ago, hour_ago))
    git("commit", "--allow-empty", "-m", "ship it")
    commits = store.recent_commits()
    assert len(commits) == 1
    assert commits[0].endswith(" ship it")


def test_subdirectory_todo_is_linked_from_root(tmp_path: Path) -> None:
    engine = tmp_path / "platform" / "engine"
    engine.mkdir(parents=True)
    root = TodoStore(tmp_path)
    root.export("# Agent Todo\n\n- [ ] Root task\n", "missing")
    sub = TodoStore(tmp_path, "platform/engine")
    assert sub.path == engine / "AGENT_TODO.md"
    saved = sub.export("# Agent Todo\n\n- [ ] Engine task\n", "missing")
    assert saved["path"] == str(engine / "AGENT_TODO.md")
    link = "- [platform/engine](platform/engine/AGENT_TODO.md)"
    assert root.read()["content"] == (
        f"# Agent Todo\n\n- [ ] Root task\n\n## Subdirectory Todos\n\n{link}\n"
    )
    sub.export("# Agent Todo\n\n- [ ] Engine task\n- [ ] More\n",
               saved["revision"])
    assert root.read()["content"].count(link) == 1
    assert TodoStore(tmp_path, str(engine)).path == sub.path
    assert TodoStore(tmp_path, ".").path == root.path


def test_link_joins_existing_section(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    TodoStore(tmp_path).export(
        "- [ ] Root\n\n## Subdirectory Todos\n\n## Done\n\n- [x] Old\n",
        "missing",
    )
    TodoStore(tmp_path, "a").export("- [ ] A\n", "missing")
    TodoStore(tmp_path, "b").export("- [ ] B\n", "missing")
    assert TodoStore(tmp_path).read()["content"] == (
        "- [ ] Root\n\n## Subdirectory Todos\n\n"
        "- [a](a/AGENT_TODO.md)\n- [b](b/AGENT_TODO.md)\n\n"
        "## Done\n\n- [x] Old\n"
    )


def test_subdirectory_without_root_file_creates_root(tmp_path: Path) -> None:
    (tmp_path / "engine").mkdir()
    TodoStore(tmp_path, "engine").export("- [ ] Engine\n", "missing")
    assert TodoStore(tmp_path).read()["content"] == (
        "# Agent Todo\n\n## Subdirectory Todos\n\n"
        "- [engine](engine/AGENT_TODO.md)\n"
    )


def test_root_export_must_keep_live_links(tmp_path: Path) -> None:
    (tmp_path / "engine").mkdir()
    TodoStore(tmp_path, "engine").export("- [ ] Engine\n", "missing")
    root = TodoStore(tmp_path)
    current = root.read()
    with pytest.raises(ValueError, match="Keep the link to engine/AGENT_TODO"):
        root.export("# Agent Todo\n\n- [ ] Root\n", current["revision"])
    assert root.read() == current
    root.export(current["content"] + "\n- [ ] Root\n", current["revision"])
    (tmp_path / "engine" / "AGENT_TODO.md").unlink()
    root.export("- [ ] Root\n", root.read()["revision"])


@pytest.mark.parametrize("directory", ["..", "missing", "../elsewhere"])
def test_subdirectory_must_exist_inside_repo(
    tmp_path: Path, directory: str,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "elsewhere").mkdir()
    with pytest.raises(ValueError, match="inside the repo|does not exist"):
        TodoStore(repo, directory)


def test_subdirectory_commits_are_scoped(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                       env=env, capture_output=True)

    git("init")
    (tmp_path / "engine").mkdir()
    sub = TodoStore(tmp_path, "engine")
    sub.export("- [ ] Engine\n", "missing")
    hour_ago = time.time() - 3600
    os.utime(sub.path, (hour_ago, hour_ago))
    (tmp_path / "engine" / "lib.rs").write_text("fn main() {}")
    git("add", "engine/lib.rs")
    git("commit", "-m", "engine work")
    (tmp_path / "other.txt").write_text("x")
    git("add", "other.txt")
    git("commit", "-m", "other work")
    commits = sub.recent_commits()
    assert len(commits) == 1
    assert commits[0].endswith(" engine work")


def test_failed_replace_preserves_original_and_cleans_temp(
    tmp_path: Path,
) -> None:
    store = TodoStore(tmp_path)
    saved = store.export("- [ ] Original\n", "missing")
    with patch.object(Path, "replace", side_effect=OSError("busy")):
        with pytest.raises(OSError, match="busy"):
            store.export("- [ ] New\n", saved["revision"])
    assert store.read() == saved
    assert not list(tmp_path.glob(".AGENT_TODO-*.tmp"))


def test_two_writers_cannot_overwrite_each_other(tmp_path: Path) -> None:
    def write(label: str) -> bool:
        try:
            TodoStore(tmp_path).export(f"- [ ] {label}\n", "missing")
        except TodoConflictError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["one", "two"]))
    assert sorted(results) == [False, True]
    assert TodoStore(tmp_path).read()["content"] in {
        "- [ ] one\n", "- [ ] two\n",
    }


def test_mcp_tools_and_export_prompt(tmp_path: Path) -> None:
    async def exercise() -> None:
        app = build_server(tmp_path)
        tools = {tool.name: tool for tool in await app.list_tools()}
        assert set(tools) == {"read_todo", "export_todo"}
        # Clients may drop server instructions, so tools repeat key rules.
        assert "TODO_REPO_PATH" in (tools["read_todo"].description or "")
        assert tools["read_todo"].annotations.idempotent_hint is True
        export_description = tools["export_todo"].description or ""
        assert "requested or agreed" in export_description
        assert "never save" in export_description
        assert "Working Memory" in export_description
        assert "Working Memory" in EXPORT_WORKFLOW
        assert tools["export_todo"].annotations.idempotent_hint is None
        prompt = await app.get_prompt("export")
        assert prompt.messages[0].content.text == EXPORT_WORKFLOW
        first = await app.call_tool("read_todo", {})
        assert not first.is_error
        assert first.structured_content["revision"] == "missing"
        assert first.structured_content["recent_commits"] == []
        assert first.structured_content["due_tasks"] == []
        assert "recent_commits" in EXPORT_WORKFLOW
        assert "due_tasks" in EXPORT_WORKFLOW
        saved = await app.call_tool("export_todo", {
            "content": "# Agent Todo\n\n- [ ] Conversation task\n",
            "expected_revision": "missing",
        })
        assert not saved.is_error
        assert saved.structured_content["exists"] is True
        with pytest.raises(ToolError, match="changed"):
            await app.call_tool("export_todo", {
                "content": "- [ ] Stale export\n",
                "expected_revision": "missing",
            })
        with pytest.raises(ToolError, match="at least one"):
            await app.call_tool("export_todo", {
                "content": "Not a todo list",
                "expected_revision": saved.structured_content["revision"],
            })
        (tmp_path / "engine").mkdir()
        sub = await app.call_tool("read_todo", {"directory": "engine"})
        assert sub.structured_content["path"] == str(
            tmp_path / "engine" / "AGENT_TODO.md"
        )
        await app.call_tool("export_todo", {
            "content": "- [ ] Engine task\n",
            "expected_revision": "missing",
            "directory": "engine",
        })
        root = await app.call_tool("read_todo", {})
        assert "(engine/AGENT_TODO.md)" in root.structured_content["content"]
        with pytest.raises(ToolError, match="inside the repo"):
            await app.call_tool("read_todo", {"directory": ".."})

    asyncio.run(exercise())


def test_stdio_client_roundtrip(tmp_path: Path) -> None:
    async def exercise() -> None:
        params = StdioServerParameters(
            command=str(
                Path(sys.executable).parent
                / ("plain-todo-mcp.exe" if os.name == "nt" else "plain-todo-mcp")
            ),
            env={**os.environ, "TODO_REPO_PATH": str(tmp_path)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert "no access to conversation history" in (
                    initialized.instructions
                )
                pyproject = tomllib.loads(
                    (Path(__file__).parents[1] / "pyproject.toml").read_text(
                        encoding="utf-8"
                    )
                )
                assert initialized.server_info.version == (
                    pyproject["project"]["version"]
                )
                prompts = await session.list_prompts()
                assert [p.name for p in prompts.prompts] == ["export"]
                first = await session.call_tool("read_todo", {})
                assert first.structured_content["path"] == str(
                    tmp_path / "AGENT_TODO.md"
                )
                saved = await session.call_tool("export_todo", {
                    "content": "# Agent Todo\n\n- [ ] Ship tested export\n",
                    "expected_revision": first.structured_content["revision"],
                })
                assert not saved.is_error
                stale = await session.call_tool("export_todo", {
                    "content": "- [ ] Stale\n",
                    "expected_revision": "missing",
                })
                assert stale.is_error
                assert "changed" in stale.content[0].text
        assert (tmp_path / "AGENT_TODO.md").read_text() == (
            "# Agent Todo\n\n- [ ] Ship tested export\n"
        )

    asyncio.run(exercise())

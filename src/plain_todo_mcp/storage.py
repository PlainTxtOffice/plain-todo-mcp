"""Read and atomically update the repository's todo document."""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NamedTuple, TypedDict

from filelock import FileLock

# Enough to cover a working session without flooding the agent's context.
MAX_RECENT_COMMITS = 30
HEADING = re.compile(r"(#{1,6})[ \t]+(.*?)[ \t]*$")
TASK = re.compile(r"[ \t]*- \[([ xX])\] (.*)")
CHECK_AFTER = re.compile(r"Check after: *(\d{4}-\d{2}-\d{2})\b")
WORKING_MEMORY_HEADING = re.compile(r"(?m)^## Working Memory[ \t]*$")
WORKING_MEMORY_BULLETS = ("- Now:", "- Next:", "- Blockers:")
# Enough for a wrapped bullet each; more means the snapshot became a log.
MAX_WORKING_MEMORY_LINES = 12
SUBDIRECTORY_HEADING = "## Subdirectory Todos"
TODO_LINK = re.compile(r"\]\(<?([^)<>]*AGENT_TODO\.md)>?\)")
NEXT_SECTION = re.compile(r"(?m)^#{1,2}[ \t]")


def check_working_memory(content: str) -> None:
    """Reject a Working Memory section that has grown beyond a snapshot."""
    heading = WORKING_MEMORY_HEADING.search(content)
    if heading is None:
        return
    lines = []
    for line in content[heading.end() :].splitlines():
        if line.strip() == "---":
            break
        if line.startswith("#"):
            message = (
                "Close Working Memory with a '---' line before the next "
                "heading."
            )
            raise ValueError(message)
        if re.match(r"\s*- \[[ xX]\]", line):
            message = (
                "Working Memory holds plain bullets only; move '- [ ]' and "
                "'- [x]' tasks below its '---' line."
            )
            raise ValueError(message)
        if (
            line.strip()
            and not line[0].isspace()
            and not line.startswith(WORKING_MEMORY_BULLETS)
        ):
            message = (
                "Working Memory bullets must start with 'Now:', 'Next:', or "
                f"'Blockers:'. Move this into the tasks or drop it: {line}"
            )
            raise ValueError(message)
        if line.strip():
            lines.append(line)
    else:
        message = "Close Working Memory with a '---' line above the tasks."
        raise ValueError(message)
    if len(lines) > MAX_WORKING_MEMORY_LINES:
        message = (
            f"Working Memory has {len(lines)} lines; keep it to "
            f"{MAX_WORKING_MEMORY_LINES}. Move finished work into the tasks "
            "as '- [x]' and drop entries that are no longer current."
        )
        raise ValueError(message)


class Task(NamedTuple):
    """One checkbox task with its wrapped lines and sub-bullets joined."""

    sections: tuple[str, ...]
    done: bool
    text: str


def parse_tasks(content: str) -> list[Task]:
    """Group each checkbox line with the indented lines below it."""
    tasks: list[Task] = []
    headings: list[tuple[int, str]] = []
    in_task = False
    for line in content.splitlines():
        heading = HEADING.match(line)
        task = TASK.match(line)
        if heading:
            level = len(heading[1])
            headings = [h for h in headings if h[0] < level]
            headings.append((level, heading[2].lower()))
        elif task:
            sections = tuple(title for _, title in headings)
            tasks.append(Task(sections, task[1] != " ", task[2]))
        elif in_task and line[:1].isspace() and line.strip():
            last = tasks[-1]
            tasks[-1] = last._replace(text=f"{last.text} {line.strip()}")
            continue
        in_task = task is not None
    return tasks


def check_after(task: Task) -> date | None:
    """Return the task's revisit date, or None when it has no valid one."""
    found = CHECK_AFTER.search(task.text)
    if found is None:
        return None
    try:
        return date.fromisoformat(found[1])
    except ValueError:
        return None


def due_tasks(content: str, today: date) -> list[str]:
    """List open tasks whose revisit date has arrived."""
    return [
        task.text
        for task in parse_tasks(content)
        if not task.done
        and (revisit := check_after(task)) is not None
        and revisit <= today
    ]


def check_task_sections(content: str) -> None:
    """Reject open tasks under Done and undated or misdated revisits."""
    for task in parse_tasks(content):
        if task.done:
            continue
        if "done" in task.sections:
            message = (
                "A Done section holds only '- [x]' tasks. Move this open task "
                "to the open tasks, or under '## Waiting' with 'Check after: "
                f"YYYY-MM-DD' if it is blocked: {task.text}"
            )
            raise ValueError(message)
        dated = check_after(task) is not None
        if "Check after:" in task.text and not dated:
            message = (
                f"Write the revisit date as 'Check after: YYYY-MM-DD': "
                f"{task.text}"
            )
            raise ValueError(message)
        if "waiting" in task.sections and not dated:
            message = (
                "Each Waiting task needs 'Waiting on:' and 'Check after: "
                f"YYYY-MM-DD' so it gets checked again: {task.text}"
            )
            raise ValueError(message)


def linked_todos(content: str, folder: Path) -> set[Path]:
    """Resolve the AGENT_TODO.md files that Markdown links point to."""
    return {(folder / href).resolve() for href in TODO_LINK.findall(content)}


def check_kept_links(old: str, new: str, folder: Path) -> None:
    """Reject dropping a link to a subdirectory todo that still exists."""
    kept = linked_todos(new, folder)
    for todo in sorted(linked_todos(old, folder) - kept):
        if todo.is_file():
            href = todo.relative_to(folder).as_posix()
            message = (
                f"Keep the link to {href}: that subdirectory still has its "
                f"own AGENT_TODO.md, listed under '{SUBDIRECTORY_HEADING}'."
            )
            raise ValueError(message)


def with_link(content: str, link: str) -> str:
    """Add a link bullet under Subdirectory Todos, creating the section."""
    if not content.strip():
        return f"# Agent Todo\n\n{SUBDIRECTORY_HEADING}\n\n{link}\n"
    heading = re.search(
        rf"(?m)^{re.escape(SUBDIRECTORY_HEADING)}[ \t]*$", content
    )
    if heading is None:
        return f"{content.rstrip()}\n\n{SUBDIRECTORY_HEADING}\n\n{link}\n"
    after = NEXT_SECTION.search(content, heading.end())
    cut = after.start() if after else len(content)
    body = content[heading.end() : cut].strip()
    links = f"{body}\n{link}" if body else link
    section = f"{content[: heading.end()]}\n\n{links}\n"
    return f"{section}\n{content[cut:]}" if after else section


class TodoSnapshot(TypedDict):
    """The file content and revision required for a safe export."""

    path: str
    exists: bool
    content: str
    revision: str


class TodoContext(TodoSnapshot):
    """A snapshot plus evidence of work finished since the last save."""

    recent_commits: list[str]
    due_tasks: list[str]


class TodoConflictError(ValueError):
    """The todo document changed after the agent read it."""


def resolve_repo(environ: Mapping[str, str], cwd: Path) -> Path:
    """Use an explicit repo directory, the nearest git root, or cwd."""
    override = environ.get("TODO_REPO_PATH")
    if override is not None:
        if not override.strip():
            message = "TODO_REPO_PATH must not be empty."
            raise ValueError(message)
        root = (cwd / override).resolve()
    else:
        start = cwd.resolve()
        root = next(
            (
                folder
                for folder in (start, *start.parents)
                if (folder / ".git").exists()
            ),
            start,
        )
    if not root.is_dir():
        message = f"Todo repository directory does not exist: {root}"
        raise ValueError(message)
    return root


class TodoStore:
    """Protect cooperating agents from lost updates using a revision."""

    def __init__(self, repo: Path, directory: str = "") -> None:
        """Bind the store to the repo's document or a subdirectory's."""
        self.repo = repo
        folder = (repo / directory).resolve()
        if folder == repo.resolve():
            folder = repo
        elif not folder.is_relative_to(repo.resolve()):
            message = f"Todo directory must be inside the repo: {directory}"
            raise ValueError(message)
        elif not folder.is_dir():
            message = f"Todo directory does not exist: {folder}"
            raise ValueError(message)
        self.path = folder / "AGENT_TODO.md"
        self.lock = FileLock(str(self.path) + ".lock", timeout=10)

    @property
    def in_subdirectory(self) -> bool:
        """Whether this document covers a subdirectory, not the repo."""
        return self.path.parent != self.repo

    def read(self) -> TodoSnapshot:
        """Read UTF-8 Markdown and a hash of its exact bytes."""
        if self.path.is_symlink():
            message = "AGENT_TODO.md must not be a symbolic link."
            raise ValueError(message)
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {
                "path": str(self.path),
                "exists": False,
                "content": "",
                "revision": "missing",
            }
        return {
            "path": str(self.path),
            "exists": True,
            "content": raw.decode("utf-8"),
            "revision": hashlib.sha256(raw).hexdigest(),
        }

    def recent_commits(self) -> list[str]:
        """List commits made since AGENT_TODO.md was last saved, newest first.

        Gives the agent evidence of work finished outside its conversation.
        A subdirectory's document lists only commits touching that folder.
        Returns nothing when the file is missing or git cannot answer.
        """
        git = shutil.which("git")
        if git is None or not self.path.is_file():
            return []
        saved = datetime.fromtimestamp(self.path.stat().st_mtime, UTC)
        # A pathspec would also hide commits without file changes.
        scope = ["--", "."] if self.in_subdirectory else []
        try:
            result = subprocess.run(  # noqa: S603
                [
                    git,
                    "-C",
                    str(self.path.parent),
                    "log",
                    f"--since={saved.isoformat()}",
                    f"--max-count={MAX_RECENT_COMMITS}",
                    "--format=%h %s",
                    *scope,
                ],
                capture_output=True,
                check=True,
                encoding="utf-8",
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return result.stdout.splitlines()

    def export(self, content: str, expected_revision: str) -> TodoSnapshot:
        """Save merged Markdown only if the observed revision still matches."""
        if not re.search(r"(?m)^- \[[ xX]\] \S", content):
            message = (
                "Provide Markdown with at least one '- [ ]' or '- [x]' task."
            )
            raise ValueError(message)
        check_working_memory(content)
        check_task_sections(content)
        normalized = content.rstrip() + "\n"
        with self.lock:
            current = self.read()
            if current["revision"] != expected_revision:
                message = (
                    "AGENT_TODO.md changed. Read it again, merge your tasks "
                    "with the latest content, and retry with its revision."
                )
                raise TodoConflictError(message)
            check_kept_links(
                current["content"], normalized, self.path.parent.resolve()
            )
            if current["content"] != normalized:
                self._replace(normalized)
                current = self.read()
        if self.in_subdirectory:
            TodoStore(self.repo).link(self.path)
        return current

    def link(self, todo: Path) -> None:
        """List a subdirectory's AGENT_TODO.md here unless already linked."""
        folder = self.path.parent.resolve()
        todo = todo.resolve()
        with self.lock:
            content = self.read()["content"]
            if todo in linked_todos(content, folder):
                return
            href = todo.relative_to(folder).as_posix()
            label = todo.parent.relative_to(folder).as_posix()
            target = f"<{href}>" if " " in href else href
            self._replace(with_link(content, f"- [{label}]({target})"))

    def _replace(self, normalized: str) -> None:
        """Atomically replace the document; callers hold the lock."""
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".AGENT_TODO-",
                suffix=".tmp",
                dir=self.path.parent,
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)
                temp.write(normalized)
                temp.flush()
                os.fsync(temp.fileno())
            temp_path.replace(self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

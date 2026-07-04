"""Daily note and vault file parser."""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DailyNoteSections:
    focus: str = ""
    schedule: list[tuple[str, str]] = field(default_factory=list)
    directives: list[tuple[str, bool]] = field(default_factory=list)


@dataclass
class VaultState:
    schedule: list[tuple[str, str]] = field(default_factory=list)
    directives: list[tuple[str, bool]] = field(default_factory=list)
    documents: list[tuple[str, float]] = field(default_factory=list)
    focus: str = ""
    metrics: dict = field(default_factory=dict)
    goal: dict = field(default_factory=dict)
    queue_summary: dict = field(default_factory=dict)

    @property
    def active_jobs(self) -> int:
        return self.queue_summary.get("active", 0)

    @property
    def queued_jobs(self) -> int:
        return self.queue_summary.get("queued", 0)


def parse_daily_note(path: Path) -> DailyNoteSections:
    """Parse schedule, directives, and focus sections from a daily note."""
    result = DailyNoteSections()
    if not path.exists():
        return result

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return result

    text = _strip_frontmatter(text)

    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            if heading == "schedule":
                section = "schedule"
            elif heading in ("directives", "todo"):
                section = "directives"
            elif heading == "focus":
                section = "focus"
            else:
                section = None
            continue

        if section == "schedule" and re.match(r"^-\s*\d{2}:\d{2}", stripped):
            m = re.match(r"^-\s*(\d{2}:\d{2})\s*(.+)", stripped)
            if m:
                result.schedule.append((m.group(1), m.group(2).strip()))
        elif section == "directives" and stripped.startswith("- ["):
            done = stripped.startswith("- [x]") or stripped.startswith("- [X]")
            task = re.sub(r"^-\s*\[[ xX]\]\s*", "", stripped).strip()
            result.directives.append((task, done))
        elif section == "focus":
            if stripped and not stripped.startswith("#"):
                result.focus += f" {stripped}"

    return result


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}
    try:
        parts = stripped.split("---", 2)
        if len(parts) >= 2:
            return yaml.safe_load(parts[1]) or {}
    except Exception:
        pass
    return {}


def _strip_frontmatter(text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("---"):
        end = stripped.find("---", 4)
        if end != -1:
            return text[end + 4:]
    return text


def toggle_checkbox(path: Path, task_text: str, state: bool) -> dict:
    """Toggle a checkbox in a daily note. Returns the updated directive list."""
    if not path.exists():
        return {"directives": []}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return {"directives": []}

    task_pattern = re.compile(
        r"^(\s*-\s*)\[[ xX]\](\s*)(" + re.escape(task_text) + r")(.*)$", re.MULTILINE
    )
    new_marker = "[x]" if state else "[ ]"
    replacement = r"\1" + new_marker + r"\2\3\4"

    new_text, count = task_pattern.subn(replacement, text, count=1)
    if count > 0:
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError:
            pass
        parsed = parse_daily_note(path)
        return {"directives": [(t, d) for t, d in parsed.directives]}

    return {"directives": []}


def read_metrics(vault_root: Path) -> dict:
    """Read 90-system/metrics.json."""
    metrics_path = vault_root / "90-system" / "metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_goal(vault_root: Path) -> dict:
    """Read 90-system/goal.yaml."""
    goal_path = vault_root / "90-system" / "goal.yaml"
    if not goal_path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(goal_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def list_documents(vault_root: Path, folder: str = "04-notes", limit: int = 5) -> list[tuple[str, float]]:
    """List newest N markdown files by mtime."""
    doc_dir = vault_root / folder
    if not doc_dir.exists():
        return []
    files = []
    for f in doc_dir.rglob("*.md"):
        try:
            files.append((f.relative_to(vault_root), f.stat().st_mtime))
        except OSError:
            continue
    files.sort(key=lambda x: x[1], reverse=True)
    return files[:limit]


def get_current_schedule_line(schedule: list[tuple[str, str]]) -> str:
    """Return the schedule entry whose time window contains now."""
    if not schedule:
        return ""
    now = time.strftime("%H:%M")
    last = None
    for tm, task in schedule:
        if now >= tm:
            last = tm
        else:
            break
    return last or ""

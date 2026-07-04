"""Parser tests — daily note sections, checkbox toggle, frontmatter extraction."""

import shutil
import textwrap
from pathlib import Path

import pytest

from src.vault_tab.core.parser import (
    DailyNoteSections,
    parse_daily_note,
    parse_frontmatter,
    toggle_checkbox,
)


DEMO_VAULT = Path("/tmp/vibeflow/agent/demo-vault")


class TestParseDailyNote:
    def test_parse_demo_daily_note(self):
        daily = DEMO_VAULT / "01-daily" / "2026-07-03.md"
        result = parse_daily_note(daily)
        assert len(result.schedule) >= 3
        assert result.schedule[0][0] == "09:00"
        assert result.schedule[0][1] == "Standup review"

    def test_parse_directives(self):
        daily = DEMO_VAULT / "01-daily" / "2026-07-03.md"
        result = parse_daily_note(daily)
        assert len(result.directives) >= 3
        # Check done/undone state
        done_items = [t for t, d in result.directives if d]
        undone_items = [t for t, d in result.directives if not d]
        assert len(done_items) >= 1
        assert len(undone_items) >= 1

    def test_parse_focus(self):
        daily = DEMO_VAULT / "01-daily" / "2026-07-03.md"
        result = parse_daily_note(daily)
        assert "Oschertator" in result.focus or "pipeline" in result.focus

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        result = parse_daily_note(tmp_path / "nope.md")
        assert result.schedule == []
        assert result.directives == []
        assert result.focus == ""

    def test_empty_file_returns_empty(self, tmp_path: Path):
        fp = tmp_path / "empty.md"
        fp.write_text("")
        result = parse_daily_note(fp)
        assert result.schedule == []
        assert result.directives == []
        assert result.focus == ""


class TestToggleCheckbox:
    def test_mark_checkbox_done(self, tmp_path: Path):
        fp = tmp_path / "test.md"
        fp.write_text("## Directives\n\n- [ ] Buy groceries\n- [ ] Clean house\n")
        result = toggle_checkbox(fp, "Buy groceries", True)
        assert result["directives"][0] == ("Buy groceries", True)
        content = fp.read_text()
        assert "- [x] Buy groceries" in content

    def test_uncheck_checkbox(self, tmp_path: Path):
        fp = tmp_path / "test.md"
        fp.write_text("## Directives\n\n- [x] Buy groceries\n- [ ] Clean house\n")
        result = toggle_checkbox(fp, "Buy groceries", False)
        assert result["directives"][0] == ("Buy groceries", False)
        content = fp.read_text()
        assert "- [ ] Buy groceries" in content

    def test_no_matching_task(self, tmp_path: Path):
        fp = tmp_path / "test.md"
        fp.write_text("- [ ] Buy groceries\n")
        result = toggle_checkbox(fp, "Nonexistent task", True)
        assert result["directives"] == []

    def test_nonexistent_file(self, tmp_path: Path):
        result = toggle_checkbox(tmp_path / "nope.md", "anything", True)
        assert result["directives"] == []


class TestFrontmatter:
    def test_extract_valid_frontmatter(self):
        text = "---\ntitle: My Title\ntags:\n  - tag1\n  - tag2\n---\n\nBody"
        fm = parse_frontmatter(text)
        assert fm["title"] == "My Title"
        assert fm["tags"] == ["tag1", "tag2"]

    def test_no_frontmatter(self):
        fm = parse_frontmatter("Just plain text\n\nNo frontmatter")
        assert fm == {}

    def test_empty_frontmatter(self):
        text = "---\n---\n\nBody"
        fm = parse_frontmatter(text)
        assert fm == {}

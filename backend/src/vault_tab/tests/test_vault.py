"""VaultWriter tests — path guard, collisions, frontmatter, move, rename+link-rewrite."""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.vault_tab.core.vault import VaultWriter, VaultWriteError


@pytest.fixture
def vault(tmp_path: Path):
    """Create a temporary vault with some test notes."""
    root = tmp_path / "vault"
    root.mkdir()
    # Create some seed content
    (root / "04-notes").mkdir()
    (root / "99-archive").mkdir()

    (root / "04-notes" / "alpha.md").write_text(
        "---\ntitle: Alpha\n---\n\nContent of alpha.\n"
    )
    (root / "04-notes" / "beta.md").write_text(
        "---\ntitle: Beta\n---\n\nLinks: [[alpha]] and [[alpha|Alpha Note]]\n"
    )
    return root


class TestPathGuard:
    def test_write_inside_vault_succeeds(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/new-note.md", "hello", mode="create")
        assert (vault / "04-notes" / "new-note.md").exists()

    def test_write_escape_dotdot_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Path escapes vault"):
            writer.write("../../etc/passwd", "malicious")

    def test_write_escape_absolute_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Path escapes vault"):
            writer.write(f"/etc/passwd", "malicious")

    def test_move_inside_vault_succeeds(self, vault: Path):
        writer = VaultWriter(vault)
        writer.move("04-notes/alpha.md", "99-archive/alpha.md")
        assert (vault / "99-archive" / "alpha.md").exists()
        assert not (vault / "04-notes" / "alpha.md").exists()

    def test_move_source_not_found_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Source not found"):
            writer.move("nonexistent.md", "04-notes/dest.md")

    def test_move_escape_src_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Path escapes vault"):
            writer.move("../../etc/passwd", "04-notes/safe.md")

    def test_move_escape_dst_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Path escapes vault"):
            writer.move("04-notes/alpha.md", "../../etc/safe")


class TestCreateMode:
    def test_create_writes_frontmatter_and_content(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/test.md", "body text", mode="create")
        content = (vault / "04-notes" / "test.md").read_text()
        assert "body text" in content
        assert "---" in content

    def test_create_collision_suffix(self, vault: Path):
        """If dest already exists, appends -1, -2, ..."""
        writer = VaultWriter(vault)
        alpha = vault / "04-notes" / "alpha.md"
        orig = alpha.read_text()
        writer.write("04-notes/alpha.md", "v2", mode="create")
        # Original untouched
        assert alpha.read_text() == orig
        # Collision file created
        c1 = vault / "04-notes" / "alpha-1.md"
        assert c1.exists()
        assert "v2" in c1.read_text()

    def test_create_second_collision_suffix(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/alpha.md", "v2", mode="create")
        writer.write("04-notes/alpha.md", "v3", mode="create")
        assert (vault / "04-notes" / "alpha-1.md").exists()
        assert (vault / "04-notes" / "alpha-2.md").exists()


class TestOverwriteMode:
    def test_overwrite_replaces_content(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/alpha.md", "REPLACED", mode="overwrite")
        content = (vault / "04-notes" / "alpha.md").read_text()
        assert "REPLACED" in content

    def test_overwrite_new_file(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/new.md", "brand new", mode="overwrite")
        assert (vault / "04-notes" / "new.md").read_text().strip().startswith("---")


class TestAppendMode:
    def test_append_to_existing(self, vault: Path):
        writer = VaultWriter(vault)
        orig = (vault / "04-notes" / "alpha.md").read_text()
        writer.write("04-notes/alpha.md", "APPENDED", mode="append")
        content = (vault / "04-notes" / "alpha.md").read_text()
        assert orig in content
        assert "APPENDED" in content

    def test_append_to_new_file(self, vault: Path):
        writer = VaultWriter(vault)
        writer.write("04-notes/new.md", "first", mode="append")
        content = (vault / "04-notes" / "new.md").read_text()
        assert "first" in content


class TestRenameAndRewriteLinks:
    def test_rename_file(self, vault: Path):
        writer = VaultWriter(vault)
        writer.rename_and_rewrite_links("04-notes/alpha.md", "04-notes/renamed.md")
        assert not (vault / "04-notes" / "alpha.md").exists()
        assert (vault / "04-notes" / "renamed.md").exists()

    def test_rewrite_stem_wikilinks(self, vault: Path):
        writer = VaultWriter(vault)
        writer.rename_and_rewrite_links("04-notes/alpha.md", "04-notes/renamed.md")
        beta = (vault / "04-notes" / "beta.md").read_text()
        assert "[[renamed]]" in beta
        assert "[[alpha]]" not in beta

    def test_rewrite_alias_wikilinks(self, vault: Path):
        writer = VaultWriter(vault)
        writer.rename_and_rewrite_links("04-notes/alpha.md", "04-notes/renamed.md")
        beta = (vault / "04-notes" / "beta.md").read_text()
        # [[alpha|Alpha Note]] should become [[renamed|Alpha Note]]
        assert "[[renamed|Alpha Note]]" in beta

    def test_source_not_found_raises(self, vault: Path):
        writer = VaultWriter(vault)
        with pytest.raises(VaultWriteError, match="Source not found"):
            writer.rename_and_rewrite_links("nonexistent.md", "04-notes/dest.md")


class TestDryRunRename:
    def test_dry_run_counts_affected_files(self, vault: Path):
        writer = VaultWriter(vault)
        count = writer.dry_run_rename("04-notes/alpha.md", "04-notes/renamed.md")
        assert count >= 1  # beta.md has [[alpha]]


class TestRewriteWikilinksDirectly:
    def test_rewrite_exact_name(self, vault: Path):
        writer = VaultWriter(vault)
        text = "Hello [[oldfile.md]] goodbye"
        result = writer._rewrite_wikilinks(text, "oldfile.md", "newfile.md", "oldfile", "newfile")
        assert "[[newfile.md]]" in result
        assert "[[oldfile.md]]" not in result

    def test_rewrite_stem(self, vault: Path):
        writer = VaultWriter(vault)
        text = "Link [[oldfile]] here"
        result = writer._rewrite_wikilinks(text, "oldfile.md", "newfile.md", "oldfile", "newfile")
        assert "[[newfile]]" in result

    def test_rewrite_preserves_alias(self, vault: Path):
        writer = VaultWriter(vault)
        text = "Link [[oldfile|Friendly Name]] here"
        result = writer._rewrite_wikilinks(text, "oldfile.md", "newfile.md", "oldfile", "newfile")
        assert "[[newfile|Friendly Name]]" in result

    def test_no_rewrite_unrelated_link(self, vault: Path):
        writer = VaultWriter(vault)
        text = "Link [[other]] stays"
        result = writer._rewrite_wikilinks(text, "oldfile", "newfile", "oldfile", "newfile")
        assert "[[other]]" in result
        assert "[[newfile]]" not in result

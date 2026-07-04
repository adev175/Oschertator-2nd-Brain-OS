"""VaultWriter - THE ONLY module that writes to the vault."""

import os
import re
import time
from pathlib import Path
from typing import Literal

VaultMode = Literal["create", "append", "overwrite"]


class VaultWriteError(Exception):
    pass


class VaultWriter:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root.resolve()
        if not self.vault_root.exists():
            self.vault_root.mkdir(parents=True, exist_ok=True)

    def _guard(self, rel_path: str) -> Path:
        resolved = (self.vault_root / rel_path).resolve()
        if not str(resolved).startswith(str(self.vault_root)):
            raise VaultWriteError(f"Path escapes vault: {rel_path}")
        return resolved

    def _write(self, full_path: Path, mode: VaultMode, content: str, skill: str = "", job_id: str = ""):
        parent = full_path.parent
        parent.mkdir(parents=True, exist_ok=True)

        frontmatter = (
            f"---\nskill: {skill}\njob_id: {job_id}\ncreated: '{self._iso_now()}'\n---\n\n"
        )

        if mode == "overwrite":
            full_path.write_text(frontmatter + content, encoding="utf-8")
        elif mode == "append":
            if full_path.exists():
                existing = full_path.read_text(encoding="utf-8")
                full_path.write_text(existing + "\n" + content + "\n", encoding="utf-8")
            else:
                full_path.write_text(frontmatter + content, encoding="utf-8")
        elif mode == "create":
            safe = self._collision_safe(full_path, content=frontmatter + content, skill=skill, job_id=job_id)
            safe.write_text(frontmatter + content, encoding="utf-8")

    def write(self, rel_path: str, content: str, mode: VaultMode = "create", skill: str = "", job_id: str = ""):
        full = self._guard(rel_path)
        self._write(full, mode, content, skill=skill, job_id=job_id)

    def move(self, src_rel: str, dst_rel: str):
        src = self._guard(src_rel)
        dst = self._guard(dst_rel)
        if not src.exists():
            raise VaultWriteError(f"Source not found: {src_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)

    def rename_and_rewrite_links(self, old_rel: str, new_rel: str):
        old_full = self._guard(old_rel)
        new_full = self._guard(new_rel)

        if not old_full.exists():
            raise VaultWriteError(f"Source not found: {old_rel}")

        old_name = old_full.name
        new_name = new_full.name
        old_stem = old_full.stem
        new_stem = new_full.stem

        move_succeeded = False
        try:
            new_full.parent.mkdir(parents=True, exist_ok=True)
            old_full.rename(new_full)
            move_succeeded = True
        except OSError as e:
            raise VaultWriteError(f"Cannot rename vault file: {e}")

        for md_file in self.vault_root.rglob("*.md"):
            if md_file == new_full:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            rewritten = self._rewrite_wikilinks(text, old_name, new_name, old_stem, new_stem)
            if rewritten != text:
                try:
                    md_file.write_text(rewritten, encoding="utf-8")
                except OSError:
                    raise VaultWriteError(f"Cannot write back: {md_file}")

    def dry_run_rename(self, old_rel: str, new_rel: str) -> int:
        old_full = self._guard(old_rel)
        new_full = self._guard(new_rel)
        old_name = old_full.name
        new_name = new_full.name
        old_stem = old_full.stem
        new_stem = new_full.stem

        count = 0
        for md_file in self.vault_root.rglob("*.md"):
            if md_file == old_full:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            _new = self._rewrite_wikilinks(text, old_name, new_name, old_stem, new_stem)
            if _new != text:
                count += 1
        return count

    def _rewrite_wikilinks(
        self, text: str, old_name: str, new_name: str, old_stem: str, new_stem: str
    ) -> str:
        escaped_name = re.escape(old_name)
        escaped_stem = re.escape(old_stem)
        # Match [[target|alias]] where target is old_name or old_stem
        pattern = r"\[\[(" + escaped_name + "|" + escaped_stem + r")(\|[^]]*)?\]\]"

        def replacer(m):
            target = m.group(1)
            alias_part = m.group(2) or ""  # e.g. "|Nice Alias"
            if target == old_name:
                return "[[" + new_name + alias_part + "]]"
            if target == old_stem:
                return "[[" + new_stem + alias_part + "]]"
            return m.group(0)

        return re.sub(pattern, replacer, text)

    def _collision_safe(self, full: Path, content: str = "", skill: str = "", job_id: str = "") -> Path:
        if not full.exists():
            return full
        stem = full.stem
        suffix = 1
        while True:
            new_name = f"{stem}-{suffix}{full.suffix}"
            candidate = full.with_name(new_name)
            if not candidate.exists():
                return candidate
            suffix += 1

    @staticmethod
    def _iso_now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime())

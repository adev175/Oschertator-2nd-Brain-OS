"""Graph index builder for vault wikilinks."""

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

WIKILINK_RE = re.compile(r"\[\[([^]\|]+)(?:\|([^\]]+))?\]\]")
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")


@dataclass
class GraphNode:
    id: str
    title: str
    folder: str
    tags: list[str]
    out_degree: int = 0
    in_degree: int = 0
    mtime: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class GraphEdge:
    source: str
    target: str

    def to_dict(self):
        return asdict(self)


class GraphIndex:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root.resolve()
        cache_dir = self.vault_root / "90-system"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = cache_dir / "graph-cache.json"

    @property
    def _cache_valid(self) -> bool:
        if not self._cache_file.exists():
            return False
        cache_mtime = self._cache_file.stat().st_mtime
        for md in self.vault_root.rglob("*.md"):
            if md == self._cache_file:
                continue
            try:
                if md.stat().st_mtime > cache_mtime:
                    return False
            except OSError:
                continue
        return True

    def build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        if self._cache_valid:
            return self._load_cache()
        return self._build()

    def _build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        notes = {str(f.relative_to(self.vault_root)): f for f in self.vault_root.rglob("*.md")}
        basename_map = self._build_basename_map(notes)
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        edge_set = set()

        for rel_id, full in notes.items():
            p = Path(rel_id)
            title = self._parse_title(full)
            folder = str(p.parent) if str(p.parent) != "." else ""
            tags = self._parse_tags(full, rel_id)
            mtime = self._safe_mtime(full)
            nodes[rel_id] = GraphNode(
                id=rel_id, title=title or p.stem, folder=folder, tags=tags, mtime=mtime
            )

        for rel_id, full in notes.items():
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            cleaned = CODE_FENCE_RE.sub("", text)
            for match in WIKILINK_RE.finditer(cleaned):
                raw_ref = match.group(1).strip()
                target_rel = self._resolve_link(raw_ref, Path(rel_id), basename_map)
                if target_rel and target_rel in notes and target_rel != rel_id:
                    if (rel_id, target_rel) not in edge_set:
                        edges.append(GraphEdge(source=rel_id, target=target_rel))
                        edge_set.add((rel_id, target_rel))

        for edge in edges:
            if edge.source in nodes:
                nodes[edge.source].out_degree += 1
            if edge.target in nodes:
                nodes[edge.target].in_degree += 1

        node_list = list(nodes.values())
        self._save_cache(node_list, edges)
        return node_list, edges

    def filter(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        folder: str = "",
        tag: str = "",
        q: str = "",
        limit: int = 400,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        filtered = nodes
        if folder:
            filtered = [n for n in filtered if n.folder.startswith(folder)]
        if tag:
            filtered = [n for n in filtered if tag.lower() in [t.lower() for t in n.tags]]
        if q:
            ql = q.lower()
            filtered = [n for n in filtered if ql in n.title.lower() or ql in n.id.lower()]
        filtered.sort(key=lambda n: n.in_degree + n.out_degree, reverse=True)
        if limit and len(filtered) > limit:
            filtered = filtered[:limit]
        node_ids = {n.id for n in filtered}
        filtered_edges = [e for e in edges if e.source in node_ids and e.target in node_ids]
        return filtered, filtered_edges

    def get_note_links(self, note_path: str) -> dict:
        notes = {str(f.relative_to(self.vault_root)): f for f in self.vault_root.rglob("*.md")}
        basename_map = self._build_basename_map(notes)
        note_rel = self._find_note(note_path, notes)
        if note_rel is None or note_rel not in notes:
            return {"outgoing": [], "backlinks": [], "unlinked_mentions": []}
        full = notes[note_rel]
        outgoing = self._parse_outgoing_links(full, note_rel, basename_map, notes)
        backlinks = self._find_backlinks(notes, note_rel, basename_map)
        return {"outgoing": outgoing, "backlinks": backlinks, "unlinked_mentions": []}

    def get_unlinked_mentions(self, note_path: str) -> list[dict]:
        notes = {str(f.relative_to(self.vault_root)): f for f in self.vault_root.rglob("*.md")}
        note_rel = self._find_note(note_path, notes)
        if note_rel is None or note_rel not in notes:
            return []
        full = notes[note_rel]
        stem = full.stem
        mentions = []
        for rel, src_full in notes.items():
            if rel == note_rel:
                continue
            try:
                text = src_full.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            cleaned = CODE_FENCE_RE.sub("", text)
            if re.search(r"\b" + re.escape(stem) + r"\b", cleaned):
                idx = cleaned.index(stem) if stem in cleaned else -1
                if idx >= 0:
                    line_start = text.rfind("\n", 0, idx) + 1
                    line_end = text.find("\n", idx)
                    if line_end == -1:
                        line_end = len(text)
                    context = text[line_start:line_end].strip()[:120]
                    mentions.append({"source": rel, "context": context})
        return mentions[:20]

    def _parse_outgoing_links(self, full: Path, note_rel: str, basename_map, notes: dict) -> list[dict]:
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return []
        cleaned = CODE_FENCE_RE.sub("", text)
        links = []
        for match in WIKILINK_RE.finditer(cleaned):
            raw_ref = match.group(1).strip()
            alias = match.group(2)
            target_rel = self._resolve_link(raw_ref, Path(note_rel), basename_map)
            line_num = text[:match.start()].count("\n") + 1
            ctx = self._line_context(text, match.start())
            links.append({"target": target_rel or raw_ref, "alias": alias or "", "line": line_num, "context": ctx})
        return links

    def _find_backlinks(self, notes: dict, note_rel: str, basename_map) -> list[dict]:
        backlinks = []
        for rel, full in notes.items():
            if rel == note_rel:
                continue
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            cleaned = CODE_FENCE_RE.sub("", text)
            for match in WIKILINK_RE.finditer(cleaned):
                raw_ref = match.group(1).strip()
                resolved = self._resolve_link(raw_ref, Path(rel), basename_map)
                if resolved == note_rel:
                    line_num = text[:match.start()].count("\n") + 1
                    ctx = self._line_context(text, match.start())
                    backlinks.append({"source": rel, "line": line_num, "context": ctx})
        return backlinks

    def _resolve_link(self, ref: str, from_path: Path, basename_map: dict) -> Optional[str]:
        ref_stem = ref.split("#")[0].strip()
        if ref_stem in basename_map:
            return basename_map[ref_stem]
        same_folder = None
        other = None
        for stem, rel_id in basename_map.items():
            p = Path(rel_id)
            if p.stem == ref_stem or stem == ref_stem:
                if str(p.parent) == str(from_path.parent):
                    same_folder = rel_id
                elif other is None:
                    other = rel_id
        return same_folder or other

    def _find_note(self, note_path: str, notes: dict) -> Optional[str]:
        for k in notes:
            if k.lower() == note_path.lower():
                return k
        p = Path(note_path)
        for k in notes:
            if Path(k).name.lower() == p.name.lower():
                return k
        return None

    def _build_basename_map(self, notes: dict) -> dict[str, str]:
        m = {}
        for rel in notes:
            p = Path(rel)
            if p.stem not in m:
                m[p.stem] = rel
        return m

    def _parse_title(self, full: Path) -> str:
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return full.name
        fm = _parse_frontmatter_static(text)
        if fm and fm.get("title"):
            return str(fm["title"])
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                return stripped
        return full.name

    def _parse_tags(self, full: Path, rel_id: str) -> list[str]:
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return []
        tags = []
        fm = _parse_frontmatter_static(text)
        if isinstance(fm.get("tags"), list):
            tags = [str(t) for t in fm["tags"]]
        in_fence = False
        for line in text.splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for tag in re.findall(r"(?<!\w)#(\w+)", line):
                if tag not in tags:
                    tags.append(tag)
        return tags

    @staticmethod
    def _safe_mtime(full: Path) -> float:
        try:
            return full.stat().st_mtime
        except OSError:
            return 0.0

    @staticmethod
    def _line_context(text: str, pos: int) -> str:
        line_start = text.rfind("\n", 0, pos) + 1
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        return text[line_start:line_end].strip()[:120]

    def _save_cache(self, nodes: list[GraphNode], edges: list[GraphEdge]):
        data = {"built_at": time.time(), "nodes": [n.to_dict() for n in nodes], "edges": [e.to_dict() for e in edges]}
        try:
            self._cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _load_cache(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            nodes = [GraphNode(**n) for n in data.get("nodes", [])]
            edges = [GraphEdge(**e) for e in data.get("edges", [])]
            return nodes, edges
        except (OSError, json.JSONDecodeError, KeyError):
            # Cache file is corrupt. Remove it so _cache_valid returns False next call,
            # and rebuild instead of recursing into build() which calls _load_cache again.
            try:
                self._cache_file.unlink(missing_ok=True)
            except OSError:
                pass
            return self._build()


def _parse_frontmatter_static(text: str) -> dict:
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}
    try:
        import yaml
        parts = stripped.split("---", 2)
        if len(parts) >= 2:
            return yaml.safe_load(parts[1]) or {}
    except Exception:
        pass
    return {}
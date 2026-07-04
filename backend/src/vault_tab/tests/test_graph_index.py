"""GraphIndex tests - wikilink parsing, basename resolution, alias links, code fence exclusion."""

import json
import os
from pathlib import Path

import pytest

from src.vault_tab.core.graph_index import GraphIndex, GraphNode, GraphEdge, WIKILINK_RE

DEMO_VAULT = Path("/tmp/vibeflow/agent/demo-vault")


def _make_vault(tmp_path: Path) -> Path:
    """Helper: create a vault root with 90-system dir."""
    root = tmp_path / "vault"
    root.mkdir(parents=True)
    (root / "90-system").mkdir()
    return root


class TestGraphNode:
    def test_to_dict(self):
        node = GraphNode(id="a.md", title="A", folder="notes", tags=["tag1"])
        d = node.to_dict()
        assert d["id"] == "a.md"
        assert d["title"] == "A"
        assert d["tags"] == ["tag1"]
        assert d["in_degree"] == 0
        assert d["out_degree"] == 0


class TestGraphEdge:
    def test_to_dict(self):
        edge = GraphEdge(source="a.md", target="b.md")
        d = edge.to_dict()
        assert d["source"] == "a.md"
        assert d["target"] == "b.md"


class TestWikilinkRegex:
    def test_simple_wikilink(self):
        m = WIKILINK_RE.search("[[alpha]]")
        assert m.group(1) == "alpha"
        assert m.group(2) is None

    def test_wikilink_with_alias(self):
        m = WIKILINK_RE.search("[[alpha|Alpha Note]]")
        assert m.group(1) == "alpha"
        assert m.group(2) == "Alpha Note"

    def test_multi_wikilinks(self):
        text = "[[alpha]] and [[beta|B]]"
        matches = list(WIKILINK_RE.finditer(text))
        assert len(matches) == 2
        assert matches[0].group(1) == "alpha"
        assert matches[1].group(1) == "beta"
        assert matches[1].group(2) == "B"


class TestBuildGraphOnDemoVault:
    def test_build_returns_nodes(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        nodes, edges = idx.build()
        assert len(nodes) >= 5

    def test_build_returns_edges(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        nodes, edges = idx.build()
        assert len(edges) >= 1

    def test_nodes_have_titles(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        nodes, _ = idx.build()
        for n in nodes:
            assert n.title
            assert len(n.title) > 0

    def test_nodes_have_folders(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        nodes, _ = idx.build()
        folders = [n.folder for n in nodes if n.folder]
        assert len(folders) >= 1

    def test_edge_degree_counts(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        nodes, edges = idx.build()
        total_out = sum(n.out_degree for n in nodes)
        total_in = sum(n.in_degree for n in nodes)
        assert total_out == len(edges)
        assert total_in == len(edges)


class TestCodeFenceExclusion:
    def test_wikilinks_in_code_fence_ignored(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "04-notes").mkdir()
        (root / "04-notes" / "a.md").write_text(
            "---\n---\n\nSome link [[b]]\n\n```\n[[not-a-link]]\n```\n"
        )
        (root / "04-notes" / "b.md").write_text("---\n---\n\nLinked from a.\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        edges_a_to_b = [e for e in edges if e.source.endswith("a.md") and e.target.endswith("b.md")]
        assert len(edges_a_to_b) == 1

    def test_wikilinks_outside_code_fence_included(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "04-notes").mkdir()
        (root / "04-notes" / "a.md").write_text("---\n---\n\n[[b]]\n")
        (root / "04-notes" / "b.md").write_text("---\n---\n\n")
        idx = GraphIndex(root)
        _, edges = idx.build()
        assert any(e.source.endswith("a.md") for e in edges)


class TestBasenameResolution:
    def test_resolve_stem(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "04-notes").mkdir()
        (root / "04-notes" / "hello.md").write_text("Content\n")
        notes = {"04-notes/hello.md": root / "04-notes" / "hello.md"}
        idx = GraphIndex(root)
        bm = idx._build_basename_map(notes)
        resolved = idx._resolve_link("hello", Path("04-notes/other.md"), bm)
        assert resolved == "04-notes/hello.md"


class TestAliasLinks:
    def test_alias_link_parsed(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "04-notes").mkdir()
        (root / "04-notes" / "alpha.md").write_text("---\n---\n\nHello [[beta|Beta Note]]\n")
        (root / "04-notes" / "beta.md").write_text("---\n---\n\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        assert any(e.target.endswith("beta.md") for e in edges)


class TestCache:
    def test_cache_creates_file(self):
        cache = DEMO_VAULT / "90-system" / "graph-cache.json"
        cache.unlink(missing_ok=True)
        idx = GraphIndex(DEMO_VAULT)
        idx.build()
        assert cache.exists()

    def test_corrupt_cache_rebuilds(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        cache = root / "90-system" / "graph-cache.json"
        cache.write_text("NOT VALID JSON{{{")
        (root / "notes").mkdir()
        (root / "notes" / "a.md").write_text("---\n---\n\n[[b]]\n")
        (root / "notes" / "b.md").write_text("---\n---\n\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        assert len(nodes) >= 1


class TestFilter:
    def test_filter_by_folder(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "04-notes").mkdir()
        (root / "notes").mkdir()
        (root / "04-notes" / "one.md").write_text("---\ntitle: One\n---\n\n")
        (root / "notes" / "two.md").write_text("---\ntitle: Two\n---\n\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        fn, _ = idx.filter(nodes, edges, folder="04-notes")
        assert len(fn) == 1
        assert fn[0].id.endswith("one.md")

    def test_filter_by_tag(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "notes").mkdir()
        (root / "notes" / "tagged.md").write_text("---\ntitle: Tagged\ntags: [important]\n---\n\n")
        (root / "notes" / "untagged.md").write_text("---\ntitle: Untagged\n---\n\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        fn, _ = idx.filter(nodes, edges, tag="important")
        assert len(fn) == 1
        assert fn[0].id.endswith("tagged.md")

    def test_filter_by_query(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "notes").mkdir()
        (root / "notes" / "hello.md").write_text("---\ntitle: Hello World\n---\n\n")
        (root / "notes" / "goodbye.md").write_text("---\ntitle: Goodbye\n---\n\n")
        idx = GraphIndex(root)
        nodes, edges = idx.build()
        fn, _ = idx.filter(nodes, edges, q="hello")
        assert len(fn) == 1
        assert fn[0].id.endswith("hello.md")


class TestGetNoteLinks:
    def test_outgoing_links(self, tmp_path: Path):
        root = _make_vault(tmp_path)
        (root / "notes").mkdir()
        (root / "notes" / "a.md").write_text("---\n---\n\n[[b]]\n")
        (root / "notes" / "b.md").write_text("---\n---\n\n")
        idx = GraphIndex(root)
        links = idx.get_note_links("notes/a.md")
        assert len(links["outgoing"]) >= 1

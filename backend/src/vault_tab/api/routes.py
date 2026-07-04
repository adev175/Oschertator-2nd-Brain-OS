"""API routes for /api/vault/*."""

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..core.graph_index import GraphIndex
from ..core.parser import (
    VaultState,
    list_documents,
    parse_daily_note,
    read_goal,
    read_metrics,
    toggle_checkbox,
)
from ..core.skills import SkillLoader
from ..core.vault import VaultWriter

router = APIRouter()


def _vault_root() -> Path:
    return Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/tmp/vibeflow/agent/demo-vault")).resolve()


def _daily_path(vr: Path) -> Path:
    today = time.strftime("%Y-%m-%d")
    return vr / "01-daily" / f"{today}.md"


def _runner():
    state = get_state()
    return state.get("runner")


def _store():
    state = get_state()
    return state.get("store")


@router.get("/health")
async def health():
    vr = _vault_root()
    return {
        "status": "ok" if vr.exists() else "vault_missing",
        "vault_path": str(vr),
        "vault_readable": vr.exists(),
        "runner": "alive",
    }


@router.get("/skills")
async def list_skills():
    loader = SkillLoader(_vault_root())
    return [s.to_dict() for s in loader.load_all()]


class JobCreate(BaseModel):
    skill_id: str
    input_params: str = ""


@router.post("/jobs")
async def create_job(body: JobCreate):
    runner = _runner()
    if not runner:
        raise HTTPException(503, "Runner not started")
    try:
        job = await runner.enqueue_job(body.skill_id, body.input_params)
        return job
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/jobs")
async def list_jobs(limit: int = Query(20, ge=1, le=100)):
    store = _store()
    if not store:
        raise HTTPException(503, "Store not available")
    return await store.list_jobs(limit=limit)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    store = _store()
    if not store:
        raise HTTPException(503, "Store not available")
    job = await store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    runner = _runner()
    if not runner:
        raise HTTPException(503, "Runner not started")
    ok = await runner.cancel_job(job_id)
    if not ok:
        raise HTTPException(400, "Job cannot be cancelled")
    return {"cancelled": True}


@router.get("/state")
async def get_vault_state():
    vr = _vault_root()
    daily = parse_daily_note(_daily_path(vr))
    docs = list_documents(vr)
    metrics = read_metrics(vr)
    goal = read_goal(vr)
    store = _store()
    summary = await store.queue_summary() if store else {"active": 0, "queued": 0}
    return {
        "schedule": daily.schedule,
        "directives": daily.directives,
        "documents": [{"path": str(p), "mtime": m} for p, m in docs],
        "focus": daily.focus.strip(),
        "metrics": metrics,
        "goal": goal,
        "queue": summary,
    }


@router.get("/file")
async def get_file(path: str):
    vr = _vault_root()
    target = (vr / path).resolve()
    if not str(target).startswith(str(vr)):
        raise HTTPException(403, "Path traversal blocked")
    if not target.exists():
        raise HTTPException(404, "File not found")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@router.get("/tree")
async def get_tree():
    return _build_tree(_vault_root())


def _build_tree(root: Path, current: Path | None = None) -> list[dict]:
    if current is None:
        current = root
    items = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except PermissionError:
        return []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            sub = _build_tree(root, entry)
            count = len(list(entry.rglob("*.md")))
            items.append({"name": entry.name, "type": "folder", "children": sub, "note_count": count})
        elif entry.suffix == ".md":
            items.append({"name": entry.name, "type": "file", "path": str(entry.relative_to(root))})
    return items


@router.get("/graph")
async def get_graph(
    folder: str = "",
    tag: str = "",
    q: str = "",
    limit: int = Query(400, ge=10, le=2000),
):
    idx = GraphIndex(_vault_root())
    nodes, edges = idx.build()
    fn, fe = idx.filter(nodes, edges, folder=folder, tag=tag, q=q, limit=limit)
    return {
        "nodes": [n.to_dict() for n in fn],
        "edges": [e.to_dict() for e in fe],
        "total_nodes": len(nodes),
        "shown": len(fn),
    }


@router.get("/notes/{note_path:path}/links")
async def get_note_links(note_path: str):
    idx = GraphIndex(_vault_root())
    return idx.get_note_links(note_path)


@router.get("/search")
async def search_vault(q: str = ""):
    if not q:
        return {"results": []}
    vr = _vault_root()
    results = []
    ql = q.lower()
    for md in vr.rglob("*.md"):
        title_match = ql in md.name.lower()
        body_match = False
        snippet = ""
        if not title_match:
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
                idx_pos = text.lower().find(ql)
                if idx_pos >= 0:
                    body_match = True
                    start = max(0, idx_pos - 50)
                    end = min(len(text), idx_pos + 80)
                    snippet = text[start:end].replace("\n", " ")
                    if start > 0:
                        snippet = "..." + snippet
            except (OSError, UnicodeDecodeError):
                continue
        if title_match or body_match:
            results.append({
                "path": str(md.relative_to(vr)),
                "title": md.name,
                "title_match": title_match,
                "snippet": snippet,
            })
    results.sort(key=lambda r: (not r["title_match"], r["title"]))
    return {"results": results[:50]}


class FileCreate(BaseModel):
    path: str
    template: str = ""


@router.post("/files")
async def create_file(body: FileCreate):
    writer = VaultWriter(_vault_root())
    writer.write(body.path, body.template, mode="create")
    return {"created": body.path}


class FileRename(BaseModel):
    path: str
    new_path: str


@router.patch("/files")
async def rename_file(body: FileRename):
    writer = VaultWriter(_vault_root())
    count = writer.dry_run_rename(body.path, body.new_path)
    writer.rename_and_rewrite_links(body.path, body.new_path)
    return {"renamed": True, "links_updated": count}


class FileArchive(BaseModel):
    path: str


@router.post("/files/archive")
async def archive_file(body: FileArchive):
    writer = VaultWriter(_vault_root())
    basename = Path(body.path).name
    writer.move(body.path, f"99-archive/{basename}")
    return {"archived": body.path}


class DirectiveToggle(BaseModel):
    task: str
    done: bool = False


@router.post("/directives/toggle")
async def toggle_directive(body: DirectiveToggle):
    if not body.task:
        raise HTTPException(400, "task required")
    daily = _daily_path(_vault_root())
    return toggle_checkbox(daily, body.task, body.done)


# -- State management --
_state: dict[str, Any] = {}
_state_lock = None


def get_state() -> dict[str, Any]:
    return _state


def set_state(key: str, value: Any) -> None:
    _state[key] = value


def clear_state() -> None:
    _state.clear()

"""Async job runner - picks queued jobs, builds prompts, calls LLM, writes vault."""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from .llm import LLMClient
from .skills import Skill, SkillLoader
from .vault import VaultMode, VaultWriter, VaultWriteError

logger = logging.getLogger(__name__)


class SQLiteJobStore:
    """Async-safe SQLite job store for the runner loop."""

    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve()
        self.db = None

    async def connect(self):
        import aiosqlite

        self.db = await aiosqlite.connect(str(self.db_path))
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self._init_schema()

    async def _init_schema(self):
        if not self.db:
            raise RuntimeError("Not connected")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                input_params TEXT,
                output_path TEXT,
                error TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0
            )
        """)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def insert(self, job: dict):
        if not self.db:
            raise RuntimeError("Not connected")
        await self.db.execute(
            """INSERT INTO jobs
            (id, skill_id, status, created_at, started_at, finished_at,
             input_params, output_path, error, tokens_in, tokens_out)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job["id"],
                job["skill_id"],
                job["status"],
                job["created_at"],
                job.get("started_at"),
                job.get("finished_at"),
                job.get("input_params"),
                job.get("output_path"),
                job.get("error"),
                job.get("tokens_in", 0),
                job.get("tokens_out", 0),
            ),
        )
        await self.db.commit()

    async def get_queued(self) -> dict | None:
        if not self.db:
            return None
        row = await self.db.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1", ("queued",)
        )
        result = await row.fetchone()
        if result:
            values = list(result)
            job = dict(zip(
                ["id", "skill_id", "status", "created_at", "started_at", "finished_at",
                 "input_params", "output_path", "error", "tokens_in", "tokens_out"],
                values,
            ))
            await self.db.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (_now_iso(), job["id"]),
            )
            await self.db.commit()
            job["status"] = "running"
            job["started_at"] = _now_iso()
            return job
        return None

    async def update(self, job_id: str, **kw: Any) -> None:
        if not self.db:
            return
        if not kw:
            return
        fields = ", ".join(f"{k} = ?" for k in kw)
        await self.db.execute(f"UPDATE jobs SET {fields} WHERE id = ?", list(kw.values()) + [job_id])
        await self.db.commit()

    async def get(self, job_id: str) -> dict | None:
        if not self.db:
            return None
        row = await self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        result = await row.fetchone()
        if not result:
            return None
        return dict(zip(
            ["id", "skill_id", "status", "created_at", "started_at", "finished_at",
             "input_params", "output_path", "error", "tokens_in", "tokens_out"],
            list(result),
        ))

    async def list_jobs(self, limit: int = 50, status: str | None = None) -> list[dict]:
        if not self.db:
            return []
        keys = [
            "id", "skill_id", "status", "created_at", "started_at", "finished_at",
            "input_params", "output_path", "error", "tokens_in", "tokens_out",
        ]
        if status:
            rows = await self.db.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)
            )
        else:
            rows = await self.db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        results = await rows.fetchall()
        return [dict(zip(keys, list(r))) for r in results]

    async def queue_summary(self) -> dict:
        if not self.db:
            return {"active": 0, "queued": 0}
        r1 = await self.db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('running', 'reserved')")
        active = (await r1.fetchone())[0]
        r2 = await self.db.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued'")
        queued = (await r2.fetchone())[0]
        return {"active": active, "queued": queued}


class JobRunner:
    def __init__(
        self,
        store: SQLiteJobStore,
        vault_writer: VaultWriter,
        skill_loader: SkillLoader,
        llm_client: LLMClient,
        job_timeout_s: int = 300,
    ):
        self.store = store
        self.vault_writer = vault_writer
        self.skill_loader = skill_loader
        self.llm_client = llm_client
        self.job_timeout_s = job_timeout_s
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: list[Any] = []
        self._skills_cache: list[Skill] | None = None

    def register_callback(self, cb: Any) -> None:
        self._callbacks.append(cb)

    def _notify(self, event: str, data: dict) -> None:
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(event, data))
                else:
                    cb(event, data)
            except Exception as e:
                logger.error("Callback error: %s", e)

    async def start(self, poll_interval_s: int = 2) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop(poll_interval_s))
        logger.info("Runner started (poll=%ss)", poll_interval_s)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Runner stopped")

    async def _loop(self, poll_s: int) -> None:
        while self._running:
            try:
                await self._process_one()
            except Exception as e:
                logger.exception("Runner loop error")
            await asyncio.sleep(poll_s)

    async def _process_one(self) -> None:
        job = await self.store.get_queued()
        if not job:
            return
        job_id = job["id"]
        self._notify("job_update", {"id": job_id, "status": "running"})

        skill = self._find_skill(job["skill_id"])
        if not skill:
            await self.store.update(job_id, status="error", finished_at=_now_iso(), error="Skill not found")
            self._notify("job_update", {"id": job_id, "status": "error", "error": "Skill not found"})
            return

        try:
            ctx_parts = self.skill_loader.resolve_context_files(skill)
            prompt = skill.build_prompt(ctx_parts, job.get("input_params") or "")
            resp = await asyncio.wait_for(
                self.llm_client.complete("", prompt),
                timeout=self.job_timeout_s,
            )
            out_path = self._resolve_output_path(skill)
            mode: VaultMode = skill.output_mode if skill.output_mode in ("create", "append", "overwrite") else "create"
            self.vault_writer.write(out_path, resp.text, mode=mode, skill=skill.id, job_id=job_id)
            await self.store.update(
                job_id,
                status="done",
                finished_at=_now_iso(),
                output_path=out_path,
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
            )
            self._notify("job_update", {"id": job_id, "status": "done", "output_path": out_path})
        except asyncio.TimeoutError:
            await self.store.update(job_id, status="error", finished_at=_now_iso(), error="timeout")
            self._notify("job_update", {"id": job_id, "status": "error", "error": "timeout"})
        except VaultWriteError as e:
            await self.store.update(job_id, status="error", finished_at=_now_iso(), error=str(e))
            self._notify("job_update", {"id": job_id, "status": "error", "error": str(e)})
        except Exception as e:
            await self.store.update(job_id, status="error", finished_at=_now_iso(), error=str(e))
            self._notify("job_update", {"id": job_id, "status": "error", "error": str(e)})

    def _resolve_output_path(self, skill: Skill) -> str:
        path = skill.output_path
        path = path.replace("{{date}}", time.strftime("%Y-%m-%d"))
        path = path.replace("{{time}}", time.strftime("%H%M"))
        return path

    def _find_skill(self, skill_id: str) -> Skill | None:
        skills = self.skill_loader.load_all()
        for s in skills:
            if s.id == skill_id:
                return s
        return None

    async def enqueue_job(self, skill_id: str, input_params: str = "") -> dict:
        skill = self._find_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        now = _now_iso()
        job = {
            "id": str(uuid.uuid4()),
            "skill_id": skill_id,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "input_params": input_params,
            "output_path": None,
            "error": None,
            "tokens_in": 0,
            "tokens_out": 0,
        }
        await self.store.insert(job)
        self._notify("job_update", {"id": job["id"], "status": "queued"})
        return job

    async def cancel_job(self, job_id: str) -> bool:
        job = await self.store.get(job_id)
        if not job or job["status"] != "queued":
            return False
        await self.store.update(job_id, status="cancelled", finished_at=_now_iso())
        self._notify("job_update", {"id": job_id, "status": "cancelled"})
        return True

    async def recover_interrupted(self) -> None:
        running = await self.store.list_jobs(status="running", limit=100)
        for job in running:
            await self.store.update(job["id"], status="error", finished_at=_now_iso(), error="interrupted")
            self._notify("job_update", {"id": job["id"], "status": "error", "error": "interrupted"})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime())

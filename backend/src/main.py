"""Oschertator - 2nd Brain OS FastAPI application."""

import logging
import os
import sys
from pathlib import Path

# Add src to path so vault_tab can be imported as a package
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vault_tab.api.routes import get_state, router as vault_router, set_state
from vault_tab.api.oschertator import router as oschertator_router
from vault_tab.core.llm import create_llm_client
from vault_tab.core.runner import JobRunner, SQLiteJobStore
from vault_tab.core.skills import SkillLoader
from vault_tab.core.vault import VaultWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def get_app() -> FastAPI:
    app = FastAPI(title="Oschertator", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(vault_router, prefix="/api/vault", tags=["vault"])
    app.include_router(oschertator_router, tags=["oschertator"])

    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    @app.on_event("startup")
    async def startup():
        vault_root = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/tmp/vibeflow/agent/demo-vault")).resolve()
        db_path = vault_root / "90-system" / "jobs.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        llm_config = {
            "protocol": os.environ.get("LLM_PROTOCOL", "openai-compatible"),
            "base_url": os.environ.get("LLM_ENDPOINT_URL", "http://localhost:8000/v1"),
            "model": os.environ.get("LLM_MODEL", "gpt-4o"),
        }
        runner_config = {
            "poll_interval_s": int(os.environ.get("RUNNER_POLL_INTERVAL", "2")),
            "job_timeout_s": int(os.environ.get("RUNNER_JOB_TIMEOUT", "300")),
        }

        writer = VaultWriter(vault_root)
        loader = SkillLoader(vault_root)
        llm_client = create_llm_client(llm_config)

        store = SQLiteJobStore(db_path)
        await store.connect()

        runner = JobRunner(store, writer, loader, llm_client, job_timeout_s=runner_config["job_timeout_s"])
        await runner.recover_interrupted()
        await runner.start(poll_interval_s=runner_config["poll_interval_s"])

        set_state("vault_root", vault_root)
        set_state("store", store)
        set_state("runner", runner)
        logger.info("Oschertator started (vault=%s)", vault_root)

    @app.on_event("shutdown")
    async def shutdown():
        runner = get_state().get("runner")
        store = get_state().get("store")
        if runner:
            await runner.stop()
        if store:
            await store.close()

    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

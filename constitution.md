# Constitution — VAULT Agentic OS Tab

**Version:** 1.0 | **Ratified:** 2026-07-03 | **Owner:** Anh (solo dev)

> Read-only input for every phase and every coding agent. Conflicts must be resolved
> explicitly via the Amendment Log — never silently.

## Article I — Development Methodology

Milestone-driven (M0 → M3). Each milestone must run end-to-end and pass its acceptance
checklist before the next starts. No big-bang implementation.

## Article II — Architecture Non-Negotiables

1. **The UI never calls the LLM directly.** UI only enqueues jobs and renders state.
2. **The Obsidian vault is the single source of truth.** All agent output is written as
   markdown into the vault. No parallel database of content (SQLite holds job metadata only).
3. **Vault is never corrupted:** every write goes through one `VaultWriter` module that
   enforces path containment (inside vault root), UTF-8, frontmatter, and collision-safe
   filenames. No other code path writes to the vault.
4. **Additive only:** the feature is a new tab. Existing tabs, routes, and build config of
   the host dashboard must not be refactored or broken.

## Article III — Technology Constraints

- Backend: Python (FastAPI style), `uv` for deps. Frontend: follow the host repo's existing
  framework and conventions — do not introduce a second UI framework.
- No heavy graph/3D libraries (three.js, cytoscape) for the graph view — custom canvas
  force simulation or d3-force only. Bundle impact of the tab ≤ 200 KB gz excluding host deps.
- LLM access only through the `LLMClient` adapter interface. Endpoint/model/key come from
  env/config, never hardcoded.

## Article IV — Testing & Quality Bar

- Unit tests required for: vault parser, path-containment guard, skill loader, graph index
  builder, runner state machine. Coverage target on new backend code: 80%.
- Every M-milestone acceptance checklist doubles as manual E2E script.

## Article V — Observability

- Structured logs (JSON) on the runner: job_id, skill_id, status transitions, duration, tokens.
- `/api/vault/health` returns runner liveness + vault path readability.

## Article VI — Versioning & Breaking Changes

API mounted under `/api/vault/*`. Schema changes to skill YAML must stay
backward-compatible within v1 (new optional keys only).

## Article VII — Security & Data Handling

- No secrets in code, prompts, or vault files. API key via env var only.
- All file-serving endpoints must reject path traversal (resolve + prefix check against
  vault root). Vault content never leaves the local machine except to the configured LLM
  endpoint.
- The runner may create/append files but may **never delete** vault files in v1
  (`vault-clean` skill moves to `99-archive/`, doesn't delete).

## Article VIII — AI Agent Authorization Baseline

Claude Code operates at "pipeline" level: implement per tasks.md, run tests, commit.
Not authorized to: change host app dependencies' major versions, touch CI/CD of the host
repo, delete user data, or run destructive git commands (force-push, reset --hard on shared
branches).

## Article IX — Visual Fidelity (project-specific)

The tab must reproduce the VAULT HUD reference aesthetic (see spec §6 design tokens):
near-black background, phosphor-green accent, monospace micro-labels, thin 1px panel rules,
sparklines, perspective grid floor. Any deviation needs a note in the PR description.

## Amendment Log

| Date | Article changed | Reason | Approved by |
|------|------------------|--------|-------------|
| | | | |

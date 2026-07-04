# CLAUDE.md — VAULT Agentic OS Tab (feature workspace)

> For Claude Code agents. Read order: `constitution.md` → `01-spec/spec.md` (incl. addendum)
> → `02-plan/plan.md` → `03-tasks/tasks.md`. Then execute tasks strictly in order.

## Project Overview

**Type:** Feature add-on (new tab) inside an existing dashboard app
**Stack:** Backend Python/FastAPI-style + `uv`; frontend = **whatever the host repo uses — detect it, follow it**
**Purpose:** Mission-control tab: one-click LLM skills over an Obsidian vault, with an
Obsidian-parity graph view, backlinks, md preview, file explorer. Visuals per spec §A1.
**Status:** Pre-M0

## First session bootstrap (do once)

1. Inspect host repo: framework, router/tab registration, md renderer, API client pattern,
   theming system, test runner. Write findings into spec §1 CONFIG and commit.
2. Confirm env vars exist: `LLM_API_KEY`, vault path config. Never print their values.
3. Run host app's existing test suite once — record baseline so regressions are detectable.
4. Create fixture mini-vault per `04-test/test-plan.md` §2 before writing parser code.

## Structure to create (adapt names to host conventions)

```
<backend>/vault_tab/
├── api/routes.py          # /api/vault/* per spec §4 + addendum A2–A3
├── core/vault.py          # VaultWriter — THE ONLY module that writes to the vault
├── core/parser.py         # daily-note sections, frontmatter, checkbox toggle
├── core/graph_index.py    # wikilink graph, cache, LOD
├── core/skills.py         # YAML skills, prompt templating
├── core/runner.py         # async job worker
├── core/llm.py            # LLMClient ABC + OpenAICompatClient
└── tests/
<frontend>/vault-tab/
├── VaultTab.<ext>         # layout: TopBar / LeftCol / Center / RightCol
├── components/            # Panel, MicroLabel, Sparkline, StatusPill, Toast...
├── graph/                 # force sim + canvas renderer + interactions
├── overlay/               # md preview, backlinks panel, local graph
└── tokens.css             # spec §A1 variables, scoped to the tab
```

## Commands

```bash
# Backend
uv sync
uv run pytest <backend>/vault_tab/tests -v
uv run pytest -m "not live"           # default: LLM mocked
uv run uvicorn <host_app>:app --reload

# Frontend — use host repo's existing scripts (detect: pnpm/npm/yarn dev|test|lint)

# Perf fixtures
uv run python tests/gen_vault.py --notes 1000 --out /tmp/perfvault
```

## Hard rules (from constitution — violations are bugs)

- ❌ UI never calls the LLM endpoint; only backend `LLMClient` does.
- ❌ No vault writes outside `VaultWriter`; no deletes ever — archive-move only.
- ❌ No path escapes: every file param resolved + prefix-checked against vault root.
- ❌ No three.js/cytoscape/heavy chart libs for the graph; ≤ 200 KB gz added to bundle.
- ❌ Do not refactor, restyle, or upgrade deps of existing host tabs.
- ❌ No secrets in code/prompts/logs; key via env only.
- ✅ Milestone gates: complete every ✓-gate in `03-tasks/tasks.md` before the next milestone.
- ✅ Tolerant reads: malformed md/frontmatter must degrade to empty state, never crash.
- ✅ JP text everywhere in tests: filenames, wikilinks, content are often Japanese.

## Coding conventions

- Python: 3.12+, type hints everywhere, ruff format/lint, async route handlers,
  Pydantic schemas for all responses, Google-style docstrings only where non-obvious.
- Code style: compact, no unnecessary comments (owner preference).
- Frontend: mirror host patterns exactly (state mgmt, naming, CSS approach). Design tokens
  scoped under the tab root class so nothing leaks into other tabs.
- Git: Conventional Commits, branch `feature/vault-tab-m{N}-{slug}`, one commit per task ID
  where practical (`feat(vault-tab): 2.4 canvas force sim`).

## Definition of Done per task

Code + tests green + relevant checklist item verified + committed. If a task reveals a
spec gap, write the decision into `02-plan/plan.md` §2 as a new D-row instead of improvising
silently.

## Current Sprint Context

**Milestone:** M0 | **Next gate:** task 0.6 (POST job → file in vault → done)
**Blocked:** — | Update this section at every milestone gate.

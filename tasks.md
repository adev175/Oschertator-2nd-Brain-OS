# Tasks (WBS-lite) — VAULT Agentic OS Tab

**Owner:** Claude Code (solo pipeline) | Est. hours = agent-assisted wall-clock
Execute strictly in order inside each milestone. `✓ gate` = must pass before moving on.

## M0 — Pipeline proof (est. 4 h)

| ID | Task | Deliverable | Est | Status |
|----|------|-------------|-----|--------|
| 0.1 | Inspect host repo; fill CONFIG in spec §1; record detected stack in `02-plan/plan.md` §1 note | CONFIG committed | 0.5 | ⬜ |
| 0.2 | Backend module skeleton (`api/`, `core/`), mount `/api/vault`, `/health` | Health returns vault readable | 0.5 | ⬜ |
| 0.3 | `VaultWriter` + path-containment guard + unit tests (traversal, collision suffix, frontmatter, JP filenames) | tests green | 1 | ⬜ |
| 0.4 | Skill YAML loader + prompt templating + `plan-today.yaml` | `/skills` lists 1 skill | 0.5 | ⬜ |
| 0.5 | Jobs table + `/jobs` POST/GET + runner loop + `OpenAICompatClient` | — | 1 | ⬜ |
| 0.6 | ✓ gate: POST job → md file appears in vault → job `done`; kill endpoint mid-job → `error` | manual E2E per spec §7 | 0.5 | ⬜ |

## M1 — Full tab UI, VAULT aesthetic (est. 8 h)

| ID | Task | Deliverable | Est | Status |
|----|------|-------------|-----|--------|
| 1.1 | Register VAULT tab in host nav (follow host convention) | tab renders empty shell | 0.5 | ⬜ |
| 1.2 | Design tokens (spec §A1) as scoped CSS vars + base panel/label/pill components | storybook-less demo panel | 1 | ⬜ |
| 1.3 | Backend: daily-note parser (Schedule/Directives/Focus), `/state` aggregate, `/file` with traversal guard, `metrics.json` + `goal.yaml` readers | `/state` returns full payload | 1.5 | ⬜ |
| 1.4 | TopBar: clock, status pills wired to `/state.queue` + `/health` | — | 0.5 | ⬜ |
| 1.5 | LeftCol: SYSTEM VITALS (sparkline inline SVG), DIRECTIVES (read-only), DOCUMENTS | — | 1.5 | ⬜ |
| 1.6 | RightCol: COMMAND DECK (skills grid, spinner per running job, toast), SCHEDULE (now-highlight), JOB LOG | — | 1.5 | ⬜ |
| 1.7 | Center: PRIMARY DIRECTIVE counter + ETA; placeholder grid-floor (graph comes in M2) | — | 0.5 | ⬜ |
| 1.8 | Markdown preview overlay: md→HTML, wikilinks navigate in-overlay, history back/fwd, frontmatter chips | — | 1 | ⬜ |
| 1.9 | Write 4 starter skill YAMLs (`plan-today`, `inbox-brief`, `wk-review`, `vault-clean`→archive-move) | skills usable | 0.5 | ⬜ |
| 1.10 | ✓ gate: spec §7 items 1–2, 4–5; empty-state check with fresh vault | — | 0.5 | ⬜ |

## M2 — Graph view + backlinks (est. 8 h)

| ID | Task | Deliverable | Est | Status |
|----|------|-------------|-----|--------|
| 2.1 | `graph_index.py`: wikilink regex (skip code fences), basename resolution (D6), nodes/edges, degree | unit tests incl. alias links, JP titles | 1.5 | ⬜ |
| 2.2 | Cache to `90-system/graph-cache.json`, mtime invalidation (D11), `/graph` with folder/tag/q/limit + LOD ranking | 964-note vault < 3 s cold | 1 | ⬜ |
| 2.3 | `/notes/{path}/links`: outgoing, backlinks, on-demand unlinked mentions with context lines (D7) | matches Obsidian spot-check | 1 | ⬜ |
| 2.4 | Canvas force sim: repulsion+spring+gravity, settle-freeze, reheat on change | 60 fps @ 400 nodes | 2 | ⬜ |
| 2.5 | Graph interactions: hover highlight/dim, tooltip, click→overlay, wheel zoom, pan, folder color groups, filter controls, "N/total shown" | behavior table §A2.2 all pass | 1.5 | ⬜ |
| 2.6 | BACKLINKS panel in overlay (linked/unlinked sections) + LOCAL GRAPH 1-hop footer | — | 0.5 | ⬜ |
| 2.7 | Job-pulse glow tied to runner state | — | 0.25 | ⬜ |
| 2.8 | ✓ gate: spec §A5 items 1–2, 4–5 | — | 0.25 | ⬜ |

## M3 — Explorer, search, live polish (est. 6 h)

| ID | Task | Deliverable | Est | Status |
|----|------|-------------|-----|--------|
| 3.1 | `/tree` lazy folder tree + EXPLORER panel | — | 1 | ⬜ |
| 3.2 | New note / rename / move / archive endpoints via VaultWriter; rename does vault-wide wikilink rewrite with dry-run count confirm (D8) | grep-verified rewrite | 1.5 | ⬜ |
| 3.3 | Global search `/search` (filename + fulltext) + dropdown, `graph:` prefix pipes to graph filter | — | 1 | ⬜ |
| 3.4 | WebSocket `/ws` push (job_update, state_update); UI falls back to polling | — | 1 | ⬜ |
| 3.5 | Directive checkbox toggle (writes back to daily note via parser) | — | 0.5 | ⬜ |
| 3.6 | Job cancel (queued only); boot-time `running`→`error: interrupted` sweep | — | 0.5 | ⬜ |
| 3.7 | ✓ gate: full spec §7 + §A5 checklist; update CLAUDE.md Current Sprint | — | 0.5 | ⬜ |

**Total ~26 h · +20% buffer ≈ 31 h** (≈ 4 weekend sessions)

## Out of order = bug
If a task needs something from a later task, stop and flag it — do not reorder silently.

# SPEC — "VAULT" Agentic OS Tab (add-on to existing dashboard)

## 0. Instructions for Claude Code (read first)

1. **Inspect the existing repo before writing any code.** Detect: frontend framework, routing/tab mechanism, backend framework, how existing tabs fetch data. Reuse existing conventions (component style, state management, API client, theming).
2. Fill the CONFIG section below from the repo + environment. If a value cannot be inferred, ask once, then proceed.
3. Implement in the milestone order (M0 → M2). Each milestone must run end-to-end before starting the next.
4. Do not refactor unrelated parts of the app.

## 1. CONFIG (fill in / confirm)

```yaml
vault_path: "<ABSOLUTE_PATH_TO_OBSIDIAN_VAULT>"
llm_endpoint:
  base_url: "<LLM_ENDPOINT_URL>"          # e.g. http://localhost:8000/v1
  protocol: "openai-compatible"           # openai-compatible | anthropic | custom
  model: "<MODEL_NAME>"
  api_key_env: "LLM_API_KEY"
dashboard:
  frontend: "<detect from repo>"           # e.g. React + Vite
  backend: "<detect from repo>"            # e.g. FastAPI
  tab_registration: "<detect from repo>"   # how a new tab/page is added
runner:
  poll_interval_s: 2
  max_concurrent_jobs: 1
  job_timeout_s: 300
```

## 2. Goal

Add one new tab **"VAULT"** to the existing dashboard: a mission-control view where predefined **skills** (one-click prompts) are dispatched to an **LLM runner** that reads/writes the Obsidian vault. The tab displays live state parsed from vault files. The UI never calls the LLM directly — it only enqueues jobs and renders vault/queue state.

```
UI (VAULT tab) ──HTTP──▶ Backend API ──▶ Job queue (SQLite)
                                              │
                                        Runner (async worker)
                                              │  calls LLM endpoint (adapter)
                                              ▼
                                     Obsidian vault (read/write .md)
                                              │
UI ◀──poll/WS── Backend API ◀── parse vault + queue state
```

## 3. Data contracts

### 3.1 Skill definition — `vault/90-system/skills/*.yaml`

```yaml
id: inbox-brief                # slug, unique
label: "INBOX BRIEF"           # button text
description: "Summarize today's inbox notes into a brief"
prompt_template: |
  You are an assistant operating on an Obsidian vault.
  Today is {{date}}.
  Task: read the notes listed below and produce a concise brief.
  {{context}}
context_files:                 # globs relative to vault root, injected as {{context}}
  - "01-daily/{{date}}.md"
output:
  path: "04-notes/brief-{{date}}-{{time}}.md"   # where runner writes the result
  mode: create                 # create | append | overwrite
tags: [daily]
```

### 3.2 Job record — SQLite table `jobs`

| column | type | notes |
|---|---|---|
| id | TEXT (uuid) | PK |
| skill_id | TEXT | FK to skill yaml id |
| status | TEXT | queued / running / done / error / cancelled |
| created_at / started_at / finished_at | TEXT ISO8601 | |
| input_params | TEXT JSON | optional user text appended to prompt |
| output_path | TEXT | vault-relative path of result |
| error | TEXT | traceback / message on failure |
| tokens_in / tokens_out | INTEGER | if endpoint returns usage |

### 3.3 Vault file conventions the tab reads

| Panel | Source | Parse rule |
|---|---|---|
| Schedule | `01-daily/{{date}}.md` section `## Schedule` | lines `- HH:MM task`; highlight the row whose time window contains now |
| Directives (todo) | same file, section `## Directives` | `- [ ]` / `- [x]` checkboxes, top 5 unchecked |
| Documents | `04-notes/` | newest 5 files by mtime → name + relative age |
| Focus note | same daily file, section `## Focus` | render as paragraph |
| Metrics | `90-system/metrics.json` | see 3.4 |
| Primary directive | `90-system/goal.yaml` | `{label, current, target, weekly_delta}` |

If a section/file is missing, render the panel in an empty "—" state; never crash.

### 3.4 Metrics — `vault/90-system/metrics.json`

```json
{
  "updated_at": "2026-07-03T09:00:00+09:00",
  "series": [
    {"id": "yt_subs", "label": "YT SUBSCRIBERS", "value": 135000,
     "delta_label": "+2.0K /wk", "history": [/* last 30 numbers */]}
  ]
}
```

Written by a `metrics-pull` skill (or any external script). UI renders value + delta + sparkline per series.

## 4. Backend API (mount under `/api/vault`)

| Method | Route | Behavior |
|---|---|---|
| GET | `/skills` | list parsed skill yamls |
| POST | `/jobs` | body `{skill_id, input_params?}` → enqueue, return job |
| GET | `/jobs?limit=20` | recent jobs, newest first |
| GET | `/jobs/{id}` | job detail incl. error |
| POST | `/jobs/{id}/cancel` | only if queued |
| GET | `/state` | aggregated: schedule, directives, documents, focus, metrics, goal, queue summary `{active, queued}` |
| GET | `/file?path=` | raw markdown of a vault file (path must resolve inside vault — reject traversal) |
| WS | `/ws` | push `job_update` and `state_update` events; fallback: UI polls `/state` every 5 s |

### Runner

- Async worker in the same backend process (start with app lifespan). Loop: pick oldest `queued` job → `running` → build prompt (inject `{{date}}`, `{{time}}`, `{{context}}` from `context_files`, append `input_params`) → call LLM via **adapter interface** → write output file per `output` spec → `done`. Any exception → `error` with message.
- **Adapter interface** `LLMClient.complete(system, user) -> {text, tokens_in, tokens_out}` with one implementation per protocol (openai-compatible first). Endpoint/model/key from CONFIG.
- Enforce `job_timeout_s`; on timeout mark `error`.
- Vault writes: create parent dirs; `create` mode adds `-1`, `-2` suffix on collision; always write UTF-8 with YAML frontmatter `{skill, job_id, created}`.

## 5. UI — VAULT tab layout

Dark theme, monospace accents, green-on-black accent color (follow existing theme system if present). Three-column grid, responsive to two columns < 1280 px.

**Left column**
1. `SYSTEM VITALS` — metric cards: label, big value, delta, sparkline (tiny inline SVG, no chart lib needed).
2. `DIRECTIVES` — checkbox list (read-only display; toggling = M2).
3. `DOCUMENTS` — recent output files; click → modal rendering markdown via `/file`.

**Center column**
4. Hero visual: animated particle/network canvas (single `<canvas>` + requestAnimationFrame, ~300 points, no three.js dependency). Pulse animation while any job is `running`.
5. `PRIMARY DIRECTIVE` — big counter from `goal.yaml`: current, target, weekly delta, naive ETA (`(target-current)/weekly_delta` weeks).

**Right column**
6. Header: clock (client-side, 1 s tick) + status pills `CORE idle/busy`, `RUNNER alive/dead` (from `/state.queue`).
7. `COMMAND DECK` — grid of skill buttons from `/skills`. Click → POST `/jobs` → button shows spinner while its job is queued/running; toast on done/error. Optional text input appended as `input_params`.
8. `SCHEDULE` — today's timeline, current row highlighted.
9. `JOB LOG` — last 10 jobs: skill, status, duration; click error row → error detail.

## 6. Milestones

**M0 — pipeline proof.** Backend: skills loader, jobs table, `/skills` `/jobs` `/state`, runner with openai-adapter. One skill (`plan-today`). Verify: POST job → file appears in vault → job `done`.

**M1 — full tab UI.** All panels above with 5 s polling; 4 starter skills: `plan-today`, `inbox-brief`, `wk-review`, `vault-clean` (write these yamls with sensible prompts). Empty states everywhere.

**M2 — polish.** WebSocket push, directive checkbox toggle (writes back to daily note), particle canvas job-pulse, job cancel, metrics history sparkline.

## 7. Acceptance criteria

- [ ] New tab appears in existing nav without breaking existing tabs.
- [ ] Clicking any skill creates a job; result file appears in vault within timeout; UI reflects status without reload.
- [ ] Killing the LLM endpoint mid-job → job `error`, UI shows message, app stays healthy.
- [ ] `/file` rejects paths outside the vault (`../` traversal test).
- [ ] Missing daily note / metrics.json → panels render empty state, no console errors.
- [ ] Backend restart with jobs `running` → those jobs marked `error: interrupted` on boot.

## 8. Non-goals (v1)

Voice input, TTS, live news ticker, 3D graphics library, multi-user auth, editing skills from the UI, direct Claude Code CLI orchestration (LLM endpoint only).

---

# SPEC ADDENDUM v1.1 — Visual Fidelity + Obsidian Feature Parity

> This addendum extends the base spec. Where it conflicts with §5 (UI) of the base spec,
> the addendum wins. Non-goals list in §8 is amended: graph view is now IN scope (M2).

## A1. Design tokens (replicate the VAULT HUD reference image)

```css
:root {
  --vault-bg:        #060906;   /* near-black, slight green cast */
  --vault-panel:     #0a0f0a;
  --vault-accent:    #c8f04b;   /* phosphor green — values, sparklines, graph nodes */
  --vault-accent-dim:#7a9430;
  --vault-text:      #e8ece2;
  --vault-muted:     #6b7264;   /* micro-labels */
  --vault-rule:      #1c231c;   /* 1px panel borders */
  --vault-danger:    #f0654b;
  --vault-font-mono: "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace;
}
```

Rules:
- All micro-labels: uppercase, monospace, ~10px, letter-spacing 0.12em, color `--vault-muted`,
  prefixed with a 4px square accent dot (e.g. `▪ SYSTEM VITALS`).
- Panel headers: label left, thin rule extending right to panel edge.
- Big numerals (metric values, PRIMARY DIRECTIVE counter): condensed sans or mono,
  tabular-nums, accent-on-dark glow (`text-shadow: 0 0 24px rgba(200,240,75,.35)`).
- Perspective grid floor under the center graph: CSS/canvas gradient lines converging to
  horizon, opacity ≤ 0.15.
- Status pills top bar: `● CORE · IDLE   LINK · ONLINE   RUNNER · ALIVE` — dot green when
  healthy, red `--vault-danger` when not.
- Clock top-right: HH:MM large + :SS small raised, date underneath in muted.
- Scanline/vignette overlay optional, must be a single toggleable CSS class.

## A2. Center visual = REAL vault graph view (not decorative particles)

Replaces the decorative particle canvas. The glowing cloud is the actual Obsidian-style
graph of the vault.

### A2.1 Graph index (backend)

- Module `graph_index.py`: scan `**/*.md`, parse `[[wikilink]]` and `[[wikilink|alias]]`
  (regex, ignore code fences), resolve to note paths (Obsidian shortest-path rule: match by
  basename; if ambiguous prefer same folder, else first match).
- Output nodes `{id, title, folder, tags[], out_degree, in_degree, mtime}` and edges
  `{source, target}`. Also compute **unlinked mentions** lazily (per-note only, on demand —
  full-vault scan is too slow): plain-text occurrences of another note's basename that are
  not already links.
- Cache to `90-system/graph-cache.json`; rebuild if any md mtime > cache mtime (debounced
  watcher or on-request check). Target: ≤ 3 s cold build for 1,000 notes.
- API:
  - `GET /api/vault/graph?folder=&tag=&q=&limit=400` → filtered node/edge lists.
    Default limit 400 nodes ranked by degree (LOD for big vaults); response includes
    `total_nodes` so UI can show "400 / 964 shown".
  - `GET /api/vault/notes/{path}/links` → `{outgoing[], backlinks[], unlinked_mentions[]}`
    with a context snippet (the containing line) per mention — mirrors Obsidian's
    Linked mentions / Unlinked mentions split.

### A2.2 Graph rendering (frontend)

Single `<canvas>`, custom force simulation (or d3-force if already in host deps):
repulsion (Barnes-Hut or simple n² under 400 nodes), spring on edges, mild centering
gravity. Behaviors to replicate from Obsidian graph view:

| Behavior | Requirement |
|---|---|
| Node size | radius ∝ sqrt(in_degree+out_degree), clamp 2–10 px |
| Hover | highlight node + its edges/neighbors at full accent; dim rest to 25%; tooltip with note title |
| Click | open note in the Markdown preview overlay (A3) |
| Zoom / pan | wheel zoom to cursor, drag to pan; pinch on touch |
| Filters | search box (`q`), folder dropdown, tag dropdown → re-query `/graph` |
| Color groups | by top-level folder, from a fixed 6-color ramp around the accent hue |
| Job pulse | while any job is `running`, slow radial pulse of node glow (reuse existing hook) |
| Idle drift | very low-amplitude jitter so the cloud feels alive, pausable via the scanline toggle class |

Performance bar: 60 fps at 400 nodes on a mid laptop; simulation freezes (alpha → 0) after
settle, reheats on filter change or drag.

## A3. Obsidian feature parity panels

### A3.1 Markdown preview overlay
- Triggered from: graph node click, DOCUMENTS list, file explorer, backlink rows.
- Renders md → HTML (marked/markdown-it or host's existing renderer): headings, lists,
  checkboxes, code fences, tables, YAML frontmatter as a folded properties chip row.
- `[[wikilinks]]` render as accent links and navigate **inside the overlay** (client-side,
  fetch via `/file`), with back/forward history in the overlay header.
- Right side of overlay: **BACKLINKS** panel — two collapsible sections, `LINKED MENTIONS`
  and `UNLINKED MENTIONS`, each row = source note + context line, click navigates.
- Footer: LOCAL GRAPH mini-canvas — 1-hop neighborhood of the open note (reuse A2 renderer,
  ≤ 50 nodes, no filters).

### A3.2 File explorer (folder manage)
- Left column gains an `EXPLORER` panel above DOCUMENTS: collapsible folder tree of the
  vault (`GET /api/vault/tree`, lazy-load children per folder).
- Shows only folders + `.md` files; counts per folder; typed-subfolder prefixes
  (01-daily, 02-concepts, …) sorted naturally.
- v1 operations (each = confirm dialog → API → optimistic refresh):
  - New note in folder (`POST /api/vault/files` `{path, template?}`)
  - Rename note/folder (`PATCH /api/vault/files` `{path, new_path}`) — backend must also
    rewrite `[[wikilinks]]` pointing at the renamed note (Obsidian-style link update)
  - Move note via rename with different folder
  - **No delete** (Constitution Art. VII) — "Archive" action moves to `99-archive/`.
- All mutating endpoints go through `VaultWriter` with path-containment checks.

### A3.3 Search
- Top-bar global search input: `GET /api/vault/search?q=` — filename match + full-text
  (simple ripgrep-style scan or cached index), returns path + highlighted snippet.
- Results dropdown; Enter opens preview overlay; `graph:` prefix pipes the query into the
  graph filter instead.

## A4. Milestone amendments

| Milestone | Adds |
|---|---|
| M1 | Design tokens + all static panels restyled to A1; md preview overlay (A3.1 without local-graph footer) |
| M2 | Graph index + center graph view (A2), backlinks panel, local-graph footer |
| M3 (was M2 polish) | File explorer + rename-with-link-rewrite, global search, WebSocket push, directive toggle, job cancel |

## A5. Acceptance additions

- [ ] Graph renders the real vault: node count shown matches `/graph` response; hovering a
      hub note highlights exactly its neighbors.
- [ ] Clicking a node opens the note preview; its backlinks list matches Obsidian's for the
      same note (spot-check 3 notes).
- [ ] Renaming a note updates all `[[wikilinks]]` that pointed to it (verify with grep).
- [ ] 964-note vault: graph first paint < 4 s cold, < 1 s warm cache; steady 60 fps after settle.
- [ ] Unlinked mentions computed on-demand only (no full-vault scan on tab load).

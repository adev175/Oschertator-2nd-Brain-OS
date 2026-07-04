# Plan (SAD-lite) — VAULT Agentic OS Tab

**Version:** 1.1 | **Date:** 2026-07-03 | Respects `constitution.md`; implements `01-spec/spec.md` (incl. addendum v1.1)

## 1. Component view

```
┌─ Host dashboard (existing) ─────────────────────────────────────────┐
│  Nav/tab system ──▶ [VAULT tab]                                     │
│                     ├─ TopBar (clock, status pills, global search)  │
│                     ├─ LeftCol (Vitals, Explorer, Directives, Docs) │
│                     ├─ Center (GraphView canvas, PrimaryDirective)  │
│                     ├─ RightCol (CommandDeck, Schedule, JobLog)     │
│                     └─ PreviewOverlay (md render, Backlinks,        │
│                        LocalGraph)                                  │
└──────────────────────────────────────────────────────────────────────┘
        │ REST /api/vault/*  +  WS /api/vault/ws
┌─ Backend (new module, mounted into existing app if same-origin;     ┐
│  else standalone FastAPI service behind existing proxy)             │
│  api/            routes: skills, jobs, state, graph, tree, files,   │
│                  search, file, notes-links, health, ws              │
│  core/vault.py   VaultWriter (ONLY write path), path guard          │
│  core/parser.py  daily-note sections, frontmatter, checkbox toggle  │
│  core/graph_index.py  wikilink parse → nodes/edges → cache json     │
│  core/skills.py  YAML loader + prompt templating                    │
│  core/runner.py  async worker, job state machine                    │
│  core/llm.py     LLMClient ABC + OpenAICompatClient                 │
│  db.sqlite       jobs table only                                    │
└──────────────────────────────────────────────────────────────────────┘
        │ read/write .md                     │ HTTPS
   Obsidian vault (source of truth)     LLM endpoint (configured)
```

## 2. Key decisions (mini-ADRs)

| # | Decision | Choice | Why / alternatives rejected |
|---|---|---|---|
| D1 | Job store | SQLite, 1 table | Zero-infra, solo use. Redis/Celery = overkill (rejected) |
| D2 | Runner placement | asyncio task in backend process lifespan | Separate daemon adds ops burden; revisit if jobs need GPU/long CPU |
| D3 | UI ↔ state sync | Poll `/state` 5 s (M1) → WS push (M3) | Poll is enough to ship; WS is pure UX upgrade |
| D4 | Graph rendering | Custom canvas force sim (d3-force allowed if already in host deps) | Constitution Art. III bans heavy libs; 400-node LOD keeps n² viable |
| D5 | Graph scale for 964 notes | Server-side LOD: top-400 by degree + filters | Full graph kills fps and legibility; matches Obsidian filter UX |
| D6 | Wikilink resolution | Basename match, same-folder preferred | Mirrors Obsidian shortest-path; full path resolution deferred |
| D7 | Unlinked mentions | Per-note on demand, never vault-wide | O(N²) text scan on 964 notes is seconds of CPU per load |
| D8 | Rename link-rewrite | Backend rewrites `[[oldname]]` & `[[oldname\|alias]]` across vault in one pass, dry-run count returned in confirm dialog | Silent mass-edit is risky; confirm with count first |
| D9 | Md rendering | Host's existing md lib if present, else markdown-it | Avoid duplicate renderers |
| D10 | Delete ops | Not implemented; archive-move only | Constitution Art. VII |
| D11 | Vault watching | mtime check on request + 2 s debounce cache | inotify/watchdog adds platform issues on WSL2/OneDrive paths |

## 3. Data flow — skill run (happy path)

1. UI POST `/jobs {skill_id}` → row `queued`, returns job id.
2. Runner picks job → `running` → loads skill YAML → resolves `context_files` globs →
   builds prompt (`{{date}} {{time}} {{context}}` + `input_params`).
3. `LLMClient.complete()` → text + usage.
4. `VaultWriter.write(output.path, mode)` → frontmatter `{skill, job_id, created}`.
5. Job → `done`; WS event (M3) or next poll updates UI; DOCUMENTS panel shows the new file;
   graph cache invalidated if the file adds wikilinks.

## 4. Risks

| Risk | L×I | Mitigation |
|---|---|---|
| OneDrive-synced vault path → file-lock/latency flakiness | M×M | Retry-once on write; health check flags slow vault reads |
| Vault has non-standard md (Excel-pasted tables, JP text) | H×L | Parser is tolerant: unknown sections ignored; UTF-8 with errors="replace" on read only |
| Rename rewrite corrupts a note | L×H | Dry-run count + single-pass regex bounded to `[[...]]` tokens + unit tests with JP filenames |
| LLM endpoint slow/down | M×M | job_timeout_s, error state surfaces in JOB LOG, health pill goes red |
| Graph fps on low-end | M×L | LOD 400, freeze-after-settle, devicePixelRatio cap 2 |

## 5. Definition of Done (feature)

All milestone checklists in spec §7 + §A5 pass; constitution articles verified in a final
self-review; CLAUDE.md updated with any new commands.

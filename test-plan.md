# Test Plan — VAULT Agentic OS Tab

**Version:** 1.0 | **QA:** self (solo) | Scope: this feature only, not the host app.

## 1. Strategy

| Type | Tool | Target | When |
|------|------|--------|------|
| Unit (backend) | pytest | VaultWriter, path guard, parser, skill loader, graph_index, rename-rewrite, runner FSM — 80% cov on new code | every commit |
| Integration | pytest + httpx (LLM mocked) | all `/api/vault/*` routes | every milestone gate |
| E2E manual | milestone ✓-gate checklists (spec §7 + §A5) | happy + failure paths | end of each milestone |
| Perf | timed script + browser devtools | graph budgets | end of M2 |

LLM endpoint is **always mocked** in automated tests (canned completion + usage). One
opt-in marked test (`-m live`) hits the real endpoint.

## 2. Test data

`tests/fixtures/mini-vault/` — committed synthetic vault, ~30 notes covering: typed
subfolders, JP filenames (日本語ノート.md), alias wikilinks `[[a|b]]`, links inside code
fences (must be ignored), a hub note with 10 backlinks, a note with unlinked mentions,
daily note with Schedule/Directives/Focus sections, missing-section daily note,
metrics.json + goal.yaml, and one file with broken frontmatter.

Perf tests generate a 1,000-note vault on the fly (script `tests/gen_vault.py`).

## 3. P0 cases

| TC | Title | Steps | Expected |
|----|-------|-------|----------|
| 01 | Skill happy path | POST /jobs plan-today (mock LLM) | job done; file in 04-notes with frontmatter {skill, job_id} |
| 02 | LLM failure | mock raises timeout | job error, message stored, runner keeps serving next job |
| 03 | Path traversal | GET /file?path=../../etc/passwd (and encoded variants) | 400/403, nothing read |
| 04 | Write containment | skill output.path points outside vault | VaultWriter refuses, job error |
| 05 | Collision suffix | run same create-mode skill twice same minute | second file gets -1 suffix |
| 06 | Missing daily note | fresh vault, GET /state | 200, empty-state fields, no exception |
| 07 | Graph build correctness | mini-vault /graph | node/edge counts match hand-count; code-fence link excluded; alias resolved |
| 08 | Backlinks parity | /notes/{hub}/links | 10 linked mentions with context lines; unlinked mention detected on demand |
| 09 | LOD | 1,000-note vault, /graph default | ≤400 nodes, ranked by degree, total_nodes=1000 |
| 10 | Rename rewrite | rename note referenced by 5 files (incl. alias link + JP name) | dry-run count=5; after confirm, grep old name in [[ ]] → 0 hits; content otherwise untouched |
| 11 | Archive not delete | vault-clean skill / archive action | file moved to 99-archive/, original gone, nothing unlinked from disk |
| 12 | Interrupted jobs | kill backend with job running, restart | job status error: interrupted |
| 13 | Cancel | cancel a queued job | status cancelled, runner never picks it |
| 14 | Search | q matches filename + body | both hit types returned with snippet |

## 4. Perf budgets (M2 gate)

| Metric | Budget |
|--------|--------|
| Graph cold index, 1,000 notes | < 3 s |
| /graph warm (cache hit) | < 300 ms |
| Canvas steady-state | 60 fps @ 400 nodes (mid laptop, DPR ≤ 2) |
| Tab bundle addition | ≤ 200 KB gz |

## 5. Exit criteria (feature release)

- [ ] All P0 cases pass; 0 known data-loss bugs
- [ ] Milestone checklists §7 + §A5 all checked
- [ ] Coverage ≥ 80% on new backend modules
- [ ] Host app's existing tests still green (regression)

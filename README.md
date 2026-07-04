# Oschertator — 2nd Brain OS

Obsidian vault command center with AI chatbot, graph view, and skill automation.

## Quick Start

```bash
cd oschertor

# Backend
cd backend
uv sync
uv run uvicorn src.main:get_app --factory --host 0.0.0.0 --port 8080

# Frontend (another terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`

## Setup

### Environment Variables

```bash
# Required
export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"
export LLM_API_KEY="your-api-key"

# Optional
export LLM_ENDPOINT_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o"
export PORT=8080
```

### Create Skills

Place YAML files in your vault at `90-system/skills/`:

```yaml
id: my-skill
label: "My Skill"
description: "What it does"
prompt_template: |
  Read these notes and summarize:
  {{context}}
context_files:
  - "04-notes/*.md"
output:
  path: "04-notes/output-{{date}}-{{time}}.md"
  mode: create
tags: [daily]
```

## Architecture

```
Frontend (React+Vite) ←proxy→ Backend (FastAPI) ←read/write→ Obsidian Vault
                                        ↓
                                   LLM Endpoint
```

### Backend
- **FastAPI** app with job queue (SQLite)
- **VaultWriter**: single write path, path-containment guard
- **GraphIndex**: wikilink graph with caching
- **Oschertator**: RAG chatbot with tool use

### Frontend
- React 19 + Vite + TypeScript
- 3-column VAULT tab layout
- Graph canvas (custom force sim)
- Floating chat widget

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/vault/health` | Health check |
| GET | `/api/vault/state` | Vault state + metrics |
| GET | `/api/vault/skills` | List available skills |
| POST | `/api/vault/jobs` | Enqueue a job |
| GET | `/api/vault/jobs` | List recent jobs |
| GET | `/api/vault/graph` | Graph nodes + edges |
| GET | `/api/vault/search?q=` | Search vault |
| GET | `/api/vault/file?path=` | Read a note |
| GET | `/api/vault/tree` | Folder tree |
| POST | `/v1/chat/completions` | Oschertator chat |
| POST | `/v1/chat/stream` | Oschertator streaming |

## Project Structure

```
oschertor/
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI app factory
│   │   └── vault_tab/
│   │       ├── api/             # Routes + Oschertator
│   │       ├── core/            # Business logic
│   │       └── tests/           # Unit tests (68 tests)
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/          # UI components
│   │   ├── styles/              # Design tokens
│   │   └── utils/               # API helpers
│   └── package.json
└── demo-vault/                  # Demo Obsidian vault
    ├── 01-daily/               # Daily notes
    ├── 02-concepts/            # Concepts
    ├── 03-projects/            # Project notes
    ├── 04-notes/               # Output notes
    └── 90-system/              # Config + skills
```

## Tests

```bash
cd backend
uv run pytest -v
```

68 tests covering:
- VaultWriter (path guard, collision, rename+link-rewrite)
- Parser (daily notes, checkboxes, frontmatter)
- Skills (YAML loading, prompt templating)
- GraphIndex (wikilinks, aliases, code fences)

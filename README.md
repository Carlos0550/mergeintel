# MergeIntel

> AI-powered merge analysis tool. Before merging a PR, understand exactly what changed, who changed it, and what could break.

![Status](https://img.shields.io/badge/status-in%20development-amber)
![Stack](https://img.shields.io/badge/stack-TypeScript%20%7C%20Python%20%7C%20React-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## The problem

You've been working on a branch for weeks. Your teammate Pedro opens a PR. You have no idea:

- What exactly changed since the last merge
- Whether Pedro touched files outside his scope
- If his branch is so old it'll overwrite recent code
- What Alembic migrations you need to generate
- Which bugs were fixed, which features were added

MergeIntel solves all of this automatically, before you click merge.

---

## What it does

MergeIntel connects to your GitHub repository, reads every commit in a PR, and generates a full technical summary of what's going to land in `main`.

**Automatic author detection**
Every commit is mapped to its author. The system builds a per-person breakdown: which files they touched, when they committed, and how diverged their branch was at the time.

**Schema change analysis**
Detects changes to SQL files, Alembic migration files, and ORM models. Tells you exactly which migrations you need to generate before deploying.

**Out-of-scope file detection**
You tell the system (or the AI infers) what each person was supposed to work on. MergeIntel flags every file touched outside that scope — the most common source of accidental overwrites.

**Branch divergence detection**
Compares commit timestamps against `main` history to detect stale branches. If Pedro's branch diverged 3 weeks ago, MergeIntel tells you before you merge.

**Pre-merge checklist**
A structured checklist of everything that needs to happen before the merge: migrations to run, breaking changes to review, risky files to inspect.

**AI chat — contextual Q&A**
Ask questions about the PR in natural language. The AI has full context of every commit, every author, and every changed file. Examples:

- *"Pedro was only supposed to touch the payments module, is that what happened?"*
- *"What Alembic migrations do I need to generate for this PR?"*
- *"Which commits are most likely to cause conflicts with main?"*

---

## Stack

| Layer | Technology |
|---|---|
| GitHub integration | GitHub REST API v3 via `httpx` |
| Backend | Python + FastAPI |
| AI analysis | Anthropic SDK / OpenAI SDK / Ollama |
| Frontend | React + TypeScript |
| Database | PostgreSQL via `asyncpg` |
| CI integration | GitHub Actions |

---

## Architecture

Single backend — FastAPI handles everything: GitHub integration, AI analysis, and serving the built frontend.

```
GitHub PR
    │
    ▼
FastAPI backend
    │
    ├── github/         GitHub API client (httpx)
    │       ├── Commit parser
    │       ├── Author mapper        (who touched what)
    │       ├── File diff analyzer   (what changed)
    │       ├── Schema detector      (SQL / Alembic / ORM models)
    │       └── Branch age checker   (divergence from main)
    │
    ├── analyzer/       AI analysis layer
    │       ├── Summary generator
    │       ├── Out-of-scope detector
    │       ├── Risk scorer
    │       └── Chat context builder
    │
    └── api/            REST endpoints consumed by the React dashboard
```

---

## MVP scope

The first version focuses on the core value: **connect a PR, get a useful summary**.

- [ ] GitHub OAuth + repo connection
- [ ] PR diff fetching via GitHub API
- [ ] Commit → author mapping (automatic)
- [ ] File change breakdown per author
- [ ] Branch divergence detection
- [ ] Schema/migration file detection
- [ ] LLM summary generation
- [ ] Basic dashboard with per-author cards
- [ ] Pre-merge checklist
- [ ] AI chat with PR context

Out of scope for MVP:
- GitHub Action (post-MVP)
- Multi-repo support
- Saved history of past PRs

---

## Project structure

```
mergeintel/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── routers/
│   │   ├── pr.py                # PR analysis endpoints
│   │   └── chat.py              # AI chat endpoints
│   ├── github/
│   │   ├── client.py            # GitHub API client (httpx)
│   │   ├── commits.py           # Commit + author parser
│   │   ├── diff.py              # File diff analyzer
│   │   └── divergence.py        # Branch age / divergence checker
│   ├── analyzer/
│   │   ├── summary.py           # LLM summary generator
│   │   ├── scope.py             # Out-of-scope file detector
│   │   ├── schema.py            # SQL / Alembic / ORM change detector
│   │   └── chat.py              # Chat context + LLM handler
│   ├── models/                  # Pydantic schemas
│   └── db/                      # asyncpg database layer
├── frontend/                    # React + TypeScript dashboard
├── alembic/                     # DB migrations
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

---

## Getting started

> Setup instructions will be added as the project progresses.

```bash
# Clone the repo
git clone https://github.com/your-username/mergeintel.git
cd mergeintel

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start development
uvicorn backend.main:app --reload
```

---

## Environment variables

```env
# GitHub
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_WEBHOOK_SECRET=

# AI provider (pick one)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/mergeintel
```

---

## Motivation

Built out of real frustration. Working on a team where branches diverge for weeks, teammates accidentally touch files outside their scope, and every merge becomes an investigation. MergeIntel is the tool I wanted before every merge at work.

---

## License

MIT
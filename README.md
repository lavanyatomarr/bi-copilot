# AI-Powered Business Intelligence Copilot

Natural-language analytics over your own datasets, with an AST-based SQL safety engine
and hybrid RAG. Built on a 100% free / open-source stack.

> **Status:** Milestone 1 — backend + PostgreSQL (pgvector) booting via Docker.

## Run it (Milestone 1)

Requirements: Docker Desktop installed and running.

```bash
docker compose up --build
```

Then open:
- http://localhost:8000/         → backend alive check
- http://localhost:8000/health   → DB + pgvector check
- http://localhost:8000/docs     → auto-generated interactive API docs (FastAPI)

A healthy response from `/health` looks like:

```json
{ "ok": true, "database": "connected", "pgvector": "enabled" }
```

Stop everything with `Ctrl+C`, or wipe the database volume with:

```bash
docker compose down -v
```

## Stack
FastAPI · PostgreSQL + pgvector · Docker · (React, free LLM, RAG — coming in later milestones)

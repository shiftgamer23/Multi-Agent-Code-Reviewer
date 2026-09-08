# Phase 9: Docker Deployment ✓ COMPLETE

## What We Built

- `Dockerfile` — `python:3.12-slim`, installs `requirements.txt`, copies
  only `app/` (not the whole repo - see `.dockerignore`), runs uvicorn on
  `0.0.0.0:8000`
- `.dockerignore` — excludes `venv/`, `data/`, `Comment_Generation/`,
  `.git/`, `.env`, docs
- `docker-compose.yml` — two services:
  - `app` — built from the Dockerfile, `REDIS_HOST=redis`/`REDIS_PORT=6379`
    set explicitly (overrides `app/infra/redis_client.py`'s `localhost`
    default, since containers reach each other by service name on the
    compose network, not `localhost`), secrets (`GEMINI_API_KEY`,
    `GROQ_API_KEY`, `LANGFUSE_*`) passed via `env_file: .env`
  - `redis` — `redis:7-alpine`, with a named volume (`redis_data`) so the
    cache/run-store survive a container restart

## Scope Decisions (both explicitly conditional in plan.md)

- **No self-hosted Langfuse service**: plan.md lists this as optional
  ("and (optionally) a self-hosted Langfuse instance"). We're already on
  Langfuse Cloud (Phase 8, verified working end-to-end) - running a
  second, separate Langfuse instance would just fragment where traces go,
  not add anything.
- **No Ollama service**: plan.md's own note says to add this "based on
  whether free-tier cloud limits actually became a blocker during Phase
  6" - they did (Gemini's daily quota), but we solved it with the Groq
  cloud fallback (Phase 8), not a local model. Revisit only if Groq's
  free tier also becomes insufficient.

## End-to-End Verification

Replaced the standalone Phase-7 Redis container with the compose-managed
one (`docker compose up -d --build`), then drove the fully containerized
stack with real requests:

1. **`GET /health`** → `200 OK` through the container
2. **`POST /review` (new diff)** → container logs confirmed
   `"Cache miss for run ... - starting background review"`, then each
   node completing (`test_coverage`, `security`, `style`, `merge`) via the
   `BackgroundTasks` job - proving the app container can reach both the
   `redis` service (by name, not `localhost`) and the external Gemini API
2. **Same diff submitted again** → container logs confirmed
   `"Cache hit for run ... (diff_hash=238a33dc5440...)"`, identical review
   content returned - proving the Phase 7 cache works correctly inside
   the compose network, not just against the standalone container it was
   built against.

## Files Created

- `Dockerfile`, `.dockerignore`, `docker-compose.yml`

## Bring the stack up/down

```
docker compose up -d --build   # build + start app + redis
docker compose logs app -f     # follow app logs
docker compose down            # stop (add -v to also drop the redis_data volume)
```

## Project Status

All 9 phases from `plan.md` are complete. The system: routes a diff to
relevant specialist agents, runs them in parallel with tool-calling
(style/security/test-coverage checks), merges their findings, caches
results in Redis, serves everything over a FastAPI + SSE backend with
automatic Gemini→Groq failover, traces every call through Langfuse, and
runs as a two-service Docker Compose stack. Evaluated against 100 real
human reviewer comments from the CodeReviewer dataset (Phase 6) with an
honest, documented account of both what it catches well (checklist-style
issues) and its ceiling (deep logic/design review).

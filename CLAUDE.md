# Album Deep-Dive App

Plan: [docs/PLAN.md](docs/PLAN.md). One PR per milestone; stop for review after each.

## Commands
- `docker compose up -d db` start Postgres (copy `.env.example` to `.env` first)
- `pnpm dev:api` FastAPI on :8000 (`uv run fastapi dev app/main.py` in `apps/api`)
- `pnpm dev:web` Next.js on :3000
- `pnpm lint` / `pnpm test` run both apps' checks (`uv run ruff check .`, `uv run pytest`, eslint, vitest)

## Rules
- Node >= 22.12 (see `.nvmrc`), Python 3.12.
- Every factual statement is a claim with sources; public endpoints return only `approved` claims.
- Never store lyric text in the DB; lyrics come from `LyricsProvider` at runtime.
- Check Apple MusicKit details against current Apple docs before coding.
- Secrets (.env, .p8) are never committed.

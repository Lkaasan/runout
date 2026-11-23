# Album Deep-Dive App

Plan: [docs/PLAN.md](docs/PLAN.md). One PR per milestone; stop for review after each.

## Commands
- `pnpm setup` one-time: install deps, migrate, import the placeholder album (copy `.env.example` to `.env` first; use the SQLite line in it if you have no Docker)
- `pnpm db` start Postgres in Docker (optional)
- `pnpm dev` API on :8000 and web on :3000 together
- `pnpm dev:api` FastAPI on :8000 (`uv run fastapi dev app/main.py` in `apps/api`)
- `pnpm dev:web` Next.js on :3000
- `cd apps/api && uv run alembic upgrade head` apply migrations; `uv run alembic revision --autogenerate -m msg` after model changes (a test fails if models and migrations drift)
- `cd apps/api && uv run python -m app.seed import <slug>` import `content/albums/<slug>/` (validates first; safe to re-run)
- `pnpm gen:api` regenerate `apps/web/openapi.json` and `src/api/schema.d.ts` after any API schema change (CI fails if stale)
- `cd apps/api && uv run python -m app.research init "<Artist>" "<Album>"` start a NEW album: builds a claim-free seed folder (tracks, lengths, Apple Music ids, cover) from the Apple Music or Bandcamp page linked in the album's Wikipedia article, and a first `research.yaml` from that article's references (`--from URL` to name the track-list page)
- `cd apps/api && uv run python -m app.research collect <slug>` fetch MusicBrainz and Wikipedia pages into `.research-cache/` (no AI; repeat runs use the cache)
- `cd apps/api && uv run python -m app.research extract <slug> [--ignore-seed]` ask Claude Code (your subscription login, no API key) to propose claims from the collected pages; writes `content/albums/<slug>/proposals/<run>/`. Needs `claude` signed in; uses subscription usage
- `cd apps/api && uv run python -m app.research trace <slug> [--limit N]` look for the original interview/book behind artist-intent claims. The ONLY step that gives a model web tools; it returns addresses only, which our own fetcher vets and downloads. A found original is *proposed* as primary; a person must confirm it
- `cd apps/api && uv run python -m app.research verify-eval <slug>` test the verifier on errors planted into the last extract run (uses subscription usage)
- Extra pages for the finder to read go in `content/albums/<slug>/research.yaml` (`urls:`); model answers are saved in `.research-cache/llm/` so re-runs are free (`--fresh` asks again)
- `cd apps/api && uv run python -m app.research score <slug> --oracle|--empty|--proposal FILE` score an information-finder run against `apps/api/evals/gold/<slug>.yaml`
- `pnpm lint` / `pnpm test` run both apps' checks (`uv run ruff check .`, `uv run pytest`, eslint, vitest)

## Rules
- Node >= 22.12 (see `.nvmrc`), Python 3.12.
- Every factual statement is a claim with sources; public endpoints return only `approved` claims.
- Never store lyric text in the DB; lyrics come from `LyricsProvider` at runtime.
- Check Apple MusicKit details against current Apple docs before coding.
- Secrets (.env, .p8) are never committed.

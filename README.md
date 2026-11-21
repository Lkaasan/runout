# runout

Album deep-dive listening app. See [docs/PLAN.md](docs/PLAN.md).

## Quick start
Requires Node >= 22.12, pnpm, uv. Docker is optional (SQLite works for local dev).

```
cp .env.example .env     # for SQLite, set DATABASE_URL=sqlite:///./dev.db
pnpm db                  # only if using Postgres
pnpm setup               # install, migrate, import the placeholder album
pnpm dev                 # API http://localhost:8000 (docs at /docs), web http://localhost:3000
```

Admin endpoints (`/admin/...`) use HTTP basic auth with `ADMIN_PASSWORD` from `.env` (any username).

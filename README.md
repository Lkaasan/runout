# runout

Album deep-dive listening app. See [docs/PLAN.md](docs/PLAN.md).

## Quick start
Requires Node >= 22.12, pnpm, uv, Docker.

```
cp .env.example .env
pnpm install
(cd apps/api && uv sync)
pnpm dev        # Postgres + API (:8000) + web (:3000)
```

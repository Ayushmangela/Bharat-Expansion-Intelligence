# 10 — Deployment

Everything free. No trials, no credit cards.

---

## docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: ./backend
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  worker:
    build: ./backend
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
    volumes: ["./data:/app/data"]
    command: python -m pipeline.flows.orchestrator

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [api]

  # Optional, heavy. Profile-gated.
  ollama:
    image: ollama/ollama
    profiles: ["llm"]
    volumes: [ollama:/root/.ollama]
    ports: ["11434:11434"]

  # Optional ad-hoc BI on the gold schema
  metabase:
    image: metabase/metabase
    profiles: ["bi"]
    ports: ["3000:3000"]

volumes: {pgdata: , ollama: }
```

```bash
docker compose up -d                      # core
docker compose --profile llm up -d        # with local LLM
docker compose --profile bi up -d         # with Metabase
```

---

## Free hosting

| Component | Service | Notes |
|---|---|---|
| Database | **Neon** or **Supabase** free tier | Real Postgres. Watch storage — multiple MCA snapshots add up. Retain last 6 snapshots + permanent transition log. |
| API | **Render** / **Railway** / **Fly.io** free tier | Container deploy. Cold starts on free tiers — acceptable. |
| Frontend | **Vercel** (native Next.js support) / Netlify / Cloudflare Pages | Free tier |
| Scheduled jobs | **GitHub Actions cron** | Free for public repos. **Underrated for exactly this.** Run logs are public and become portfolio evidence. |
| LLM | Local Ollama in dev; **disabled in prod** | App must work without it |

### GitHub Actions as the scheduler

```yaml
# .github/workflows/monthly-pipeline.yml
name: Monthly Pipeline
on:
  schedule: [{cron: '0 2 5 * *'}]   # 5th of each month, 02:00 UTC
  workflow_dispatch:
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -e "./backend[dev]"
      - run: python -m pipeline.flows.monthly
        env:
          DATA_GOV_IN_API_KEY: ${{ secrets.DATA_GOV_IN_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
      - name: Upload run manifest
        if: always()
        uses: actions/upload-artifact@v4
        with: {name: run-manifest, path: data/manifests/}
```

Secrets go in GitHub repo settings. **Never in the workflow file.**

---

## CI

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  backend:
    services:
      postgres:
        image: postgres:16
        env: {POSTGRES_PASSWORD: test, POSTGRES_DB: test}
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-retries 5
    steps:
      - run: ruff check .
      - run: mypy backend/app backend/pipeline
      - run: pytest --cov=app --cov=pipeline
  frontend:
    steps:
      - run: npm ci && npm run lint && npm run typecheck && npm run test
```

---

## Secrets checklist — do this before the first commit

- [ ] `.env` in `.gitignore`
- [ ] `.env.example` committed with placeholders only
- [ ] `data/bronze/` in `.gitignore`
- [ ] No API key in any notebook output, test fixture, or commit message
- [ ] `api-key` redacted from all logged URLs
- [ ] GitHub secrets configured for CI/scheduled runs

If a key is ever committed, **regenerate it immediately.** Git history is permanent and
scrapers find committed keys within hours.

---

## Migrations

```bash
alembic revision --autogenerate -m "add fact_score_contribution"
alembic upgrade head
```

Never edit an applied migration. Never `DROP` in a migration without an explicit,
reviewed decision — bronze can rebuild gold, but only if bronze survived.

---

## Backup

Bronze Parquet is the real backup — gold can be rebuilt from it. Keep bronze on durable
storage if you deploy for real. For a portfolio project, local disk plus the fact that
sources are re-fetchable is sufficient.

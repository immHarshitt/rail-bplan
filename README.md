# RAIL-OPT — AI-Powered Railway Maintenance Block Optimization

Prototype for Indian Railways: CP-SAT-based optimization that **coordinates cross-department
maintenance blocks** (Engineering, Signal & Telecom, Traction) into shared closures instead of
three separate ones per corridor — cutting block-hours and reducing train hold-ups, with full
explainability and what-if simulation.

**Demo result (deterministic, seed 42):** 78 tasks → **34 blocks** (21 multi-department),
**K5: −32.0% block-hours** vs baseline (target ≥25%), **K3: 61.8% coordination** (target ≥40%).

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python · FastAPI · SQLAlchemy 2.0 · OR-Tools CP-SAT |
| Frontend | Next.js 16 · React 19 · Tailwind CSS v4 · TypeScript |
| Database | PostgreSQL 15 (Docker) |
| Infra | docker-compose (postgres only; backend/frontend run from venv/npm) |

## Quick start

1. **PostgreSQL** (Docker):
   ```bash
   docker compose up -d
   ```

2. **Backend** (http://localhost:8000):
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # adjust if needed
   python run.py
   ```

3. **Frontend** (http://localhost:3000):
   ```bash
   cd frontend
   npm install
   cp .env.example .env.local   # points to http://localhost:8000
   npm run dev
   ```

4. **Verify the demo numbers** (any terminal, needs only the backend running):
   ```bash
   python3 verify_demo.py
   ```

## Repository layout

```
backend/            FastAPI app (optimizer, baseline, KPI, ripple, explain engines)
frontend/           Next.js dashboard (plan board, what-if panel, why panel)
verify_demo.py      One-command check of all frozen demo numbers
DEMO.md             ️Demo runbook: pre-flight + 5-minute click-by-click script
phase.md etc.       Development tracking files (phases, decisions, flows, brain)
RAIL-OPT_PRD_v1.md  The product requirements document
```

> ⚠️ **Demo-only**: all data is synthetic, the DB credentials in `docker-compose.yml` /
> `.env.example` are for local development, and the system is designed for offline demos.

## Demo highlights

1. **Generate weekly plan** — one click → baseline & RAIL-OPT compared (K1–K5).
2. **Plan board** — weekly lanes; gradient blocks mark multi-department coordinated closures.
3. **Why panel** — click any block: coordination rationale, block-hours saved, per-task
   priority drivers, timing window. Numbers derive from the *same* code the optimizer ran.
4. **What-if** — extend/move a block → instantly see trains held, cascade delay, plan-score
   delta (analytic recompute, no re-solve, <2s).

See [DEMO.md](DEMO.md) for the full presenter runbook.

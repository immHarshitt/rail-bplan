# RAIL-OPT — Demo Runbook

**Demo date:** 2026-09-03 · **Duration:** ~5 minutes · **Everything is offline & deterministic** (seed 42 → identical numbers every run).

> One-line confidence check before you present:
> ```bash
> python3 verify_demo.py
> ```
> Green "ALL CHECKS PASSED" = every frozen number is intact and all four demo beats work. Do not present if it prints red.

---

## 0. The stack (what runs where)

| Layer | How it runs | URL / port |
|-------|-------------|-----------|
| **PostgreSQL** | Docker container `railopt-db` (postgres:15-alpine) | localhost:5432 |
| **Backend** | Python venv at `/tmp/railopt-venv`, `python run.py` (uvicorn, auto-reload) | http://localhost:8000 |
| **Frontend** | Next.js dev server, `npm run dev` | http://localhost:3000 |

Only PostgreSQL is containerized. Backend and frontend run from the venv / npm. This is the verified working setup — don't try to dockerize the rest the morning of.

> **Docker CLI note:** the `docker` command may not be on your PATH even when Docker Desktop is running. On this machine it lives at
> `/Applications/Docker.app/Contents/Resources/bin/docker`. If `docker` "isn't found" but the app is open, the DB is still up — check with `lsof -nP -iTCP:5432 -sTCP:LISTEN`.

---

## 1. Pre-flight (T‑15 min)

Run these from the repo root: `/Users/harshitmishra/IMP Documents/Rail-Bplan`

**1. Start PostgreSQL** (skip if `railopt-db` already shows healthy):
```bash
docker compose up -d
```

**2. Start the backend:**
```bash
cd backend && source /tmp/railopt-venv/bin/activate && python run.py
```
Wait for `Uvicorn running on http://0.0.0.0:8000`. Leave this terminal open.

**3. Start the frontend** (new terminal):
```bash
cd frontend && npm run dev
```
Wait for `Ready` / `Local: http://localhost:3000`. Leave this terminal open.

**4. Verify everything** (new terminal, repo root):
```bash
python3 verify_demo.py
```
Expect green **ALL CHECKS PASSED**. It also prints the what-if hero block's **corridor** and the "why" hero block — glance at those so you know which blocks to click on stage.

**5. Warm the browser:** open http://localhost:3000, click **Generate weekly plan** once so Next.js compiles the page and the data is cached. Then refresh to a clean slate for the real run.

> If `/data/generate` is ever re-run (fresh DB), immediately `POST /api/v1/data/backfill-train-paths` or the what-if ripple will be empty. You should NOT need to regenerate — the DB is already loaded (200 requests, 724 train paths).

---

## 2. The 5-minute script (click-by-click)

### Beat 0 — The problem (30s, no clicks)
> "Indian Railways runs three maintenance departments — Engineering, Signal & Telecom, and Traction. Today each one requests track closures **separately**. The same stretch of corridor gets shut three times in a week: wasted block-hours, and trains held again and again. RAIL-OPT coordinates them into shared closures."

### Beat 1 — Generate the plan (45s)
- **Click:** `Generate weekly plan`.
- Watch the **KPI strip** fill in. Say the headline while pointing:
  - **78 tasks → 34 blocks**
  - **K5 block-hours: −32%** (target was ≥25%) — green
  - **K3 coordination: 61.8%** (target was ≥40%) — green
- > "Same 78 maintenance jobs. The optimizer packed them into 34 closures instead of 78 — a third fewer block-hours — and it solved in about a second."

### Beat 2 — The board & the before/after (60s)
- **Scroll** the weekly block board. Point at the **gradient (multi-color) blocks** — those are coordinated closures where 2–3 departments share one window.
- **Click** the **RAIL-OPT ⇄ Baseline** toggle → the board expands from **34 blocks to 78**.
- > "This is the 'before'. Baseline is first-come-first-served: 78 separate closures. RAIL-OPT is 34, and **21 of them coordinate two or three departments** in a single window. That's the whole game — collapse three closures into one."
- Toggle **back to RAIL-OPT**.

### Beat 3 — Why is it here? (60s)
- **Click** the widest **gradient block** (labeled "4 tasks · 3 departments"). The teal **WHY** panel opens.
- Walk the four cards:
  - **Coordination:** "4 → 1" — 4 tasks, 3 departments, one closure.
  - **Value:** **3h 45m saved**, **2.5× compression**, plan value 965.
  - **Task priorities:** each task's score with its **drivers** ("Base weight +50", "Overdue by N days +…", "Defect severity …").
  - **Timing:** sits in a **Traffic-lean** window that permits a power block.
- > "This isn't a black box. Every number here is computed by the **same functions the optimizer used** to make the decision — the priorities, the coordination bonus, the block-hours math. If a controller asks 'why this block?', the answer is the arithmetic itself."

### Beat 4 — What if it overruns? (75s)
- **Click** a **single-department block** (solid color) on a **single-line corridor** — the one the pre-flight script flagged (corridor printed by `verify_demo.py`).
- In the **What-If** panel, press **Extend** to add **+120 min**.
- Point at the result:
  - Mode badge: **HOLD** (single line → trains wait at the upstream loop).
  - **7 passenger trains held**, cascade delay ~6h.
  - **Plan score 72.2 → 70.4**.
  - Returned in **<2 seconds**.
- > "A planner asks 'what if this job overruns by two hours?' Instantly: seven trains would be held, here's the cascade, here's the score hit. No re-solve, no waiting. That's the difference between a static plan and a decision tool."

### Close (30s)
> "Targets were 25% fewer block-hours and 40% cross-department coordination. We hit **32%** and **62%** — on synthetic but realistic data, deterministic, fully explainable, and interactive. That's RAIL-OPT."

---

## 3. The numbers (cheat-sheet for Q&A)

| Metric | Value | Note |
|--------|-------|------|
| Objective value | **657110** | frozen; deterministic (seed 42, 1 worker) |
| Tasks scheduled | **78** | of 200 requests, within the weekly windows |
| Blocks (RAIL-OPT) | **34** | vs **78** baseline |
| Coordinated blocks | **21** | ≥2 departments in one window |
| K5 block-hours | **−32.0%** | target ≥25% |
| K3 coordination rate | **61.8%** | target ≥40% |
| K4 compression (hero block) | **2.5×** | 6.25h standalone → 2.5h bundled |
| Train paths | **724** | across 6 corridors |
| What-if hero | **7 trains held**, score 72.2→70.4 | single-line extend +120, HOLD, <2s |

**Bundling rule:** tasks within **8 km** on the same corridor, compatible block types, fitting an admissible window, can share one closure. **Coordination bonus:** +300 objective per extra department in a block — that's what tips the optimizer toward shared windows.

---

## 4. If something breaks (fallbacks)

| Symptom | Fix |
|---------|-----|
| Frontend won't load / white screen | Backend must be up first (`:8000`). Check the backend terminal for tracebacks. CORS already allows :3000/:3001. |
| KPIs show `undefined` / blanks | Backend response shape drifted from `lib/api.ts`. Re-run `verify_demo.py` — it hits the raw endpoints and will pinpoint which one. |
| What-if shows "0 trains affected" | Train paths missing. `curl -X POST http://localhost:8000/api/v1/data/backfill-train-paths` then re-generate the plan. |
| `role "railopt" does not exist` | A local Homebrew postgres is fighting the container for :5432. `brew services stop postgresql@18`; the Docker `railopt-db` is the real DB. |
| Solve seems stuck | It shouldn't exceed ~1–2s. If a browser call hangs, the backend is fine — reload the page; the plan is deterministic so nothing is lost. |
| Total UI failure | Fall back to the API directly: `python3 verify_demo.py` prints every headline number live in the terminal — you can narrate from that. |

**Golden rule:** the numbers are frozen and deterministic. If in doubt, re-run `verify_demo.py` — green means you're safe to present.

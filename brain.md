# RAIL-OPT Project Context (Brain)

**Last Updated**: 2026-09-02  
**Current Phase**: DEMO-READY — critical path + explainability + demo hardening COMPLETE (Phases 0,1,2,4,5,6,8 done)

---

## What We're Building

**RAIL-OPT** = AI-Powered Railway Maintenance Block Optimization for Indian Railways  
**Goal**: Coordinate maintenance across 3 departments (Engineering, S&T, Traction) to minimize train disruption  
**Demo Date**: Tomorrow (2026-09-03)  
**Key Metric**: Show ≥25% fewer block-hours and ≥40% cross-department coordination vs baseline

---

## The Core Problem

Today's process:
1. Engineering department needs 2h to fix track at KM 245
2. S&T department needs 1.5h for signal work at KM 247 (2km away)
3. Traction department needs 1h for OHE work at KM 246 (middle)
4. Each raises separate block request → **3 blocks = 4.5 hours total + 3× overhead**

Our solution:
- **Spatial bundling**: All within 5km → can share one block
- **CP-SAT optimizer**: Schedules them in one 90min window → **1 block = 1.5h + 1× overhead**
- **Result**: ~60% time saved, one closure instead of three

---

## Current State

### Phase 0: Foundation ✅ COMPLETED
- ✅ Backend structure (FastAPI + SQLAlchemy)
- ✅ All 16 database models from PRD §9
- ✅ Synthetic data generator (200 requests, 6 corridors, 15-20 planted bundles)
- ✅ Data generation API endpoints
- ✅ Docker compose configuration
- ✅ All 5 tracking files initialized

### Phase 1: Core Optimizer ✅ COMPLETED
- ✅ CP-SAT optimizer (M6) — `backend/app/engines/optimizer.py`, OPTIMAL in 0.11s
- ✅ FCFS baseline planner (M11) — `backend/app/engines/baseline.py`
- ✅ KPI engine K1-K5 — `backend/app/engines/kpi.py`
- ✅ Plan APIs — generate / baseline / compare / kpis / details / list
- ✅ Verified end-to-end: 78 tasks scheduled, optimizer==baseline at parity (correct pre-bundling)

### Phase 2: Bundle Coordination ✅ COMPLETED
- ✅ Opportunity engine (M4) — `backend/app/engines/opportunity.py`
  - Singleton + all contiguous sub-bundle candidates; 8km block-section radius (D15)
  - PRD §12.4 bundle duration (same-dept serialize, cross-dept parallel)
- ✅ Optimizer rewritten to candidate/set-packing CP-SAT (D16); persists multi-dept blocks
- ✅ **K5 −32.0%** (target ≥25%), **K3 61.8%** (target ≥40%) — BOTH TARGETS MET
- ✅ 78 tasks → 34 blocks (21 coordinated), OPTIMAL ~1.0s, deterministic (D17), no double-scheduling

### Phase 4: Minimal UI ✅ COMPLETED
- ✅ Next.js 16.3.4 client dashboard (`frontend/app/page.tsx`) — one "Generate weekly plan"
  button fans out to `/plan/generate` + `/plan/baseline`, then `/plan/compare` + 2× `/details`
- ✅ Typed API client `frontend/lib/api.ts`; KPI strip `components/KpiStrip.tsx`;
  interactive weekly plan board `components/PlanBoard.tsx` (gradient multi-dept blocks + badges,
  click→task detail, RAIL-OPT⇄Baseline toggle showing the 34↔78 flip)
- ✅ Verified live against backend: all 5 calls 200, locked numbers rendered, both targets green
- Preview: `.claude/launch.json` → `railopt-frontend` (npm run dev, port 3000)

### Phase 5: What-If Interaction ✅ COMPLETED
- ✅ Data fix: `_generate_train_paths` corridor bug (hardcoded `randint(1,6)` vs real ids 8–13)
  + `POST /data/backfill-train-paths` (deterministic, train_path only) → **724 paths, 6 corridors**
- ✅ Ripple engine (M5) — `backend/app/engines/ripple.py` — deterministic §12.9.2:
  DIVERT (double-line) / HOLD (single-line, at upstream loop) / INFEASIBLE (no loop);
  priority regulation (goods absorb detention); headway-spaced queue discharge
- ✅ What-if engine — `backend/app/engines/whatif.py` — EXTEND/MOVE applied to in-memory
  copies (stored plan untouched); KPI recompute + plan_score §12.9.3 (0-100 w/ breakdown)
- ✅ `POST /plan/{id}/whatif` → kpi/ripple/plan_score before→after→delta
- ✅ Frontend `components/WhatIfPanel.tsx` in the plan board (RAIL-OPT only): extend/move
  steppers + 3 metric cards + mode badge + most-delayed-train chips
- ✅ Verified live: **extend single-line block +120 → 7 passenger trains HELD, cascade 6h31m,
  plan score 72.2→70.4**; ~0.19s latency (K15 ≤2s ✓); acceptance §12.9.4 holds

### Phase 6: Explainability ✅ COMPLETED
- ✅ `optimizer.priority_of` refactored to expose `priority_components()` (labelled drivers,
  bit-identical sum → **frozen objective 657110 preserved**)
- ✅ `backend/app/engines/explain.py` — `ExplainEngine.explain(plan_id, block_id)`:
  coordination rationale, value + block-hours saved, per-task priority drivers, timing window
- ✅ `GET /plan/{id}/block/{block_id}/why`
- ✅ Frontend `components/WhyPanel.tsx` (teal, auto-loads) wired into PlanBoard for both kinds
- ✅ Verified: 3-dept block → "4→1" collapse, 3h45m saved, 2.50×, plan value 965, driver chips,
  TRAFFIC_LEAN window; no console errors

### Phase 8: Demo Hardening ✅ COMPLETED
- ✅ `verify_demo.py` (repo root, stdlib-only) — one command hits the live backend and asserts EVERY
  frozen number: data (6/200/724), objective 657110, 34 blocks / 21 coord / 78 tasks, K5 −32% & K3 61.8%
  (+ target flags), what-if ripple (extend strictly ↑trains-held & ↓plan-score, §12.9.4), why-panel
  (coord bonus / hours saved / drivers / window). Exits non-zero on any drift. **ALL CHECKS PASSED** live.
- ✅ `DEMO.md` (repo root) — full runbook: accurate stack (postgres=Docker `railopt-db`; backend=venv
  `python run.py`; frontend=`npm run dev`), T-15 pre-flight, 5-min click-by-click script with on-screen
  numbers + talking points, Q&A cheat-sheet, §4 fallbacks table for offline failures.
- ✅ Stack verified up: `railopt-db` healthy, backend :8000 (200), frontend :3000. Solve ~1s, what-if ~0.19s.
- ✅ Honest scope call: only postgres containerized; did NOT re-dockerize backend/frontend the night before
  (the venv+npm path is the verified working setup — lower risk than new Docker images hours before demo).

### Remaining (optional stretch — NOT on critical path)
Phase 3 (priority scoring/Weibull) and Phase 7 (shadow blocks/pull-forward, K11). The demo is complete
without them. All must-haves (0,1,2,4,5) + P1 credibility (6) + demo prep (8) are done.

---

## Architecture Overview

```
Input Data (synthetic):
  ├─ maintenance_request (200 tasks across 3 depts)
  ├─ corridor (6 rail sections, ~70km each)
  ├─ train_path (180 trains with schedules)
  └─ block_window (traffic-lean maintenance slots)

Processing Pipeline:
  ├─ M6: CP-SAT Optimizer → schedules tasks to maximize value
  ├─ M11: Baseline Planner → naive FCFS for comparison
  └─ KPI Engine → computes K1-K5 metrics

Output:
  ├─ Weekly block plan (which tasks, when, which corridor)
  ├─ KPIs: block-hours, coordination rate, completion
  └─ Comparison: RAIL-OPT vs baseline
```

---

## Key Technical Concepts

### 1. Block Types
- **TRAFFIC_BLOCK**: Stop trains on one track line
- **POWER_BLOCK**: De-energize overhead wire
- **DISCONNECTION**: Isolate signaling equipment
- **CORRIDOR_BLOCK**: Close entire corridor

### 2. Bundle Compatibility
Two tasks can share a block if:
- Same corridor
- Within 5km of each other
- Compatible block types
- Different gangs or serializable
- Fit in an available window

### 3. Bundle Duration Formula
```
duration = T_protect + max(parallel_groups) + T_release
T_protect = 15min + 15min (if power block)
T_release = 10min + 10min (if power block)
```

### 4. CP-SAT Model (Phase 1)
- **Decision variables**: x_i (scheduled?), s_i, e_i (start/end slots)
- **Hard constraints**: H1-H6 (NoOverlap, task-in-block, windows, gangs)
- **Objective**: Maximize (priority × completion - block_hours)
- **Time slots**: 15-minute granularity, weekly horizon = 672 slots

---

## Critical Path to Demo

**Must-have** (Phases 0,1,2,4,5):
1. ✅ Phase 0: Foundation (DONE)
2. ✅ Phase 1: CP-SAT optimizer + baseline + KPIs (DONE)
3. ✅ Phase 2: Bundle coordination — the differentiator (DONE, both targets met)
4. ⏳ Phase 4: UI comparison screen (the proof)
5. ⏳ Phase 5: What-if interaction (the wow)

**Nice-to-have** (Phases 3,6,7):
- Phase 3: Priority scoring
- Phase 6: Explainability panel
- Phase 7: Shadow blocks

**Fallback**:
- UI fails → Streamlit with comparison table
- Optimizer slow → Pre-solved frozen plan
- Time runs out → Show comparison screen only

---

## Important Constraints

### Hard Requirements
- ✅ **Offline demo**: All in Docker Compose
- ✅ **Deterministic**: Same seed → same plan
- ✅ **Fast solve**: <60 seconds
- ✅ **What-if latency**: <2 seconds

### Scope Boundaries
- ❌ NOT building: Real railway integration, auth, mobile app
- ✅ ARE building: Proof-of-concept with synthetic data

---

## Key Assumptions

1. **200 requests** (Decision D8): Reduced from 600 for demo solve time
2. **6 corridors**: Simplified from multi-division
3. **CP-SAT can solve in <60s**: If not, use pre-solved fallback
4. **Ground truth validation**: 15-20 planted bundles to verify optimizer
5. **Weekly horizon**: Single horizon only (no multi-level)

---

## Technology Stack

**Backend**:
- Python 3.10+, FastAPI, SQLAlchemy 2.0
- OR-Tools CP-SAT (constraint solver)
- PostgreSQL 15

**Frontend** (Phase 4 — built):
- Next.js 16.3.4 (App Router, Turbopack), React 19, Tailwind CSS v4
- Client-only dashboard hitting the FastAPI backend directly; forced light theme
- Fallback: Streamlit (not needed — Next.js UI works)

**Infrastructure**:
- Docker Compose
- Uvicorn with auto-reload

---

## Data Model (Simplified)

### Core Tables (16 total)
- **Infrastructure**: corridor, station, track_section
- **Assets**: asset (with condition tracking)
- **Work**: maintenance_request (200 tasks)
- **Resources**: resource_gang (4 gangs)
- **Traffic**: train, train_path (180 trains)
- **Windows**: block_window
- **Planning**: plan, planned_block, planned_block_task
- **Analysis**: kpi_snapshot, scenario

### Key Relationships
- Request → Asset (1:1)
- Request → Station + TrackSection (location)
- Block → Window (1:1)
- Block → Tasks (1:N)
- Block → Gang (1:1)

---

## Demo KPIs (K1-K5)

| Metric | Formula | Target |
|--------|---------|--------|
| **K1: Completion rate** | Tasks scheduled / total | ≥ baseline |
| **K2: Asset availability** | Weighted uptime | ≥3pp better |
| **K3: Coordination rate** | Blocks with ≥2 depts / total | ≥40% |
| **K4: Compression ratio** | Standalone hours / bundled | ≥1.8× |
| **K5: Block-hours** | Σ(block duration) | ≥25% below baseline |

**The story**: Same work, fewer block-hours, better coordination.

---

## Files Created (Phase 0)

### Backend (15 files)
1. `backend/app/core/config.py` - Settings
2. `backend/app/core/database.py` - DB engine
3. `backend/app/models/__init__.py` - All 16 models
4. `backend/app/main.py` - FastAPI app
5. `backend/app/api/routers/data.py` - Data endpoints
6. `backend/synth/generator.py` - Synthetic data
7. `backend/run.py` - Dev server
8. `backend/requirements.txt` - Dependencies
9. `backend/README.md` - Setup guide
10. `backend/.env.example` - Environment template

### Configuration (2 files)
1. `docker-compose.yml` - PostgreSQL service
2. `.gitignore` - Ignore patterns

### Documentation (5 files)
1. `phase.md` - Phase tracking
2. `implementation.md` - Implementation log
3. `decision.md` - Technical decisions
4. `brain.md` - This file
5. `flow.md` - System flows

---

## Next Task (Phase 1)

**Implement CP-SAT Model Builder (M6)**

File: `backend/app/engines/optimizer.py`

**Components**:
1. **Decision Variables**:
   - `x_i`: Binary (task i scheduled?)
   - `s_i, e_i`: Integer (start/end time slots)
   - `interval_i`: IntervalVar (task duration in schedule)

2. **Hard Constraints** (PRD §12.6.1):
   - H1: NoOverlap (no conflicting blocks on same track)
   - H2: Task in block (each task in exactly one block)
   - H3: Task within block (task fits within block bounds)
   - H4: Window constraint (block within admissible window)
   - H5: Gang availability (no double-booking)
   - H6: Scope match (gang can do all tasks)

3. **Objective**:
   ```
   maximize: Σ(priority_i × x_i) - Σ(block_duration)
   ```

4. **API Endpoint**:
   ```
   POST /api/v1/plan/generate
   → Returns: plan_id, objective_value, solve_time, blocks
   ```

**Expected Outcome**:
- Solve time <60s for 200 requests
- Find some bundled blocks (validation in Phase 2)
- Baseline for comparison (Phase 1 also implements M11)

---

## Resume Instructions

**If continuing**:
1. Read `phase.md` for current status
2. Check last completed task in `implementation.md`
3. Review context in this file
4. Continue from next incomplete task
5. Update all tracking files after progress

**Do NOT**:
- Redo completed work
- Re-plan phases
- Second-guess documented decisions

**Golden rule**: Trust the tracking files, continue where we left off.

---

## Success Criteria (Minimum Demo)

Demo is ready when:
1. ✅ Database with 200 synthetic requests
2. ⏳ `/plan/generate` returns plan in <60s
3. ⏳ `/baseline/generate` returns comparison
4. ⏳ `/compare` shows K1-K5 with ≥25% improvement
5. ⏳ UI displays comparison table
6. ⏳ Docker Compose starts everything
7. ⏳ Demo script under 5 minutes

**Current**: #1-#3 done (data, optimizer, baseline+compare all working). Working on Phase 2 bundling to hit #4 (≥25% improvement).

---

## Critical Gotchas (learned in Phase 1)

1. **Port 5432**: Local Homebrew `postgresql@18` fights Docker for the port. If connections
   fail with `role "railopt" does not exist`, run `brew services stop postgresql@18` — the
   Docker container (`railopt-db`) is the real DB.
2. **Field names matter**: use `est_duration_min`, `start_ts`/`end_ts`, `PlannedBlock.depts`
   (array), `kpi_snapshot.kpi` (single JSONB col). Not the invented names from early drafts.
3. **Datetimes**: block_window/planned_block columns are `timezone=True`; psycopg2 returns
   tz-aware. Use `_naive()` from optimizer.py before mixing with naive horizon datetimes.
4. **Duration model**: always slot-round (ceil to 15 min) — optimizer, baseline, AND kpi must
   agree or the comparison is unfair (see D13).
5. **Venv**: server runs from `/tmp/railopt-venv`. Start with:
   `cd backend && source /tmp/railopt-venv/bin/activate && python run.py`
6. **Regenerating data**: `POST /api/v1/data/generate` now wipes all tables first, so plan_ids
   reset. Re-run generate → generate plan → baseline → compare in order.
7. **Bundling knobs (Phase 2)**: `opportunity.py` — `BUNDLE_RADIUS_KM=8.0` (block section, D15),
   candidates = singletons + all contiguous sub-bundles. The optimizer is candidate/set-packing
   (D16), NOT one-interval-per-request. `COORD_BONUS_OBJ=300` lives in optimizer.py and must
   match `COORDINATION_BONUS_PER_EXTRA_DEPT` in opportunity.py (kept separate to avoid a circular
   import). To re-tune K5/K3, change the radius — K5 is monotonic in it and all within-radius
   pairs are always bundled.
8. **KPI engine reads the DB, not the solver**: K3/K4/K5 are computed from persisted
   `planned_block.depts` + timestamps. If bundling looks absent in KPIs, check `persist_plan`
   wrote `depts` as the union and `bundle_id` for multi-task blocks — not the KPI code.
9. **Frontend (Phase 4)**: `frontend/` is Next.js **16.3.4**, NOT 14 — it has real breaking
   changes vs older training data (`params`/`searchParams` are Promises; layout uses the
   auto-generated `LayoutProps<"/">`). `frontend/AGENTS.md` (re-added by `next dev`) says to read
   `node_modules/next/dist/docs/` before writing Next code. `'use client'` works normally.
   Run the UI via the preview tool (`railopt-frontend` in `.claude/launch.json`, port 3000);
   backend must be up on :8000 first. CORS already allows :3000/:3001 (`app/main.py`).
   `devIndicators:false` in `next.config.ts` hides the dev overlay for the demo.
10. **Frontend↔backend contract is by hand**: `lib/api.ts` interfaces mirror `plan.py`/`data.py`
    responses exactly (e.g. `compare()` → {railopt, baseline, improvements, summary};
    `/details` → {..., blocks:[{depts, is_coordinated, tasks:[...]}]}). If you change a backend
    response shape, update the matching TS interface or the UI silently renders `undefined`.
11. **train_paths needs backfill after every `/data/generate`**: `/data/generate` produces
    0 paths on a drifted DB (corridor ids ≠ 1–6). The what-if ripple is empty without paths.
    After regenerating data, ALWAYS run `POST /api/v1/data/backfill-train-paths` (deterministic,
    724 paths, touches only train_path so locked K5/K3 stay frozen). The generator itself is now
    fixed for fresh DBs, but existing/drifted DBs still need the backfill.
12. **What-if works in minute-of-day space, not wall-clock**: ripple compares a block's
    `hour*60+minute` against train `entry_min` (both 0–1440), checking day offsets −1/0/+1 for
    the midnight-wrap lean window. The browser shows block times in **IST (+5:30)** so a 04:30
    block reads "10:00" — purely cosmetic, impact numbers are correct. Don't "fix" the tz.
13. **What-if never re-solves and never mutates the plan**: EXTEND/MOVE only change block bounds,
    so `whatif.py` recomputes analytically on in-memory copies (no CP-SAT). Fast (~0.19s) and safe
    to click repeatedly on stage. Only RAIL-OPT blocks get the panel (baseline is read-only).
14. **plan_score is per-plan, not per-block**: §12.9.3 aggregates the whole plan (maint value,
    block-hours, coord, total cascade delay, utilization). A single block edit moves it a little
    (72.2→70.4). Constants live at the top of `whatif.py` (weights + `CASCADE_REF_PER_BLOCK=120`).
15. **`priority_of` feeds the objective — treat edits as frozen-number changes**: Phase 6 refactored
    it to `priority_components()` for the why-panel. The component sum MUST stay bit-identical or the
    locked objective (657110) shifts and the demo numbers break. After ANY touch to `priority_of`,
    `_bundle_minutes`, `COORD_BONUS_OBJ`, or the objective, regenerate a plan and re-verify 657110
    in the same session. The explain engine reuses these functions on purpose (D21) — the "why" IS
    the computation, so it stays honest under questioning; don't write a parallel display-only scorer.
16. **Demo verification is one command — use it before touching anything**: `python3 verify_demo.py`
    (repo root, stdlib-only, no venv needed) hits the live backend and asserts every frozen number +
    all four demo beats. Green "ALL CHECKS PASSED" = safe to present / safe that a change didn't drift
    the locked numbers. It's the fastest regression check in the repo — run it after any backend edit,
    not just before the demo. Full presenter runbook is `DEMO.md`.
17. **`docker` CLI is often NOT on PATH even when Docker Desktop is running**: on this machine it lives
    at `/Applications/Docker.app/Contents/Resources/bin/docker`, not `/usr/local/bin`. So `docker ps`
    can say "not found" while the DB is perfectly up. Don't panic-restart — check the port instead:
    `lsof -nP -iTCP:5432 -sTCP:LISTEN` (a `com.docker` process bound there = `railopt-db` container is
    serving). Same for the backend: `lsof -nP -iTCP:8000 -sTCP:LISTEN`.

# RAIL-OPT Implementation Record

**Last Updated**: 2026-09-02  
**Current Phase**: Phase 8 - Demo Hardening (COMPLETED ✓) → DEMO-READY

---

## Phase 8: Demo Hardening & Runbook (COMPLETED ✓)

Make the demo trustworthy on stage: one command that proves every frozen number is intact,
and a runbook the presenter can follow click-by-click. No new product code — this phase is
about repeatability and de-risking.

### Deliverables
- **`verify_demo.py`** (repo root, stdlib-only — runs with any `python3`, no venv/deps) — hits the
  live backend on :8000 and asserts, in five sections:
  1. **DATA** — 6 corridors · 200 requests · 724 train paths
  2. **OPTIMIZE** — objective **657110** · 34 blocks · 21 coordinated · 78 tasks · OPTIMAL
  3. **COMPARE** — K5 ≥25% (got −32.0%) · K3 ≥40% (got 61.8%) · both `meets_*_target` flags True
  4. **WHAT-IF** — scans blocks for the first whose +120 extend adds trains, asserts trains-affected
     **strictly increases** AND plan score **strictly decreases** (acceptance §12.9.4)
  5. **WHY** — picks the top coordinated block, asserts multi-dept + coordination bonus > 0 +
     hours saved > 0 + compression > 1 + every task has priority drivers + a timing window
  Prints per-check ✓/✗ with values, exits non-zero on any failure. Designed as a fast regression
  check, not just a pre-demo ritual — run it after any backend edit.
- **`DEMO.md`** (repo root) — the presenter runbook:
  - **Stack table** — postgres = Docker `railopt-db`; backend = venv `/tmp/railopt-venv` `python run.py`;
    frontend = `npm run dev`. Only postgres is containerized (honest about the real setup).
  - **T-15 pre-flight** — exact startup commands in order + `verify_demo.py` gate + browser warm-up.
  - **5-minute script** — Beat 0 problem → 1 generate (78→34, −32%, 62%) → 2 board + RAIL-OPT⇄Baseline
    toggle (34↔78) → 3 Why panel (4→1, 3h45m saved, 2.5×, drivers) → 4 What-if (extend +120 → 7 held,
    72.2→70.4, HOLD) → close. Each beat has the on-screen numbers and the line to say.
  - **Q&A cheat-sheet** — every frozen number in one table + the bundling/coordination-bonus rules.
  - **§4 fallbacks** — UI white screen, undefined KPIs, empty ripple (backfill), :5432 port fight,
    hung call, total UI failure (narrate from `verify_demo.py` output).

### Verified (live, 2026-09-02)
- `verify_demo.py` → **ALL CHECKS PASSED**. What-if hero landed on corridor 11 (ENGG, single-line,
  1 task): 0→7 trains held, HOLD, score 72.2→70.4 — matching the frozen story exactly.
- Confirmed the compare shape uses `n_blocks`/`n_scheduled_tasks`/`n_coordinated_blocks`
  (RAIL-OPT 34/78/21 @ 86.5h vs baseline 78/78/0 @ 127.25h) → the "34 → 78" toggle claim is correct.
- Stack up: `railopt-db` (postgres:15-alpine) healthy 3h; backend :8000 returns 200; frontend :3000.

### Decisions / gotchas
- **Did NOT re-dockerize backend/frontend the night before** (D22). The venv+npm path is verified and
  working; new Docker images hours before the demo is pure downside risk. `DEMO.md` documents reality.
- **`docker` CLI is not on the default PATH** (it's under `/Applications/Docker.app/...`). `docker ps`
  can report "not found" while the DB is up — check `lsof -iTCP:5432` instead. Captured in `DEMO.md`
  and brain gotcha 17.
- `verify_demo.py` asserts the what-if **mechanic** (strict monotonic change), not a brittle exact
  train count — deterministic iteration reliably surfaces the corridor-11 hero, but the check stays
  robust if block ordering ever shifts.

---

## Phase 6: Explainability "Why" Panel (COMPLETED ✓)

Click any block and see the optimizer's OWN reasoning — not a post-hoc story. Four
strands (PRD §12.10): why these tasks are together (coordination), the value + block-hours
it saved, why each task earns its place (priority drivers), and the window that pinned the
timing. Read-only; works on RAIL-OPT and baseline blocks alike.

### Backend
- **`backend/app/engines/optimizer.py`** — refactored `priority_of()` to delegate its
  fallback path to a new **`priority_components(req, horizon_start)`** returning
  `[(label, points)]` (Base weight 50 / Defect severity N/5 / Overdue by N days / Due
  today|in N days). The score and its explanation now live in ONE place so they can never
  drift. **Verified the component sum is bit-identical** to the old logic → the locked
  objective is unchanged (fresh plan = **657110.0**, 34 blocks, 21 coordinated).
- **`backend/app/engines/explain.py`** (new) — `ExplainEngine.explain(plan_id, block_id)`:
  - **coordination**: n_tasks/n_depts, km_span, radius, headline + prose rationale
    ("3 departments (ENGG, SNT and TRD) within 4.5 km … bundled into ONE closure instead of 4")
  - **value**: task_value (Σ priority) + coordination_bonus (`n_extra_depts × COORD_BONUS_OBJ`,
    imported from optimizer), plus standalone_hours (`Σ _bundle_minutes([task])`) vs
    bundled_hours → hours_saved + compression
  - **tasks**: per-task priority + driver breakdown, sorted highest-priority first
  - **window**: reconstructs the admissible window (H4) — containing windows on the corridor,
    preferring TRAFFIC_LEAN whose allowed types include this block's type — with a rationale
- **`backend/app/api/routers/plan.py`** — `GET /plan/{id}/block/{block_id}/why` (404 bad ids).

### Frontend
- **`frontend/lib/api.ts`** — `PriorityDriver`, `WhyTask`, `WhyWindow`, `WhyBlock` types +
  `explainBlock(planId, blockId)`.
- **`frontend/components/WhyPanel.tsx`** (new, teal accent) — auto-loads on block open
  (`useEffect` keyed on plan+block, with cancel guard). Sections: coordination card with a
  "N → 1" collapse visual + dept chips; 3 value stats (time saved / compression / plan value);
  per-task priority rows with driver chips; timing card with window-kind badge.
- **`frontend/components/PlanBoard.tsx`** — renders `<WhyPanel>` in BlockDetail for BOTH
  plan kinds, before the (RAIL-OPT-only) What-If panel: "why it's here" precedes "what if".

### Verified (live, 2026-09-02)
- Frozen objective preserved after the refactor (657110.0).
- `/why` on a 3-dept POWER_BLOCK (4 tasks): task_value 365 + coord 600 = 965, standalone
  6.25h → bundled 2.5h = **3.75h saved, 2.50×**, 3 OVERDUE tasks @100 + 1 SCHEDULED @65,
  TRAFFIC_LEAN window. Renders correctly in-browser (4→1 visual, driver chips). No console errors.

### Decisions / gotchas
- **Never fabricate the explanation.** Every number is derived from the same code the
  optimizer ran (priority_components, COORD_BONUS_OBJ, _bundle_minutes). Honest under questioning.
- **The refactor is the risk.** Touching `priority_of` could shift the objective. Mitigated by
  making the component-sum bit-identical and re-verifying 657110 immediately. See decision D21.
- The optimizer doesn't persist which window a block used, so ExplainEngine reconstructs it
  by containment + a TRAFFIC_LEAN/type-match preference — a heuristic, but matches H4's intent.

---

## Phase 5: What-If Ripple Simulator (COMPLETED ✓)

The demo centrepiece: click a RAIL-OPT block, extend or move it, and see the
train-traffic consequences recompute instantly — trains held, cascade delay,
goods detention, plan-score drop, feasibility. Turns the static proof screen
into the interactive "wow". PRD §12.9.

### Data foundation fix (blocker)
- **`backend/synth/generator.py`** `_generate_train_paths()` rewritten: it
  hardcoded `corridor_id = random.randint(1, 6)`, but Postgres SERIAL ids drift
  after repeated `/data/generate` wipes (corridors are now 8–13), so **zero**
  paths ever matched → `train_paths = 0`. Now groups sections by their real
  `corridor_id`, sorts each by km, and routes each train through 3–5 physically
  consecutive sections on a corridor that actually exists.
- **`backend/app/api/routers/data.py`** — new `POST /api/v1/data/backfill-train-paths`:
  regenerates ONLY the `train_path` table for the current dataset (fixed RNG seed
  20260903 → deterministic). Touches nothing else, so the locked K5/K3 numbers stay
  frozen (the optimizer never consumes train paths). Result: **724 paths across all
  6 corridors, 74/77 sections**, clear diurnal shape (goods in lean hours), 243 goods.

### New engines
- **`backend/app/engines/ripple.py`** — `RippleEngine` (M5), deterministic
  event-propagation per PRD §12.9.2:
  - Finds train paths on the blocked section(s) within `[t_start − headway,
    t_end + clearance]` (checks day-1/day/day+1 for the midnight-wrap lean window)
  - **Mode**: `n_lines ≥ 2` and not CORRIDOR_BLOCK → **DIVERT** (single-line working,
    trains metered at headway); single-line / corridor block → **HOLD** at the
    nearest upstream loop station; no upstream loop → **INFEASIBLE** (edit rejected)
  - **Regulation order**: protected first, then priority_class, goods last (goods
    absorb detention) — deterministic tie-break by entry time
  - Queue discharge at `headway` spacing; escalating congestion capped at `D_MAX=6`
  - Aggregates trains_affected, passenger/goods delay, goods_detention_hours,
    max_delay, held/diverted, protected_train_hit, top-6 most-delayed trains
  - Pure: every number from DB rows + fixed arithmetic (no RNG, no wall-clock)
- **`backend/app/engines/whatif.py`** — `WhatIfEngine`:
  - Applies `EXTEND_BLOCK` (fix start, push end by delta) / `MOVE_BLOCK` (shift both
    bounds, keep duration) to in-memory block copies — **stored plan never mutated**
  - Recomputes KPIs analytically (same slot-rounded conventions as kpi.py) and the
    ripple for the edited block only (others unchanged), before vs after
  - **plan_score §12.9.3** (0–100): `100 × (0.30·maint_value + 0.20·(1−block_hours) +
    0.15·coord + 0.15·(1−cascade_delay) + 0.10·asset_avail + 0.10·utilization)` with
    a component breakdown returned for the UI

### New API
- **`backend/app/api/routers/plan.py`** — `POST /api/v1/plan/{id}/whatif`
  {op, block_id, delta_min, label?} → {feasible, infeasibility_reason, kpi_before/
  after/delta, ripple_before/after/delta, plan_score_before/after, plan_score_delta}.
  400 on bad block id / unsupported op.

### Frontend
- **`frontend/lib/api.ts`** — added `RippleTrain`, `RippleResult`, `PlanScore`,
  `WhatIfResult`, `WhatIfOp` types + `simulateWhatIf(planId, op, blockId, deltaMin)`.
- **`frontend/components/WhatIfPanel.tsx`** (new) — Extend (+15/+30/+60/+120) & Move
  (◀60/◀30/30▶/60▶) stepper rows; 3 headline metric cards (trains affected / cascade
  delay / plan score) showing before→after with red-for-disruption / green-for-relief
  delta tone; mode badge (HOLD/DIVERT/INFEASIBLE); held/diverted + passenger-delay +
  goods-detention summary; protected-train warning; most-delayed-train chips (pax/goods,
  🛡 for protected). INFEASIBLE renders a rejection card.
- **`frontend/components/PlanBoard.tsx`** — `BlockDetail` now takes `planId` +
  `whatIfEnabled`; renders `<WhatIfPanel>` only for the RAIL-OPT plan (baseline is
  read-only). Resets on block change via `useEffect`.

### Verified (live in-browser + API, 2026-09-02)
- DataBar shows **724 train paths** (was 0) after backfill
- **Hero moment**: extend the single-line corridor-11 ENGG block **+120** → mode HOLD,
  **0→7 passenger trains held, cascade delay 0→6h 31m, plan score 72.2→70.4**,
  K5 86.5→88.5h; most-delayed chips 10057 1h52m / 10038 1h18m / … including a RAJ_SHTB
- MOVE ◀60 on the same block → 0→2 trains, 0→2h47m, score 72.2→71.6 (smaller, still red —
  the optimizer already placed it at zero-impact)
- Acceptance §12.9.4 holds: extend strictly ↑ trains-affected and strictly ↓ plan score
- Latency ~0.19s per call (K15 ≤2s ✓); deterministic; no console errors

### Bugs/decisions during Phase 5
1. `train_paths = 0` — generator corridor bug (see data foundation fix above); backfill
   endpoint keeps locked numbers frozen (D19)
2. Browser renders block times in IST (+5:30), so a 04:30 lean-window block displays as
   "10:00". Cosmetic only — the ripple works in a shared 0–1440 minute space (block
   wall-minute vs train `entry_min`), so impact numbers are correct regardless of tz label
3. Only 10/35 RAJ_SHTB are flagged `is_protected`, so `protected_train_hit` can be False
   even when a Rajdhani is held — honest, not a bug (the flag fires when a protected train
   is actually hit)
4. Chose stepper buttons over drag-to-extend: identical "see impact move" moment, far more
   reliable on stage (D18 rationale extended)

---

## Phase 4: Minimal UI (COMPLETED ✓)

The "proof screen": a client-side dashboard (`frontend/`, Next.js 16.3.4 + React 19 +
Tailwind v4) that calls the FastAPI backend directly and renders the baseline-vs-RAIL-OPT
comparison. No server components / no DB access from the front end — everything goes through
the typed API client.

### Files
- **`frontend/lib/api.ts`** — typed client mirroring `plan.py`/`data.py` responses.
  `API_BASE` from `NEXT_PUBLIC_API_BASE` (fallback `http://localhost:8000`). Interfaces:
  `DataStats`, `PlanResult`, `Kpi`, `Improvements`, `CompareResult`, `PlanBlock`, `BlockTask`,
  `PlanDetails`. Functions: `getStats`, `generatePlan`, `generateBaseline`, `comparePlans`,
  `getPlanDetails`. `DEPT_COLORS`/`deptColor()`: ENGG=blue, SNT=green, TRD=orange.
- **`frontend/app/page.tsx`** — `'use client'` dashboard. Loads `/data/stats` on mount;
  "Generate weekly plan" runs `generatePlan` + `generateBaseline` in parallel, then
  `comparePlans` + `getPlanDetails×2`. Holds both plans; view toggle switches the board.
  Empty / loading / error states included (error hints "is the backend on :8000?").
- **`frontend/components/KpiStrip.tsx`** — four cards: K5 block-hours + K3 coordination as
  hero cards with target badges (✓≥25% / ✓≥40%), plus track-closures (78→34) and K4
  compression. Footer line: "40.75 block-hours saved… 44 fewer closures… completion 100%".
- **`frontend/components/PlanBoard.tsx`** — weekly (7-day) timeline. Blocks grouped by
  corridor, greedy-packed into non-overlapping sub-lanes, positioned by `start_ts`/`end_ts`.
  Single-dept = solid colour; multi-dept = hard-stop gradient of member dept colours + amber
  dept-count badge. Click a block → detail panel (type, time, km-span, per-task dept/km/dur).
- **`frontend/app/layout.tsx` / `globals.css`** — forced light theme (demo must look the same
  on any presenter OS), Geist fonts, slate palette.
- **`frontend/next.config.ts`** — `devIndicators: false` (clean demo, no dev overlay).
- **`.claude/launch.json`** — `railopt-frontend` preview config (`npm run dev`, cwd `frontend`,
  port 3000).

### Verified (live against backend :8000, 2026-09-02)
- All 5 calls HTTP 200 (generate plan 19, baseline 18, compare, 2× details); CORS preflight OK
- KPI strip shows locked numbers (86.5h/−32%, 62%/+61.8pp, 34 vs 78, 1.47×); both target
  badges green
- Plan board renders 6 corridors, gradient coordinated blocks with count badges; click opens
  task detail (e.g. Block #1090 Corridor 8, ENGG+SNT, 3 tasks, 1.5h)
- Baseline↔RAIL-OPT toggle flips 34→78 (baseline all single-dept, zero coordination badges) —
  the strongest visual

---

## Phase 2: Bundle Coordination (COMPLETED ✓)

### New Engine (backend/app/engines/opportunity.py)
- **`OpportunityEngine` (M4)** — generates the candidate set the optimizer chooses from
  - Emits a **singleton** candidate `s:{id}` per task (guarantees feasibility) PLUS
    every **contiguous sub-bundle** `b:{ids}` (sizes 2..5) per sliding anchor on a corridor
  - Spatial clustering within **8km** (block-section radius, D15); compatibility check on
    block types; per-corridor cap 200 by value
  - **`BundleCandidate`** dataclass carries `duration_slots/min`, `value`, `base_priority`,
    `n_extra_depts`, `depts`, km-span, `block_type`, `is_multi_dept`
  - **`_bundle_minutes()`** implements PRD §12.4: same-dept tasks serialize (Σ), different
    depts parallelize (max across depts), + protect/release (+15/+10 if power), slot-rounded
  - Value = Σ task priorities + `n_extra_depts × 300` coordination bonus

### Optimizer rewrite (backend/app/engines/optimizer.py)
- `build_and_solve()` is now **candidate/set-packing** based (was one-interval-per-request):
  - One BoolVar `y[k]` per candidate (open?), `cs[k]`/`ce[k]` start/end slots, OptionalIntervalVar
  - **Set packing**: `Σ (candidates covering task i) <= 1` — no task double-scheduled (D16)
  - **H4** window-fit per candidate; **H1** NoOverlap per corridor over opened intervals
  - Objective: `Σ y_k · (base_priority_k·100 + n_extra_depts_k·300 − block_minutes_k)`
- `persist_plan()` writes one PlannedBlock per opened candidate: `depts` = union of member
  depts, `bundle_id` set for multi-task blocks, all member tasks assigned (seq by dept)
- `optimize()` returns real `coordination_count` and `covered_tasks`
- KPI engine unchanged — it reads block-level `depts`/timestamps from the DB, so K3/K4/K5
  pick up bundling automatically

### Verified (live, 2026-09-02)
| Metric | Baseline (FCFS) | RAIL-OPT | Result |
|---|---|---|---|
| K5 block-hours | 127.25h | 86.5h | **−32.0%** (target ≥25% ✓) |
| K3 coordination | 0% | 61.8% | **+61.8pp** (target ≥40% ✓) |
| Blocks | 78 | 34 | 44 fewer closures |
| K4 compression | 1.00 | 1.47 | 40.75h saved |
| K1 completion | 100% | 100% | parity |
- OPTIMAL in ~1.0s (deterministic, 1 worker + seed 42, D17); 21 of 34 blocks multi-department
- Integrity check: 78 unique task ids / 78 task rows (set-packing holds)
- Headline example: one 2.5h POWER_BLOCK covers ENGG+SNT+TRD (4 tasks) vs 4 separate closures

### Bugs/decisions during Phase 2
1. Maximal-cluster-only candidates left adjacent singletons unbundled → emit all contiguous
   sub-bundles so the solver can pick the largest window-fitting bundle (D16)
2. 5km planting radius was too tight for the 25% K5 target → adopted 8km block-section radius
   after measuring 9.64km avg inter-station spacing (D15); ran a radius sweep to confirm
   monotonic K5 and that all within-radius pairs were already bundled at each setting
3. 8 parallel workers gave non-deterministic tie-breaking (K3 wobbled 61.8↔64.7%) → pinned
   to 1 worker + seed 42 for a repeatable demo (D17); solve still ~1.0s

---

## Phase 1: Core Optimizer (COMPLETED ✓)

### Engines Implemented (backend/app/engines/)
- **optimizer.py** — `CPSATOptimizer` (M6)
  - Decision vars: `x[i]` scheduled?, `s[i]`/`e[i]` start/end slot, optional IntervalVar
  - 15-min slots, weekly horizon = 672 slots
  - H1 NoOverlap per corridor; H4 each task must fit inside one admissible window
  - Objective: maximize Σ x_i·(priority·100 − block_minutes)
  - `priority_of()` fallback scoring (severity + overdue urgency) until M3 lands in Phase 3
  - Persists Plan + PlannedBlock + PlannedBlockTask; one standalone block per task
- **baseline.py** — `BaselinePlanner` (M11)
  - FCFS: sort by dept (ENGG→SNT→TRD), due date, severity; greedy earliest-fit placement
  - Same safety rules (no overlap, within windows), no coordination
  - Slot-rounded durations to match optimizer (fair K5 comparison)
- **kpi.py** — `KPIEngine`
  - K1 completion, K2 asset-availability (severity-weighted proxy), K3 coordination rate,
    K4 compression ratio, K5 block-hours
  - Stores results in `kpi_snapshot.kpi` (JSONB); `compare()` produces improvement deltas
  - Durations slot-rounded everywhere so K4=1.0 for standalone plans

### APIs Added (backend/app/api/routers/plan.py)
- `POST /api/v1/plan/generate` — run CP-SAT, returns plan_id/status/objective/solve time
- `POST /api/v1/plan/baseline` — run FCFS baseline
- `GET  /api/v1/plan/compare?railopt_plan_id=&baseline_plan_id=` — KPI comparison + deltas
- `GET  /api/v1/plan/{id}/kpis` — compute/recompute KPIs for a plan
- `GET  /api/v1/plan/{id}/details` — plan metadata + blocks + tasks (for UI)
- `GET  /api/v1/plan/list` — list all plans

### Verified (live, 2026-09-02)
- Optimizer: 78 candidate tasks (due within 1-week horizon), all scheduled, **OPTIMAL in 0.11s**
- Baseline: 78 tasks scheduled, FCFS
- Compare: both at parity K5=127.25h, K4=1.0 (correct — bundling gains come in Phase 2)

### Bugs Fixed During Phase 1
1. Engine files initially used wrong field names — rewrote against real schema
   (`est_duration_min`, `start_ts`/`end_ts`, `depts` array, `kpi_snapshot.kpi` JSONB)
2. tz-aware vs naive datetime mismatch → added `_naive()` helper
3. Duration model mismatch (optimizer slot-rounded, baseline/KPI raw minutes) made
   optimizer look worse → aligned all three to slot-rounded durations
4. Data generator: `data/` dir missing + no cleanup on regenerate → added `os.makedirs`
   and delete-all-then-regenerate in `/data/generate`
5. Local PostgreSQL@18 was occupying port 5432 → stopped it so Docker PG is used
6. SQL echo noise → set `echo=False` in engine

---

## Phase 0: Foundation & Setup (COMPLETED ✓)

## What Has Been Built (Phase 0)

### Planning & Documentation
- ✅ **PRD Analysis**: Full review of RAIL-OPT_PRD_v1.md completed
- ✅ **Phase Planning**: 8-phase development plan created with clear deliverables
- ✅ **Tracking System**: All 5 tracking files created and maintained

### Infrastructure
- ✅ **Backend Structure**: FastAPI application with modular architecture
- ✅ **Database**: SQLAlchemy models implementing PRD §9 canonical schema
- ✅ **Docker Setup**: Docker compose configuration for PostgreSQL
- ✅ **API Framework**: RESTful endpoints with OpenAPI documentation

### Backend Modules
- ✅ **Core**: Configuration management, database connection
- ✅ **Models**: All 16 database models from PRD §9
- ✅ **Synthetic Data Generator**: Internally consistent railway data with ground truth
- ✅ **Data API**: Endpoints for data generation and statistics

### Frontend
- ✅ **Scaffold**: Next.js project structure initialized (UI in Phase 4)

### Testing
- ✅ **Seed-based Generation**: Reproducible datasets (seed=42)
- ✅ **Ground Truth**: Planted bundle opportunities for validation

---

## Files Created/Modified

### Documentation (5 files)
1. `/phase.md` - Phase tracking (Phase 0 completed)
2. `/implementation.md` - This file (updated)
3. `/decision.md` - Technical decisions
4. `/brain.md` - Project context
5. `/flow.md` - System flows

### Backend (15 files)
1. `backend/app/core/config.py` - Settings with Pydantic
2. `backend/app/core/database.py` - SQLAlchemy engine/session
3. `backend/app/core/__init__.py`
4. `backend/app/models/__init__.py` - All 16 database models
5. `backend/app/main.py` - FastAPI app with CORS
6. `backend/app/__init__.py`
7. `backend/app/api/__init__.py`
8. `backend/app/api/routers/__init__.py`
9. `backend/app/api/routers/data.py` - Data generation endpoints
10. `backend/app/engines/__init__.py` - Placeholder for Phase 1
11. `backend/synth/__init__.py`
12. `backend/synth/generator.py` - Synthetic data generator
13. `backend/run.py` - Dev server launcher
14. `backend/requirements.txt` - Dependencies
15. `backend/README.md` - Setup guide

### Configuration (2 files)
1. `backend/.env.example` - Environment template
2. `docker-compose.yml` - PostgreSQL service

### Data (1 directory)
1. `data/` - Ground truth output directory

---

## Features Implemented

### Data Generation
- **6 Corridors**: Varied traffic classes (HIGH/MEDIUM/LOW)
- **~48 Stations**: 8 per corridor with junction flags
- **Track Sections**: Bidirectional support for single-line
- **~800 Assets**: ENGG/SNT/TRD with condition tracking
- **200 Maintenance Requests**: Decision D8 (reduced from 600 for demo)
  - Distribution: 60% ENGG, 25% SNT, 15% TRD
  - Task kinds: DEFECT, SCHEDULED, OVERDUE, INSPECTION
  - Realistic durations: 30-120 minutes
- **180 Trains**: 120 passenger + 60 goods with priority classes
- **Train Paths**: Diurnal patterns (peak/lean hours)
- **Block Windows**: Traffic-class-dependent maintenance slots
- **Ground Truth**: 15-20 planted bundle opportunities

### Asset Modeling
- **Aging Simulation**: Condition degrades with install date and GMT
- **Criticality Levels**: 1-5 scale with weighted distribution
- **Overhaul Tracking**: Last maintenance date influences condition

### Bundle Opportunity Planting
- **Spatial Clustering**: Tasks within 5km across departments
- **Multi-department**: At least 2 different departments per bundle
- **Ground Truth JSON**: Validates optimizer bundle detection

---

## APIs Implemented

### Data Management
- `POST /api/v1/data/generate` - Generate synthetic dataset
  - Input: seed, weeks, division
  - Output: Entity counts and ground truth cases
- `GET /api/v1/data/stats` - Database statistics
- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /docs` - OpenAPI documentation (auto-generated)

---

## Database Schema

### Core Tables (16 total)
1. **corridor** - Railway sections with traffic classification
2. **station** - Stations with platform/loop metadata
3. **track_section** - Sections between stations with runtime
4. **asset** - Railway assets with condition tracking
5. **resource_gang** - Maintenance crews with shift/scope
6. **maintenance_request** - Work tasks with priority scoring
7. **train** - Train registry with priority classes
8. **train_path** - Timetable with day-of-week masks
9. **block_window** - Admissible maintenance windows
10. **plan** - Optimization output plans
11. **planned_block** - Scheduled maintenance blocks
12. **planned_block_task** - Tasks assigned to blocks
13. **kpi_snapshot** - KPI metrics per plan
14. **scenario** - What-if scenario storage

### Enums (10 total)
- Dept, SrcSystem, BlockType, ReqStatus, Horizon
- LineType, TrafficClass, train classes

### Constraints
- Criticality: 1-5 range check
- Defect severity: 0-5 range check
- Task kind validation
- Train class validation

---

## Algorithms Implemented

### Synthetic Data Generation
1. **Corridor Generation**: 6 corridors with realistic km ranges
2. **Station Placement**: Even spacing with junction identification
3. **Asset Aging Model**: 
   - `condition = age_factor + overhaul_boost + noise`
   - Correlated with GMT and last maintenance
4. **Request Distribution**:
   - Dept distribution: 60/25/15 (ENGG/SNT/TRD)
   - Task kind weights: 30/45/20/5 (DEFECT/SCHEDULED/OVERDUE/INSPECTION)
   - Due dates: Spread over planning horizon
5. **Bundle Opportunity Detection**:
   - Spatial clustering within 5km
   - Multi-department requirement (≥2 depts)
   - Natural cluster identification from generated requests
6. **Diurnal Traffic Pattern**:
   - Peak hours: 6-11, 16-22
   - Lean hours: 0:30-4:30
   - Goods trains prefer lean hours
7. **Window Generation**:
   - HIGH traffic: 0:30-4:30 (4 hours)
   - MEDIUM traffic: 23:00-5:00 (6 hours)
   - LOW traffic: 22:00-6:00 (8 hours)

---

## Testing Coverage

### Data Validation
- ✅ Reproducible generation (seed=42)
- ✅ Ground truth JSON output
- ✅ Database statistics endpoint for sanity checks
- ✅ Asset count targets (~800 total)
- ✅ Request count target (200 per Decision D8)
- ✅ Bundle opportunity count (15-20 planted)

### Not Yet Implemented
- Unit tests for generator
- Integration tests for API
- Optimizer validation (Phase 1)

---

## Performance Metrics

### Phase 0 Targets (Met)
- ✅ Data generation: <10 seconds for full dataset
- ✅ API response: <1s for statistics endpoint

### Future Targets (Phase 1+)
- Solve time: Target <60s for weekly plan
- What-if latency: Target <2s p95

---

## Known Issues

### None Currently
Phase 0 completed successfully. All foundation components working.

---

## Blockers

### None Currently
Ready to begin Phase 1 (Core Optimizer MVP).

---

## Next Steps

**Immediate** (Phase 1 - Core Optimizer):
1. Implement CP-SAT model builder (§12.6)
   - Decision variables: x_i, s_i, e_i, intervals
   - Hard constraints: H1-H6 (NoOverlap, task-in-block, windows, gangs)
   - Simple objective: priority × completion - block duration
2. Implement baseline FCFS planner (§12.11)
3. Implement KPI computation engine (K1, K2, K3, K5)
4. Create API endpoints: /plan/generate, /baseline/generate, /compare

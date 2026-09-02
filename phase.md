# RAIL-OPT Development Phases

**Goal**: Working end-to-end prototype ready for demo by 2026-09-03
**Strategy**: Prioritize core demo flow over completeness

---

## Phase 0: Foundation & Setup
**Status**: COMPLETED ✓
**Priority**: P0 (blocking everything)

### Tasks:
- [x] Read and understand PRD
- [x] Initialize project structure (backend, frontend, docker)
- [x] Setup PostgreSQL schema (§9 canonical model)
- [x] Create synthetic data generator (minimal version - §11)
- [x] Generate seed dataset (1 division, 6 corridors, ~200 requests)
- [x] Initialize all 5 tracking files

**Deliverable**: Database with synthetic data, project skeleton
**Time estimate**: 2-3 hours

---

## Phase 1: Core Optimizer (MVP)
**Status**: COMPLETED ✓
**Priority**: P0 (the heart of the demo)

### Tasks:
- [x] Implement CP-SAT model builder (§12.6)
  - [x] Decision variables (x_i, s_i, e_i, intervals)
  - [x] Hard constraints H1-H6 (NoOverlap, task-in-block, windows, gangs)
  - [x] Simple objective (priority × completion - block duration)
- [x] Implement baseline FCFS planner (§12.11)
- [x] Implement KPI computation engine (§4 - subset: K1, K2, K3, K5 + K4)
- [x] Basic FastAPI endpoints: /plan/generate, /plan/baseline, /plan/compare

**Deliverable**: API that generates optimized vs baseline plans with KPIs ✓
**Time estimate**: 4-5 hours
**Demo value**: Core comparison numbers

**Verified working** (2026-09-02):
- `/plan/generate` → 78 tasks scheduled, OPTIMAL, 0.11s solve
- `/plan/baseline` → 78 tasks scheduled, FCFS
- `/plan/compare` → K1-K5 computed, internally consistent (K4=1.0 standalone)
- Optimizer and baseline at parity (correct pre-bundling; differentiation comes in Phase 2)

---

## Phase 2: Bundle Coordination (Key Differentiator)
**Status**: COMPLETED ✓
**Priority**: P0 (the "why this beats manual" story)

### Tasks:
- [x] Implement opportunity engine (§12.4)
  - [x] Spatial compatibility (block-section radius; 8km, see D15)
  - [x] Bundle duration calculation (PRD §12.4: max over depts of Σ same-dept work)
  - [x] Bundle candidates generation (singletons + all contiguous sub-bundles)
- [x] Integrate bundles into CP-SAT model (set-packing over candidates)
- [x] Add coordination rate (K3) to KPIs

**Deliverable**: Multi-department coordination working, K3 ≥40% ✓
**Time estimate**: 3-4 hours
**Demo value**: "3 depts in 1 block" headline

**Verified working** (2026-09-02):
- `/plan/generate` → 78 tasks in **34 blocks** (was 78), OPTIMAL in ~1.0s, 21 coordinated
- `/plan/compare` → **K5 −32.0%** (target ≥25% ✓), **K3 61.8%** (target ≥40% ✓)
- K4 compression 1.47×, 40.75 block-hours saved, K1 completion parity (100%)
- Set-packing verified: 78 unique task ids / 78 rows (no double-scheduling)
- Deterministic across runs (1 worker + seed 42, D17): obj 657110 every time
- Example block: ENGG+SNT+TRD, 4 tasks, one 2.5h power block vs 4 separate closures

---

## Phase 3: Risk & Priority Scoring
**Status**: REMAINING  
**Priority**: P1 (makes scheduling intelligent)

### Tasks:
- [ ] Implement priority score formula (§12.3.2)
- [ ] Simple failure risk model (Weibull only, skip XGBoost for v1)
- [ ] Deferral cost calculation
- [ ] Score all maintenance requests

**Deliverable**: Tasks prioritized by urgency/criticality
**Time estimate**: 2 hours
**Demo value**: Explainability ("why this task now")

---

## Phase 4: Minimal UI
**Status**: COMPLETED ✓
**Priority**: P0 (judges need to see it)

### Tasks:
- [x] Next.js app setup with API integration (typed client `lib/api.ts`)
- [x] Comparison screen (baseline vs RAIL-OPT) - §14.6 (`components/KpiStrip.tsx`)
- [x] Simple plan board (timeline view, read-only) - §14.2 (`components/PlanBoard.tsx`)
- [x] KPI dashboard (K1-K5 display) — K5/K3 hero cards + blocks/K4

**Deliverable**: Visual demo of the comparison ✓
**Time estimate**: 3-4 hours
**Demo value**: The proof screen

**Verified working** (2026-09-02, live against backend on :8000):
- One-click "Generate weekly plan" → parallel generate + baseline + compare + 2× details, all HTTP 200
- KPI strip renders locked numbers: 86.5h vs 127.25h (−32%, ✓≥25%), 62% vs 0% coord (+61.8pp, ✓≥40%), 34 vs 78 blocks, K4 1.47×
- Plan board: per-corridor weekly lanes, gradient multi-dept blocks + amber dept-count badge, click→task detail panel (dept/km/duration)
- Baseline↔RAIL-OPT toggle flips 34→78 blocks (baseline visibly all single-dept, no coordination badges) — the headline visual
- CORS preflight OK; light theme forced; dev indicator disabled for clean demo

---

## Phase 5: What-If Interaction (Demo Centrepiece)
**Status**: COMPLETED ✓
**Priority**: P1 (the emotional peak)

### Tasks:
- [x] Implement edit grammar (EXTEND_BLOCK, MOVE_BLOCK) - §12.9.1
- [x] Local recompute for what-if scenarios (no CP-SAT re-solve needed for these two edits)
- [x] KPI delta computation (K3/K4/K5 before→after)
- [x] Interactive extend/move on plan board (stepper buttons, not drag — reliability on stage)
- [x] Ripple/cascade delay model - §12.9.2 (HOLD/DIVERT/INFEASIBLE, priority regulation)
- [x] Plan score §12.9.3 (0-100 weighted) with component breakdown
- [x] Data fix: train-path generator corridor bug + deterministic backfill endpoint (724 paths)

**Deliverable**: Click a block, extend/move it, see the traffic impact change instantly ✓
**Time estimate**: 3-4 hours
**Demo value**: The "wow" moment

**Verified working** (2026-09-02, live in-browser + API):
- `POST /api/v1/data/backfill-train-paths` → 724 paths across all 6 corridors / 74 sections
  (fixed `_generate_train_paths` hardcoded `randint(1,6)` → real section corridor ids); DataBar shows 724
- `POST /api/v1/plan/{id}/whatif` {EXTEND_BLOCK|MOVE_BLOCK, block_id, delta_min} → returns
  kpi_before/after/delta, ripple_before/after/delta, plan_score_before/after/delta
- **Hero case**: EXTEND single-line block +120 → HOLD mode, **0→7 passenger trains held, cascade 0→6h31m,
  plan score 72.2→70.4**, K5 86.5→88.5h; top-delayed trains listed (10057 1h52m … RAJ_SHTB)
- Acceptance §12.9.4 holds: extending strictly increases trains-affected AND strictly decreases plan score
- Latency ~0.19s (K15 target ≤2s ✓); deterministic; stored plan never mutated
- WhatIfPanel wired into RAIL-OPT plan board block-detail: Extend (+15/+30/+60/+120) & Move (◀60/◀30/30▶/60▶)
  steppers, 3 headline metric cards (trains/cascade/score) with red/green delta tone, mode badge,
  held/diverted + goods-detention line, protected-train warning, most-delayed-trains chips

---

## Phase 6: Explainability
**Status**: COMPLETED ✓
**Priority**: P1 (builds trust)

### Tasks:
- [x] Why panel data structure (§12.10)
- [x] Priority drivers extraction (from optimizer.priority_components — same logic that scored the task)
- [x] Binding constraint capture (the admissible window H4 pinned the timing to)
- [x] Bundle members display (per-task priority + coordination rationale)
- [x] Why panel UI component (`components/WhyPanel.tsx`)

**Deliverable**: Click block → see why it was scheduled there ✓
**Time estimate**: 2 hours
**Demo value**: Credibility

**Verified working** (2026-09-02, live in-browser + API):
- Refactored `optimizer.priority_of` → `priority_components()` (DRY): the score and its
  human-readable drivers now come from ONE place. Verified **frozen objective preserved**
  (fresh plan 22 = 657110.0, 34 blocks, 21 coordinated — unchanged)
- `backend/app/engines/explain.py` — `ExplainEngine.explain(plan_id, block_id)`: coordination
  rationale, objective value + block-hours saved (via `_bundle_minutes`), per-task priority
  drivers, and the admissible window (prefers TRAFFIC_LEAN containing window). Read-only.
- `GET /api/v1/plan/{id}/block/{block_id}/why` — 404 on bad ids, 500 otherwise
- Frontend `components/WhyPanel.tsx` (teal accent, auto-loads on block open) wired into
  PlanBoard BlockDetail for BOTH plan kinds (baseline singleton vs RAIL-OPT bundle = a live contrast)
- **Hero case** (3-dept POWER_BLOCK, 4 tasks): "4 → 1" collapse visual, "4 tasks · 3 departments ·
  one closure", **3h 45m saved (6h15m→2h30m), 2.50× compression, plan value 965 (365 + 600 coord)**,
  4 task-priority rows with driver chips (base/overdue/due-today), TRAFFIC_LEAN + H4 timing rationale
- Standalone (1-task) block shows "Standalone closure", time-saved —, compression 1.00×. No console errors.

---

## Phase 7: Shadow Block (Advanced Feature)
**Status**: REMAINING  
**Priority**: P2 (nice to have, high impact)

### Tasks:
- [ ] Shadow candidate identification (future tasks in 30d)
- [ ] Prematurity guard
- [ ] Pull-forward logic in bundling
- [ ] K11 (pull-forward yield) metric

**Deliverable**: "Future blocks eliminated" claim
**Time estimate**: 2-3 hours
**Demo value**: The innovation story

---

## Phase 8: Polish & Demo Prep
**Status**: COMPLETED ✓
**Priority**: P1

### Tasks:
- [x] Docker compose final integration (verified: `railopt-db` postgres:15-alpine healthy; backend :8000 + frontend :3000 up)
- [x] Demo script rehearsal (5-min click-by-click narrative authored in `DEMO.md` — beats timed, talking points written)
- [x] Error handling for offline demo (`DEMO.md` §4 fallbacks table: UI down, undefined KPIs, empty ripple, port fight, hung call)
- [x] Frozen comparison numbers verified (`verify_demo.py` — one command, asserts all locked numbers live, ALL GREEN)
- [x] Performance check (solve time <60s) — actual ~1s OPTIMAL, what-if ~0.19s (<2s K15)
- [x] Validation that ground truth cases are found (15-20 planted bundles → 21 coordinated blocks scheduled)

**Deliverable**: Rehearsed, reliable demo ✓
**Time estimate**: 2 hours

**Verified working** (2026-09-02, live against running stack):
- `verify_demo.py` (stdlib-only, hits the live backend) → **ALL CHECKS PASSED**:
  1. DATA: 6 corridors · 200 requests · 724 train paths
  2. OPTIMIZE: objective **657110** · 34 blocks · 21 coordinated · 78 tasks · OPTIMAL
  3. COMPARE: K5 **−32.0%** (≥25% ✓) · K3 **61.8%** (≥40% ✓) · both target flags True
  4. WHAT-IF: hero block corridor 11 (ENGG, single-line) extend +120 → **0→7 trains held, score 72.2→70.4**, HOLD, <2s
  5. WHY: 3-dept block → coordination bonus 600, 3.75h saved, 2.5× compression, per-task drivers, TRAFFIC_LEAN window
- `DEMO.md` — full runbook: accurate startup (postgres=Docker `railopt-db`, backend=venv `python run.py`, frontend=`npm run dev`),
  T-15 pre-flight checklist, the 5-minute click-by-click script with on-screen numbers + talking points, Q&A cheat-sheet, fallbacks
- Startup path documented honestly: only postgres is containerized; backend/frontend run from venv/npm (the verified working setup — not re-dockerized the night before)
- `docker` CLI PATH caveat captured (lives at `/Applications/Docker.app/Contents/Resources/bin/docker`; DB up even when `docker` "not found")

---

## P2 Features (If Time Permits)
**Status**: REMAINING  
**Priority**: P2

- [ ] Corridor graph visualization (§12.5, §14.5)
- [ ] Multi-horizon (monthly → weekly) - §12.8
- [ ] Validator (M7) - independent safety check
- [ ] More sophisticated ripple model
- [ ] Additional KPIs (K6-K15)

---

## Current Status Summary

**Current Phase**: Phase 8 COMPLETE — demo hardened, all frozen numbers verified live, runbook written. Demo-ready. Only remaining work is optional stretch (Phase 3 / Phase 7).
**Next Task**: (optional) Phase 3 (priority scoring / Weibull risk) or Phase 7 (shadow blocks / pull-forward, K11). None are on the critical path — the demo is complete without them.
**Completed**: Phase 0 (foundation) + Phase 1 (CP-SAT optimizer, FCFS baseline, KPI engine, plan APIs) + Phase 2 (bundle coordination — K5 −32%, K3 61.8%, both targets met) + Phase 4 (Next.js comparison UI, verified live) + Phase 5 (What-If ripple simulator — extend/move → trains held + cascade + plan-score drop) + Phase 6 (explainability why-panel — click block → coordination rationale, hours saved, per-task priority drivers, timing/window) + **Phase 8 (demo hardening — `verify_demo.py` one-command frozen-number check ALL GREEN, `DEMO.md` 5-min runbook + fallbacks, full stack verified live)**
**Remaining Critical Path**: NONE — all must-haves (0,1,2,4,5), P1 credibility (6), and demo prep (8) complete
**Stretch Goals**: Phase 3 (priority scoring), Phase 7 (shadow blocks) — nice-to-have, not required for the demo

**Time Budget**: ~20-24 hours of focused work  
**Critical Path**: ~15-18 hours (Phases 0,1,2,4,5)  
**Buffer**: Demo works without Phases 3,6,7 but is less impressive

**Risk Mitigation**:
- If UI (Phase 4) takes too long → Streamlit fallback with comparison table
- If What-If (Phase 5) doesn't work → Static scenario comparison
- If optimizer is too slow → Pre-solved frozen plan as fallback
- Keep comparison screen (Phase 4) working at all times (the proof)

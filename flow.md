# RAIL-OPT System Flows

**Last Updated**: 2026-09-02  
**Purpose**: Document user flows, data flows, and system interactions

> **Note**: Sections 1, 2, 2b and 2c are marked **AS BUILT** — they match the shipped code (the
> source of truth) through Phase 8 (end-to-end demo flow, what-if ripple simulator, the
> explainability "why" panel, and the demo verification/runbook flow). Sections 3–8 describe the
> *intended* full-system design; of these, bundle discovery (3), CP-SAT solve (4), synthetic data (5)
> and baseline (6) are built, while approve/export (8) and infeasibility relaxation (7) remain
> as-designed targets.

---

## 1. End-to-End Demo Flow (Primary) — AS BUILT (Phase 4)

**Context**: Division planner needs one coordinated weekly maintenance plan.

The Phase 4 UI is a single `'use client'` dashboard (`frontend/app/page.tsx`) that talks
straight to the FastAPI backend. There is **one button**: it generates *both* plans and the
comparison in parallel, then renders everything. No separate "Compare" click.

```
┌─────────────────────────────┐
│ Dashboard loads             │
│ → GET /data/stats           │
│   (6 corridors, 200 reqs,   │
│    210 windows shown in bar)│
└──────┬──────────────────────┘
       │ [Click "Generate weekly plan"]
       ▼
┌─────────────────────────────────────────────┐
│ Parallel fan-out (Promise.all):             │
│   POST /plan/generate  {division:'NDLS',    │
│                         time_limit:60}      │
│   POST /plan/baseline  {division:'NDLS'}    │
│ then, with both plan_ids:                   │
│   GET  /plan/compare?railopt=&baseline=     │
│   GET  /plan/{railopt}/details              │
│   GET  /plan/{baseline}/details             │
└──────┬──────────────────────────────────────┘
       │  (all 5 HTTP 200, ~1–2s wall clock)
       ▼
┌─────────────────────────────────────────────┐
│ Backend per plan: load reqs in horizon →    │
│ opportunity engine (candidates) → CP-SAT    │
│ set-packing solve (1 worker, seed 42) →     │
│ persist Plan/Block/BlockTask → KPI compute  │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ KpiStrip (locked, verified numbers):        │
│   K5 block-hours   127.25h → 86.5h  −32% ✓  │
│   K3 coordination    0%    → 62%  +61.8pp ✓ │
│   Track closures    78     → 34   (−44)     │
│   K4 compression   1.00×   → 1.47×          │
│   "40.75 block-hours saved · completion 100%"│
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ PlanBoard (interactive):                    │
│   per-corridor weekly (7-day) lanes         │
│   solid = single dept, gradient+badge = ≥2  │
│   click block → task detail panel           │
│   [RAIL-OPT 34 blocks ⇄ Baseline 78 blocks] │
│   toggle → the headline 34↔78 flip          │
└─────────────────────────────────────────────┘
```

**Duration**: ~1–2 seconds end to end (both solves are deterministic ~1.0s each).  
**Key Demo Moment**: the KPI strip proves the numbers; the board toggle *shows* why —
34 coordinated blocks vs 78 isolated single-dept closures for the same 78 tasks.

---

## 1b. End-to-End Demo Flow (Original design, for reference)

**Context**: Block Section planner needs weekly maintenance plan for their Division

```
┌─────────────┐
│ User Opens  │
│  Demo UI    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ Command Centre Dashboard    │
│ - Shows 6 corridors         │
│ - 200 open requests         │
│ - "Generate Weekly Plan"    │
└──────┬──────────────────────┘
       │ [Click Generate]
       ▼
┌─────────────────────────────┐
│ POST /plan/generate         │
│ {division, horizon=WEEK,    │
│  period_start=2026-09-02}   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Backend Pipeline:           │
│ 1. Load maintenance_request │
│ 2. Score priorities (M3)    │
│ 3. Find bundles (M4)        │
│ 4. Build CP-SAT model (M6)  │
│ 5. Solve (45s limit)        │
│ 6. Persist plan to DB       │
│ 7. Compute KPIs (M11)       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Plan Board Renders:         │
│ - Timeline with blocks      │
│ - Color by department       │
│ - Bundle markers (★)        │
│ - KPI strip at top          │
└──────┬──────────────────────┘
       │
       ▼ [User clicks "Compare"]
       │
┌─────────────────────────────┐
│ POST /baseline/generate     │
│ (same inputs)               │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Baseline FCFS Planner:      │
│ - Process dept by dept      │
│ - First-available window    │
│ - No coordination           │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ GET /compare                │
│ ?railopt_plan_id=1          │
│ &baseline_plan_id=2         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Comparison Screen Shows:    │
│                             │
│ Metric     Baseline  RAIL   │
│ K1 Hours      48h     35h   │
│ K3 Coord      0%      42%   │
│ K5 Value     2400    2480   │
│                             │
│ ✓ 27% fewer block-hours     │
│ ✓ 42% coordination rate     │
└─────────────────────────────┘
```

**Duration**: ~60 seconds (45s solve + 15s baseline)  
**Key Demo Moment**: Side-by-side numbers proving improvement

---

## 2. What-If Interaction Flow (Demo Centrepiece) — AS BUILT (Phase 5)

**Context**: Planner clicks a RAIL-OPT block and asks "what does it cost to hold this
closure open longer, or shift it into busier hours?"

**What actually shipped** (differs from the original design in three ways):
1. **Stepper buttons, not drag.** `WhatIfPanel` exposes Extend (+15/+30/+60/+120) and
   Move (◀60/◀30/30▶/60▶). Discrete, reliable, rehearsable on stage (D18 extension).
2. **No CP-SAT re-solve.** EXTEND/MOVE only change one block's bounds, so the engine
   recomputes analytically on in-memory copies. ~0.19s round-trip (K15 ≤2s). The stored
   plan is never mutated — the panel is safe to click repeatedly (D19).
3. **Panel is RAIL-OPT-only.** Baseline blocks are read-only (`whatIfEnabled={kind==="railopt"}`).

```
┌─────────────────────────────────────────────┐
│ PlanBoard → click a RAIL-OPT block          │
│ BlockDetail opens → <WhatIfPanel/> mounts    │
│ (useEffect resets result on block_id change) │
└──────┬──────────────────────────────────────┘
       │ [Click a stepper, e.g. "+120"]
       ▼
┌─────────────────────────────────────────────┐
│ simulateWhatIf(planId, op, blockId, delta)  │
│   op = 'EXTEND_BLOCK' | 'MOVE_BLOCK'        │
│ POST /api/v1/plan/{plan_id}/whatif           │
│   { op, block_id, delta_min, label }         │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ WhatIfEngine.simulate(plan_id, edit):       │
│  1. _load_block_views(plan_id) — bounds +   │
│     Σ member est_duration_min per block     │
│  2. _apply_edit on a COPY (extend: push end │
│     by delta; move: shift both, keep dur.)   │
│  3. _kpis before & after (analytic K1/K3/    │
│     K4/K5, slot-rounded to match kpi.py)     │
│  4. _ripple_all before & after               │
│  5. _plan_score before & after (§12.9.3)     │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ RippleEngine.simulate(corridor, km, window):│
│  • eff window = [w_start−headway,            │
│                  w_end+CLEARANCE_MIN]        │
│  • divertible? n_lines≥2 & not CORRIDOR_BLOCK│
│      → DIVERT (meter at headway)             │
│    else needs HOLD → upstream loop?          │
│      yes → HOLD (queue at loop station)      │
│      no  → INFEASIBLE (edit rejected)        │
│  • collect train_paths (day offsets −1/0/+1),│
│    one entry per train (earliest crossing)   │
│  • regulate: protected first, then           │
│    priority_class, GOODS last (absorb        │
│    detention); discharge headway-spaced      │
│  • congestion escalates, capped at D_MAX=6   │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ Response (before → after → delta each):     │
│ {                                            │
│   kpi_before/after/delta,                    │
│   ripple_before/after/delta {                │
│     feasible, mode, trains_affected,         │
│     passenger/goods split, held/diverted,    │
│     cascade delay, protected_train_hit,      │
│     top_trains[] },                          │
│   plan_score_before/after/delta (0–100)      │
│ }                                            │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ ImpactReadout renders:                      │
│  • INFEASIBLE → red card, edit rejected      │
│  • else 3 metric cards: trains affected,     │
│    cascade delay, plan score (red=worse,     │
│    green=better via deltaTone)               │
│  • ModeBadge HOLD/DIVERT/CORRIDOR_BLOCK      │
│  • held / diverted / goods-detention line    │
│  • protected-train warning (if hit)          │
│  • most-delayed-train chips (pax / goods 🛡)  │
└─────────────────────────────────────────────┘
```

**Verified hero case** (2026-09-02, live): extend a single-line corridor-11 block **+120**
→ **HOLD**, 0 → 7 passenger trains held, cascade 0 → 6h31m, plan score 72.2 → 70.4,
K5 86.5 → 88.5h. Acceptance §12.9.4 holds: extending strictly ↑ trains-affected AND
strictly ↓ plan score. The optimizer had placed the block at a **zero-impact** slot, so
*any* edit demonstrably costs trains — "the optimizer found the zero-impact slot."

**Duration**: ~0.19s round-trip (K15 target ≤2s ✓)  
**Key Demo Moment**: one click → the calm plan turns red — 7 trains held, 6½ hours of cascade

---

## 2b. Explainability "Why" Flow (Phase 6) — AS BUILT

**Context**: A judge (or planner) clicks a block and asks "why is this here — why these
tasks, why this value, why this time?" The answer is the optimizer's own computation, not
a generated narrative (D21).

```
┌─────────────────────────────────────────────┐
│ PlanBoard → click any block (either plan)   │
│ BlockDetail opens → <WhyPanel/> auto-loads   │
│ (useEffect keyed on plan+block, cancel-safe) │
└──────┬──────────────────────────────────────┘
       │ GET /api/v1/plan/{plan_id}/block/{block_id}/why
       ▼
┌─────────────────────────────────────────────┐
│ ExplainEngine.explain(plan_id, block_id):   │
│  • load block + its tasks                    │
│  • coordination: n_tasks/n_depts, km_span,   │
│    "N tasks bundled into ONE closure"        │
│  • value: Σ priority_of + n_extra×COORD_BONUS│
│    standalone Σ_bundle_minutes vs bundled →  │
│    hours saved + compression                 │
│  • per task: priority_components() drivers   │
│    (base / severity / overdue / due-soon)    │
│  • window: containing admissible window (H4),│
│    prefer TRAFFIC_LEAN + block-type match    │
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ WhyPanel (teal) renders 4 cards:            │
│  1. Coordination "N → 1" collapse + rationale│
│  2. Time saved · compression · plan value    │
│  3. Task priorities w/ driver chips (+50 …)  │
│  4. Timing: window-kind badge + H4 rationale │
└─────────────────────────────────────────────┘
```

**Every number is the computation itself** — coordination bonus = the objective's
`n_extra_depts × COORD_BONUS_OBJ`, hours saved = the `_bundle_minutes` duration model,
priority drivers = the exact terms `priority_of` summed. Refactoring `priority_of` →
`priority_components` kept the score and its explanation in one place (verified the sum is
bit-identical, so the locked objective 657110 is unchanged).

**Verified hero** (2026-09-02, live): a 3-dept POWER_BLOCK (4 tasks) shows "4 → 1", **3h 45m
saved (6h15m → 2h30m), 2.50× compression, plan value 965 (365 task + 600 coordination)**, three
OVERDUE tasks @100 + one SCHEDULED @65, placed in a TRAFFIC_LEAN window.

**Key Demo Moment**: the numbers stop being a claim — you can see exactly what drove each one.

---

## 2c. Demo Verification & Runbook Flow (Phase 8) — AS BUILT

**Context**: The presenter needs to *prove* the stage is safe before speaking, and follow a fixed
choreography during the 5 minutes. Two artifacts at repo root cover this: `verify_demo.py` (the
machine gate) and `DEMO.md` (the human runbook).

**Pre-flight gate** — one command, stdlib-only, hits the live backend:

```
python3 verify_demo.py
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. DATA      GET /data/stats        → 6 / 200 / 724          │
│ 2. OPTIMIZE  POST /plan/generate    → obj 657110, 34, 21, 78 │
│ 3. COMPARE   POST /plan/baseline                             │
│              GET  /plan/compare     → K5 −32%, K3 61.8%, ✓✓  │
│ 4. WHAT-IF   scan blocks; first +120-extend that adds trains │
│              POST /plan/{id}/whatif → trains↑ AND score↓     │
│ 5. WHY       GET  /plan/{id}/block/{bid}/why → coord/saved/  │
│              drivers/window                                  │
└──────┬──────────────────────────────────────────────────────┘
       ▼
  ALL CHECKS PASSED  (exit 0)   |   N FAILED — do not demo (exit 1)
```

Each section asserts against the frozen numbers; the what-if check asserts the **mechanic**
(strict monotonic ↑trains / ↓plan-score per §12.9.4), not a brittle exact count. Green = safe.

**On-stage choreography** (`DEMO.md`, mapped to the flows above):

```
Beat 0  Problem framing (no clicks)
Beat 1  Generate weekly plan        → Flow 1  (78→34, −32%, 62%)
Beat 2  Board + RAIL-OPT⇄Baseline   → Flow 1  (34 ⇄ 78 blocks)
Beat 3  Click hero block → WHY      → Flow 2b (4→1, 3h45m, 2.5×, drivers)
Beat 4  Extend a single-line block  → Flow 2  (7 held, 72.2→70.4, HOLD)
Close   Targets 25%/40% → hit 32%/62%
```

**Runbook also carries**: accurate startup (postgres=Docker `railopt-db`, backend=venv, frontend=npm),
a Q&A cheat-sheet of every frozen number, and a §4 fallbacks table (UI down → narrate from
`verify_demo.py`; empty ripple → backfill train paths; :5432 port fight → stop Homebrew postgres).

**Key Demo Moment**: before a word is spoken, one command has already proven every number on stage.

---

## 3. Bundle Discovery Flow (Internal)

**Context**: Backend preparing inputs for optimizer

```
┌─────────────────────────────┐
│ Maintenance Requests:       │
│ R1: ENGG, KM 245.2, 30min   │
│ R2: SNT,  KM 247.0, 45min   │
│ R3: TRD,  KM 246.5, 20min   │
│ R4: ENGG, KM 252.0, 60min   │
│ (all corridor C1, same week)│
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Opportunity Engine (M4):    │
│ 1. Group by corridor        │
│ 2. Sort by km_from          │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Spatial Clustering:         │
│ - R1, R2, R3 within 5km     │
│   → bundle candidate B1     │
│ - R4 standalone (7km gap)   │
│   → bundle candidate B2     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Compatibility Check:        │
│ B1: R1+R2+R3                │
│ - Different depts ✓         │
│ - Block types compatible ✓  │
│ - Same corridor ✓           │
│ - Within 5km ✓              │
│ - No mutex conflicts ✓      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Bundle Duration Calc:       │
│ B1 = T_protect + max(tasks) │
│       + T_release            │
│    = 15 + 45 + 10           │
│    = 70 minutes             │
│                             │
│ vs 3 standalone:            │
│    = 3 × (15+task+10)       │
│    = 105 min                │
│                             │
│ Compression: 105/70 = 1.5× │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Bundle Value:               │
│ value_B1 = Σ priorities     │
│          = P1 + P2 + P3     │
│          = 75 + 82 + 68     │
│          = 225              │
│                             │
│ + coordination_bonus        │
│   = 0.8 × (3-1) × 95        │
│   = 152                     │
│                             │
│ Total: 377 value points     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Output to Optimizer:        │
│ [                           │
│   BundleCandidate(          │
│     id='B1',                │
│     tasks=[R1,R2,R3],       │
│     duration_min=70,        │
│     value=377,              │
│     depts=[ENGG,SNT,TRD],   │
│     km_span=(245.2, 247.0)  │
│   ),                        │
│   BundleCandidate(          │
│     id='B2',                │
│     tasks=[R4], ...         │
│   )                         │
│ ]                           │
└─────────────────────────────┘
```

**Output**: Bundle candidates for CP-SAT to schedule

---

## 4. CP-SAT Solver Flow (Core Algorithm)

**Context**: Optimizer decides which bundles to open and when

```
┌─────────────────────────────┐
│ Inputs:                     │
│ - Bundle candidates         │
│ - Available windows         │
│ - Train paths               │
│ - Gang resources            │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Model Building:             │
│                             │
│ Decision Variables:         │
│ - b_k ∈ {0,1} (open bundle?)│
│ - S_k, E_k (start/end slot) │
│ - a_ik (task i in bundle k?)│
│ - x_i (task i scheduled?)   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Hard Constraints:           │
│                             │
│ H1: NoOverlap per section   │
│   AddNoOverlap(BLK_k...)    │
│                             │
│ H2: Task inside block       │
│   s_i ≥ S_k, e_i ≤ E_k      │
│   (enforced if a_ik=1)      │
│                             │
│ H3: Block inside window     │
│   S_k ≥ w.start + protect   │
│   E_k ≤ w.end - release     │
│                             │
│ H4: Protected trains        │
│   Never overlap             │
│                             │
│ H6: Gang capacity           │
│   AddCumulative(gangs)      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Objective (Maximize):       │
│                             │
│ + Σ x_i × priority_i × 100  │
│   (complete high-pri tasks) │
│                             │
│ + Σ b_k × coord_bonus_k     │
│   (reward multi-dept)       │
│                             │
│ - Σ b_k × D_k × traffic_w   │
│   (minimize block time)     │
│                             │
│ - Σ h_t × train_penalty_t   │
│   (avoid disrupting trains) │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ OR-Tools CP-SAT.Solve():    │
│ - max_time: 45 seconds      │
│ - num_workers: 8            │
│ - Warm start from previous  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Solution Status:            │
│ OPTIMAL or FEASIBLE → ✓     │
│ INFEASIBLE → relax H8       │
│ TIMEOUT → use best so far   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Extract Solution:           │
│ - Which bundles opened      │
│ - When scheduled            │
│ - Which tasks assigned      │
│ - Objective value           │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Persist to DB:              │
│ - plan row (status=VALID)   │
│ - planned_block rows        │
│ - planned_block_task rows   │
└─────────────────────────────┘
```

**Duration**: 10-45 seconds depending on problem size  
**Critical**: Must respect all H-rules or plan is invalid

---

## 5. Data Flow (Synthetic Generation)

**Context**: Creating believable test data for demo

```
┌─────────────────────────────┐
│ POST /data/generate         │
│ {seed: 42, weeks: 5,        │
│  division: 'NDLS'}          │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Generator (M12):            │
│ 1. Create corridors         │
│    - 6 corridors            │
│    - ~70km each             │
│    - Traffic class (H/M/L)  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 2. Create stations          │
│    - 8 per corridor         │
│    - Every ~10km            │
│    - Junction flags         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 3. Create assets            │
│    - RAIL, WELD (ENGG)      │
│    - SIGNAL, POINTS (SNT)   │
│    - OHE, FEEDER (TRD)      │
│    - Age, condition, GMT    │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 4. Generate defects         │
│    - P(defect) ∝ age + GMT  │
│    - Severity correlated    │
│    - Overdue based on cycle │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 5. Create maintenance tasks │
│    - 200 total              │
│    - 60% ENGG, 25% SNT,     │
│      15% TRD (realistic)    │
│    - Est duration 15-120min │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 6. Plant opportunities      │
│    - 15-20 bundle cases     │
│      (3 tasks within 5km)   │
│    - Record in ground_truth │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 7. Generate train paths     │
│    - Diurnal curve          │
│    - Peak: 06-11, 16-22     │
│    - Lean: 00:30-04:30      │
│    - 120 passenger + 60 gds │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 8. Create block windows     │
│    - Night windows on HIGH  │
│    - Wider on MEDIUM/LOW    │
│    - Align with lean hours  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 9. Persist to DB            │
│    - All tables populated   │
│    - Consistent FKs         │
│    - Export SQL dump        │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Response:                   │
│ {                           │
│   corridors: 6,             │
│   stations: 48,             │
│   assets: 800,              │
│   requests: 200,            │
│   trains: 180,              │
│   ground_truth_cases: 18,   │
│   seed: 42,                 │
│   sql_dump: 'data/seed.sql' │
│ }                           │
└─────────────────────────────┘
```

**Output**: `data/seed.sql` (can reload for reproducibility)  
**Key**: Consistency rules make data believable

---

## 6. Baseline Planner Flow (Comparison)

**Context**: Simulating today's manual process

```
┌─────────────────────────────┐
│ POST /baseline/generate     │
│ (same inputs as RAIL-OPT)   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ FCFS Planner (M11):         │
│                             │
│ For dept in [ENGG,SNT,TRD]: │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Sort this dept's tasks:   │
│   - By due_on ASC           │
│   - Then severity DESC      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   For each task:            │
│   1. Find first window      │
│      that fits on corridor  │
│   2. Check no overlap       │
│   3. Assign standalone      │
│   4. Mark section occupied  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Result:                     │
│ - Each task = 1 block       │
│ - No coordination           │
│ - First-available greedy    │
│ - Same safety rules (H1-H4) │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Persist baseline plan:      │
│ - planner_kind='BASELINE'   │
│ - One block per task        │
│ - Coordination rate = 0%    │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ KPI Computation (identical  │
│ formula as RAIL-OPT):       │
│ - K1: 48 block-hours        │
│ - K3: 0% coordination       │
│ - K5: 2400 value completed  │
└─────────────────────────────┘
```

**Purpose**: Honest comparison baseline (not a strawman)  
**Key**: Same safety constraints, just no optimization

---

## 7. Error Flow (Infeasibility Handling)

**Context**: No feasible solution exists

```
┌─────────────────────────────┐
│ CP-SAT Solver returns       │
│ Status: INFEASIBLE          │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Relaxation Strategy:        │
│ Try in order:               │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 1. Drop H8 envelope         │
│    (weekly cap from monthly)│
│    Re-solve                 │
└──────┬──────────────────────┘
       │ Still infeasible?
       ▼
┌─────────────────────────────┐
│ 2. Drop H12 one-per-night   │
│    (allow 2 blocks/night)   │
│    Re-solve                 │
└──────┬──────────────────────┘
       │ Still infeasible?
       ▼
┌─────────────────────────────┐
│ 3. Allow task dropping      │
│    (minimize dropped value) │
│    Re-solve                 │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Response:                   │
│ {                           │
│   status: 'FEASIBLE',       │
│   relaxations_used: [       │
│     'H8_ENVELOPE',          │
│     'H12_NIGHT_COUNT'       │
│   ],                        │
│   warning: 'Plan exceeds... │
│ }                           │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ UI shows warning badge:     │
│ ⚠️ Plan required constraint │
│    relaxation (details...)  │
└─────────────────────────────┘
```

**Purpose**: Graceful degradation, never silent failure

---

## 8. Approval & Export Flow

**Context**: Planner satisfied with plan, ready to sanction

```
┌─────────────────────────────┐
│ User reviews plan:          │
│ - Checks KPIs               │
│ - Reads explanations        │
│ - Runs what-if scenarios    │
│ - Satisfied with choice     │
└──────┬──────────────────────┘
       │
       ▼ [Click "Approve"]
       │
┌─────────────────────────────┐
│ POST /plan/{id}/approve     │
│ {                           │
│   approver: 'BS_PLANNER',   │
│   remarks: 'Approved for... │
│ }                           │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Backend checks:             │
│ - status != 'INVALID' ✓     │
│ - Not already approved ✓    │
│ - Mark status='APPROVED'    │
│ - Record timestamp, actor   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Generate BDMS export:       │
│ For each planned_block:     │
│   {                         │
│     REQ_NO: generated,      │
│     SECTION: corridor.code, │
│     FROM_TIME: start_ts,    │
│     TO_TIME: end_ts,        │
│     BLOCK_TYPE: type,       │
│     DEPTS: depts[],         │
│     TASKS: [...],           │
│     STATUS: 'PROPOSED'      │
│   }                         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ GET /plan/{id}/export       │
│ ?format=bdms_json           │
│                             │
│ Downloads: plan_42.json     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ [Outside scope of demo:]    │
│ File imported to BDMS       │
│ → Official sanction process │
└─────────────────────────────┘
```

**Output**: JSON/CSV compatible with BDMS format  
**Key**: RAIL-OPT proposes, BDMS sanctions (we don't replace BDMS)

---

## Decision Points in Flows

### When to use bundling vs standalone?
- **Bundling**: Tasks within 5km, compatible types, same corridor
- **Standalone**: Isolated tasks, incompatible types, no spatial overlap

### When to divert vs hold trains?
- **Divert**: Alternate path exists, detour <30min, track capacity available
- **Hold**: No diversion possible, previous station has loop, detention acceptable
- **Reject block**: Protected train, no diversion, no holding point

### When to defer a task?
- **Schedule now**: High priority, overdue, critical asset
- **Defer**: Low priority, can wait, no good window this week
- **Carry over**: Deferred task's priority rises next iteration

---

## Data Dependencies

```
Optimizer depends on:
  ├─ maintenance_request (must have priorities)
  ├─ bundle_candidates (from opportunity engine)
  ├─ block_window (available time slots)
  └─ train_path (protected paths)

Baseline depends on:
  ├─ maintenance_request (same dataset)
  └─ block_window (same windows)

KPI engine depends on:
  ├─ plan + planned_block + planned_block_task
  └─ Original inputs (for normalization)

What-if depends on:
  ├─ Base plan (to clone)
  └─ Ripple model (for impact)

Ripple model depends on:
  ├─ Candidate block geometry
  └─ train_path (to find affected)
```

---

## Critical Flow (Must Work for Demo)

1. **Generate Plan** → Optimizer → Plan Board (visual)
2. **Generate Baseline** → FCFS → Same visual
3. **Compare** → KPIs side-by-side → Numbers prove improvement
4. **What-If** → Extend block → KPIs update → Impact visible
5. **Approve** → Export → JSON file → Demo complete

**If any flow breaks**: Fall back to pre-generated frozen plans.

---

## Performance Flow

```
Target: 60s for weekly plan

Breakdown:
  10s - Load data (200 tasks, 6 corridors)
   5s - Priority scoring (M3)
  10s - Bundle discovery (M4)
  30s - CP-SAT solve (M6)
   5s - KPI computation (M11)
────────
  60s total
```

**If slower**: Reduce task count or corridor count, not time limit.

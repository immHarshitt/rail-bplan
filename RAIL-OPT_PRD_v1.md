# RAIL-OPT — Product Requirements Document

**AI-Powered Integrated Railway Maintenance & Block Optimization**
Smart India Hackathon | PS: *AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways*

| Field | Value |
|---|---|
| Document | PRD v1.1 |
| Date | 2026-09-02 |
| Owner | Harshit Mishra (project lead) |
| Status | Baselined for build — changes go through §21 change log |
| Source inputs | `RAIL-OPT_SIH_Ideation.md` + 3 team ideation discussions (Shadow Block predictor, What-If ripple simulator, graph corridor intelligence, consolidated simulator narrative) |
| Out of scope | Build schedule, phase plan and task allocation — owned by the team lead, see §17 |

---

## 1. Executive summary

Indian Railways plans fixed-infrastructure maintenance in three silos. Engineering (P.Way), S&T, and Traction
Distribution each raise their own block/disconnection requests through BDMS, each reading their own defect
system — TMS, SMMS, TDMS respectively — while corridor availability lives in COA. Nobody in that loop is
answerable for the one question that actually determines asset availability: *could these three requests have
been served by one closure instead of three?*

RAIL-OPT answers that question. It unifies maintenance demand and traffic supply into one canonical model,
uses ML to score how risky it is to keep deferring each task, uses an opportunity engine to discover which
tasks across departments can legally and physically share a single block, and then hands the actual scheduling
decision to a constraint solver (OR-Tools CP-SAT) whose hard constraints encode the safety and capacity rules
that must never be "learned." On top of that sits a What-If Ripple Simulator where the Block Section planner
drags, extends and relocates blocks and immediately sees the cascade delay on passenger and goods traffic,
plus a Shadow Block Clustering layer that pulls compatible *future* maintenance into today's window so that
tomorrow's block is never requested at all.

**The one line for the slide:** *AI estimates risk and opportunity. A constraint optimizer decides the
schedule. A human approves it. Nothing bypasses the optimizer.*

**What "done" means for this PRD:** a running system that, on a representative synthetic Division, produces a
weekly and monthly block plan that beats a faithful simulation of today's manual process on total block-hours,
cross-department coordination rate, weighted asset availability and train-delay minutes — with every number on
screen and every block explainable.

---

## 2. Problem statement decomposition

The PS text contains four explicit asks and three implicit ones. All seven are tracked as first-class
requirements because judges score against the PS wording, not against our architecture diagram.

| # | Ask (from PS) | Explicit? | Where it is satisfied |
|---|---|---|---|
| A1 | Integrate defects + overdue maintenance from TMS, SMMS, TDMS with corridor block availability from COA, the working timetable, and the goods-train forecast | Explicit | M1 Adapters, M2 Canonical model (§9, §10) |
| A2 | Use AI/ML to prioritize and schedule by criticality, urgency and impact on asset availability | Explicit | M3 Risk & Priority Engine (§12.3) |
| A3 | Optimize block scheduling to maximize uptime and coordinate multi-department activity | Explicit | M4 Opportunity Engine + M6 CP-SAT (§12.4, §12.6) |
| A4 | Provide weekly and monthly horizon plans | Explicit | M8 Multi-Horizon Rolling Planner (§12.8) |
| A5 | Replace a manual, decentralised process — i.e. a human workflow must exist, not just an algorithm | Implicit | M9 What-If Simulator + approval/BDMS export (§12.9, §14.4) |
| A6 | Improve safety | Implicit | M7 Safety Validator + risk burn-down KPI (§12.7, §4) |
| A7 | Be trustworthy to a planner who is accountable for the block | Implicit | M10 Explainability + M11 Baseline comparison (§12.10, §12.11) |

### 2.1 Root causes we are attacking

Decentralised request origin means each department optimises locally; no shared spatial index means nobody
sees that a signal job and a track job are 800 m apart; no cost model for deferral means "overdue" is a binary
label rather than a rising risk; and no impact model means a planner extending a block by an hour has no idea
what it costs the train graph. Each of those four gaps maps to exactly one module below, which is why the
architecture looks the way it does.

### 2.2 Explicit non-problems

We are not building a train-graph/timetable generator, not doing rolling-stock or crew planning, not touching
rolling blocks for new construction projects, and not replacing BDMS as the system of record. RAIL-OPT
*proposes* to BDMS; BDMS remains the sanctioning authority.

---

## 3. Goals and non-goals

**G1** — Produce a feasible, safety-validated weekly block plan for a whole Division in under 60 seconds.
**G2** — Beat the manual-process baseline by ≥25% on total block-hours consumed for the same completed
maintenance value, and reach ≥40% cross-department coordination rate (share of blocks serving ≥2 departments).
**G3** — Make every block auditable: priority inputs, binding constraint, bundle members, deferral cost.
**G4** — Give the planner a live what-if loop with ≤2 s recompute so the AI is advisory, never dictatorial.
**G5** — Show pull-forward value: ≥15% of future-horizon tasks absorbed into already-planned blocks.

**Non-goals for v1:** live integration with real railway systems, authentication/RBAC beyond a role switch in
the UI, multi-user concurrency, mobile app, Hindi UI, and any deep-learning component. Each is a defensible
"next phase" answer, not a build item.

---

## 4. Success metrics (exact definitions)

These are the numbers on the comparison screen. They must be computed identically for the baseline planner and
for RAIL-OPT, from the same synthetic dataset, or the comparison is worthless.

| ID | Metric | Formula / definition | v1 target |
|---|---|---|---|
| K1 | Total block-hours | Σ over planned blocks of `(end − start)` in hours | ≥25% below baseline |
| K2 | Weighted asset availability | `1 − Σ_a (downtime_a × crit_a) / Σ_a (H × crit_a)`, H = horizon hours, crit ∈ 1..5 | ≥ +3 pp vs baseline |
| K3 | Coordination rate | blocks with ≥2 distinct departments ÷ total blocks | ≥40% |
| K4 | Bundle compression ratio | Σ standalone durations of bundled tasks ÷ Σ actual bundled block durations | ≥1.8× |
| K5 | Maintenance value completed | `Σ_i x_i × priority_i` (see §12.3) | ≥ baseline, at lower K1 |
| K6 | Overdue backlog burn-down | count(overdue tasks at horizon end) − count(at start) | strictly negative |
| K7 | Risk exposure | `Σ_i P_fail_i(t_horizon_end)` over all open tasks | ≥15% below baseline |
| K8 | Trains affected | count of scheduled train paths intersecting any block, weighted by train class | ≤ baseline |
| K9 | Cascade delay minutes | output of ripple model §12.9.2, passenger and goods reported separately | ≤ baseline |
| K10 | Goods detention hours | Σ holding time applied to freight paths | ≤ baseline |
| K11 | Shadow pull-forward yield | future-horizon tasks absorbed ÷ future-horizon tasks eligible | ≥15% |
| K12 | Future blocks avoided | count of distinct (corridor, week) blocks the pulled-forward tasks would otherwise have needed | reported |
| K13 | Plan stability | share of tasks whose start time moves <30 min between consecutive re-solves | ≥85% |
| K14 | Solve time | CP-SAT wall clock, weekly solve | ≤60 s |
| K15 | What-if latency | edit submitted → KPIs rendered | ≤2 s p95 |

K13 exists because a planner who sees the whole plan reshuffle on every re-run will stop trusting the tool,
even when the new plan is mathematically better. It is a product requirement, not an optimisation nicety.

---

## 5. Personas and user stories

**P1 — Block Section (BS) / Divisional block planner.** Primary user. Accountable for the sanctioned block.
Needs to see a recommendation, understand it, override it, and know the cost of the override.
**P2 — Departmental maintenance in-charge (SSE P.Way / SSE Signal / SSE TRD).** Raises requests, cares that
his overdue tasks get windows and that a bundled block doesn't leave his gang waiting.
**P3 — Divisional operations controller (COA side).** Cares only about train impact and diversion feasibility.
**P4 — Sr. DEN / Divisional officer.** Wants the weekly/monthly picture, backlog trend and audit trail.

| ID | Story | Acceptance |
|---|---|---|
| US1 | As BS planner I generate a weekly plan for my Division in one click | plan appears with per-corridor Gantt, ≤60 s, zero hard-constraint violations |
| US2 | As BS planner I see why a block was placed where it was | Why-panel lists priority drivers, binding constraint, bundle members, deferral cost |
| US3 | As BS planner I drag a block from 2 h to 3 h and see the consequence | KPI delta panel updates ≤2 s with trains affected, cascade delay, goods conflict, utilization, new plan score |
| US4 | As BS planner I compare the AI plan against 2–3 alternative scenarios side by side | scenario compare table with per-KPI winner highlighting |
| US5 | As BS planner I accept, modify or reject and export the sanctioned plan | JSON/CSV BDMS-shaped export + immutable version record |
| US6 | As SSE Signal I see my S&T task ride along with an Engineering block near KM 245 | bundle view shows dept, task, km span, in-block sequence, gang |
| US7 | As controller I check whether affected trains can be diverted | graph panel shows alternate path, detour minutes, capacity headroom |
| US8 | As Sr. DEN I see monthly reserved capacity per corridor and backlog trend | monthly view + burn-down chart |
| US9 | As BS planner an emergency defect arrives at 20:00 and I re-plan only the next 24 h | local re-optimization, pinned blocks unchanged, diff highlighted |
| US10 | As a judge I toggle "manual process" vs "RAIL-OPT" on identical data | comparison screen (§4) renders both |

---

## 6. Scope and requirement register

Priorities: **P0** demo-critical (no demo without it), **P1** strongly differentiating, **P2** stretch.

| ID | Requirement | Module | Pri |
|---|---|---|---|
| FR-01 | Normalise TMS/SMMS/TDMS records into one `maintenance_request` model via per-source adapters | M1 | P0 |
| FR-02 | Ingest corridor block windows from COA/BDMS-shaped feed | M1 | P0 |
| FR-03 | Ingest working timetable paths + goods-train forecast per corridor-hour | M1 | P0 |
| FR-04 | Generate internally consistent synthetic Division dataset with a seed | M12 | P0 |
| FR-05 | Compute per-task priority score with time-rising risk | M3 | P0 |
| FR-06 | Train and serve failure-risk model with monotone constraint on days-since-maintenance | M3 | P1 |
| FR-07 | Discover spatially + temporally compatible cross-department bundles | M4 | P0 |
| FR-08 | Shadow-block pull-forward of future tasks within lookahead L and radius R, with prematurity guard | M4 | P1 |
| FR-09 | Build corridor graph; compute K alternate paths and detour cost under a block | M5 | P1 |
| FR-10 | CP-SAT model with all hard constraints of §12.6.2 and objective of §12.6.3 | M6 | P0 |
| FR-11 | Independent safety validator re-checking solver output | M7 | P0 |
| FR-12 | Monthly capacity reservation + weekly detailed solve, rolling with backlog carry | M8 | P0 |
| FR-13 | Emergency re-optimization with pinned/frozen blocks | M8 | P1 |
| FR-14 | Ripple/cascade delay simulation for any candidate plan | M9 | P0 |
| FR-15 | Interactive what-if edits: extend, move, add/remove task, change window, drop block | M9 | P0 |
| FR-16 | Scenario storage + side-by-side comparison incl. plan score | M9 | P1 |
| FR-17 | Per-block explanation payload | M10 | P0 |
| FR-18 | Baseline (manual-process) planner on identical data | M11 | P0 |
| FR-19 | KPI engine computing all of §4 for any plan | M11 | P0 |
| FR-20 | Dashboard: command centre, plan board, graph map, compare, approval | M13 | P0 |
| FR-21 | Pareto plan generation (min-disruption / max-maintenance / balanced) | M6 | P2 |
| FR-22 | Maintenance-debt heatmap per corridor | M11 | P2 |
| FR-23 | NL query copilot over the existing API (never scheduling directly) | M14 | P2 |

---

## 7. System architecture

```
  TMS        SMMS       TDMS      BDMS/COA     Working TT     Goods forecast
   │           │          │           │            │               │
   └────── M1 Source Adapters (pluggable, one class per source, CSV/JSON now, REST later) ──────┘
                                     │
                       M2 Canonical Data Model — PostgreSQL
        (asset · maintenance_request · corridor · track_section · train_path ·
         block_window · resource_gang · freight_forecast · plan · scenario)
                                     │
        ┌────────────────┬───────────┴────────────┬───────────────────┐
        ▼                ▼                        ▼                   ▼
 M3 Risk & Priority  M4 Opportunity /       M5 Corridor Graph    M12 Synthetic
 (XGBoost + hazard    Shadow-Block Engine   (networkx: nodes,     Data Generator
  curve → priority,   (spatial 5 km ×       edges, K-shortest     (seeded, feeds
  deferral cost)      temporal 30 d →       alternate paths,      everything)
                      bundle candidates)    detour cost)
        └────────────────┴───────────┬────────────┴───────────────────┘
                                     ▼
                     M6 CP-SAT Optimizer (OR-Tools)
        optional intervals · NoOverlap per section · cumulative gangs ·
        protected train windows · bundle reward · churn penalty · deferral cost
                                     │
                                     ▼
                     M7 Safety Validator  (independent re-check; blocks publish on failure)
                                     │
                     M8 Multi-Horizon Rolling Planner
              monthly capacity reservation → weekly detailed solve → daily emergency repair
                                     │
        ┌────────────────┬───────────┴────────────┬───────────────────┐
        ▼                ▼                        ▼                   ▼
 M9 What-If +      M10 Explainability      M11 Baseline planner   M13 Dashboard
 Ripple Simulator  (why / binding          + KPI engine           (React/Next.js)
 (edit → re-solve   constraint / deferral   (manual-process sim)
  locally → KPIs)   impact)
                                     │
                                     ▼
                       Approval → BDMS-shaped export (M13)
```

Two properties of this diagram are load-bearing in the pitch. First, **every arrow into the schedule passes
through M6** — the ML layers produce numbers, never decisions, so any question about safety is answered by
pointing at an explicit constraint. Second, **M7 is downstream of M6 and independent of it**, so a solver bug
cannot publish an unsafe plan; it can only produce an empty plan and an error.

### 7.1 Runtime shape

A single FastAPI process, a Postgres instance, and a Next.js frontend, all in Docker Compose. Solves run
in-process synchronously with a hard time limit (§12.6.5) — no task queue, because a 60 s synchronous request
with a progress stream is acceptable at demo scale and Celery/Redis would be pure ceremony. If solve time ever
exceeds the request budget, the escape hatch is a background thread plus polling on `/solve/{job_id}`, not new
infrastructure.

---

## 8. Core flows

### 8.1 Weekly plan generation (happy path)

1. Planner picks Division + week + horizon `WEEK`, hits **Generate**.
2. M2 loads open requests (status ∈ `OPEN`,`OVERDUE`,`DEFERRED`) plus requests due within `L` days (shadow
   candidates), corridor windows for the week, train paths, freight forecast, gang rosters.
3. M3 scores every request → `priority_score`, `p_fail_curve`, `deferral_cost_per_day`.
4. M4 builds per-corridor compatibility graph → bundle candidates with `bundle_duration`, `bundle_value`,
   `pull_forward_saving`.
5. M5 marks, for each candidate (corridor, km span, window), which trains are divertible and at what detour cost.
6. M6 solves; warm-started from the previous published plan for stability (K13).
7. M7 validates; on violation the plan is stored as `INVALID` with the failing rule and nothing is published.
8. M11 computes KPIs for the plan and for the baseline plan on the same inputs.
9. M10 attaches explanation payloads. Response returns plan + KPIs + explanations.

### 8.2 What-if edit loop

Planner edit (extend / move / add task / remove task / drop block / change gang) → M9 applies the edit as
**additional constraints** on a *cloned* model, not as a free-text mutation → limited re-solve (≤5 s, only the
affected corridor and its coupled corridors are unfixed; everything else is pinned) → ripple model runs →
KPI delta + plan-score delta returned → stored as a `scenario` row so it can be compared and replayed.

The critical design rule: **a manual edit never produces an unvalidated plan.** Edits are constraints, the
solver re-solves, M7 re-validates. If the planner's edit is infeasible, the response says which constraint it
breaks, in words, rather than silently repairing it.

### 8.3 Emergency defect (US9)

New critical defect arrives → M3 scores it → M8 freezes all blocks starting within `freeze_horizon` (default
6 h) and all blocks already sanctioned in BDMS → re-solves the remaining 24–72 h with the new task available →
diff view shows exactly what moved and why.

### 8.4 Monthly → weekly hand-off

Monthly solve works at 1-day granularity and produces, per corridor per week, a **reserved block-minute
envelope** and a soft assignment of heavy tasks to weeks. The weekly solve then treats that envelope as an
upper bound (H8) and is free to place blocks inside it at 15-minute granularity. Unfinished tasks roll into the
next week's candidate pool with their deferral cost now higher, which is what makes the backlog burn down
instead of drifting.

---

## 9. Canonical data model

PostgreSQL 15. No spatial extension: asset and task location is `(corridor_id, km_from, km_to)` as `numeric(8,3)`
chainage, which is exactly the precision the bundling and conflict logic needs. All timestamps `timestamptz`,
all durations in **minutes** as integers (CP-SAT needs integers; this also fixes the granularity question once).

```sql
CREATE TYPE dept       AS ENUM ('ENGG','SNT','TRD');
CREATE TYPE src_system AS ENUM ('TMS','SMMS','TDMS','BDMS','COA','TT','FREIGHT','SYNTH');
CREATE TYPE block_type AS ENUM ('TRAFFIC_BLOCK','POWER_BLOCK','DISCONNECTION','CORRIDOR_BLOCK');
CREATE TYPE req_status AS ENUM ('OPEN','OVERDUE','PLANNED','SANCTIONED','DONE','DEFERRED','CANCELLED');
CREATE TYPE horizon    AS ENUM ('MONTH','WEEK','DAY');

CREATE TABLE corridor (
  id            serial PRIMARY KEY,
  code          text UNIQUE NOT NULL,           -- e.g. 'NDLS-GZB-UP'
  name          text NOT NULL,
  division      text NOT NULL,
  km_start      numeric(8,3) NOT NULL,
  km_end        numeric(8,3) NOT NULL,
  line_type     text NOT NULL CHECK (line_type IN ('SINGLE','DOUBLE','MULTI')),
  n_lines       int  NOT NULL DEFAULT 2,
  electrified   bool NOT NULL DEFAULT true,
  max_speed_kmph int NOT NULL DEFAULT 110,
  traffic_class text NOT NULL CHECK (traffic_class IN ('HIGH','MEDIUM','LOW'))
);

CREATE TABLE station (
  code       text PRIMARY KEY,
  name       text NOT NULL,
  corridor_id int REFERENCES corridor(id),
  km         numeric(8,3) NOT NULL,
  is_junction bool DEFAULT false,
  n_platforms int DEFAULT 2,
  has_loop    bool DEFAULT true             -- can a goods train be held here?
);

CREATE TABLE track_section (               -- graph edge + conflict unit
  id          serial PRIMARY KEY,
  corridor_id int REFERENCES corridor(id),
  from_stn    text REFERENCES station(code),
  to_stn      text REFERENCES station(code),
  line_no     int NOT NULL DEFAULT 1,
  km_start    numeric(8,3) NOT NULL,
  km_end      numeric(8,3) NOT NULL,
  run_time_min int NOT NULL,               -- nominal sectional running time
  headway_min  int NOT NULL DEFAULT 5,
  bidirectional bool DEFAULT false
);
```

```sql
CREATE TABLE asset (
  id           serial PRIMARY KEY,
  source_system src_system NOT NULL,
  source_id    text NOT NULL,               -- native key in TMS/SMMS/TDMS
  dept         dept NOT NULL,
  asset_type   text NOT NULL,               -- RAIL, WELD, TURNOUT, LC_GATE, SIGNAL, POINT_MACHINE,
                                            -- TRACK_CIRCUIT, AXLE_COUNTER, IPS, OHE_SPAN, INSULATOR,
                                            -- ISOLATOR, FEEDER, NEUTRAL_SECTION ...
  corridor_id  int REFERENCES corridor(id),
  km_from      numeric(8,3) NOT NULL,
  km_to        numeric(8,3) NOT NULL,
  line_no      int,
  install_date date,
  last_overhaul date,
  criticality  int NOT NULL CHECK (criticality BETWEEN 1 AND 5),
  condition_index numeric(4,3),             -- 0..1, 1 = as-new
  gmt          numeric(8,2),                -- gross million tonnes (ENGG relevance)
  UNIQUE (source_system, source_id)
);

CREATE TABLE resource_gang (
  id          serial PRIMARY KEY,
  dept        dept NOT NULL,
  code        text UNIQUE NOT NULL,
  depot_stn   text REFERENCES station(code),
  strength    int NOT NULL,
  corridor_scope int[] NOT NULL,            -- corridor ids this gang can serve
  shift_start_min int NOT NULL DEFAULT 0,   -- minutes from midnight
  shift_end_min   int NOT NULL DEFAULT 1440,
  travel_buffer_min int NOT NULL DEFAULT 30
);

CREATE TABLE maintenance_request (
  id            serial PRIMARY KEY,
  source_system src_system NOT NULL,
  source_id     text NOT NULL,
  dept          dept NOT NULL,
  asset_id      int REFERENCES asset(id),
  corridor_id   int REFERENCES corridor(id),
  km_from       numeric(8,3) NOT NULL,
  km_to         numeric(8,3) NOT NULL,
  task_code     text NOT NULL,              -- e.g. 'TAMPING','USFD_WELD','SIG_GEAR_OVH','OHE_TENSION'
  task_kind     text NOT NULL CHECK (task_kind IN ('DEFECT','SCHEDULED','OVERDUE','INSPECTION')),
  description   text,
  defect_severity int CHECK (defect_severity BETWEEN 0 AND 5),  -- 0 = none (scheduled task)
  raised_on     date,
  due_on        date NOT NULL,
  periodicity_days int,                     -- NULL for defects
  last_done_on  date,
  est_duration_min int NOT NULL,
  min_duration_min int,                     -- if the task can be split/compressed
  required_block  block_type NOT NULL,
  needs_power_block bool DEFAULT false,
  needs_disconnection bool DEFAULT false,
  gang_dept       dept,
  gang_size_req   int DEFAULT 1,
  night_only      bool DEFAULT false,
  status        req_status NOT NULL DEFAULT 'OPEN',
  priority_score numeric(8,4),
  p_fail_30d     numeric(6,5),
  deferral_cost_per_day numeric(8,4),
  UNIQUE (source_system, source_id)
);
```

```sql
CREATE TABLE train (
  id            serial PRIMARY KEY,
  number        text UNIQUE NOT NULL,
  name          text,
  train_class   text NOT NULL CHECK (train_class IN ('RAJ_SHTB','MAIL_EXP','PASS_MEMU','SUBURBAN','GOODS','ENGG_SPL')),
  priority_class int NOT NULL,              -- 1 = highest; drives regulation order in ripple model
  is_protected  bool NOT NULL DEFAULT false -- may never be delayed by a planned block
);

CREATE TABLE train_path (                   -- timetable occupancy, one row per section traversal
  id          bigserial PRIMARY KEY,
  train_id    int REFERENCES train(id),
  section_id  int REFERENCES track_section(id),
  entry_min   int NOT NULL,                 -- minutes from midnight, day-relative
  exit_min    int NOT NULL,
  dow_mask    int NOT NULL DEFAULT 127,     -- bitmask Mon..Sun
  slack_min   int NOT NULL DEFAULT 0        -- recovery time available downstream
);

CREATE TABLE freight_forecast (
  corridor_id int REFERENCES corridor(id),
  date        date NOT NULL,
  hour        int  NOT NULL CHECK (hour BETWEEN 0 AND 23),
  exp_trains  numeric(5,2) NOT NULL,
  confidence  numeric(4,3) NOT NULL DEFAULT 0.8,
  PRIMARY KEY (corridor_id, date, hour)
);

CREATE TABLE block_window (                 -- admissible windows from COA / corridor policy
  id          serial PRIMARY KEY,
  corridor_id int REFERENCES corridor(id),
  km_start    numeric(8,3), km_end numeric(8,3),
  start_ts    timestamptz NOT NULL,
  end_ts      timestamptz NOT NULL,
  window_kind text NOT NULL CHECK (window_kind IN ('CORRIDOR_POLICY','TRAFFIC_LEAN','MAINT_NOTIFIED')),
  allowed_block_types block_type[] NOT NULL,
  source      src_system NOT NULL DEFAULT 'COA'
);

CREATE TABLE embargo (                      -- festival / VIP / special-traffic bans (H9)
  id serial PRIMARY KEY,
  corridor_id int REFERENCES corridor(id),  -- NULL = division-wide
  start_ts timestamptz NOT NULL,
  end_ts   timestamptz NOT NULL,
  reason   text NOT NULL
);
```

```sql
CREATE TABLE plan (
  id           serial PRIMARY KEY,
  division     text NOT NULL,
  horizon      horizon NOT NULL,
  period_start date NOT NULL,
  period_end   date NOT NULL,
  version      int NOT NULL,
  parent_plan_id int REFERENCES plan(id),    -- for re-solves / scenarios
  planner_kind text NOT NULL CHECK (planner_kind IN ('RAILOPT','BASELINE','SCENARIO')),
  status       text NOT NULL CHECK (status IN ('DRAFT','VALID','INVALID','APPROVED','SUPERSEDED')),
  objective_value numeric(12,4),
  solver_status text, solve_ms int, weights jsonb,
  created_at   timestamptz DEFAULT now(),
  UNIQUE (division, horizon, period_start, planner_kind, version)
);

CREATE TABLE planned_block (
  id          serial PRIMARY KEY,
  plan_id     int REFERENCES plan(id) ON DELETE CASCADE,
  corridor_id int REFERENCES corridor(id),
  km_start    numeric(8,3), km_end numeric(8,3),
  line_no     int,
  start_ts    timestamptz NOT NULL,
  end_ts      timestamptz NOT NULL,
  block_type  block_type NOT NULL,
  bundle_id   text,                          -- shared by tasks planned into one closure
  depts       dept[] NOT NULL,
  is_pinned   bool DEFAULT false,            -- sanctioned / frozen, solver may not move it
  utilization numeric(4,3),                  -- productive task minutes / block minutes
  score       numeric(8,4)
);

CREATE TABLE planned_block_task (
  planned_block_id int REFERENCES planned_block(id) ON DELETE CASCADE,
  request_id  int REFERENCES maintenance_request(id),
  seq         int NOT NULL,                  -- in-block sequencing where tasks are mutex
  start_ts    timestamptz NOT NULL,
  end_ts      timestamptz NOT NULL,
  gang_id     int REFERENCES resource_gang(id),
  is_shadow   bool DEFAULT false,            -- pulled forward from a future horizon
  PRIMARY KEY (planned_block_id, request_id)
);

CREATE TABLE explanation (
  plan_id int REFERENCES plan(id) ON DELETE CASCADE,
  entity_type text NOT NULL,                 -- 'BLOCK' | 'TASK' | 'PLAN'
  entity_id   text NOT NULL,
  payload     jsonb NOT NULL,
  PRIMARY KEY (plan_id, entity_type, entity_id)
);

CREATE TABLE scenario (
  id serial PRIMARY KEY,
  base_plan_id int REFERENCES plan(id),
  result_plan_id int REFERENCES plan(id),
  label text, edits jsonb NOT NULL, kpi jsonb, feasible bool,
  infeasibility_reason text, created_at timestamptz DEFAULT now()
);

CREATE TABLE kpi_snapshot (
  plan_id int PRIMARY KEY REFERENCES plan(id) ON DELETE CASCADE,
  kpi jsonb NOT NULL
);
```

Indexes that matter: `maintenance_request (corridor_id, due_on, status)`, `maintenance_request (corridor_id,
km_from, km_to)` for bundling scans, `train_path (section_id, entry_min)` for conflict lookup, and
`block_window (corridor_id, start_ts)`.

---

## 10. Source adapters (M1)

One abstract base, one subclass per source. Each subclass owns its own field mapping, unit conversion and
severity translation, and nothing downstream ever sees a source-specific field name. This is the part that makes
the "integration" claim in A1 real without pretending we have production access.

```python
class SourceAdapter(ABC):
    source: SrcSystem
    @abstractmethod
    def fetch_assets(self, **kw) -> Iterable[dict]: ...
    @abstractmethod
    def fetch_requests(self, **kw) -> Iterable[dict]: ...
    def normalise_severity(self, raw) -> int: ...      # source scale -> 0..5
    def to_canonical(self, row: dict) -> MaintenanceRequestIn: ...
```

| Source | Owns | Representative native fields | Canonical mapping |
|---|---|---|---|
| TMS (Engineering) | track geometry, USFD/rail flaws, tamping, weld, LC gates, turnouts | `TRACK_ID`, `KM`, `CHAINAGE`, `DEFECT_CODE`, `TGI`, `GMT`, `SCH_DUE_DT` | `asset(dept=ENGG)`, `task_code`, `defect_severity` from defect class, `km_from/km_to` from KM+chainage |
| SMMS (S&T) | signals, point machines, track circuits, axle counters, IPS, relay rooms; disconnection needs | `EQP_ID`, `STN_CODE`, `SCHEDULE_TYPE`, `FAULT_PRIORITY`, `DISCONNECTION_REQD` | `asset(dept=SNT)`, `needs_disconnection`, km derived from station chainage where equipment is station-based |
| TDMS (Traction Distribution) | OHE spans, insulators, isolators, feeders, neutral sections; power-block needs | `OHE_LOC`, `SPAN_NO`, `PTW_TYPE`, `SCH_CODE`, `LAST_ATTN_DT` | `asset(dept=TRD)`, `needs_power_block=true`, `required_block=POWER_BLOCK` |
| BDMS | existing block/disconnection requests and sanctions | `REQ_NO`, `SECTION`, `FROM_TIME`, `TO_TIME`, `STATUS` | pre-existing `planned_block(is_pinned=true)` for sanctioned blocks |
| COA | corridor availability, actual train running | `SECTION`, `CORRIDOR_WINDOW`, `TRAIN_NO`, `SCH/ACT times` | `block_window`, `train_path` |
| Timetable / Freight | working TT paths, goods forecast | standard TT export | `train`, `train_path`, `freight_forecast` |

Adapter contract rules: idempotent upsert on `(source_system, source_id)`; unmappable rows go to a
`ingest_reject` table with a reason instead of being silently dropped; every adapter has a fixture file in
`tests/fixtures/<source>/` so ingestion is testable without the generator.

---

## 11. Synthetic dataset (M12)

The dataset is a deliverable, not a scaffold — internally consistent data is what makes the demo believable,
and independent random columns are what makes judges suspicious.

Scale target: **1 Division, 6 corridors, ~420 route-km, 48 stations, ~3,000 assets, ~600 open maintenance
requests, 180 trains (120 passenger + 60 goods paths), 5 weeks of horizon.** Seeded (`--seed`), regenerable,
committed as a SQL dump so the demo never depends on generation succeeding live.

Consistency rules the generator must obey:

1. Defect probability rises with asset age, GMT and time since last attention — `p ∝ σ(α·age_norm + β·gmt_norm + γ·overdue_norm)`. Severity is then drawn conditional on `p`, so severity correlates with condition rather than floating free.
2. `condition_index` decays monotonically with GMT and jumps back up on `last_overhaul`.
3. Timetable density follows a realistic diurnal curve: passenger peaks 06:00–11:00 and 16:00–22:00, a genuine lean window 00:30–04:30 on HIGH-traffic corridors, wider lean windows on LOW-traffic corridors. Goods forecast is anti-correlated with passenger peaks.
4. Periodic tasks are generated from `periodicity_days` and `last_done_on`, so the overdue population is a consequence of the calendar, not a random flag.
5. At least 40 planted **bundle opportunities**: triplets of ENGG/SNT/TRD tasks within 5 km and compatible windows, so the opportunity engine has something real to find, plus at least 15 planted **shadow candidates** (future tasks 10–30 days out near an already-due task).
6. Two planted "hard" cases for the demo: a HIGH-traffic corridor where only a 2 h night window exists, and a single-line corridor where any block forces either diversion or goods detention.

Every planted case is recorded in `data/ground_truth.json` so tests can assert that the engines actually find them.

---

## 12. Module specifications

### 12.1 M1 Ingestion · 12.2 M2 Canonical store
Covered by §10 and §9. Contract: after ingestion, `POST /ingest/validate` must report zero orphan foreign keys,
zero requests whose km span falls outside their corridor, and zero tasks whose `est_duration_min` exceeds the
longest available window on their corridor (those are flagged `NEEDS_MEGA_BLOCK` rather than silently dropped).

### 12.3 M3 Risk & Priority Engine

**Purpose.** Turn heterogeneous defect/schedule records into two numbers the optimizer can reason about: how
much value there is in doing task *i* now, and how much it costs to defer it another day. Nothing else. This
module never schedules.

**12.3.1 Failure-risk model.** Weibull hazard as the analytical backbone, XGBoost as the learned refinement.

```
p_fail(i, t) = 1 − exp( −( (age_i + t) / η(asset_type, condition) ) ^ β(asset_type) )
```

XGBoost classifier `P(failure within 30 days)` trained on the synthetic failure outcomes, with
`monotone_constraints` forcing the prediction to be non-decreasing in `days_since_last_maintenance`,
`days_overdue` and `gmt`, and non-increasing in `condition_index`. The monotone constraint is a deliberate
credibility feature: it guarantees the model can never claim a task got *safer* by being ignored longer, which
is the first thing a domain expert will try to break.

Features: `asset_type` (one-hot), `criticality`, `condition_index`, `age_days`, `gmt`, `days_since_last_maint`,
`days_overdue`, `periodicity_days`, `defect_severity`, `corridor.traffic_class`, `n_defects_same_asset_180d`,
`km_density_of_open_defects` (open defects within ±2 km — a genuine leading indicator of local degradation).

**12.3.2 Priority score.** Bounded 0–100, deliberately interpretable because it appears in the Why panel:

```
priority_i = 100 × normalise(
      w_c · crit_i/5
    + w_s · sev_i/5
    + w_o · min(days_overdue_i / periodicity_i, 2)/2
    + w_f · p_fail_30d_i
    + w_t · traffic_weight(corridor_i)          # consequence of failure
    + w_p · protected_asset_flag_i )            # e.g. LC gate, points on a through line
defaults: w_c .22  w_s .20  w_o .18  w_f .22  w_t .12  w_p .06
```

**12.3.3 Deferral cost** — the term that makes the optimizer prefer sooner over later without hard due dates:

```
deferral_cost_per_day_i = crit_i × ( p_fail(i, t+1) − p_fail(i, t) ) × consequence_i
consequence_i = traffic_weight(corridor) × (1 + safety_multiplier(task_code))
```

**Outputs.** `priority_score`, `p_fail_30d`, `deferral_cost_per_day` written back to `maintenance_request`, plus
a `risk_curve` array (14 points, one per day) cached for the Why panel's "what if we postpone this" line.
**Acceptance:** monotonicity test passes on 100 synthetic probes; priority score for a severity-5 overdue
critical defect strictly exceeds every routine inspection in the dataset; scoring 600 requests takes <2 s.

---

### 12.4 M4 Opportunity Engine + Shadow Block Clustering  ← primary differentiator

**Purpose.** Find sets of tasks — across departments, including tasks *not yet due* — that can be served by one
closure. This is the module that answers the PS's "poor coordination" complaint, and it is what produces the
headline number: "7 tasks across 3 departments in one 90-minute block instead of 4.5 hours of separate closures."

**12.4.1 Candidate pool.**
`CURRENT` = requests with `due_on ≤ horizon_end` and status in (OPEN, OVERDUE, DEFERRED).
`SHADOW`  = requests with `horizon_end < due_on ≤ horizon_end + L`, `L = 30 days` (configurable).
Shadow tasks are only ever *added* to a block that already exists for a CURRENT task — they never justify a
block on their own. That rule is what keeps the feature honest.

**12.4.2 Compatibility predicate.** Tasks *i*, *j* on the same corridor are bundle-compatible iff:

```
SPATIAL   gap(i,j) = max(0, max(km_from) − min(km_to)) ≤ R        R = 5.0 km (per block type, §22.2)
LINE      same line_no, or block_type ∈ {CORRIDOR_BLOCK, POWER_BLOCK} which affect all lines
BLOCK     block_type_compatible(i,j) per matrix §12.4.3
MUTEX     not in mutual-exclusion set (same km ± 100 m physical conflict, e.g. tamping vs OHE mast work)
RESOURCE  gangs are distinct, or same gang and tasks are serialised
WINDOW    est_duration fits: see 12.4.4
SAFETY    if either needs_power_block, a TRD-authorised task/gang must be present in the bundle
```

**12.4.3 Block-type compatibility matrix** (rows = existing block, cols = task to add):

| | TRAFFIC | POWER | DISCONNECTION |
|---|---|---|---|
| **TRAFFIC_BLOCK** | ✔ parallel | ✔ upgrade block to TRAFFIC+POWER, +15 min isolation overhead | ✔ parallel if S&T staff available |
| **POWER_BLOCK** | ✔ upgrade | ✔ parallel | ✔ parallel |
| **DISCONNECTION** | ✔ upgrade | ✔ upgrade | ✔ parallel, same relay room only |

**12.4.4 Bundle duration model** — this is where naive implementations lose credibility:

```
bundle_duration = T_protect + max over parallel groups( Σ serialised durations ) + T_release
T_protect  = 15 min (traffic protection / caution orders) + 15 min extra if power block (isolation + earthing)
T_release  = 10 min (site clearance, PTW return) + 10 min if power block (de-earthing, charging)
parallel groups = connected components of the *incompatible-simultaneous* graph inside the bundle
```

So bundling three 30-minute parallel tasks yields a 55–85 min block, not 90 — and it beats three standalone
blocks of 55 min each (165 min). The compression ratio K4 comes straight out of this arithmetic.

**12.4.5 Bundle value.**
```
value_k = Σ_i∈CURRENT priority_i
        + φ · Σ_i∈SHADOW ( priority_i(due_on) + avoided_block_cost_i )      φ = 0.7 (pull-forward discount)
        − prematurity_penalty_k
avoided_block_cost_i = expected_standalone_minutes_i × traffic_weight(corridor_i) × λ_time
prematurity_penalty_i = ψ · max(0, 1 − elapsed_fraction_i)   where elapsed_fraction = (today − last_done)/periodicity
```

**Prematurity guard (hard):** a shadow task may only be pulled forward if `elapsed_fraction ≥ 0.6` **and**
`days_early ≤ 30` **and** `task_kind ≠ INSPECTION` (statutory inspections keep their own calendar). Without this
guard the engine would happily burn asset life to look efficient, and a domain judge will ask exactly that.

**12.4.6 Algorithm.**
```
for each corridor c:
    build graph G_c: nodes = candidate tasks, edges = compatible pairs (12.4.2)
    for each maximal clique-ish seed (greedy by priority desc, networkx find_cliques capped at size 12):
        grow bundle while duration ≤ max_window(c) and marginal value > 0
        emit BundleCandidate(tasks, duration, value, depts, km_span, block_type, gangs)
keep top N=40 candidates per corridor by value density (value / duration)
```
Cliques are capped and greedily seeded because exact maximum-weight clique is NP-hard and we only need good
candidates — the CP-SAT stage is what makes the final choice.

**Acceptance:** recovers ≥90% of the 40 planted bundle opportunities and ≥80% of the 15 planted shadow cases from
`ground_truth.json`; produces zero bundles violating the mutex or prematurity rules; runs in <5 s for 600 tasks.

---

### 12.5 M5 Corridor Graph Intelligence

**Model.** `G = (V, E)` in networkx. `V` = stations and junctions (attributes: loop availability, platforms,
whether a goods train can be held there). `E` = `track_section` rows (attributes: `run_time_min`, `headway_min`,
`km_start/km_end`, `line_no`, `bidirectional`, capacity trains/hour). Multi-line corridors are parallel edges.

**Queries the rest of the system needs.**
1. `blocked_edges(corridor, km_start, km_end, line_no)` → the edge set a block takes out of service.
2. `affected_trains(blocked_edges, t_start, t_end)` → train paths whose occupancy intersects, via the
   `train_path (section_id, entry_min)` index.
3. `alternate_paths(origin, destination, blocked_edges, K=3)` → Yen's K-shortest paths on cost
   `run_time + congestion_penalty(edge, hour) + 4 min per intermediate junction (route setting/crossing)`.
4. `diversion_feasible(train, path)` → true iff every edge on the path is electrified when the train needs it,
   permits the train's max speed class, and has residual capacity in the affected hours
   (`capacity − scheduled_occupancy ≥ 1`).
5. `detour_minutes(train)` = `cost(alt_path) − cost(original_path)`.
6. `single_line_flag(corridor)` → if true, a block cannot be worked "on one line"; the ripple model must hold or
   divert rather than assume parallel-line working.

**Why it earns its place.** Without the graph, "trains affected" is the only impact number available, and the
honest answer to "can't you just divert them?" is a shrug. With it, the what-if panel can say *"11 of 14 affected
trains are divertible via the loop line at +18 min average; 3 goods trains must be held at ANDI (loop
available)."* That sentence is the difference between a visualisation and a decision-support tool.

**Scale note.** ~48 nodes, ~120 edges — networkx is comfortably fast enough; a K=3 Yen's query is sub-millisecond
at this size. Precompute and cache alternate paths per (blocked edge set) since block spans repeat across scenarios.

**Acceptance:** on the planted single-line corridor, `alternate_paths` returns no feasible diversion and the
ripple model falls back to holding; on the double-line corridor it returns the parallel line with correct detour
minutes; all six queries covered by unit tests.

### 12.6 M6 CP-SAT Optimizer — the technical core

**12.6.1 Decision variables** (OR-Tools CP-SAT, time discretised to 15-minute slots over the horizon; slot index
`0 … T`, `T = 7 × 96` for a week):

```
x_i        ∈ {0,1}        task i is executed in this horizon
s_i, e_i   ∈ [0, T]       task start / end slot           (IntVar)
itv_i                     OptionalIntervalVar(s_i, d_i, e_i, x_i),  d_i = ceil(est_duration/15)
b_k        ∈ {0,1}        bundle candidate k is opened
S_k, E_k   ∈ [0, T]       block start / end slot for bundle k
BLK_k                     OptionalIntervalVar(S_k, D_k, E_k, b_k)
a_ik       ∈ {0,1}        task i assigned to bundle k          (only for i ∈ candidate k)
w_kw       ∈ {0,1}        bundle k placed in admissible window w
g_ir       ∈ {0,1}        task i served by gang r
h_t        ∈ {0,1}        train path t is impacted (channelled from block intervals)
```

Every task must sit in exactly one opened bundle: `Σ_k a_ik = x_i`. A single-task bundle is legal, so the model
degenerates gracefully to "one block per task" when no coordination is possible — which is exactly what the
baseline does, and is why RAIL-OPT can never be *worse* than the baseline on maintenance value.

**12.6.2 Hard constraints.** These are the safety and capacity rules. They are stated here in one place because
this table *is* the answer to "how do you know your AI plan is safe."

| ID | Constraint | CP-SAT encoding |
|---|---|---|
| H1 | No two blocks overlap in time on the same track section | `AddNoOverlap` over block intervals grouped by section (a bundle occupies every section its km span touches) |
| H2 | Each task lies wholly inside its bundle's block | `s_i ≥ S_k`, `e_i ≤ E_k` enforced with `OnlyEnforceIf(a_ik)` |
| H3 | Block lies inside exactly one admissible window, minus protection/release overheads | `Σ_w w_kw = b_k`; `S_k ≥ w.start + t_protect`, `E_k ≤ w.end − t_release` under `OnlyEnforceIf(w_kw)` |
| H4 | Protected trains (`is_protected`) are never impacted | forbid block intervals overlapping those paths' section occupancy outright |
| H5 | Non-protected train impact allowed only if divertible or holdable | if M5 says not divertible and no loop at the previous station, the overlap is forbidden, not penalised |
| H6 | Gang capacity per department per shift | `AddCumulative` over gang intervals, capacity = gang strength; plus travel buffer between consecutive tasks of the same gang |
| H7 | Gang shift and travel window | `s_i ≥ shift_start`, `e_i ≤ shift_end`, `Σ g_ir = x_i`, gang's corridor scope respected |
| H8 | Weekly block-minutes per corridor ≤ monthly reserved envelope | `Σ_k b_k·D_k ≤ cap_c` |
| H9 | No block during an embargo | remove overlapping windows before model build (cheapest correct encoding) |
| H10 | Mutually exclusive tasks never run simultaneously | `AddNoOverlap` within the bundle for mutex pairs (forces in-block sequencing, `seq` in output) |
| H11 | Power block requires TRD authorisation present; disconnection requires S&T staff | implication: `b_k ⇒ Σ_{i∈k, dept=TRD} a_ik ≥ 1` when any member needs a power block |
| H12 | Max one corridor block per corridor per night, and `night_only` tasks only in 00:00–05:00 | domain restriction on `S_k` + count constraint |
| H13 | Min and max block duration per block type | `D_k ∈ [min_dur(type), max_dur(type)]` |
| H14 | Pinned (already sanctioned) blocks are immovable | fixed intervals added to the same NoOverlap groups |

**12.6.3 Objective.** Maximise, with all terms in integer "value points" (multiply by 100 and round — CP-SAT is
integer-only; do this once in a helper, not ad hoc):

```
maximise
    Σ_i  x_i · priority_i · V_task                        # A2: get critical work done
  + Σ_k  b_k · coordination_bonus_k                       # A3: reward multi-dept sharing
  + Σ_i  shadow_i · pull_forward_saving_i                 # future blocks avoided
  − λ_time  · Σ_k b_k · D_k · traffic_weight(c_k, slot)   # A3: minimise closure cost, time-of-day aware
  − λ_train · Σ_t h_t · train_penalty(class_t)            # protect train operations
  − λ_delay · Σ_t h_t · est_delay_min_t                   # from M9 pre-computed per (path, window)
  − λ_defer · Σ_i (1 − x_i) · deferral_cost_i · horizon_days   # A2: urgency without hard deadlines
  − λ_churn · Σ_i churn_i                                  # K13: plan stability vs previous version
  − λ_util  · Σ_k idle_minutes_k                           # discourage padded blocks

coordination_bonus_k = κ · (n_depts_k − 1) · Σ_i∈k d_i     κ = 0.8
churn_i encoded as |s_i − s_i^prev| > 6 slots  →  bool via AddAbsEquality + threshold reification
defaults: V_task 100 · λ_time 1.2 · λ_train 8 · λ_delay 0.5 · λ_defer 3 · λ_churn 5 · λ_util 0.3
traffic_weight: HIGH 1.6 / MEDIUM 1.0 / LOW 0.6, × 1.8 in peak slots, × 0.4 in 00:30–04:30
```

Weights live in `config/weights.yaml`, are stored on the `plan` row, and are exposed in the UI as three presets
(FR-21): *min-disruption* (λ_train ×2, λ_time ×2), *max-maintenance* (V_task ×2, λ_defer ×2), *balanced*.
Three re-solves with different weights is also, conveniently, the whole Pareto feature.

**12.6.4 Warm start & stability.** Add the previous published plan as solution hints (`AddHint`) for `x_i`, `S_k`.
This both speeds up the solve and, together with `λ_churn`, delivers K13.

**12.6.5 Solver settings.** `max_time_in_seconds`: 45 (weekly), 90 (monthly), 5 (what-if repair);
`num_search_workers = 8`; `log_search_progress = True` captured into `plan.solver_stats`. On `INFEASIBLE`, relax in
a fixed documented order — drop H8 envelope, then H12 one-block-per-night, then allow lower-priority tasks to be
dropped — and report which relaxation was needed rather than returning nothing.

**Acceptance:** returns `OPTIMAL` or `FEASIBLE` for the full synthetic Division within 60 s; zero H-rule
violations per M7; on a hand-built 12-task fixture the objective matches a brute-force enumeration exactly.

---

### 12.7 M7 Safety Validator

An independent implementation — deliberately *not* sharing code with the model builder, because a validator that
reuses the buggy helper validates the bug. Reads the persisted plan and re-checks H1–H14 plus three
plan-level rules: every task's gang exists and was free, every block has at least one CURRENT task, and no
shadow task violates the prematurity guard. Output: `ValidationReport{ok, violations[{rule, entity, detail}]}`.
A plan with any violation is stored `INVALID` and refused by the publish endpoint. The validator also runs on
every what-if scenario, so a planner cannot hand-edit their way into an unsafe plan.

### 12.8 M8 Multi-Horizon Rolling Planner (A4)

**Monthly pass.** Granularity 1 day. Simplified model: decide which week each heavy/periodic task lands in, and
reserve per-corridor block-minute envelopes per week. Objective ignores intra-day placement and train delay,
keeping only priority, deferral cost and total closure cost. Output: `plan(horizon=MONTH)` with weekly envelopes
and soft task→week assignment.

**Weekly pass.** Granularity 15 min, full model of §12.6, bounded by the monthly envelope (H8), with the monthly
task→week assignment as a hint rather than a constraint (so a genuinely better week can still win).

**Daily/emergency pass.** Freeze anything starting within 6 h or already sanctioned; re-solve the next 24–72 h.

**Rolling and carry-over.** After each week, tasks with `x_i = 0` return to the pool with their `days_overdue`
increased, which raises both priority and deferral cost — the backlog is therefore self-correcting rather than
permanently starved. Tasks deferred three consecutive weeks are escalated in the UI as `STARVED`, because a
planner needs to know when the optimizer keeps saying no.

**Why not solve the whole month at 15-min granularity:** ~2,880 slots × 600 tasks is a needlessly large model for
a decision that is only committed a week at a time. Reserve-then-refine is both faster and closer to how
Divisional planning actually works.

### 12.9 M9 What-If Ripple Simulator (the demo centrepiece)

**12.9.1 Edit grammar.** Every planner action is a typed edit, validated then compiled into constraints:

| Edit | Payload | Compiles to |
|---|---|---|
| `EXTEND_BLOCK` | block_id, new_end | fix `E_k = new_end`, keep `S_k` |
| `MOVE_BLOCK` | block_id, new_start | fix `S_k`, duration preserved |
| `RESIZE_BLOCK` | block_id, new_start, new_end | fix both |
| `CHANGE_WINDOW` | block_id, window_id | fix `w_kw = 1` |
| `ADD_TASK` | block_id, request_id | fix `a_ik = 1`, `x_i = 1` |
| `REMOVE_TASK` | block_id, request_id | fix `a_ik = 0` |
| `DROP_BLOCK` | block_id | fix `b_k = 0` |
| `PIN_BLOCK` | block_id | mark immovable for subsequent solves |
| `CHANGE_GANG` | request_id, gang_id | fix `g_ir = 1` |
| `INJECT_DEFECT` | full request payload | add task to pool, re-score, re-solve |
| `SET_FREIGHT` | corridor, date, multiplier | scale `freight_forecast`, re-derive traffic weights |
| `REMOVE_GANG` | gang_id, date | zero that gang's capacity |

Everything except the last three is a *local* repair: unfix only the edited corridor plus corridors sharing a
junction with it, pin the rest, 5 s solve budget. That is how K15 (≤2 s p95 for typical single-corridor edits) is met.

**12.9.2 Ripple / cascade delay model.** A deterministic event-propagation simulator — not ML, because we need it
explainable and sub-second. For a candidate block `B = (sections, t_start, t_end)`:

```
1. DIRECT IMPACT
   affected = train paths occupying any blocked section within [t_start − headway, t_end + headway]
   for each affected train τ, in ascending priority_class (highest priority handled first):
       if divertible(τ) per M5:      delay_τ = detour_minutes(τ);  mode = DIVERT
       elif holdable(τ) at previous station with loop:
                                     delay_τ = t_end + clearance − sched_entry_τ;  mode = HOLD
       else:                         mode = INFEASIBLE  → this block violates H5, reject
   clearance = 10 min (block release + line clear + signal restoration)

2. KNOCK-ON PROPAGATION  (per section, in time order)
   for successor train σ following τ on the same section:
       required_entry = actual_exit_τ + headway_min(section)
       delay_σ = max(0, required_entry − sched_entry_σ − slack_min_σ)
       propagate until delay = 0 or depth > D_max (default 6) — timetable slack absorbs the rest
   record knock_on_depth and the absorbing station

3. PRIORITY REGULATION
   if a GOODS path and a MAIL_EXP path both need the same slot, the goods path takes the delay
   goods_detention_hours += delay / 60 for train_class = GOODS

4. AGGREGATE
   trains_affected, passenger_delay_min, goods_delay_min, goods_detention_hours,
   max_single_delay, knock_on_depth, n_diverted, n_held, punctuality_risk =
       Σ over passenger trains of 1[delay > 15 min] / n_passenger_paths
```

Complexity is `O(|affected| × D_max)` — tens of operations, so the whole simulation runs in milliseconds and can
be called inside the optimizer's pre-computation (`est_delay_min_t` in §12.6.3) as well as in the UI.

**12.9.3 Plan score** — the single number the planner watches move (0–100, shown with its component breakdown so
it never looks like a magic number):

```
plan_score = 100 × (
    0.30 · maintenance_value_completed_norm
  + 0.20 · (1 − block_hours_norm)
  + 0.15 · coordination_rate
  + 0.15 · (1 − cascade_delay_norm)
  + 0.10 · weighted_asset_availability_gain_norm
  + 0.10 · block_utilization )
```
Normalisation is against the AI-recommended plan for the same period, so the recommended plan sits near a
reference point and every manual edit reads as a visible ±Δ.

**12.9.4 Alternative scenario generation.** The dashboard never shows only the optimum. On plan generation the
system also emits 2–3 named alternatives — *Min Disruption*, *Max Maintenance*, *Latest Feasible Night Window* —
by re-solving with the preset weights of §12.6.3, and displays them alongside so the BS team can choose rather
than accept. Human-in-the-loop is the workflow, not a disclaimer.

**Acceptance:** injecting the planted single-line block produces HOLD mode with non-zero goods detention;
extending a 2 h block to 4 h on the HIGH-traffic corridor strictly increases trains affected and strictly
decreases plan score; every edit type round-trips through scenario storage and replays identically.

### 12.10 M10 Explainability

For each block and task, a JSON payload rendered as sentences in the Why panel:
`priority_drivers` (top-3 contributing terms of §12.3.2 with their numeric contributions), `binding_constraint`
(which H-rule pinned this block to this window — captured during model build by tagging constraints and checking
which are tight in the solution), `bundle_members` (dept, task, km, duration, shadow flag),
`counterfactual_delay` ("postponing this task by 7 days raises failure risk from 4.1% to 9.8%"),
`window_rationale` ("chosen 01:15–02:45: only lean window on this corridor with no protected train paths"),
`alternatives_rejected` (top-2 rejected windows with the reason and the score they would have scored).
This is nearly free to build because every number already exists upstream — its value is that it converts the
system from "our AI generated this" into something a planner can defend to his own supervisor.

### 12.11 M11 Baseline planner + KPI engine

**Baseline = a faithful simulation of today's process**, and it must be faithful, not a straw man, or the whole
comparison is worthless. Rules: iterate departments independently in a fixed order (ENGG, SNT, TRD); within each
department, sort requests by `due_on` then severity; for each request, take the **first available window** on its
corridor that fits its own duration + overheads; never look at other departments' requests; never bundle; obey
the same hard safety rules H1, H3, H4, H9, H13 (so any advantage RAIL-OPT shows comes from coordination and
optimisation, not from the baseline being allowed to be unsafe).

**KPI engine.** One pure function `compute_kpis(plan_id) -> dict` implementing every formula of §4, used
identically for baseline, RAIL-OPT and every scenario. Persisted to `kpi_snapshot`. Any KPI shown anywhere in the
UI must come from this function — no per-screen recomputation, which is how comparison tables end up
inconsistent and a judge notices.

**Stretch (FR-22) maintenance-debt heatmap:** per corridor per km-bucket,
`debt = Σ (priority_i × days_overdue_i) / km_bucket_length`, rendered as a colour band along the corridor.

---

## 13. API contracts (FastAPI)

All responses `application/json`; errors as `{detail, code, hints[]}`. Base path `/api/v1`.

```
POST /ingest/{source}                 body: {file_id|payload}          → {inserted, updated, rejected[]}
POST /ingest/validate                                                  → {ok, issues[]}
POST /data/generate                   {seed, weeks, division}          → {counts, ground_truth_path}

GET  /corridors                                                        → [Corridor]
GET  /requests?corridor&status&dept&due_before                          → [MaintenanceRequest]
POST /risk/score                      {request_ids?|all:true}           → {scored, sample[]}
GET  /risk/{request_id}/curve                                          → {days[], p_fail[], deferral_cost[]}

POST /opportunity/bundles             {corridor_id?, horizon_end, lookahead_days}
                                      → [{bundle_id, tasks[], depts[], duration_min, value,
                                          shadow_tasks[], compression_ratio}]

POST /plan/generate                   {division, horizon, period_start, weights_preset?, warm_start_plan_id?}
                                      → {plan_id, status, solver, blocks[], kpi, alternatives[]}
GET  /plan/{id}                                                        → full plan + blocks + tasks
GET  /plan/{id}/explain?block_id=                                      → Explanation payload (§12.10)
GET  /plan/{id}/kpi                                                    → §4 metrics
POST /plan/{id}/validate                                               → ValidationReport
POST /plan/{id}/approve               {approver, remarks}              → {status:'APPROVED', export_url}
GET  /plan/{id}/export?format=bdms_json|csv                            → BDMS-shaped request rows

POST /whatif/simulate                 {base_plan_id, edits[Edit], resolve:true|false}
                                      → {scenario_id, feasible, infeasibility_reason?, plan{...},
                                         kpi, kpi_delta, ripple{...}, plan_score, plan_score_delta}
GET  /whatif/scenarios?base_plan_id                                    → [Scenario]
POST /whatif/compare                  {scenario_ids[], base_plan_id}   → comparison matrix

POST /graph/impact                    {corridor_id, km_start, km_end, start_ts, end_ts}
                                      → {affected_trains[], divertible[], detour_min, held[], alt_paths[]}

POST /baseline/generate               {division, horizon, period_start} → {plan_id, kpi}
GET  /compare?railopt_plan_id&baseline_plan_id                         → side-by-side KPI table
```

Contract detail that saves integration pain later: `/whatif/simulate` accepts a **list** of edits and is
stateless with respect to the base plan — the frontend keeps the edit stack, so undo/redo and "reset to AI plan"
are trivial and the backend never holds session state.

---

## 14. Frontend specification (M13)

Stack: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, `dnd-kit` for drag-resize on the Gantt,
`visx` or lightweight custom SVG for the timeline, `react-flow` for the corridor graph, TanStack Query for
server state. Chosen over Streamlit because the drag-to-extend interaction in US3 is the demo's emotional peak and
Streamlit cannot do it convincingly. If the frontend owner is unavailable, the documented fallback is a Streamlit
build with dropdown-driven edits instead of drag — same API, degraded interaction.

**14.1 Command Centre** — division KPI strip (K1, K2, K3, K6, K7), open vs overdue counts by department,
maintenance-debt bar per corridor, "Generate weekly plan" and "Generate monthly plan" actions, list of
`STARVED` tasks needing attention.

**14.2 Plan Board (primary screen)** — horizontal timeline, one swim-lane per corridor, 15-min grid, night hours
visually shaded. Each block is a card showing time range, department chips (E / S&T / TRD), km span, task count,
utilization bar, and a ★ if it contains shadow tasks. Train-path density is drawn as a background heat strip so
the planner sees *why* a window is lean. Interactions: drag horizontally to move, drag edge to extend, click to
open task list, drag a task from the backlog panel onto a block, right-click to drop or pin. Every interaction
fires `/whatif/simulate` and updates the KPI delta rail without a page change.

**14.3 Why Panel** — slides in from the right for the selected block: priority drivers with contribution bars,
binding constraint in plain words, bundle members table with shadow flags, counterfactual delay line, rejected
alternative windows with their scores.

**14.4 What-If / Scenario Compare** — the AI-recommended plan and up to three scenarios as columns; rows are the
§4 KPIs plus plan score; better values highlighted; a "cascade detail" expander showing per-train delay, mode
(DIVERT / HOLD), and where the knock-on was absorbed. Actions: promote a scenario to the working plan, discard,
or reset to the AI recommendation.

**14.5 Corridor Graph View** — nodes and edges from M5; blocked edges in red, diverted paths in amber with detour
minutes labelled, held trains pinned at their holding station. This is the screen that answers "can't you just
divert them?" in one glance.

**14.6 Baseline vs RAIL-OPT** — the proof screen. Two columns of KPIs on identical input data, with the deltas
expressed the way a Divisional officer would say them: "18 fewer block-hours this week, 41% of blocks now serve
more than one department, 3 future blocks eliminated."

**14.7 Approval & Export** — plan summary, validator status badge, approve with remarks, download BDMS-shaped
export. Role switcher (BS Planner / SSE / Controller / Officer) changes which screens and actions are visible;
this is presentation-level role separation, explicitly not authentication (§15).

---

## 15. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | Weekly solve ≤60 s, monthly ≤120 s, what-if local repair ≤2 s p95, other API p95 ≤300 ms |
| NFR-02 | Full stack starts with `docker compose up` and seeds the synthetic dataset in ≤3 min on a laptop |
| NFR-03 | Demo runs fully offline — no external API, no CDN dependency at runtime |
| NFR-04 | Deterministic: same seed + same weights + same `random_seed` for CP-SAT → identical plan |
| NFR-05 | Every plan version immutable; approvals and scenarios keep an audit trail with timestamp and actor |
| NFR-06 | No plan can be approved while `status = INVALID` |
| NFR-07 | Backend test coverage ≥70% on engine modules (M3–M9); 100% of H-rules have a violation test |
| NFR-08 | Structured JSON logs incl. solver stats; a `--explain-solve` flag dumps the model for debugging |
| NFR-09 | Security posture stated honestly: single-tenant demo, no auth, no PII, synthetic data only. If the API is ever exposed beyond localhost, add auth first — the current build has none by design |
| NFR-10 | Config (weights, R, L, overheads, thresholds) in YAML, never hardcoded in engine code |

---

## 16. Repository structure

```
rail-opt/
├─ docker-compose.yml
├─ config/
│   ├─ weights.yaml            # objective weights + presets
│   ├─ engine.yaml             # R, L, overheads, thresholds, solver limits
│   └─ compatibility.yaml      # block-type matrix + mutex task pairs
├─ backend/
│   ├─ app/
│   │   ├─ main.py  api/(routers)  core/(config, logging)
│   │   ├─ models/             # SQLAlchemy models = §9 DDL
│   │   ├─ schemas/            # Pydantic I/O contracts = §13
│   │   ├─ adapters/           # base.py tms.py smms.py tdms.py bdms.py coa.py tt.py
│   │   ├─ engines/
│   │   │   ├─ risk/           # hazard.py features.py model.py priority.py
│   │   │   ├─ opportunity/    # compat.py bundling.py shadow.py duration.py
│   │   │   ├─ graph/          # build.py paths.py impact.py
│   │   │   ├─ optimizer/      # model_build.py constraints.py objective.py solve.py repair.py
│   │   │   ├─ validator/      # rules.py report.py       (no imports from optimizer/)
│   │   │   ├─ horizon/        # monthly.py weekly.py rolling.py emergency.py
│   │   │   ├─ ripple/         # propagate.py regulate.py score.py
│   │   │   ├─ baseline/       # fcfs_planner.py
│   │   │   └─ kpi/            # compute.py
│   │   └─ services/           # plan_service.py whatif_service.py explain_service.py
│   ├─ synth/                  # generator.py profiles.py ground_truth.py
│   └─ tests/                  # unit/ integration/ fixtures/ golden/
├─ frontend/                   # Next.js app per §14
├─ data/                       # seed dump + ground_truth.json
└─ docs/                       # this PRD, architecture notes, demo script, slide assets
```

Hard rule enforced in review: `validator/` may not import from `optimizer/`, and `engines/` may not import from
`api/`. Those two lines keep the "independent validation" claim true and keep the engines unit-testable.

---

## 17. Build sequencing — out of scope for this PRD

Who builds what, in what order, and by when is decided by the team lead, not by this document. No schedule,
phase plan or task allocation is specified here on purpose.

The only build-order statement this PRD makes is a technical dependency fact, not a plan: the canonical data
model and synthetic dataset (§9, §11) must exist before the risk and opportunity engines can be tested, those
must exist before the optimizer has meaningful inputs, and the optimizer must return real plans before the
what-if loop has anything to re-solve. Anything that violates that order will block itself regardless of how it
is scheduled. The frontend is the exception — it can be built in parallel against the stubbed §13 contracts.

---

## 18. Test plan and acceptance criteria

**Unit.** Compatibility predicate truth table (spatial edge cases at exactly R, mutex pairs, power-block
implication); bundle duration arithmetic incl. overheads; priority monotonicity probes; Weibull vs XGBoost
agreement in direction; ripple propagation on a 5-train fixture with hand-computed delays; Yen's K-shortest on a
known 6-node graph.

**Constraint tests (one per H-rule).** For each of H1–H14, construct an input where the naive answer violates the
rule and assert the solver output does not, and separately assert that a manually corrupted plan is caught by M7.
This suite is the evidence behind every safety claim in the pitch.

**Golden tests.** A 12-task fixture with a brute-force enumerated optimum — assert CP-SAT matches the objective
value exactly. A frozen full-Division run with a stored plan hash — assert determinism (NFR-04).

**Integration.** Ingest → score → bundle → solve → validate → KPI → explain, end to end, asserting the planted
`ground_truth.json` opportunities are found (≥90% bundles, ≥80% shadows).

**Performance.** Weekly solve ≤60 s and what-if repair ≤2 s p95, measured in CI on the frozen dataset, failing the
build if exceeded.

**P0 acceptance gate (all must pass before the build is considered demo-ready).**
1. Weekly plan for 6 corridors / 600 requests generated in ≤60 s with zero validator violations.
2. K1 ≥25% better and K3 ≥40% versus the baseline on the frozen dataset.
3. K11 ≥15% and at least one demonstrable "future block eliminated" case (K12 ≥1).
4. Extending any block in the UI updates trains affected, cascade delay and plan score within 2 s.
5. Every block on screen has a non-empty, human-readable Why payload.
6. Monthly plan exists and the weekly plan respects its envelope.
7. `docker compose up` on a clean machine reproduces the demo offline.

---

## 19. Demo script (5 minutes, rehearsed)

**0:00 Frame the problem.** Command Centre with the baseline toggle on. "Three departments, three systems, three
separate block requests on the same corridor within the same week. Here they are. Nobody in this workflow is
responsible for noticing that." Point at the three separate blocks on the Plan Board.

**0:45 Generate.** One click. The optimizer runs; the three separate blocks collapse into one coordinated
01:15–02:45 corridor block. Read the bundle out loud: "one closure, three departments, seven tasks, KM 243–247."

**1:30 Prove it.** Baseline vs RAIL-OPT screen. Block-hours, coordination rate, weighted asset availability,
trains affected, cascade delay. Same data, same safety rules, one number at a time.

**2:15 Explain it.** Click Why. Priority drivers, the binding constraint, the rejected 22:00 window and why it
lost, and the counterfactual: "postponing the weld renewal by a week takes its failure risk from 4% to 10%."

**3:00 Shadow block.** Point at the ★ block. "Two of these seven tasks were not even due yet — an S&T gear
overhaul due in 19 days and an OHE tension check due in 24. Both are inside 5 km and past 60% of their cycle, so
the optimizer pulled them in. That is one entire future block that will never be requested."

**3:45 The what-if.** Drag the block from 2 h to 3 h. Watch trains affected go from 4 to 11, goods detention
appear, plan score fall. Then switch to the graph view: "9 of those 11 can divert via the loop at +16 minutes; 2
goods trains must be held at ANDI." Undo. "The AI recommends. The BS planner decides. Both of them can now see
the cost."

**4:30 Close.** Approve → BDMS-shaped export. "This slots into the existing sanction workflow. We are not
replacing BDMS; we are giving it a plan worth sanctioning."

Delivery rules: never type during the demo, never explain architecture unprompted, and if anything breaks, cut
straight to the frozen comparison screen — the numbers, not the animation, are the argument.

---

## 20. Risks and mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | CP-SAT too slow or infeasible at full scale | Demo dead | Per-corridor decomposition, 15-min granularity, candidate capping, warm start, documented relaxation order (§12.6.5), and a frozen pre-solved plan as demo fallback |
| R2 | Synthetic data looks fake to domain judges | Credibility loss | §11 consistency rules, real task codes and periodicities, honest statement that data is representative |
| R3 | Drag-and-resize interaction turns out harder than expected | Loses the centrepiece | Fallback dropdown-driven edits on the same API (§14); build the Plan Board against stubbed contracts early so the risk surfaces while it is still cheap |
| R4 | Bundling produces operationally absurd bundles | Domain expert dismisses it | Mutex matrix, prematurity guard, in-block sequencing, and validator rules — plus review of 10 sample bundles by anyone with railway exposure |
| R5 | Scope creep into the copilot / extra ML | P0 features left unfinished | Copilot is P2, gated behind the §18 acceptance list |
| R6 | Ripple model over-claims precision | Judge challenge | Present it as a deterministic first-order regulation model with stated assumptions (headway, slack, priority order), not a microsimulation |
| R7 | A contributor becomes unavailable | Optimizer work stalls | Keep a second person familiar with the optimizer module; engines are separately testable and depend only on §9 and §13, so work is transferable |
| R8 | "Where is the AI?" challenge | Perception | Answer is prepared and specific (§20.2) |

### 20.2 Q&A preparation

*"Where is the AI?"* — Two learned components (failure-risk model with monotone constraints, and the priority
model that turns heterogeneous defect data into a comparable deferral cost) plus a discovery layer (bundle
clustering over spatial-temporal compatibility). Scheduling itself is combinatorial optimisation, and that is a
deliberate choice: hard safety and capacity rules must be guaranteed, not learned.

*"Why not an LLM planner?"* — An LLM cannot guarantee H1–H14. We use no LLM in the scheduling loop; the optional
copilot only translates questions into API calls.

*"Have you integrated with the real TMS/SMMS/TDMS/COA?"* — No, and we say so plainly. Adapters exist per source
with documented field mappings; the demo runs on representative synthetic data because production access is not
available to a hackathon team. That is the honest answer and it is more credible than the alternative.

*"What if the planner disagrees with your plan?"* — Then he edits it, and the system re-solves under his
constraint and shows him the cost. The plan is never published without human approval, and never published if the
validator fails.

*"Would this actually reduce block-hours in the field?"* — The mechanism is coordination, not magic: three
departments needing the same corridor in the same week currently take three protection/release cycles. One shared
closure takes one. Our measured compression on representative data is K4; the field number depends on how much
spatial-temporal overlap a given Division actually has, which the tool also measures.

---

## 21. Open questions and change log

**Open product questions (defaults in §22.2 are in effect until answered):**
1. Whether a dedicated frontend owner exists — decides the §14 stack versus the Streamlit fallback. This is the
   one open question with a hard downstream consequence, so it is worth settling early.
2. Target Division/corridor for the synthetic dataset — using a generic 6-corridor Division unless a real
   geography is preferred for familiarity with judges.
3. Whether anyone can reach a domain contact (SSE/DEN) for a 20-minute sanity review of the bundle
   compatibility matrix (§12.4.3) — the single highest-value external input available to this project.
4. Whether Pareto plan presets (FR-21) are presented in the demo or left as a stated capability.
5. Whether the export format should mirror a real BDMS request payload, if anyone can obtain a sample.

**Change log:**
v1.1 (2026-09-02) — removed the build schedule, phase plan and role allocation; sequencing and task assignment
are owned by the team lead (§17 now records only the technical dependency order).
v1.0 (2026-09-01) — initial baselined PRD, synthesised from `RAIL-OPT_SIH_Ideation.md` and the
three team discussions (shadow-block predictor, what-if ripple simulator, graph corridor intelligence,
consolidated simulator narrative).

---

## 22. Appendix

### 22.1 Glossary
**Block** — planned closure of a track section to traffic for maintenance. **Corridor block** — a pre-declared
recurring maintenance window on a corridor. **Disconnection** — planned isolation of signalling gear, needs S&T
authorisation. **Power block** — de-energising OHE, needs traction isolation and earthing. **PTW** — permit to
work. **Chainage / KM** — linear location along a line. **BDMS** — Block Demand Management System (request and
sanction). **COA** — Control Office Application (train running and corridor availability). **TMS / SMMS / TDMS** —
Track / Signalling / Traction Distribution maintenance management systems. **BS team** — block section planning
team, our primary user. **USFD** — ultrasonic flaw detection of rails. **GMT** — gross million tonnes carried.
**Caution order** — speed restriction issued around work sites. **Headway** — minimum separation between
successive trains. **Knock-on delay** — delay transmitted from one train to those following it.

### 22.2 Default configuration
```yaml
engine:
  bundle_radius_km:      {TRAFFIC_BLOCK: 5.0, POWER_BLOCK: 8.0, DISCONNECTION: 2.0}
  shadow_lookahead_days: 30
  shadow_min_elapsed_fraction: 0.6
  shadow_max_days_early: 30
  shadow_value_discount: 0.7
  protect_min:  {default: 15, power_block: 30}
  release_min:  {default: 10, power_block: 20}
  slot_minutes: 15
  max_candidates_per_corridor: 40
  ripple_max_depth: 6
  clearance_min: 10
  freeze_horizon_hours: 6
solver:
  weekly_time_limit_s: 45
  monthly_time_limit_s: 90
  whatif_time_limit_s: 5
  workers: 8
  random_seed: 42
```

### 22.3 Traceability
Every PS ask (§2, A1–A7) maps to at least one module (§12) and at least one KPI (§4) and at least one acceptance
criterion (§18). Keep that chain intact through every scope cut — if a cut breaks the chain, the cut is wrong.


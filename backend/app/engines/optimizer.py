"""
CP-SAT Optimizer Engine - Phase 1
Constraint-based scheduler for railway maintenance blocks.

Based on PRD §12.6 - Hard constraints H1-H6.
Phase 1 schedules each request as its own block (standalone).
Phase 2 adds spatial bundling / coordination.
"""
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta, date
import math

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from app.models import (
    MaintenanceRequest, Corridor, BlockWindow, ResourceGang,
    Plan, PlannedBlock, PlannedBlockTask, Dept, Horizon, ReqStatus, BlockType,
)

SLOT_MINUTES = 15
T_PROTECT_MIN = 15   # protection time before work starts
T_RELEASE_MIN = 10   # release time after work ends

# Objective bonus per department beyond the first in a shared block.
# Must match opportunity.COORDINATION_BONUS_PER_EXTRA_DEPT (kept separate to
# avoid a circular import; opportunity.py imports from this module).
COORD_BONUS_OBJ = 300


def _naive(dt: datetime) -> datetime:
    """Strip tzinfo so naive/aware datetimes can be compared safely."""
    if dt is not None and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def priority_components(req: MaintenanceRequest, horizon_start: datetime):
    """
    Break the fallback priority score into human-readable drivers: a list of
    (label, points) pairs. The points sum to priority_of()'s fallback value
    EXACTLY — this is the data behind the explainability "why" panel (Phase 6).
    Score and explanation live in one place so they can never drift apart.
    """
    comps = [("Base weight", 50.0)]

    severity = req.defect_severity or 0
    if severity:
        comps.append((f"Defect severity {severity}/5", severity * 10.0))

    if req.due_on is not None:
        days_to_due = (req.due_on - horizon_start.date()).days
        if days_to_due < 0:
            n = -days_to_due
            comps.append((f"Overdue by {n} day{'s' if n != 1 else ''}",
                          min(50.0, n * 5.0)))
        elif days_to_due <= 3:
            if days_to_due == 0:
                label = "Due today"
            elif days_to_due == 1:
                label = "Due in 1 day"
            else:
                label = f"Due in {days_to_due} days"
            comps.append((label, 15.0))

    return comps


def priority_of(req: MaintenanceRequest, horizon_start: datetime) -> float:
    """
    Fallback priority score when M3 risk engine hasn't run yet (Phase 3).
    Combines defect severity, overdue urgency, and a small base weight.
    """
    if req.priority_score is not None:
        return float(req.priority_score)
    return sum(v for _, v in priority_components(req, horizon_start))


class CPSATOptimizer:
    """OR-Tools CP-SAT based maintenance block optimizer."""

    def __init__(self, db: Session, horizon_weeks: int = 1):
        self.db = db
        self.horizon_weeks = horizon_weeks
        self.total_slots = horizon_weeks * 7 * 24 * (60 // SLOT_MINUTES)  # 672 for 1 week

    # ---- slot helpers ----
    def _dt_to_slot(self, dt: datetime, horizon_start: datetime) -> int:
        return int((dt - horizon_start).total_seconds() // (SLOT_MINUTES * 60))

    def _slot_to_dt(self, slot: int, horizon_start: datetime) -> datetime:
        return horizon_start + timedelta(minutes=slot * SLOT_MINUTES)

    def _duration_slots(self, req: MaintenanceRequest) -> int:
        total_min = T_PROTECT_MIN + (req.est_duration_min or 60) + T_RELEASE_MIN
        return max(1, math.ceil(total_min / SLOT_MINUTES))

    # ---- core solve (candidate / set-partitioning formulation) ----
    def build_and_solve(
        self,
        requests: List[MaintenanceRequest],
        windows: List[BlockWindow],
        horizon_start: datetime,
        time_limit_seconds: int = 60,
        candidates=None,
    ) -> Dict:
        """
        Candidate-based CP-SAT.

        Each candidate is a potential block covering 1+ tasks (from the
        opportunity engine). The solver picks a subset of candidates such that
        every task is covered at most once (set packing), places each chosen
        candidate inside an admissible window, and enforces NoOverlap per
        corridor. Objective rewards covered priority + coordination, penalises
        block minutes.

        If `candidates` is None, falls back to one singleton candidate per task
        (equivalent to Phase 1 behaviour).
        """
        from app.engines.opportunity import OpportunityEngine

        if candidates is None:
            candidates = OpportunityEngine(horizon_start).generate(requests)

        model = cp_model.CpModel()

        # Window slot-bounds per corridor
        windows_by_corridor: Dict[int, List[Tuple[int, int]]] = {}
        for w in windows:
            w_start = max(0, self._dt_to_slot(_naive(w.start_ts), horizon_start))
            w_end = min(self.total_slots, self._dt_to_slot(_naive(w.end_ts), horizon_start))
            if w_end - w_start < 1:
                continue
            windows_by_corridor.setdefault(w.corridor_id, []).append((w_start, w_end))

        # Per-candidate decision vars
        y: Dict[str, cp_model.IntVar] = {}          # candidate chosen?
        cs: Dict[str, cp_model.IntVar] = {}         # start slot
        ce: Dict[str, cp_model.IntVar] = {}         # end slot (exclusive)
        corridor_intervals: Dict[int, List[cp_model.IntervalVar]] = {}

        for c in candidates:
            k = c.key
            d = c.duration_slots
            y[k] = model.NewBoolVar(f"y_{k}")
            cs[k] = model.NewIntVar(0, self.total_slots, f"cs_{k}")
            ce[k] = model.NewIntVar(0, self.total_slots, f"ce_{k}")
            model.Add(ce[k] == cs[k] + d)

            iv = model.NewOptionalIntervalVar(cs[k], d, ce[k], y[k], f"civ_{k}")
            corridor_intervals.setdefault(c.corridor_id, []).append(iv)

            # H4: candidate must fit inside exactly one admissible window
            cwins = windows_by_corridor.get(c.corridor_id, [])
            flags = []
            for wi, (ws, we) in enumerate(cwins):
                if we - ws < d:
                    continue
                f = model.NewBoolVar(f"cinw_{k}_{wi}")
                model.Add(cs[k] >= ws).OnlyEnforceIf(f)
                model.Add(ce[k] <= we).OnlyEnforceIf(f)
                flags.append(f)
            if not flags:
                model.Add(y[k] == 0)
            else:
                model.Add(sum(flags) == y[k])

        # Set packing: each task covered by at most one chosen candidate
        cands_by_task: Dict[int, List[str]] = {}
        for c in candidates:
            for tid in c.task_ids:
                cands_by_task.setdefault(tid, []).append(c.key)
        for tid, keys in cands_by_task.items():
            model.Add(sum(y[k] for k in keys) <= 1)

        # H1: NoOverlap per corridor
        for cid, ivs in corridor_intervals.items():
            if len(ivs) > 1:
                model.AddNoOverlap(ivs)

        # Objective: covered priority + coordination bonus − block-minute penalty
        obj_terms = []
        for c in candidates:
            reward = int(round(c.base_priority)) * 100
            coord = c.n_extra_depts * COORD_BONUS_OBJ
            penalty = c.duration_min
            obj_terms.append(y[c.key] * (reward + coord - penalty))
        model.Maximize(sum(obj_terms))

        # Solve — deterministic settings so the demo shows the same plan every run.
        # (8 parallel workers can return different equally-optimal bundle selections;
        # the model solves in <0.5s single-worker, so we trade nothing for stability.)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 42
        status = solver.Solve(model)
        status_name = solver.StatusName(status)

        scheduled = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for c in candidates:
                if solver.Value(y[c.key]) == 1:
                    start_slot = solver.Value(cs[c.key])
                    end_slot = solver.Value(ce[c.key])
                    scheduled.append({
                        "candidate": c,
                        "start_ts": self._slot_to_dt(start_slot, horizon_start),
                        "end_ts": self._slot_to_dt(end_slot, horizon_start),
                    })

        covered_tasks = sum(len(item["candidate"].task_ids) for item in scheduled)
        coordination_count = sum(1 for item in scheduled if item["candidate"].is_multi_dept)

        return {
            "status": status_name,
            "objective_value": solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0.0,
            "solve_ms": int(solver.WallTime() * 1000),
            "scheduled": scheduled,
            "total_requests": len(requests),
            "covered_tasks": covered_tasks,
            "coordination_count": coordination_count,
        }


    # ---- persistence ----
    def persist_plan(
        self,
        result: Dict,
        horizon_start: datetime,
        division: str,
    ) -> int:
        period_start = horizon_start.date()
        period_end = (horizon_start + timedelta(weeks=self.horizon_weeks)).date()

        plan = Plan(
            division=division,
            horizon=Horizon.WEEK,
            period_start=period_start,
            period_end=period_end,
            version=1,
            planner_kind="RAILOPT",
            status="VALID" if result["status"] in ("OPTIMAL", "FEASIBLE") else "INVALID",
            objective_value=result["objective_value"],
            solver_status=result["status"],
            solve_ms=result["solve_ms"],
            weights={},
        )
        self.db.add(plan)
        self.db.flush()

        for item in result["scheduled"]:
            cand = item["candidate"]
            reqs: List[MaintenanceRequest] = cand.requests
            depts = sorted({r.dept.value for r in reqs})
            # bundle_id only meaningful for multi-task shared blocks
            bundle_id = cand.key if cand.size > 1 else None
            block_score = sum(priority_of(r, horizon_start) for r in reqs)

            block = PlannedBlock(
                plan_id=plan.id,
                corridor_id=cand.corridor_id,
                km_start=cand.km_from,
                km_end=cand.km_to,
                line_no=1,
                start_ts=item["start_ts"],
                end_ts=item["end_ts"],
                block_type=BlockType(cand.block_type),
                bundle_id=bundle_id,
                depts=depts,
                is_pinned=False,
                utilization=None,
                score=block_score,
            )
            self.db.add(block)
            self.db.flush()

            # Assign each member task to the block. Same-dept tasks serialize
            # (seq increments); different depts run in parallel (share start).
            # For Phase 2 we record every task spanning the shared block window;
            # the block duration already accounts for serialization (PRD §12.4).
            for seq, req in enumerate(
                sorted(reqs, key=lambda r: (r.dept.value, -(r.defect_severity or 0))), start=1
            ):
                self.db.add(PlannedBlockTask(
                    planned_block_id=block.id,
                    request_id=req.id,
                    seq=seq,
                    start_ts=item["start_ts"],
                    end_ts=item["end_ts"],
                    gang_id=None,
                    is_shadow=False,
                ))

        self.db.commit()
        return plan.id

    # ---- entry point ----
    def optimize(
        self,
        division: str = "NDLS",
        horizon_start: Optional[datetime] = None,
        time_limit_seconds: int = 60,
    ) -> Dict:
        # Determine horizon from earliest window if not provided
        if horizon_start is None:
            first_window = (
                self.db.query(BlockWindow)
                .order_by(BlockWindow.start_ts.asc())
                .first()
            )
            if first_window is None:
                raise ValueError("No block windows found. Generate data first.")
            base = _naive(first_window.start_ts)
            horizon_start = datetime(base.year, base.month, base.day)

        horizon_end = horizon_start + timedelta(weeks=self.horizon_weeks)

        # Load requests due within (or before) horizon end and still open
        requests = (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < horizon_end.date())
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .all()
        )

        # Load windows within horizon (naive datetimes for comparison)
        windows = (
            self.db.query(BlockWindow)
            .filter(BlockWindow.start_ts >= horizon_start)
            .filter(BlockWindow.start_ts < horizon_end)
            .all()
        )

        result = self.build_and_solve(
            requests, windows, horizon_start, time_limit_seconds
        )
        plan_id = self.persist_plan(result, horizon_start, division)

        return {
            "plan_id": plan_id,
            "status": result["status"],
            "objective_value": round(result["objective_value"], 2),
            "solve_time_seconds": round(result["solve_ms"] / 1000.0, 2),
            "total_requests": result["total_requests"],
            "scheduled_blocks": len(result["scheduled"]),
            "scheduled_tasks": result["covered_tasks"],
            "unscheduled_tasks": result["total_requests"] - result["covered_tasks"],
            "coordination_count": result["coordination_count"],
        }

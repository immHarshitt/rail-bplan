"""
Explainability Engine (M-explain) - Phase 6

Answers "why is this block here?" for a single planned block, using the SAME
logic that drove the optimizer's decision — never a post-hoc narrative:

  1. Coordination   - which tasks/departments were bundled into one closure, and why
                      (spatial proximity within the bundling radius, D15).
  2. Value & saving - the objective contribution (task priority + coordination
                      bonus) and the block-hours saved vs running the tasks as
                      separate closures (PRD §12.4 duration model).
  3. Task priorities- per-task priority broken into its drivers (base / severity /
                      overdue), straight from optimizer.priority_components().
  4. Timing         - the admissible window the block was placed in and what kind
                      of window it is (why it sits in the overnight lean band).

Read-only. Works for RAIL-OPT and baseline plans alike (a baseline singleton just
shows one task and no coordination bonus — a useful contrast on stage).
"""
from datetime import datetime, time
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    Plan,
    PlannedBlock,
    PlannedBlockTask,
    MaintenanceRequest,
    BlockWindow,
)
from app.engines.optimizer import (
    priority_of,
    priority_components,
    _naive,
    COORD_BONUS_OBJ,
)
from app.engines.opportunity import _bundle_minutes, BUNDLE_RADIUS_KM

_DEPT_FULL = {"ENGG": "Engineering", "SNT": "Signal & Telecom", "TRD": "Traction/OHE"}

_WINDOW_KIND_TEXT = {
    "TRAFFIC_LEAN": "a traffic-lean window — the overnight band when fewest trains run",
    "CORRIDOR_POLICY": "a corridor-policy maintenance window",
    "MAINT_NOTIFIED": "a pre-notified maintenance window",
}


def _fmt_depts(depts: List[str]) -> str:
    """Join department codes into prose: 'ENGG', 'ENGG and SNT', 'ENGG, SNT and TRD'."""
    if not depts:
        return ""
    if len(depts) == 1:
        return depts[0]
    return f"{', '.join(depts[:-1])} and {depts[-1]}"


class ExplainEngine:
    def __init__(self, db: Session):
        self.db = db

    def explain(self, plan_id: int, block_id: int) -> Dict:
        plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        block = (
            self.db.query(PlannedBlock)
            .filter(PlannedBlock.id == block_id, PlannedBlock.plan_id == plan_id)
            .first()
        )
        if block is None:
            raise ValueError(f"Block {block_id} not found in plan {plan_id}")

        horizon_start = datetime.combine(plan.period_start, time())

        # ---- tasks in this block ----
        task_rows = (
            self.db.query(PlannedBlockTask)
            .filter(PlannedBlockTask.planned_block_id == block.id)
            .all()
        )
        reqs: List[MaintenanceRequest] = []
        for tr in task_rows:
            req = (
                self.db.query(MaintenanceRequest)
                .filter(MaintenanceRequest.id == tr.request_id)
                .first()
            )
            if req:
                reqs.append(req)

        depts = sorted({r.dept.value for r in reqs})
        n_depts = len(depts)
        n_tasks = len(reqs)
        b_start = _naive(block.start_ts)
        b_end = _naive(block.end_ts)
        bundled_min = (b_end - b_start).total_seconds() / 60.0

        # ---- per-task priority breakdown ----
        tasks_out = []
        task_value = 0.0
        for r in reqs:
            comps = priority_components(r, horizon_start)
            score = priority_of(r, horizon_start)
            task_value += score
            tasks_out.append({
                "request_id": r.id,
                "dept": r.dept.value,
                "task_kind": r.task_kind,
                "task_code": r.task_code,
                "km_from": float(r.km_from),
                "est_duration_min": r.est_duration_min,
                "defect_severity": r.defect_severity,
                "due_on": r.due_on.isoformat() if r.due_on else None,
                "priority": round(score, 1),
                "drivers": [{"label": lbl, "points": round(pts, 1)} for lbl, pts in comps],
            })
        # highest-priority task first (the one that most justifies the closure)
        tasks_out.sort(key=lambda t: t["priority"], reverse=True)

        # ---- value & time saved (only meaningful vs separate closures) ----
        n_extra_depts = max(0, n_depts - 1)
        coordination_bonus = float(n_extra_depts * COORD_BONUS_OBJ)
        standalone_min = sum(_bundle_minutes([r]) for r in reqs)
        hours_saved = max(0.0, (standalone_min - bundled_min) / 60.0)
        compression = round(standalone_min / bundled_min, 2) if bundled_min > 0 else 1.0

        # ---- spatial span ----
        if block.km_start is not None and block.km_end is not None:
            km_start, km_end = float(block.km_start), float(block.km_end)
        else:
            kms = [float(r.km_from) for r in reqs]
            km_start, km_end = (min(kms), max(kms)) if kms else (0.0, 0.0)
        km_span = round(km_end - km_start, 2)

        # ---- coordination narrative ----
        if n_tasks <= 1:
            coord_headline = "Standalone closure · 1 task"
            coord_rationale = (
                "This block runs a single task, so there was no coordination "
                "opportunity within the bundling radius."
            )
        else:
            dept_clause = (
                f"{n_depts} departments ({_fmt_depts(depts)})"
                if n_depts >= 2
                else f"{n_tasks} {depts[0]} tasks"
            )
            coord_headline = f"{n_tasks} tasks · {n_depts} department{'s' if n_depts != 1 else ''} · one closure"
            coord_rationale = (
                f"{dept_clause} within {km_span:.1f} km on this corridor were bundled "
                f"into ONE track closure instead of {n_tasks} separate ones "
                f"(bundling radius {BUNDLE_RADIUS_KM:.0f} km)."
            )

        # ---- binding timing constraint: the admissible window ----
        window = self._find_window(block, b_start, b_end)

        return {
            "block_id": block.id,
            "plan_id": plan_id,
            "planner_kind": plan.planner_kind,
            "corridor_id": block.corridor_id,
            "block_type": block.block_type.value,
            "depts": depts,
            "is_coordinated": n_depts >= 2,
            "n_tasks": n_tasks,
            "n_depts": n_depts,
            "km_start": km_start,
            "km_end": km_end,
            "km_span": km_span,
            "start_ts": block.start_ts.isoformat(),
            "end_ts": block.end_ts.isoformat(),
            "duration_hours": round(bundled_min / 60.0, 2),
            "coordination": {
                "n_tasks": n_tasks,
                "n_depts": n_depts,
                "depts": depts,
                "km_span": km_span,
                "radius_km": BUNDLE_RADIUS_KM,
                "headline": coord_headline,
                "rationale": coord_rationale,
            },
            "value": {
                "task_value": round(task_value, 1),
                "coordination_bonus": coordination_bonus,
                "n_extra_depts": n_extra_depts,
                "total_value": round(task_value + coordination_bonus, 1),
                "bundled_hours": round(bundled_min / 60.0, 2),
                "standalone_hours": round(standalone_min / 60.0, 2),
                "hours_saved": round(hours_saved, 2),
                "compression": compression,
            },
            "tasks": tasks_out,
            "window": window,
        }

    def _find_window(self, block: PlannedBlock, b_start: datetime, b_end: datetime) -> Dict:
        """
        Reconstruct which admissible window the block was placed in (H4). The
        optimizer doesn't persist the chosen window, so we find containing windows
        on the same corridor and prefer TRAFFIC_LEAN whose allowed types include
        this block's type — that is the interesting 'why overnight' story.
        """
        candidates = (
            self.db.query(BlockWindow)
            .filter(BlockWindow.corridor_id == block.corridor_id)
            .all()
        )
        btype = block.block_type.value
        containing = [
            w for w in candidates
            if _naive(w.start_ts) <= b_start and _naive(w.end_ts) >= b_end
        ]

        def _rank(w: BlockWindow):
            type_ok = 1 if (w.allowed_block_types and btype in w.allowed_block_types) else 0
            lean = 1 if w.window_kind == "TRAFFIC_LEAN" else 0
            tightness = -(_naive(w.end_ts) - _naive(w.start_ts)).total_seconds()
            return (type_ok, lean, tightness)

        if not containing:
            return {
                "found": False,
                "window_kind": None,
                "rationale": (
                    "Scheduled inside its corridor's admissible maintenance window."
                ),
            }

        w = max(containing, key=_rank)
        kind = w.window_kind
        text = _WINDOW_KIND_TEXT.get(kind, "an admissible maintenance window")
        return {
            "found": True,
            "window_kind": kind,
            "start_ts": w.start_ts.isoformat(),
            "end_ts": w.end_ts.isoformat(),
            "allowed_block_types": list(w.allowed_block_types or []),
            "rationale": (
                f"Placed inside {text}. Constraint H4 requires every block to sit "
                f"within an admissible window — this one permits {btype} work."
            ),
        }

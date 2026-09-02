"""
Baseline FCFS Planner (M11)
Simulates today's manual first-come-first-serve process for comparison.

Same safety rules (no overlap, within windows) but no coordination /
bundling and no global optimisation - one block per task, greedy placement.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    MaintenanceRequest, BlockWindow, Plan, PlannedBlock, PlannedBlockTask,
    Dept, Horizon, ReqStatus,
)
from app.engines.optimizer import _naive, T_PROTECT_MIN, T_RELEASE_MIN, SLOT_MINUTES
import math


class BaselinePlanner:
    """First-Come-First-Serve baseline planner."""

    def __init__(self, db: Session, horizon_weeks: int = 1):
        self.db = db
        self.horizon_weeks = horizon_weeks

    def _block_minutes(self, req: MaintenanceRequest) -> int:
        # Slot-rounded to match the optimizer's duration model (fair comparison)
        raw = T_PROTECT_MIN + (req.est_duration_min or 60) + T_RELEASE_MIN
        return int(math.ceil(raw / SLOT_MINUTES) * SLOT_MINUTES)

    def generate(
        self,
        division: str = "NDLS",
        horizon_start: Optional[datetime] = None,
    ) -> Dict:
        # Determine horizon
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

        requests = (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < horizon_end.date())
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .all()
        )

        windows = (
            self.db.query(BlockWindow)
            .filter(BlockWindow.start_ts >= horizon_start)
            .filter(BlockWindow.start_ts < horizon_end)
            .all()
        )

        # Windows per corridor sorted by start
        windows_by_corridor: Dict[int, List[BlockWindow]] = {}
        for w in windows:
            windows_by_corridor.setdefault(w.corridor_id, []).append(w)
        for cid in windows_by_corridor:
            windows_by_corridor[cid].sort(key=lambda w: _naive(w.start_ts))

        # Sort requests: dept order, then due date, then severity (manual triage)
        dept_order = {Dept.ENGG: 0, Dept.SNT: 1, Dept.TRD: 2}
        requests.sort(key=lambda r: (
            dept_order.get(r.dept, 9),
            r.due_on,
            -(r.defect_severity or 0),
        ))

        # Track occupied intervals per corridor
        occupied: Dict[int, List[tuple]] = {}

        scheduled = []
        for req in requests:
            placed = self._place(req, windows_by_corridor.get(req.corridor_id, []), occupied)
            if placed:
                scheduled.append(placed)

        plan_id = self._persist(scheduled, horizon_start, division)

        total_block_hours = sum(
            (item["end_ts"] - item["start_ts"]).total_seconds() / 3600.0
            for item in scheduled
        )

        return {
            "plan_id": plan_id,
            "status": "FEASIBLE",
            "objective_value": 0.0,
            "solve_time_seconds": 0.0,
            "total_requests": len(requests),
            "scheduled_blocks": len(scheduled),
            "scheduled_tasks": len(scheduled),
            "unscheduled_tasks": len(requests) - len(scheduled),
            "coordination_count": 0,
            "total_block_hours": round(total_block_hours, 2),
        }

    def _place(self, req, corridor_windows, occupied) -> Optional[Dict]:
        """Greedy: earliest window+slot that fits without overlap."""
        need = timedelta(minutes=self._block_minutes(req))
        cid = req.corridor_id

        for w in corridor_windows:
            w_start = _naive(w.start_ts)
            w_end = _naive(w.end_ts)
            if w_end - w_start < need:
                continue

            # Try to slot in right after the latest occupied block inside this window
            candidate = w_start
            while candidate + need <= w_end:
                conflict_end = self._conflict(cid, candidate, candidate + need, occupied)
                if conflict_end is None:
                    occupied.setdefault(cid, []).append((candidate, candidate + need))
                    return {
                        "request": req,
                        "start_ts": candidate,
                        "end_ts": candidate + need,
                    }
                candidate = conflict_end  # jump past the conflict
        return None

    def _conflict(self, cid, start, end, occupied) -> Optional[datetime]:
        """Return end of a conflicting interval, or None if free."""
        for (os, oe) in occupied.get(cid, []):
            if not (end <= os or start >= oe):
                return oe
        return None

    def _persist(self, scheduled, horizon_start, division) -> int:
        period_start = horizon_start.date()
        period_end = (horizon_start + timedelta(weeks=self.horizon_weeks)).date()

        plan = Plan(
            division=division,
            horizon=Horizon.WEEK,
            period_start=period_start,
            period_end=period_end,
            version=1,
            planner_kind="BASELINE",
            status="VALID",
            objective_value=0.0,
            solver_status="BASELINE_FCFS",
            solve_ms=0,
            weights={},
        )
        self.db.add(plan)
        self.db.flush()

        for item in scheduled:
            req = item["request"]
            block = PlannedBlock(
                plan_id=plan.id,
                corridor_id=req.corridor_id,
                km_start=req.km_from,
                km_end=req.km_to,
                line_no=1,
                start_ts=item["start_ts"],
                end_ts=item["end_ts"],
                block_type=req.required_block,
                bundle_id=None,
                depts=[req.dept.value],
                is_pinned=False,
                utilization=None,
                score=None,
            )
            self.db.add(block)
            self.db.flush()
            self.db.add(PlannedBlockTask(
                planned_block_id=block.id,
                request_id=req.id,
                seq=1,
                start_ts=item["start_ts"],
                end_ts=item["end_ts"],
                gang_id=None,
                is_shadow=False,
            ))

        self.db.commit()
        return plan.id

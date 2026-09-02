"""
What-If Simulation Engine — PRD §12.9

Applies a single edit to a plan's block and reports the consequences: recomputed
KPIs, the ripple/cascade traffic impact of the edited block, and a 0-100 plan
score (§12.9.3), each with a delta vs the unedited plan.

Supported edits (the two that need NO CP-SAT re-solve — they only move a block's
bounds, so the answer is a fast deterministic recompute, well under the K15 ≤2s
target):

  EXTEND_BLOCK { block_id, delta_min }   fix start, push end out by delta_min
  MOVE_BLOCK   { block_id, delta_min }   shift start (and end) by delta_min, dur kept
                                         delta_min < 0 = earlier, > 0 = later

The stored plan is never mutated; edits are applied to in-memory copies of the
block bounds and everything is recomputed analytically + via the RippleEngine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, datetime, time
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    Plan, PlannedBlock, PlannedBlockTask, MaintenanceRequest, ReqStatus,
)
from app.engines.optimizer import (
    T_PROTECT_MIN, T_RELEASE_MIN, SLOT_MINUTES, _naive, priority_of,
)
from app.engines.ripple import RippleEngine, RippleResult
import math


# plan_score §12.9.3 weights
W_MAINT_VALUE = 0.30
W_BLOCK_HOURS = 0.20
W_COORD = 0.15
W_CASCADE = 0.15
W_ASSET = 0.10
W_UTIL = 0.10

# cascade-delay normalization reference: per-block "bad case" aggregate delay (min)
CASCADE_REF_PER_BLOCK = 120.0


@dataclass
class BlockView:
    """In-memory, mutable copy of a block's ripple-relevant fields."""
    id: int
    corridor_id: int
    km_start: float
    km_end: float
    start_ts: object
    end_ts: object
    block_type: str
    depts: List[str]
    work_min: int  # sum of member-task est durations


class WhatIfEngine:
    def __init__(self, db: Session):
        self.db = db
        self.ripple = RippleEngine(db)

    # -- load ------------------------------------------------------------------
    def _load_block_views(self, plan_id: int) -> List[BlockView]:
        blocks = (
            self.db.query(PlannedBlock)
            .filter(PlannedBlock.plan_id == plan_id)
            .order_by(PlannedBlock.start_ts)
            .all()
        )
        # work-minutes per block = Σ member est_duration_min
        views: List[BlockView] = []
        for b in blocks:
            task_rows = (
                self.db.query(MaintenanceRequest.est_duration_min)
                .join(PlannedBlockTask, PlannedBlockTask.request_id == MaintenanceRequest.id)
                .filter(PlannedBlockTask.planned_block_id == b.id)
                .all()
            )
            work_min = sum((r[0] or 60) for r in task_rows)
            views.append(BlockView(
                id=b.id, corridor_id=b.corridor_id,
                km_start=float(b.km_start), km_end=float(b.km_end),
                start_ts=_naive(b.start_ts), end_ts=_naive(b.end_ts),
                block_type=b.block_type.value if hasattr(b.block_type, "value") else str(b.block_type),
                depts=list(b.depts or []), work_min=work_min,
            ))
        return views

    # -- ripple over the whole plan -------------------------------------------
    def _ripple_all(self, views: List[BlockView]) -> Dict[int, RippleResult]:
        out: Dict[int, RippleResult] = {}
        for v in views:
            out[v.id] = self.ripple.simulate(
                v.corridor_id, v.km_start, v.km_end, v.start_ts, v.end_ts, v.block_type,
            )
        return out

    # -- KPI recompute (analytic, from block views) ---------------------------
    def _kpis(self, plan: Plan, views: List[BlockView]) -> Dict:
        actual_block_hours = sum(
            (_naive(v.end_ts) - _naive(v.start_ts)).total_seconds() / 3600.0 for v in views
        )
        # standalone hours = Σ slot-rounded standalone block per scheduled task
        task_rows = (
            self.db.query(MaintenanceRequest)
            .join(PlannedBlockTask, PlannedBlockTask.request_id == MaintenanceRequest.id)
            .join(PlannedBlock, PlannedBlock.id == PlannedBlockTask.planned_block_id)
            .filter(PlannedBlock.plan_id == plan.id)
            .all()
        )
        standalone_hours = 0.0
        for r in task_rows:
            raw = T_PROTECT_MIN + (r.est_duration_min or 60) + T_RELEASE_MIN
            standalone_hours += (math.ceil(raw / SLOT_MINUTES) * SLOT_MINUTES) / 60.0

        n_scheduled = len(task_rows)
        total_candidates = (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < plan.period_end)
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .count()
        ) or 1

        n_blocks = len(views)
        coord_blocks = sum(1 for v in views if len(set(v.depts)) >= 2)

        k5 = actual_block_hours
        k4 = (standalone_hours / actual_block_hours) if actual_block_hours > 0 else 1.0
        k3 = (coord_blocks / n_blocks) if n_blocks else 0.0
        k1 = n_scheduled / total_candidates

        return {
            "k1_completion_rate": round(k1, 4),
            "k3_coordination_rate": round(k3, 4),
            "k4_compression_ratio": round(k4, 4),
            "k5_block_hours": round(k5, 2),
            "n_blocks": n_blocks,
            "n_scheduled_tasks": n_scheduled,
            "n_coordinated_blocks": coord_blocks,
            "_standalone_hours": round(standalone_hours, 2),
            "_work_min": sum(v.work_min for v in views),
        }

    # -- plan score §12.9.3 ----------------------------------------------------
    def _plan_score(self, plan: Plan, views: List[BlockView], kpis: Dict,
                    ripples: Dict[int, RippleResult]) -> Dict:
        # maint value: scheduled priority / total candidate priority (constant for
        # EXTEND/MOVE, but computed honestly so the absolute score is meaningful)
        horizon_start = datetime.combine(plan.period_start, time())
        cand = (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < plan.period_end)
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .all()
        )
        sched_ids = set()
        for v in views:
            for r in (
                self.db.query(PlannedBlockTask.request_id)
                .filter(PlannedBlockTask.planned_block_id == v.id)
                .all()
            ):
                sched_ids.add(r[0])
        total_val = sum(priority_of(r, horizon_start) for r in cand) or 1.0
        sched_val = sum(priority_of(r, horizon_start) for r in cand if r.id in sched_ids)
        maint_value_norm = min(1.0, sched_val / total_val)

        # block-hours: actual / standalone ∈ (0,1]; lower is better
        stand = kpis["_standalone_hours"] or 1.0
        block_hours_norm = min(1.0, kpis["k5_block_hours"] / stand)

        coord_rate = kpis["k3_coordination_rate"]

        # cascade delay over the whole plan, normalized against a per-block ref
        total_delay = sum(r.total_delay_min for r in ripples.values())
        cascade_ref = max(1.0, len(views) * CASCADE_REF_PER_BLOCK)
        cascade_delay_norm = min(1.0, total_delay / cascade_ref)

        # asset availability gain proxy = K1 (severity-weighted omitted here; K1 is
        # constant for EXTEND/MOVE so it does not distort deltas)
        asset_avail_gain_norm = kpis["k1_completion_rate"]

        # block utilization = Σ work_min / Σ block_min
        block_min = sum(
            (_naive(v.end_ts) - _naive(v.start_ts)).total_seconds() / 60.0 for v in views
        ) or 1.0
        block_utilization = min(1.0, kpis["_work_min"] / block_min)

        score = 100.0 * (
            W_MAINT_VALUE * maint_value_norm
            + W_BLOCK_HOURS * (1.0 - block_hours_norm)
            + W_COORD * coord_rate
            + W_CASCADE * (1.0 - cascade_delay_norm)
            + W_ASSET * asset_avail_gain_norm
            + W_UTIL * block_utilization
        )
        return {
            "score": round(score, 1),
            "components": {
                "maint_value_norm": round(maint_value_norm, 3),
                "block_hours_norm": round(block_hours_norm, 3),
                "coord_rate": round(coord_rate, 3),
                "cascade_delay_norm": round(cascade_delay_norm, 3),
                "asset_avail_gain_norm": round(asset_avail_gain_norm, 3),
                "block_utilization": round(block_utilization, 3),
                "total_cascade_delay_min": int(total_delay),
            },
        }

    # -- edit application ------------------------------------------------------
    def _apply_edit(self, views: List[BlockView], edit: Dict) -> BlockView:
        op = edit.get("op")
        block_id = edit.get("block_id")
        delta_min = int(edit.get("delta_min", 0))
        target = next((v for v in views if v.id == block_id), None)
        if target is None:
            raise ValueError(f"Block {block_id} not in plan")

        if op == "EXTEND_BLOCK":
            target.end_ts = target.end_ts + timedelta(minutes=delta_min)
        elif op == "MOVE_BLOCK":
            target.start_ts = target.start_ts + timedelta(minutes=delta_min)
            target.end_ts = target.end_ts + timedelta(minutes=delta_min)
        else:
            raise ValueError(f"Unsupported edit op: {op}")
        return target

    # -- public API ------------------------------------------------------------
    def simulate(self, plan_id: int, edit: Dict) -> Dict:
        plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        # BEFORE
        views_before = self._load_block_views(plan_id)
        ripples_before = self._ripple_all(views_before)
        kpis_before = self._kpis(plan, views_before)
        score_before = self._plan_score(plan, views_before, kpis_before, ripples_before)

        target_id = edit.get("block_id")
        ripple_before_target = ripples_before.get(target_id)

        # AFTER (edit applied to a fresh copy)
        views_after = self._load_block_views(plan_id)
        target = self._apply_edit(views_after, edit)
        ripples_after = dict(ripples_before)  # other blocks unchanged
        ripples_after[target.id] = self.ripple.simulate(
            target.corridor_id, target.km_start, target.km_end,
            target.start_ts, target.end_ts, target.block_type,
        )
        kpis_after = self._kpis(plan, views_after)
        score_after = self._plan_score(plan, views_after, kpis_after, ripples_after)

        ripple_after_target = ripples_after[target.id]
        feasible = ripple_after_target.feasible

        return {
            "feasible": feasible,
            "infeasibility_reason": ripple_after_target.infeasibility_reason,
            "edit": edit,
            "block_id": target.id,
            "kpi_before": _public_kpi(kpis_before),
            "kpi_after": _public_kpi(kpis_after),
            "kpi_delta": {
                "k5_block_hours": round(kpis_after["k5_block_hours"] - kpis_before["k5_block_hours"], 2),
                "k4_compression_ratio": round(kpis_after["k4_compression_ratio"] - kpis_before["k4_compression_ratio"], 4),
                "k3_coordination_rate": round(kpis_after["k3_coordination_rate"] - kpis_before["k3_coordination_rate"], 4),
            },
            "ripple_before": ripple_before_target.to_dict() if ripple_before_target else None,
            "ripple_after": ripple_after_target.to_dict(),
            "ripple_delta": {
                "trains_affected": ripple_after_target.trains_affected - (ripple_before_target.trains_affected if ripple_before_target else 0),
                "total_delay_min": ripple_after_target.total_delay_min - (ripple_before_target.total_delay_min if ripple_before_target else 0),
                "goods_detention_hours": round(
                    ripple_after_target.goods_detention_hours - (ripple_before_target.goods_detention_hours if ripple_before_target else 0.0), 2),
            },
            "plan_score_before": score_before,
            "plan_score_after": score_after,
            "plan_score_delta": round(score_after["score"] - score_before["score"], 1),
        }


def _public_kpi(k: Dict) -> Dict:
    return {kk: vv for kk, vv in k.items() if not kk.startswith("_")}

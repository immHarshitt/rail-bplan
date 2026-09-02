"""
KPI Computation Engine
Computes K1-K5 metrics for a plan and stores them in kpi_snapshot.kpi (JSONB).

K1 Completion rate      = scheduled tasks / total candidate tasks
K2 Asset availability   = criticality-weighted scheduled / total (proxy)
K3 Coordination rate    = blocks with >=2 depts / total blocks
K4 Compression ratio    = standalone block-hours / actual block-hours
K5 Block-hours          = sum of block durations (lower is better)
"""
from typing import Dict, Optional
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import (
    Plan, PlannedBlock, PlannedBlockTask, MaintenanceRequest, Asset, KPISnapshot,
)
from app.engines.optimizer import T_PROTECT_MIN, T_RELEASE_MIN, SLOT_MINUTES
import math


class KPIEngine:
    def __init__(self, db: Session):
        self.db = db

    def _candidate_total(self, plan: Plan) -> int:
        """Total requests that were candidates in this plan's horizon."""
        from app.models import ReqStatus
        return (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < plan.period_end)
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .count()
        )

    def compute(self, plan_id: int) -> Dict:
        plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        blocks = self.db.query(PlannedBlock).filter(PlannedBlock.plan_id == plan_id).all()
        block_task_rows = (
            self.db.query(PlannedBlockTask)
            .join(PlannedBlock, PlannedBlock.id == PlannedBlockTask.planned_block_id)
            .filter(PlannedBlock.plan_id == plan_id)
            .all()
        )

        total_candidates = self._candidate_total(plan) or 1
        scheduled_task_ids = {bt.request_id for bt in block_task_rows}
        n_scheduled = len(scheduled_task_ids)

        # K1 completion
        k1 = n_scheduled / total_candidates

        # K5 block-hours + K4 compression
        actual_block_hours = 0.0
        for b in blocks:
            actual_block_hours += (b.end_ts - b.start_ts).total_seconds() / 3600.0

        standalone_hours = 0.0
        if scheduled_task_ids:
            reqs = (
                self.db.query(MaintenanceRequest)
                .filter(MaintenanceRequest.id.in_(scheduled_task_ids))
                .all()
            )
            for r in reqs:
                # Slot-rounded standalone block to match how blocks are actually sized
                raw = T_PROTECT_MIN + (r.est_duration_min or 60) + T_RELEASE_MIN
                rounded = math.ceil(raw / SLOT_MINUTES) * SLOT_MINUTES
                standalone_hours += rounded / 60.0

        k5 = actual_block_hours
        k4 = (standalone_hours / actual_block_hours) if actual_block_hours > 0 else 1.0

        # K3 coordination rate (blocks with >=2 distinct depts)
        n_blocks = len(blocks)
        coord_blocks = sum(1 for b in blocks if b.depts and len(set(b.depts)) >= 2)
        k3 = (coord_blocks / n_blocks) if n_blocks > 0 else 0.0

        # K2 asset availability proxy (criticality-weighted completion)
        k2 = self._k2_asset_availability(plan, scheduled_task_ids)

        kpi = {
            "k1_completion_rate": round(k1, 4),
            "k2_asset_availability": round(k2, 4),
            "k3_coordination_rate": round(k3, 4),
            "k4_compression_ratio": round(k4, 4),
            "k5_block_hours": round(k5, 2),
            "n_blocks": n_blocks,
            "n_scheduled_tasks": n_scheduled,
            "n_coordinated_blocks": coord_blocks,
            "total_candidates": total_candidates,
        }

        self._persist(plan_id, kpi)
        return kpi

    def _k2_asset_availability(self, plan, scheduled_task_ids) -> float:
        from app.models import ReqStatus
        reqs = (
            self.db.query(MaintenanceRequest)
            .filter(MaintenanceRequest.due_on < plan.period_end)
            .filter(MaintenanceRequest.status.in_([ReqStatus.OPEN, ReqStatus.OVERDUE]))
            .all()
        )
        total_w = 0.0
        done_w = 0.0
        for r in reqs:
            # Weight by defect severity as a criticality proxy (fallback 1)
            w = float((r.defect_severity or 0) + 1)
            total_w += w
            if r.id in scheduled_task_ids:
                done_w += w
        return (done_w / total_w) if total_w > 0 else 1.0

    def _persist(self, plan_id: int, kpi: Dict) -> None:
        snap = self.db.query(KPISnapshot).filter(KPISnapshot.plan_id == plan_id).first()
        if snap is None:
            snap = KPISnapshot(plan_id=plan_id, kpi=kpi)
            self.db.add(snap)
        else:
            snap.kpi = kpi
        self.db.commit()

    def compare(self, railopt_plan_id: int, baseline_plan_id: int) -> Dict:
        railopt = self.compute(railopt_plan_id)
        baseline = self.compute(baseline_plan_id)

        base_k5 = baseline["k5_block_hours"] or 1.0
        k5_reduction_pct = (base_k5 - railopt["k5_block_hours"]) / base_k5 * 100.0
        k3_delta_pp = (railopt["k3_coordination_rate"] - baseline["k3_coordination_rate"]) * 100.0

        return {
            "railopt": railopt,
            "baseline": baseline,
            "improvements": {
                "k1_delta": round(railopt["k1_completion_rate"] - baseline["k1_completion_rate"], 4),
                "k2_delta": round(railopt["k2_asset_availability"] - baseline["k2_asset_availability"], 4),
                "k3_delta_pp": round(k3_delta_pp, 1),
                "k4_improvement": round(railopt["k4_compression_ratio"] - baseline["k4_compression_ratio"], 4),
                "k5_reduction_pct": round(k5_reduction_pct, 1),
                "block_hours_saved": round(base_k5 - railopt["k5_block_hours"], 2),
            },
            "summary": {
                "meets_k5_target": k5_reduction_pct >= 25.0,
                "meets_k3_target": railopt["k3_coordination_rate"] >= 0.40,
            },
        }

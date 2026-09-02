"""
Plan generation and comparison API endpoints (Phase 1)
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.engines.optimizer import CPSATOptimizer
from app.engines.baseline import BaselinePlanner
from app.engines.kpi import KPIEngine
from app.engines.whatif import WhatIfEngine
from app.engines.explain import ExplainEngine


router = APIRouter()


class GeneratePlanRequest(BaseModel):
    division: str = "NDLS"
    time_limit_seconds: int = 60


class GeneratePlanResponse(BaseModel):
    plan_id: int
    status: str
    objective_value: float
    solve_time_seconds: float
    total_requests: int
    scheduled_blocks: int
    scheduled_tasks: int
    unscheduled_tasks: int
    coordination_count: int


@router.post("/generate", response_model=GeneratePlanResponse)
def generate_plan(request: GeneratePlanRequest, db: Session = Depends(get_db)):
    """Generate optimised maintenance plan using CP-SAT."""
    try:
        optimizer = CPSATOptimizer(db, horizon_weeks=1)
        result = optimizer.optimize(
            division=request.division,
            time_limit_seconds=request.time_limit_seconds,
        )
        return GeneratePlanResponse(**result)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e}")


@router.post("/baseline", response_model=GeneratePlanResponse)
def generate_baseline(request: GeneratePlanRequest, db: Session = Depends(get_db)):
    """Generate baseline plan using FCFS (manual process simulation)."""
    try:
        planner = BaselinePlanner(db, horizon_weeks=1)
        result = planner.generate(division=request.division)
        # baseline result has extra 'total_block_hours' key - filter to response model
        return GeneratePlanResponse(
            plan_id=result["plan_id"],
            status=result["status"],
            objective_value=result["objective_value"],
            solve_time_seconds=result["solve_time_seconds"],
            total_requests=result["total_requests"],
            scheduled_blocks=result["scheduled_blocks"],
            scheduled_tasks=result["scheduled_tasks"],
            unscheduled_tasks=result["unscheduled_tasks"],
            coordination_count=result["coordination_count"],
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Baseline generation failed: {e}")


@router.get("/compare")
def compare_plans(
    railopt_plan_id: int,
    baseline_plan_id: int,
    db: Session = Depends(get_db),
):
    """Compare RAIL-OPT plan vs baseline plan with KPIs."""
    try:
        engine = KPIEngine(db)
        return engine.compare(railopt_plan_id, baseline_plan_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


@router.get("/{plan_id}/kpis")
def get_plan_kpis(plan_id: int, db: Session = Depends(get_db)):
    """Compute (or recompute) KPIs for a plan."""
    try:
        engine = KPIEngine(db)
        return engine.compute(plan_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"KPI computation failed: {e}")


@router.get("/{plan_id}/details")
def get_plan_details(plan_id: int, db: Session = Depends(get_db)):
    """Return plan metadata plus all blocks and their tasks."""
    from app.models import Plan, PlannedBlock, PlannedBlockTask, MaintenanceRequest

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    blocks = db.query(PlannedBlock).filter(PlannedBlock.plan_id == plan_id).all()
    blocks_data = []
    for block in blocks:
        task_rows = (
            db.query(PlannedBlockTask)
            .filter(PlannedBlockTask.planned_block_id == block.id)
            .all()
        )
        tasks_data = []
        for tr in task_rows:
            req = (
                db.query(MaintenanceRequest)
                .filter(MaintenanceRequest.id == tr.request_id)
                .first()
            )
            if req:
                tasks_data.append({
                    "request_id": req.id,
                    "dept": req.dept.value,
                    "task_kind": req.task_kind,
                    "task_code": req.task_code,
                    "est_duration_min": req.est_duration_min,
                    "km_from": float(req.km_from),
                    "priority_score": float(req.priority_score) if req.priority_score else None,
                })
        blocks_data.append({
            "block_id": block.id,
            "corridor_id": block.corridor_id,
            "start_ts": block.start_ts.isoformat(),
            "end_ts": block.end_ts.isoformat(),
            "duration_hours": round((block.end_ts - block.start_ts).total_seconds() / 3600.0, 2),
            "block_type": block.block_type.value,
            "depts": block.depts,
            "is_coordinated": len(set(block.depts)) >= 2 if block.depts else False,
            "km_start": float(block.km_start) if block.km_start is not None else None,
            "km_end": float(block.km_end) if block.km_end is not None else None,
            "tasks": tasks_data,
        })

    return {
        "plan_id": plan.id,
        "division": plan.division,
        "horizon": plan.horizon.value,
        "period_start": plan.period_start.isoformat(),
        "period_end": plan.period_end.isoformat(),
        "status": plan.status,
        "planner_kind": plan.planner_kind,
        "objective_value": float(plan.objective_value) if plan.objective_value is not None else None,
        "solver_status": plan.solver_status,
        "solve_ms": plan.solve_ms,
        "blocks": blocks_data,
    }


class WhatIfRequest(BaseModel):
    op: str            # "EXTEND_BLOCK" | "MOVE_BLOCK"
    block_id: int
    delta_min: int     # EXTEND: minutes to add to end; MOVE: signed shift (<0 earlier)
    label: Optional[str] = None


@router.post("/{plan_id}/whatif")
def whatif(plan_id: int, request: WhatIfRequest, db: Session = Depends(get_db)):
    """
    Apply a single EXTEND_BLOCK / MOVE_BLOCK edit and return the recomputed KPIs,
    ripple/cascade traffic impact, and plan score — each with a delta vs the
    unedited plan. The stored plan is never mutated (PRD §12.9).
    """
    try:
        engine = WhatIfEngine(db)
        return engine.simulate(plan_id, {
            "op": request.op,
            "block_id": request.block_id,
            "delta_min": request.delta_min,
            "label": request.label,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"What-if simulation failed: {e}")


@router.get("/{plan_id}/block/{block_id}/why")
def explain_block(plan_id: int, block_id: int, db: Session = Depends(get_db)):
    """
    Explainability (Phase 6): why is this block here? Returns the coordination
    rationale, objective value + block-hours saved, per-task priority drivers,
    and the admissible window that pinned the timing — all from the same logic
    that drove the optimizer (PRD §12.10). Read-only.
    """
    try:
        engine = ExplainEngine(db)
        return engine.explain(plan_id, block_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Explain failed: {e}")


@router.get("/list")
def list_plans(db: Session = Depends(get_db)):
    """List all plans (most recent first)."""
    from app.models import Plan
    plans = db.query(Plan).order_by(Plan.id.desc()).all()
    return [
        {
            "plan_id": p.id,
            "planner_kind": p.planner_kind,
            "status": p.status,
            "objective_value": float(p.objective_value) if p.objective_value is not None else None,
            "solve_ms": p.solve_ms,
            "period_start": p.period_start.isoformat(),
            "period_end": p.period_end.isoformat(),
        }
        for p in plans
    ]

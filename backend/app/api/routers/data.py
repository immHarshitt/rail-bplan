"""
Data generation API endpoint
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict

from app.core.database import get_db
from synth.generator import SyntheticDataGenerator


router = APIRouter()


class GenerateRequest(BaseModel):
    """Request to generate synthetic data"""
    seed: int = 42
    weeks: int = 5
    division: str = "NDLS"


class GenerateResponse(BaseModel):
    """Response from data generation"""
    corridors: int
    stations: int
    track_sections: int
    assets: int
    gangs: int
    requests: int
    trains: int
    train_paths: int
    windows: int
    ground_truth_cases: int
    seed: int


@router.post("/generate", response_model=GenerateResponse)
async def generate_data(request: GenerateRequest, db: Session = Depends(get_db)) -> Dict:
    """
    Generate synthetic railway maintenance data

    Creates internally consistent dataset with:
    - 6 corridors with varied traffic classes
    - ~200 maintenance requests across 3 departments
    - 15-20 planted bundle opportunities
    - Realistic train paths with diurnal patterns
    - Block windows aligned with traffic lean hours
    """
    try:
        # Clear existing data first
        from app.models import (
            PlannedBlockTask, PlannedBlock, Plan, KPISnapshot, Scenario,
            TrainPath, Train, BlockWindow, MaintenanceRequest, Asset,
            ResourceGang, TrackSection, Station, Corridor
        )

        # Delete in order of dependencies
        db.query(PlannedBlockTask).delete()
        db.query(PlannedBlock).delete()
        db.query(Plan).delete()
        db.query(KPISnapshot).delete()
        db.query(Scenario).delete()
        db.query(TrainPath).delete()
        db.query(Train).delete()
        db.query(BlockWindow).delete()
        db.query(MaintenanceRequest).delete()
        db.query(Asset).delete()
        db.query(ResourceGang).delete()
        db.query(TrackSection).delete()
        db.query(Station).delete()
        db.query(Corridor).delete()
        db.commit()

        generator = SyntheticDataGenerator(seed=request.seed)
        result = generator.generate_all(
            db=db,
            division=request.division,
            weeks=request.weeks
        )
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Data generation failed: {str(e)}")


class BackfillResponse(BaseModel):
    """Response from train-path backfill"""
    train_paths: int
    trains: int
    sections: int


@router.post("/backfill-train-paths", response_model=BackfillResponse)
async def backfill_train_paths(db: Session = Depends(get_db)) -> Dict:
    """
    Regenerate ONLY the train_path table for the current dataset.

    The original generator hardcoded corridor_id = randint(1, 6) when picking
    sections for each train, but Postgres SERIAL ids drift after repeated
    /data/generate wipes (corridors are now 8..13), so zero paths ever matched.
    This backfill re-runs the (fixed) path generator against the actual
    corridor/section ids in the DB.

    Touches only train_path — corridors, sections, requests, plans, and the
    locked KPI numbers are untouched (the optimizer does not consume paths).
    Deterministic: fixed RNG seed so the What-If ripple is repeatable on stage.
    """
    import random
    from app.models import Train, TrackSection, TrainPath

    try:
        trains = db.query(Train).order_by(Train.id).all()
        sections = db.query(TrackSection).order_by(TrackSection.id).all()
        if not trains or not sections:
            raise HTTPException(
                status_code=400,
                detail="No trains/sections in DB — run /data/generate first.",
            )

        # Wipe existing paths (there should be 0, but be idempotent)
        db.query(TrainPath).delete()
        db.commit()

        # Deterministic, independent of any prior RNG consumption
        random.seed(20260903)

        generator = SyntheticDataGenerator(seed=20260903)
        paths = generator._generate_train_paths(db, trains, sections)

        return {
            "train_paths": len(paths),
            "trains": len(trains),
            "sections": len(sections),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")


@router.get("/stats")
async def get_data_stats(db: Session = Depends(get_db)) -> Dict:
    """Get current database statistics"""
    from app.models import (
        Corridor, Station, Asset, MaintenanceRequest,
        Train, TrainPath, BlockWindow
    )

    stats = {
        "corridors": db.query(Corridor).count(),
        "stations": db.query(Station).count(),
        "assets": db.query(Asset).count(),
        "maintenance_requests": db.query(MaintenanceRequest).count(),
        "trains": db.query(Train).count(),
        "train_paths": db.query(TrainPath).count(),
        "block_windows": db.query(BlockWindow).count()
    }

    return stats

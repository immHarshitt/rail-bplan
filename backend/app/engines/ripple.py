"""
Ripple / Cascade Model (M5) — PRD §12.9.2

Deterministic event-propagation model that estimates the train-traffic impact of
a single maintenance block. Given a block (corridor, line, km-span, time window,
type), it finds the train paths that would try to cross the blocked section while
it is occupied and computes how they are handled:

  1. Direct impact   — paths on the blocked section within
                       [t_start − headway, t_end + clearance] on the block's DOW.
  2. Divert or hold  — double/multi-line corridor  → single-line working on the
                       open line (trains diverted, queued at headway);
                       single-line corridor / CORRIDOR_BLOCK → HOLD at the nearest
                       upstream loop station until the block clears; no upstream
                       loop → INFEASIBLE (the edit is rejected).
  3. Knock-on        — held/diverted trains discharge at headway spacing, so each
                       train's delay depends on those ahead of it (propagation,
                       capped at D_MAX hops of escalating congestion).
  4. Regulation      — trains released in priority order (protected / passenger
                       first, goods last), so goods absorb the detention.
  5. Aggregate       — trains affected, passenger delay, goods delay / detention,
                       max delay, held vs diverted, feasibility.

Pure and deterministic: every number derives from persisted DB rows + fixed
arithmetic (no RNG, no wall-clock), so the What-If demo is repeatable on stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    Corridor, Station, TrackSection, TrainPath, Train, BlockType,
)
from app.engines.optimizer import _naive


# --- Model constants (PRD §12.9.2) --------------------------------------------
CLEARANCE_MIN = 10        # min gap between block release and the first train
DEFAULT_HEADWAY_MIN = 5   # fallback if a section has no headway set
D_MAX = 6                 # max propagation depth for escalating congestion
GOODS_CLASS = "GOODS"


def _minute_of_day(dt: datetime) -> int:
    dt = _naive(dt)
    return dt.hour * 60 + dt.minute


@dataclass
class AffectedTrain:
    train_id: int
    number: str
    train_class: str
    is_goods: bool
    is_protected: bool
    priority_class: int
    handling: str        # "DIVERT" | "HOLD"
    delay_min: int
    section_id: int


@dataclass
class RippleResult:
    feasible: bool = True
    infeasibility_reason: Optional[str] = None
    mode: str = "CLEAR"          # "DIVERT" | "HOLD" | "CORRIDOR_BLOCK" | "CLEAR"
    trains_affected: int = 0
    passenger_trains: int = 0
    goods_trains: int = 0
    held_trains: int = 0
    diverted_trains: int = 0
    passenger_delay_min: int = 0
    goods_delay_min: int = 0
    goods_detention_hours: float = 0.0
    total_delay_min: int = 0
    max_delay_min: int = 0
    protected_train_hit: bool = False
    n_sections: int = 0
    headway_min: int = DEFAULT_HEADWAY_MIN
    top_trains: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["goods_detention_hours"] = round(self.goods_detention_hours, 2)
        return d


class RippleEngine:
    """Deterministic per-block traffic-impact simulator (M5)."""

    def __init__(self, db: Session):
        self.db = db

    # -- geometry helpers ------------------------------------------------------
    def _sections_for(self, corridor_id: int, km_start: float, km_end: float) -> List[TrackSection]:
        """Track sections on the corridor whose km-span overlaps the block."""
        lo, hi = min(km_start, km_end), max(km_start, km_end)
        return (
            self.db.query(TrackSection)
            .filter(TrackSection.corridor_id == corridor_id)
            .filter(TrackSection.km_start < hi)
            .filter(TrackSection.km_end > lo)
            .all()
        )

    def _has_upstream_loop(self, corridor_id: int, km_start: float) -> bool:
        """Is there a loop-equipped station upstream (lower km) to hold trains at?"""
        stn = (
            self.db.query(Station)
            .filter(Station.corridor_id == corridor_id)
            .filter(Station.km <= km_start)
            .filter(Station.has_loop.is_(True))
            .first()
        )
        return stn is not None

    # -- core simulation -------------------------------------------------------
    def simulate(
        self,
        corridor_id: int,
        km_start: float,
        km_end: float,
        start_ts: datetime,
        end_ts: datetime,
        block_type: str,
    ) -> RippleResult:
        corridor = self.db.query(Corridor).filter(Corridor.id == corridor_id).first()
        if corridor is None:
            return RippleResult(feasible=False, infeasibility_reason="Corridor not found")

        sections = self._sections_for(corridor_id, float(km_start), float(km_end))
        if not sections:
            return RippleResult(mode="CLEAR", n_sections=0)

        sec_ids = [s.id for s in sections]
        headway = max([s.headway_min or DEFAULT_HEADWAY_MIN for s in sections])
        run_time_by_sec = {s.id: (s.run_time_min or 10) for s in sections}

        # Linear minute window anchored at the block-day midnight (handles the
        # common lean-hour block that crosses midnight).
        w_start = _minute_of_day(start_ts)
        duration_min = int((_naive(end_ts) - _naive(start_ts)).total_seconds() // 60)
        w_end = w_start + duration_min
        eff_start = w_start - headway
        eff_end = w_end + CLEARANCE_MIN

        # Determine handling mode.
        is_corridor_block = str(block_type) in (BlockType.CORRIDOR_BLOCK.value, "CORRIDOR_BLOCK")
        divertible = (corridor.n_lines or 2) >= 2 and not is_corridor_block

        if not divertible:
            # HOLD mode needs somewhere upstream to hold.
            if not self._has_upstream_loop(corridor_id, float(km_start)):
                return RippleResult(
                    feasible=False,
                    mode="CORRIDOR_BLOCK" if is_corridor_block else "HOLD",
                    infeasibility_reason=(
                        "Single-line block with no upstream loop station to hold trains — "
                        "would strand traffic (INFEASIBLE)."
                    ),
                    n_sections=len(sections),
                    headway_min=headway,
                )

        # Collect affected train paths. Paths recur daily (dow_mask=127); check the
        # day-1 / day / day+1 occurrences so trains near the midnight wrap are caught.
        rows = (
            self.db.query(TrainPath, Train)
            .join(Train, Train.id == TrainPath.train_id)
            .filter(TrainPath.section_id.in_(sec_ids))
            .all()
        )

        affected: List[AffectedTrain] = []
        seen_trains = set()
        for tp, train in rows:
            rt = run_time_by_sec.get(tp.section_id, 10)
            e0 = tp.entry_min
            occ = None
            for day_off in (-1, 0, 1):
                e_lin = e0 + day_off * 1440
                x_lin = e_lin + rt
                if e_lin < eff_end and x_lin > eff_start:
                    occ = e_lin
                    break
            if occ is None:
                continue
            # One entry per train (earliest crossing) to avoid double-count when a
            # train spans several blocked sections.
            if train.id in seen_trains:
                continue
            seen_trains.add(train.id)
            is_goods = train.train_class == GOODS_CLASS
            affected.append(AffectedTrain(
                train_id=train.id, number=train.number, train_class=train.train_class,
                is_goods=is_goods, is_protected=bool(train.is_protected),
                priority_class=train.priority_class, handling="", delay_min=0,
                section_id=tp.section_id,
            ))
            affected[-1]._entry = occ  # type: ignore[attr-defined]

        if not affected:
            return RippleResult(mode="DIVERT" if divertible else "HOLD",
                                n_sections=len(sections), headway_min=headway)

        # Regulation order: protected first, then by priority_class asc (1=highest),
        # goods last; tie-break by natural entry time. Deterministic.
        affected.sort(key=lambda a: (
            0 if a.is_protected else 1,
            1 if a.is_goods else 0,
            a.priority_class,
            a._entry,  # type: ignore[attr-defined]
        ))

        result = RippleResult(
            mode="DIVERT" if divertible else "HOLD",
            n_sections=len(sections),
            headway_min=headway,
        )

        if divertible:
            # Single-line working on the open line: trains pass but are metered at
            # `headway` spacing. Server-queue discharge in regulation order.
            free_at = eff_start
            for i, a in enumerate(affected):
                entry = a._entry  # type: ignore[attr-defined]
                start_service = max(entry, free_at)
                # Escalating congestion capped at D_MAX positions deep.
                depth = min(i, D_MAX)
                delay = max(0, start_service - entry) + (headway if depth > 0 else 0)
                free_at = start_service + headway
                a.handling = "DIVERT"
                a.delay_min = int(round(delay))
        else:
            # HOLD: nothing moves through until the block clears; then the queue
            # discharges from the upstream loop at headway spacing in priority order.
            release = w_end + CLEARANCE_MIN
            for i, a in enumerate(affected):
                entry = a._entry  # type: ignore[attr-defined]
                depart = release + i * headway
                delay = max(0, depart - entry)
                a.handling = "HOLD"
                a.delay_min = int(round(delay))

        # Aggregate.
        for a in affected:
            result.trains_affected += 1
            if a.handling == "HOLD":
                result.held_trains += 1
            else:
                result.diverted_trains += 1
            if a.is_goods:
                result.goods_trains += 1
                result.goods_delay_min += a.delay_min
            else:
                result.passenger_trains += 1
                result.passenger_delay_min += a.delay_min
            if a.is_protected and a.delay_min > 0:
                result.protected_train_hit = True
            result.total_delay_min += a.delay_min
            result.max_delay_min = max(result.max_delay_min, a.delay_min)

        result.goods_detention_hours = result.goods_delay_min / 60.0

        # Top affected trains for the UI (most-delayed first).
        top = sorted(affected, key=lambda a: -a.delay_min)[:6]
        result.top_trains = [{
            "number": a.number,
            "train_class": a.train_class,
            "handling": a.handling,
            "delay_min": a.delay_min,
            "is_goods": a.is_goods,
            "is_protected": a.is_protected,
        } for a in top]

        return result

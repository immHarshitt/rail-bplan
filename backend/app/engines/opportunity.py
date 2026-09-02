"""
Opportunity Engine (M4) - Phase 2
Generates bundle candidates: groups of maintenance tasks that can share a
single maintenance block because they are spatially close on the same corridor.

A bundle's value comes from coordination - multiple departments (or multiple
tasks) sharing ONE track closure instead of many. Bundle duration follows
PRD §12.4:  T_protect + max_over_depts(Σ dept task durations) + T_release
(tasks in the same dept serialize on one gang; different depts work in parallel).
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import math

from app.models import MaintenanceRequest, BlockType
from app.engines.optimizer import SLOT_MINUTES, T_PROTECT_MIN, T_RELEASE_MIN, priority_of
from datetime import datetime

BUNDLE_RADIUS_KM = 8.0   # ~1 block section (avg inter-station spacing is 9.6km); see D15
MAX_BUNDLE_SIZE = 5
MAX_CANDIDATES_PER_CORRIDOR = 200  # generous: model solves in <0.2s; singletons are separate
COORDINATION_BONUS_PER_EXTRA_DEPT = 300  # objective bonus for each dept beyond the first


# Block-type compatibility: which types can co-exist in one shared closure.
# Phase 2 simplification: TRAFFIC/POWER/DISCONNECTION are mutually compatible
# (a corridor block can host them); CORRIDOR_BLOCK is a full closure (compatible too).
_COMPATIBLE = {
    BlockType.TRAFFIC_BLOCK, BlockType.POWER_BLOCK,
    BlockType.DISCONNECTION, BlockType.CORRIDOR_BLOCK,
}


@dataclass
class BundleCandidate:
    """A candidate maintenance block covering one or more tasks."""
    key: str                              # stable id, e.g. "b:157" or "s:202"
    corridor_id: int
    task_ids: List[int]
    requests: List[MaintenanceRequest] = field(repr=False, default_factory=list)
    duration_slots: int = 0
    duration_min: int = 0
    value: float = 0.0                    # ranking value (priority + coordination)
    base_priority: float = 0.0            # sum of task priorities (no coordination bonus)
    n_extra_depts: int = 0                # depts beyond the first (for coordination reward)
    depts: List[str] = field(default_factory=list)
    km_from: float = 0.0
    km_to: float = 0.0
    block_type: str = "TRAFFIC_BLOCK"

    @property
    def is_multi_dept(self) -> bool:
        return len(set(self.depts)) >= 2

    @property
    def size(self) -> int:
        return len(self.task_ids)


def _bundle_minutes(requests: List[MaintenanceRequest]) -> int:
    """
    PRD §12.4 duration: same-dept tasks serialize on one gang (sum);
    different depts work in parallel (max across depts). Plus protect/release.
    Slot-rounded to match the optimizer's time model (D13).
    """
    by_dept: Dict[str, int] = {}
    needs_power = False
    for r in requests:
        by_dept[r.dept.value] = by_dept.get(r.dept.value, 0) + (r.est_duration_min or 60)
        needs_power = needs_power or bool(r.needs_power_block)

    work = max(by_dept.values()) if by_dept else 60
    protect = T_PROTECT_MIN + (15 if needs_power else 0)
    release = T_RELEASE_MIN + (10 if needs_power else 0)
    raw = protect + work + release
    return int(math.ceil(raw / SLOT_MINUTES) * SLOT_MINUTES)


def _dominant_block_type(requests: List[MaintenanceRequest]) -> str:
    """Pick the 'largest' required block type for the shared closure."""
    order = [BlockType.CORRIDOR_BLOCK, BlockType.POWER_BLOCK,
             BlockType.TRAFFIC_BLOCK, BlockType.DISCONNECTION]
    present = {r.required_block for r in requests}
    for t in order:
        if t in present:
            return t.value
    return BlockType.TRAFFIC_BLOCK.value


def _compatible(requests: List[MaintenanceRequest]) -> bool:
    return all(r.required_block in _COMPATIBLE for r in requests)


class OpportunityEngine:
    """Generates standalone + bundled candidates for the optimizer."""

    def __init__(
        self,
        horizon_start: datetime,
        radius_km: float = BUNDLE_RADIUS_KM,
        max_bundle_size: int = MAX_BUNDLE_SIZE,
    ):
        self.horizon_start = horizon_start
        self.radius_km = radius_km
        self.max_bundle_size = max_bundle_size

    def generate(self, requests: List[MaintenanceRequest]) -> List[BundleCandidate]:
        candidates: List[BundleCandidate] = []

        # 1. Always include a singleton candidate per task (guarantees feasibility)
        for r in requests:
            candidates.append(self._make_candidate(f"s:{r.id}", [r]))

        # 2. Spatial bundle candidates, per corridor
        by_corridor: Dict[int, List[MaintenanceRequest]] = {}
        for r in requests:
            by_corridor.setdefault(r.corridor_id, []).append(r)

        for cid, reqs in by_corridor.items():
            reqs_sorted = sorted(reqs, key=lambda r: float(r.km_from))
            bundle_keys = set()
            corridor_bundles: List[BundleCandidate] = []

            # Sliding anchor: from each anchor, grow a contiguous cluster and
            # emit a candidate at EVERY size >= 2 (all contiguous sub-bundles).
            # Emitting sub-bundles — not just the maximal cluster — lets the
            # optimizer pick the largest bundle that actually fits a window;
            # otherwise an over-long maximal cluster forces a fallback all the
            # way to singletons, losing block-hour savings (K5).
            for i, anchor in enumerate(reqs_sorted):
                cluster = [anchor]
                for j in range(i + 1, len(reqs_sorted)):
                    if float(reqs_sorted[j].km_from) - float(anchor.km_from) > self.radius_km:
                        break
                    cluster.append(reqs_sorted[j])

                    if not _compatible(cluster):
                        break  # incompatible member: stop growing this anchor

                    task_ids = tuple(sorted(r.id for r in cluster))
                    if task_ids not in bundle_keys:
                        bundle_keys.add(task_ids)
                        key = "b:" + "-".join(str(t) for t in task_ids)
                        corridor_bundles.append(self._make_candidate(key, list(cluster)))

                    if len(cluster) >= self.max_bundle_size:
                        break

            # Cap candidates per corridor: keep the highest-value bundles
            corridor_bundles.sort(key=lambda c: c.value, reverse=True)
            candidates.extend(corridor_bundles[:MAX_CANDIDATES_PER_CORRIDOR])

        return candidates

    def _make_candidate(self, key: str, requests: List[MaintenanceRequest]) -> BundleCandidate:
        duration_min = _bundle_minutes(requests)
        depts = [r.dept.value for r in requests]
        base_value = sum(priority_of(r, self.horizon_start) for r in requests)
        n_extra_depts = max(0, len(set(depts)) - 1)
        value = base_value + n_extra_depts * COORDINATION_BONUS_PER_EXTRA_DEPT

        kms = [float(r.km_from) for r in requests] + [float(r.km_to) for r in requests]
        return BundleCandidate(
            key=key,
            corridor_id=requests[0].corridor_id,
            task_ids=[r.id for r in requests],
            requests=list(requests),
            duration_min=duration_min,
            duration_slots=max(1, duration_min // SLOT_MINUTES),
            value=value,
            base_priority=base_value,
            n_extra_depts=n_extra_depts,
            depts=depts,
            km_from=min(kms),
            km_to=max(kms),
            block_type=_dominant_block_type(requests),
        )

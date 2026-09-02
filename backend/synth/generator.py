"""
Synthetic data generator for RAIL-OPT
Based on PRD §11 - generates internally consistent railway maintenance data

Decision D8: 200 requests (not 600) for initial demo
"""
import random
from datetime import date, timedelta, datetime
from typing import List, Dict, Tuple
import json
from sqlalchemy.orm import Session

from app.models import (
    Corridor, Station, TrackSection, Asset, MaintenanceRequest,
    ResourceGang, BlockWindow, Train, TrainPath,
    Dept, SrcSystem, BlockType, ReqStatus, LineType, TrafficClass
)


class SyntheticDataGenerator:
    """Generate consistent synthetic railway data for demo"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        self.ground_truth = {
            "bundle_opportunities": [],
            "shadow_candidates": [],
            "hard_cases": []
        }

    def generate_all(self, db: Session, division: str = "NDLS", weeks: int = 5) -> Dict:
        """Generate complete synthetic dataset"""
        print(f"🌱 Generating synthetic data (seed={self.seed}, division={division})")

        # 1. Generate corridors (6 per PRD)
        corridors = self._generate_corridors(db, division)
        print(f"✓ Generated {len(corridors)} corridors")

        # 2. Generate stations (8 per corridor)
        stations = self._generate_stations(db, corridors)
        print(f"✓ Generated {len(stations)} stations")

        # 3. Generate track sections
        track_sections = self._generate_track_sections(db, corridors, stations)
        print(f"✓ Generated {len(track_sections)} track sections")

        # 4. Generate assets (~800 total)
        assets = self._generate_assets(db, corridors)
        print(f"✓ Generated {len(assets)} assets")

        # 5. Generate gangs
        gangs = self._generate_gangs(db, corridors)
        print(f"✓ Generated {len(gangs)} maintenance gangs")

        # 6. Generate maintenance requests (~200)
        requests = self._generate_maintenance_requests(db, corridors, assets, weeks)
        print(f"✓ Generated {len(requests)} maintenance requests")

        # 7. Plant bundle opportunities
        self._plant_bundle_opportunities(db, corridors, requests)
        print(f"✓ Planted {len(self.ground_truth['bundle_opportunities'])} bundle opportunities")

        # 8. Generate trains
        trains = self._generate_trains(db)
        print(f"✓ Generated {len(trains)} trains")

        # 9. Generate train paths
        train_paths = self._generate_train_paths(db, trains, track_sections)
        print(f"✓ Generated {len(train_paths)} train paths")

        # 10. Generate block windows
        windows = self._generate_block_windows(db, corridors, weeks)
        print(f"✓ Generated {len(windows)} block windows")

        # Save ground truth
        import os
        ground_truth_path = "data/ground_truth.json"
        os.makedirs(os.path.dirname(ground_truth_path), exist_ok=True)
        with open(ground_truth_path, 'w') as f:
            json.dump(self.ground_truth, f, indent=2, default=str)

        return {
            "corridors": len(corridors),
            "stations": len(stations),
            "track_sections": len(track_sections),
            "assets": len(assets),
            "gangs": len(gangs),
            "requests": len(requests),
            "trains": len(trains),
            "train_paths": len(train_paths),
            "windows": len(windows),
            "ground_truth_cases": len(self.ground_truth['bundle_opportunities']),
            "seed": self.seed
        }

    def _generate_corridors(self, db: Session, division: str) -> List[Corridor]:
        """Generate 6 corridors with varied characteristics"""
        corridor_specs = [
            ("NDLS-GZB-UP", "New Delhi - Ghaziabad UP", 0.0, 70.0, LineType.DOUBLE, TrafficClass.HIGH),
            ("NDLS-GZB-DN", "New Delhi - Ghaziabad DN", 0.0, 70.0, LineType.DOUBLE, TrafficClass.HIGH),
            ("GZB-MB-MAIN", "Ghaziabad - Modinagar Main", 70.0, 140.0, LineType.DOUBLE, TrafficClass.MEDIUM),
            ("MB-HPU-SINGLE", "Modinagar - Hapur Single", 140.0, 195.0, LineType.SINGLE, TrafficClass.LOW),
            ("HPU-MUT-LOOP", "Hapur - Meerut Loop", 195.0, 265.0, LineType.DOUBLE, TrafficClass.MEDIUM),
            ("MUT-SRE-GOODS", "Meerut - Saharanpur Goods", 265.0, 335.0, LineType.DOUBLE, TrafficClass.LOW),
        ]

        corridors = []
        for code, name, km_start, km_end, line_type, traffic in corridor_specs:
            corridor = Corridor(
                code=code,
                name=name,
                division=division,
                km_start=km_start,
                km_end=km_end,
                line_type=line_type,
                n_lines=1 if line_type == LineType.SINGLE else 2,
                electrified=True,
                max_speed_kmph=110 if traffic == TrafficClass.HIGH else 90,
                traffic_class=traffic
            )
            db.add(corridor)
            corridors.append(corridor)

        db.commit()
        for c in corridors:
            db.refresh(c)
        return corridors

    def _generate_stations(self, db: Session, corridors: List[Corridor]) -> List[Station]:
        """Generate ~8 stations per corridor"""
        stations = []
        station_counter = 1

        for corridor in corridors:
            km_range = float(corridor.km_end - corridor.km_start)
            n_stations = 8
            interval = km_range / (n_stations - 1)

            for i in range(n_stations):
                km = float(corridor.km_start) + (i * interval)
                code = f"ST{station_counter:02d}"
                is_junction = (i == 0 or i == n_stations - 1)

                station = Station(
                    code=code,
                    name=f"Station {code}",
                    corridor_id=corridor.id,
                    km=km,
                    is_junction=is_junction,
                    n_platforms=3 if is_junction else 2,
                    has_loop=corridor.traffic_class != TrafficClass.HIGH or i % 2 == 0
                )
                db.add(station)
                stations.append(station)
                station_counter += 1

        db.commit()
        return stations

    def _generate_track_sections(self, db: Session, corridors: List[Corridor],
                                  stations: List[Station]) -> List[TrackSection]:
        """Generate track sections between consecutive stations"""
        sections = []

        # Group stations by corridor
        for corridor in corridors:
            corridor_stations = [s for s in stations if s.corridor_id == corridor.id]
            corridor_stations.sort(key=lambda s: s.km)

            for i in range(len(corridor_stations) - 1):
                from_stn = corridor_stations[i]
                to_stn = corridor_stations[i + 1]
                km_diff = float(to_stn.km - from_stn.km)
                run_time = int(km_diff / 60 * 60)  # ~60 kmph average

                # Create section for each line
                for line_no in range(1, corridor.n_lines + 1):
                    section = TrackSection(
                        corridor_id=corridor.id,
                        from_stn=from_stn.code,
                        to_stn=to_stn.code,
                        line_no=line_no,
                        km_start=from_stn.km,
                        km_end=to_stn.km,
                        run_time_min=run_time,
                        headway_min=5 if corridor.traffic_class == TrafficClass.HIGH else 8,
                        bidirectional=corridor.line_type == LineType.SINGLE
                    )
                    db.add(section)
                    sections.append(section)

        db.commit()
        return sections

    def _generate_assets(self, db: Session, corridors: List[Corridor]) -> List[Asset]:
        """Generate ~800 assets across corridors"""
        assets = []
        asset_types_by_dept = {
            Dept.ENGG: ["RAIL", "WELD", "TURNOUT", "LC_GATE", "SLEEPER"],
            Dept.SNT: ["SIGNAL", "POINT_MACHINE", "TRACK_CIRCUIT", "AXLE_COUNTER", "IPS"],
            Dept.TRD: ["OHE_SPAN", "INSULATOR", "ISOLATOR", "FEEDER", "NEUTRAL_SECTION"]
        }

        target_per_corridor = 130

        for corridor in corridors:
            km_range = float(corridor.km_end - corridor.km_start)

            for dept, asset_types in asset_types_by_dept.items():
                n_assets = target_per_corridor // 3

                for i in range(n_assets):
                    asset_type = random.choice(asset_types)
                    km_from = float(corridor.km_start) + random.uniform(0, km_range)
                    km_span = 0.05 if asset_type in ["SIGNAL", "LC_GATE"] else random.uniform(0.1, 2.0)

                    # Age determines condition
                    install_years_ago = random.randint(1, 25)
                    install_date = date.today() - timedelta(days=install_years_ago * 365)
                    last_overhaul_years = random.randint(0, min(5, install_years_ago))
                    last_overhaul = date.today() - timedelta(days=last_overhaul_years * 365)

                    # Condition degrades with age and GMT
                    age_factor = 1.0 - (install_years_ago / 30)
                    overhaul_boost = 0.3 if last_overhaul_years < 2 else 0
                    condition = max(0.3, min(1.0, age_factor + overhaul_boost + random.uniform(-0.1, 0.1)))

                    asset = Asset(
                        source_system=SrcSystem.SYNTH,
                        source_id=f"SYNTH-{dept.value}-{len(assets)+1:04d}",
                        dept=dept,
                        asset_type=asset_type,
                        corridor_id=corridor.id,
                        km_from=km_from,
                        km_to=km_from + km_span,
                        line_no=random.randint(1, corridor.n_lines),
                        install_date=install_date,
                        last_overhaul=last_overhaul,
                        criticality=random.choices([1,2,3,4,5], weights=[5,15,40,30,10])[0],
                        condition_index=condition,
                        gmt=random.uniform(50, 500) if dept == Dept.ENGG else None
                    )
                    db.add(asset)
                    assets.append(asset)

        db.commit()
        for a in assets:
            db.refresh(a)
        return assets

    def _generate_gangs(self, db: Session, corridors: List[Corridor]) -> List[ResourceGang]:
        """Generate maintenance gangs"""
        gangs = []
        depot_stations = ["ST01", "ST08", "ST16", "ST24", "ST32", "ST40"]

        for i, dept in enumerate([Dept.ENGG, Dept.ENGG, Dept.SNT, Dept.TRD]):
            gang = ResourceGang(
                dept=dept,
                code=f"{dept.value}-GANG-{i+1}",
                depot_stn=depot_stations[i] if i < len(depot_stations) else "ST01",
                strength=random.randint(8, 15),
                corridor_scope=[c.id for c in corridors[i:i+3]],  # Overlapping scopes
                shift_start_min=0,
                shift_end_min=1440,
                travel_buffer_min=30
            )
            db.add(gang)
            gangs.append(gang)

        db.commit()
        return gangs

    def _generate_maintenance_requests(self, db: Session, corridors: List[Corridor],
                                        assets: List[Asset], weeks: int) -> List[MaintenanceRequest]:
        """Generate ~200 maintenance requests (Decision D8)"""
        requests = []
        today = date.today()
        target_count = 200

        # Distribution: 60% ENGG, 25% SNT, 15% TRD
        dept_targets = {
            Dept.ENGG: int(target_count * 0.60),
            Dept.SNT: int(target_count * 0.25),
            Dept.TRD: int(target_count * 0.15)
        }

        task_codes_by_dept = {
            Dept.ENGG: ["TAMPING", "USFD_WELD", "RAIL_RENEWAL", "TURNOUT_OVH", "LC_REPAIR"],
            Dept.SNT: ["SIG_GEAR_OVH", "RELAY_TEST", "TRACK_CKT_ADJ", "POINT_MACH_OVH"],
            Dept.TRD: ["OHE_TENSION", "INSULATOR_CLEAN", "FEEDER_TEST", "ISOLATOR_OVH"]
        }

        for dept, target in dept_targets.items():
            dept_assets = [a for a in assets if a.dept == dept]

            for i in range(target):
                asset = random.choice(dept_assets)
                task_code = random.choice(task_codes_by_dept[dept])

                # Task kind distribution
                task_kind = random.choices(
                    ["DEFECT", "SCHEDULED", "OVERDUE", "INSPECTION"],
                    weights=[30, 45, 20, 5]
                )[0]

                # Severity for defects
                defect_severity = None
                if task_kind == "DEFECT":
                    # Correlated with asset condition
                    severity_prob = 1.0 - float(asset.condition_index or 0.7)
                    defect_severity = min(5, int(severity_prob * 6))

                # Due date (spread over next 5 weeks)
                if task_kind == "OVERDUE":
                    due_on = today - timedelta(days=random.randint(1, 30))
                else:
                    due_on = today + timedelta(days=random.randint(0, weeks * 7))

                # Duration
                est_duration_min = random.choice([30, 45, 60, 90, 120])

                # Block type
                if dept == Dept.TRD:
                    required_block = BlockType.POWER_BLOCK
                    needs_power_block = True
                elif dept == Dept.SNT and random.random() < 0.3:
                    required_block = BlockType.DISCONNECTION
                    needs_disconnection = True
                else:
                    required_block = BlockType.TRAFFIC_BLOCK
                    needs_power_block = False
                    needs_disconnection = False

                request = MaintenanceRequest(
                    source_system=SrcSystem.SYNTH,
                    source_id=f"REQ-{len(requests)+1:04d}",
                    dept=dept,
                    asset_id=asset.id,
                    corridor_id=asset.corridor_id,
                    km_from=asset.km_from,
                    km_to=asset.km_to,
                    task_code=task_code,
                    task_kind=task_kind,
                    description=f"{task_code} at KM {float(asset.km_from):.1f}",
                    defect_severity=defect_severity,
                    raised_on=today - timedelta(days=random.randint(1, 60)),
                    due_on=due_on,
                    periodicity_days=random.choice([30, 60, 90, 180]) if task_kind == "SCHEDULED" else None,
                    last_done_on=asset.last_overhaul,
                    est_duration_min=est_duration_min,
                    required_block=required_block,
                    needs_power_block=needs_power_block,
                    needs_disconnection=needs_disconnection,
                    gang_dept=dept,
                    status=ReqStatus.OVERDUE if task_kind == "OVERDUE" else ReqStatus.OPEN
                )
                db.add(request)
                requests.append(request)

        db.commit()
        for r in requests:
            db.refresh(r)
        return requests

    def _plant_bundle_opportunities(self, db: Session, corridors: List[Corridor],
                                     requests: List[MaintenanceRequest]):
        """Plant 15-20 deliberate bundle opportunities for validation"""
        # Find existing clusters that naturally formed
        opportunities_found = 0

        for corridor in corridors[:4]:  # Check first 4 corridors
            corridor_requests = [r for r in requests if r.corridor_id == corridor.id]

            # Sort by km
            corridor_requests.sort(key=lambda r: float(r.km_from))

            # Look for potential bundles (within 5km, different depts)
            for i, req1 in enumerate(corridor_requests):
                cluster = [req1]
                for req2 in corridor_requests[i+1:]:
                    gap = float(req2.km_from) - float(req1.km_to)
                    if gap <= 5.0 and req2.dept != req1.dept:
                        cluster.append(req2)

                if len(cluster) >= 2:
                    depts = list(set([r.dept.value for r in cluster]))
                    if len(depts) >= 2:
                        self.ground_truth["bundle_opportunities"].append({
                            "corridor_id": corridor.id,
                            "corridor_code": corridor.code,
                            "request_ids": [r.id for r in cluster],
                            "departments": depts,
                            "km_span": (float(cluster[0].km_from), float(cluster[-1].km_to)),
                            "task_count": len(cluster)
                        })
                        opportunities_found += 1
                        if opportunities_found >= 20:
                            return

    def _generate_trains(self, db: Session) -> List[Train]:
        """Generate ~180 trains (120 passenger + 60 goods)"""
        trains = []

        # Passenger trains
        passenger_classes = ["RAJ_SHTB", "MAIL_EXP", "PASS_MEMU"]
        for i in range(120):
            train_class = random.choice(passenger_classes)
            is_protected = (train_class == "RAJ_SHTB" and random.random() < 0.3)

            train = Train(
                number=f"1{i+1:04d}",
                name=f"Train {i+1}",
                train_class=train_class,
                priority_class=1 if train_class == "RAJ_SHTB" else 2,
                is_protected=is_protected
            )
            db.add(train)
            trains.append(train)

        # Goods trains
        for i in range(60):
            train = Train(
                number=f"5{i+1:04d}",
                name=f"Goods {i+1}",
                train_class="GOODS",
                priority_class=4,
                is_protected=False
            )
            db.add(train)
            trains.append(train)

        db.commit()
        for t in trains:
            db.refresh(t)
        return trains

    def _generate_train_paths(self, db: Session, trains: List[Train],
                               sections: List[TrackSection]) -> List[TrainPath]:
        """Generate train paths with diurnal pattern"""
        paths = []

        # Diurnal curve: peaks at 6-11 and 16-22, lean at 0:30-4:30
        peak_hours = list(range(6, 12)) + list(range(16, 23))
        lean_hours = list(range(0, 5))

        # Group sections by their ACTUAL corridor_id (SERIAL ids drift across
        # regenerations, so never assume 1..6). Only corridors that actually
        # have sections are eligible.
        sections_by_corridor: Dict[int, List[TrackSection]] = {}
        for s in sections:
            sections_by_corridor.setdefault(s.corridor_id, []).append(s)
        # Deterministic order: sort each corridor's sections by km so a path
        # runs through physically consecutive sections.
        for cid in sections_by_corridor:
            sections_by_corridor[cid].sort(key=lambda s: float(s.km_start))
        eligible_corridor_ids = sorted(sections_by_corridor.keys())
        if not eligible_corridor_ids:
            return paths

        for train in trains:
            is_passenger = train.train_class != "GOODS"

            # Choose start time based on type
            if is_passenger:
                start_hour = random.choice(peak_hours)
            else:
                # Goods trains prefer lean hours
                start_hour = random.choice(lean_hours + list(range(12, 16)))

            entry_min = start_hour * 60 + random.randint(0, 59)

            # Pick a real corridor that has sections
            corridor_id = random.choice(eligible_corridor_ids)
            corridor_sections = sections_by_corridor[corridor_id]

            if not corridor_sections:
                continue

            # Create path through 3-5 consecutive sections
            n_sections = random.randint(3, min(5, len(corridor_sections)))
            start_idx = random.randint(0, len(corridor_sections) - n_sections)
            selected_sections = corridor_sections[start_idx:start_idx + n_sections]

            current_min = entry_min
            for section in selected_sections:
                path = TrainPath(
                    train_id=train.id,
                    section_id=section.id,
                    entry_min=current_min % 1440,
                    exit_min=(current_min + section.run_time_min) % 1440,
                    dow_mask=127,  # All days
                    slack_min=random.choice([0, 2, 5])
                )
                db.add(path)
                paths.append(path)
                current_min += section.run_time_min

        db.commit()
        return paths

    def _generate_block_windows(self, db: Session, corridors: List[Corridor],
                                 weeks: int) -> List[BlockWindow]:
        """Generate available maintenance windows"""
        windows = []
        today = date.today()

        for corridor in corridors:
            # Generate windows for each night over the period
            for day_offset in range(weeks * 7):
                window_date = today + timedelta(days=day_offset)

                # Night window (varies by traffic class)
                if corridor.traffic_class == TrafficClass.HIGH:
                    # Narrow window: 00:30 - 04:30
                    start_hour, end_hour = 0.5, 4.5
                elif corridor.traffic_class == TrafficClass.MEDIUM:
                    # Medium window: 23:00 - 05:00
                    start_hour, end_hour = 23.0, 29.0  # crosses midnight
                else:
                    # Wide window: 22:00 - 06:00
                    start_hour, end_hour = 22.0, 30.0

                start_ts = datetime.combine(window_date, datetime.min.time())
                start_ts = start_ts.replace(hour=int(start_hour), minute=int((start_hour % 1) * 60))

                end_ts = start_ts + timedelta(hours=end_hour - start_hour)

                window = BlockWindow(
                    corridor_id=corridor.id,
                    km_start=corridor.km_start,
                    km_end=corridor.km_end,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    window_kind="TRAFFIC_LEAN",
                    allowed_block_types=["TRAFFIC_BLOCK", "POWER_BLOCK", "DISCONNECTION"],
                    source=SrcSystem.COA
                )
                db.add(window)
                windows.append(window)

        db.commit()
        return windows

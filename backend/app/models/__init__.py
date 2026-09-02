"""
SQLAlchemy models for RAIL-OPT
Based on PRD §9 canonical data model
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, Date, DateTime,
    ForeignKey, Text, ARRAY, Enum as SQLEnum, CheckConstraint,
    func, Numeric, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
import enum
from datetime import datetime


# Enums (from PRD §9)
class Dept(str, enum.Enum):
    ENGG = "ENGG"
    SNT = "SNT"
    TRD = "TRD"


class SrcSystem(str, enum.Enum):
    TMS = "TMS"
    SMMS = "SMMS"
    TDMS = "TDMS"
    BDMS = "BDMS"
    COA = "COA"
    TT = "TT"
    FREIGHT = "FREIGHT"
    SYNTH = "SYNTH"


class BlockType(str, enum.Enum):
    TRAFFIC_BLOCK = "TRAFFIC_BLOCK"
    POWER_BLOCK = "POWER_BLOCK"
    DISCONNECTION = "DISCONNECTION"
    CORRIDOR_BLOCK = "CORRIDOR_BLOCK"


class ReqStatus(str, enum.Enum):
    OPEN = "OPEN"
    OVERDUE = "OVERDUE"
    PLANNED = "PLANNED"
    SANCTIONED = "SANCTIONED"
    DONE = "DONE"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"


class Horizon(str, enum.Enum):
    MONTH = "MONTH"
    WEEK = "WEEK"
    DAY = "DAY"


class LineType(str, enum.Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    MULTI = "MULTI"


class TrafficClass(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Models
class Corridor(Base):
    """Railway corridor/section (PRD §9)"""
    __tablename__ = "corridor"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    division = Column(String(100), nullable=False)
    km_start = Column(Numeric(8, 3), nullable=False)
    km_end = Column(Numeric(8, 3), nullable=False)
    line_type = Column(SQLEnum(LineType), nullable=False)
    n_lines = Column(Integer, nullable=False, default=2)
    electrified = Column(Boolean, nullable=False, default=True)
    max_speed_kmph = Column(Integer, nullable=False, default=110)
    traffic_class = Column(SQLEnum(TrafficClass), nullable=False)

    # Relationships
    stations = relationship("Station", back_populates="corridor")
    track_sections = relationship("TrackSection", back_populates="corridor")
    assets = relationship("Asset", back_populates="corridor")
    maintenance_requests = relationship("MaintenanceRequest", back_populates="corridor")


class Station(Base):
    """Railway station (PRD §9)"""
    __tablename__ = "station"

    code = Column(String(10), primary_key=True)
    name = Column(String(200), nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridor.id"))
    km = Column(Numeric(8, 3), nullable=False)
    is_junction = Column(Boolean, default=False)
    n_platforms = Column(Integer, default=2)
    has_loop = Column(Boolean, default=True)

    # Relationships
    corridor = relationship("Corridor", back_populates="stations")


class TrackSection(Base):
    """Track section between stations (PRD §9)"""
    __tablename__ = "track_section"

    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(Integer, ForeignKey("corridor.id"))
    from_stn = Column(String(10), ForeignKey("station.code"))
    to_stn = Column(String(10), ForeignKey("station.code"))
    line_no = Column(Integer, nullable=False, default=1)
    km_start = Column(Numeric(8, 3), nullable=False)
    km_end = Column(Numeric(8, 3), nullable=False)
    run_time_min = Column(Integer, nullable=False)
    headway_min = Column(Integer, nullable=False, default=5)
    bidirectional = Column(Boolean, default=False)

    # Relationships
    corridor = relationship("Corridor", back_populates="track_sections")


class Asset(Base):
    """Railway asset (track, signal, OHE, etc.) (PRD §9)"""
    __tablename__ = "asset"

    id = Column(Integer, primary_key=True, index=True)
    source_system = Column(SQLEnum(SrcSystem), nullable=False)
    source_id = Column(String(100), nullable=False)
    dept = Column(SQLEnum(Dept), nullable=False)
    asset_type = Column(String(50), nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridor.id"))
    km_from = Column(Numeric(8, 3), nullable=False)
    km_to = Column(Numeric(8, 3), nullable=False)
    line_no = Column(Integer)
    install_date = Column(Date)
    last_overhaul = Column(Date)
    criticality = Column(Integer, nullable=False)
    condition_index = Column(Numeric(4, 3))  # 0..1
    gmt = Column(Numeric(8, 2))  # gross million tonnes

    __table_args__ = (
        CheckConstraint('criticality BETWEEN 1 AND 5', name='check_criticality'),
    )

    # Relationships
    corridor = relationship("Corridor", back_populates="assets")
    maintenance_requests = relationship("MaintenanceRequest", back_populates="asset")


class ResourceGang(Base):
    """Maintenance gang/crew (PRD §9)"""
    __tablename__ = "resource_gang"

    id = Column(Integer, primary_key=True, index=True)
    dept = Column(SQLEnum(Dept), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    depot_stn = Column(String(10), ForeignKey("station.code"))
    strength = Column(Integer, nullable=False)
    corridor_scope = Column(ARRAY(Integer), nullable=False)  # corridor IDs
    shift_start_min = Column(Integer, nullable=False, default=0)
    shift_end_min = Column(Integer, nullable=False, default=1440)
    travel_buffer_min = Column(Integer, nullable=False, default=30)


class MaintenanceRequest(Base):
    """Maintenance task/request (PRD §9)"""
    __tablename__ = "maintenance_request"

    id = Column(Integer, primary_key=True, index=True)
    source_system = Column(SQLEnum(SrcSystem), nullable=False)
    source_id = Column(String(100), nullable=False)
    dept = Column(SQLEnum(Dept), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("asset.id"))
    corridor_id = Column(Integer, ForeignKey("corridor.id"), index=True)
    km_from = Column(Numeric(8, 3), nullable=False, index=True)
    km_to = Column(Numeric(8, 3), nullable=False)
    task_code = Column(String(50), nullable=False)
    task_kind = Column(String(20), nullable=False)
    description = Column(Text)
    defect_severity = Column(Integer)
    raised_on = Column(Date)
    due_on = Column(Date, nullable=False, index=True)
    periodicity_days = Column(Integer)
    last_done_on = Column(Date)
    est_duration_min = Column(Integer, nullable=False)
    min_duration_min = Column(Integer)
    required_block = Column(SQLEnum(BlockType), nullable=False)
    needs_power_block = Column(Boolean, default=False)
    needs_disconnection = Column(Boolean, default=False)
    gang_dept = Column(SQLEnum(Dept))
    gang_size_req = Column(Integer, default=1)
    night_only = Column(Boolean, default=False)
    status = Column(SQLEnum(ReqStatus), nullable=False, default=ReqStatus.OPEN, index=True)

    # Computed fields (from M3 Risk Engine)
    priority_score = Column(Numeric(8, 4))
    p_fail_30d = Column(Numeric(6, 5))
    deferral_cost_per_day = Column(Numeric(8, 4))

    __table_args__ = (
        CheckConstraint('task_kind IN (\'DEFECT\',\'SCHEDULED\',\'OVERDUE\',\'INSPECTION\')',
                       name='check_task_kind'),
        CheckConstraint('defect_severity IS NULL OR defect_severity BETWEEN 0 AND 5',
                       name='check_defect_severity'),
    )

    # Relationships
    asset = relationship("Asset", back_populates="maintenance_requests")
    corridor = relationship("Corridor", back_populates="maintenance_requests")


class Train(Base):
    """Train (PRD §9)"""
    __tablename__ = "train"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(20), unique=True, nullable=False)
    name = Column(String(200))
    train_class = Column(String(20), nullable=False)
    priority_class = Column(Integer, nullable=False)
    is_protected = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint('train_class IN (\'RAJ_SHTB\',\'MAIL_EXP\',\'PASS_MEMU\',\'SUBURBAN\',\'GOODS\',\'ENGG_SPL\')',
                       name='check_train_class'),
    )

    # Relationships
    train_paths = relationship("TrainPath", back_populates="train")


class TrainPath(Base):
    """Train path/timetable entry (PRD §9)"""
    __tablename__ = "train_path"

    id = Column(BigInteger, primary_key=True, index=True)
    train_id = Column(Integer, ForeignKey("train.id"))
    section_id = Column(Integer, ForeignKey("track_section.id"), index=True)
    entry_min = Column(Integer, nullable=False, index=True)  # minutes from midnight
    exit_min = Column(Integer, nullable=False)
    dow_mask = Column(Integer, nullable=False, default=127)  # day of week bitmask
    slack_min = Column(Integer, nullable=False, default=0)

    # Relationships
    train = relationship("Train", back_populates="train_paths")


class BlockWindow(Base):
    """Admissible maintenance window (PRD §9)"""
    __tablename__ = "block_window"

    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(Integer, ForeignKey("corridor.id"), index=True)
    km_start = Column(Numeric(8, 3))
    km_end = Column(Numeric(8, 3))
    start_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    end_ts = Column(DateTime(timezone=True), nullable=False)
    window_kind = Column(String(30), nullable=False)
    allowed_block_types = Column(ARRAY(String), nullable=False)
    source = Column(SQLEnum(SrcSystem), nullable=False, default=SrcSystem.COA)

    __table_args__ = (
        CheckConstraint('window_kind IN (\'CORRIDOR_POLICY\',\'TRAFFIC_LEAN\',\'MAINT_NOTIFIED\')',
                       name='check_window_kind'),
    )


class Plan(Base):
    """Block plan (PRD §9)"""
    __tablename__ = "plan"

    id = Column(Integer, primary_key=True, index=True)
    division = Column(String(100), nullable=False)
    horizon = Column(SQLEnum(Horizon), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    version = Column(Integer, nullable=False)
    parent_plan_id = Column(Integer, ForeignKey("plan.id"))
    planner_kind = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    objective_value = Column(Numeric(12, 4))
    solver_status = Column(String(50))
    solve_ms = Column(Integer)
    weights = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint('planner_kind IN (\'RAILOPT\',\'BASELINE\',\'SCENARIO\')',
                       name='check_planner_kind'),
        CheckConstraint('status IN (\'DRAFT\',\'VALID\',\'INVALID\',\'APPROVED\',\'SUPERSEDED\')',
                       name='check_status'),
    )

    # Relationships
    planned_blocks = relationship("PlannedBlock", back_populates="plan", cascade="all, delete-orphan")


class PlannedBlock(Base):
    """Planned maintenance block (PRD §9)"""
    __tablename__ = "planned_block"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    corridor_id = Column(Integer, ForeignKey("corridor.id"))
    km_start = Column(Numeric(8, 3))
    km_end = Column(Numeric(8, 3))
    line_no = Column(Integer)
    start_ts = Column(DateTime(timezone=True), nullable=False)
    end_ts = Column(DateTime(timezone=True), nullable=False)
    block_type = Column(SQLEnum(BlockType), nullable=False)
    bundle_id = Column(String(50))
    depts = Column(ARRAY(String), nullable=False)
    is_pinned = Column(Boolean, default=False)
    utilization = Column(Numeric(4, 3))
    score = Column(Numeric(8, 4))

    # Relationships
    plan = relationship("Plan", back_populates="planned_blocks")
    tasks = relationship("PlannedBlockTask", back_populates="planned_block", cascade="all, delete-orphan")


class PlannedBlockTask(Base):
    """Task assigned to a planned block (PRD §9)"""
    __tablename__ = "planned_block_task"

    planned_block_id = Column(Integer, ForeignKey("planned_block.id", ondelete="CASCADE"), primary_key=True)
    request_id = Column(Integer, ForeignKey("maintenance_request.id"), primary_key=True)
    seq = Column(Integer, nullable=False)
    start_ts = Column(DateTime(timezone=True), nullable=False)
    end_ts = Column(DateTime(timezone=True), nullable=False)
    gang_id = Column(Integer, ForeignKey("resource_gang.id"))
    is_shadow = Column(Boolean, default=False)

    # Relationships
    planned_block = relationship("PlannedBlock", back_populates="tasks")


class KPISnapshot(Base):
    """KPI metrics for a plan (PRD §9)"""
    __tablename__ = "kpi_snapshot"

    plan_id = Column(Integer, ForeignKey("plan.id", ondelete="CASCADE"), primary_key=True)
    kpi = Column(JSONB, nullable=False)


class Scenario(Base):
    """What-if scenario (PRD §9)"""
    __tablename__ = "scenario"

    id = Column(Integer, primary_key=True, index=True)
    base_plan_id = Column(Integer, ForeignKey("plan.id"))
    result_plan_id = Column(Integer, ForeignKey("plan.id"))
    label = Column(String(200))
    edits = Column(JSONB, nullable=False)
    kpi = Column(JSONB)
    feasible = Column(Boolean)
    infeasibility_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

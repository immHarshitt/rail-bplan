"""
RAIL-OPT Configuration
Loaded from environment variables and config files
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "RAIL-OPT"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://railopt:railopt_dev@localhost:5432/railopt"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Solver settings (from PRD §22.2)
    SOLVER_WEEKLY_TIME_LIMIT_S: int = 45
    SOLVER_MONTHLY_TIME_LIMIT_S: int = 90
    SOLVER_WHATIF_TIME_LIMIT_S: int = 5
    SOLVER_NUM_WORKERS: int = 8
    SOLVER_RANDOM_SEED: int = 42

    # Engine settings (from PRD §22.2)
    BUNDLE_RADIUS_KM: float = 5.0
    SHADOW_LOOKAHEAD_DAYS: int = 30
    SHADOW_MIN_ELAPSED_FRACTION: float = 0.6
    SHADOW_MAX_DAYS_EARLY: int = 30
    SHADOW_VALUE_DISCOUNT: float = 0.7
    PROTECT_MIN: int = 15  # minutes
    RELEASE_MIN: int = 10  # minutes
    PROTECT_POWER_EXTRA: int = 15  # extra for power blocks
    RELEASE_POWER_EXTRA: int = 10
    SLOT_MINUTES: int = 15  # time discretization
    MAX_CANDIDATES_PER_CORRIDOR: int = 40
    RIPPLE_MAX_DEPTH: int = 6
    CLEARANCE_MIN: int = 10
    FREEZE_HORIZON_HOURS: int = 6

    # Priority weights (from PRD §12.3.2)
    PRIORITY_WEIGHT_CRITICALITY: float = 0.22
    PRIORITY_WEIGHT_SEVERITY: float = 0.20
    PRIORITY_WEIGHT_OVERDUE: float = 0.18
    PRIORITY_WEIGHT_FAILURE: float = 0.22
    PRIORITY_WEIGHT_TRAFFIC: float = 0.12
    PRIORITY_WEIGHT_PROTECTED: float = 0.06

    # Objective weights (from PRD §12.6.3)
    OBJECTIVE_TASK_VALUE: float = 100.0
    OBJECTIVE_LAMBDA_TIME: float = 1.2
    OBJECTIVE_LAMBDA_TRAIN: float = 8.0
    OBJECTIVE_LAMBDA_DELAY: float = 0.5
    OBJECTIVE_LAMBDA_DEFER: float = 3.0
    OBJECTIVE_LAMBDA_CHURN: float = 5.0
    OBJECTIVE_LAMBDA_UTIL: float = 0.3
    OBJECTIVE_COORDINATION_BONUS: float = 0.8

    # Traffic weights (from PRD §12.6.3)
    TRAFFIC_WEIGHT_HIGH: float = 1.6
    TRAFFIC_WEIGHT_MEDIUM: float = 1.0
    TRAFFIC_WEIGHT_LOW: float = 0.6
    TRAFFIC_WEIGHT_PEAK_MULTIPLIER: float = 1.8
    TRAFFIC_WEIGHT_LEAN_MULTIPLIER: float = 0.4

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

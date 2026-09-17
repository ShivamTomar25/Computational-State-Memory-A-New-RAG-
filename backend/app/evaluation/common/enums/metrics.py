from __future__ import annotations

from enum import Enum


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class EvaluationProfile(str, Enum):
    SMOKE = "smoke"
    PILOT = "pilot"
    FULL = "full"
    ABLATION = "ablation"
    ROBUSTNESS = "robustness"


class ExperimentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class MetricResultStatus(str, Enum):
    MEASURED = "measured"
    PENDING = "pending"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    UNRESOLVED = "unresolved"

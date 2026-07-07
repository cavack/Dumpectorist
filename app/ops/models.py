from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AuditOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"


class OperationalState(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class AuditEvent(BaseModel):
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: str
    outcome: AuditOutcome
    actor: str = "system"
    details: dict[str, Any] = Field(default_factory=dict)


class BackupArtifact(BaseModel):
    name: str
    size_bytes: int
    sha256: str


class BackupManifest(BaseModel):
    created_at: datetime
    total_bytes: int
    artifacts: tuple[BackupArtifact, ...]


class DependencyCheck(BaseModel):
    name: str
    state: OperationalState
    latency_ms: float
    detail: str = ""


class OperationalHealth(BaseModel):
    checked_at: datetime
    state: OperationalState
    checks: tuple[DependencyCheck, ...]

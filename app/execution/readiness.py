from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessAudit:
    reasons: tuple[str, ...]

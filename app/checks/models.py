from dataclasses import dataclass, field
from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    symbol: str
    status: CheckStatus
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def can_continue(self) -> bool:
        return self.status == CheckStatus.PASS

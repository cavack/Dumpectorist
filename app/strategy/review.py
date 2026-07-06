from dataclasses import dataclass, field


@dataclass(frozen=True)
class CandidateReview:
    symbol: str
    structure_ok: bool = False
    validation_ok: bool = False
    freshness_ok: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


def classify_candidate(review: CandidateReview) -> str:
    if review.structure_ok and review.validation_ok and review.freshness_ok:
        return "READY"
    if review.structure_ok:
        return "REVIEW"
    return "WATCH"

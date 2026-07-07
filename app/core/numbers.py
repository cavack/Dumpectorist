from math import isfinite
from typing import SupportsFloat


def finite_float(value: SupportsFloat, *, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def positive_finite_float(value: SupportsFloat, *, name: str) -> float:
    parsed = finite_float(value, name=name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed

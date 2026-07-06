from typing import Any


class ParserError(ValueError):
    pass


def require_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ParserError("payload must be an object")
    return payload


def require_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        joined = ", ".join(missing)
        raise ParserError(f"missing fields: {joined}")

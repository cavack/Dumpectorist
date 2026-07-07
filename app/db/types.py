from decimal import Decimal, InvalidOperation

from sqlalchemy import Numeric, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class ExactNumeric(TypeDecorator[Decimal]):
    """Persist exact decimals on PostgreSQL and SQLite.

    PostgreSQL uses its native NUMERIC type. SQLite has no exact decimal
    storage class and SQLAlchemy's Numeric binding can round-trip through a
    binary float, so SQLite stores the canonical decimal string instead.
    This keeps local and CI repository tests faithful to production decimal
    semantics without reducing the supported 18-decimal price precision.
    """

    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int, scale: int) -> None:
        if precision <= 0:
            raise ValueError("precision must be positive")
        if scale < 0 or scale > precision:
            raise ValueError("scale must be between zero and precision")
        self.precision = precision
        self.scale = scale
        super().__init__(precision=precision, scale=scale, asdecimal=True)

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[object]:
        if dialect.name == "sqlite":
            # Sign, decimal point, and a little defensive headroom.
            return dialect.type_descriptor(String(self.precision + 3))
        return dialect.type_descriptor(
            Numeric(self.precision, self.scale, asdecimal=True)
        )

    def process_bind_param(
        self,
        value: Decimal | int | str | float | None,
        dialect: Dialect,
    ) -> Decimal | str | None:
        if value is None:
            return None
        try:
            normalized = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError("value must be decimal-compatible") from error
        if not normalized.is_finite():
            raise ValueError("value must be finite")
        if dialect.name == "sqlite":
            return format(normalized, "f")
        return normalized

    def process_result_value(
        self,
        value: Decimal | int | str | float | None,
        dialect: Dialect,
    ) -> Decimal | None:
        if value is None:
            return None
        try:
            normalized = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError("stored value is not decimal-compatible") from error
        if not normalized.is_finite():
            raise ValueError("stored value must be finite")
        return normalized

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_upgrade_and_downgrade_full_migration_chain(tmp_path):
    database_path = tmp_path / "migration.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    sync_url = f"sqlite:///{database_path}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", async_url)

    command.upgrade(config, "head")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        assert {"domain_records", "ohlcv_candles"}.issubset(
            set(inspector.get_table_names())
        )
        domain_columns = {
            column["name"] for column in inspector.get_columns("domain_records")
        }
        assert domain_columns == {
            "id",
            "record_type",
            "symbol",
            "state",
            "payload",
            "created_at",
            "updated_at",
            "expires_at",
        }
        candle_columns = {
            column["name"] for column in inspector.get_columns("ohlcv_candles")
        }
        assert candle_columns == {
            "id",
            "source",
            "role",
            "category",
            "symbol",
            "interval",
            "open_time",
            "close_time",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "turnover",
            "created_at",
            "updated_at",
        }
        unique_names = {
            item.get("name") for item in inspector.get_unique_constraints("ohlcv_candles")
        }
        assert "uq_ohlcv_source_symbol_interval_open" in unique_names
        index_names = {item["name"] for item in inspector.get_indexes("ohlcv_candles")}
        assert index_names == {
            "ix_ohlcv_source_close",
            "ix_ohlcv_symbol_interval_open",
        }
    finally:
        engine.dispose()

    command.downgrade(config, "20260707_0001")

    engine = create_engine(sync_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "domain_records" in tables
        assert "ohlcv_candles" not in tables
    finally:
        engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(sync_url)
    try:
        assert "domain_records" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

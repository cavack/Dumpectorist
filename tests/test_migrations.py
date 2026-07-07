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
        tables = set(inspector.get_table_names())
        assert {
            "domain_records",
            "ohlcv_candles",
            "support_zones",
            "structure_events",
        }.issubset(tables)
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
        zone_columns = {
            column["name"] for column in inspector.get_columns("support_zones")
        }
        assert {
            "zone_id",
            "source",
            "symbol",
            "interval",
            "zone_low",
            "zone_high",
            "state",
            "created_at_evidence",
            "confirmed_at",
            "last_test_at",
            "touch_count",
            "rejection_count",
            "strength_score",
            "evidence_open_times",
            "reasons",
            "created_at",
            "updated_at",
        } == zone_columns
        event_columns = {
            column["name"] for column in inspector.get_columns("structure_events")
        }
        assert {
            "event_id",
            "zone_id",
            "source",
            "symbol",
            "interval",
            "state",
            "observed_at",
            "candle_open_time",
            "close_price",
            "zone_low",
            "zone_high",
            "distance_bps",
            "body_fraction",
            "volume_ratio",
            "invalidates_event_id",
            "reasons",
            "created_at",
            "updated_at",
        } == event_columns
        unique_names = {
            item.get("name") for item in inspector.get_unique_constraints("ohlcv_candles")
        }
        assert "uq_ohlcv_source_symbol_interval_open" in unique_names
        assert {item["name"] for item in inspector.get_indexes("support_zones")} == {
            "ix_support_zones_state_updated",
            "ix_support_zones_symbol_interval_confirmed",
        }
        assert {item["name"] for item in inspector.get_indexes("structure_events")} == {
            "ix_structure_events_state_observed",
            "ix_structure_events_symbol_interval_observed",
            "ix_structure_events_zone_observed",
        }
    finally:
        engine.dispose()

    command.downgrade(config, "20260707_0002")

    engine = create_engine(sync_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "domain_records" in tables
        assert "ohlcv_candles" in tables
        assert "support_zones" not in tables
        assert "structure_events" not in tables
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

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_reclaim_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "reclaim-migration.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    sync_url = f"sqlite:///{database_path}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", async_url)

    command.upgrade(config, "head")
    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        assert "reclaim_attempts" in inspector.get_table_names()
        columns = {item["name"] for item in inspector.get_columns("reclaim_attempts")}
        assert {
            "attempt_id",
            "break_event_id",
            "zone_id",
            "source",
            "symbol",
            "structure_interval",
            "started_at",
            "observed_at",
            "outcome",
            "setup_type",
            "readiness",
            "zone_low",
            "zone_high",
            "maximum_price",
            "maximum_penetration_bps",
            "duration_bars",
            "closes_above_zone",
            "bars_above_zone",
            "bounce_volume_ratio",
            "rejection_candle_open_time",
            "rejection_low",
            "trigger_candle_open_time",
            "quality_score",
            "reasons",
            "warnings",
            "created_at",
            "updated_at",
        } == columns
        indexes = {item["name"] for item in inspector.get_indexes("reclaim_attempts")}
        assert indexes == {
            "ix_reclaim_attempts_break_event_observed",
            "ix_reclaim_attempts_readiness_observed",
            "ix_reclaim_attempts_symbol_observed",
        }
    finally:
        engine.dispose()

    command.downgrade(config, "20260707_0003")
    engine = create_engine(sync_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "reclaim_attempts" not in tables
        assert "support_zones" in tables
        assert "structure_events" in tables
    finally:
        engine.dispose()

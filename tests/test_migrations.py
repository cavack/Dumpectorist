from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_upgrade_and_downgrade_domain_records_migration(tmp_path):
    database_path = tmp_path / "migration.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    sync_url = f"sqlite:///{database_path}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", async_url)

    command.upgrade(config, "head")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        assert "domain_records" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("domain_records")}
        assert columns == {
            "id",
            "record_type",
            "symbol",
            "state",
            "payload",
            "created_at",
            "updated_at",
            "expires_at",
        }
    finally:
        engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(sync_url)
    try:
        assert "domain_records" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

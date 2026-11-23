from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from alembic import command
from app.models import Base

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config(connection) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.attributes["connection"] = connection
    return cfg


def test_migrations_match_models():
    """After upgrading to head, the schema must equal the models (no forgotten migration)."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_to_base():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:
        cfg = alembic_config(conn)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")


def test_constraint_names_are_unique_per_table_on_postgres():
    """SQLite tolerates duplicate constraint names; Postgres does not."""
    import re
    from collections import Counter

    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        names = re.findall(r"CONSTRAINT (\w+)", ddl)
        dupes = [n for n, c in Counter(names).items() if c > 1]
        assert not dupes, f"{table.name}: {dupes}"


def test_artist_slugs_are_filled_in_for_existing_artists():
    """Upgrading a database that already has artists gives each a URL name, clashes suffixed."""
    import sqlalchemy as sa

    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:
        cfg = alembic_config(conn)
        command.upgrade(cfg, "0001")
        for name in ("Pink Floyd", "Pink-Floyd", "Sigur Rós"):
            conn.execute(sa.text("INSERT INTO artist (name) VALUES (:n)"), {"n": name})
        command.upgrade(cfg, "head")
        rows = conn.execute(sa.text("SELECT name, slug FROM artist ORDER BY id")).fetchall()
    assert [tuple(r) for r in rows] == [
        ("Pink Floyd", "pink-floyd"),
        ("Pink-Floyd", "pink-floyd-2"),
        ("Sigur Rós", "sigur-ros"),
    ]

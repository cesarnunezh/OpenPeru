"""Database container and migration helpers."""

import os
import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .migration import (
    DEFAULT_DB_URL,
    DEFAULT_SQLITE_PATH,
    enable_extensions,
    assert_raw_tables_empty,
    import_direct_tables,
    import_document_tables,
    validate_import,
    reset_sequences,
)
from backend.database.models import Base
from backend.database import raw_models as raw_models


def main() -> None:
    args = parse_args()
    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite source not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_engine = create_engine(args.db_url, pool_pre_ping=True)

    try:
        migrate(
            sqlite_conn,
            pg_engine,
            validate_checksums=not args.skip_checksums,
            process_clean=not args.skip_clean_processing,
        )
    finally:
        sqlite_conn.close()
        pg_engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the baked OpenPeru raw SQLite database into PostgreSQL."
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("DB_URL", DEFAULT_DB_URL),
        help="SQLAlchemy PostgreSQL URL. Defaults to DB_URL.",
    )
    parser.add_argument(
        "--sqlite-path",
        default=os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH),
        help="Path to OpenPeruRaw.db inside the migration container.",
    )
    parser.add_argument(
        "--skip-checksums",
        action="store_true",
        help="Only validate row counts after import.",
    )
    parser.add_argument(
        "--skip-clean-processing",
        action="store_true",
        help="Only import raw tables; do not seed clean tables from raw data.",
    )
    return parser.parse_args()


def migrate(
    sqlite_conn: sqlite3.Connection,
    pg_engine: Engine,
    *,
    validate_checksums: bool = True,
    process_clean: bool = True,
) -> None:
    enable_extensions(pg_engine)
    Base.metadata.create_all(pg_engine)

    with pg_engine.begin() as pg_conn:
        assert_raw_tables_empty(pg_conn)
        import_direct_tables(sqlite_conn, pg_conn)
        import_document_tables(sqlite_conn, pg_conn)
        reset_sequences(pg_conn)
        validate_import(sqlite_conn, pg_conn, validate_checksums=validate_checksums)

    if process_clean:
        run_clean_processing(pg_engine)


def run_clean_processing(pg_engine: Engine, orchestrator_cls=None) -> None:
    if orchestrator_cls is None:
        from backend.database.orchestrator import OpenPeruOrchestrator

        orchestrator_cls = OpenPeruOrchestrator

    db_url = pg_engine.url.render_as_string(hide_password=False)
    orchestrator = orchestrator_cls(db_url=db_url)
    summary = orchestrator.run_processing(
        process_bills=True,
        process_motions=True,
        process_leyes=True,
        process_others=True,
        include_documents=False,
    )

    failed = {stage: stats.errors for stage, stats in summary.items() if stats.errors}
    if failed:
        details = ", ".join(
            f"{stage}={errors}" for stage, errors in sorted(failed.items())
        )
        raise RuntimeError(f"Clean processing failed with errors: {details}")


if __name__ == "__main__":
    main()

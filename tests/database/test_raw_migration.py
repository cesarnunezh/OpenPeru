from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from datetime import datetime

import pytest
from sqlalchemy import create_engine, func, select

from backend.database.models import Base
from backend.database.migration import __main__ as migration_main
from backend.database.migration.migration import (
    BILL_DOCUMENTS,
    MOTION_DOCUMENTS,
    assert_raw_tables_empty,
    build_s3_key,
    build_source_select,
    import_document_tables,
    source_count,
    source_checksum,
    target_checksum,
)


def make_source() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE raw_bill_documents (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            bill_id VARCHAR NOT NULL,
            step_date DATETIME NOT NULL,
            seguimiento_id VARCHAR NOT NULL,
            archivo_id VARCHAR NOT NULL,
            url VARCHAR NOT NULL,
            text VARCHAR NOT NULL,
            processed BOOLEAN NOT NULL DEFAULT 0,
            last_update BOOLEAN NOT NULL DEFAULT 0,
            changed BOOLEAN NOT NULL DEFAULT 0
        );
        CREATE TABLE raw_motion_documents (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            motion_id VARCHAR NOT NULL,
            step_date DATETIME NOT NULL,
            seguimiento_id VARCHAR NOT NULL,
            archivo_id VARCHAR NOT NULL,
            url VARCHAR NOT NULL,
            text VARCHAR NOT NULL,
            processed BOOLEAN NOT NULL DEFAULT 0,
            last_update BOOLEAN NOT NULL DEFAULT 0,
            changed BOOLEAN NOT NULL DEFAULT 0
        );
        CREATE TABLE raw_bill_pages (
            bill_id VARCHAR NOT NULL,
            step_id VARCHAR NOT NULL,
            archivo_id VARCHAR NOT NULL,
            page_num INTEGER NOT NULL,
            text VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            timestamp DATETIME NOT NULL,
            last_update BOOLEAN NOT NULL DEFAULT 0,
            changed BOOLEAN NOT NULL DEFAULT 0,
            processed BOOLEAN NOT NULL DEFAULT 0
        );
        CREATE TABLE raw_motion_pages (
            motion_id VARCHAR NOT NULL,
            step_id VARCHAR NOT NULL,
            archivo_id VARCHAR NOT NULL,
            page_num INTEGER NOT NULL,
            text VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            timestamp DATETIME NOT NULL,
            last_update BOOLEAN NOT NULL DEFAULT 0,
            changed BOOLEAN NOT NULL DEFAULT 0,
            processed BOOLEAN NOT NULL DEFAULT 0
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO raw_bill_documents (
            id, timestamp, bill_id, step_date, seguimiento_id, archivo_id, url,
            text, processed, last_update, changed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                0,
                "2026-01-03 10:00:00",
                "2021_ignored",
                "2026-01-03 00:00:00",
                "99",
                "99",
                "https://example.test/ignored.pdf",
                "ignored extracted text",
                0,
                0,
                1,
            ),
            (
                1,
                "2026-01-01 10:00:00",
                "2021_1",
                "2026-01-01 00:00:00",
                "10",
                "20",
                "https://example.test/old.pdf",
                "old extracted text",
                0,
                1,
                1,
            ),
            (
                2,
                "2026-01-02 10:00:00",
                "2021_1",
                "2026-01-01 00:00:00",
                "10",
                "20",
                "https://example.test/new.pdf",
                "new extracted text",
                1,
                1,
                1,
            ),
        ],
    )
    conn.executemany(
        """
        INSERT INTO raw_motion_documents (
            id, timestamp, motion_id, step_date, seguimiento_id, archivo_id, url,
            text, processed, last_update, changed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "2026-02-01 10:00:00",
                "2021_2",
                "2026-02-01 00:00:00",
                "11",
                "21",
                "https://example.test/motion.pdf",
                "motion extracted text",
                0,
                1,
                0,
            ),
            (
                2,
                "2026-02-02 10:00:00",
                "2021_ignored",
                "2026-02-02 00:00:00",
                "99",
                "99",
                "https://example.test/ignored-motion.pdf",
                "ignored motion extracted text",
                0,
                0,
                0,
            ),
        ],
    )
    return conn


@pytest.fixture
def target_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_document_import_maps_metadata_paths_and_drops_extracted_text(
    target_engine, monkeypatch
):
    monkeypatch.delenv("AWS_S3_PREFIX", raising=False)
    source = make_source()
    with target_engine.begin() as conn:
        import_document_tables(source, conn)

        row = (
            conn.execute(select(Base.metadata.tables["raw_bill_documents"]))
            .one()
            ._mapping
        )

    assert row["bill_id"] == "2021_1"
    assert row["step_id"] == "10"
    assert row["file_id"] == "20"
    assert row["url"] == "https://example.test/new.pdf"
    assert row["s3_key"] == "documents/bills/2021_1-10-20.pdf"
    assert row["local_path"] == str(BILL_DOCUMENTS / "2021_1-10-20.pdf")
    assert "text" not in row
    assert row["timestamp"] == datetime(2026, 1, 2, 10, 0, 0)


def test_motion_document_import_maps_motion_paths(target_engine, monkeypatch):
    monkeypatch.delenv("AWS_S3_PREFIX", raising=False)
    source = make_source()
    with target_engine.begin() as conn:
        import_document_tables(source, conn)

        row = (
            conn.execute(select(Base.metadata.tables["raw_motion_documents"]))
            .one()
            ._mapping
        )

    assert row["motion_id"] == "2021_2"
    assert row["step_id"] == "11"
    assert row["file_id"] == "21"
    assert row["s3_key"] == "documents/motions/2021_2-11-21.pdf"
    assert row["local_path"] == str(MOTION_DOCUMENTS / "2021_2-11-21.pdf")


def test_document_import_deduplicates_bill_documents_by_latest_timestamp(
    target_engine,
):
    source = make_source()
    with target_engine.begin() as conn:
        import_document_tables(source, conn)

        bill_count = conn.execute(
            select(func.count()).select_from(Base.metadata.tables["raw_bill_documents"])
        ).scalar_one()
        motion_count = conn.execute(
            select(func.count()).select_from(
                Base.metadata.tables["raw_motion_documents"]
            )
        ).scalar_one()

    assert bill_count == 1
    assert motion_count == 1
    assert source_count(source, "raw_bill_documents") == 1
    assert source_count(source, "raw_motion_documents") == 1


def test_direct_table_selects_filter_to_latest_rows():
    sql = build_source_select("raw_bills", ("id", "timestamp", "last_update"))

    assert "WHERE last_update = 1" in sql


def test_scraper_runs_select_does_not_filter_latest():
    sql = build_source_select("scraper_runs", ("run_id", "scraper_name"))

    assert "last_update" not in sql


def test_s3_key_uses_optional_prefix(monkeypatch):
    monkeypatch.setenv("AWS_S3_PREFIX", "openperu/raw/")

    assert (
        build_s3_key("bills", "2021_1-10-20.pdf")
        == "openperu/raw/documents/bills/2021_1-10-20.pdf"
    )


def test_page_source_count_is_zero_without_importing_page_rows():
    source = make_source()

    assert source_count(source, "raw_bill_pages") == 0
    assert source_count(source, "raw_motion_pages") == 0


def test_document_checksums_match_after_import(target_engine):
    source = make_source()
    with target_engine.begin() as conn:
        import_document_tables(source, conn)

    with target_engine.connect() as conn:
        assert source_checksum(source, "raw_bill_documents") == target_checksum(
            conn, "raw_bill_documents"
        )
        assert source_checksum(source, "raw_motion_documents") == target_checksum(
            conn, "raw_motion_documents"
        )


def test_assert_raw_tables_empty_fails_when_any_raw_table_has_rows(target_engine):
    source = make_source()
    with target_engine.begin() as conn:
        import_document_tables(source, conn)

        with pytest.raises(RuntimeError, match="target raw tables are not empty"):
            assert_raw_tables_empty(conn)


def test_migrate_runs_clean_processing_after_raw_import(monkeypatch):
    source = make_source()
    engine = create_engine("sqlite:///:memory:")
    calls = []

    monkeypatch.setattr(migration_main, "enable_extensions", lambda engine: None)
    monkeypatch.setattr(
        migration_main, "assert_raw_tables_empty", lambda conn: calls.append("empty")
    )
    monkeypatch.setattr(
        migration_main,
        "import_direct_tables",
        lambda sqlite_conn, conn: calls.append("direct"),
    )
    monkeypatch.setattr(
        migration_main,
        "import_document_tables",
        lambda sqlite_conn, conn: calls.append("documents"),
    )
    monkeypatch.setattr(
        migration_main, "reset_sequences", lambda conn: calls.append("sequences")
    )
    monkeypatch.setattr(
        migration_main,
        "validate_import",
        lambda sqlite_conn, conn, *, validate_checksums: calls.append(
            f"validate={validate_checksums}"
        ),
    )
    monkeypatch.setattr(
        migration_main, "run_clean_processing", lambda engine: calls.append("clean")
    )

    migration_main.migrate(source, engine, validate_checksums=False)

    assert calls == [
        "empty",
        "direct",
        "documents",
        "sequences",
        "validate=False",
        "clean",
    ]
    engine.dispose()


def test_migrate_can_skip_clean_processing(monkeypatch):
    source = make_source()
    engine = create_engine("sqlite:///:memory:")
    calls = []

    monkeypatch.setattr(migration_main, "enable_extensions", lambda engine: None)
    monkeypatch.setattr(migration_main, "assert_raw_tables_empty", lambda conn: None)
    monkeypatch.setattr(
        migration_main, "import_direct_tables", lambda sqlite_conn, conn: None
    )
    monkeypatch.setattr(
        migration_main, "import_document_tables", lambda sqlite_conn, conn: None
    )
    monkeypatch.setattr(migration_main, "reset_sequences", lambda conn: None)
    monkeypatch.setattr(
        migration_main,
        "validate_import",
        lambda sqlite_conn, conn, *, validate_checksums: None,
    )
    monkeypatch.setattr(
        migration_main, "run_clean_processing", lambda engine: calls.append("clean")
    )

    migration_main.migrate(source, engine, process_clean=False)

    assert calls == []
    engine.dispose()


def test_run_clean_processing_disables_documents_and_uses_engine_url():
    engine = create_engine("sqlite:///clean.db")
    calls = []

    class FakeOrchestrator:
        def __init__(self, db_url):
            calls.append(("init", db_url))

        def run_processing(self, **kwargs):
            calls.append(("run_processing", kwargs))
            return {"bills": SimpleNamespace(errors=0)}

    migration_main.run_clean_processing(engine, orchestrator_cls=FakeOrchestrator)

    assert calls == [
        ("init", "sqlite:///clean.db"),
        (
            "run_processing",
            {
                "process_bills": True,
                "process_motions": True,
                "process_leyes": True,
                "process_others": True,
                "include_documents": False,
            },
        ),
    ]
    engine.dispose()


def test_run_clean_processing_raises_on_stage_errors():
    engine = create_engine("sqlite:///:memory:")

    class FakeOrchestrator:
        def __init__(self, db_url):
            pass

        def run_processing(self, **kwargs):
            return {
                "bills": SimpleNamespace(errors=2),
                "motions": SimpleNamespace(errors=0),
            }

    with pytest.raises(RuntimeError, match="bills=2"):
        migration_main.run_clean_processing(engine, orchestrator_cls=FakeOrchestrator)

    engine.dispose()

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Table, func, select, text
from sqlalchemy.engine import Engine

from backend.database.models import Base
from backend.config import directories, settings

DEFAULT_DB_URL = settings.DB_URL
DEFAULT_SQLITE_PATH = settings.SQLITE_PATH
BATCH_SIZE = 1000

COMMON_RAW_COLUMNS = ("timestamp", "last_update", "changed", "processed")

DIRECT_TABLES: dict[str, tuple[str, ...]] = {
    "raw_bancadas": (
        "id",
        "timestamp",
        "legislative_period",
        "raw_html",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "raw_bills": (
        "id",
        "timestamp",
        "general",
        "committees",
        "congresistas",
        "steps",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "raw_committees": (
        "id",
        "timestamp",
        "legislative_year",
        "committee_type",
        "raw_html",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "raw_congresistas": (
        "id",
        "timestamp",
        "leg_period",
        "website",
        "profile_content",
        "memberships_content",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "raw_leyes": ("id", "timestamp", "data", *COMMON_RAW_COLUMNS[1:]),
    "raw_motions": (
        "id",
        "timestamp",
        "general",
        "congresistas",
        "steps",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "raw_organizations": (
        "id",
        "timestamp",
        "legislative_year",
        "type_org",
        "org_link",
        "raw_html",
        *COMMON_RAW_COLUMNS[1:],
    ),
    "scraper_runs": (
        "run_id",
        "scraper_name",
        "start_time",
        "end_time",
        "scraped_rows",
    ),
}

DOCUMENT_TABLES = ("raw_bill_documents", "raw_motion_documents")
PAGE_TABLES = ("raw_bill_pages", "raw_motion_pages")
RAW_TARGET_TABLES = tuple(DIRECT_TABLES) + DOCUMENT_TABLES + PAGE_TABLES
LATEST_ONLY_TABLES = tuple(table for table in DIRECT_TABLES if table != "scraper_runs")

BILL_DOCUMENTS = directories.BILL_DOCUMENTS
MOTION_DOCUMENTS = directories.MOTION_DOCUMENTS

DATETIME_COLUMNS = {"timestamp", "step_date", "start_time", "end_time"}
BOOLEAN_COLUMNS = {"last_update", "changed", "processed"}
STRING_COLUMNS = {
    ("raw_committees", "legislative_year"),
    ("raw_organizations", "legislative_year"),
    ("raw_bill_documents", "step_id"),
    ("raw_bill_documents", "file_id"),
    ("raw_motion_documents", "step_id"),
    ("raw_motion_documents", "file_id"),
}


def enable_extensions(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_similarity;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))


def assert_raw_tables_empty(pg_conn) -> None:
    non_empty: list[str] = []
    for table_name in RAW_TARGET_TABLES:
        table = Base.metadata.tables[table_name]
        count = pg_conn.execute(select(func.count()).select_from(table)).scalar_one()
        if count:
            non_empty.append(f"{table_name}={count}")

    if non_empty:
        details = ", ".join(non_empty)
        raise RuntimeError(
            "Raw migration refused to run because target raw tables are not empty: "
            f"{details}. Reset the PostgreSQL volume before rerunning."
        )


def import_direct_tables(sqlite_conn: sqlite3.Connection, pg_conn) -> None:
    for table_name, columns in DIRECT_TABLES.items():
        sql = build_source_select(table_name, columns)
        rows = iter_sqlite_rows(sqlite_conn, sql)
        insert_rows(pg_conn, Base.metadata.tables[table_name], rows)


def import_document_tables(sqlite_conn: sqlite3.Connection, pg_conn) -> None:
    bill_rows = iter_sqlite_rows(
        sqlite_conn,
        """
        SELECT
            bill_id,
            seguimiento_id AS step_id,
            archivo_id AS file_id,
            step_date,
            url,
            NULL AS s3_key,
            NULL AS local_path,
            timestamp,
            last_update,
            changed,
            processed
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY bill_id, seguimiento_id, archivo_id
                    ORDER BY timestamp DESC, id DESC
                ) AS rn
            FROM raw_bill_documents
            WHERE last_update = 1
        )
        WHERE rn = 1
        ORDER BY bill_id, seguimiento_id, archivo_id
        """,
        table_name="raw_bill_documents",
    )
    insert_rows(pg_conn, Base.metadata.tables["raw_bill_documents"], bill_rows)

    motion_rows = iter_sqlite_rows(
        sqlite_conn,
        """
        SELECT
            motion_id,
            seguimiento_id AS step_id,
            archivo_id AS file_id,
            step_date,
            url,
            NULL AS s3_key,
            NULL AS local_path,
            timestamp,
            last_update,
            changed,
            processed
        FROM raw_motion_documents
        WHERE last_update = 1
        ORDER BY motion_id, seguimiento_id, archivo_id
        """,
        table_name="raw_motion_documents",
    )
    insert_rows(pg_conn, Base.metadata.tables["raw_motion_documents"], motion_rows)


def build_source_select(table_name: str, columns: Sequence[str]) -> str:
    column_sql = ", ".join(columns)
    where_sql = " WHERE last_update = 1" if table_name in LATEST_ONLY_TABLES else ""
    order_sql = ", ".join(primary_key_columns(table_name))
    return f"SELECT {column_sql} FROM {table_name}{where_sql} ORDER BY {order_sql}"


def iter_sqlite_rows(
    sqlite_conn: sqlite3.Connection,
    sql: str,
    *,
    table_name: str | None = None,
) -> Iterator[dict[str, Any]]:
    cursor = sqlite_conn.execute(sql)
    source_table = table_name or infer_table_name(sql)

    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        for row in rows:
            yield normalize_row(source_table, dict(row))


def infer_table_name(sql: str) -> str:
    tokens = sql.replace("\n", " ").split()
    return tokens[tokens.index("FROM") + 1]


def normalize_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    if table_name == "raw_bill_documents":
        populate_bill_document_paths(row)
    elif table_name == "raw_motion_documents":
        populate_motion_document_paths(row)

    normalized: dict[str, Any] = {}
    for column, value in row.items():
        if value is None:
            normalized[column] = None
        elif column in DATETIME_COLUMNS:
            normalized[column] = parse_datetime(value)
        elif column in BOOLEAN_COLUMNS:
            normalized[column] = bool(value)
        elif (table_name, column) in STRING_COLUMNS:
            normalized[column] = str(value)
        else:
            normalized[column] = value
    return normalized


def populate_bill_document_paths(row: dict[str, Any]) -> None:
    filename = build_filename(row["bill_id"], row["step_id"], row["file_id"])
    row["s3_key"] = build_s3_key("bills", filename)
    row["local_path"] = str(BILL_DOCUMENTS / filename)


def populate_motion_document_paths(row: dict[str, Any]) -> None:
    filename = build_filename(row["motion_id"], row["step_id"], row["file_id"])
    row["s3_key"] = build_s3_key("motions", filename)
    row["local_path"] = str(MOTION_DOCUMENTS / filename)


def build_filename(item_id: Any, step_id: Any, file_id: Any) -> str:
    return f"{item_id}-{step_id}-{file_id}.pdf"


def build_s3_key(kind: str, filename: str) -> str:
    parts = []
    prefix = os.getenv("AWS_S3_PREFIX")
    if prefix:
        parts.append(prefix.strip("/"))
    parts.extend(["documents", kind, filename])
    return "/".join(parts)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def insert_rows(pg_conn, table: Table, rows: Iterator[dict[str, Any]]) -> None:
    batch: list[dict[str, Any]] = []
    total = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            pg_conn.execute(table.insert(), batch)
            total += len(batch)
            batch.clear()

    if batch:
        pg_conn.execute(table.insert(), batch)
        total += len(batch)

    print(f"Imported {total} rows into {table.name}")


def reset_sequences(pg_conn) -> None:
    for table_name, pk_column in {
        "raw_bancadas": "id",
        "raw_committees": "id",
        "raw_congresistas": "id",
        "raw_leyes": "id",
        "raw_organizations": "id",
        "scraper_runs": "run_id",
    }.items():
        sequence_name = pg_conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :pk_column)"),
            {"table_name": table_name, "pk_column": pk_column},
        ).scalar_one()
        if sequence_name is None:
            continue

        pg_conn.execute(
            text(
                f"""
                SELECT setval(
                    CAST(:sequence_name AS regclass),
                    COALESCE((SELECT MAX({pk_column}) FROM {table_name}), 1),
                    (SELECT COUNT(*) > 0 FROM {table_name})
                )
                """
            ),
            {"sequence_name": sequence_name},
        )


def validate_import(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    *,
    validate_checksums: bool,
) -> None:
    for table_name in tuple(DIRECT_TABLES) + DOCUMENT_TABLES + PAGE_TABLES:
        expected = source_count(sqlite_conn, table_name)
        actual = target_count(pg_conn, table_name)
        if expected != actual:
            raise RuntimeError(
                f"Row count mismatch for {table_name}: expected {expected}, got {actual}"
            )

        if validate_checksums:
            expected_hash = source_checksum(sqlite_conn, table_name)
            actual_hash = target_checksum(pg_conn, table_name)
            if expected_hash != actual_hash:
                raise RuntimeError(
                    f"Checksum mismatch for {table_name}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )

        print(f"Validated {table_name}: {actual} rows")


def source_count(sqlite_conn: sqlite3.Connection, table_name: str) -> int:
    if table_name in PAGE_TABLES:
        return 0
    if table_name == "raw_bill_documents":
        sql = """
            SELECT COUNT(*) FROM (
                SELECT 1
                FROM raw_bill_documents
                WHERE last_update = 1
                GROUP BY bill_id, seguimiento_id, archivo_id
            )
        """
    elif table_name == "raw_motion_documents":
        sql = "SELECT COUNT(*) FROM raw_motion_documents WHERE last_update = 1"
    elif table_name in LATEST_ONLY_TABLES:
        sql = f"SELECT COUNT(*) FROM {table_name} WHERE last_update = 1"
    else:
        sql = f"SELECT COUNT(*) FROM {table_name}"
    return int(sqlite_conn.execute(sql).fetchone()[0])


def target_count(pg_conn, table_name: str) -> int:
    table = Base.metadata.tables[table_name]
    return pg_conn.execute(select(func.count()).select_from(table)).scalar_one()


def source_checksum(sqlite_conn: sqlite3.Connection, table_name: str) -> str:
    if table_name in PAGE_TABLES:
        return empty_checksum()
    if table_name == "raw_bill_documents":
        sql = """
            SELECT
                bill_id,
                seguimiento_id AS step_id,
                archivo_id AS file_id,
                step_date,
                url,
                NULL AS s3_key,
                NULL AS local_path,
                timestamp,
                last_update,
                changed,
                processed
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY bill_id, seguimiento_id, archivo_id
                        ORDER BY timestamp DESC, id DESC
                    ) AS rn
                FROM raw_bill_documents
                WHERE last_update = 1
            )
            WHERE rn = 1
            ORDER BY bill_id, seguimiento_id, archivo_id
        """
        rows = iter_sqlite_rows(sqlite_conn, sql, table_name=table_name)
    elif table_name == "raw_motion_documents":
        sql = """
            SELECT
                motion_id,
                seguimiento_id AS step_id,
                archivo_id AS file_id,
                step_date,
                url,
                NULL AS s3_key,
                NULL AS local_path,
                timestamp,
                last_update,
                changed,
                processed
            FROM raw_motion_documents
            WHERE last_update = 1
            ORDER BY motion_id, seguimiento_id, archivo_id
        """
        rows = iter_sqlite_rows(sqlite_conn, sql, table_name=table_name)
    else:
        rows = iter_sqlite_rows(
            sqlite_conn,
            build_source_select(table_name, DIRECT_TABLES[table_name]),
            table_name=table_name,
        )
    return checksum_rows(rows)


def target_checksum(pg_conn, table_name: str) -> str:
    if table_name in PAGE_TABLES:
        return empty_checksum()

    table = Base.metadata.tables[table_name]
    columns = validation_columns(table_name)
    stmt = select(*(table.c[column] for column in columns)).order_by(
        *(table.c[column] for column in primary_key_columns(table_name))
    )
    rows = (dict(row._mapping) for row in pg_conn.execute(stmt))
    return checksum_rows(rows)


def validation_columns(table_name: str) -> tuple[str, ...]:
    if table_name == "raw_bill_documents":
        return (
            "bill_id",
            "step_id",
            "file_id",
            "step_date",
            "url",
            "s3_key",
            "local_path",
            *COMMON_RAW_COLUMNS,
        )
    if table_name == "raw_motion_documents":
        return (
            "motion_id",
            "step_id",
            "file_id",
            "step_date",
            "url",
            "s3_key",
            "local_path",
            *COMMON_RAW_COLUMNS,
        )
    return DIRECT_TABLES[table_name]


def primary_key_columns(table_name: str) -> tuple[str, ...]:
    if table_name == "raw_bills":
        return ("id", "timestamp")
    if table_name == "raw_motions":
        return ("id", "timestamp")
    if table_name == "raw_bill_documents":
        return ("bill_id", "step_id", "file_id")
    if table_name == "raw_motion_documents":
        return ("motion_id", "step_id", "file_id")
    if table_name == "raw_bill_pages":
        return ("bill_id", "step_id", "file_id", "page_num", "ocr_model")
    if table_name == "raw_motion_pages":
        return ("motion_id", "step_id", "file_id", "page_num", "ocr_model")
    if table_name == "scraper_runs":
        return ("run_id",)
    return ("id",)


def checksum_rows(rows: Iterator[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        normalized = {
            key: normalize_checksum_value(value) for key, value in row.items()
        }
        digest.update(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def normalize_checksum_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return value


def empty_checksum() -> str:
    return hashlib.sha256().hexdigest()

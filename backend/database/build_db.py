from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from .models import Base


def _enable_extensions(engine) -> None:
    """
    Enable PostgreSQL extensions used by the database.

    Required:
        vector: needed by pgvector.sqlalchemy.Vector.

    Used by search / text normalization:
        pg_similarity
        unaccent
    """
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_similarity;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))


def _default_for_non_nullable(col: Column) -> str:
    """
    Return a safe PostgreSQL default for a new NOT NULL column.

    This is used only when adding a missing NOT NULL column through
    ALTER TABLE. PostgreSQL needs a value for existing rows.
    """
    if isinstance(col.type, Boolean):
        return "FALSE"

    if isinstance(col.type, (Integer, Numeric)):
        return "0"

    if isinstance(col.type, (String, Text)):
        return "''"

    if isinstance(col.type, DateTime):
        return "'1970-01-01 00:00:00'"

    if isinstance(col.type, SAEnum):
        raise ValueError(
            f"Cannot safely add non-nullable enum column '{col.name}' "
            "without an explicit valid default."
        )

    return "''"


def _ensure_columns_postgres(
    base,
    engine,
    cols: list[str] | None = None,
) -> None:
    """
    For each table in `base`, if a model column does not exist in the actual
    PostgreSQL table yet, add it via ALTER TABLE.

    This only handles simple column additions. It does not add indexes,
    foreign keys, unique constraints, check constraints, or enum migrations.
    For those, use Alembic.
    """
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    preparer = engine.dialect.identifier_preparer

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            table_name = table.name
            schema_name = table.schema

            existing_cols = {
                col["name"]
                for col in inspector.get_columns(table_name, schema=schema_name)
            }

            if schema_name:
                full_table_name = (
                    f"{preparer.quote_schema(schema_name)}.{preparer.quote(table_name)}"
                )
            else:
                full_table_name = preparer.quote(table_name)

            target_cols = cols or [c.name for c in table.c]

            for col_name in target_cols:
                if col_name not in table.c:
                    continue

                if col_name in existing_cols:
                    continue

                model_col: Column = table.c[col_name]

                quoted_col_name = preparer.quote(col_name)
                col_type = model_col.type.compile(dialect=engine.dialect)

                nullable_sql = "" if model_col.nullable else " NOT NULL"
                default_sql = ""

                if not model_col.nullable:
                    default_sql = f" DEFAULT {_default_for_non_nullable(model_col)}"

                print(
                    f"[MIGRATION] Adding column '{col_name}' "
                    f"to table '{full_table_name}'"
                )

                conn.execute(
                    text(
                        f"ALTER TABLE {full_table_name} "
                        f"ADD COLUMN {quoted_col_name} "
                        f"{col_type}{nullable_sql}{default_sql};"
                    )
                )

                existing_cols.add(col_name)


def drop_step_vote_event_fks(engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE bill_steps "
                "DROP CONSTRAINT IF EXISTS bill_steps_vote_event_id_fkey;"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE motion_steps "
                "DROP CONSTRAINT IF EXISTS motion_steps_vote_event_id_fkey;"
            )
        )


def create_database(db_url: str = settings.DB_URL) -> bool:
    """
    Create all database tables in PostgreSQL using SQLAlchemy metadata.

    This creates missing tables and adds simple missing columns to existing
    tables. For real schema changes, use Alembic migrations.
    """
    engine = create_engine(db_url)

    try:
        _enable_extensions(engine)

        # Creates missing tables only.
        Base.metadata.create_all(bind=engine)

        # Adds simple missing columns to existing tables.
        _ensure_columns_postgres(Base, engine)

        # Drops specific FK constraints you do not want in the physical schema.
        drop_step_vote_event_fks(engine)

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"Database initialized successfully with {len(tables)} tables.")
        return True

    except SQLAlchemyError as error:
        print(f"Error creating database schema: {error}")
        return False

    except ValueError as error:
        print(f"Error applying lightweight schema migration: {error}")
        return False


if __name__ == "__main__":
    create_database()

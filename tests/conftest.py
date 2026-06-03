import unicodedata
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.database import models as db_models


def sqlite_unaccent(value):
    if value is None:
        return None

    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def sqlite_jarowinkler(left, right):
    if left is None or right is None:
        return 0.0

    return 1.0 if left == right else 0.0


@pytest.fixture(scope="function")
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function("unaccent", 1, sqlite_unaccent)
        dbapi_connection.create_function("jarowinkler", 2, sqlite_jarowinkler)

    db_models.Base.metadata.create_all(engine)

    yield engine

    db_models.Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def session(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()

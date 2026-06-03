import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database.raw_models import Base as RawBase

connect_args = {"check_same_thread": False} if os.getenv("ENV") == "dev" else {}
engine = create_engine(
    settings.RAW_DB_URL,
    connect_args=connect_args,
)
RawBase.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

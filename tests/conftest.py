import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.raw_models import RawBase

# repo root: .../OpenPeru
ROOT = Path(__file__).resolve().parents[1]

# Ensure root is on sys.path so `import backend` works
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def raw_session(tmp_path):
    db_path = tmp_path / "raw_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    RawBase.metadata.create_all(engine)  # <-- this prevents "no such table"

    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
        session.rollback()

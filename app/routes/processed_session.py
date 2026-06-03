from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings

db_engine = create_engine(settings.DB_URL, pool_pre_ping=True)
SessionProcessed = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

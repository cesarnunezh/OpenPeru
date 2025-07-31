import os
from eralchemy import render_er
from sqlalchemy import create_engine
from estecon.backend.database.models import Base
from estecon.backend.config import settings

connect_args = {"check_same_thread": False} if os.getenv("ENV") == "dev" else {}
engine = create_engine(
    settings.DB_URL,
    connect_args=connect_args,
)
Base.metadata.create_all(engine)


render_er(Base, "estecon/backend/database/schema_graph.png")

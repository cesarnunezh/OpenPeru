from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Import all models from the models.py file
from .models import (
    Base
)

def create_database():
    """
    Create SQLite database with all tables from the models.
    """
    
    database_url = "sqlite:///OpenPeru.db"
    engine = create_engine(database_url)
    
    try:
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = [row[0] for row in result.fetchall()]
        
        print(f"Database created successfully with {len(tables)} tables")
        return True
        
    except SQLAlchemyError as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    create_database()
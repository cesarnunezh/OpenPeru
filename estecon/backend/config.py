import os
from pydantic_settings import BaseSettings
from pathlib import Path

# Directories
class Directories:
    """
    Directories used by the application.

    Attributes:
        ROOT_DIR (Path): The root directory of the project.
        DATA (Path): The directory containing data.
        RAW_DATA (Path): The directory containing raw data.
        PROCESSED_DATA (Path): The directory containing processed data.
        LOGS (Path): The directory containing logs.
    """
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    DATA = ROOT_DIR / "data"
    RAW_DATA = DATA / "raw"
    PROCESSED_DATA = DATA / "processed"
    LOGS = ROOT_DIR / "logs"

    def __init__(self):
        for dir in [self.DATA, self.RAW_DATA, self.PROCESSED_DATA, self.LOGS]:
            dir.mkdir(exist_ok=True)

directories = Directories()

# Settings
class Settings(BaseSettings):
    """
    Settings for the application.

    The settings are loaded from the following sources in order of priority:

    1. Environment variables
    2. `.env` file in the root directory of the project
    3. Default values

    The settings are used to configure the application, such as setting up the database connection.
    """
    # This should change depending on where the DB will be stored
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///{directories.RAW_DATA.as_posix()}/openperu.db")
    # Uncomment this 
    # AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID")
    # AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY")
    # AWS_REGION: str = os.getenv("AWS_REGION")
    # AWS_S3_BUCKET_NAME: str = os.getenv("AWS_S3_BUCKET_NAME")
    
    # This is only in case we need some API_KEYS. Allow us to handle safely.
    class Config:
        env_file = directories.ROOT_DIR / ".env"

settings = Settings()
import os
from loguru import logger
from pathlib import Path
from tqdm import tqdm

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


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

    ROOT_DIR = Path(__file__).resolve().parent.parent
    DATA = ROOT_DIR / "data"
    RAW_DATA = DATA / "raw"
    PROCESSED_DATA = DATA / "processed"
    DOCUMENTS = RAW_DATA / "documents"
    BILL_DOCUMENTS = DOCUMENTS / "bills"
    MOTION_DOCUMENTS = DOCUMENTS / "motions"
    LOGS = ROOT_DIR / "logs"

    def __init__(self):
        for dir in [
            self.DATA,
            self.RAW_DATA,
            self.PROCESSED_DATA,
            self.DOCUMENTS,
            self.BILL_DOCUMENTS,
            self.MOTION_DOCUMENTS,
            self.LOGS,
        ]:
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
    DB_URL: str = os.getenv(
        "DB_URL", f"sqlite:///{directories.PROCESSED_DATA.as_posix()}/OpenPeru.db"
    )
    RAW_DB_URL: str = os.getenv(
        "RAW_DB_URL", f"sqlite:///{directories.RAW_DATA.as_posix()}/OpenPeruRaw.db"
    )
    AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str | None = os.getenv("AWS_REGION")
    AWS_S3_BUCKET_NAME: str | None = os.getenv("AWS_S3_BUCKET_NAME")
    AWS_S3_PREFIX: str | None = os.getenv("AWS_S3_PREFIX")

    # This is only in case we need some API_KEYS. Allow us to handle safely.
    model_config = ConfigDict(env_file=directories.ROOT_DIR / ".env")


settings = Settings()


def stop_logging_to_console(
    filename: str = directories.LOGS / "main.log", mode: str = "a"
):
    """
    Stops logging messages to the console and redirects them to a file.

    This function removes all existing logging handlers, effectively stopping
    any logging to the console. It then adds a new logging handler that writes
    log messages to the specified file. This is useful for capturing log
    messages in a file instead of displaying them in the console.

    Parameters
    ----------
    filename : str
        The path of the file where log messages should be written.
    mode : str, optional
        The mode in which the file is opened. Default is "a", which means
        append mode. Use "w" for write mode to overwrite the file.
    """
    for handler_id in list(logger._core.handlers.keys()):
        logger.remove(handler_id)

    # Add new logger
    logger.add(
        filename,
        format="{file}:{function}:{line} {time} {level} {message}",
        level="INFO",
        colorize=True,
        catch=True,
        mode=mode,
    )


def resume_logging_to_console():
    """
    Resumes logging messages to the console using tqdm for writing.

    This function adds a new logging handler that writes log messages to the
    console. The messages are displayed using tqdm's write function, which is
    useful for keeping log messages separate from progress bar outputs.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)

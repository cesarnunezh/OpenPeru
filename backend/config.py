import os
from contextlib import contextmanager
from datetime import date, datetime
from loguru import logger
from pathlib import Path
from collections.abc import Iterator
from tqdm import tqdm
from zoneinfo import ZoneInfo

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
    LOGS_SCRAPERS = LOGS / "scrapers"
    LOGS_PROCESS = LOGS / "process"

    def __init__(self):
        for dir in [
            self.DATA,
            self.RAW_DATA,
            self.PROCESSED_DATA,
            self.DOCUMENTS,
            self.BILL_DOCUMENTS,
            self.MOTION_DOCUMENTS,
            self.LOGS,
            self.LOGS_SCRAPERS,
            self.LOGS_PROCESS,
        ]:
            dir.mkdir(exist_ok=True)

    @classmethod
    def scraper_log(cls, scraper_name: str, log_date: date | None = None) -> Path:
        log_date = log_date or date.today()

        scraper_log_dir = cls.LOGS_SCRAPERS / scraper_name
        scraper_log_dir.mkdir(parents=True, exist_ok=True)

        return scraper_log_dir / f"{log_date.isoformat()}.log"

    @classmethod
    def process_log(cls, process_name: str, log_date: date | None = None) -> Path:
        log_date = log_date or date.today()

        process_log_dir = cls.LOGS_PROCESS / process_name
        process_log_dir.mkdir(parents=True, exist_ok=True)

        return process_log_dir / f"{log_date.isoformat()}.log"


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
        "DB_URL",
        "postgresql+psycopg://opencongress:opencongress@localhost:5999/opencongress",
    )
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "/app/data/raw/OpenPeruRaw.db")
    AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str | None = os.getenv("AWS_REGION")
    AWS_S3_BUCKET_NAME: str | None = os.getenv("AWS_S3_BUCKET_NAME")
    AWS_S3_PREFIX: str | None = os.getenv("AWS_S3_PREFIX")

    # This is only in case we need some API_KEYS. Allow us to handle safely.
    model_config = ConfigDict(env_file=directories.ROOT_DIR / ".env", extra="allow")


settings = Settings()


class LogManager:
    """
    Manage project logging destinations.

    Supports:
    - logging to console with tqdm.write
    - logging to a custom file
    - logging to daily scraper files
    - logging to daily process files
    """

    LOG_FORMAT = "{time} | {level} | {file}:{function}:{line} | {message}"

    def __init__(self, directories: Directories):
        self.directories = directories
        self.time_zone = ZoneInfo("America/Lima")
        self._console_sink_id: int | None = None

    def daily_log_file(
        self,
        base_log_dir: Path,
        name: str,
        log_date: date | None = None,
    ) -> Path:
        """
        Return a daily log file path.

        Example
        -------
        logs/scrapers/2026-05-13/bills.log
        logs/process/2026-05-13/bills.log
        """

        log_date = log_date or datetime.now(self.time_zone).date()

        return base_log_dir / log_date.isoformat() / f"{name}.log"

    def setup_console(self) -> None:
        if self._console_sink_id is not None:
            return

        logger.remove()
        self._console_sink_id = logger.add(
            lambda msg: tqdm.write(msg, end=""),
            format=self.LOG_FORMAT,
            level="INFO",
            colorize=True,
            catch=True,
            filter=lambda record: record["extra"].get("console", False),
        )

    def add_file_sink(
        self,
        filename: str | Path,
        mode: str = "a",
        log_kind: str | None = None,
        log_stage: str | None = None,
    ) -> int:
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)

        def stage_filter(record) -> bool:
            extra = record["extra"]
            if log_kind is not None and extra.get("log_kind") != log_kind:
                return False
            if log_stage is not None and extra.get("log_stage") != log_stage:
                return False
            return True

        return logger.add(
            filename,
            format=self.LOG_FORMAT,
            level="INFO",
            colorize=False,
            catch=True,
            mode=mode,
            encoding="utf-8",
            filter=stage_filter,
        )

    def add_stage_logger(
        self,
        log_kind: str,
        stage_name: str,
        log_date: date | None = None,
        mode: str = "a",
    ) -> int:
        if log_kind == "scraper":
            base_log_dir = self.directories.LOGS_SCRAPERS
        elif log_kind == "process":
            base_log_dir = self.directories.LOGS_PROCESS
        else:
            base_log_dir = self.directories.LOGS

        filename = self.daily_log_file(
            base_log_dir,
            stage_name,
            log_date,
        )

        return self.add_file_sink(
            filename,
            mode=mode,
            log_kind=log_kind,
            log_stage=stage_name,
        )

    @contextmanager
    def stage(
        self,
        log_kind: str,
        stage_name: str,
        log_date: date | None = None,
        mode: str = "a",
    ) -> Iterator:
        self.setup_console()
        sink_id = self.add_stage_logger(log_kind, stage_name, log_date, mode)
        try:
            with logger.contextualize(log_kind=log_kind, log_stage=stage_name):
                yield logger.bind(log_kind=log_kind, log_stage=stage_name)
        finally:
            logger.remove(sink_id)

    def console_logger(self):
        self.setup_console()
        return logger.bind(console=True)


log_manager = LogManager(directories)

from datetime import date

from loguru import logger

from backend.config import LogManager, log_manager, tqdm


class _TestDirectories:
    def __init__(self, root):
        self.LOGS = root / "logs"
        self.LOGS_SCRAPERS = self.LOGS / "scrapers"
        self.LOGS_PROCESS = self.LOGS / "process"


def test_stage_logger_routes_contextual_records_to_stage_file(tmp_path):
    manager = LogManager(_TestDirectories(tmp_path))

    try:
        with manager.stage("scraper", "bills", log_date=date(2026, 5, 15)):
            logger.info("bill detail")

        with manager.stage("scraper", "motions", log_date=date(2026, 5, 15)):
            logger.info("motion detail")

        bills_log = (
            tmp_path / "logs" / "scrapers" / "2026-05-15" / "bills.log"
        ).read_text()
        motions_log = (
            tmp_path / "logs" / "scrapers" / "2026-05-15" / "motions.log"
        ).read_text()

        assert "bill detail" in bills_log
        assert "motion detail" not in bills_log
        assert "motion detail" in motions_log
        assert "bill detail" not in motions_log
    finally:
        logger.remove()
        log_manager._console_sink_id = None


def test_console_sink_only_emits_console_records(tmp_path, monkeypatch):
    messages = []
    manager = LogManager(_TestDirectories(tmp_path))
    monkeypatch.setattr(tqdm, "write", lambda msg, end="": messages.append(msg))

    try:
        manager.setup_console()

        logger.info("file-only detail")
        manager.console_logger().info("console summary")

        assert not any("file-only detail" in message for message in messages)
        assert any("console summary" in message for message in messages)
    finally:
        logger.remove()
        log_manager._console_sink_id = None

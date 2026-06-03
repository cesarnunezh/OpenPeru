# Scrapers Module

This module extracts raw data from Congress endpoints/web pages and stores it in raw tables.

## Files

- `bills.py`, `motions.py`, `leyes.py`: scrape bill/motion/leyes JSON/XML payloads into `RawBill`/`RawMotion`/`RawLeyes`.
- `bills_documents.py`, `motions_documents.py`: extract and OCR documents into raw document tables.
- `congresistas.py`, `bancadas.py`, `committees.py`, `organizations.py`: scrape reference entities.
- `utils.py`: HTTP helpers, parsing helpers, OCR/PDF support.

## Output

Scrapers write to raw SQLAlchemy models in `backend/database/raw_models.py`.

Tracking fields on raw records:

- `last_update`: marks latest snapshot for an entity/version key.
- `changed`: whether latest snapshot differs from previous one.
- `processed`: whether latest snapshot still needs processing into clean tables.

## Typical use

You can run individual scraper scripts directly, but recommended usage is through the orchestrator:

```bash
uv run python -m backend --scrape
```

Useful options (from orchestrator):

- `--weekly-days N`: refresh stale non-approved bills/motions older than `N` days.
- `--only-bills`, `--only-motions`, `--only-others`.
- `--scrape-documents`.

## Logging

Some scripts route logs to files via `stop_logging_to_console(...)` from `backend/config.py`.
By default, logs are stored under `logs/`.

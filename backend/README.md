# OpenPeru Backend

This directory contains the OpenPeru data pipeline. It scrapes official Peruvian
Congress sources, stores raw snapshots, transforms them into normalized schemas,
and loads them into a clean relational database for analysis and future API or
dashboard layers.

## What lives here

- `backend/__main__.py` and `backend/cli.py`: CLI entrypoint and pipeline control.
- `backend/scrapers/`: raw extraction layer for HTML, API, and PDF sources.
- `backend/process/`: transformation layer for schema normalization and validation.
- `backend/database/`: raw and processed SQLAlchemy models, CRUD helpers, sessions, and orchestration.

Supporting docs:

- [`backend/scrapers/README.md`](./scrapers/README.md)
- [`backend/process/README.md`](./process/README.md)
- [`backend/database/README.md`](./database/README.md)

## Requirements

- Python `>= 3.13`
- `uv` for dependency management

## Setup

From the repository root:

```bash
uv sync
```

Optional pre-commit hooks:

```bash
uv run pre-commit install
```

Runtime dependency extras are intentionally separated from the default install:

- `ocr`: GPU/LLM OCR tooling, including Chandra and Transformers.
- `embeddings`: semantic embedding rebuild tooling.
- `documents`: S3 document upload/download dependencies.
- `analysis`: local analysis and notebook-oriented packages.

The Docker cron image uses only the default runtime dependencies.

## Create Databases

The project is currently working with local SQLite databases. Either download
them or create them from scratch:

```bash
uv run python -m backend.database.build_db
```

By default this creates or updates:

- Raw database: `data/raw/OpenPeruRaw.db`
- Processed database: `data/processed/OpenPeru.db`

## How To Run

The backend is executed through the module entrypoint.

Show the CLI help:

```bash
uv run python -m backend --help
```

Process pending raw records without scraping:

```bash
uv run python -m backend
```

Scrape then process all target groups:

```bash
uv run python -m backend --scrape
```

Scrape only and skip processing:

```bash
uv run python -m backend --scrape --skip-processing
```

Run a specific scraper target:

```bash
uv run python -m backend --scrape --skip-processing --only-bills
uv run python -m backend --scrape --skip-processing --only-motions
uv run python -m backend --scrape --skip-processing --only-leyes
uv run python -m backend --scrape --skip-processing --only-others --only-current
```

Scrape pending bill and motion documents:

```bash
uv run python -m backend --scrape --scrape-documents
```

Skip loading documents during processing:

```bash
uv run python -m backend --no-documents
```

## Makefile Targets

Scheduled jobs and local operational runs should use the Makefile targets:

```bash
make scrape-others
make scrape-bills
make scrape-motions
make scrape-leyes
make process
```

The targets map to the backend CLI:

- `scrape-others`: scrapes congresistas, bancadas, committees, and organizations for the current period.
- `scrape-bills`: scrapes bills only, without processing.
- `scrape-motions`: scrapes motions only, without processing.
- `scrape-leyes`: scrapes leyes only, without processing.
- `process`: processes raw records into clean tables.

## Docker Cron Service

The Docker Compose `cron` service runs the Makefile targets on a daily
`America/Lima` schedule. Job output is written to `/app/logs/cron.log`.

```bash
docker compose up cron
```

The current schedule is:

- `00:00`: `scrape-others`
- `01:00`: `scrape-bills`
- `02:00`: `scrape-motions`
- `03:00`: `scrape-leyes`
- `07:00`: `process`

The cron image is intentionally light for ETL runtime usage. It excludes CUDA,
LLM OCR, embedding, notebook, and test packages from the default install.

## CLI Reference

The orchestrator exposes these flags:

- `--scrape`: run scrapers before processing.
- `--skip-processing`: do not run raw-to-clean processing.
- `--only-current`: scrape only the current period where supported.
- `--scrape-documents`: scrape pending bill and motion documents.
- `--no-documents`: skip loading documents in processing.

Mutually exclusive target groups:

- `--only-bills`
- `--only-motions`
- `--only-leyes`
- `--only-others`

## Scraper Refresh Semantics

Bills and motions scrape new IDs first, then refresh pending daily rows that are
not approved and whose latest raw snapshot is older than one day. Leyes scrape
new IDs. Reference scrapers skip work when their latest raw scrape is already
recent.

## Tracking Semantics In Raw Tables

Raw tables track whether a scraped record is new, changed, or already processed.
This enables fast incremental processing.

For the latest raw snapshot per record key:

- First version of a record: `last_update = True`, `changed = True`, `processed = False`
- Unchanged rescrape: `last_update = True`, `changed = False`, `processed = True`
- Changed rescrape: `last_update = True`, `changed = True`, `processed = False`

Processing should focus on raw rows where `last_update = True`,
`changed = True`, and `processed = False`.

## Tests

Run the full test suite from the repo root:

```bash
uv run pytest -q
```

You can also run focused tests:

```bash
uv run pytest -q tests/scrapers
uv run pytest -q tests/process
uv run pytest -q tests/database
```

## Logging

Scrapers and pipeline steps write logs to the `logs/` directory. If a run fails,
the logs are usually the fastest way to understand which source or parsing rule
changed.

## Contributing

See `CONTRIBUTING.md` in the repository root.

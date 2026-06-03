# OpenPeru Backend

This directory contains the OpenPeru data pipeline. It scrapes official Peruvian Congress sources, stores raw snapshots, transforms them into normalized schemas, and loads them into a clean relational database for analysis and future API or dashboard layers.

## What lives here

• `backend/__main__.py` and `backend/cli.py` (cli entrypoint and pipeline control)

• `backend/scrapers/` raw extraction layer (HTML and PDF sources)

• `backend/process/` transformation layer (schema normalization and validation)

• `backend/database/` raw and processed SQLAlchemy models, CRUD helpers, sessions, and DB orchestration

Supporting docs

• [`backend/scrapers/README.md`](./scrapers/README.md)

• [`backend/process/README.md`](./process/README.md)

• [`backend/database/README.md`](./database/README.md)

## Requirements

• Python `>= 3.13`

• `uv` for dependency management

## Setup

From the repository root:

```bash
uv sync
```

Optional pre-commit hooks:

```bash
uv run pre-commit install
```

## Create databases

The project is currently working with a local SQLite database. Either download it or create them from scratch. Initialize or update the SQLite databases:

```bash
uv run python -m backend.database.build_db
```

By default this creates or updates

• Raw database: `data/raw/OpenPeruRaw.db`

• Processed database: `data/processed/OpenPeru.db`

## How to run

The backend is executed through the module entrypoint.

Show the CLI help

```bash
uv run python -m backend --help
```

### Common commands

Process only pending raw records, without scraping (default behavior)

```bash
uv run python -m backend
```

Scrape then process everything

```bash
uv run python -m backend --scrape
```

Scrape only, skip processing

```bash
uv run python -m backend --scrape --skip-processing
```

### Run a specific target group to scrape

Bills only

```bash
uv run python -m backend --scrape --only-bills
```

Motions only

```bash
uv run python -m backend --scrape --only-motions
```

Others only (congresistas, bancadas, committees, organizations)

```bash
uv run python -m backend --scrape --only-others
```

### Current period only

Where supported, scrape only the current legislative period (only supported for congresistas, bancadas, committees and organizations)

```bash
uv run python -m backend --scrape --only-current
```

### Incremental refresh windows

Refresh stale non approved bills and motions older than N days

```bash
uv run python -m backend --scrape --weekly-days 7
```

Skip scraping others (congresistas, bancadas, committees and organizations) if their latest raw scrape is within N days

```bash
uv run python -m backend --scrape --others-days 14
```

### Scrape numeric ranges

Bills

```bash
uv run python -m backend --scrape --bill-year 2021 --bill-start 1 --bill-end 200
```

Motions

```bash
uv run python -m backend --scrape --motion-year 2021 --motion-start 1 --motion-end 200
```

Leyes

```bash
uv run python -m backend --scrape --ley-start 31222 --ley-end 31250
```

### Documents

Scrape pending bill and motion documents

```bash
uv run python -m backend --scrape --scrape-documents
```

Download PDFs from RawDB document links

```bash
uv run python -m backend --download-documents
```

Limit downloads per type (bills/motions)

```bash
uv run python -m backend --download-documents --download-documents-limit 100
```

Download PDFs and upload to AWS S3 (requires AWS_* env vars)

```bash
uv run python -m backend --download-documents --upload-documents-s3
```

Skip loading documents during processing

```bash
uv run python -m backend --scrape --no-documents
```

### Processing limits

Limit the number of raw rows processed (useful for debugging)

```bash
uv run python -m backend --process-bills-limit 200
uv run python -m backend --process-motions-limit 200
```

## CLI reference

The orchestrator exposes these flags.

• `--scrape` run scrapers before processing

• `--skip-processing` do not run raw to clean processing

• `--only-current` scrape only the current period where supported

• `--weekly-days N` refresh stale non approved bills and motions older than N days

• `--others-days N` skip congresistas, bancadas, committees, organizations scrape when the latest raw scrape is within N days

Mutually exclusive target groups

• `--only-bills`

• `--only-motions`

• `--only-others`

Optional range filters

• `--bill-year YEAR`, `--bill-start A`, `--bill-end B`

• `--motion-year YEAR`, `--motion-start A`, `--motion-end B`

• `--ley-start A`, `--ley-end B`


Documents

• `--scrape-documents` scrape pending bill and motion documents

• `--download-documents` download PDFs from RawDB document links

• `--download-documents-limit` limit the number of documents downloaded per type (bills/motions)

• `--update-documents` re-download PDFs even if they already exist locally

• `--upload-documents-s3` upload downloaded PDFs to the configured AWS S3 bucket

• `--no-documents` skip loading documents in processing stage

Processing limits

• `--process-bills-limit N`

• `--process-motions-limit N`

## Tracking semantics in raw tables

Raw tables track whether a scraped record is new, changed, or already processed. This is what enables fast incremental runs.

For the latest raw snapshot per record key

• First version of a record: `last_update = True`, `changed = True`, `processed = False`

• Unchanged re scrape: `last_update = True`, `changed = False`, `processed = True`

• Changed re scrape: `last_update = True`, `changed = True`, `processed = False`

Processing should focus on raw rows where `last_update = True`, `changed = True` and `processed = False`.

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

Scrapers and pipeline steps write logs to the `logs/` directory. If a run fails, the logs are usually the fastest way to understand which source or parsing rule changed.

## Contributing

See `CONTRIBUTING.md` in the repository root.

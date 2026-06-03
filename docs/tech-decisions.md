# Technical Decisions Record

This document tracks the major technical decisions made in this project, including the rationale behind each choice. It serves as a reference for current and future contributors to understand why the project is built the way it is.

Each decision includes the context that motivated it, the alternatives considered, and the reasoning for the final choice. Decisions are grouped by category.

---

## Language and Runtime

### Python as the core backend language

- **Decision**: Use Python as the sole backend language.
- **Context**: The project involves web scraping, PDF processing, OCR, data transformation, and database modeling — all domains where Python has mature, well-maintained libraries.
- **Alternatives considered**: Node.js (strong for web scraping, weaker for data processing), R (strong for analysis, weaker for scraping and infrastructure).
- **Rationale**: Python provides the broadest coverage across all project needs with a single language. The team has strong Python experience. The ecosystem for OCR (Tesseract bindings, OCR AI-driven APIs), PDF extraction (PyMuPDF), and data modeling (SQLAlchemy, Pydantic) is unmatched.

## Dependency Management

### uv (astral)

- **Decision**: Use `uv` for dependency management and Python version management.
- **Context**: The project needs reproducible builds, fast dependency resolution, and lockfile support.
- **Alternatives considered**: pip + pip-tools (manual, slower), conda or micromamba.
- **Rationale**: `uv` provides dramatically faster dependency resolution, built-in lockfile support (`uv.lock`), and Python version management in a single tool. It's compatible with `pyproject.toml` standards and reduces CI/CD times.

## Web Scraping

### Selenium and Playwright for dynamic pages

- **Decision**: Use both Selenium (`selenium>=4.33.0`) and Playwright (`playwright>=1.58.0`) for scraping dynamic web pages.
- **Context**: The Congress website uses JavaScript-heavy pages that require browser automation to fully render content.
- **Alternatives considered**: Using only one browser automation tool.
- **Rationale**: Selenium was the original choice and remains in use for established scrapers. Playwright was adopted later for new scrapers due to its faster execution, better async support, and more reliable waiting mechanisms. Both coexist because rewriting existing Selenium scrapers offers no immediate value. New scrapers should prefer Playwright.

### httpx for static pages and API calls

- **Decision**: Use `httpx[http2]>=0.28.1` for HTTP requests that don't require browser rendering.
- **Context**: Many Congress data sources are static HTML or XML endpoints that don't need a full browser.
- **Alternatives considered**: requests (synchronous only), aiohttp (async but less ergonomic).
- **Rationale**: httpx supports both sync and async modes, HTTP/2, and has a cleaner API than alternatives. HTTP/2 support reduces connection overhead when scraping multiple pages from the same host.

## OCR Processing

### Tesseract + PyMuPDF + OpenCV as the OCR stack

- **Decision**: Use `pytesseract`, `pymupdf`, and `opencv-python` for PDF OCR.
- **Context**: Congressional bills and motions are often scanned PDFs with no embedded text layer. Text must be extracted via OCR to be processed by the pipeline.
- **Alternatives considered**: EasyOCR (no Spanish fine-tuning, slower), Google Cloud Vision (external dependency, per-page cost), PaddleOCR (heavier install, overkill for current volume).
- **Rationale**: PyMuPDF renders each PDF page as a pixmap at 300 DPI; OpenCV applies binarization to improve contrast on low-quality scans; Tesseract extracts text with Spanish language support (`lang="spa"`, PSM 6). The pipeline is self-contained, runs fully offline, and requires no API credentials. See `backend/scrapers/utils.py`.

## Data Processing

### Polars for tabular data operations

- **Decision**: Use `polars>=1.30.0` for tabular data operations in the processing layer.
- **Context**: The processing layer serializes structured records to JSON output (e.g., `gen_congresistas_df` in `backend/process/utils.py`). Polars is currently used in one utility function but is the designated library for all future tabular work.
- **Alternatives considered**: pandas (ubiquitous but heavier API, slower for large frames), plain `json.dump` (sufficient for current usage but doesn't scale).
- **Rationale**: Polars' lazy evaluation and Apache Arrow memory format make it significantly faster than pandas for large DataFrames. Its strict null-handling and explicit type system align with the project's validation approach. Adopting it early avoids a future migration away from pandas.

### lxml for HTML and XML parsing

- **Decision**: Use `lxml>=5.3.1` for parsing HTML and XML responses from Congress data sources.
- **Context**: Several Congress data sources return XML feeds or structured HTML that needs robust, standards-compliant parsing.
- **Alternatives considered**: BeautifulSoup (friendlier API but requires a separate parser backend and is slower), stdlib `html.parser` (tolerant of malformed HTML but slow and limited).
- **Rationale**: lxml is the fastest Python HTML/XML parser with full XPath support. It handles malformed markup more reliably than the stdlib and integrates naturally with httpx response bytes.

## Database

### SQLAlchemy ORM

- **Decision**: Use SQLAlchemy (`sqlalchemy>=2.0.41`) for all database modeling and persistence.
- **Context**: The project needs a robust ORM that supports multiple database backends, migration-friendly schema definitions, and relationship modeling.
- **Alternatives considered**: Raw SQL (harder to maintain), Django ORM (would pull in the full Django framework), Tortoise ORM (async-only, less mature).
- **Rationale**: SQLAlchemy 2.0+ provides modern Python typing support, both sync and async execution, and is the most mature Python ORM. Its backend-agnostic design supports the planned migration from SQLite to PostgreSQL.

### SQLite over PostgreSQL (for now)

- **Decision**: Use SQLite as the database engine for both raw and processed layers.
- **Context**: The project is in active development with a small team. Infrastructure overhead should be minimal.
- **Alternatives considered**: PostgreSQL (production-grade, required for some advanced features), DuckDB (analytical, not suited for concurrent writes).
- **Rationale**: SQLite requires zero infrastructure — no server, no configuration, no credentials. The database files can be versioned, shared, and inspected easily. The SQLAlchemy models are written to be portable, so migration to PostgreSQL is a schema change, not a rewrite. PostgreSQL will be adopted when the API layer requires concurrent access or when the vector store for semantic search needs to be co-located.

### Two-layer database design (raw / processed)

- **Decision**: Maintain separate raw and processed databases with distinct SQLAlchemy models.
- **Context**: Congressional data sources change format without warning. Parsing logic improves over time. Raw data must be preserved for reprocessing.
- **Alternatives considered**: Single database with raw columns alongside processed columns, ELT into a data warehouse.
- **Rationale**: Strict separation ensures raw data integrity. If a parser is improved, the processed layer can be fully regenerated from raw data without re-scraping. The `last_update`, `changed`, and `processed` flags on raw models support incremental processing — only new or changed records need to be reprocessed.

### Incremental processing flags on raw models

- **Decision**: All raw models include `timestamp`, `last_update`, `changed`, and `processed` boolean columns, with a custom `RawBase.__eq__` that ignores these metadata fields.
- **Context**: Scrapers run periodically. Most runs return identical data. The pipeline needs to efficiently detect and process only what changed.
- **Rationale**: The `last_update` flag marks the most recent scrape per entity. The custom equality check compares only data columns, setting `changed=True` when content differs from the previous scrape. The `processed` flag tracks whether changed data has been propagated to the processed layer. This avoids full-table reprocessing on every scraper run.

## Validation

### Pydantic for schema validation

- **Decision**: Use Pydantic (`pydantic>=2.11.7`) and Pydantic Settings (`pydantic-settings>=2.10.1`) for data validation and configuration management.
- **Context**: Data flowing from raw to processed must be validated against strict schemas. Application configuration (database paths, API keys, scraper settings) needs type-safe management.
- **Alternatives considered**: marshmallow (older, less Pythonic), attrs + cattrs (less ecosystem support), manual validation.
- **Rationale**: Pydantic 2.x is fast (Rust-backed validation), integrates naturally with Python type hints, and provides clear error messages when validation fails. Pydantic Settings handles `.env` files and environment variables for configuration.

### Domain enums at the database level

- **Decision**: Use Python Enums mapped to SQLAlchemy `Enum` columns for domain-constrained values (e.g., `VoteOption`, `LegPeriod`, `BillStepType`).
- **Context**: Many columns have a fixed set of valid values derived from the congressional domain.
- **Alternatives considered**: String columns with application-level validation only, check constraints.
- **Rationale**: Enum columns enforce constraints at the database level, preventing invalid data from entering the processed layer regardless of how it's inserted. They also serve as self-documenting schema — reading the enum definitions reveals the full set of valid values.

 ## Code Quality

### Ruff for linting and formatting

- **Decision**: Use `ruff` as the sole linter and formatter, enforced via pre-commit hooks and CI.
- **Context**: The project needs consistent code style and early detection of common errors without slowing down developer workflow.
- **Alternatives considered**: flake8 + black + isort (three separate tools with separate configs), pylint (comprehensive but slow and noisy on a project this size).
- **Rationale**: Ruff replaces flake8, black, and isort in a single binary with near-instant execution (written in Rust). Pre-commit hooks apply formatting before code reaches the repository, eliminating style noise from diffs and CI failures.

## Testing

### Pytest

- **Decision**: Use Pytest (`pytest>=8.4.1`, `pytest-asyncio>=1.0.0`) for all testing.
- **Context**: The project has tests for scrapers, database models, and processing logic.
- **Alternatives considered**: unittest (stdlib, more verbose), nose2 (less maintained).
- **Rationale**: Pytest is the de facto standard for Python testing. Its fixture system, parametrization, and plugin ecosystem (including pytest-asyncio for testing async scrapers) make it the best fit.


## Logging

### Loguru over stdlib logging

- **Decision**: Use Loguru (`loguru>=0.7.3`) for all logging across scrapers and pipelines.
- **Context**: Scrapers run unattended and need structured, readable logs for debugging failures.
- **Alternatives considered**: Python stdlib logging (verbose configuration), structlog (more complex setup).
- **Rationale**: Loguru provides colored console output, file rotation, and structured logging with zero configuration. It's a single import (`from loguru import logger`) versus the multi-line boilerplate required by stdlib logging.


## Cloud and Storage

### boto3 for object storage

- **Decision**: Use boto3 (`boto3>=1.35.0`) for cloud object storage (S3-compatible).
- **Context**: Raw PDFs and scanned documents need to be archived beyond the local filesystem.
- **Alternatives considered**: Local-only storage, Google Cloud Storage client.
- **Rationale**: boto3 supports both AWS S3 and S3-compatible services (MinIO, DigitalOcean Spaces, etc.), providing flexibility in hosting. PDF archival is a write-once, read-rarely pattern that fits object storage well. S3 upload is opt-in per run via an `upload_s3` flag in `backend/documents/downloader.py` — the default is local storage only, so no AWS credentials are needed for development.

## AI Policy

### AI as reference, not author

- **Decision**: AI tools can be used for reference, explanation, refactoring review, and test generation, but never as the sole author of both tests and implementation for the same feature.
- **Context**: As documented in `CONTRIBUTING.md`, the project takes a deliberate position on AI-assisted development.
- **Rationale**: A human must be fully responsible for either the implementation or the test suite for any feature. This provides a safeguard against subtle architectural decisions and bugs that AI tools may introduce without full project context. AI-generated code must include proper attribution.

## Future Decisions (Pending)

The following decisions are expected to arise during the class development phase and will be recorded here when made:

- **Frontend framework**: React vs. Next.js vs. other
- **LLM provider and model**: OpenAI vs. Anthropic vs. open-source for bill summaries
- **Vector store**: pgvector vs. Qdrant vs. ChromaDB for semantic search embeddings
- **API framework**: FastAPI vs. Django REST Framework for the public API
- **Deployment**: Cloud provider and containerization strategy
- **Database migration**: When and how to move from SQLite to PostgreSQL if needed.
- **LLM-assisted OCR**: For complex or handwritten documents, a vision-capable LLM (e.g., DeepSeekOCR HuggingFace API, GOT-OCR, Surya) may outperform Tesseract. Requires GPU or external API. Evaluate when Tesseract accuracy on real scanned bills is measured.

# Process Module

This module transforms raw SQLAlchemy rows into validated, normalized Pydantic schemas.

## Files

- `schema.py`: core Pydantic schemas used by processing.
- `bills.py`, `motions.py`: map raw records into clean bill/motion DTOs.
- `billtext.py`: cut the normative-body slice from a bill PDF's raw text using known headings and trailing markers.
- `congresistas.py`, `organizations.py`, `bancadas.py`: process reference entities and memberships.
- `votes.py`: vote-related parsing helpers.
- `utils.py`: shared processing utilities.
- `chandra2.py`: OCR runner for bill documents using Chandra vLLM with 6 workers threads.
- `diff/`: three-layer hybrid bill-text diff (structural → line → word). Public surface is `compute_bill_difference` in `diff/__init__.py`; renderer contract in [`docs/bill_difference_contract.md`](../../docs/bill_difference_contract.md).

## Role in pipeline

- Input: raw models from `backend/database/raw_models.py`.
- Output: Pydantic models that are then persisted via DB CRUD helpers in the orchestrator flow.

This layer should stay:

- deterministic,
- side-effect free (no DB writes),
- strict about schema/normalization.

## How it is used

The orchestrator imports these functions and runs them in stage order:

1. load raw rows (`last_update=True`, `processed=False`)
2. process into schemas
3. upsert into clean DB models

## Chandra2 OCR

Run steps:

1. git clone --branch feature/chandra2-ocr-vllm --single-branch git@github.com:openperu2026/dev-opencongress.git
2. create .env
3. cd dev-opencongress
4. uv sync
5. uv run chandra_vllm
6. In a different terminal: uv run python -m backend.process.chandra2 [limit]
	- Default limit is 15 if not provided and is in a descending order of the bill_id

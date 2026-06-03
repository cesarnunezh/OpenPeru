# Process Module

This module transforms raw SQLAlchemy rows into validated, normalized Pydantic schemas.

## Files

- `schema.py`: core Pydantic schemas used by processing.
- `bills.py`, `motions.py`: map raw records into clean bill/motion DTOs.
- `congresistas.py`, `organizations.py`, `bancadas.py`: process reference entities and memberships.
- `votes.py`: vote-related parsing helpers.
- `utils.py`: shared processing utilities.

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

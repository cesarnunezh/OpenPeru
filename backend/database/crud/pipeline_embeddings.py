from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from sqlalchemy import select, desc, func, text, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend import EmbeddingModel
from backend.database import models as db_models
from backend.database.models import SEMANTIC_BILLS_HNSW_INDEX, DEFAULT_EMBEDDING_DIM
from sentence_transformers import SentenceTransformer


def drop_semantic_bills_hnsw_index(db: Session) -> None:
    """
    Drop the semantic_bills HNSW index before a large rebuild.

    Maintaining an HNSW index during a large insert/upsert is slower than
    recreating it after the data has been loaded.
    """

    db.execute(text(f"DROP INDEX IF EXISTS {SEMANTIC_BILLS_HNSW_INDEX}"))


def create_semantic_bills_hnsw_index(db: Session) -> None:
    """
    Create the semantic_bills HNSW index after a large rebuild.
    """

    db.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS {SEMANTIC_BILLS_HNSW_INDEX}
            ON semantic_bills
            USING hnsw (embedding vector_cosine_ops)
            WITH (
                m = 16,
                ef_construction = 64
            )
            """
        )
    )


def normalize_whitespace(text: str) -> str:
    """Normalize the whitespace in a text"""
    return re.sub(r"\s+", " ", text).strip()


def create_bill_full_text(
    bill: dict,
    authors: list[str],
    committees: list[str],
    bill_text: str | None,
) -> str | None:
    """
    Create the full semantic-search text for a bill.

    Returns None when the bill has no meaningful text to index.
    """

    title = bill.get("title") or ""
    summary = bill.get("summary_congreso") or ""
    authors_text = ", ".join(authors)
    committees_text = ", ".join(committees)
    body_text = bill_text or ""

    has_content = any(
        [
            title.strip(),
            summary.strip(),
            authors_text.strip(),
            committees_text.strip(),
            body_text.strip(),
        ]
    )

    if not has_content:
        return None

    full_text = f"""
Título: {title}

Sumilla: {summary}

Autores: {authors_text}

Comisiones: {committees_text}

Texto:
{body_text}
"""

    return normalize_whitespace(full_text)


def rebuild_semantic_bills(
    db: Session,
    bill_ids: list[str] | None = None,
    embedding_model_name: str = "intfloat/multilingual-e5-base",
) -> int:
    """
    Fully rebuild semantic_bills rows for a set of bills.

    If bill_ids is None, all bills are rebuilt.

    This function is intended for large semantic rebuilds, such as the first
    population of semantic_bills, changes to the text template, changes to the
    chunking logic, or switching embedding models.

    Args:
        db (Session): Active SQLAlchemy database session.
        bill_ids (list[str] | None): Bills to rebuild. If None, all bills are used.
        embedding_model_name (str): SentenceTransformer model used to generate embeddings.

    Returns:
        int: Number of semantic_bills rows inserted.
    """

    if bill_ids is None:
        bill_ids = list(db.execute(select(db_models.Bill.bill_id)).scalars())

    if not bill_ids:
        return 0

    drop_semantic_bills_hnsw_index(db)

    db.execute(
        delete(db_models.SemanticBill).where(
            db_models.SemanticBill.bill_id.in_(bill_ids),
            db_models.SemanticBill.embedding_model_name == embedding_model_name,
        )
    )

    inserted_count = bulk_upsert_semantic_bills(
        db=db,
        bill_ids=bill_ids,
        embedding_model_name=embedding_model_name,
    )

    create_semantic_bills_hnsw_index(db)

    return inserted_count


def create_bill_full_texts(
    db: Session,
    bill_ids: list[str],
) -> dict[str, str]:
    """
    Build full searchable text representations for multiple bills.

    The returned dictionary maps each bill ID to a structured text string that
    combines the bill title, congressional summary, authors, committees, and the
    latest available bill text.

    Args:
        db (Session): Active SQLAlchemy database session.
        bill_ids (list[str]): Bill IDs to process.

    Returns:
        dict[str, str]: Mapping from bill ID to its structured searchable text.
    """

    bill_ids = list(dict.fromkeys(bill_ids))

    if not bill_ids:
        return {}

    # 1. Bills: title + summary
    bill_rows = db.execute(
        select(
            db_models.Bill.id.label("bill_id"),
            db_models.Bill.title,
            db_models.Bill.summary_congreso,
        ).where(db_models.Bill.id.in_(bill_ids))
    ).all()

    bills_by_id = {
        row.bill_id: {
            "title": row.title or "",
            "summary_congreso": row.summary_congreso or "",
        }
        for row in bill_rows
    }

    # 2. Authors
    author_rows = db.execute(
        select(
            db_models.BillCongresistas.bill_id,
            db_models.Congresista.full_name,
        )
        .join(
            db_models.Congresista,
            db_models.BillCongresistas.person_id == db_models.Congresista.id,
        )
        .where(
            db_models.BillCongresistas.bill_id.in_(bill_ids),
            db_models.BillCongresistas.role_type == "Autor",
        )
        .order_by(
            db_models.BillCongresistas.bill_id,
            db_models.Congresista.full_name,
            db_models.Congresista.id,
        )
    ).all()

    authors_by_bill: dict[str, list[str]] = defaultdict(list)

    for bill_id, full_name in author_rows:
        if full_name:
            authors_by_bill[bill_id].append(full_name)

    # 3. Committees
    committee_rows = db.execute(
        select(
            db_models.BillOrganization.bill_id,
            db_models.Organization.org_name,
        )
        .join(
            db_models.Organization,
            db_models.BillOrganization.org_id == db_models.Organization.org_id,
        )
        .where(
            db_models.BillOrganization.bill_id.in_(bill_ids),
            db_models.Organization.org_type == "Comisión",
        )
        .order_by(
            db_models.BillOrganization.bill_id,
            db_models.Organization.org_name,
            db_models.Organization.org_id,
        )
    ).all()

    committees_by_bill: dict[str, list[str]] = defaultdict(list)

    for bill_id, org_name in committee_rows:
        if org_name:
            committees_by_bill[bill_id].append(org_name)

    # 4. Latest bill text per bill
    ranked_bill_texts = (
        select(
            db_models.BillText.bill_id.label("bill_id"),
            db_models.BillText.text.label("text"),
            func.row_number()
            .over(
                partition_by=db_models.BillText.bill_id,
                order_by=(
                    desc(db_models.BillStep.step_date),
                    desc(db_models.BillText.version_id),
                    desc(db_models.BillText.step_id),
                ),
            )
            .label("rn"),
        )
        .join(
            db_models.BillStep,
            (db_models.BillStep.bill_id == db_models.BillText.bill_id)
            & (db_models.BillStep.step_id == db_models.BillText.step_id),
        )
        .where(db_models.BillText.bill_id.in_(bill_ids))
        .subquery()
    )

    latest_text_rows = db.execute(
        select(
            ranked_bill_texts.c.bill_id,
            ranked_bill_texts.c.text,
        ).where(ranked_bill_texts.c.rn == 1)
    ).all()

    latest_text_by_bill = {bill_id: text or "" for bill_id, text in latest_text_rows}

    # Assemble final strings
    full_texts: dict[str, str] = {}

    for bill_id in bill_ids:
        bill = bills_by_id.get(
            bill_id,
            {
                "title": "",
                "summary_congreso": "",
            },
        )

        if bill is None:
            continue

        authors = authors_by_bill.get(bill_id, [])
        committees = committees_by_bill.get(bill_id, [])
        bill_text = latest_text_by_bill.get(bill_id, "")

        full_text = create_bill_full_text(
            bill=bill,
            authors=authors,
            committees=committees,
            bill_text=bill_text,
        )

        if full_text is None:
            continue

        full_texts[bill_id] = full_text

    return full_texts


def _get_text_chunks(
    text: str,
    embedding_model: SentenceTransformer,
    chunk_size: int = 384,
    overlap: int = 40,
) -> list[str]:
    """
    Split text into overlapping token-bounded chunks for embedding generation.

    This function uses the embedding model tokenizer instead of splitting by
    words. This avoids silent truncation for models with limited context windows,
    such as intfloat/multilingual-e5-* models.

    Args:
        text (str): Full text to split into chunks.
        embedding_model (SentenceTransformer): Embedding model whose tokenizer
            is used to split text.
        chunk_size (int): Maximum number of tokenizer tokens per chunk.
        overlap (int): Number of tokenizer tokens shared between consecutive
            chunks.

    Returns:
        list[str]: List of text chunks ready for embedding generation.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text or not text.strip():
        return []

    tokenizer = getattr(embedding_model, "tokenizer", None)

    if tokenizer is None:
        raise ValueError("embedding_model must expose a tokenizer")

    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False,
    )

    if not token_ids:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(token_ids):
        end = start + chunk_size
        chunk_token_ids = token_ids[start:end]

        chunk = tokenizer.decode(
            chunk_token_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(token_ids):
            break

        start = end - overlap

    return chunks


def validate_embedding_model_dimension(embedding_model: SentenceTransformer) -> None:
    dim = embedding_model.get_embedding_dimension()

    if dim != DEFAULT_EMBEDDING_DIM:
        raise ValueError(
            f"Embedding model dimension mismatch. "
            f"Database expects {DEFAULT_EMBEDDING_DIM}, but model returns {dim}."
        )


def build_semantic_bill_rows(
    db: Session,
    bill_ids: list[str],
    embedding_model_name: str,
    embedding_model: SentenceTransformer,
) -> list[dict]:
    """
    Build semantic-search rows for multiple bills.

    The function creates bill text chunks for all provided bills, embeds all
    chunks in batches, and returns dictionaries ready for bulk upsert.

    Args:
        db (Session): Active SQLAlchemy database session.
        bill_ids (list[str]): Bill IDs to process.
        embedding_model_name (str): Name of the SentenceTransformer model used to generate
            embeddings.
        embedding_model (SentenceTransformer): Loaded embedding model.

    Returns:
        list[dict]: Rows ready to be inserted or updated in the
            semantic_bills table.
    """

    texts: list[str] = []
    metadata: list[dict] = []

    full_texts_by_bill = create_bill_full_texts(db, bill_ids)

    for bill_id in bill_ids:
        full_text = full_texts_by_bill.get(bill_id, "")
        chunks = _get_text_chunks(
            text=full_text,
            embedding_model=embedding_model,
        )

        for chunk_index, chunk in enumerate(chunks):
            texts.append(chunk)
            metadata.append(
                {
                    "bill_id": bill_id,
                    "chunk_index": chunk_index,
                    "text": chunk,
                    "embedding_model_name": embedding_model_name,
                }
            )

    if not texts:
        return []

    embeddings = embedding_model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
    )

    return [
        {
            **meta,
            "embedding": embedding,
        }
        for meta, embedding in zip(metadata, embeddings)
    ]


@lru_cache(maxsize=2)
def _get_embedding_model(embedding_model_name: str) -> SentenceTransformer:
    """
    Load and cache embedding models per Python process.

    This avoids reloading model weights every time semantic rows are generated.
    """
    return SentenceTransformer(embedding_model_name)


def bulk_upsert_semantic_bills(
    db: Session,
    bill_ids: list[str],
    embedding_model_name: str = "intfloat/multilingual-e5-base",
    embedding_model: SentenceTransformer | None = None,
) -> int:
    """
    Generate and upsert semantic-search chunks for multiple bills.

    Args:
        db (Session): Active SQLAlchemy database session.
        bill_ids (list[str]): Bill IDs to process.
        embedding_model_name (str): SentenceTransformer model used to generate embeddings.

    Returns:
        int: Number of semantic chunk rows inserted or updated.
    """
    if embedding_model_name != EmbeddingModel.MULTILINGUAL_E5_BASE:
        raise ValueError(f"Unsupported embedding model: {embedding_model_name}")

    if not bill_ids:
        return 0

    if embedding_model is None:
        embedding_model = _get_embedding_model(embedding_model_name)

    validate_embedding_model_dimension(embedding_model)

    rows = build_semantic_bill_rows(
        db=db,
        bill_ids=bill_ids,
        embedding_model_name=embedding_model_name,
        embedding_model=embedding_model,
    )

    if not rows:
        return 0

    stmt = pg_insert(db_models.SemanticBill).values(rows)

    stmt = stmt.on_conflict_do_update(
        constraint="uq_semantic_bills_bill_chunk_model",
        set_={
            "text": stmt.excluded.text,
            "embedding": stmt.excluded.embedding,
        },
    )

    db.execute(stmt)
    db.flush()

    return len(rows)

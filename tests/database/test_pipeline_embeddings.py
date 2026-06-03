from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend import EmbeddingModel, Proponents, TypeBillStep
from backend.database.models import Base, Bill, BillStep, BillText, SemanticBill
from backend.database.crud.pipeline_embeddings import (
    _get_text_chunks,
    build_semantic_bill_rows,
    bulk_upsert_semantic_bills,
)


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return text.split()

    def decode(
        self,
        token_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ):
        return " ".join(token_ids)


class FakeEmbeddingModel:
    tokenizer = FakeTokenizer()

    def get_embedding_dimension(self):
        return 768

    def encode(self, texts, normalize_embeddings=True, batch_size=32):
        return [[float(index + 1)] * 768 for index, _ in enumerate(texts)]


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_get_text_chunks_returns_empty_for_blank_text():
    assert _get_text_chunks(" \n\t ", FakeEmbeddingModel()) == []


def test_get_text_chunks_validates_window_parameters():
    with pytest.raises(ValueError, match="chunk_size"):
        _get_text_chunks("uno dos", FakeEmbeddingModel(), chunk_size=0)

    with pytest.raises(ValueError, match="negative"):
        _get_text_chunks("uno dos", FakeEmbeddingModel(), overlap=-1)

    with pytest.raises(ValueError, match="smaller"):
        _get_text_chunks("uno dos", FakeEmbeddingModel(), chunk_size=2, overlap=2)


def test_get_text_chunks_uses_token_overlap():
    chunks = _get_text_chunks(
        "uno dos tres cuatro cinco",
        FakeEmbeddingModel(),
        chunk_size=3,
        overlap=1,
    )

    assert chunks == ["uno dos tres", "tres cuatro cinco"]


def test_empty_bill_text_builds_no_semantic_rows(session):
    session.add(
        Bill(
            id="B_EMPTY",
            title=" ",
            summary_congreso=" ",
            observations="",
            status="En trámite",
            proponent=Proponents.CONGRESO.value,
            author_id=None,
            bill_approved=False,
            summary_oc="",
        )
    )
    session.commit()

    rows = build_semantic_bill_rows(
        session,
        ["B_EMPTY"],
        EmbeddingModel.MULTILINGUAL_E5_BASE.value,
        FakeEmbeddingModel(),
    )

    assert rows == []


def test_bulk_upsert_semantic_bills_roundtrip_uses_embedding_model_name(session):
    """Semantic rows should upsert by `(bill_id, chunk_index, embedding_model_name)` using the `embedding_model_name` column."""
    session.add(
        Bill(
            id="B_SEM",
            title="Ley de transparencia",
            summary_congreso="Publica datos abiertos",
            observations="",
            status="En trámite",
            proponent=Proponents.CONGRESO.value,
            author_id=None,
            bill_approved=False,
            summary_oc="",
        )
    )
    session.add(
        BillStep(
            bill_id="B_SEM",
            step_id=1,
            step_type=TypeBillStep.PRESENTADO.value,
            vote_step=False,
            vote_event_id=None,
            step_date=date(2024, 1, 1),
            step_detail="Presentado",
        )
    )
    session.add(
        BillText(
            bill_id="B_SEM",
            step_id=1,
            file_id=1,
            version_id=1,
            text="Texto principal del proyecto",
        )
    )
    session.commit()

    inserted = bulk_upsert_semantic_bills(
        session,
        ["B_SEM"],
        embedding_model_name=EmbeddingModel.MULTILINGUAL_E5_BASE.value,
        embedding_model=FakeEmbeddingModel(),
    )
    repeated = bulk_upsert_semantic_bills(
        session,
        ["B_SEM"],
        embedding_model_name=EmbeddingModel.MULTILINGUAL_E5_BASE.value,
        embedding_model=FakeEmbeddingModel(),
    )
    rows = session.scalars(
        select(SemanticBill).where(SemanticBill.bill_id == "B_SEM")
    ).fetchall()

    assert inserted == repeated == 1
    assert len(rows) == 1
    assert rows[0].embedding_model_name == EmbeddingModel.MULTILINGUAL_E5_BASE

from datetime import date
from types import SimpleNamespace

import pytest
from backend import TypeBillStep
import backend.process.summarization as summarization


class _FakeQuery:
    """Minimal query stub that returns predefined step rows."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """Context-managed DB stub used to fake bill and step lookups."""

    def __init__(self, bill, steps):
        self._bill = bill
        self._steps = steps

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def get(self, model, bill_id):
        if self._bill and self._bill.id == bill_id:
            return self._bill
        return None

    def query(self, model):
        return _FakeQuery(self._steps)


@pytest.fixture
def bill_factory():
    """Build lightweight bill objects with defaults for tests."""

    def _make(
        *,
        bill_id="2021_1",
        presentation_date=date(2021, 1, 1),
        title="Ley de prueba",
        status="En comisión",
    ):
        return SimpleNamespace(
            id=bill_id,
            presentation_date=presentation_date,
            title=title,
            status=status,
        )

    return _make


@pytest.fixture
def step_factory():
    """Build lightweight legislative-step objects for test scenarios."""

    def _make(
        *,
        step_type=TypeBillStep.PRESENTADO,
        step_date=date(2021, 1, 1),
        step_detail="Presentado en mesa de partes",
    ):
        return SimpleNamespace(
            step_type=step_type,
            step_date=step_date,
            step_detail=step_detail,
        )

    return _make


@pytest.fixture
def patch_session(monkeypatch):
    """Patch session factory so summarization reads from fake DB data."""

    def _patch(*, bill, steps):
        def _fake_factory():
            return lambda: _FakeDB(bill=bill, steps=steps)

        monkeypatch.setattr(summarization, "_session_factory", _fake_factory)

    return _patch


@pytest.mark.parametrize(
    "days, expected",
    [
        (10, "10 días"),
        (30, "1 mes"),
        (360, "1 año"),
    ],
)
def test_format_elapsed_time_behavior(days, expected):
    assert summarization._format_elapsed_time(days) == expected


def test_rank_steps_prefers_higher_score_then_newer_date(step_factory):
    steps = [
        step_factory(
            step_type=TypeBillStep.VOTACION,
            step_date=date(2021, 5, 2),
            step_detail="Aprobado",
        ),
        step_factory(step_type=TypeBillStep.PUBLICADO, step_date=date(2021, 5, 3)),
        step_factory(
            step_type=TypeBillStep.VOTACION,
            step_date=date(2021, 5, 1),
            step_detail="Aprobado",
        ),
    ]

    ranked = summarization._rank_steps(steps)

    assert ranked[0]["type"] == TypeBillStep.PUBLICADO
    assert ranked[1]["type"] == TypeBillStep.VOTACION
    assert ranked[1]["step"].step_date == date(2021, 5, 2)
    assert ranked[2]["step"].step_date == date(2021, 5, 1)


def test_find_ranked_step_filters_by_needles(step_factory):
    steps = [
        step_factory(
            step_type=TypeBillStep.VOTACION,
            step_detail="Aprobado sin exoneración",
        ),
        step_factory(
            step_type=TypeBillStep.VOTACION,
            step_detail="Aprobado con exoneración de segunda votación",
        ),
    ]

    ranked = summarization._rank_steps(steps)

    out = summarization._find_ranked_step(
        ranked,
        {TypeBillStep.VOTACION},
        needles=("exoneración de segunda votación",),
    )

    assert out is not None
    assert "exoneración" in out.step_detail.lower()


def test_approved_vote_uses_step_detail(step_factory):
    approved = step_factory(
        step_type=TypeBillStep.VOTACION,
        step_detail="APROBADO 1ERA. VOTACIÓN",
    )
    not_approved = step_factory(
        step_type=TypeBillStep.VOTACION,
        step_detail="No alcanzó N° de votos",
    )

    assert summarization._is_approved_vote(approved)
    assert not summarization._is_approved_vote(not_approved)


def test_observed_autograph_requires_autograph_type_and_detail(step_factory):
    observed = step_factory(
        step_type=TypeBillStep.AUTOGRAFA,
        step_detail="Autógrafa observada por el Poder Ejecutivo",
    )
    regular_autograph = step_factory(
        step_type=TypeBillStep.AUTOGRAFA,
        step_detail="Autógrafa enviada al Poder Ejecutivo",
    )
    text_update = step_factory(
        step_type=TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION,
        step_detail="Autógrafa observada por el Poder Ejecutivo",
    )

    assert summarization._is_observed_autograph(observed)
    assert not summarization._is_observed_autograph(regular_autograph)
    assert not summarization._is_observed_autograph(text_update)


def test_summarize_bill_from_db_requires_bill_id():
    out = summarization.summarize_bill_from_db("")

    assert out["bill_id"] == ""
    assert out["context"] == ""
    assert "required" in out["summary"].lower()


def test_summarize_bill_from_db_bill_not_found(patch_session):
    patch_session(bill=None, steps=[])

    out = summarization.summarize_bill_from_db("2021_99999")

    assert out["bill_id"] == "2021_99999"
    assert out["context"] == ""
    assert "no se encontro" in out["summary"].lower()


def test_summarize_bill_from_db_no_steps(patch_session, bill_factory):
    patch_session(bill=bill_factory(bill_id="2021_10"), steps=[])

    out = summarization.summarize_bill_from_db("2021_10")

    assert out["bill_id"] == "2021_10"
    assert out["context"] == ""
    assert "no tiene pasos legislativos" in out["summary"].lower()


def test_summarize_bill_from_db_single_paragraph_when_few_steps(
    patch_session, bill_factory, step_factory
):
    bill = bill_factory(bill_id="2021_11", title="Reforma constitucional")
    steps = [
        step_factory(
            step_type=TypeBillStep.PRESENTADO,
            step_date=date(2021, 1, 10),
            step_detail="Presentado",
        ),
        step_factory(
            step_type=TypeBillStep.EN_COMISION,
            step_date=date(2021, 2, 1),
            step_detail="Pasa a comisión",
        ),
    ]
    patch_session(bill=bill, steps=steps)

    out = summarization.summarize_bill_from_db("2021_11")

    assert "Proyecto: 2021_11" in out["context"]
    assert "\n\n" not in out["summary"]
    assert "El Proyecto 2021_11" in out["summary"]


def test_summarize_bill_from_db_two_paragraphs_when_many_steps(
    patch_session, bill_factory, step_factory
):
    bill = bill_factory(
        bill_id="2021_12",
        title="Ley marco",
        status="En comisión",
    )
    steps = [
        step_factory(
            step_type=TypeBillStep.PRESENTADO,
            step_date=date(2021, 1, 1),
            step_detail="Presentado",
        ),
        step_factory(
            step_type=TypeBillStep.EN_COMISION,
            step_date=date(2021, 1, 10),
            step_detail="Pasa a comisión",
        ),
        step_factory(
            step_type=TypeBillStep.DEBATE_EN_EL_PLENO,
            step_date=date(2021, 1, 20),
            step_detail="Debate en pleno",
        ),
        step_factory(
            step_type=TypeBillStep.VOTACION,
            step_date=date(2021, 2, 1),
            step_detail="Aprobado",
        ),
        step_factory(
            step_type=TypeBillStep.AUTOGRAFA,
            step_date=date(2021, 2, 5),
            step_detail="Se actualiza texto",
        ),
        step_factory(
            step_type=TypeBillStep.EN_COMISION,
            step_date=date(2021, 2, 10),
            step_detail="Retorna a comisión",
        ),
    ]
    patch_session(bill=bill, steps=steps)

    out = summarization.summarize_bill_from_db("2021_12")

    assert "\n\n" in out["summary"]
    assert "Finalmente" in out["summary"]

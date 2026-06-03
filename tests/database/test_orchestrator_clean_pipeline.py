import json
from datetime import date, datetime
import pytest

from backend.core.enums import Proponents
from backend.database import models as db_models
from backend.database.crud import pipeline_bills as crud_bills
from backend.database.crud import pipeline_motions as crud_motions
from backend.database.orchestrator import OpenPeruOrchestrator
from backend.database.raw_models import (
    RawBill,
    RawBillDocument,
    RawBillPage,
    RawLey,
    RawMotion,
)
from backend import OcrModel
from backend.database.crud.pipeline_core import ProcessStats
from backend.process import schema
from backend import TypeBillStep, TypeMotionStep


@pytest.fixture
def orchestrator(engine):
    return OpenPeruOrchestrator(engine=engine)


def test_run_processing_loads_reference_definitions_before_memberships(monkeypatch):
    calls = []
    orch = OpenPeruOrchestrator.__new__(OpenPeruOrchestrator)

    def record(name):
        def _inner(*args, **kwargs):
            calls.append(name)
            return ProcessStats()

        return _inner

    monkeypatch.setattr(orch, "_process_organization_definitions", record("orgs"))
    monkeypatch.setattr(orch, "_process_bancada_definitions", record("bancadas"))
    monkeypatch.setattr(orch, "_process_congresistas", record("congresistas"))
    monkeypatch.setattr(orch, "_process_admin_memberships", record("admin_ms"))
    monkeypatch.setattr(orch, "_process_bancada_memberships", record("bancada_ms"))

    orch.run_processing(
        process_bills=False,
        process_motions=False,
        process_leyes=False,
        process_others=True,
        process_documents=False,
    )

    assert calls == ["orgs", "bancadas", "congresistas", "admin_ms", "bancada_ms"]


def test_process_bills_loads_bill_when_author_and_bancada_are_missing(orchestrator):
    with orchestrator.DBSession() as db:
        db.add(
            db_models.Organization(
                org_name="Cámara de Diputados",
                org_type="Cámara",
            )
        )
        db.add(
            RawBill(
                id="2026_1",
                timestamp=datetime(2026, 1, 10),
                general=json.dumps(
                    {
                        "fecPresentacion": "2026-01-10",
                        "titulo": "Proyecto de Ley X",
                        "sumilla": "Resumen",
                        "observaciones": "",
                        "desEstado": "Presentado",
                        "desProponente": "Ministerio Público",
                        "desGpar": "Bancada Ausente",
                    }
                ),
                congresistas=json.dumps(
                    [
                        {
                            "nombre": "Autora Ausente",
                            "pagWeb": "https://example.com/autora",
                            "tipoFirmanteId": 1,
                        }
                    ]
                ),
                steps=json.dumps([]),
                committees=json.dumps([]),
                last_update=True,
                processed=False,
                changed=True,
            )
        )
        db.commit()

    stats = orchestrator._process_bills(limit=None)

    with orchestrator.DBSession() as db:
        bill = db.get(db_models.Bill, "2026_1")
        raw = db.get(RawBill, ("2026_1", datetime(2026, 1, 10)))

        assert stats.processed == 1
        assert stats.errors == 0
        assert bill is not None
        assert bill.author_id is None
        assert raw.processed is True
        assert db.query(db_models.BillCongresistas).count() == 0


def test_process_bills_marks_raw_pages_processed_when_bill_text_extracted(
    orchestrator,
):
    """When include_documents=True and bill text is extracted, the raw pages
    that fed the extraction must be flipped to processed=True alongside the
    raw document."""
    bill_id = "2026_2"
    step_id = "5"
    file_id = "50"
    presentation_date = datetime(2026, 1, 10)

    with orchestrator.DBSession() as db:
        db.add(
            db_models.Organization(
                org_name="Cámara de Diputados",
                org_type="Cámara",
            )
        )
        db.add(
            RawBill(
                id=bill_id,
                timestamp=presentation_date,
                general=json.dumps(
                    {
                        "fecPresentacion": "2026-01-10",
                        "titulo": "Proyecto con texto",
                        "sumilla": "Resumen",
                        "observaciones": "",
                        "desEstado": "Presentado",
                        "desProponente": "Ministerio Público",
                        "desGpar": "Bancada Ausente",
                    }
                ),
                congresistas=json.dumps([]),
                steps=json.dumps([]),
                committees=json.dumps([]),
                last_update=True,
                processed=False,
                changed=True,
            )
        )
        db.add(
            RawBillDocument(
                timestamp=presentation_date,
                bill_id=bill_id,
                step_id=step_id,
                file_id=file_id,
                step_date=presentation_date,
                url="https://example.com/doc.pdf",
                last_update=True,
                processed=False,
            )
        )
        db.add_all(
            [
                RawBillPage(
                    timestamp=presentation_date,
                    bill_id=bill_id,
                    step_id=step_id,
                    file_id=file_id,
                    page_num=1,
                    text="FÓRMULA LEGAL\nArticulo 1. Inicio.",
                    ocr_model=OcrModel.CHANDRA.value,
                    last_update=True,
                    processed=False,
                ),
                RawBillPage(
                    timestamp=presentation_date,
                    bill_id=bill_id,
                    step_id=step_id,
                    file_id=file_id,
                    page_num=2,
                    text="Articulo 2. Final.",
                    ocr_model=OcrModel.CHANDRA.value,
                    last_update=True,
                    processed=False,
                ),
            ]
        )
        db.commit()

    stats = orchestrator._process_bills(limit=None)
    stats_bill_text = orchestrator._process_bill_text(limit=None)

    with orchestrator.DBSession() as db:
        raw_doc = db.get(RawBillDocument, (bill_id, step_id, file_id))
        pages = (
            db.query(RawBillPage)
            .filter(
                RawBillPage.bill_id == bill_id,
                RawBillPage.step_id == step_id,
                RawBillPage.file_id == file_id,
            )
            .order_by(RawBillPage.page_num)
            .all()
        )
        bill_text = db.get(db_models.BillText, (bill_id, int(step_id), int(file_id), 1))

        assert stats.processed == 1
        assert stats.errors == 0
        assert stats_bill_text.processed == 2
        assert stats_bill_text.errors == 0
        assert bill_text is not None
        assert raw_doc.processed is True
        assert len(pages) == 2
        assert all(page.processed is True for page in pages)


def test_process_motions_loads_motion_when_author_is_missing(orchestrator):
    with orchestrator.DBSession() as db:
        db.add(
            db_models.Organization(
                org_name="Cámara de Diputados",
                org_type="Cámara",
            )
        )
        db.add(
            RawMotion(
                id="2026_2",
                timestamp=datetime(2026, 1, 10),
                general=json.dumps(
                    {
                        "fecPresentacion": "2026-01-10",
                        "desTipoMocion": "Otras",
                        "sumilla": "Resumen",
                        "observacion": None,
                        "desEstadoMocion": "Presentado",
                    }
                ),
                congresistas=json.dumps(
                    [
                        {
                            "nombre": "Autor Ausente",
                            "pagWeb": "https://example.com/autor",
                            "tipoFirmanteId": 1,
                        }
                    ]
                ),
                steps=json.dumps([]),
                last_update=True,
                processed=False,
                changed=True,
            )
        )
        db.commit()

    stats = orchestrator._process_motions(include_documents=False, limit=None)

    with orchestrator.DBSession() as db:
        motion = db.get(db_models.Motion, "2026_2")
        raw = db.get(RawMotion, ("2026_2", datetime(2026, 1, 10)))

        assert stats.processed == 1
        assert stats.errors == 0
        assert motion is not None
        assert motion.author_id is None
        assert raw.processed is True
        assert db.query(db_models.MotionCongresistas).count() == 0


def test_process_leyes_leaves_parsed_missing_bill_pending(orchestrator):
    xml = """
    <root>
      <data>
        <ley>
          <numley>32558</numley>
          <tituloley>LEY DE PRUEBA</tituloley>
        </ley>
        <ignored></ignored>
        <recursos>
          <recursos>
            <tiporecursoleyitemmenu>6</tiporecursoleyitemmenu>
            <enlace>https://wb2server.congreso.gob.pe/spley-portal/#/expediente/2021/3623</enlace>
          </recursos>
        </recursos>
      </data>
    </root>
    """.strip()

    with orchestrator.DBSession() as db:
        raw = RawLey(
            timestamp=datetime(2026, 1, 10),
            data=xml,
            last_update=True,
            processed=False,
            changed=True,
        )
        db.add(raw)
        db.commit()
        raw_id = raw.id

    stats = orchestrator._process_leyes(limit=None)

    with orchestrator.DBSession() as db:
        raw = db.get(RawLey, raw_id)

        assert stats.processed == 0
        assert stats.skipped == 1
        assert stats.errors == 0
        assert raw.processed is False
        assert db.query(db_models.Ley).count() == 0


def test_process_leyes_marks_unparseable_rows_skipped(orchestrator):
    with orchestrator.DBSession() as db:
        raw = RawLey(
            timestamp=datetime(2026, 1, 10),
            data="<root><data></data></root>",
            last_update=True,
            processed=False,
            changed=True,
        )
        db.add(raw)
        db.commit()
        raw_id = raw.id

    stats = orchestrator._process_leyes(limit=None)

    with orchestrator.DBSession() as db:
        raw = db.get(RawLey, raw_id)

        assert stats.processed == 0
        assert stats.skipped == 1
        assert stats.errors == 0
        assert raw.processed is True


def test_bill_step_upsert_retains_planned_vote_event_reference(orchestrator):
    with orchestrator.DBSession() as db:
        db.add(
            db_models.Bill(
                id="2026_10",
                title="PL",
                summary_congreso="Resumen",
                observations="",
                status="Presentado",
                proponent="Ministerio Público",
                author_id=None,
                bill_approved=False,
                summary_oc="Resumen OC",
            )
        )
        db.flush()

        step = crud_bills.upsert_bill_step(
            db,
            schema.BillStep(
                bill_id="2026_10",
                step_id=10,
                step_type=TypeBillStep.VOTACION,
                vote_step=True,
                vote_event_id="B_2026_10_1",
                step_date=datetime(2026, 1, 10),
                step_detail="Votación",
                step_committees=[],
            ),
        )

        assert step.vote_event_id == "B_2026_10_1"


def test_motion_step_upsert_retains_planned_vote_event_reference(orchestrator):
    with orchestrator.DBSession() as db:
        db.add(
            db_models.Motion(
                id="2026_20",
                motion_type="Otras",
                summary_congreso="Resumen",
                observations="",
                status="Presentado",
                author_id=None,
                motion_approved=False,
                summary_oc="Resumen OC",
            )
        )
        db.flush()

        step = crud_motions.upsert_motion_step(
            db,
            schema.MotionStep(
                motion_id="2026_20",
                step_id=20,
                step_type=TypeMotionStep.VOTACION_O_DECISION,
                vote_step=True,
                vote_event_id="M_2026_20_1",
                step_date=datetime(2026, 1, 10),
                step_detail="Votación",
            ),
        )

        assert step.vote_event_id == "M_2026_20_1"


def _seed_bill_with_two_text_steps(db, bill_id="2026_30"):
    db.add(
        db_models.Bill(
            id=bill_id,
            title="PL",
            summary_congreso="Resumen",
            observations="",
            status="Presentado",
            proponent=Proponents.CONGRESO,
            bill_approved=False,
            summary_oc="Resumen OC",
        )
    )
    db.add(
        db_models.BillStep(
            bill_id=bill_id,
            step_id=1,
            vote_step=False,
            step_type=TypeBillStep.VOTACION,
            step_date=date(2026, 1, 10),
            step_detail="presented",
        )
    )
    db.add(
        db_models.BillStep(
            bill_id=bill_id,
            step_id=2,
            vote_step=False,
            step_type=TypeBillStep.VOTACION,
            step_date=date(2026, 1, 20),
            step_detail="amended",
        )
    )
    db.add(
        db_models.BillText(
            bill_id=bill_id,
            step_id=1,
            file_id=1,
            version_id=1,
            text="Artículo 1.- Texto original.\n",
        )
    )
    db.add(
        db_models.BillText(
            bill_id=bill_id,
            step_id=2,
            file_id=1,
            version_id=1,
            text="Artículo 1.- Texto modificado.\n",
        )
    )
    db.commit()


def test_process_bill_differences_runs_over_bill_texts(orchestrator):
    with orchestrator.DBSession() as db:
        _seed_bill_with_two_text_steps(db, bill_id="2026_30")

    stats = orchestrator._process_bill_differences(limit=None)

    assert stats.processed == 1
    assert stats.errors == 0

    with orchestrator.DBSession() as db:
        rows = (
            db.query(db_models.BillDifference)
            .filter_by(bill_id="2026_30")
            .order_by(db_models.BillDifference.step_id)
            .all()
        )
        assert [r.step_id for r in rows] == [1, 2]
        assert rows[0].difference_type == "first_version"
        assert rows[0].prev_step_id is None
        assert rows[1].difference_type == "modified"
        assert rows[1].prev_step_id == 1
        assert rows[1].difference_content is not None


def test_process_bill_differences_isolates_failures_per_bill(orchestrator, monkeypatch):
    # Regression: a failure on one bill must not roll back diffs already
    # written for earlier bills in the same batch. We seed two bills, then
    # force ``_compute_bill_differences`` to raise on the second one; the
    # first bill's BillDifference rows must still be persisted.
    with orchestrator.DBSession() as db:
        _seed_bill_with_two_text_steps(db, bill_id="2026_40")
        _seed_bill_with_two_text_steps(db, bill_id="2026_41")

    real = orchestrator._compute_bill_differences

    def raise_on_41(db, bill_id):
        if bill_id == "2026_41":
            raise RuntimeError("boom")
        return real(db, bill_id)

    monkeypatch.setattr(orchestrator, "_compute_bill_differences", raise_on_41)

    stats = orchestrator._process_bill_differences(limit=None)

    assert stats.processed == 1
    assert stats.errors == 1

    with orchestrator.DBSession() as db:
        persisted = {row.bill_id for row in db.query(db_models.BillDifference).all()}
        assert persisted == {"2026_40"}


def test_process_bill_differences_skips_bills_without_text(orchestrator):
    # A bill with no bill_texts row should not appear in the driver query at
    # all — _process_bill_differences is driven off bill_texts.
    with orchestrator.DBSession() as db:
        db.add(
            db_models.Bill(
                id="2026_31",
                title="PL",
                summary_congreso="Resumen",
                observations="",
                status="Presentado",
                proponent=Proponents.CONGRESO,
                bill_approved=False,
                summary_oc="Resumen OC",
            )
        )
        db.commit()

    stats = orchestrator._process_bill_differences(limit=None)

    assert stats.processed == 0
    with orchestrator.DBSession() as db:
        assert db.query(db_models.BillDifference).count() == 0

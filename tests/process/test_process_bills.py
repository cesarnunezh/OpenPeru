import json
from types import SimpleNamespace

import pytest

import backend.process.bills as mod
from backend import OcrModel, TypeRoleBill, TypeBillStep


def _raw_bill(
    *,
    id="PL_123",
    general=None,
    congresistas=None,
    steps=None,
    committees=None,
):
    if general is None:
        general = {
            "desPerParAbrev": "2021-2026",
            "desLegis": "Primera Legislatura Ordinaria 2021",
            "fecPresentacion": "2026-01-10",
            "titulo": "Proyecto de Ley X",
            "sumilla": "Resumen",
            "observaciones": "Obs",
            "desEstado": "En Comisión",
            "desProponente": "Ministerio Público",
            "desGpar": "Bancada Test",
        }
    if congresistas is None:
        congresistas = []
    if steps is None:
        steps = []
    if committees is None:
        committees = []

    return SimpleNamespace(
        id=id,
        general=json.dumps(general),
        congresistas=json.dumps(congresistas),
        steps=json.dumps(steps),
        committees=json.dumps(committees),
    )


def _raw_page(
    *,
    bill_id="PL_123",
    step_id="1",
    file_id="12",
    page_num=1,
    text="",
    ocr_model=OcrModel.CHANDRA.value,
):
    return SimpleNamespace(
        bill_id=bill_id,
        step_id=step_id,
        file_id=file_id,
        page_num=page_num,
        text=text,
        ocr_model=ocr_model,
    )


def test_process_bill_with_firmantes_sets_author_and_cong_list():
    firmantes = [
        {
            "nombre": "Juan Perez",
            "pagWeb": "https://example.com/juan",
            "tipoFirmanteId": 1,
        },
        {
            "nombre": "Maria Lopez",
            "pagWeb": "https://example.com/maria",
            "tipoFirmanteId": 2,
        },
    ]
    rb = _raw_bill(id="PL_999", congresistas=firmantes)

    bill, congs, steps = mod.process_bill(rb)

    assert bill.id == "PL_999"
    assert bill.title == "Proyecto de Ley x"
    assert bill.summary_congreso == "Resumen"
    assert bill.status == "En Comisión"
    assert bill.proponent == "Ministerio Público"
    assert bill.bancada_name == "Bancada Test"
    assert bill.bill_approved is False
    assert steps == []

    assert bill.author_name == "Juan Perez"
    assert bill.author_web == "https://example.com/juan"

    assert len(congs) == 2
    assert congs[0].bill_id == "PL_999"
    assert congs[0].nombre == "Juan Perez"
    assert congs[0].role_type == TypeRoleBill.AUTHOR
    assert congs[1].nombre == "Maria Lopez"
    assert congs[1].role_type == TypeRoleBill.COAUTHOR


def test_process_bill_without_firmantes_sets_author_none_and_empty_cong_list():
    rb = _raw_bill(congresistas=[])

    bill, congs, steps = mod.process_bill(rb)

    assert bill.author_name is None
    assert bill.author_web is None
    assert congs == []
    assert steps == []


def test_process_bill_approved_uses_steps_then_status_fallback():
    published_step = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2026-01-11",
            "desEstado": "Publicada en el Diario Oficial El Peruano",
            "detalle": "",
        }
    ]
    rb = _raw_bill(steps=published_step)
    bill, _, _ = mod.process_bill(rb)
    assert bill.bill_approved is True

    general = {
        "fecPresentacion": "2026-01-10",
        "titulo": "PL",
        "sumilla": "S",
        "observaciones": "None",
        "desEstado": "Publicada en el Diario Oficial El Peruano",
        "desProponente": "Ministerio Público",
        "desGpar": "Bancada Test",
    }
    rb = _raw_bill(general=general, steps=[])
    bill, _, _ = mod.process_bill(rb)
    assert bill.bill_approved is True


def test_process_bill_steps_empty_when_no_steps():
    rb = _raw_bill(steps=[])

    out = mod.process_bill_steps(rb)

    assert out == []


def test_process_bill_steps_vote_detection_assigns_vote_event_id():
    steps = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2026-01-01",
            "desEstado": "En Comisión",
            "detalle": "Pasa a comisión",
        },
        {
            "seguimientoPleyId": 2,
            "fecha": "2026-01-02",
            "desEstado": "APROBADO 1ERA. VOTACIÓN",
            "detalle": "Se realiza VOTACIÓN en el pleno",
        },
    ]
    rb = _raw_bill(id="2021_777", steps=steps)

    out = mod.process_bill_steps(rb)

    assert len(out) == 2
    assert out[0].step_id == 1
    assert out[0].step_type == TypeBillStep.EN_COMISION
    assert out[0].vote_step is False
    assert out[0].vote_event_id is None
    assert out[0].step_committees == []

    assert out[1].step_id == 2
    assert out[1].step_type == TypeBillStep.VOTACION
    assert out[1].vote_step is True
    assert out[1].vote_event_id == "B_2021_777_1"


def test_process_bill_steps_parses_semicolon_committee_text():
    steps = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2026-01-01",
            "desEstado": "En Comisión",
            "detalle": "Pasa a comisión",
            "desComisiones": "Comisión de Economía; Comisión de Justicia ; ",
        },
    ]
    rb = _raw_bill(id="2021_777", steps=steps)

    out = mod.process_bill_steps(rb)

    assert out[0].step_committees == [
        "Comisión de Economía",
        "Comisión de Justicia",
    ]


def test_process_bill_organizations_uses_step_committees_only_and_dates():
    steps = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2026-01-01",
            "desEstado": "Presentado",
            "detalle": "Presentado",
        },
        {
            "seguimientoPleyId": 2,
            "fecha": "2026-01-02",
            "desEstado": "En Comisión",
            "detalle": "Pasa a comisión",
            "desComisiones": json.dumps(["Comisión de Economía"]),
        },
        {
            "seguimientoPleyId": 3,
            "fecha": "2026-01-05",
            "desEstado": "DICTAMEN",
            "detalle": "Dictamen",
            "desComisiones": json.dumps(["Comisión de Economía"]),
        },
    ]
    rb = _raw_bill(
        id="PL_111",
        steps=steps,
        committees=[{"nombre": "Comisión Ignorada"}],
    )

    bill_steps = mod.process_bill_steps(rb)
    orgs = mod.process_bill_organizations(rb, bill_steps)

    assert [org.org_name for org in orgs] == [
        "Comisión de Economía",
        "Cámara de Diputados",
    ]
    committee = orgs[0]
    assert committee.org_type == "Comisión"
    assert committee.presentation_date.isoformat() == "2026-01-02"
    assert committee.decision_date.isoformat() == "2026-01-05"
    chamber = orgs[1]
    assert chamber.org_type == "Cámara"
    assert chamber.presentation_date.isoformat() == "2026-01-01"
    assert type(chamber.presentation_date).__name__ == "date"


def test_process_bill_organizations_no_steps_uses_raw_presentation_date():
    rb = _raw_bill(id="PL_222", steps=[])

    orgs = mod.process_bill_organizations(rb, [])

    assert len(orgs) == 1
    assert orgs[0].org_name == "Cámara de Diputados"
    assert orgs[0].presentation_date.isoformat() == "2026-01-10"


def test_process_bill_text_extracts_body_from_ordered_pages():
    pages = [
        _raw_page(page_num=2, text="\nArticulo 2. Final"),
        _raw_page(
            page_num=1,
            text="Intro\nFÓRMULA LEGAL\nArticulo 1. Contenido",
        ),
    ]

    bill_text = mod.process_bill_text(pages, 8)

    assert bill_text.bill_id == "PL_123"
    assert bill_text.step_id == 1
    assert bill_text.file_id == 12
    assert bill_text.version_id == 8
    assert bill_text.text.startswith("FÓRMULA LEGAL")
    assert "Articulo 2. Final" in bill_text.text


def test_process_bill_text_raises_when_body_missing():
    pages = [_raw_page(text="Texto sin encabezado")]

    with pytest.raises(ValueError):
        mod.process_bill_text(pages, 1)


def test_process_bill_text_raises_on_empty_pages():
    with pytest.raises(ValueError, match="No raw pages"):
        mod.process_bill_text([], 1)


def test_process_bill_text_raises_on_mixed_ocr_models():
    pages = [
        _raw_page(page_num=1, text="FÓRMULA LEGAL\nArticulo 1."),
        _raw_page(page_num=2, text="Articulo 2.", ocr_model=OcrModel.TESSERACT.value),
    ]

    with pytest.raises(ValueError, match="mix OCR models"):
        mod.process_bill_text(pages, 1)

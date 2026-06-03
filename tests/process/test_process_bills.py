import json
from types import SimpleNamespace
import backend.process.bills as mod


def _raw_bill(
    *,
    id="PL_123",
    general=None,
    congresistas=None,
    steps=None,
    committees=None,
):
    """
    Minimal stand-in for RawBill. Only fields used by the processing functions.
    """
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


def _raw_bill_document(
    *,
    bill_id="PL_123",
    seguimiento_id=1,
    archivo_id=12,
    url="https://example.com/doc.pdf",
    text="",
):
    """
    Minimal stand-in for RawBillDocument.
    """
    return SimpleNamespace(
        bill_id=bill_id,
        seguimiento_id=seguimiento_id,
        archivo_id=archivo_id,
        url=url,
        text=text,
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

    bill, congs = mod.process_bill(rb)

    assert bill.id == "PL_999"
    assert bill.leg_period == "2021-2026"
    assert bill.legislature == "2021-II"
    assert bill.title == "Proyecto de Ley X"
    assert bill.status == "En Comisión"
    assert bill.proponent == "Ministerio Público"
    assert bill.complete_text is None

    # author fields come from first firmante
    assert bill.author_name == "Juan Perez"
    assert bill.author_web == "https://example.com/juan"

    # congresistas list created for each firmante
    assert len(congs) == 2
    assert congs[0].bill_id == "PL_999"
    assert congs[0].nombre == "Juan Perez"
    assert congs[0].leg_period == "2021-2026"
    assert congs[0].role_type == "author"

    assert congs[1].nombre == "Maria Lopez"
    assert congs[1].role_type == "coauthor"


def test_process_bill_without_firmantes_sets_author_none_and_empty_cong_list():
    rb = _raw_bill(congresistas=[])

    bill, congs = mod.process_bill(rb)

    assert bill.author_name is None
    assert bill.author_web is None
    assert congs == []


def test_process_bill_sets_bill_approved_true_only_for_published_state():
    general = {
        "desPerParAbrev": "2021-2026",
        "desLegis": "Primera Legislatura Ordinaria 2021",
        "fecPresentacion": "2026-01-10",
        "titulo": "PL",
        "sumilla": "S",
        "observaciones": "None",
        "desEstado": "Publicada en el Diario Oficial El Peruano",
        "desProponente": "Ministerio Público",
    }
    rb = _raw_bill(general=general)

    bill, _ = mod.process_bill(rb)

    assert bill.bill_approved is True


def test_process_bill_steps_none_when_no_steps():
    rb = _raw_bill(steps=[])

    out = mod.process_bill_steps(rb)

    assert out is None


def test_process_bill_steps_vote_detection_and_vote_id_increment():
    steps = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2026-01-01",
            "detalle": "Pasa a comisión",
            "archivos": [{"proyectoArchivoId": 1}],
        },
        {
            "seguimientoPleyId": 2,
            "fecha": "2026-01-02",
            "detalle": "Se realiza VOTACIÓN en el pleno",
            "archivos": [{"proyectoArchivoId": 2}, {"proyectoArchivoId": 3}],
        },
        {
            "seguimientoPleyId": 3,
            "fecha": "2026-01-03",
            "detalle": "Otra votacion en comisión (segunda)",
            "archivos": [],
        },
    ]
    rb = _raw_bill(id="PL_777", steps=steps)

    out = mod.process_bill_steps(rb)

    assert out is not None
    assert len(out) == 3

    # Step 1: not a vote step
    assert out[0].id == 1
    assert out[0].bill_id == "PL_777"
    assert out[0].vote_step is False
    assert out[0].vote_id is None
    assert out[0].step_files == [1]

    # Step 2: vote step -> vote_id PL_777_1
    assert out[1].vote_step is True
    assert out[1].vote_id == "PL_777_1"
    assert out[1].step_files == [2, 3]

    # Step 3: second vote -> vote_id PL_777_2
    assert out[2].vote_step is True
    assert out[2].vote_id == "PL_777_2"
    assert out[2].step_files == []


def test_process_bill_steps_carries_des_estado_as_step_status():
    steps = [
        {
            "seguimientoPleyId": 7,
            "fecha": "2026-02-01",
            "desEstado": "En Comisión",
            "detalle": "Texto narrativo libre que no clasifica",
            "archivos": [],
        }
    ]
    rb = _raw_bill(id="PL_888", steps=steps)

    out = mod.process_bill_steps(rb)

    assert out is not None
    assert len(out) == 1
    assert out[0].step_status == "En Comisión"


def test_process_bill_document_vote_doc_true_for_si_no_pattern_si_first():
    # Matches: SI ++ ... NO --
    text = "Resultado: SI +++++  80 votos ... NO ---- 20 votos"
    rbd = _raw_bill_document(text=text)

    doc = mod.process_bill_document(rbd)

    assert doc.bill_id == "PL_123"
    assert doc.step_id == 1
    assert doc.archivo_id == 12
    assert doc.vote_doc is True


def test_process_bill_document_vote_doc_true_for_si_no_pattern_no_first():
    # Matches: NO -- ... SI ++
    text = "Conteo: NO ----- 50 ... luego SI ++++++ 60"
    rbd = _raw_bill_document(text=text)

    doc = mod.process_bill_document(rbd)

    assert doc.vote_doc is True


def test_process_bill_document_vote_doc_false_when_no_match():
    text = "Este documento no contiene un cuadro de votación."
    rbd = _raw_bill_document(text=text)

    doc = mod.process_bill_document(rbd)

    assert doc.vote_doc is False


def test_get_committees_none_when_empty():
    rb = _raw_bill(committees=[])

    out = mod.get_committees(rb)

    assert out is None


def test_get_committees_returns_list_with_names():
    committees = [
        {"nombre": "Comisión de Economía"},
        {"nombre": "Comisión de Justicia"},
    ]
    rb = _raw_bill(id="PL_111", committees=committees)

    out = mod.get_committees(rb)

    assert out is not None
    assert len(out) == 2
    assert out[0].bill_id == "PL_111"
    assert out[0].committee_name == "Comisión de Economía"
    assert out[1].committee_name == "Comisión de Justicia"

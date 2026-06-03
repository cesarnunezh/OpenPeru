# tests/test_motions.py

import json
from types import SimpleNamespace

from datetime import datetime
import backend.process.motions as mod


def _raw_motion(
    *,
    id="MO_123",
    general=None,
    congresistas=None,
    steps=None,
):
    """
    Minimal stand-in for RawMotion. Only fields used by these functions.
    """
    if general is None:
        general = {
            "desPerParAbrev": "2021-2026",
            "desLegis": "Primera Legislatura Ordinaria 2025",
            "fecPresentacion": "2026-01-10",
            "desTipoMocion": "Otras",
            "sumilla": "Resumen moción",
            "observacion": "Obs",
            "desEstadoMocion": "En trámite",
        }
    if congresistas is None:
        congresistas = []
    if steps is None:
        steps = []

    return SimpleNamespace(
        id=id,
        general=json.dumps(general),
        congresistas=json.dumps(congresistas),
        steps=json.dumps(steps),
    )


def _raw_motion_document(
    *,
    motion_id="MO_123",
    seguimiento_id=123,
    archivo_id=12,
    url="https://example.com/doc.pdf",
    text="",
):
    """
    Minimal stand-in for RawMotionDocument.
    """
    return SimpleNamespace(
        motion_id=motion_id,
        seguimiento_id=seguimiento_id,
        archivo_id=archivo_id,
        url=url,
        text=text,
    )


def test_process_motion_with_firmantes_sets_author_and_cong_list():
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
    rm = _raw_motion(id="MO_999", congresistas=firmantes)

    motion, congs = mod.process_motion(rm)

    assert motion.id == "MO_999"
    assert motion.leg_period == "2021-2026"
    assert motion.legislature == "2025-II"
    assert motion.presentation_date == datetime.fromisoformat("2026-01-10")
    assert motion.motion_type == "Otras"
    assert motion.summary == "Resumen moción"
    assert motion.observations == "Obs"
    assert motion.complete_text is None
    assert motion.status == "En trámite"

    # author fields from first firmante
    assert motion.author_name == "Juan Perez"
    assert motion.author_web == "https://example.com/juan"

    # congresistas list created
    assert len(congs) == 2
    assert congs[0].motion_id == "MO_999"
    assert congs[0].nombre == "Juan Perez"
    assert congs[0].leg_period == "2021-2026"
    assert congs[0].role_type == "author"

    assert congs[1].nombre == "Maria Lopez"
    assert congs[1].role_type == "coauthor"


def test_process_motion_sets_motion_approved_true_only_for_published_state():
    general = {
        "desPerParAbrev": "2021-2026",
        "desLegis": "Primera Legislatura Ordinaria 2025",
        "fecPresentacion": "2026-01-10",
        "desTipoMocion": "Saludo",
        "sumilla": "S",
        "observacion": None,
        "desEstadoMocion": "Publicado Diario Oficial  El Peruano",
    }
    rm = _raw_motion(
        general=general,
        congresistas=[
            {"nombre": "X", "pagWeb": "https://example.com/x", "tipoFirmanteId": 1}
        ],
    )

    motion, _ = mod.process_motion(rm)

    assert motion.motion_approved is True


def test_process_motion_steps_none_when_no_steps():
    rm = _raw_motion(steps=[])

    out = mod.process_motion_steps(rm)

    assert out is None


def test_process_motion_steps_vote_detection_and_vote_id_increment():
    steps = [
        {
            "seguimientoId": 123,
            "fecSeguimiento": "2026-01-01",
            "detalle": "Pasa a comisión",
            "adjuntos": [{"seguimientoAdjuntoId": 1}],
        },
        {
            "seguimientoId": 234,
            "fecSeguimiento": "2026-01-02",
            "detalle": "Se realiza VOTACIÓN en el pleno",
            "adjuntos": [{"seguimientoAdjuntoId": 2}, {"seguimientoAdjuntoId": 3}],
        },
        {
            "seguimientoId": 345,
            "fecSeguimiento": "2026-01-03",
            "detalle": "Otra votacion en comisión (segunda)",
            "adjuntos": [],
        },
    ]
    rm = _raw_motion(id="MO_777", steps=steps)

    out = mod.process_motion_steps(rm)

    assert out is not None
    assert len(out) == 3

    # Step 1
    assert out[0].id == 123
    assert out[0].motion_id == "MO_777"
    assert out[0].vote_step is False
    assert out[0].vote_id is None
    assert out[0].step_files == [1]

    # Step 2
    assert out[1].vote_step is True
    assert out[1].vote_id == "MO_777_1"
    assert out[1].step_files == [2, 3]

    # Step 3
    assert out[2].vote_step is True
    assert out[2].vote_id == "MO_777_2"
    assert out[2].step_files == []


def test_process_motion_steps_carries_des_estado_mocion_as_step_status():
    steps = [
        {
            "seguimientoId": 456,
            "fecSeguimiento": "2026-02-10",
            "desEstadoMocion": "En Comisión",
            "detalle": "Texto libre sin clasificación directa",
            "adjuntos": [],
        }
    ]
    rm = _raw_motion(id="MO_888", steps=steps)

    out = mod.process_motion_steps(rm)

    assert out is not None
    assert len(out) == 1
    assert out[0].step_status == "En Comisión"


def test_process_motion_document_vote_doc_true_for_si_no_pattern_si_first():
    text = "Resultado: SI +++++  80 ... NO ---- 20"
    rmd = _raw_motion_document(text=text)

    doc = mod.process_motion_document(rmd)

    assert doc.motion_id == "MO_123"
    assert doc.step_id == 123
    assert doc.archivo_id == 12
    assert doc.vote_doc is True


def test_process_motion_document_vote_doc_true_for_si_no_pattern_no_first():
    text = "Conteo: NO ----- 50 ... luego SI ++++++ 60"
    rmd = _raw_motion_document(text=text)

    doc = mod.process_motion_document(rmd)

    assert doc.vote_doc is True


def test_process_motion_document_vote_doc_false_when_no_match():
    text = "Documento sin cuadro de votación."
    rmd = _raw_motion_document(text=text)

    doc = mod.process_motion_document(rmd)

    assert doc.vote_doc is False

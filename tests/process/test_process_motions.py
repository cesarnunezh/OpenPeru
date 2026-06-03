import json
from types import SimpleNamespace

import pytest

import backend.process.motions as mod
from backend import TypeMotionStep, TypeRoleBill


def _raw_motion(
    *,
    id="MO_123",
    general=None,
    congresistas=None,
    steps=None,
):
    if general is None:
        general = {
            "desPerParAbrev": "2021-2026",
            "desLegis": "Primera Legislatura Ordinaria 2025",
            "fecPresentacion": "2026-01-10",
            "desTipoMocion": "Otras",
            "sumilla": "Resumen moción",
            "observacion": "Obs",
            "desEstadoMocion": "En debate",
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


def _raw_page(
    *,
    motion_id="MO_123",
    step_id="1",
    file_id="12",
    page_num=1,
    text="",
):
    return SimpleNamespace(
        motion_id=motion_id,
        step_id=step_id,
        file_id=file_id,
        page_num=page_num,
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

    motion, congs, steps = mod.process_motion(rm)

    assert motion.id == "MO_999"
    assert motion.motion_type == "Otras"
    assert motion.summary_congreso == "Resumen moción"
    assert motion.observations == "Obs"
    assert motion.status == "En Debate"
    assert motion.summary_opencongress.startswith("MO_999: PENDING SUMMARY")
    assert steps == []

    assert motion.author_name == "Juan Perez"
    assert motion.author_web == "https://example.com/juan"

    assert len(congs) == 2
    assert congs[0].motion_id == "MO_999"
    assert congs[0].nombre == "Juan Perez"
    assert congs[0].role_type == TypeRoleBill.AUTHOR
    assert congs[1].nombre == "Maria Lopez"
    assert congs[1].role_type == TypeRoleBill.COAUTHOR


def test_process_motion_without_firmantes_sets_author_none_and_empty_cong_list():
    rm = _raw_motion(congresistas=[])

    motion, congs, steps = mod.process_motion(rm)

    assert motion.author_name is None
    assert motion.author_web is None
    assert congs == []
    assert steps == []


def test_process_motion_approved_uses_steps_then_status_fallback():
    published_step = [
        {
            "seguimientoId": 1,
            "fecSeguimiento": "2026-01-11",
            "desEstadoMocion": "Publicado Diario Oficial El Peruano",
            "detalle": "",
        }
    ]
    rm = _raw_motion(steps=published_step)
    motion, _, _ = mod.process_motion(rm)
    assert motion.motion_approved is True

    general = {
        "fecPresentacion": "2026-01-10",
        "desTipoMocion": "Saludo",
        "sumilla": "S",
        "observacion": None,
        "desEstadoMocion": "Publicado Diario Oficial  El Peruano",
    }
    rm = _raw_motion(general=general, steps=[])
    motion, _, _ = mod.process_motion(rm)
    assert motion.motion_approved is True


def test_process_motion_steps_empty_when_no_steps():
    rm = _raw_motion(steps=[])

    out = mod.process_motion_steps(rm)

    assert out == []


def test_process_motion_steps_vote_detection_and_vote_id_increment():
    steps = [
        {
            "seguimientoId": 123,
            "fecSeguimiento": "2026-01-01",
            "desEstadoMocion": "En Comisión",
            "detalle": "Pasa a comisión",
        },
        {
            "seguimientoId": 234,
            "fecSeguimiento": "2026-01-02",
            "desEstadoMocion": "Aprobada la Moción",
            "detalle": "Se realiza VOTACIÓN en el pleno",
        },
        {
            "seguimientoId": 345,
            "fecSeguimiento": "2026-01-03",
            "desEstadoMocion": "Rechazada",
            "detalle": "Otra votacion en comisión (segunda)",
        },
    ]
    rm = _raw_motion(id="2021_777", steps=steps)

    out = mod.process_motion_steps(rm)

    assert len(out) == 3
    assert out[0].step_id == 123
    assert out[0].motion_id == "2021_777"
    assert out[0].step_type == TypeMotionStep.ETAPA_EN_COMISION
    assert out[0].vote_step is False
    assert out[0].vote_event_id is None

    assert out[1].step_id == 234
    assert out[1].step_type == TypeMotionStep.VOTACION_O_DECISION
    assert out[1].vote_step is True
    assert out[1].vote_event_id == "M_2021_777_1"

    assert out[2].step_id == 345
    assert out[2].step_type == TypeMotionStep.VOTACION_O_DECISION
    assert out[2].vote_step is True
    assert out[2].vote_event_id == "M_2021_777_2"


def test_process_motion_organizations_chamber_only_and_dates():
    steps = [
        {
            "seguimientoId": 1,
            "fecSeguimiento": "2026-01-01",
            "desEstadoMocion": "Presentado",
            "detalle": "",
        },
        {
            "seguimientoId": 2,
            "fecSeguimiento": "2026-01-05",
            "desEstadoMocion": "Aprobada la Moción",
            "detalle": "Se realiza VOTACIÓN en el pleno",
        },
        {
            "seguimientoId": 3,
            "fecSeguimiento": "2026-01-07",
            "desEstadoMocion": "Publicado Diario Oficial El Peruano",
            "detalle": "",
        },
    ]
    rm = _raw_motion(id="MO_111", steps=steps)

    motion_steps = mod.process_motion_steps(rm)
    orgs = mod.process_motion_organizations(rm, motion_steps)

    assert len(orgs) == 1
    assert orgs[0].org_name == "Cámara de Diputados"
    assert orgs[0].org_type == "Cámara"
    assert orgs[0].presentation_date.isoformat() == "2026-01-01"
    assert orgs[0].decision_date.isoformat() == "2026-01-07"


def test_process_motion_organizations_no_steps_uses_raw_presentation_date():
    rm = _raw_motion(id="MO_222", steps=[])

    orgs = mod.process_motion_organizations(rm, [])

    assert len(orgs) == 1
    assert orgs[0].org_name == "Cámara de Diputados"
    assert orgs[0].presentation_date.isoformat() == "2026-01-10"


def test_process_motion_text_joins_ordered_pages():
    pages = [
        _raw_page(page_num=2, text="Segunda página"),
        _raw_page(page_num=1, text="Primera página"),
    ]

    motion_text = mod.process_motion_text(pages)

    assert motion_text.motion_id == "MO_123"
    assert motion_text.step_id == 1
    assert motion_text.file_id == 12
    assert motion_text.version_id == 1
    assert motion_text.text == "Primera página\nSegunda página"


def test_process_motion_text_raises_when_empty():
    pages = [_raw_page(text="")]

    with pytest.raises(ValueError):
        mod.process_motion_text(pages)

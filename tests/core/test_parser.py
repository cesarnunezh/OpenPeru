from __future__ import annotations

import json
from pathlib import Path

from backend.core.enums import RoleOrganization, TypeBillStep, TypeMotionStep
from backend.core.parsers import (
    classify_des_estado,
    classify_motion_des_estado,
    normalize_membership_role,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> list[dict]:
    with path.open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise TypeError(f"Expected list payload in {path}")
    return payload


def test_classify_bill_status_exact():
    label = classify_des_estado("APROBADO", "ASISTENCIA Y VOTACIÓN")

    assert label is TypeBillStep.VOTACION


def test_classify_bill_status_normalizes_variant():
    label = classify_des_estado(" Aprobado Com.Permanente ", "VOTACION")

    assert label is TypeBillStep.VOTACION


def test_classify_bill_status_uses_detail_when_placeholder():
    label = classify_des_estado(
        "------",
        "TEXTO SUSTITUTORIO DE LA COMISIÓN DE SALUD",
    )

    assert label is TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION


def test_classify_bill_status_uses_detail_to_refine_dictamen():
    label = classify_des_estado(
        "DICTAMEN",
        "POR UNANIMIDAD - FÓRMULA SUSTITUTORIA - LEY QUE CREA EL COLEGIO PROFESIONAL",
    )

    assert label is TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION


def test_classify_bill_detail_vote_overrides_debate_status():
    label = classify_des_estado(
        "EN DEBATE - PLENO",
        "ASISTENCIA Y VOTACIÓN - RECONSIDERACIÓN (APROBADA)",
    )

    assert label is TypeBillStep.VOTACION


def test_classify_bill_title_reconsideracion_does_not_force_step_type():
    label = classify_des_estado(
        "PRESENTADO",
        "LEY QUE REDUCE LOS PLAZOS PARA LA PRESENTACIÓN DE RECURSOS IMPUGNATIVOS DE RECONSIDERACIÓN",
    )

    assert label is TypeBillStep.PRESENTADO


def test_classify_motion_status_maps_foundation():
    label = classify_motion_des_estado(
        "Fundamentada la Moción",
        "LA CONGRESISTA FUNDAMENTA LA MOCIÓN DE ORDEN DEL DÍA.",
    )

    assert label is TypeMotionStep.FUNDAMENTACION


def test_classify_motion_status_uses_detail_for_blank_status():
    label = classify_motion_des_estado(
        "",
        "La Presidenta anunció que se había presentado la moción de censura.",
    )

    assert label is TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA


def test_classify_motion_status_maps_withdrawn_case():
    label = classify_motion_des_estado(
        "Se deje sin efecto",
        "Solicita que ya no sea debatida en la sesión del pleno.",
    )

    assert label is TypeMotionStep.RETIRADO


def test_classify_motion_blank_title_as_presented():
    label = classify_motion_des_estado(
        "",
        "Censurar a la señora María del Carmen Alva Prieto por su conducta antidemocrática.",
    )

    assert label is TypeMotionStep.PRESENTADO


def test_classify_motion_blank_document_as_official_communication():
    label = classify_motion_des_estado(
        "",
        "ACTA DE ACUERDO DE LA COMISIÓN DE SALUD",
    )

    assert label is TypeMotionStep.COMUNICACION_OFICIAL


def test_classify_motion_detail_title_overrides_routing_status():
    label = classify_motion_des_estado(
        "PARA SER VISTA POR EL CONSEJO DIRECTIVO",
        "Expresar su más cálido saludo y felicitación a los ciudadanos del distrito",
    )

    assert label is TypeMotionStep.PRESENTADO


def test_classify_motion_detail_document_overrides_routing_status():
    label = classify_motion_des_estado(
        "TRAMITADA CON ACUERDO DE CD",
        "OFICIO 0021-2021-2022-ADP-M-CR. LA PRIMERA VICEPRESIDENTA COMUNICA A LA DIRECTORA",
    )

    assert label is TypeMotionStep.COMUNICACION_OFICIAL


def test_classify_motion_vote_detail_keeps_vote_family():
    label = classify_motion_des_estado(
        "Aprobada",
        "APROBADO UN TEXTO SUSTITUTORIO",
    )

    assert label is TypeMotionStep.VOTACION_O_DECISION


def test_normalize_membership_role_maps_presidency_encargado_variant():
    role = normalize_membership_role(
        "primer vicepresidente encargado de la presidencia del congreso de la república"
    )

    assert role is RoleOrganization.VICEPRESIDENTE

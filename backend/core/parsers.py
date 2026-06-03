from __future__ import annotations

import re
from datetime import date, datetime
import unicodedata
from backend.core.constants import (
    BILL_ROLE_MAPS,
    LEG_PERIOD_ALIASES,
    LEGISLATURE_ALIASES,
)
from backend.core.enums import (
    TypeBillStep,
    LegPeriod,
    Legislature,
    TypeMotionStep,
    TypeMotion,
    Proponents,
    RoleOrganization,
    TypeRoleBill,
)

LEG_PERIOD_RANGES = [
    (LegPeriod.PERIODO_2026_2031, date(2026, 7, 28), date(2031, 7, 27)),
    (LegPeriod.PERIODO_2021_2026, date(2021, 7, 28), date(2026, 7, 27)),
    (LegPeriod.PERIODO_2016_2021, date(2016, 7, 28), date(2021, 7, 27)),
    (LegPeriod.PERIODO_2011_2016, date(2011, 7, 28), date(2016, 7, 27)),
    (LegPeriod.PERIODO_2006_2011, date(2006, 7, 28), date(2011, 7, 27)),
    (LegPeriod.PERIODO_2001_2006, date(2001, 7, 28), date(2006, 7, 27)),
    (LegPeriod.PERIODO_2000_2001, date(2000, 7, 28), date(2001, 7, 27)),
    (LegPeriod.PERIODO_1995_2000, date(1995, 7, 28), date(2000, 7, 27)),
]


def _normalize_leg_period(value: str) -> str:
    # 1) Unicode normalize (handles odd forms)
    v = unicodedata.normalize("NFKC", value)

    # 2) Replace non-breaking spaces and other common weird spaces with normal space
    v = v.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")

    v = v.strip()

    # 3) normalize different dash characters to "-"
    v = re.sub(r"[–—−]", "-", v)

    # 4) normalize spaces around dash
    v = re.sub(r"\s*-\s*", "-", v)

    # 5) collapse multiple spaces
    v = re.sub(r"\s+", " ", v)

    return v


LEG_PERIOD_RE = re.compile(r"(\d{4})-(\d{4})")


def parse_leg_period(value: str) -> LegPeriod:
    if value is None:
        raise ValueError("leg_period cannot be null")

    v = _normalize_leg_period(value)

    canon = LEG_PERIOD_ALIASES.get(v)
    if canon is None:
        m = LEG_PERIOD_RE.search(v)
        if m:
            canon = f"{m.group(1)}-{m.group(2)}"

    if canon is None:
        raise ValueError(f"Unknown leg period: {value!r} (normalized={v!r})")

    return LegPeriod(canon)


def _normalize_legislature(value: str) -> str:
    v = value.strip()
    v = re.sub(r"\s+", " ", v)  # collapse whitespace
    return v


def parse_legislature(value: str) -> Legislature:
    if value is None:
        raise ValueError("legislature cannot be null")

    v = _normalize_legislature(value)
    canon = LEGISLATURE_ALIASES.get(v)

    if canon is None:
        raise ValueError(f"Unknown legislature: {value!r}")

    return Legislature(canon)


def parse_role_bill(value: int | str) -> TypeRoleBill:
    if value is None:
        raise ValueError("role_bill cannot be null")

    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())

    canon = BILL_ROLE_MAPS.get(value, value)
    role_map = {
        "author": TypeRoleBill.AUTHOR,
        "autor": TypeRoleBill.AUTHOR,
        "coauthor": TypeRoleBill.COAUTHOR,
        "coautor": TypeRoleBill.COAUTHOR,
        "adherente": TypeRoleBill.ADHERENTE,
        TypeRoleBill.AUTHOR.value: TypeRoleBill.AUTHOR,
        TypeRoleBill.COAUTHOR.value: TypeRoleBill.COAUTHOR,
        TypeRoleBill.ADHERENTE.value: TypeRoleBill.ADHERENTE,
    }

    role = role_map.get(str(canon).strip().lower())
    if role is None:
        raise ValueError(f"Unknown role_bill: {value!r}")
    return role


MOTION_TYPE_ALIASES = {
    "Otorgar Facultades de Comisión Investigadora": TypeMotion.COMISION_INVESTIGADORA,
    "Comisiones Investigadoras": TypeMotion.COMISION_INVESTIGADORA,
}


def parse_motion_type(value: str | None) -> TypeMotion:
    if value is None:
        raise ValueError("motion_type cannot be null")

    v = " ".join(value.strip().split())

    if v in MOTION_TYPE_ALIASES:
        return MOTION_TYPE_ALIASES[v]

    for item in TypeMotion:
        if item.value == v:
            return item

    raise ValueError(f"Unknown motion_type: {value!r}")


def parse_proponent(value: str) -> Proponents:
    if value is None:
        raise ValueError("proponent cannot be null")

    v = " ".join(value.strip().split())

    try:
        return Proponents(v)
    except ValueError:
        pass

    # Handle suffixes like "Congreso-Actualización"
    if "-" in v:
        head = v.split("-", 1)[0].strip()
        try:
            return Proponents(head)
        except ValueError:
            pass

    raise ValueError(f"Unknown proponent: {value!r}")


DES_ESTADO_TO_MOTION_STEP_LABEL: dict[str, TypeMotionStep] = {
    "": TypeMotionStep.SIN_CATEGORIA,
    # Presented / admission
    "Presentado": TypeMotionStep.PRESENTADO,
    "Admitida la Moción": TypeMotionStep.ADMISION,
    "ADMITIDA A DEBATE": TypeMotionStep.ADMISION,
    "NO ADMITIDA A DEBATE": TypeMotionStep.ADMISION,
    "RECHAZADA LA ADMISIÓN A DEBATE": TypeMotionStep.ADMISION,
    # Committee handling
    "En Comisión": TypeMotionStep.ETAPA_EN_COMISION,
    "Integrantes de Comisión": TypeMotionStep.ETAPA_EN_COMISION,
    "Aprobado integrantes de Comisión": TypeMotionStep.ETAPA_EN_COMISION,
    # Agenda / internal routing (CD = Consejo Directivo)
    "En Agenda C.D": TypeMotionStep.AGENDA_CD,
    "PARA SER VISTA POR EL CONSEJO DIRECTIVO": TypeMotionStep.AGENDA_CD,
    "Tramitada con conocimiento del CD": TypeMotionStep.ACUERDO_CD,
    "TRAMITADA CON ACUERDO DE CD": TypeMotionStep.ACUERDO_CD,
    "Por Acuerdo de CD.": TypeMotionStep.ACUERDO_CD,
    "Acuerdo Junta de Portavoces": TypeMotionStep.ACUERDO_JP,
    # Pleno routing / agenda
    "Para ser vista por el Pleno": TypeMotionStep.AGENDA_DEL_PLENO,
    "En Agenda del Pleno": TypeMotionStep.AGENDA_DEL_PLENO,
    "En Agenda de Pleno": TypeMotionStep.AGENDA_DEL_PLENO,
    "Orden del Día": TypeMotionStep.AGENDA_DEL_PLENO,
    "Dado cuenta en el Pleno": TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA,
    "Se ha dado cuenta": TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA,
    "Por Acuerdo de Pleno": TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA,
    # Debate / floor handling
    "En Debate": TypeMotionStep.DEBATE,
    "En debate": TypeMotionStep.DEBATE,
    "Leída en sesión": TypeMotionStep.DEBATE,
    "Fundamentada la Moción": TypeMotionStep.FUNDAMENTACION,
    # Vote-ish / outcomes
    "Aprobada": TypeMotionStep.VOTACION_O_DECISION,
    "Aprobada la Moción": TypeMotionStep.VOTACION_O_DECISION,
    "Rechazada": TypeMotionStep.VOTACION_O_DECISION,
    # Reconsideration
    "Reconsideración": TypeMotionStep.RECONSIDERACION,
    "Rechazada Reconsideración": TypeMotionStep.RECONSIDERACION,
    # Text updates
    "Texto consensuado": TypeMotionStep.REVISION_DE_TEXTO,
    "Texto Sustitutorio": TypeMotionStep.REVISION_DE_TEXTO,
    "Adhesión": TypeMotionStep.REVISION_DE_TEXTO,
    "Se adhiere": TypeMotionStep.REVISION_DE_TEXTO,
    "Retiro de Firma": TypeMotionStep.RETIRADO,
    # Official comms / documents
    "Oficio": TypeMotionStep.COMUNICACION_OFICIAL,
    "Fe de Erratas": TypeMotionStep.FE_DE_ERRATAS_O_CORRECCION,
    # Publication
    "Publicado Diario Oficial  El Peruano": TypeMotionStep.PUBLICADO,
    "Publicado Diario Oficial El Peruano": TypeMotionStep.PUBLICADO,
    # Appearances (minister, etc.)
    "Concurre Ministro": TypeMotionStep.ASISTENCIA_O_COMPARECENCIA,
    "Asiste": TypeMotionStep.ASISTENCIA_O_COMPARECENCIA,
    "Asistió el Ministro  para contestar el pliego.": TypeMotionStep.ASISTENCIA_O_COMPARECENCIA,
    "Asistió el Ministro para contestar el pliego.": TypeMotionStep.ASISTENCIA_O_COMPARECENCIA,
    # Order / procedural
    "Cuestión de Orden": TypeMotionStep.CUESTION_DE_ORDEN,
    "EN CUARTO INTERMEDIO": TypeMotionStep.CUARTO_INTERMEDIO,
    # Requirements / blocking status
    "INCUMPLE REQUISITOS PARA CONTINUAR SU TRÁMITE": TypeMotionStep.BLOQUEO_POR_REQUISITOS,
    # Withdrawal
    "Solicita retiro de moción": TypeMotionStep.RETIRADO,
    "RETIRADA POR SU AUTOR": TypeMotionStep.RETIRADO,
    "Se deje sin efecto": TypeMotionStep.RETIRADO,
    # Archive
    "Al archivo": TypeMotionStep.ARCHIVADO,
    "En Archivo General": TypeMotionStep.ARCHIVADO,
    # Resignation / referrals
    "Renuncia": TypeMotionStep.RENUNCIA,
    "En Fiscalía de la Nación": TypeMotionStep.COMUNICACION_OFICIAL,
}


DES_ESTADO_TO_STEP_LABEL: dict[str, TypeBillStep] = {
    "------": TypeBillStep.SIN_CATEGORIA,
    # Presented
    "PRESENTADO": TypeBillStep.PRESENTADO,
    # Assigned / committee routing
    "EN COMISIÓN": TypeBillStep.EN_COMISION,
    "PASA A COMISIÓN": TypeBillStep.EN_COMISION,
    "RETORNA A COMISIÓN": TypeBillStep.EN_COMISION,
    "Acumulado en Sala": TypeBillStep.ACUMULADO,
    # Committee stage artifacts / decisions
    "DICTAMEN": TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
    "ACUERDO DE COMISIÓN": TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
    # Exemptions / procedural shortcuts
    "Dispensado de Dictamen": TypeBillStep.EXONERACION_DE_DICTAMEN,
    "EXONERADO DE DICTAMEN": TypeBillStep.EXONERACION_DE_DICTAMEN,
    "EXONERADO DE PLAZO DE PUBLICACIÓN": TypeBillStep.EXONERACION_DE_DICTAMEN,
    "Dispensado de Publicación en el Portal": TypeBillStep.EXONERACION_DE_DICTAMEN,
    # Agenda
    "Orden del Día": TypeBillStep.AGENDA_DEL_PLENO,
    "EN AGENDA DEL PLENO": TypeBillStep.AGENDA_DEL_PLENO,
    "EN AGENDA DE LA COMISIÓN PERMANENTE": TypeBillStep.AGENDA_DE_LA_COMISION_PERMANENTE,
    # Debate
    "EN DEBATE - PLENO": TypeBillStep.DEBATE_EN_EL_PLENO,
    "EN DEBATE - COMISIÓN PERMANENTE": TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE,
    "EN DEBATE DE LA COMISIÓN PERMANENTE": TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE,
    # Vote events
    "APROBADO 1ERA. VOTACIÓN": TypeBillStep.VOTACION,
    "Pendiente 2da. votación": TypeBillStep.VOTACION,
    "Pendiente 2da. Votación": TypeBillStep.VOTACION,
    "No alcanzó Nº de votos": TypeBillStep.VOTACION,
    "No alcanzó N° de votos": TypeBillStep.VOTACION,
    "No alcanzó No de votos": TypeBillStep.VOTACION,
    "NO APROBADO": TypeBillStep.VOTACION,
    "APROBADO": TypeBillStep.VOTACION,
    "Aprobado Com.Permanente": TypeBillStep.VOTACION,
    "ACUERDO DEL PLENO": TypeBillStep.VOTACION,
    # Text / autographs (post-approval drafting)
    "TEXTO SUSTITUTORIO": TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION,
    "AUTÓGRAFA": TypeBillStep.AUTOGRAFA,
    "AUTÓGRAFA OBSERVADA": TypeBillStep.AUTOGRAFA,
    # Reconsideration
    "EN RECONSIDERACIÓN": TypeBillStep.RECONSIDERACION,
    # Rejection
    "RECHAZADO": TypeBillStep.RECHAZADO,
    # Withdrawal
    "Retirado por su Autor": TypeBillStep.RETIRADO,
    "Solicita Retiro": TypeBillStep.RETIRADO,
    "Retiro de Firma": TypeBillStep.RETIRADO,
    # Archive
    "Al Archivo": TypeBillStep.ARCHIVADO,
    "DECRETO DE ARCHIVO": TypeBillStep.ARCHIVADO,
    # Promulgation / publication
    "Promulgado/Presidente de la República": TypeBillStep.PROMULGADO,
    "Promulgado/Presidente del Congreso": TypeBillStep.PROMULGADO,
    "Publicada en el Diario Oficial El Peruano": TypeBillStep.PUBLICADO,
    # Clarification / internal routing
    "ACLARACIÓN": TypeBillStep.ACLARACION,
    "EN CUARTO INTERMEDIO": TypeBillStep.CUARTO_INTERMEDIO,
    "PARA CONSEJO DIRECTIVO": TypeBillStep.AGENDA_DEL_CONSEJO_DIRECTIVO,
}


def classify_motion_des_estado(
    des_estado: str | None, detail: str | None = None
) -> TypeMotionStep:
    key = _normalize_step_text(des_estado)
    status_label = _lookup_step_label(DES_ESTADO_TO_MOTION_STEP_LABEL, key)
    detail_labels = _collect_detail_labels(detail, _MOTION_DETAIL_LABEL_RULES)
    return _resolve_step_label(
        status_label,
        detail_labels,
        _MOTION_STEP_PRIORITY,
        TypeMotionStep.SIN_CATEGORIA,
    )


def classify_des_estado(
    des_estado: str | None, detail: str | None = None
) -> TypeBillStep:
    key = _normalize_step_text(des_estado)
    status_label = _lookup_step_label(DES_ESTADO_TO_STEP_LABEL, key)
    detail_labels = _collect_detail_labels(detail, _BILL_DETAIL_LABEL_RULES)
    return _resolve_step_label(
        status_label,
        detail_labels,
        _BILL_STEP_PRIORITY,
        TypeBillStep.SIN_CATEGORIA,
    )


def _normalize_step_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")
    text = re.sub(r"[–—−]", "-", text)
    return " ".join(text.strip().split())


def _lookup_step_label(mapping: dict[str, object], key: str):
    if not key:
        return None
    return mapping.get(key) or mapping.get(key.upper()) or mapping.get(key.title())


def _collect_detail_labels(
    detail: str | None, rules: list[tuple[re.Pattern[str], object]]
) -> list:
    detail_key = _normalize_step_text(detail)
    if not detail_key:
        return []

    labels = []
    for pattern, label in rules:
        if pattern.search(detail_key):
            labels.append(label)
    return labels


def _resolve_step_label(
    status_label, detail_labels: list, priority_map: dict, unknown_label
):
    best_label = status_label or unknown_label
    best_rank = (priority_map.get(best_label, 0), 0, 0)

    for index, label in enumerate(detail_labels):
        rank = (priority_map.get(label, 0), 1, -index)
        if rank > best_rank:
            best_label = label
            best_rank = rank

    return best_label


_BILL_DETAIL_LABEL_RULES: list[tuple[re.Pattern[str], TypeBillStep]] = [
    (
        re.compile(
            r"\bpublicad[ao]s?\b.*\b(diario oficial|el peruano)\b", re.IGNORECASE
        ),
        TypeBillStep.PUBLICADO,
    ),
    (
        re.compile(r"\bpromulgad[ao]s?\b", re.IGNORECASE),
        TypeBillStep.PROMULGADO,
    ),
    (
        re.compile(
            r"\bsolicita retiro\b|\bretirad[oa] por su autor\b|\bretiro de firma\b|\bconsid[eé]rese retirad[oa]\b",
            re.IGNORECASE,
        ),
        TypeBillStep.RETIRADO,
    ),
    (
        re.compile(
            r"\bal archivo\b|\benv[ií]o al archivo\b|\bdecreto de archivo\b|\bpas[oó] al archivo\b",
            re.IGNORECASE,
        ),
        TypeBillStep.ARCHIVADO,
    ),
    (
        re.compile(
            r"\basistencia y votaci[oó]n\b|\bprimera votaci[oó]n\b|\bsegunda votaci[oó]n\b|\b1era\.?\s*votaci[oó]n\b|\b2da\.?\s*votaci[oó]n\b|\bno alcanz[oó]\b.*\bvotos?\b",
            re.IGNORECASE,
        ),
        TypeBillStep.VOTACION,
    ),
    (
        re.compile(r"\bcuarto intermedio\b", re.IGNORECASE),
        TypeBillStep.CUARTO_INTERMEDIO,
    ),
    (
        re.compile(r"\bdebat\w+\b.*\bcomisi[oó]n permanente\b", re.IGNORECASE),
        TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE,
    ),
    (
        re.compile(r"\b(debate|debat\w+)\b", re.IGNORECASE),
        TypeBillStep.DEBATE_EN_EL_PLENO,
    ),
    (
        re.compile(
            r"^reconsideraci[oó]n\b|\basistencia y votaci[oó]n\s*-\s*reconsideraci[oó]n\b|\breconsideraci[oó]n a la votaci[oó]n\b|\bpresentaron reconsideraci[oó]n\b|\bpresentada .* reconsideraci[oó]n\b",
            re.IGNORECASE,
        ),
        TypeBillStep.RECONSIDERACION,
    ),
    (
        re.compile(
            r"\b(texto|nuevo texto|f[oó]rmula)\s+sustitutor\w*\b|\btexto consensuado\b",
            re.IGNORECASE,
        ),
        TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION,
    ),
    (
        re.compile(r"\baut[oó]grafa\b", re.IGNORECASE),
        TypeBillStep.AUTOGRAFA,
    ),
    (
        re.compile(r"\baclaraci[oó]n\b", re.IGNORECASE),
        TypeBillStep.ACLARACION,
    ),
    (
        re.compile(
            r"\bexoneraci[oó]n de dictamen\b|\bexoneraci[oó]n del? plazo de publicaci[oó]n\b|\bdispensad[oa] de dictamen\b|\bdispensad[oa] de publicaci[oó]n\b|\bexoneraci[oó]n del tr[aá]mite de env[ií]o a comisi[oó]n\b",
            re.IGNORECASE,
        ),
        TypeBillStep.EXONERACION_DE_DICTAMEN,
    ),
    (
        re.compile(r"\bacumulad[oa]\b", re.IGNORECASE),
        TypeBillStep.ACUMULADO,
    ),
    (
        re.compile(
            r"\b(pasa|pas[oó]|retorna|retorn[ao]) a comisi[oó]n\b|\bdevuelv\w+ a la comisi[oó]n\b",
            re.IGNORECASE,
        ),
        TypeBillStep.EN_COMISION,
    ),
    (
        re.compile(r"\bconsejo directivo\b", re.IGNORECASE),
        TypeBillStep.AGENDA_DEL_CONSEJO_DIRECTIVO,
    ),
    (
        re.compile(r"\bagenda\b.*\bcomisi[oó]n permanente\b", re.IGNORECASE),
        TypeBillStep.AGENDA_DE_LA_COMISION_PERMANENTE,
    ),
    (
        re.compile(
            r"\b(orden del d[ií]a|ampliaci[oó]n de agenda|agenda del pleno)\b",
            re.IGNORECASE,
        ),
        TypeBillStep.AGENDA_DEL_PLENO,
    ),
]


_BILL_STEP_PRIORITY: dict[TypeBillStep, int] = {
    TypeBillStep.SIN_CATEGORIA: 0,
    TypeBillStep.AGENDA_DEL_CONSEJO_DIRECTIVO: 100,
    TypeBillStep.AGENDA_DEL_PLENO: 110,
    TypeBillStep.AGENDA_DE_LA_COMISION_PERMANENTE: 120,
    TypeBillStep.EN_COMISION: 130,
    TypeBillStep.PRESENTADO: 140,
    TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION: 160,
    TypeBillStep.EXONERACION_DE_DICTAMEN: 320,
    TypeBillStep.ACUMULADO: 330,
    TypeBillStep.ACLARACION: 340,
    TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION: 350,
    TypeBillStep.RECONSIDERACION: 370,
    TypeBillStep.DEBATE_EN_EL_PLENO: 500,
    TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE: 510,
    TypeBillStep.CUARTO_INTERMEDIO: 520,
    TypeBillStep.VOTACION: 530,
    TypeBillStep.RECHAZADO: 540,
    TypeBillStep.ARCHIVADO: 550,
    TypeBillStep.RETIRADO: 560,
    TypeBillStep.AUTOGRAFA: 570,
    TypeBillStep.PROMULGADO: 590,
    TypeBillStep.PUBLICADO: 600,
}


_MOTION_DETAIL_LABEL_RULES: list[tuple[re.Pattern[str], TypeMotionStep]] = [
    (
        re.compile(r"\bfundamenta\b.*\bmoci[oó]n\b", re.IGNORECASE),
        TypeMotionStep.FUNDAMENTACION,
    ),
    (
        re.compile(
            r"\basistencia y votaci[oó]n\b|\b(fue|fueron)\s+aprobad[ao]s?\b|\b(fue|fueron)\s+rechazad[ao]s?\b|\baprobad[ao]\s+(la|el|un|una)\b|\brechazad[ao]\s+la\b|\bno alcanz[oó]\b.*\bvotos?\b|\bpor \d+ votos?\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.VOTACION_O_DECISION,
    ),
    (
        re.compile(
            r"\badmitid[ao]\b.*\bmoci[oó]n\b|\badmisi[oó]n a debate\b", re.IGNORECASE
        ),
        TypeMotionStep.ADMISION,
    ),
    (
        re.compile(
            r"\bse ha dado cuenta\b|\bse consultar[aá] su admisi[oó]n\b|\banunci[oó] que se hab[ií]a presentado la moci[oó]n\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA,
    ),
    (
        re.compile(
            r"\ble[ií]d[ao] en sesi[oó]n\b|\bfue le[ií]d[ao]\b.*\bsesi[oó]n\b|\bse reabri[oó] el debate\b|\breabri[oó] el debate\b|\ben debate\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.DEBATE,
    ),
    (
        re.compile(
            r"\bpas[oó] a la comisi[oó]n\b|\bpase a la comisi[oó]n\b|\bdevolvi[oó] a la comisi[oó]n\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.ETAPA_EN_COMISION,
    ),
    (
        re.compile(
            r"^(acta de acuerdo|acuerdo n[°ºo.]?\s*\d+|oficio|carta|informe)\b|^\bn[°ºo.]?\s*\d+",
            re.IGNORECASE,
        ),
        TypeMotionStep.COMUNICACION_OFICIAL,
    ),
    (
        re.compile(
            r"\bsolicita el retiro\b|\bsolicita retiro\b|\bconsid[eé]rese retirad[oa]\b|\bretira su moci[oó]n\b|\bdeje sin efecto\b|\bsolicita el retiro de la moci[oó]n\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.RETIRADO,
    ),
    (
        re.compile(r"\bal archivo\b|\bpas[oó] al archivo\b", re.IGNORECASE),
        TypeMotionStep.ARCHIVADO,
    ),
    (
        re.compile(
            r"\bcuarto intermedio\b|\btexto sustitutorio presentado\b", re.IGNORECASE
        ),
        TypeMotionStep.CUARTO_INTERMEDIO,
    ),
    (
        re.compile(r"\breconsideraci[oó]n\b", re.IGNORECASE),
        TypeMotionStep.RECONSIDERACION,
    ),
    (
        re.compile(
            r"\btexto sustitutorio\b|\btexto consensuado\b|\badhier[ea]\b|\bcon texto sustitutorio\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.REVISION_DE_TEXTO,
    ),
    (
        re.compile(r"\bfe de erratas\b", re.IGNORECASE),
        TypeMotionStep.FE_DE_ERRATAS_O_CORRECCION,
    ),
    (
        re.compile(
            r"^(censurar|saludar|felicitar|expresar|considerar|conformar|aprobar|declarar|otorgar|constituir|crear)\b",
            re.IGNORECASE,
        ),
        TypeMotionStep.PRESENTADO,
    ),
]


_MOTION_STEP_PRIORITY: dict[TypeMotionStep, int] = {
    TypeMotionStep.SIN_CATEGORIA: 0,
    TypeMotionStep.AGENDA_CD: 100,
    TypeMotionStep.ACUERDO_CD: 105,
    TypeMotionStep.ACUERDO_JP: 108,
    TypeMotionStep.AGENDA_DEL_PLENO: 110,
    TypeMotionStep.PRESENTADO: 120,
    TypeMotionStep.REVISION_DE_TEXTO: 300,
    TypeMotionStep.RECONSIDERACION: 310,
    TypeMotionStep.COMUNICACION_OFICIAL: 320,
    TypeMotionStep.ETAPA_EN_COMISION: 330,
    TypeMotionStep.ASISTENCIA_O_COMPARECENCIA: 340,
    TypeMotionStep.ANUNCIO_O_DACION_DE_CUENTA: 350,
    TypeMotionStep.ADMISION: 360,
    TypeMotionStep.FUNDAMENTACION: 370,
    TypeMotionStep.DEBATE: 380,
    TypeMotionStep.CUESTION_DE_ORDEN: 390,
    TypeMotionStep.CUARTO_INTERMEDIO: 400,
    TypeMotionStep.VOTACION_O_DECISION: 410,
    TypeMotionStep.RETIRADO: 420,
    TypeMotionStep.ARCHIVADO: 430,
    TypeMotionStep.BLOQUEO_POR_REQUISITOS: 440,
    TypeMotionStep.RENUNCIA: 450,
    TypeMotionStep.PUBLICADO: 460,
    TypeMotionStep.FE_DE_ERRATAS_O_CORRECCION: 470,
}


def find_leg_period(value: str | date | datetime) -> LegPeriod:
    """
    Pure Python version.
    Use this when value is already a Python date/datetime.
    """
    if value is None:
        raise ValueError("date cannot be null")

    if isinstance(value, str):
        value = datetime.fromisoformat(value).date()
    elif isinstance(value, datetime):
        value = value.date()
    elif isinstance(value, date):
        pass
    else:
        raise TypeError(f"Expected str, date, or datetime. Got {type(value).__name__}")

    for leg_period, start_date, end_date in LEG_PERIOD_RANGES:
        if start_date <= value <= end_date:
            return leg_period

    return LegPeriod.PERIODO_1992_1995


def normalize_membership_role(raw: str) -> RoleOrganization:
    if not raw:
        raise ValueError("Empty membership role")

    role = raw.strip().lower()

    role_map = {
        "presidenta": RoleOrganization.PRESIDENTE,
        "presidente": RoleOrganization.PRESIDENTE,
        "vicepresidenta": RoleOrganization.VICEPRESIDENTE,
        "vicepresidente": RoleOrganization.VICEPRESIDENTE,
        "secretaria": RoleOrganization.SECRETARIO,
        "secretario": RoleOrganization.SECRETARIO,
        "vocera": RoleOrganization.VOCERO,
        "vocero": RoleOrganization.VOCERO,
        "miembro": RoleOrganization.MIEMBRO,
        "titular": RoleOrganization.TITULAR,
        "suplente": RoleOrganization.SUPLENTE,
        "accesitaria": RoleOrganization.ACCESITARIO,
        "accesitario": RoleOrganization.ACCESITARIO,
        "presidente (e) del congreso de la república": RoleOrganization.PRESIDENTE,
        "primer vicepresidente encargado de la presidencia del congreso de la república": RoleOrganization.VICEPRESIDENTE,
        "segundo vicepresidente": RoleOrganization.SEGUNDO_VICE,
        "tercer vicepresidente": RoleOrganization.TERCER_VICE,
        "diputado": RoleOrganization.DIPUTADO,
        "diputada": RoleOrganization.DIPUTADO,
        "senadora": RoleOrganization.SENADOR,
        "senador": RoleOrganization.SENADOR,
    }

    normalized_role = role_map.get(role)
    if normalized_role is None:
        raise ValueError(f"Unknown role: {role!r}")

    return normalized_role


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


# Canonical outputs must exactly match your enum values
_COMM_TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Most specific first
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+acusaciones\s+constitucionales", re.I),
        "Subcomisión de Acusaciones Constitucionales",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+control\s+pol[ií]tico", re.I),
        "Subcomisión de Control Político",
    ),
    (
        re.compile(
            r"^comisi[oó]n\s+de\s+levantamiento\s+de\s+inmunidad\s+parlamentaria", re.I
        ),
        "Comisión de Levantamiento de Inmunidad Parlamentaria",
    ),
    (
        re.compile(r"^comisi[oó]n\s+de\s+[eé]tica\s+parlamentaria", re.I),
        "Comisión de Ética Parlamentaria",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+seguimiento\s+del\s+tlc", re.I),
        "Sub Comisión de Seguimiento del TLC",
    ),
    # Common noisy cases
    (re.compile(r"^comisi[oó]n\s+ordinaria\b", re.I), "Comisión Ordinaria"),
    (
        re.compile(r"^comisiones?\s+investigadoras?\b", re.I),
        "Comisiones Investigadoras",
    ),
    (re.compile(r"^comisiones?\s+especiales?\b", re.I), "Comisiones Especiales"),
    (re.compile(r"^grupo\s+de\s+trabajo\b", re.I), "Grupo de Trabajo"),
]


def parse_comm_type(value: str) -> str:
    raw = value
    v = _norm_text(value)

    # normalize dash variants (optional, but consistent with your style)
    v = re.sub(r"[–—−]", "-", v)

    for pat, canon in _COMM_TYPE_RULES:
        if pat.search(v):
            return canon

    raise ValueError(f"Unknown comm_type: {raw!r} (normalized={v!r})")

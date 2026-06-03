from datetime import datetime, date
import re
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import TypeBillStep
from backend.config import settings
from backend.database import models as db_models

MONTHS_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

OBSERVED_AUTOGRAPH_NEEDLES = ("autógrafa observada", "autografa observada")
MAJORITY_NEEDLES = ("en mayoría", "en mayoria")
NO_APPROVAL_NEEDLES = ("no aprobación", "no aprobacion", "archivo")
APPROVAL_NEEDLES = (
    "aprobado",
    "aprobada",
    "aprueba",
    "acuerdo del pleno",
    "exoneración de segunda votación",
    "exoneracion de segunda votación",
    "exoneración de segunda votacion",
    "exoneracion de segunda votacion",
)
NEGATIVE_APPROVAL_NEEDLES = (
    "no aprobado",
    "no aprobada",
    "no aprobación",
    "no aprobacion",
    "no alcanzó",
    "no alcanzo",
)
DEBATE_TYPES = {
    TypeBillStep.DEBATE_EN_EL_PLENO,
    TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE,
}
COMMITTEE_DECISION_TYPES = {
    TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
    TypeBillStep.EXONERACION_DE_DICTAMEN,
}
INSISTENCE_TYPES = {
    TypeBillStep.VOTACION,
    TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
    TypeBillStep.EXONERACION_DE_DICTAMEN,
    TypeBillStep.RECONSIDERACION,
}


def _session_factory():
    engine = create_engine(settings.DB_URL)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _enum_text(value) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _step_type(step: db_models.BillStep) -> TypeBillStep | None:
    value = step.step_type
    if isinstance(value, TypeBillStep):
        return value
    try:
        return TypeBillStep(value)
    except ValueError:
        return None


def _clean_text(text: str | None) -> str:
    compact = " ".join((text or "").split())
    compact = _strip_time_fragments(compact)
    normalized = _normalize_caps_sentence(compact)
    return _restore_preferred_tokens(normalized)


def _strip_time_fragments(text: str) -> str:
    without_time = re.sub(
        r"\b\d{1,2}:\d{2}(?:\s*(?:a\.?m\.?|p\.?m\.?))?\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    without_empty_parens = re.sub(r"\(\s*\)", "", without_time)
    without_punct_parens = re.sub(
        r"\(\s*[\.,;:!?-]*\s*\)",
        "",
        without_empty_parens,
    )
    cleaned = " ".join(without_punct_parens.split())
    cleaned = re.sub(r"\s+([\.,;:!?])", r"\1", cleaned)
    return cleaned


def _restore_preferred_tokens(text: str) -> str:
    restored = re.sub(r"n\s*°", "N°", text, flags=re.IGNORECASE)
    restored = re.sub(r"\bperu\b", "Perú", restored, flags=re.IGNORECASE)
    restored = re.sub(r"\bperú\b", "Perú", restored, flags=re.IGNORECASE)
    return restored


def _capitalize_first_alpha(text: str) -> str:
    for idx, char in enumerate(text):
        if char.isalpha():
            return text[:idx] + char.upper() + text[idx + 1 :]
    return text


def _normalize_caps_sentence(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return text

    upper_ratio = sum(char.isupper() for char in letters) / len(letters)
    if upper_ratio < 0.9:
        return text

    lowered = text.lower()
    chunks = re.split(r"([.!?]\s+)", lowered)
    normalized = []

    for index, chunk in enumerate(chunks):
        if index % 2 == 0:
            normalized.append(_capitalize_first_alpha(chunk))
        else:
            normalized.append(chunk)

    return "".join(normalized)


def _format_date(date_value: date | None) -> str:
    if date_value is None:
        return ""
    return f"{date_value.day} de {MONTHS_ES[date_value.month]} de {date_value.year}"


def _format_month_year(date_value: date | None) -> str:
    if date_value is None:
        return ""
    return f"{MONTHS_ES[date_value.month]} de {date_value.year}"


def _date_only(date_value: date | datetime | None) -> date | None:
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value.date()
    return date_value


def _format_elapsed_time(days: int) -> str:
    if days < 30:
        return f"{days} días"

    total_months = days // 30
    remainder_days = days % 30

    # Round up when the remainder is close to a full month.
    if remainder_days >= 25:
        total_months += 1
        remainder_days = 0

    years = total_months // 12
    months = total_months % 12

    parts = []
    if years > 0:
        parts.append("1 año" if years == 1 else f"{years} años")
    if months > 0:
        parts.append("1 mes" if months == 1 else f"{months} meses")
    if not parts:
        parts.append("1 mes")

    elapsed_text = " y ".join(parts)
    if years == 0 and 15 <= remainder_days < 25:
        elapsed_text += " y medio"

    return elapsed_text


def _build_context(bill_id: str, steps: list[db_models.BillStep]) -> str:
    lines = [
        f"Proyecto: {bill_id}",
        "Linea de tiempo de pasos legislativos (en orden cronologico):",
    ]
    for idx, step in enumerate(steps, start=1):
        step_date = step.step_date.isoformat() if step.step_date else ""
        step_type = _enum_text(step.step_type)
        line = f"{idx}. [{step_date}] ({step_type}) {_clean_text(step.step_detail)}"
        lines.append(line)
    return "\n".join(lines)


def _score_step(step: db_models.BillStep) -> int:
    step_type = _step_type(step)
    detail = _clean_text(step.step_detail).lower()

    base_scores = {
        TypeBillStep.PUBLICADO: 100,
        TypeBillStep.PROMULGADO: 95,
        TypeBillStep.AUTOGRAFA: 90,
        TypeBillStep.ARCHIVADO: 87,
        TypeBillStep.RETIRADO: 87,
        TypeBillStep.RECHAZADO: 87,
        TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION: 60,
        TypeBillStep.PRESENTADO: 50,
        TypeBillStep.EN_COMISION: 45,
        TypeBillStep.RECONSIDERACION: 40,
    }
    for debate_type in DEBATE_TYPES:
        base_scores[debate_type] = 70
    for committee_type in COMMITTEE_DECISION_TYPES:
        base_scores[committee_type] = 65

    score = base_scores.get(step_type, 20)
    if step_type == TypeBillStep.VOTACION:
        score = 85 if _is_approved_vote(step) else 75

    if any(needle in detail for needle in OBSERVED_AUTOGRAPH_NEEDLES):
        score = max(score, 94)
    if "insistencia" in detail:
        score += 18
    if any(needle in detail for needle in MAJORITY_NEEDLES):
        score += 12
    if "exoneración de segunda votación" in detail:
        score += 15

    return score


def _rank_steps(steps: list[db_models.BillStep]) -> list[dict]:
    ranked = []
    for step in steps:
        ranked.append(
            {
                "step": step,
                "score": _score_step(step),
                "type": _step_type(step),
                "detail": _clean_text(step.step_detail),
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["score"],
            date.max - (_date_only(item["step"].step_date) or date.min),
            _enum_text(item["type"]),
        )
    )
    return ranked


def _find_ranked_step(
    ranked_steps: list[dict],
    accepted_types: set[TypeBillStep],
    needles=(),
    predicate=None,
):
    for item in ranked_steps:
        if item["type"] not in accepted_types:
            continue

        if predicate is not None and not predicate(item["step"]):
            continue

        if not needles:
            return item["step"]

        detail = item["detail"].lower()
        if any(needle in detail for needle in needles):
            return item["step"]

    return None


def _detail_contains(step: db_models.BillStep, needles: tuple[str, ...]) -> bool:
    detail = _clean_text(step.step_detail).lower()
    return any(needle in detail for needle in needles)


def _is_approved_vote(step: db_models.BillStep) -> bool:
    if _step_type(step) != TypeBillStep.VOTACION:
        return False

    detail = _clean_text(step.step_detail).lower()
    if any(needle in detail for needle in NEGATIVE_APPROVAL_NEEDLES):
        return False
    return any(needle in detail for needle in APPROVAL_NEEDLES)


def _is_observed_autograph(step: db_models.BillStep) -> bool:
    return _step_type(step) == TypeBillStep.AUTOGRAFA and _detail_contains(
        step,
        OBSERVED_AUTOGRAPH_NEEDLES,
    )


def _has_second_vote_exoneration(step: db_models.BillStep) -> bool:
    return _detail_contains(
        step,
        (
            "exoneración de segunda votación",
            "exoneracion de segunda votación",
            "exoneración de segunda votacion",
            "exoneracion de segunda votacion",
        ),
    )


def _paragraph_one(
    bill_id: str, bill: db_models.Bill, steps: list[db_models.BillStep]
) -> str:
    start_date = steps[0].step_date
    title = _clean_text(bill.title)
    start_month_year = _format_month_year(start_date)

    sentence_one = (
        f"El Proyecto {bill_id}, presentado en {start_month_year}, aborda la {title}."
    )

    ranked_steps = _rank_steps(steps)

    majority_committee_step = _find_ranked_step(
        ranked_steps,
        COMMITTEE_DECISION_TYPES,
        needles=MAJORITY_NEEDLES,
    )
    debate_step = _find_ranked_step(ranked_steps, DEBATE_TYPES)
    approved_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.VOTACION},
        predicate=_is_approved_vote,
    )
    exoneration_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.VOTACION},
        predicate=_has_second_vote_exoneration,
    )
    exec_observed_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.AUTOGRAFA},
        predicate=_is_observed_autograph,
    )
    reconsideration_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.RECONSIDERACION},
    )
    reconsideration_rejected = False
    if reconsideration_step:
        reconsideration_rejected_step = _find_ranked_step(
            ranked_steps,
            {TypeBillStep.VOTACION},
            needles=("reconsideración", "rechazada"),
        )
        if reconsideration_rejected_step:
            detail = _clean_text(reconsideration_rejected_step.step_detail).lower()
            if "rechazada" in detail:
                reconsideration_rejected = True

    insistence_approval_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.VOTACION},
        needles=("insistencia",),
        predicate=_is_approved_vote,
    )
    if exec_observed_step and not insistence_approval_step:
        if debate_step:
            sentence_two = (
                "Tras su evaluación en comisión y su debate parlamentario, "
                "el proyecto fue observado por el Poder Ejecutivo y "
                "retornó a comisión para su revisión."
            )
        else:
            sentence_two = (
                "Tras su evaluación en comisión, el proyecto fue observado "
                "por el Poder Ejecutivo y retornó a comisión para su "
                "revisión."
            )
    # This branch is reserved for the strongest approval pattern: committee
    # approval, plenary debate, and exoneration together
    elif majority_committee_step and debate_step and approved_step and exoneration_step:
        if exec_observed_step:
            sentence_two = (
                "Tras su evaluación en comisión, se aprobó un dictamen en "
                "mayoría que fue debatido en el pleno, con exoneración de "
                "segunda votación, pero luego fue observado por el Poder "
                "Ejecutivo y retornó a comisión."
            )
        else:
            sentence_two = (
                "Tras su evaluación en comisión, se aprobó un dictamen en "
                "mayoría que fue debatido y aprobado en el pleno, "
                "con exoneración de segunda votación."
            )
    else:
        withdrawn_step = _find_ranked_step(ranked_steps, {TypeBillStep.RETIRADO})
        archived_or_rejected_step = _find_ranked_step(
            ranked_steps,
            {TypeBillStep.ARCHIVADO, TypeBillStep.RECHAZADO, TypeBillStep.RETIRADO},
        )
        no_approval_step = _find_ranked_step(
            ranked_steps,
            COMMITTEE_DECISION_TYPES | {TypeBillStep.ARCHIVADO},
            needles=NO_APPROVAL_NEEDLES,
        )

        # Prefer explicit withdrawal before falling back to generic archive
        # wording
        if withdrawn_step:
            sentence_two = (
                "Tras su evaluación en comisión, el proyecto fue retirado por su autor."
            )
        elif archived_or_rejected_step or no_approval_step:
            sentence_two = (
                "Tras su evaluación en comisión, el proyecto no obtuvo "
                "aprobación y su trámite concluyó con su archivo."
            )
        elif approved_step:
            if debate_step:
                sentence_two = (
                    "Tras su evaluación en comisión y su "
                    "debate parlamentario, "
                    "el proyecto avanzó hasta su aprobación en el pleno."
                )
            else:
                sentence_two = (
                    "Tras su evaluación en comisión, el proyecto avanzó hasta "
                    "su aprobación en el pleno."
                )
        else:
            if debate_step:
                sentence_two = (
                    "Tras su evaluación en comisión y su "
                    "debate parlamentario, "
                    "el proyecto continuó su trámite sin un resultado final "
                    "aprobatorio en los registros disponibles."
                )
            else:
                sentence_two = (
                    "Tras su evaluación en comisión, el proyecto continuó su "
                    "trámite sin un resultado final aprobatorio en los "
                    "registros disponibles."
                )

    if reconsideration_rejected and approved_step:
        sentence_two += (
            " Hubo una reconsideración que fue rechazada, pero el proyecto avanzó."
        )

    return f"{sentence_one} {sentence_two}"


def _paragraph_two(bill, steps) -> str:
    ranked_steps = _rank_steps(steps)

    exec_observed_step = _find_ranked_step(
        ranked_steps,
        {TypeBillStep.AUTOGRAFA},
        predicate=_is_observed_autograph,
    )
    insistence_step = _find_ranked_step(
        ranked_steps,
        INSISTENCE_TYPES,
        needles=("insistencia",),
    )

    promulgated_step = _find_ranked_step(ranked_steps, {TypeBillStep.PROMULGADO})
    published_step = _find_ranked_step(ranked_steps, {TypeBillStep.PUBLICADO})

    # Use the observation and insistence narrative only when both events
    # are present.
    if exec_observed_step and insistence_step:
        observed_month_year = _format_month_year(exec_observed_step.step_date)
        sentence_one = (
            f"En {observed_month_year}, el Poder Ejecutivo "
            "observó la autógrafa, "
            "pero el Congreso decidió insistir en su versión original."
        )
    # If there was an observation but no insistence, describe the observed
    # return path instead
    elif exec_observed_step and not insistence_step:
        observed_month_year = _format_month_year(exec_observed_step.step_date)
        status_text = _clean_text(bill.status).lower()
        last_step_type = _step_type(steps[-1])

        if last_step_type == TypeBillStep.EN_COMISION or "comisión" in status_text:
            sentence_one = (
                f"En {observed_month_year}, el Poder Ejecutivo observó "
                "la autógrafa y el proyecto retornó a comisión para su "
                "revisión."
            )
        else:
            sentence_one = (
                f"En {observed_month_year}, el Poder Ejecutivo observó "
                "la autógrafa y el proyecto continuó su trámite "
                "parlamentario."
            )
    else:
        # When there is no special observation pattern, summarize the elapsed
        # span from the first to the last step.
        first_date = _date_only(steps[0].step_date)
        last_date = _date_only(steps[-1].step_date)
        elapsed_days = (last_date - first_date).days
        elapsed_text = _format_elapsed_time(elapsed_days)
        sentence_one = (
            "El último estado identificado fue del "
            f"{_format_date(last_date)} y el documento permaneció en "
            f"trámite por un periodo de {elapsed_text}."
        )

    law_text = ""
    if promulgated_step:
        law_text = _clean_text(promulgated_step.step_detail)
    elif published_step:
        law_text = _clean_text(published_step.step_detail)

    if not law_text:
        law_text = "norma final registrada"

    law_text = law_text.split(" - ")[0].strip()

    if promulgated_step:
        sentence_two = (
            f"Finalmente, el {_format_date(promulgated_step.step_date)} "
            f"se promulgó como la {law_text}."
        )
    elif published_step:
        sentence_two = (
            f"Finalmente, el {_format_date(published_step.step_date)} "
            f"se publicó la {law_text}."
        )
    else:
        status_text = _clean_text(bill.status)
        sentence_two = (
            f"Finalmente, el estado reportado del proyecto es: {status_text}."
        )

    return f"{sentence_one} {sentence_two}"


def summarize_bill_from_steps(bill: db_models.Bill, steps: list[db_models.BillStep]):
    context = _build_context(bill.id, steps)
    paragraph_one = _paragraph_one(bill.id, bill, steps).strip()

    if len(steps) <= 5:
        summary = paragraph_one
    else:
        paragraph_two = _paragraph_two(bill, steps).strip()
        summary = f"{paragraph_one}\n\n{paragraph_two}"

    return {
        "bill_id": bill.id,
        "context": context,
        "summary": summary,
    }


def summarize_bill_from_db(bill_id: str) -> dict:
    if not bill_id:
        return {
            "bill_id": "",
            "context": "",
            "summary": "Error: bill_id argument required",
        }

    SessionLocal = _session_factory()
    with SessionLocal() as db:
        bill = db.get(db_models.Bill, bill_id)
        if bill is None:
            return {
                "bill_id": bill_id,
                "context": "",
                "summary": (
                    f"No se encontro el proyecto {bill_id} en la base de datos."
                ),
            }

        steps = (
            db.query(db_models.BillStep)
            .filter(db_models.BillStep.bill_id == bill_id)
            .order_by(db_models.BillStep.step_date.asc())
            .all()
        )

        if not steps:
            return {
                "bill_id": bill_id,
                "context": "",
                "summary": (
                    f"El proyecto {bill_id} no tiene pasos legislativos registrados."
                ),
            }

    return summarize_bill_from_steps(bill, steps)


if __name__ == "__main__":
    if len(sys.argv) <= 1 or not sys.argv[1].strip():
        print(
            "Error: bill_id required. "
            "Use: python -m backend.process.summarization <bill_id>"
        )
        sys.exit(1)

    bill_id = sys.argv[1].strip()
    result = summarize_bill_from_db(bill_id=bill_id)
    print("--- INPUT_CONTEXT_START ---")
    print(result["context"])
    print("--- INPUT_CONTEXT_END ---")
    print(result["summary"])

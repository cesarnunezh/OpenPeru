import json
from datetime import date, datetime

from backend.core.enums import TypeMotionStep
from backend.core.parsers import classify_motion_des_estado
from backend.database.raw_models import RawMotion, RawMotionPage
from backend.process.schema import (
    Motion,
    MotionCongresistas,
    MotionOrganization,
    MotionStep,
    MotionText,
)
from backend.process.utils import create_vote_ids, as_date


def _parse_datetime(value: str | None) -> date | None:
    if value:
        return datetime.fromisoformat(value).date()
    return None


def summarize_motion(
    motion_id: str, presentation_date: date, steps: list[MotionStep]
) -> str:
    # TODO: Connect in another PR with summarization.
    return f"{motion_id}: PENDING SUMMARY with {len(steps)} steps presented on {presentation_date}"


def process_motion_text(motion_pages: list[RawMotionPage]) -> MotionText:
    ordered_pages = sorted(motion_pages, key=lambda page: page.page_num)
    if not ordered_pages:
        raise ValueError("Motion pages are required to build MotionText")

    first_page = ordered_pages[0]
    text = "\n".join((page.text or "").strip() for page in ordered_pages).strip()
    if not text:
        raise ValueError("Motion text could not be extracted from raw pages")

    return MotionText(
        motion_id=first_page.motion_id,
        step_id=int(first_page.step_id),
        file_id=int(first_page.file_id),
        version_id=1,
        text=text,
    )


def process_motion(
    raw_motion: RawMotion,
) -> tuple[Motion, list[MotionCongresistas], list[MotionStep]]:
    """
    Process a RawMotion instance into a Motion, signer relations, and steps.
    """
    general = json.loads(raw_motion.general or "{}")
    firmantes = json.loads(raw_motion.congresistas or "[]")

    motion_id = raw_motion.id
    motion_type = general.get("desTipoMocion")
    summary_congreso = general.get("sumilla")
    observations = general.get("observacion")
    status = classify_motion_des_estado(general.get("desEstadoMocion"))

    cong_list: list[MotionCongresistas] = []
    if firmantes:
        author_info = firmantes[0]
        author_name = author_info.get("nombre")
        author_web = author_info.get("pagWeb")

        for cong in firmantes:
            cong_list.append(
                MotionCongresistas(
                    motion_id=motion_id,
                    nombre=cong.get("nombre"),
                    role_type=cong.get("tipoFirmanteId"),
                    web_page=cong.get("pagWeb"),
                )
            )
    else:
        author_name = None
        author_web = None

    motion_steps = process_motion_steps(raw_motion)
    motion_approved = is_motion_approved(motion_steps, status)
    presentation_date = _parse_datetime(general.get("fecPresentacion"))
    summary_opencongress = summarize_motion(motion_id, presentation_date, motion_steps)

    motion = Motion(
        id=motion_id,
        motion_type=motion_type,
        summary_congreso=summary_congreso,
        observations=observations,
        status=status,
        author_name=author_name,
        author_web=author_web,
        motion_approved=motion_approved,
        summary_opencongress=summary_opencongress,
    )

    return motion, cong_list, motion_steps


def is_motion_approved(steps: list[MotionStep], status: str | None = None) -> bool:
    if steps:
        return any([step.step_type == TypeMotionStep.PUBLICADO for step in steps])
    return status == TypeMotionStep.PUBLICADO


def process_motion_steps(raw_motion: RawMotion) -> list[MotionStep]:
    """
    Process a RawMotion instance into a sorted list of MotionStep records.
    """
    steps = json.loads(raw_motion.steps or "[]")
    if not steps:
        return []

    final_steps: list[MotionStep] = []
    for step in steps:
        step_id = step.get("seguimientoId")
        date = _parse_datetime(step.get("fecSeguimiento"))
        details = step.get("detalle") or ""
        step_type = classify_motion_des_estado(step.get("desEstadoMocion"), details)
        vote_step = step_type == TypeMotionStep.VOTACION_O_DECISION

        final_steps.append(
            MotionStep(
                motion_id=raw_motion.id,
                step_id=step_id,
                step_type=step_type,
                vote_step=vote_step,
                vote_event_id=None,
                step_date=date,
                step_detail=details,
            )
        )

    return create_vote_ids(final_steps)


def _get_motion_dates(
    raw_motion: RawMotion,
    motion_steps: list[MotionStep],
) -> dict[str, datetime | None]:
    dates: dict[str, datetime | None] = {
        "presentation_date": None,
        "final_chamber_decision_date": None,
    }

    for step in sorted(motion_steps, key=lambda item: item.step_date):
        if (
            step.step_type == TypeMotionStep.PRESENTADO
            and dates["presentation_date"] is None
        ):
            dates["presentation_date"] = step.step_date

        if step.step_type in {
            TypeMotionStep.VOTACION_O_DECISION,
            TypeMotionStep.PUBLICADO,
        }:
            dates["final_chamber_decision_date"] = step.step_date

    if dates["presentation_date"] is None:
        general = json.loads(raw_motion.general or "{}")
        raw_presentation_date = general.get("fecPresentacion")
        if raw_presentation_date:
            dates["presentation_date"] = _parse_datetime(raw_presentation_date)

    return dates


def process_motion_organizations(
    raw_motion: RawMotion,
    motion_steps: list[MotionStep],
) -> list[MotionOrganization]:
    dates = _get_motion_dates(raw_motion, motion_steps)

    presentation_date = dates.get("presentation_date", None)
    decision_date = dates.get("final_chamber_decision_date", None)

    return [
        MotionOrganization(
            motion_id=raw_motion.id,
            org_name="Cámara de Diputados",
            org_type="Cámara",
            presentation_date=as_date(presentation_date),
            decision_date=as_date(decision_date),
        )
    ]

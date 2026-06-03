import re
import json

from backend.database.raw_models import RawMotion, RawMotionDocument
from backend.process.schema import (
    Motion,
    MotionCongresistas,
    MotionStep,
    MotionDocument,
)

VOTE_PATTERN = re.compile(
    r"\bSI\s*\+{2,}.*?\bNO\s*-{2,}|\bNO\s*-{2,}.*?\bSI\s*\+{2,}",
    re.IGNORECASE | re.DOTALL,
)


def process_motion(raw_motion: RawMotion) -> tuple[Motion, list[MotionCongresistas]]:
    """
    Process a RawMotion instance into a Motion instance and a list of MotionCongresistas
    that maps all the congresistas that have a role in the Motion process

    Args:
        raw_motion (RawMotion): RawMotion instance that contains the scraped information from a motion

    Returns:
        Motion: instance that contains general information of the motion
        list[MotionCongresistas]: list of instances that relates congresistas to a Motion
    """
    # Obtaining dictionaries from the raw_motion columns
    general = json.loads(raw_motion.general)
    firmantes = json.loads(raw_motion.congresistas)

    # Extracting information from general dictionary
    id = raw_motion.id
    leg_period = general.get("desPerParAbrev")
    legislature = general.get("desLegis")
    presentation_date = general.get("fecPresentacion")
    motion_type = general.get("desTipoMocion")
    summary = general.get("sumilla")
    observations = general.get("observacion")
    complete_text = None  # TODO: Extract Motion Full Text
    status = general.get("desEstadoMocion")
    motion_approved = (
        general.get("desEstadoMocion") == "Publicado Diario Oficial  El Peruano"
    )

    # Extracting information from firmantes dictionary
    cong_list = []

    if firmantes:
        author_info = firmantes[0]
        author_name = author_info.get("nombre")
        author_web = author_info.get("pagWeb")

        for cong in firmantes:
            cong_list.append(
                MotionCongresistas(
                    motion_id=id,
                    nombre=cong.get("nombre"),
                    leg_period=leg_period,
                    role_type=cong.get("tipoFirmanteId"),
                    web_page=cong.get("pagWeb"),
                )
            )

    # Creating Motion instance
    motion = Motion(
        id=id,
        leg_period=leg_period,
        legislature=legislature,
        presentation_date=presentation_date,
        motion_type=motion_type,
        summary=summary,
        observations=observations,
        complete_text=complete_text,
        status=status,
        author_name=author_name,
        author_web=author_web,
        motion_approved=motion_approved,
    )

    return motion, cong_list


def process_motion_steps(raw_motion: RawMotion) -> list[MotionStep] | None:
    """
    Process a RawMotion instance into a list of MotionStep
    that maps all the steps that have happended during the motion processess

    Args:
        raw_motion (RawMotion): RawMotion instance that contains the scraped information from a motion

    Returns:
        list[MotionStep]: list of instances that contains all the steps related to a Motion
    """
    # Obtaining dictionaries from the raw_motion columns
    steps = json.loads(raw_motion.steps)

    if steps:
        final_steps = []
        vote_step_counter = 0

        for step in steps:
            # Extracting information from each step
            id = step.get("seguimientoId")
            date = step.get("fecSeguimiento")
            status = step.get("desEstadoMocion")
            details = step.get("detalle") or ""
            files = step.get("adjuntos") or []
            vote_step = any(
                vote_word in details.lower() for vote_word in ["votacion", "votación"]
            )
            vote_id = None

            file_ids = [
                file.get("seguimientoAdjuntoId")
                for file in files
                if file and file.get("seguimientoAdjuntoId") is not None
            ]

            if vote_step:
                vote_step_counter += 1
                vote_id = f"{raw_motion.id}_{vote_step_counter}"

            motion_step = MotionStep(
                id=id,
                motion_id=raw_motion.id,
                vote_step=vote_step,
                vote_id=vote_id,
                step_date=date,
                step_status=status,
                step_detail=details,
                step_files=file_ids,
            )

            final_steps.append(motion_step)

        return final_steps

    else:
        return None


def process_motion_document(raw_motion_document: RawMotionDocument) -> MotionDocument:
    """
    Process a RawMotionDocument into a MotionDocument

    Args:
        raw_motion_document (RawMotionDocument): RawMotionDocument instance

    Returns:
        MotionDocument: clean MotionDocument instance
    """
    return MotionDocument(
        motion_id=raw_motion_document.motion_id,
        step_id=raw_motion_document.seguimiento_id,
        archivo_id=raw_motion_document.archivo_id,
        url=raw_motion_document.url,
        text=raw_motion_document.text,
        vote_doc=bool(VOTE_PATTERN.search(raw_motion_document.text)),
    )

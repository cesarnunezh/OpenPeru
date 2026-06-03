import re
import json

from backend.database.raw_models import RawBill, RawBillDocument
from backend.process.schema import (
    Bill,
    BillCommittees,
    BillCongresistas,
    BillStep,
    BillDocument,
)

VOTE_PATTERN = re.compile(
    r"\bSI\s*\+{2,}.*?\bNO\s*-{2,}|\bNO\s*-{2,}.*?\bSI\s*\+{2,}",
    re.IGNORECASE | re.DOTALL,
)


def process_bill(raw_bill: RawBill) -> tuple[Bill, list[BillCongresistas]]:
    """
    Process a RawBill instance into a Bill instance and a list of BillCongresistas
    that maps all the congresistas that have a role in the Bill process

    Args:
        raw_bill (RawBill): RawBill instance that contains the scraped information from a bill

    Returns:
        Bill: instance that contains general information of the bill
        list[BillCongresistas]: list of instances that relates congresistas to a Bill
    """
    # Obtaining dictionaries from the raw_bill columns
    general = json.loads(raw_bill.general)
    firmantes = json.loads(raw_bill.congresistas)

    # Extracting information from general dictionary
    id = raw_bill.id
    leg_period = general.get("desPerParAbrev")
    legislature = general.get("desLegis")
    presentation_date = general.get("fecPresentacion")
    title = general.get("titulo")
    summary = general.get("sumilla")
    observations = general.get("observaciones")
    complete_text = None  # TODO: Extract Bill Full Text
    status = general.get("desEstado")
    proponent = general.get("desProponente")
    bill_approved = (
        general.get("desEstado") == "Publicada en el Diario Oficial El Peruano"
    )

    # Extracting information from firmantes dictionary
    cong_list = []

    if firmantes:
        author_info = firmantes[0]
        author_name = author_info.get("nombre")
        author_web = author_info.get("pagWeb")

        for cong in firmantes:
            cong_list.append(
                BillCongresistas(
                    bill_id=id,
                    nombre=cong.get("nombre"),
                    leg_period=leg_period,
                    role_type=cong.get("tipoFirmanteId"),
                    web_page=cong.get("pagWeb"),
                )
            )
    else:
        author_name = None
        author_web = None

    # Creating Bill instance
    bill = Bill(
        id=id,
        leg_period=leg_period,
        legislature=legislature,
        presentation_date=presentation_date,
        title=title,
        summary=summary,
        observations=observations,
        complete_text=complete_text,
        status=status,
        proponent=proponent,
        author_name=author_name,
        author_web=author_web,
        bill_approved=bill_approved,
    )

    return bill, cong_list


def process_bill_steps(raw_bill: RawBill) -> list[BillStep] | None:
    """
    Process a RawBill instance into a list of BillStep
    that maps all the steps that have happended during the bill processess

    Args:
        raw_bill (RawBill): RawBill instance that contains the scraped information from a bill

    Returns:
        list[BillStep]: list of instances that contains all the steps related to a Bill
    """
    # Obtaining dictionaries from the raw_bill columns
    steps = json.loads(raw_bill.steps)

    if steps:
        final_steps = []
        vote_step_counter = 0

        for step in steps:
            # Extracting information from each step
            id = step.get("seguimientoPleyId")
            date = step.get("fecha")
            status = step.get("desEstado")
            details = step.get("detalle") or ""
            vote_step = any(
                vote_word in details.lower() for vote_word in ["votacion", "votación"]
            )
            vote_id = None

            files = step.get("archivos") or []
            file_ids = [
                file.get("proyectoArchivoId")
                for file in files
                if file and file.get("proyectoArchivoId") is not None
            ]

            if vote_step:
                vote_step_counter += 1
                vote_id = f"{raw_bill.id}_{vote_step_counter}"

            bill_step = BillStep(
                id=id,
                bill_id=raw_bill.id,
                vote_step=vote_step,
                vote_id=vote_id,
                step_date=date,
                step_status=status,
                step_detail=details,
                step_files=file_ids,
            )

            final_steps.append(bill_step)

        return final_steps

    else:
        return None


def process_bill_document(raw_bill_document: RawBillDocument) -> BillDocument:
    """
    Process a RawBillDocument into a BillDocument

    Args:
        raw_bill_document (RawBillDocument): RawBillDocument instance

    Returns:
        BillDocument: clean BillDocument instance
    """
    return BillDocument(
        bill_id=raw_bill_document.bill_id,
        step_id=raw_bill_document.seguimiento_id,
        archivo_id=raw_bill_document.archivo_id,
        url=raw_bill_document.url,
        text=raw_bill_document.text,
        vote_doc=bool(VOTE_PATTERN.search(raw_bill_document.text)),
    )


def get_committees(raw_bill: RawBill) -> list[BillCommittees] | None:
    """
    Process a RawBill instance into a list of BillCommittees
    that maps all the Committees that are related to the bill

    Args:
        raw_bill (RawBill): RawBill instance that contains the scraped information from a bill

    Returns:
        list[BillCommittees]: list of instances that contains all the committees related to a Bill
    """
    data = json.loads(raw_bill.committees)

    if data:
        committees = []

        for committee in data:
            committees.append(
                BillCommittees(
                    bill_id=raw_bill.id, committee_name=committee.get("nombre")
                )
            )
        return committees
    else:
        return None

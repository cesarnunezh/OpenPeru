import json
from datetime import date, datetime
from backend import TypeBillStep
from backend.core.parsers import classify_des_estado
from backend.database.raw_models import RawBill, RawBillPage
from backend.process.schema import (
    Bill,
    BillOrganization,
    BillCongresistas,
    BillStep,
    BillText,
)
from backend.process.billtext import extract_bill_body
from backend.process.utils import create_vote_ids, as_date, get_sentence_case


def process_bill_text(bill_pages: list[RawBillPage], version_id: int) -> BillText:
    if not bill_pages:
        raise ValueError("No raw pages provided for bill text extraction")
    ocr_models = {page.ocr_model for page in bill_pages}
    if len(ocr_models) > 1:
        raise ValueError(
            f"Bill pages mix OCR models {sorted(ocr_models)}; expected a single model"
        )
    elif "chandra2" not in ocr_models:
        raise ValueError(
            "Bill text currently only allows chandra 2 OCR extraction. Try again later."
        )
    ordered_pages = sorted(bill_pages, key=lambda page: page.page_num)
    first_page = ordered_pages[0]
    final_text = extract_bill_body("\n".join(page.text for page in ordered_pages))

    if final_text is None:
        raise ValueError("Bill body could not be extracted from raw pages")
    return BillText(
        bill_id=first_page.bill_id,
        step_id=int(first_page.step_id),
        file_id=int(first_page.file_id),
        version_id=version_id,
        text=final_text,
    )


def process_bill(
    raw_bill: RawBill,
) -> tuple[Bill, list[BillCongresistas], list[BillStep]]:
    """
    Process a RawBill instance into a Bill instance and a list of BillCongresistas
    that maps all the congresistas that have a role in the Bill process

    Args:
        raw_bill (RawBill): RawBill instance that contains the scraped information from a bill

    Returns:
        Bill: instance that contains general information of the bill
        list[BillCongresistas]: list of instances that relates congresistas to a Bill
        list[BillStep]: list of instances that contains BillStep
    """
    # Obtaining dictionaries from the raw_bill columns
    general = json.loads(raw_bill.general or "{}")
    firmantes = json.loads(raw_bill.congresistas or "[]")

    # Extracting information from general dictionary
    bill_id = raw_bill.id
    title = get_sentence_case(general.get("titulo"))
    summary_congreso = get_sentence_case(general.get("sumilla"))
    observations = get_sentence_case(general.get("observaciones"))
    status = classify_des_estado(general.get("desEstado"))
    proponent = general.get("desProponente")
    bancada_name = general.get("desGpar")

    # Extracting information from firmantes dictionary
    cong_list = []

    if firmantes:
        author_info = firmantes[0]
        author_name = author_info.get("nombre")
        author_web = author_info.get("pagWeb")

        for cong in firmantes:
            cong_list.append(
                BillCongresistas(
                    bill_id=bill_id,
                    nombre=cong.get("nombre"),
                    role_type=cong.get("tipoFirmanteId"),
                    web_page=cong.get("pagWeb"),
                )
            )
    else:
        author_name = None
        author_web = None

    bill_steps = process_bill_steps(raw_bill)
    bill_approved = is_bill_approved(bill_steps, status)
    summary_oc = ""

    # Creating Bill instance
    bill = Bill(
        id=bill_id,
        title=title,
        summary_congreso=summary_congreso,
        observations=observations,
        status=status,
        proponent=proponent,
        author_name=author_name,
        author_web=author_web,
        bancada_name=bancada_name,
        bill_approved=bill_approved,
        summary_oc=summary_oc,
    )

    return bill, cong_list, bill_steps


def is_bill_approved(steps: list[BillStep], status: TypeBillStep | None = None) -> bool:
    if steps:
        return any([step.step_type == TypeBillStep.PUBLICADO for step in steps])
    return status == TypeBillStep.PUBLICADO


def process_bill_steps(raw_bill: RawBill) -> list[BillStep] | None:
    """
    Process a RawBill instance into a list of BillStep
    that maps all the steps that have happended during the bill processess

    Args:
        raw_bill (RawBill): RawBill instance that contains the scraped information from a bill

    Returns:
        list[BillStep]: list of instances that contains all the steps related to a Bill
    """
    steps = json.loads(raw_bill.steps or "[]")

    if steps:
        final_steps = []

        for step in steps:
            # Extracting information from each step
            step_id = step.get("seguimientoPleyId")
            date = datetime.fromisoformat(step.get("fecha")).date()
            details = step.get("detalle") or ""
            step_type = classify_des_estado(step.get("desEstado"), details)
            vote_step = step_type == TypeBillStep.VOTACION
            step_committees = _parse_step_committees(step.get("desComisiones"))

            bill_step = BillStep(
                bill_id=raw_bill.id,
                step_id=step_id,
                step_type=step_type,
                vote_step=vote_step,
                vote_event_id=None,
                step_date=date,
                step_detail=details,
                step_committees=step_committees,
            )

            final_steps.append(bill_step)

        return create_vote_ids(final_steps)

    else:
        return []


def _parse_step_committees(raw_committees) -> list[str]:
    if raw_committees is None:
        return []

    if isinstance(raw_committees, list):
        return [str(item).strip() for item in raw_committees if str(item).strip()]

    if isinstance(raw_committees, str):
        value = raw_committees.strip()
        if not value:
            return []

        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(";") if item.strip()]

        return _parse_step_committees(decoded)

    return []


def _get_committee_dates(
    bill_steps: list[BillStep],
) -> dict[str, dict[str, list | date]]:
    committee_dates: dict[str, dict[str, list | date]] = {}

    sorted_steps = sorted(bill_steps, key=lambda step: step.step_date)

    for step in sorted_steps:
        committees = getattr(step, "step_committees", [])

        if not committees:
            continue

        for committee_name in committees:
            committee = committee_dates.setdefault(
                committee_name,
                {
                    "assignment_dates": [],
                    "decision_dates": [],
                    "first_assignment_date": None,
                    "last_decision_date": None,
                },
            )

            if step.step_type == TypeBillStep.EN_COMISION:
                committee["assignment_dates"].append(step.step_date)

                if committee["first_assignment_date"] is None:
                    committee["first_assignment_date"] = step.step_date

            elif step.step_type in {
                TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
                TypeBillStep.EXONERACION_DE_DICTAMEN,
            }:
                committee["decision_dates"].append(step.step_date)
                committee["last_decision_date"] = step.step_date

    return committee_dates


def _get_bills_dates(bill_steps: list[BillStep]) -> dict[str, list | date]:
    """
    Obtain important dates from BillSteps.

    Tracks:
        presentation date
        committee rounds
        plenary agenda dates
        plenary debate dates
        plenary vote dates
        final plenary decision date
    """
    final_dict: dict[str, list | date] = {
        "presentation_date": None,
        "committee_rounds": [],
        "plenary_agenda_dates": [],
        "plenary_debate_dates": [],
        "permanent_commission_agenda_dates": [],
        "permanent_commission_debate_dates": [],
        "plenary_votes": [],
        "final_plenary_decision_date": None,
    }

    current_committee_round: dict[str, date | None] | None = None

    sorted_steps = sorted(bill_steps, key=lambda step: step.step_date)

    for step in sorted_steps:
        match step.step_type:
            case TypeBillStep.PRESENTADO:
                final_dict["presentation_date"] = step.step_date

            case TypeBillStep.EN_COMISION:
                current_committee_round = {
                    "committee_assignment_date": step.step_date,
                    "committee_decision_date": None,
                }
                final_dict["committee_rounds"].append(current_committee_round)

            case (
                TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION
                | TypeBillStep.EXONERACION_DE_DICTAMEN
            ):
                if current_committee_round is None:
                    current_committee_round = {
                        "committee_assignment_date": None,
                        "committee_decision_date": None,
                    }
                    final_dict["committee_rounds"].append(current_committee_round)

                current_committee_round["committee_decision_date"] = step.step_date

            case TypeBillStep.AGENDA_DEL_PLENO:
                final_dict["plenary_agenda_dates"].append(step.step_date)

            case TypeBillStep.DEBATE_EN_EL_PLENO:
                final_dict["plenary_debate_dates"].append(step.step_date)

            case TypeBillStep.AGENDA_DE_LA_COMISION_PERMANENTE:
                final_dict["permanent_commission_agenda_dates"].append(step.step_date)

            case TypeBillStep.DEBATE_EN_LA_COMISION_PERMANENTE:
                final_dict["permanent_commission_debate_dates"].append(step.step_date)

            case TypeBillStep.VOTACION:
                vote = {
                    "vote_date": step.step_date,
                    "vote_event_id": step.vote_event_id,
                }

                final_dict["plenary_votes"].append(vote)
                final_dict["final_plenary_decision_date"] = step.step_date

    return final_dict


def process_bill_organizations(
    raw_bill: RawBill,
    bill_steps: list[BillStep],
) -> list[BillOrganization]:
    """
    Process a RawBill instance into a list of BillOrganization instances.

    This maps the bill to the committees and chamber involved in its legislative
    process.
    """
    list_orgs: list[BillOrganization] = []

    dates = _get_bills_dates(bill_steps)
    if dates.get("presentation_date") is None:
        general = json.loads(raw_bill.general or "{}")
        raw_presentation_date = general.get("fecPresentacion")
        if raw_presentation_date:
            dates["presentation_date"] = datetime.fromisoformat(
                raw_presentation_date
            ).date()

    committee_dates = _get_committee_dates(bill_steps)

    committee_names = {
        committee_name
        for step in bill_steps
        for committee_name in (step.step_committees or [])
        if committee_name
    }

    for committee_name in sorted(committee_names):
        date_info = committee_dates.get(committee_name, {})
        presentation_date = date_info.get("first_assignment_date")
        if presentation_date is None:
            continue

        list_orgs.append(
            BillOrganization(
                bill_id=raw_bill.id,
                org_name=committee_name,
                org_type="Comisión",
                presentation_date=as_date(presentation_date),
                decision_date=as_date(date_info.get("last_decision_date")),
            )
        )

    list_orgs.append(
        BillOrganization(
            bill_id=raw_bill.id,
            org_name="Cámara de Diputados",
            org_type="Cámara",
            presentation_date=as_date(dates.get("presentation_date")),
            decision_date=as_date(dates.get("final_plenary_decision_date")),
        )
    )

    return list_orgs

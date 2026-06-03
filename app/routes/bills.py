from hashlib import sha1
from datetime import date
from calendar import monthrange
from math import ceil
from types import SimpleNamespace
from datetime import datetime
import textwrap
from flask import (
    Blueprint,
    current_app,
    make_response,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session
from app.diff_render import RENDERER_VERSION, render_payload_html
from backend.database.crud.pipeline_bills import get_billtext_for_step
from backend.database.models import (
    Bill,
    BillDifference,
    BillStep,
    BillCongresistas,
    Congresista,
    BillOrganization,
    Ley,
    Membership,
    Organization,
    Vote,
    VoteCounts,
    VoteEvent,
)
from backend.core.enums import TypeOrganization, VoteOption
from .processed_session import SessionProcessed
from .utils import create_party_option, create_committee_option, latest_org_name
import json
import os
import sqlite3
from .generate_seats import generate_seats
from flask_babel import gettext as _

bills_bp = Blueprint("bills", __name__, template_folder="../templates")
DATE_YEAR_MIN = 1900

TOPIC_MAPPING = {
    "Inclusión Social y Personas con Discapacidad": [
        "Inclusión Social",
        "Discapacidad",
    ],
    "Defensa del Consumidor y Organismos Reguladores de los Servicios Públicos": [
        "Defensa del Consumidor",
        "Regulación y Competencia",
    ],
    "Relaciones Exteriores": ["Relaciones Exteriores"],
    "Defensa Nacional, Orden interno, Desarrollo alternativo y Lucha contra las Drogas": [
        "Defensa Nacional",
        "Orden Interno",
        "Desarrollo alternativo y Lucha contra las Drogas",
    ],
    "Presupuesto y Cuenta General de la República": ["Presupuesto"],
    "Pueblos Andinos, Amazónicos y Afroperuanos, Ambiente y Ecología": [
        "Pueblos Andinos, Amazónicos y Afroperuanos",
        "Ambiente y Ecología",
    ],
    "Mujer y Familia": ["Mujer y Familia"],
    "Transportes y Comunicaciones": ["Transportes y Comunicaciones"],
    "Energía y Minas": ["Energía y Minas"],
    "Educación, Juventud y Deporte": ["Educación, Juventud y Deporte"],
    "Descentralización, Regionalización, Gobiernos Locales y Modernización de la Gestión del Estado": [
        "Descentralización",
        "Modernización del Estado",
    ],
    "Fiscalización y Contraloría": ["Fiscalización y Contraloría"],
    "Constitución y Reglamento": ["Constitución y Reglamento"],
    "Justicia y Derechos Humanos": ["Justicia y Derechos Humanos"],
    "Ciencia, Innovación y Tecnología": ["Ciencia, Innovación y Tecnología"],
    "Trabajo y Seguridad Social": ["Trabajo y Seguridad Social"],
    "Salud y Población": ["Salud y Población"],
    "Cultura y Patrimonio Cultural": ["Cultura y Patrimonio Cultural"],
    "Vivienda y Construcción": ["Vivienda y Construcción"],
    "Agraria": ["Agraria"],
    "Producción, Micro y Pequeña Empresa y Cooperativas": [
        "Producción, Micro y Pequeña Empresa y Cooperativas"
    ],
    "Inteligencia": ["Inteligencia"],
    "Comercio Exterior y Turismo": ["Comercio Exterior y Turismo"],
    "Economía, Banca, Finanzas e Inteligencia Financiera": [
        "Economía",
        "Banca y Finanzas",
        "Inteligencia Financiera",
    ],
}


def get_author_with_party(
    db: Session,
    author_id: str | None,
) -> tuple[Congresista | None, str | None]:
    if not author_id:
        return None, None

    stmt = (
        select(Congresista, Organization.org_name)
        .join(Membership, Membership.person_id == Congresista.id)
        .join(Organization, Organization.org_id == Membership.org_id)
        .where(
            Congresista.id == author_id,
            Membership.org_type == "Partido",
        )
    )

    result = db.execute(stmt).first()

    if result is None:
        return None, None

    author, org_name = result
    return author, org_name


def load_voter_bancada_dict():
    """Load voter-bancada mapping from DB into dict"""
    db_path = os.path.join(
        os.path.dirname(__file__), "..", "mock_data", "example_voter_bancada.db"
    )
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT voter, bancada FROM voter_bancada")
    voter_bancada_map = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return voter_bancada_map


def _parse_int_arg(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_date_picker(prefix, args, today):
    """
    Safely normalizes form date inputs and prepares both the selected date (if valid)
    and the select-box option lists for the template.
    """
    raw_year = args.get(f"{prefix}_year")
    raw_month = args.get(f"{prefix}_month")
    raw_day = args.get(f"{prefix}_day")

    provided = any(value not in (None, "") for value in (raw_year, raw_month, raw_day))
    year = _parse_int_arg(raw_year, None)
    month = _parse_int_arg(raw_month, None)
    day = _parse_int_arg(raw_day, None)

    if year is not None:
        year = max(DATE_YEAR_MIN, min(year, today.year))
    if month is not None:
        month = max(1, min(month, 12))

    selected_date = None
    day_options = []
    if year is not None and month is not None:
        last_day = monthrange(year, month)[1]
        day_options = list(range(1, last_day + 1))
        if day is not None:
            day = max(1, min(day, last_day))
            selected_date = date(year, month, day)

    return {
        "provided": provided,
        "selected_date": selected_date,
        "year_value": year,
        "month_value": month,
        "day_value": day,
        "year_options": list(range(today.year, DATE_YEAR_MIN - 1, -1)),
        "month_options": list(range(1, 13)),
        "day_options": day_options,
    }


def get_topics(db, bill_id):
    committees = db.scalars(
        select(Organization.org_name)
        .join(
            BillOrganization,
            BillOrganization.org_id == Organization.org_id,
        )
        .where(
            Organization.org_type == "Comisión",
            Organization.org_subtype == "Comisión Ordinaria",
            BillOrganization.bill_id == bill_id,
        )
        .distinct()
        .order_by(Organization.org_name)
    ).all()

    topics = []
    for comm in committees:
        topics.extend(TOPIC_MAPPING[comm])

    return topics


def _vote_option_key(option) -> str:
    value = getattr(option, "value", option)
    if value == VoteOption.SI.value:
        return "yes"
    if value == VoteOption.NO.value:
        return "no"
    if value == VoteOption.ABSTENCION.value:
        return "abstain"
    return "others"


def _vote_option_label(option) -> str:
    value = getattr(option, "value", option)
    labels = {
        VoteOption.SI.value: _("In favor"),
        VoteOption.NO.value: _("Against"),
        VoteOption.ABSTENCION.value: _("Abstain"),
    }
    return labels.get(value, _("Others"))


def _build_vote_summary_counts(vote_event: VoteEvent) -> dict[str, int]:
    vote_counts = {
        "yes": vote_event.votes_in_favor,
        "no": vote_event.votes_against,
        "abstain": vote_event.votes_abstention,
    }
    counted_votes = sum(vote_counts.values())
    vote_counts["others"] = max(130 - counted_votes, 0)
    return vote_counts


def _wrap_bancada_label(name: str, max_width: int = 24) -> list[str]:
    """
    Wrap lines when the bancada name is too long.
    """
    lines = textwrap.wrap(
        name,
        width=max_width,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return lines or [name]


def _build_bancada_bars(bancada_votes):
    bar_x = 220
    bar_max_width = 520
    label_line_height = 13
    row_gap = 12

    sorted_rows = sorted(
        bancada_votes.items(),
        key=lambda item: (-item[1]["total"], item[0]),
    )

    # Match the width to the bancada with the largest number of items.
    max_total = max((counts["total"] for _, counts in sorted_rows), default=0)
    width_scale = bar_max_width / max_total if max_total else 0

    # Set the x and y coordinates of the bars for each yes, no, and abstain option in each bancada.
    rows = []
    current_y = 20
    for index, (name, counts) in enumerate(sorted_rows):
        label_lines = _wrap_bancada_label(name)
        label_height = max(label_line_height, len(label_lines) * label_line_height)
        bar_y = current_y + label_height + 18

        segments = []
        offset = 0
        for key in ("yes", "no", "abstain"):
            width = counts[key] * width_scale
            if width <= 0:
                continue
            segments.append(
                {
                    "key": key,
                    "x": bar_x + offset,
                    "width": width,
                }
            )
            offset += width

        total_width = max(offset, 2)
        rows.append(
            {
                "name": name,
                "label_lines": label_lines,
                "yes": counts["yes"],
                "no": counts["no"],
                "abstain": counts["abstain"],
                "total": counts["total"],
                "bar_y": bar_y,
                "bar_x": bar_x,
                "total_x": bar_x + total_width + 10,
                "segments": segments,
            }
        )
        current_y += label_height + 34 + row_gap

    chart_height = max(10, current_y + 10)
    return rows, chart_height


def _build_vote_bancada_rows(db: Session, vote_event_id: str):
    """
    Extract the voting results for each bancada from the database and organize them into a
    dictionary grouped by option.
    """
    bancada_votes: dict[str, dict[str, int]] = {}

    rows = db.execute(
        select(
            VoteCounts.bancada_id,
            Organization.org_name,
            VoteCounts.option,
            VoteCounts.count,
        )
        .join(Organization, Organization.org_id == VoteCounts.bancada_id)
        .where(VoteCounts.vote_event_id == vote_event_id)
        .order_by(Organization.org_name.asc())
    ).all()

    for bancada_id, bancada_name, option, count in rows:
        bucket = bancada_votes.setdefault(
            bancada_name,
            {"yes": 0, "no": 0, "abstain": 0, "total": 0},
        )
        option_key = _vote_option_key(option)
        if option_key in bucket:
            bucket[option_key] += count
            bucket["total"] += count

    return _build_bancada_bars(bancada_votes)


def _build_vote_rows(db: Session, vote_event_id: str):
    vote_rows = []

    rows = db.execute(
        select(Vote, Congresista)
        .join(Congresista, Congresista.id == Vote.voter_id)
        .where(Vote.vote_event_id == vote_event_id)
        .order_by(Congresista.full_name.asc())
    ).all()

    for vote, congresista in rows:
        vote_rows.append(
            SimpleNamespace(
                id=congresista.id,
                full_name=congresista.full_name,
                party_name=latest_org_name(db, congresista.id, TypeOrganization.PARTY),
                vote_label=_vote_option_label(vote.option),
                vote_key=_vote_option_key(vote.option),
            )
        )

    return vote_rows


@bills_bp.route("/bills")
def index():
    title_q = request.args.get("title_q", "").strip()
    author_q = request.args.get("author_q", "").strip()
    author_party_q = request.args.get("author_party_q", "").strip()
    status = request.args.get("status", "all").strip()
    bill_id_q = request.args.get("bill_id_q", "").strip()
    law_id_q = request.args.get("law_id_q", "").strip()
    current_step_q = request.args.get("current_step_q", "").strip()
    organization_name_q = request.args.get("organization_name_q", "").strip()
    page = request.args.get("page", 1, type=int)
    page = page if page and page > 0 else 1
    per_page = 50
    max_search_results = 500
    _allowed_status = {"all", "approved", "not-approved"}
    if status not in _allowed_status:
        status = "all"
    # Add search conditions to the filters and build the query.
    filters = []
    # Set author_display so that the author name or query is correctly shown in the
    # search conditions, regardless of whether the input is an ID or a person's name.
    author_display = None
    author_id_query = author_q.isdigit()
    author_id_int = None
    today = date.today()
    presentation_date_from_picker = _build_date_picker(
        "presentation_date_from", request.args, today
    )
    presentation_date_to_picker = _build_date_picker(
        "presentation_date_to", request.args, today
    )
    presentation_date_from = presentation_date_from_picker["selected_date"]
    presentation_date_to = presentation_date_to_picker["selected_date"]
    search_requested = any(
        [
            title_q,
            author_q,
            author_party_q,
            bill_id_q,
            law_id_q,
            current_step_q,
            presentation_date_from is not None,
            presentation_date_to is not None,
            organization_name_q,
        ]
    )

    search_params = dict(
        title_q=title_q,
        author_q=author_q,
        author_party_q=author_party_q,
        status=status,
        bill_id_q=bill_id_q,
        law_id_q=law_id_q,
        current_step_q=current_step_q,
        organization_name_q=organization_name_q,
    )
    if presentation_date_from_picker["provided"]:
        search_params.update(
            {
                key: value
                for key, value in {
                    "presentation_date_from_year": presentation_date_from_picker[
                        "year_value"
                    ],
                    "presentation_date_from_month": presentation_date_from_picker[
                        "month_value"
                    ],
                    "presentation_date_from_day": presentation_date_from_picker[
                        "day_value"
                    ],
                }.items()
                if value is not None
            }
        )
    if presentation_date_to_picker["provided"]:
        search_params.update(
            {
                key: value
                for key, value in {
                    "presentation_date_to_year": presentation_date_to_picker[
                        "year_value"
                    ],
                    "presentation_date_to_month": presentation_date_to_picker[
                        "month_value"
                    ],
                    "presentation_date_to_day": presentation_date_to_picker[
                        "day_value"
                    ],
                }.items()
                if value is not None
            }
        )

    if title_q:
        filters.append(
            func.unaccent(func.lower(Bill.title)).like(
                func.unaccent(func.lower(f"%{title_q}%"))
            )
        )

    if bill_id_q:
        filters.append(Bill.id.ilike(f"%{bill_id_q}%"))

    if author_q:
        # Since author_q may contain either an ID or a person's name, build the query
        # appropriately based on whether the input is an integer.
        if author_id_query:
            try:
                author_id_int = int(author_q)
            except ValueError:
                author_id_int = None

            if author_id_int is not None:
                filters.append(Bill.author_id == author_id_int)
        else:
            filters.append(
                func.unaccent(func.lower(Congresista.full_name)).like(
                    func.unaccent(func.lower(f"%{author_q}%"))
                )
            )

    if law_id_q:
        filters.append(
            select(Ley.id)
            .where(Ley.bill_id == Bill.id, Ley.id.ilike(f"%{law_id_q}%"))
            .exists()
        )

    if current_step_q:
        latest_step_type_expr = (
            select(BillStep.step_type)
            .where(BillStep.bill_id == Bill.id)
            .order_by(BillStep.step_date.desc(), BillStep.step_id.desc())
            .limit(1)
            .scalar_subquery()
        )
        filters.append(latest_step_type_expr == current_step_q)

    # Extract bills whose presentation dates fall between the from and to dates.
    if presentation_date_from or presentation_date_to:
        presentation_filters = [BillOrganization.bill_id == Bill.id]
        if presentation_date_from:
            presentation_filters.append(
                BillOrganization.presentation_date >= presentation_date_from
            )
        if presentation_date_to:
            presentation_filters.append(
                BillOrganization.presentation_date <= presentation_date_to
            )
        filters.append(
            select(BillOrganization.bill_id).where(*presentation_filters).exists()
        )

    if organization_name_q:
        filters.append(
            select(Organization.org_id)
            .join(BillOrganization, BillOrganization.org_id == Organization.org_id)
            .where(
                BillOrganization.bill_id == Bill.id,
                Organization.org_type == TypeOrganization.COMMITTEE,
                Organization.org_name == organization_name_q,
            )
            .exists()
        )

    if status == "approved":
        filters.append(Bill.bill_approved.is_(True))
    elif status == "not-approved":
        filters.append(Bill.bill_approved.is_(False))

    bills = []
    recent_bills = []
    total_count = 0
    total_count_display = None
    results_start = 0
    results_end = 0
    pagination_pages = []
    current_step_options = []
    author_party_options = []
    organization_name_options = []

    with SessionProcessed() as db:
        if author_id_int is not None:
            author_row = db.get(Congresista, author_id_int)
            author_display = author_row.full_name if author_row else None

        current_step_options = [
            step.value if hasattr(step, "value") else str(step)
            for step in db.execute(
                select(BillStep.step_type).distinct().order_by(BillStep.step_type)
            )
            .scalars()
            .all()
        ]
        # Create a list of dropdown options from the database.
        author_party_options = create_party_option(db)
        organization_name_options = create_committee_option(db)

        if search_requested:
            latest_bill_dates = (
                select(
                    BillOrganization.bill_id,
                    func.max(BillOrganization.presentation_date).label(
                        "latest_presentation_date"
                    ),
                )
                .group_by(BillOrganization.bill_id)
                .subquery()
            )

            stmt = (
                select(
                    Bill.id.label("id"),
                    Bill.title.label("title"),
                    Congresista.full_name.label("author_name"),
                    latest_bill_dates.c.latest_presentation_date.label(
                        "presentation_date"
                    ),
                )
                .join(Congresista, Bill.author_id == Congresista.id, isouter=True)
                .outerjoin(latest_bill_dates, latest_bill_dates.c.bill_id == Bill.id)
                .where(*filters)
            )

            # Limit the number of displayed results, create pagination, and display the results in fixed-size pages.
            count_stmt = select(func.count()).select_from(
                stmt.order_by(None).limit(max_search_results + 1).subquery()
            )
            total_count = db.execute(count_stmt).scalar_one()
            total_count_display = (
                f"{max_search_results}+"
                if total_count > max_search_results
                else str(total_count)
            )

            visible_total = min(total_count, max_search_results)
            total_pages = ceil(visible_total / per_page) if visible_total else 0
            if total_pages and page > total_pages:
                page = total_pages

            if total_pages:
                pagination_pages = [
                    SimpleNamespace(
                        number=page_number,
                        current=page_number == page,
                        url=url_for("bills.index", page=page_number, **search_params),
                    )
                    for page_number in range(1, total_pages + 1)
                ]

            result_stmt = (
                stmt.order_by(
                    latest_bill_dates.c.latest_presentation_date.desc(),
                    Bill.title.asc(),
                    Bill.id.asc(),
                )
                .offset((page - 1) * per_page)
                .limit(per_page)
            )

            rows = db.execute(result_stmt).mappings().all()
            if rows and author_q and not author_id_query:
                author_display = author_q
            if rows:
                results_start = (page - 1) * per_page + 1
                results_end = results_start + len(rows) - 1

            bills = [SimpleNamespace(**row) for row in rows]
        else:
            # Display the 10 bills with the most recent initial presentation dates by default.
            earliest_bill_dates = (
                select(
                    BillOrganization.bill_id,
                    func.min(BillOrganization.presentation_date).label(
                        "first_presentation_date"
                    ),
                )
                .group_by(BillOrganization.bill_id)
                .subquery()
            )

            recent_stmt = (
                select(
                    Bill.id.label("id"),
                    Bill.title.label("title"),
                    Congresista.full_name.label("author_name"),
                    earliest_bill_dates.c.first_presentation_date.label(
                        "presentation_date"
                    ),
                )
                .join(Congresista, Bill.author_id == Congresista.id, isouter=True)
                .join(earliest_bill_dates, earliest_bill_dates.c.bill_id == Bill.id)
                .order_by(
                    earliest_bill_dates.c.first_presentation_date.desc(),
                    Bill.title.asc(),
                    Bill.id.asc(),
                )
                .limit(10)
            )

            recent_rows = db.execute(recent_stmt).mappings().all()
            recent_bills = [SimpleNamespace(**row) for row in recent_rows]

    prev_page_url = None
    next_page_url = None
    if total_count_display is not None and pagination_pages:
        if page > 1:
            prev_page_url = url_for(
                "bills.index",
                page=page - 1,
                **search_params,
            )
        if page < len(pagination_pages):
            next_page_url = url_for(
                "bills.index",
                page=page + 1,
                **search_params,
            )

    return render_template(
        "bills/search.html",
        title_q=title_q,
        author_q=author_q,
        author_party_q=author_party_q,
        author_display=author_display,
        bill_id_q=bill_id_q,
        law_id_q=law_id_q,
        current_step_q=current_step_q,
        presentation_date_from=presentation_date_from,
        presentation_date_to=presentation_date_to,
        presentation_date_from_provided=presentation_date_from_picker["provided"],
        presentation_date_to_provided=presentation_date_to_picker["provided"],
        presentation_date_from_year=presentation_date_from_picker["year_value"],
        presentation_date_from_month=presentation_date_from_picker["month_value"],
        presentation_date_from_day=presentation_date_from_picker["day_value"],
        presentation_date_to_year=presentation_date_to_picker["year_value"],
        presentation_date_to_month=presentation_date_to_picker["month_value"],
        presentation_date_to_day=presentation_date_to_picker["day_value"],
        organization_name_q=organization_name_q,
        bills=bills,
        recent_bills=recent_bills,
        radio_status=status,
        page=page,
        per_page=per_page,
        total_count_display=total_count_display,
        results_start=results_start,
        results_end=results_end,
        pagination_pages=pagination_pages,
        prev_page_url=prev_page_url,
        next_page_url=next_page_url,
        current_step_options=current_step_options,
        author_party_options=author_party_options,
        presentation_date_from_year_options=presentation_date_from_picker[
            "year_options"
        ],
        presentation_date_from_month_options=presentation_date_from_picker[
            "month_options"
        ],
        presentation_date_from_day_options=presentation_date_from_picker["day_options"],
        presentation_date_to_year_options=presentation_date_to_picker["year_options"],
        presentation_date_to_month_options=presentation_date_to_picker["month_options"],
        presentation_date_to_day_options=presentation_date_to_picker["day_options"],
        organization_name_options=organization_name_options,
        search_requested=search_requested,
    )


@bills_bp.route("/bills/<bill_id>")
def bill_detail(bill_id):
    with SessionProcessed() as db:
        bill = db.get(Bill, bill_id)
        if not bill:
            return "Not Found", 404

        all_steps, latest_step = extract_steps(db, bill_id)

        # Only the types that actually carry comparable content; the others
        # (no_change, unavailable, first_version, missing row) shouldn't get
        # a "View changes" link.
        diff_types = dict(
            db.execute(
                select(BillDifference.step_id, BillDifference.difference_type).where(
                    BillDifference.bill_id == bill_id
                )
            ).all()
        )

        author_id = bill.author_id

        if not author_id:
            author_id = db.scalar(
                select(BillCongresistas.person_id)
                .where(
                    BillCongresistas.bill_id == bill_id,
                    BillCongresistas.role_type == "Autor",
                )
                .limit(1)
            )

        author, org_name = get_author_with_party(db, author_id)

        presentation_date = db.scalar(
            select(BillStep.step_date).where(
                BillStep.bill_id == bill_id, BillStep.step_type == "Presentado"
            )
        )

        # Approved and time since presentation/time for approval
        bill_status = _("Not approved")
        if bill.bill_approved:
            bill_status = _("Approved")

            stmt = (
                select(BillStep.step_date)
                .where(BillStep.bill_id == bill_id, BillStep.step_type == "Votación")
                .order_by(desc(BillStep.step_date))
                .limit(1)
            )
            approval_date = db.scalar(stmt)
            days_since_presentation = (approval_date - presentation_date).days
        else:
            today = datetime.now().date()
            days_since_presentation = (today - presentation_date).days

        # Committes -> Topics
        topics = get_topics(db, bill_id)

        return render_template(
            "bills/detail.html",
            bill=bill,
            latest_step=latest_step,
            all_steps=all_steps,
            diff_types=diff_types,
            bill_is_approved=bill.bill_approved,
            bill_status=bill_status,
            author=author,
            party_name=org_name,
            presentation_date=presentation_date,
            days_since_presentation=days_since_presentation,
            topics=topics,
        )


@bills_bp.route("/bills/<bill_id>/votes/<vote_event_id>")
def votes(bill_id, vote_event_id):
    with SessionProcessed() as db:
        bill = db.get(Bill, bill_id)
        if not bill:
            return "Not Found", 404

        vote_event = db.execute(
            select(VoteEvent).where(
                VoteEvent.vote_event_id == vote_event_id,
                VoteEvent.bill_id == bill_id,
            )
        ).scalar_one_or_none()

        if vote_event is None:
            return "Not Found", 404

        vote_step = db.execute(
            select(BillStep)
            .where(
                BillStep.bill_id == bill_id,
                BillStep.vote_event_id == vote_event_id,
            )
            .order_by(BillStep.step_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        vote_date = vote_step.step_date if vote_step else vote_event.event_date
        organization_name = db.scalar(
            select(Organization.org_name).where(
                Organization.org_id == vote_event.org_id
            )
        )

        # Generate all the information needed to visualize the vote page
        # (such as each member’s voting status and the coordinates for positioning
        # circles) in Python and send it to the HTML template.
        vote_counts = _build_vote_summary_counts(vote_event)
        vote_rows = _build_vote_rows(db, vote_event_id)
        seat_groups = {"yes": [], "no": [], "abstain": []}
        for vote_row in vote_rows:
            if vote_row.vote_key in seat_groups:
                seat_groups[vote_row.vote_key].append(vote_row.full_name)

        seats = generate_seats(
            vote_counts,
            seat_groups,
        )

        bancada_rows, bancada_chart_height = _build_vote_bancada_rows(db, vote_event_id)

        bill_status = _("Not approved")
        if bill.bill_approved:
            bill_status = _("Approved")

        presentation_date = db.scalar(
            select(BillStep.step_date).where(
                BillStep.bill_id == bill_id, BillStep.step_type == "Presentado"
            )
        )

        topics = get_topics(db, bill_id)

        return render_template(
            "bills/votes.html",
            bill=bill,
            vote_event=vote_event,
            vote_step=vote_step,
            vote_date=vote_date,
            organization_name=organization_name,
            vote_counts=vote_counts,
            seats=seats,
            bancada_rows=bancada_rows,
            bancada_chart_height=bancada_chart_height,
            bill_is_approved=bill.bill_approved,
            bill_status=bill_status,
            presentation_date=presentation_date,
            topics=topics,
            vote_rows=vote_rows,
        )


def extract_steps(db, bill_id):
    stmt = (
        select(BillStep)
        .where(BillStep.bill_id == bill_id)
        .order_by(BillStep.step_date.desc())
    )
    all_steps = db.execute(stmt).scalars().all()
    latest_step = all_steps[0] if all_steps else None

    return all_steps, latest_step


@bills_bp.route("/bills/<bill_id>/difference/<int:step_id>")
def bill_difference(bill_id, step_id):
    with SessionProcessed() as db:
        bill = db.get(Bill, bill_id)
        if not bill:
            return "Not Found", 404

        step = db.get(BillStep, (bill_id, step_id))
        if not step:
            return "Not Found", 404

        diff = db.get(BillDifference, (bill_id, step_id))

        new_bt = get_billtext_for_step(db, bill_id, step_id)
        new_text = new_bt.text if new_bt else None
        old_text = None
        prev_step = None
        if diff and diff.prev_step_id is not None:
            old_bt = get_billtext_for_step(db, bill_id, diff.prev_step_id)
            old_text = old_bt.text if old_bt else None
            prev_step = db.get(BillStep, (bill_id, diff.prev_step_id))

        # ETag covers every input the renderer (and the page) depends on so
        # any change forces a client refetch.
        content_hash = (
            sha1(diff.difference_content.encode("utf-8")).hexdigest()[:12]
            if diff and diff.difference_content
            else "none"
        )
        # No row means the diff stage hasn't reached this step yet — distinct
        # from ``unavailable``, which means we tried and the new text is
        # missing. The template's final ``else`` branch handles ``None``.
        difference_type = diff.difference_type if diff else None
        locale = session.get("lang") or request.args.get("lang") or "en"
        etag = (
            f"bd-{bill_id}-{step_id}-{locale}-{difference_type}-{content_hash}"
            f"-r{RENDERER_VERSION}"
        )

        if request.if_none_match.contains(etag):
            return "", 304

        # Both parse and render are guarded: a malformed row or a renderer
        # bug must not take the page down — the template falls back to the
        # "no difference data available" branch.
        text_html = None
        if diff and diff.difference_content:
            try:
                parsed = json.loads(diff.difference_content)
            except (ValueError, TypeError):
                current_app.logger.exception(
                    "Failed to parse difference_content for bill %s step %s",
                    bill_id,
                    step_id,
                )
                parsed = None
            if isinstance(parsed, dict):
                try:
                    text_html = render_payload_html(parsed)
                except Exception:
                    current_app.logger.exception(
                        "Renderer failed for bill %s step %s", bill_id, step_id
                    )
                    text_html = None

        resp = make_response(
            render_template(
                "bills/difference.html",
                bill=bill,
                step=step,
                prev_step=prev_step,
                difference_type=difference_type,
                old_version_text=old_text,
                new_version_text=new_text,
                text_html=text_html,
            )
        )
        resp.set_etag(etag)
        resp.headers["Cache-Control"] = (
            "public, max-age=300, stale-while-revalidate=86400"
        )
        return resp

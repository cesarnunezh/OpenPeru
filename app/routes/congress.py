from types import SimpleNamespace
from datetime import date
from flask import Blueprint, render_template, request
from sqlalchemy import func, or_, select
from backend.database.models import (
    Bill,
    ChamberMembership,
    BillOrganization,
    Congresista,
    Membership,
    Organization,
    TypeOrganization,
)


from .utils import (
    create_party_option,
    create_committee_option,
    create_region_option,
    latest_org_name,
)
from .processed_session import SessionProcessed

congress_bp = Blueprint("congress", __name__, template_folder="../templates")


# Get the main information of the Congressmember
def _congresista_view(db, congresista: Congresista) -> SimpleNamespace:
    party_name = latest_org_name(db, congresista.id, TypeOrganization.PARTY)
    chamber_membership = db.execute(
        select(ChamberMembership)
        .where(
            ChamberMembership.person_id == congresista.id,
            ChamberMembership.org_id == 1,
        )
        .order_by(ChamberMembership.end_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    return SimpleNamespace(
        id=congresista.id,
        full_name=congresista.full_name,
        first_name=congresista.first_name,
        last_name=congresista.last_name,
        photo_url=congresista.photo_url,
        website=congresista.website,
        party_name=party_name,
        dist_electoral=(
            chamber_membership.dist_electoral if chamber_membership else None
        ),
        condicion=(
            chamber_membership.condicion if chamber_membership else "Not available"
        ),
        votes_in_election=(
            chamber_membership.votes_in_election if chamber_membership else 0
        ),
    )


@congress_bp.route("/congress")
def index():
    name_q = request.args.get("name_q", "").strip()
    party_q = request.args.get("party_q", "").strip()
    region_q = request.args.get("region_q", "").strip()
    commission_q = request.args.get("commission_q", "").strip()

    congresistas = []
    filters = []
    party_options = []
    region_options = []
    committee_options = []

    if name_q:
        filters.append(
            func.unaccent(func.lower(Congresista.full_name)).like(
                func.unaccent(func.lower(f"%{name_q}%"))
            )
        )

    if party_q:
        filters.append(
            Congresista.id.in_(
                select(Membership.person_id)
                .join(Organization, Organization.org_id == Membership.org_id)
                .where(
                    Membership.org_type == TypeOrganization.PARTY,
                    Organization.org_name == party_q,
                )
            )
        )

    if region_q:
        filters.append(
            Congresista.id.in_(
                select(ChamberMembership.person_id)
                .where(ChamberMembership.dist_electoral == region_q)
                .distinct()
            )
        )

    if commission_q:
        filters.append(
            Congresista.id.in_(
                select(Membership.person_id)
                .join(Organization, Organization.org_id == Membership.org_id)
                .where(
                    Membership.org_type == TypeOrganization.COMMITTEE,
                    Organization.org_name == commission_q,
                )
            )
        )

    with SessionProcessed() as db:
        party_options = create_party_option(db)
        region_options = create_region_option(db)
        committee_options = create_committee_option(db)

        if filters:
            rows = db.execute(
                select(Congresista)
                .where(*filters)
                .order_by(Congresista.full_name.asc())
                .limit(50)
            ).scalars()
            congresistas = [_congresista_view(db, row) for row in rows]

    return render_template(
        "congress/search.html",
        name_q=name_q,
        party_q=party_q,
        region_q=region_q,
        commission_q=commission_q,
        congresistas=congresistas,
        party_options=party_options,
        region_options=region_options,
        committee_options=committee_options,
    )


@congress_bp.route("/congress/<congresista_id>")
def congress_detail(congresista_id):
    with SessionProcessed() as db:
        congresista_row = db.get(Congresista, int(congresista_id))

        if not congresista_row:
            return "Not Found", 404

        congresista = _congresista_view(db, congresista_row)

        # To avoid duplicated bills
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

        bills_authored = [
            SimpleNamespace(
                id=bill.id,
                title=bill.title,
            )
            for bill in db.execute(
                select(Bill)
                .join(latest_bill_dates, latest_bill_dates.c.bill_id == Bill.id)
                .where(Bill.author_id == congresista.id)
                .order_by(latest_bill_dates.c.latest_presentation_date.desc())
                .limit(5)
            ).scalars()
        ]

        bills_authored_count = db.execute(
            select(func.count())
            .select_from(Bill)
            .where(Bill.author_id == congresista.id)
        ).scalar_one()

        successful_bills_count = db.execute(
            select(func.count())
            .select_from(Bill)
            .where(
                Bill.author_id == congresista.id,
                Bill.bill_approved.is_(True),
            )
        ).scalar_one()

        memberships = (
            db.execute(
                select(
                    Membership.role,
                    Membership.start_date,
                    Membership.end_date,
                    Organization.org_name,
                    Organization.org_type,
                    Organization.org_subtype,
                )
                .join(Organization, Organization.org_id == Membership.org_id)
                .where(
                    Membership.person_id == congresista.id,
                    Membership.end_date >= date(2026, 7, 26),
                    func.lower(Membership.role) != "accesitario",
                    or_(
                        Membership.org_type == TypeOrganization.COMMITTEE,
                        Organization.org_type == TypeOrganization.COMMITTEE,
                    ),
                )
                .order_by(Membership.end_date.desc(), Membership.start_date.desc())
            )
            .mappings()
            .all()
        )

        profile_stats = {
            "assistance_rate": "45%",
            "bills_authored": bills_authored_count,
            "success_rate": f"{
                (
                    round(100 * (successful_bills_count / bills_authored_count), 1)
                    if bills_authored_count
                    else 0
                )
            } %",
            "successful_bills": successful_bills_count,
        }

        recent_votes = [
            {
                "position": "In favor",
                "bill": "Bill N 32014",
                "description": "Vote data is not available yet. This is placeholder content for the congressperson detail view.",
            },
            {
                "position": "Against",
                "bill": "Bill N 32074",
                "description": "Vote data is not available yet. This is placeholder content for the congressperson detail view.",
            },
        ]

        return render_template(
            "congress/congress_detail.html",
            congresista=congresista,
            memberships=memberships,
            bills_authored=bills_authored,
            profile_stats=profile_stats,
            recent_votes=recent_votes,
        )

from sqlalchemy import select

from backend.database.models import ChamberMembership, Membership, Organization
from backend.core.enums import TypeOrganization


def latest_org_name(db, person_id: int, org_type: TypeOrganization) -> str | None:
    return db.execute(
        select(Organization.org_name)
        .join(Membership, Membership.org_id == Organization.org_id)
        .where(
            Membership.person_id == person_id,
            Membership.org_type == org_type,
        )
        .order_by(Membership.end_date.desc(), Membership.start_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def create_party_option(db):
    return [
        party_name
        for party_name in db.execute(
            select(Organization.org_name)
            .join(Membership, Membership.org_id == Organization.org_id)
            .where(Membership.org_type == TypeOrganization.PARTY)
            .distinct()
            .order_by(Organization.org_name.asc())
        )
        .scalars()
        .all()
    ]


def create_committee_option(db):
    return [
        org_name
        for org_name in db.execute(
            select(Organization.org_name)
            .join(Membership, Membership.org_id == Organization.org_id)
            .where(Organization.org_type == TypeOrganization.COMMITTEE)
            .distinct()
            .order_by(Organization.org_name.asc())
        )
        .scalars()
        .all()
    ]


def create_region_option(db):
    return [
        dist_electoral
        for dist_electoral in db.execute(
            select(ChamberMembership.dist_electoral)
            .where(ChamberMembership.dist_electoral.is_not(None))
            .distinct()
            .order_by(ChamberMembership.dist_electoral.asc())
        )
        .scalars()
        .all()
    ]

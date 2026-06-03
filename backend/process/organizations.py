from backend.database.raw_models import RawCommittee, RawOrganization
from backend.process.schema import Organization, Membership
from backend.process.utils import split_and_sort_name
from backend.core.parsers import parse_comm_type

from backend import find_leg_period, normalize_membership_role

from lxml.html import fromstring


def process_chambers() -> list[Organization]:
    # TODO: replace with real links
    return [
        Organization(
            org_name="Cámara de Diputados",
            org_type="Cámara",
            org_subtype=None,
            org_link="www.congreso.gob.pe/diputados",
        ),
        Organization(
            org_name="Cámara de Senadores",
            org_type="Cámara",
            org_subtype=None,
            org_link="www.congreso.gob.pe/senadores",
        ),
    ]


def process_committee(raw_comm: RawCommittee) -> list[Organization]:
    final_lst = []
    html = fromstring(raw_comm.raw_html)

    raw_lst = html.xpath('//*[@class="congresistas"]/tbody/tr')

    for comm in raw_lst:
        name_elem, content = comm.getchildren()

        type_comm = (name_elem.text or "").strip()
        name_comm = content.text_content().strip()

        if type_comm and name_comm and type_comm != "Comisión":
            link = content.xpath(".//a/@href")
            link = link[0] if link else ""

            final_lst.append(
                Organization(
                    org_name=name_comm,
                    org_type="Comisión",
                    org_subtype=parse_comm_type(type_comm),
                    org_link=link,
                    # TODO: Update this when the new congress website address
                    # for different routes for committees in camara
                    parent_org_name="Cámara de Diputados",
                    parent_org_type="Cámara",
                )
            )

    return final_lst


def process_admin_org(
    raw_org: RawOrganization,
) -> tuple[Organization, list[Membership]]:
    org = Organization(
        org_name=raw_org.type_org,
        org_type="Administrativo",
        org_subtype=raw_org.type_org,
        org_link=raw_org.org_link or "",
        # TODO: Update this when the new congress website address
        # for different routes for committees in camara
        parent_org_name="Cámara de Diputados",
        parent_org_type="Cámara",
    )

    final_lst = []
    html = fromstring(raw_org.raw_html)
    current_leg_period = find_leg_period(raw_org.timestamp)

    raw_lst = html.xpath('//*[@class="congresistas"]/tbody/tr')

    for cong in raw_lst[1:]:
        _, name, web, _, cargo = cong.getchildren()
        website = web.getchildren()[0].get("href")
        full_name, _, _ = split_and_sort_name(name.text_content())
        text_cargo = cargo.text_content()

        if text_cargo == "" or text_cargo.strip() == "":
            continue

        final_lst.append(
            Membership(
                cong_name=full_name,
                org_name=org.org_name,
                org_type=org.org_type,
                leg_period=current_leg_period,
                role=normalize_membership_role(text_cargo),
                time_stamp=raw_org.timestamp,
                website=website,
            )
        )

    return org, final_lst


def process_org(raw_org: RawOrganization) -> Organization:
    org, _ = process_admin_org(raw_org)
    return org


def process_org_membership(
    raw_org: RawOrganization, org: Organization | None = None
) -> list[Membership]:
    parsed_org, memberships = process_admin_org(raw_org)
    if org is None:
        return memberships
    return [
        membership.model_copy(
            update={"org_name": org.org_name, "org_type": org.org_type}
        )
        for membership in memberships
        if parsed_org.org_name == org.org_name
    ]

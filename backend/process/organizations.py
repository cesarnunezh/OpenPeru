from backend.database.raw_models import RawCommittee, RawOrganization
from backend.process.schema import Organization, Membership
from backend.core.parsers import parse_comm_type

from backend import find_leg_period, normalize_membership_role

from lxml.html import fromstring
from datetime import datetime


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
                    leg_period=find_leg_period(raw_comm.legislative_year),
                    leg_year=str(raw_comm.legislative_year),
                    org_name=name_comm,
                    org_type="Comisión",
                    comm_type=parse_comm_type(type_comm),
                    org_link=link,
                )
            )

    return final_lst


def process_org(raw_org: RawOrganization) -> Organization:
    return Organization(
        leg_period=find_leg_period(raw_org.legislative_year),
        leg_year=str(raw_org.legislative_year),
        org_name=raw_org.type_org,
        org_type=raw_org.type_org,
        comm_type=None,
        org_link=raw_org.org_link or "",
    )


def process_org_membership(
    raw_org: RawOrganization, org: Organization
) -> list[Membership]:
    final_lst = []
    html = fromstring(raw_org.raw_html)

    raw_lst = html.xpath('//*[@class="congresistas"]/tbody/tr')

    for cong in raw_lst[1:]:
        _, name, web, _, cargo = cong.getchildren()

        year = int(org.leg_year)

        if not cargo.text or not cargo.text.strip():
            continue

        final_lst.append(
            Membership(
                role=normalize_membership_role(cargo.text),
                nombre=name.text_content(),
                web_page=web.text_content(),
                leg_period=org.leg_period,
                org_name=org.org_name,
                org_type=org.org_type,
                comm_type=org.comm_type,
                start_date=datetime(year, 7, 28, 0, 0, 0),
                end_date=datetime(year + 1, 7, 28, 0, 0, 0),
            )
        )

    return final_lst

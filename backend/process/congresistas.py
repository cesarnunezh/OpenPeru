from backend import normalize_membership_role
from backend.database.raw_models import RawCongresista
from backend.process.schema import Congresista, Membership

import json
from datetime import datetime, timezone
from lxml.html import fromstring


def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None


def process_profile_content(raw_cong: RawCongresista) -> Congresista:
    html = fromstring(raw_cong.profile_content)

    return Congresista(
        nombre=xpath2('//*[@class="nombres"]/span[2]', html),
        leg_period=raw_cong.leg_period,
        party_name=xpath2('//*[@class="grupo"]/span[2]', html),
        current_bancada=xpath2('//*[@class="bancada"]/span[2]', html),
        votes_in_election=int(
            xpath2('//*[@class="votacion"]/span[2]', html).replace(",", "")
        ),
        dist_electoral=xpath2('//*[@class="representa"]/span[2]', html),
        condicion=xpath2('//*[@class="condicion"]/span[2]', html),
        website=raw_cong.url,
        photo_url="https://www.congreso.gob.pe"
        + html.xpath('//*[@class="foto"]/img/@src')[0],
    )


def process_memberships(
    raw_cong: RawCongresista, cong: Congresista
) -> list[Membership]:
    lst_membership = json.loads(raw_cong.memberships_content).get("data", None)

    final_lst = []

    def to_datetime(value):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            # API sometimes returns milliseconds.
            ts = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        if isinstance(value, str) and value.isdigit():
            num = int(value)
            ts = num / 1000 if num > 10_000_000_000 else num
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        if isinstance(value, str):
            txt = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(txt).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    def map_org_fields(
        type_org: str | None, org_name: str | None
    ) -> tuple[str, str | None]:
        type_org = (type_org or "").strip()
        org_name = (org_name or "").strip()
        upper = org_name.upper()

        if org_name == "Subcomisión de Acusaciones Constitucionales":
            return "Subcomisión de Acusaciones Constitucionales", org_name
        if org_name == "Subcomisión de Control Político":
            return "Comisión", org_name
        if org_name == "Comisión de Ética Parlamentaria":
            return "Comisión", org_name
        if type_org:
            return "Comisión", type_org

        map_org = {
            "CONSEJO DIRECTIVO": "Consejo Directivo",
            "JUNTA DE PORTAVOCES": "Junta de Portavoces",
            "MESA DIRECTIVA": "Mesa Directiva",
            "COMISIÓN PERMANENTE": "Comisión Permanente",
            "COMISION PERMANENTE": "Comisión Permanente",
        }
        if upper in map_org:
            return map_org[upper], None
        return "Comisión", None

    for membership in lst_membership:
        type_org = membership.get("desOrgano")
        org_name = membership.get("desOrganoCongresista")

        try:
            cargo = normalize_membership_role(membership.get("desCargo"))
        except ValueError:
            continue

        start_date = to_datetime(membership.get("fechaInicio"))
        if start_date is None:
            continue
        end_date = to_datetime(membership.get("fechaFin"))
        if end_date and end_date < start_date:
            end_date = None

        org_type, comm_type = map_org_fields(type_org, org_name)
        final_lst.append(
            Membership(
                role=cargo,
                nombre=cong.nombre,
                web_page=cong.website,
                leg_period=cong.leg_period,
                org_name=(org_name or "").strip(),
                org_type=org_type,
                comm_type=comm_type,
                start_date=start_date,
                end_date=end_date,
            )
        )

    return final_lst

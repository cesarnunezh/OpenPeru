from backend import normalize_membership_role
from backend.database.raw_models import RawCongresista
from backend.process.schema import Congresista, Membership, Organization
from backend.process.utils import gen_congresistas_df, to_datetime
from backend.database.session import get_db

import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from lxml.html import fromstring, HtmlElement


def get_cong_data(json_path: Path) -> dict[str, dict[str, str]]:
    """
    Load and process congressmembers data from a JSON file.

    If the JSON file does not exist, the function generates it using the
    current database session. It then reads the JSON data, processes each
    congressperson record, and returns a dictionary indexed by website URL.

    Args:
        json_path (Path): Path to the JSON file containing raw congressperson
            data.

    Returns:
        dict[str, dict[str, str]]: Dictionary where each key is a congressperson
        website URL and each value is the processed congressperson data.
    """
    if not json_path.exists():
        gen_congresistas_df(next(get_db()), True)

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    final_dict = dict()
    for cong in data:
        data_cong = _process_cong_data(cong)
        final_dict[data_cong["website"]] = data_cong

    return final_dict


def _process_cong_data(cong_dict: dict[str, str | int]) -> dict[str, str]:
    """
    Normalize a raw congressperson dictionary into a standard schema.

    The function parses the full name from the raw "nombre" field, builds a
    normalized full name, maps the gender code, its full Spanish label, and
    fixes a known website URL error for Hernando Guerra García.

    Args:
        cong_dict (dict[str, str | int]): Raw congressperson data containing
            fields such as "nombre", "dni", "sexo", and "pagWeb".

    Returns:
        dict[str, str]: Processed congressperson data with first name, last
        name, full name, DNI (Documento Nacional de Identidad), gender, and website.
    """
    last_name, first_name = [sub.strip() for sub in cong_dict["nombre"].split(",")]
    full_name = f"{first_name} {last_name}"

    if cong_dict["dni"] == "07202572":
        # This is due to an error in the website, where it points to HernandoGarcia
        # which it doesn't exist
        website = "https://www3.congreso.gob.pe/congresistas2021/HernandoGuerraGarcia/"
    else:
        website = cong_dict["pagWeb"]

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "dni": str(cong_dict["dni"]),
        "gender": "Masculino" if cong_dict["sexo"] == "M" else "Femenino",
        "website": str(website),
    }


def xpath2(xpath_query: str, parse: HtmlElement) -> str | None:
    """
    Extract the text from the first element matching an XPath query.

    The function evaluates the XPath query against the parsed HTML element and
    returns the text content of the first match. If no elements match the query,
    it returns None.

    Args:
        xpath_query (str): XPath expression used to search the HTML tree.
        parse (HtmlElement): Parsed HTML element where the XPath query is applied.

    Returns:
        str | None: Text from the first matching element, or None if no match is found.
    """
    result = parse.xpath(xpath_query)
    return result[0].text if result else None


def process_profile_content(
    raw_cong: RawCongresista, dict_cong_data: dict[str, dict]
) -> tuple[Congresista, list[Organization], list[Membership]]:
    """
    Process raw congressperson profile HTML into a Congresista schema.

    The function parses the congressperson profile page, extracts the photo URL,
    and tries to enrich the profile using preprocessed congressperson data indexed
    by website. For the 2021 to 2026 legislative period, it uses the external
    processed data when available. If no matching data is found, it falls back to
    extracting the congressperson name directly from the HTML profile content.

    Args:
        raw_cong (RawCongresista): Raw congressperson record containing profile
            HTML, website, and legislative period.
        dict_cong_data (dict[str, dict]): Dictionary of processed congressperson
            data indexed by website URL.

    Returns:
        Congresista: Processed congressperson schema with available profile
        information.
    """
    html = fromstring(raw_cong.profile_content)
    website = raw_cong.website
    photo_src = html.xpath('//*[@class="foto"]/img/@src')[0]
    photo_url = urljoin(website, photo_src)
    data_cong = dict_cong_data.get(website)

    party = Organization(
        org_name=xpath2('//*[@class="grupo"]/span[2]', html),
        org_type="Partido",
    )

    if data_cong and raw_cong.leg_period == "Parlamentario 2021 - 2026":
        cong = Congresista(
            full_name=data_cong.get("full_name"),
            first_name=data_cong.get("first_name"),
            last_name=data_cong.get("last_name"),
            dni=data_cong.get("dni"),
            gender=data_cong.get("gender"),
            photo_url=photo_url,
            website=data_cong.get("website"),
        )
    else:
        cong = Congresista(
            full_name=xpath2('//*[@class="nombres"]/span[2]', html),
            photo_url=photo_url,
            website=raw_cong.website,
        )

    votes_text = xpath2('//*[@class="votacion"]/span[2]', html) or "0"
    party_mem = Membership(
        cong_name=cong.full_name,
        org_name=party.org_name,
        org_type=party.org_type,
        leg_period=raw_cong.leg_period,
        role=normalize_membership_role("Miembro"),
        time_stamp=getattr(raw_cong, "timestamp", datetime.now()),
    )

    # TODO: Update when the webpage divides diputados and senadores
    chamber_mem = Membership(
        cong_name=cong.full_name,
        org_name="Cámara de Diputados",
        org_type="Cámara",
        leg_period=raw_cong.leg_period,
        role=normalize_membership_role("Diputado"),
        time_stamp=getattr(raw_cong, "timestamp", datetime.now()),
        condicion=xpath2('//*[@class="condicion"]/span[2]', html),
        votes_in_election=int(votes_text.replace(",", "")),
        dist_electoral=xpath2('//*[@class="representa"]/span[2]', html),
    )

    chamber = Organization(
        org_name="Cámara de Diputados",
        org_type="Cámara",
        org_link="www.congreso.gob.pe/diputados",
    )

    return cong, [party, chamber], [party_mem, chamber_mem]


def map_org_fields(type_org: str | None, org_name: str | None) -> str:
    type_org = (type_org or "").strip()
    org_name = (org_name or "").strip()
    upper = org_name.upper()

    map_org = {
        "CONSEJO DIRECTIVO": "Consejo Directivo",
        "JUNTA DE PORTAVOCES": "Junta de Portavoces",
        "MESA DIRECTIVA": "Mesa Directiva",
        "COMISIÓN PERMANENTE": "Comisión Permanente",
        "COMISION PERMANENTE": "Comisión Permanente",
    }
    if upper in map_org:
        return "Administrativo"
    return "Comisión"


def process_cong_memberships(
    raw_cong: RawCongresista, cong: Congresista
) -> list[Membership]:
    lst_membership = json.loads(raw_cong.memberships_content).get("data", None)

    final_lst = []

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

        org_type = map_org_fields(type_org, org_name)
        final_lst.append(
            Membership(
                cong_name=getattr(cong, "full_name", None) or getattr(cong, "nombre"),
                org_name=(org_name or "").strip(),
                org_type=org_type,
                leg_period=raw_cong.leg_period,
                role=cargo,
                time_stamp=getattr(raw_cong, "timestamp", datetime.now()),
                start_date=start_date,
                end_date=end_date,
            )
        )

    return final_lst


def process_memberships(
    raw_cong: RawCongresista, cong: Congresista
) -> list[Membership]:
    return process_cong_memberships(raw_cong, cong)

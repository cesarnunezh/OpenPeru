import re
from lxml.html import fromstring

from backend.database.raw_models import RawLey
from backend.process.schema import Ley


def process_leyes(raw_ley: RawLey) -> Ley | None:

    html = fromstring(raw_ley.data)

    try:
        ley, _, recursos = html.xpath("./data/*")
        num_ley = ley.xpath("./numley")[0].text_content()
        title = ley.xpath("./tituloley")[0].text_content()
        bill_id = None

        for recurso in recursos.getchildren():
            if recurso.xpath("tiporecursoleyitemmenu")[0].text == "6":
                link = recurso.xpath("enlace")[0].text
                if not link:
                    continue
                clean_link = link.strip()
                # Congreso links encode expediente as /expediente/<year>/<number>.
                match_year_num = re.search(
                    r"/expediente/(\d{4})/(\d+)(?:[/?#].*)?$", clean_link
                )
                if match_year_num:
                    bill_id = f"{match_year_num.group(1)}_{match_year_num.group(2)}"
                    break
                break

        if bill_id is None:
            return None

        return Ley(
            id=num_ley,
            title=title,
            bill_id=bill_id,
        )
    except (AttributeError, IndexError, ValueError):
        return None

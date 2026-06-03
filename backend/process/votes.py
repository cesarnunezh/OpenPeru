import re
import fitz
from io import BytesIO
from jellyfish import jaro_winkler_similarity as jws

from backend import PARTIES, VOTE_RESULTS
from backend.process.schema import Vote
from backend.process.utils import extract_text


def find_bill(pdf_file: BytesIO, bill_desc: str) -> str:
    """
    Extract the vote pages associated with a specific bill from the daily parliament
    agenda.
    """
    bill_page = 0
    max_jws = 0

    with fitz.open(pdf_file) as pdf:
        for i, page in enumerate(pdf):
            if i % 2 == 0:
                text_page = extract_text_from_page(page)
                asunto = extract_text(text_page, "Asunto:", "\nAPP")
                similarity = jws(asunto, bill_desc)
                if similarity > max_jws:
                    max_jws = similarity
                    bill_page = i
        return pdf[bill_page - 1 : bill_page + 1]


def text_to_votes(vote_page: str, bill_id: int) -> list[Vote]:
    """
    Convert extracted text to a list of Vote objects.
    """
    vote_page = vote_page.replace("\n", " ")

    sorted_parties = sorted(PARTIES, key=len, reverse=True)
    pattern = r"(?=" + "|".join(re.escape(party) for party in sorted_parties) + r")"

    politician_list = re.split(pattern, vote_page)

    string_list = []

    for string in politician_list:
        if string[:4] or string[:5] in sorted_parties:
            string_list.append(string[1:])

    string_list = string_list[1:131]

    # string_list[129] = string_list[129].split("¿")[0].strip()

    vote_list = []
    for politician_vote in string_list:
        vote_as_list = re.split(", | ", politician_vote)

        # Extracting the party
        party = vote_as_list[0]

        # Extracting politician name
        potential_name = vote_as_list[1:5]

        # Condition to deal with politicians without middle name
        if len(potential_name[3]) > 3:
            first = potential_name[:2]
            last = potential_name[2:]
            return_name = last + first
            politician_name = " ".join(return_name)
        else:
            first = potential_name[:2]
            last = [potential_name[2]]
            return_name = last + first
            politician_name = " ".join(return_name)

        # Extracting vote
        for entry in vote_as_list[4:]:
            if entry in VOTE_RESULTS:
                option = entry
                break

        # vote_list.append(Vote(
        #     vote_event_id,
        #     voter_id,
        #     option,
        #     bancada_id
        # ))

        # vote_event = VoteEvent(
        #     "Peruvian Parliament",
        #     ""
        # )

from io import BytesIO

from backend.process.schema import Vote


def find_bill(pdf_file: BytesIO, bill_desc: str) -> str:
    """
    Extract the vote pages associated with a specific bill from the daily parliament
    agenda.
    """
    pass


def text_to_votes(vote_page: str, bill_id: int) -> list[Vote]:
    """
    Convert extracted text to a list of Vote objects.
    """
    pass

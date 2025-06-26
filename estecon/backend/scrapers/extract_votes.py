from .schema import Vote
import pytesseract
import os
import fitz
from io import BytesIO
import httpx
from PIL import Image
import numpy as np
import cv2
from jellyfish import jaro_winkler_similarity as jws
from backend import PARTIES, VOTE_RESULTS
import re

TESSERACT_PATH = os.environ.get('TESSERACT_PATH')
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def extract_text_from_page(page):
    '''
    Extract text from a single PDF page using Tesseract OCR.
    Args:
        page: A PyMuPDF page object.
    '''
    pix = page.get_pixmap(dpi = 300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.TRHES_BINARY)
    pil_img = Image.fromarray(thresh)
    text = pytesseract.image_to_string(pil_img, lang = 'spa', config='--psm 6')
    return text


def render_pdf(pdf_url: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF and Tesseract OCR.
    """
    response = httpx.get(pdf_url)
    response.raise_for_status()  # Ensure we raise an error for bad responses
    pdf_file = BytesIO(response.content)

    with fitz.open(pdf_file) as pdf:
        if len(pdf) == 2:
            # If the PDF has two pages, we assume that the first page is the attendance
            # and the second page is the votes.
            attendance_page = pdf[0]
            votes_page = pdf[1]

            attendance_text = extract_text_from_page(attendance_page)
            votes_text = extract_text_from_page(votes_page)
            
    return attendance_text, votes_text

def extract_bancadas():
    '''
    '''
    pass

def extract_text(text: str, initial: str = None, final: str = None) -> str:
    """
    Extracts the text between an specified initial and final texts. The initial
    or the final text could be optional, but not both

    Args:
        - text: original text
        - initial: initial part of the text to start
        - final: final part of the text to stop the extraction
    """
    assert initial or final, "Must specify either initial or final text"

    if initial and final:
        pattern = re.compile(f"{re.escape(initial)}(.*?){re.escape(final)}", re.DOTALL)
    elif initial and not final:
        pattern = re.compile(f"({re.escape(initial)})(.*)", re.DOTALL)
    else:
        pattern = re.compile(f"(.*?){re.escape(final)}", re.DOTALL)
    result = re.search(pattern, text)

    if not final:
        return result.group(2)
    else:
        return result.group(1)

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
    pattern = r'(?=' + '|'.join(re.escape(party) for party in sorted_parties) + r')'

    politician_list = re.split(pattern, vote_page)

    string_list = []

    for string in politician_list:
        if string[:4] or string[:5] in sorted_parties:
            string_list.append(string[1:])
    
    string_list = string_list[1:131]

    #string_list[129] = string_list[129].split("¿")[0].strip()

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
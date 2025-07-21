import httpx
import polars as pl 
import time
import base64
from datetime import datetime
from .schema import Bill
from .scrape_utils import url_to_cache_file, save_ocr_txt_to_cache, render_pdf
import pandas as pd
import re
from loguru import logger
import random
from ..config import directories

CONGRESS = pl.read_csv("data/congresistas.csv")
BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/" 
BASE_DIR = directories.ROOT_DIR
OCR_CACHE_DIR = BASE_DIR / "data" / "ocr_cache"
BILL_JSONS = BASE_DIR / "data" / "bill_jsons"
VOTE_PATTERN =  re.compile(
    r"\bSI\s*\+{2,}.*?\bNO\s*-{2,}|\bNO\s*-{2,}.*?\bSI\s*\+{2,}", 
    re.IGNORECASE | re.DOTALL
)  

def get_authors_and_adherents(data: dict) -> tuple[str, list[str], list[str]]:
    """
    Extracts the lead author, coauthors, and adherents

    Inputs:
        data (dict): Bill data dictionary

    Returns:
        tuple with:
            - lead_author (dict): The first signer, with keys "id", "dni", "name", and "sex".
            - coauthors (list[dict]): Signers with tipoFirmanteId == 2.
            - adherents (list[dict]): Remaining signers not classified as lead or coauthor.
    """
    lead_author = None
    coauthors = []
    adherents = []
    for i, author_raw in enumerate(data.get("firmantes", [])):
        
        # Grab author ID 
        url = author_raw.get("pagWeb", "N/A")
        match = CONGRESS.filter(pl.col("website") == url)
        if match.is_empty():
            author_id = None
        else:
            author_id = match.select("id").item()
        
        # Grab rest of author info
        name = author_raw.get("nombre")
        dni = author_raw.get("dni")
        sex = author_raw.get("sexo")
        
        # Create cleaned dictionary to save 
        author = {
            "id": author_id,
            "dni": dni,
            "name": name,
            "sex": sex
        }
        
        if i == 0:
            # Lead author 
            lead_author = author
        elif author_raw["tipoFirmanteId"] == 2:
            # Coauthor 
            coauthors.append(author)
        else:
            # Adherent
            adherents.append(author)
    
    return (lead_author, coauthors, adherents)

# Get each step in the bill 
def get_steps(data: dict, year: int, bill_number: int) -> list[dict]:
    """
    Extracts steps in the bill's progress, determine whether each step contains
    a vote or not, and save key information from step.

    Inputs:
        data (dict): Bill data dictionary
        year (int): Congressional session year
        bill_number (int): Bill number in the congress

    Returns:
        list[dict]: A list of steps, each with:
            - date (str)
            - details (str):
            - committee (str): Name of the committee involved in bill step
            - vote_id (str or None): [Congress Year]_[Bill Number]_[Vote #]
            - vote_url (str or None): URL to the vote PDF, if applicable
            - nonvote_url (str or None): URL to the non-vote PDF, if applicable
    """

    steps = [] 
    vote_step_counter = 0 # Track number of steps that have a vote 
    for step in reversed(data.get("seguimientos", [])):
        date = step.get("fecha")
        details = step.get("detalle")
        committee = step.get("desComisiones") 
        vote_step = ("votación" in details.lower() or "votacion" in details.lower())
        vote_id = None
        vote_url = None
        nonvote_url = None
        
        # Loop through each file in the step
        files = step.get("archivos")
        if files:
            for file in files:
                file_id = file["proyectoArchivoId"]
                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = (f"{BASE_URL}/archivo/{b64_id}/pdf")
                
                # If vote file within vote step, record as such
                if vote_step:
                    if is_vote_file(cached_get_file_text(url)):
                        vote_step_counter += 1
                        vote_id = f"{year}_{bill_number}_{vote_step_counter}"
                        vote_url = url
                    else:
                        nonvote_url = url
                else:
                    nonvote_url = url
                
        steps.append({
            "date": date,
            "details": details,
            "committee": committee,
            "vote_id": vote_id,
            "vote_url": vote_url,
            "nonvote_url": nonvote_url
        })
            
    return steps

def get_committees(data: dict) -> list[dict]:
    """
    Extracts comittees related to 

    Inputs:
        data (dict): Bill data dictionary
        year (int): Congressional session year
        bill_number (int): Bill number in the congress

    Returns:
        list[dict]: A list of steps, each with:
            - date (str)
            - details (str):
            - committee (str): Name of the committee involved in bill
            - vote_id (str or None): [Congress Year]_[Bill Number]_[Vote #]
            - vote_url (str or None): URL to the vote PDF, if applicable
            - nonvote_url (str or None): URL to the non-vote PDF, if applicable
    """
    committees = []
    for committee in data.get("comisiones", []):
        committees.append({
            'name': committee["nombre"],
            'id': committee["comisionId"]
        })
    return committees

def is_vote_file(pdf: str) -> bool:
    """
    Check whether scraped PDF is of a vote
    """
    return bool(VOTE_PATTERN.search(pdf))


def cached_get_file_text(url: str) -> str:
    '''
    From a given url, check OCR cache for file,
    If exists, get text, otherwise render the text and save it
    '''
    logger.info("Looking at url", url)
    cached_url_file = url_to_cache_file(url, OCR_CACHE_DIR)
    if cached_url_file.exists():
        logger.info("   Found in cache")
        return cached_url_file.read_text(encoding="utf-8")
    else:
        logger.info("   Not found in cache, extracting from file now")
        file_text = render_pdf(url)
        save_ocr_txt_to_cache(file_text, cached_url_file)
        logger.info("   Saved cache file")
        return file_text


def scrape_bill(year: str, bill_number: str) -> Bill:
    resp = httpx.get(f"{BASE_URL}/expediente/{year}/{bill_number}", verify=False)
    if resp.status_code == 200:
        data = resp.json()["data"]
        general = data["general"]
             
        legislative_session = general.get("desPerParAbrev")
        legislature = general.get("desLegis")
        presentation_date = general.get("fecPresentacion")
        proponent = general.get("desProponente")
        title = general.get("titulo")
        summary = general.get("sumilla")
        observations = general.get("observaciones")
        bancada = general.get("desGpar")
        status = general.get("desEstado")
        bill_complete = (status == "Publicada en el Diario Oficial El Peruano")
        
        lead_author, coauthors, adherents = get_authors_and_adherents(data)
        committees = get_committees(data)      
        steps = get_steps(data, year, bill_number)
        
        return Bill(
            id = f'{year}-{bill_number}',
            leg_period = f'Parlamentario {re.sub(r"\s*-\s*", " - ", legislative_session)}', 
            legislature = legislature,
            presentation_date = datetime.strptime(presentation_date, "%Y-%m-%d"),
            title = title,
            summary = summary,
            observations = observations,
            complete_text = "PENDIENTE", # TODO: Extract the complete text of the bill
            status = status,
            proponent = proponent,
            author_id = lead_author['id'] if lead_author is not None else None, # TODO: Extract the id of the congressman
            bancada_id = None, # TODO: Extract the id of the bancada
            bill_approved = bill_complete,
        )

if __name__ == '__main__':
    vote_urls = []
    for i in range(1, 10):
        print('\n', "Scraping Bill", i, '\n')
        
        # Get bill and save 
        bill = scrape_bill(2021, i)
        bill.save_to_json(f"{BILL_JSONS}/{bill.id}.json")
        time.sleep(random.uniform(5, 10))
        
        # Get vote IDs/urls to pass to vote scraper
        for step in bill.steps:
            id = step.get("vote_id")
            if id:
                vote_urls.append({
                    "id" : id,
                    "url": step.get("vote_url")
                })
        break
                
    df = pd.DataFrame(vote_urls)
    df.to_csv(BASE_DIR / "data" / "vote_pdfs.csv", index=False)
import httpx
import polars as pl 
import time
import base64
from estecon.schema.schema import Bill

CONGRESS = pl.read_csv("data/congresistas.csv")
BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/"        

def scrape_bill(year: str, bill_number: str):
    resp = httpx.get(f"{BASE_URL}/expediente/{year}/{bill_number}", verify=False)
    if resp.status_code == 200:
        data = resp.json()["data"]
        general = data["general"]

        # General information                
        legislative_session = general.get("desPerParAbrev")
        legislature = general.get("desLegis")
        presentation_date = general.get("fecPresentacion")
        proponent = general.get("desProponente")
        title = general.get("titulo")
        summary = general.get("sumilla")
        observations = general.get("observaciones")
        parliamentary_group = general.get("desGpar")
        status = general.get("desEstado")
        bill_complete = (status == "Publicada en el Diario Oficial El Peruano")
        
        # Get authors (lead author, coauthors, adherents)
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
                
        # Get committees 
        committees = []
        for committee in data.get("comisiones", []):
            committees.append({
                'name': committee["nombre"],
                'id': committee["comisionId"]
            })
        
        # Get each step in the bill 
        steps = [] 
        vote_step_counter = 0 # Track number of steps that have a vote 
        for step in reversed(data.get("seguimientos", [])):
            date = step.get("fecha")
            details = step.get("detalle")
            has_vote = ("votación" in details.lower() or 
                        "votacion" in details.lower())
            committee = step.get("desComisiones")
            
            if has_vote:
                # Determine vote ID for voting step
                vote_step_counter += 1
                vote_id = f"{year}_{bill_number}_{vote_step_counter}"
            else:
                vote_id = None
            
            # Loop through each file, check for vote count
            files = step.get("archivos")
            if files:
                urls = []
                for file in files:
                    file_id = files[0]["proyectoArchivoId"]
                    b64_id = base64.b64encode(str(file_id).encode()).decode()
                    urls.append(f"{BASE_URL}/archivo/{b64_id}/pdf")
                    # if tally_votes(vote_id, details, urls) <- Call Ganon's function
            else:
                url = None
                
            steps.append({
                "date": date,
                "details": details,
                "committee": committee,
                "vote_id": vote_id,
                "url": url
            })
        
        return Bill(
            year, 
            bill_number, 
            legislative_session, 
            legislature, 
            presentation_date,
            proponent, 
            title, 
            summary, 
            observations, 
            lead_author, 
            coauthors, 
            adherents, 
            parliamentary_group, 
            committees, 
            status, 
            bill_complete,
            steps
        )
        

if __name__ == '__main__':
    pdf_urls = []
    for i in range(10300, 10323):
        bill = scrape_bill(2021, i)
        if bill.get("is_complete"):
            for step in bill["steps"]:
                if step["vote_id"]:
                    pdf_urls.append({
                        "vote_id": step["vote_id"],
                        "details": bill["observations"]     
                    })

        
        bill.save_to_json()
        print(i, "saved to JSON")
        time.sleep(5)
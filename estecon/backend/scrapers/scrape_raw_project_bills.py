import httpx
import json
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from estecon.backend.database.models import RawBill
BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/" 
DB_PATH = "sqlite:///./OpenPeru.db" 


class RawBillScraper:
    '''
    Class to scrape and store raw bill information
    '''
    def __init__(self):
        
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH)
        self.Session = sessionmaker(bind=self.engine)
        
        # Mapping raw section name to RawBill attribute name
        self.section_mapping = {
            "general": "general",
            "firmantes": "congresistas",
            "comisiones": "committees",
            "seguimientos": "steps"
            
    }
        
    def scrape_bill(self, year: str, bill_number: str) -> tuple[bool, str]:
        '''
        Scrape key sections: general, congresistas, committees, steps
        
        Returns tuple with result of scrape, error message if relevant
        '''
        resp = httpx.get(f"{BASE_URL}/expediente/{year}/{bill_number}", verify=False)
        if resp.status_code == 200:
            data = resp.json()["data"]
            
            # Initialize raw bill with id and timestamp 
            raw_bill = RawBill(id = f"{year}_{bill_number}",
                               timestamp = datetime.now() 
                               )
            
            # Add sections
            for raw_name, attribute_name in self.section_mapping.items():
                # Grab expected section, use English value to signal no section
                # (since sections can be empty lists themselves)
                attribute_value = data.get(raw_name, "Not Found")
                if attribute_value == "Not Found":
                    return (False, f"{raw_bill.id} - Missing Attribute: {raw_name} ({attribute_name})")
                else:
                    setattr(raw_bill, attribute_name, json.dumps(attribute_value))
            
            # Successfully built the raw bill! 
            self.raw_bill = raw_bill        
            return (True, "")
        
        else:
            return (False, f"{raw_bill.id} - Received Response of {resp.status_code}")
        
    
    def add_bill_to_db(self) -> bool:
        """
        Add a single bill to the database.
        Returns True on success, False on failure.
        """
        assert self.raw_bill, "Raw Bill must be scraped before it can be saved"

        # Create a new session  
        session = self.Session()
        try:
            # Add and commit raw bill
            session.add(self.raw_bill)
            session.commit()
            print(f"Added {self.raw_bill.id} to Raw Bills table.")
            return True
        
        except SQLAlchemyError as e:
            print(f"Failed to add bill {self.raw_bill.id} to Raw Bills table: {e}")
            session.rollback() 
            return False
        
        finally:
            # Close Session
            session.close() 
        
        
if __name__ == "__main__":
    scraper = RawBillScraper()
    scraper.scrape_bill("2021", "103")
    scraper.add_bill_to_db()
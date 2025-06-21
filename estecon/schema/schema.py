import json
from datetime import datetime

class Vote:
    '''
    Represents a vote in a parliament session.
    
    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (str): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (str): The political group of the voter.
    '''
    def __init__(self, vote_event_id: str, voter_id: str, option: str, bancada_id: str):
        
        # Attributes that fit in in Popolo structure
        self.vote_event_id = vote_event_id
        self.voter_id = voter_id
        self.option = option
        self.bancada_id = bancada_id

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

class VoteEvent:
    '''
    Represents a vote event in a parliament session.
    Attributes:
        org_id (str): The org_id or parliament where the vote took place.
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    '''
    def __init__(self, org_id: str, leg_period: str, bill_id: str, date: str):
        
        # Attributes that fit in in Popolo structure
        self.org_id = org_id
        self.leg_period = leg_period
        self.bill_id = bill_id
        self.date = date

    def add_votes(self, votes: list[Vote]):
        self.votes = votes
        self.result = [v.option for v in votes]

    def get_counts(self):
        self.counts = {option: self.results.count(option) for option in set(self.results)}
        return self.counts
    
    def get_counts_by_bancada(self):
        self.counts_by_bancada = {}
        for vote in self.votes:
            if vote.bancada_id not in self.counts_by_bancada:
                self.counts_by_bancada[vote.bancada_id] = {}
            if vote.option not in self.counts_by_bancada[vote.bancada_id]:
                self.counts_by_bancada[vote.bancada_id][vote.option] = 0
            self.counts_by_bancada[vote.bancada_id][vote.option] += 1
        return self.counts_by_bancada

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

    
class Committee:
    '''
    Represents a committee in the peruvian parliament.

    Attributes:
        period (str): Legislative period.
        com_id (int): Unique identifier for the committee.
        com_name (str): Name of the committee.
    '''
    def __init__(self, leg_period: str, leg_year: int, org_id: str, 
                 com_id: int, com_name: str):
        self.leg_period = leg_period
        self.leg_year = leg_year
        self.org_id = org_id
        self.com_id = com_id
        self.com_name = com_name
    
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

class Bill:
    '''
    Represents a bill in the peruvian parliament.

    Attributes:
        year (int): Year of the bill.
        bill_number (int): Unique identifier for the bill.
        legislative_session (str): Legislative session of the bill.
        legislature (str): Legislature where the bill was presented.
        presentation_date (datetime): Date when the bill was presented.
        proponent (str): Proponent of the bill.
        title (str): Title of the bill.
        summary (str): Summary of the bill.
        observations (str): Observations on the bill.
        lead_author (str): Lead author of the bill.
        coauthors (list[dict]): List of coauthors of the bill.
        adherents (list[dict]): List of adherents to the bill.
        bancada (str): Political group associated with the bill.
        committees (list[Committee]): Committees related to the bill.
        status (str): Current status of the bill.
        bill_complete (str): Complete text of the bill.
        steps (list[dict]): Steps in the legislative process for this bill.
    '''
    def __init__(self, year: int, bill_number: int, legislative_session: str, 
                 legislature: str, presentation_date: datetime, proponent: str, 
                 title: str, summary: str, observations: str, lead_author: str, 
                 coauthors: list[dict], adherents: list[dict], bancada: str,
                 committees: list[Committee], status: str, bill_complete: str, 
                 steps: list[dict]):
    
        
        # Attributes that fit in in Popolo structure
        self.legislative_session = legislative_session
        self.lead_author = lead_author
        self.summary = summary
        self.id = f"{year}_{bill_number}"    
        self.presentation_date = presentation_date
        self.status = status
        
        
        # Additional attributes from bill page
        self.legislature = legislature
        self.proponent = proponent
        self.title = title
        self.observations = observations
        self.coauthors = coauthors
        self.adherents = adherents
        self.bancada = bancada
        self.committees = committees 
        self.bill_complete = bill_complete
        self.steps = steps
    
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
    
    def save_to_json(self):
        with open(f"data/bill_jsons/{self.id}.json", "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

class Congresista:
    '''
    Represents a congressman or congresswoman

    Attributes:
        id (str): Unique identifier for the congressperson.
        nombre (str): Name of the congressperson.
        leg_period (str): Legislative period.
        party_id (str): Unique identifier for the party.
        bancada_id (str): Unique identifier for the bancada (parliamentary group).
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
    '''
    def __init__(self, id: str, nombre: str, votation: int, leg_period: str,
                party_name: str, bancada_name: str, dist_electoral: str, 
                condicion: str, website: str):
        

        # Attributes that fit in in Popolo structure
        self.id = id
        self.nombre = nombre
        self.votation = votation
        self.leg_period = leg_period
        self.party_name = party_name
        self.bancada_name = bancada_name
        self.dist_electoral = dist_electoral
        self.condicion = condicion
        self.website = website

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items()) 

class Party:
    '''
    Represents a political party.

    Attributes:
        period (str): Legislative period.
        party_id (int): Unique identifier for the party.
        party_name (str): Name of the party.
    '''
    def __init__(self, leg_period: str, party_id: int, party_name: str):
        self.leg_period = leg_period
        self.party_id = party_id
        self.party_name = party_name

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())


class Bancada:
    '''
    Represents a political bancada (parliamentary group).

    Attributes:
        period (str): Legislative period.
        bancada_id (int): Unique identifier for the bancada.
        bancada_name (str): Name of the bancada.
    '''
    def __init__(self, leg_period: str, bancada_id: int, bancada_name: str):
        self.leg_period = leg_period
        self.bancada_id = bancada_id
        self.bancada_name = bancada_name

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
    
class Organization:
    '''
    Represents a legislative organization, such as a parliament or congress.
    Attributes:
        org_id (str): Unique identifier for the organization.
        leg_year (int): Legislative year.
        name (str): Name of the organization.
    '''
    def __init__(self, org_id: str, leg_year: int, name: str):
        self.org_id = org_id
        self.leg_year = leg_year
        self.name = name
        # self.classification = classification

class Event:
    '''
    Represents an event in a legislative organization, such as a session or meeting.

    Attributes:
        event_id (str): Unique identifier for the event.
        event_name (str): Name of the event.
        description (str): Description of the event.
        start_time (datetime): Start time of the event.
        end_time (datetime): End time of the event.
        org_id (str): Unique identifier for the organization where the event takes place.
    '''
    def __init__(self, event_id: str, event_name: str, description: str, start_time: datetime,
                 end_time: datetime, org_id: str):
        self.event_id = event_id
        self.event_name = event_name
        self.description = description
        self.start_time = start_time
        self.end_time = end_time
        self.org_id = org_id
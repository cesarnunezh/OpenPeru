import json
import pathlib

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
        organization (str): The organization or parliament where the vote took place.
        legislative_period (str): The legislative period during which the vote occurred.
        vote_id (str): Unique identifier for the vote event.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
        result (str): The result of the vote, e.g., 'approved', 'rejected'.
        counts (dict): A dictionary containing counts of votes, e.g., {'yes': 100, 'no': 50, 'abstain': 10}.
    '''
    def __init__(self, organization: str, legislative_period: str, votes: list[Vote],
                 bill_id: str, date: str):
        self.organization = organization
        self.legislative_period = legislative_period
        self.bill_id = bill_id
        self.vote_id = votes
        self.date = date
        self.result = [v.option for v in votes]
        self.counts = {option: self.results.count(option) for option in set(self.results)}

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

class Bill:
    def __init__(self, year, bill_number, legislative_session, legislature, presentation_date, 
               proponent, title, summary, observations, lead_author, coauthors, 
               adherents, parliamentary_group, committees, status, bill_complete, steps):
    
        
        # Attributes that fit in in Popolo structure
        self.organization = "Peruvian Parliament"
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
        self.parliamentary_group = parliamentary_group
        self.committees = committees 
        self.bill_complete = bill_complete
        self.steps = steps
    
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
    
    def save_to_json(self, path: pathlib.Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

class Congresista:
    def __init__(self, id: str, nombre: str, votos: int, periodo: str, partido: str,
                 bancada: str, dist_electoral: str, condicion: str, website: str):
        self.id = id
        self.nombre = nombre
        self.votos = votos
        self.periodo = periodo
        self.partido = partido
        self.bancada = bancada
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
    def __init__(self, period: str, party_id: int, party_name: str):
        self.period = period
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
    def __init__(self, period: str, bancada_id: int, bancada_name: str):
        self.period = period
        self.bancada_id = bancada_id
        self.bancada_name = bancada_name

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
    def __init__(self, period: str, com_id: int, com_name: str):
        self.period = period
        self.com_id = com_id
        self.com_name = com_name
    
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
from pydantic import BaseModel, field_validator, ConfigDict
from estecon.backend import (VoteOption, AttendanceStatus, BillStepType, RoleTypeBill,
                     LegPeriod, Legislature, LegislativeYear, Proponents,
                     TypeOrganization, RoleOrganization)
from typing import List, Optional, Dict
from datetime import datetime
from pathlib import Path


class PrintableModel(BaseModel):
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.model_dump().items())

class Vote(PrintableModel):
    """
    Pydantic model representing a vote.

    Attributes:
        vote_event_id (str):
        voter_id (str):
        option (str):
        bancada_id (str):
    """
    
    # Attributes that fit in in Popolo structure
    vote_event_id: str
    voter_id: int
    option: VoteOption
    bancada_id: int

    model_config = ConfigDict(use_enum_values=False)

class Attendance(PrintableModel):
    '''
    Represents attendance of a congressperson at an event.

    Attributes:
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    '''
    org_id: int
    event_id: str
    attendee_id: int
    status: AttendanceStatus
    
    model_config = ConfigDict(use_enum_values=False)


class VoteEvent(PrintableModel):
    '''
    Represents a vote event in a parliament session.
    Attributes:
        org_id (str): The org_id or parliament where the vote took place.
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    '''

    # Attributes that fit in in Popolo structure
    id: str
    org_id: int
    leg_period: LegPeriod
    bill_id: str
    date: datetime
    votes: Optional[List[Vote]] = None
    attendance: Optional[List[Attendance]] = None

    model_config = ConfigDict(use_enum_values=False)
    
    def get_counts(self) -> Dict[VoteOption, int]:
        """
        Counts the number of votes per option.
        """
        if not self.votes:
            return {}
        return {
            option: sum(1 for vote in self.votes if vote.option == option)
            for option in set(vote.option for vote in self.votes)
        }
    
    def get_counts_by_bancada(self) -> Dict[int, Dict[VoteOption, int]]:
        """
        Returns vote counts grouped by bancada and option.
        """        
        if not self.votes:
            return {}
        
        counts: Dict[int, Dict[VoteOption, int]] = {}
        for vote in self.votes:
            counts.setdefault(vote.bancada_id, {}).setdefault(vote.option, 0)
            counts[vote.bancada_id][vote.option] += 1
        return counts

    def get_attendance_summary(self) -> Dict[str, int]:
        """
        Returns a summary count of attendance statuses.
        """
        if not self.attendance:
            return {}
        
        summary: Dict[str, int] = {}
        for att in self.attendance:
            summary[att.status] = summary.get(att.status, 0) + 1
        return summary


class VoteCount(PrintableModel):
    '''
    Represents the counts of votes in a vote event.

    Attributes:
        org_id (int): The org_id or parliament where the vote took place.
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada (str): The political group of the voter.
        count (int): Number of votes for the option.
    '''
    org_id: int
    vote_event_id: str
    option: VoteOption
    bancada_id: int
    count: int

    model_config = ConfigDict(use_enum_values=False)

class BillStep(PrintableModel):
    '''
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        id (int): A unique identifier for each step record.
        bill_id (str): The identifier of the bill associated with this step.
        step_type (str): The type of step record (e.g. "Vote", "Assigned to Committee", "Presented", etc.)
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
        step_url (str): The url associated to the step
    '''
    id: int
    bill_id: str
    step_type: BillStepType
    step_date: datetime
    step_detail: str
    step_url: str

    model_config = ConfigDict(use_enum_values=False)


class Bill(PrintableModel):
    '''
    Represents a bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        org_id (int): The org_id or parliament where the bill was presented.
        leg_period (str): Legislative period of the bill.
        legislature (str): Legislature where the bill was presented.
        presentation_date (datetime): Date when the bill was presented.
        title (str): Title of the bill.
        summary (str): Summary of the bill.
        observations (str): Observations on the bill.
        complete_text (str): Complete text of the bill.
        status (str): Current status of the bill.
        proponent (str): Type of proponent of the bill
        author_id (str): Unique identifier for the author of the bill.
        bancada_id (str): Unique identifier for the political group associated with the bill.
        bill_approved (bool): Boolean indicating if the bill has been published        
    '''
    # Attributes that fit in in Popolo structure
    id: str
    org_id: int
    leg_period: LegPeriod
    legislature: Legislature
    presentation_date: datetime
    title: str
    summary: str
    observations: str
    complete_text: str
    status: str
    proponent: Proponents
    author_id: int
    bancada_id: int
    bill_approved: bool

    model_config = ConfigDict(use_enum_values=False)

    
    def save_to_json(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

class BillCongresistas(PrintableModel):
    '''
    Represents a relation between a bill and parliament members based on their 
    role during the presentation of the bill.
    
    Attributes:
        bill_id (str): A unique identifier for the bill.
        person_id (str): A unique identifier for the person.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc) 
    '''
    bill_id: str
    person_id: str
    role_type: RoleTypeBill

    model_config = ConfigDict(use_enum_values=False)

class BillCommittees(PrintableModel):
    '''
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_id (str): The identifier of the committee.
    '''
    bill_id: str
    committee_id: int

class Congresista(PrintableModel):
    '''
    Represents a member of the peruvian parliament

    Attributes:
        id (str): Unique identifier for the person.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_id (str): Unique identifier for the party.
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
    '''
    # Attributes that fit in Popolo structure
    id: int
    leg_period: LegPeriod
    nombre: str
    party_id: int
    votes_in_election: int
    dist_electoral: Optional[str]
    condicion: str
    website: str

    model_config = ConfigDict(use_enum_values=False)

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.model_dump().items()) 

class Party(PrintableModel):
    '''
    Represent a Political Party in the peruvian government

    Attributes:
        leg_period (str): Legislative period.
        party_id (int): Unique identifier for the party
        party_name (str): Name of the party
    '''
    leg_period: LegPeriod
    party_id: int
    party_name: str

class Bancada(PrintableModel):
    '''
    Represent a Bancada in the peruvian government

    Attributes:
        leg_year (str): Year period of the bancada
        bancada_id (int): Unique identifier for the bancada
        bancada_name (str): Name of the bancada
    '''
    leg_year: LegislativeYear
    bancada_id: int
    bancada_name: str

class Organization(PrintableModel):
    '''
    Represents a legislative organization inside the parliament, such as a committee.
    
    Attributes:
        leg_period (str): Legislative period.
        leg_year (str): Legislative year.
        org_id (int): Unique identifier for the organization.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. committee, etc)
    '''
    leg_period: LegPeriod
    leg_year: LegislativeYear
    
    # Attributes that fit in Popolo structure
    org_id: int
    org_name: str
    org_type: TypeOrganization
    org_url: Optional[str]

    model_config = ConfigDict(use_enum_values=False)

class Membership(PrintableModel):
    '''
    Represents a person's role in an organization during a specific time period.
    
    Attributes:
        id (int): Unique identifier for the membership relationship.
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    '''
    # Attributes that fit in Popolo structure
    id: int
    role: RoleOrganization
    person_id: int
    org_id: int
    start_date: datetime
    end_date: datetime

    model_config = ConfigDict(use_enum_values=False)
    
    @field_validator('end_date')
    def check_end_after_start(cls, end, info):
        start = info.data.get('start_date')
        if start and end and end < start:
            raise ValueError('end_date must be after start_date')
        return end
    
class BancadaMembership(PrintableModel):
    '''
    Represents a person's membership in a bancada during a specific time period.
    
    Attributes:
        id (int): Unique identifier for the membership relationship.
        leg_year (str): Year period of the membership
        person_id (int): Identifier for the person
        bancada_id (int): Identifier for the bancada
    '''
    id: int
    leg_year: LegislativeYear
    person_id: int
    bancada_id: int
from pydantic import BaseModel, field_validator, Field
from backend import VoteOption, AttendanceStatus, BillStepType, RoleTypeBill, LegPeriod, Legislature, LegislativeYear, Proponents
from typing import List, Optional
from loguru import logger
from datetime import datetime
from difflib import get_close_matches
import json
from pathlib import Path

class Vote(BaseModel):
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

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

class VoteEvent(BaseModel):
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

    def add_votes(self, votes: list[Vote]):
        self.votes = votes
        self.results = [v.option for v in votes]

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

    def add_attendance(self, attendance: list['Attendance']):
        '''
        Adds attendance records to the event.
        
        Args:
            attendance (list[Attendance]): List of Attendance objects.
        '''
        self.attendance = {}
        for att in attendance:
            self.attendance[att.status] = self.attendance.get(att.status, 0) + 1

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())


class Attendance(BaseModel):
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

class VoteCount(BaseModel):
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

class BillStep(BaseModel):
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
    
class Committee(BaseModel):
    '''
    Represents a committee in the peruvian parliament.

    Attributes:
        leg_period (str): Legislative period of the committee.
        leg_year (str): Year period of the committee
        org_id (int): The org_id or parliament where the committee belongs.
        id (int): A unique identifier for the committee.
        name (str): Name of the committee
    '''
    leg_period: LegPeriod
    leg_year: LegislativeYear
    org_id: int
    id: str
    name: str
    
    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

class Bill(BaseModel):
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
    org_id: str
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

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
    
    def save_to_json(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

class BillCongresistas(BaseModel):
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

class BillCommittees(BaseModel):
    '''
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_id (str): The identifier of the committee.
    '''
    bill_id: str
    committee_id: int

class Congresista(BaseModel):
    '''
    Represents a member of the peruvian parliament

    Attributes:
        id (str): Unique identifier for the person.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_id (str): Unique identifier for the party.
        bancada_id (str): Unique identifier for the bancada (parliamentary group).
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
    '''
    # Attributes that fit in in Popolo structure
    id: str
    leg_period: LegPeriod
    nombre: str
    party_id: int
    bancada_id: int
    votes_in_election: int
    dist_electoral: str
    condicion: str
    website: str

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items()) 


class Party(BaseModel):
    '''
    Represents a political party.

    Attributes:
        period (str): Legislative period.
        party_id (int): Unique identifier for the party.
        party_name (str): Name of the party.
    '''
    leg_period: LegPeriod
    party_id: int
    party_name: str

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())


class Bancada(BaseModel):
    '''
    Represents a political bancada (parliamentary group).

    Attributes:
        period (str): Legislative period.
        bancada_id (int): Unique identifier for the bancada.
        bancada_name (str): Name of the bancada.
    '''
    leg_period: LegPeriod
    bancada_id: int
    bancada_name: str

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())
    
class Organization(BaseModel):
    '''
    Represents a legislative organization, such as a parliament or congress.
    
    Attributes:
        org_id (str): Unique identifier for the organization.
        leg_period (int): Legislative year.
        name (str): Name of the organization.
    '''
    id: int
    leg_period: LegPeriod
    name: str
    # classification: str

    def __str__(self):
        return '\n'.join(f"{key}: {value}" for key, value in self.__dict__.items())

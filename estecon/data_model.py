from typing import NamedTuple

class Vote(NamedTuple):
    '''
    Represents a vote in a parliament session.
    
    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (str): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        political_group (str): The political group of the voter.
    '''
    vote_event_id: str
    voter_id: str
    option: str
    political_group: str

class VoteEvent(NamedTuple):
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
    organization: str
    legislative_period: str
    vote_id: str
    bill_id: str
    date: str
    result: str
    counts: dict



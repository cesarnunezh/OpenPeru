from datetime import date
from fastapi.testclient import TestClient
from pydantic import ValidationError, BaseModel, Field
from ..main import app
from typing import List, Optional
import pytest

client = TestClient(app)

VERSION = "v1"
ENDPOINT_NAME = "events"
TEST_QUERY = "bill_id=2021_10307"


# SUggested approach from: https://stackoverflow.com/a/68726632
# TODO: Modify to use shared response format
class VoteSum(BaseModel):
    yes: int
    no: int
    absent: int


class Vote(BaseModel):
    congresista_id: int
    option: str


class Events(BaseModel):
    step_id: int
    step_type: str
    step_date: date
    step_details: str
    vote_event_id: Optional[int] = None
    vote_sum: Optional[VoteSum] = None
    votes: Optional[List[Vote]] = Field(default_factory=list)


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}?{TEST_QUERY}")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model

    Assumes that any bill_id would have to at least on event.
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}?{TEST_QUERY}")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["bill_id"] == "2021_10307"
    try:
        for event in data["data"]["steps"]:
            Events(**event)
            if event[
                "vote_event_id"
            ]:  # If there's vote event, it pulls in aggrgeations and votes
                print(event["vote_sum"])
                VoteSum(**event["vote_sum"])
                for vote in event["votes"]:
                    Vote(**vote)
    except ValidationError as e:
        pytest.fail(f"Response does not match expected data model as {e}")


@pytest.mark.parametrize(
    "query_str",
    [
        ("bill_id=2021_10300&congresistas_id=1000"),
        ("bill_id=2021_10300&last_action_date=2025-01-01"),
        ("bill_id=2021_10300&step_type=2025-01-21"),
    ],
)
def test_query_params(query_str):
    """
    Validates the query parameters used
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}?{query_str}")
    assert response.status_code == 200, f"Failed with {query_str}"

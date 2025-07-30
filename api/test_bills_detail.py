from datetime import date
from fastapi.testclient import TestClient
from pydantic import ValidationError, BaseModel, Field
from main import app
from typing import List
import pytest

client = TestClient(app)


# TODO: Modify to use shared response format
class BillDetail(BaseModel):
    bill_id: str = Field(..., pattern=r"\d{4}_\d{5}")
    status: str
    title: str
    summary: str
    author_id: int
    coauthors: List[int]
    leg_period: str = Field(..., pattern=r"([1-2]\d{3}\-[1-2]\d{3})")
    last_action_date: date
    presentation_date: date
    complete_text: str
    bancada_id: int
    bancada_name: str
    bill_approved: bool


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get("/v1/bills/2021_10300")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model
    """
    response = client.get("/v1/bills/2021_10300")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]  # Check it's not an empty response object
    try:
        BillDetail(**data["data"])
    except ValidationError:
        pytest.fail("Response does not match expected data model")


@pytest.mark.parametrize("bill_id, response_code", [("9999_99999", 404), ("abc", 422)])
def test_invalid_path(bill_id, response_code):
    """
    Check API returns appropriate response codes for path parameteres.
    """
    response = client.get(f"/v1/bills/{bill_id}")
    assert response.status_code == response_code, "Unexpected response code"
    assert response.json()["detail"], "Missing error detail"

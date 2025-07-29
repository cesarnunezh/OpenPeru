from datetime import date
from fastapi.testclient import TestClient
from pydantic import ValidationError, BaseModel, Field
from main import app
from typing import List
import pytest

client = TestClient(app)


# SUggested approach from: https://stackoverflow.com/a/68726632
# TODO: Modify to use shared response format
class Bill(BaseModel):
    bill_id: str = Field(..., pattern=r"\d{4}_\d{5}")
    status: str
    title: str
    summary: str
    author_id: int
    coauthors: List[int]
    leg_period: str = Field(..., pattern=r"([1-2]\d{3}\-[1-2]\d{3})")
    last_action_date: date


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get("/v1/bills")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model
    """
    response = client.get("/v1/bills")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    try:
        for bill in data["data"]:
            Bill(**bill)  # Unpacks the dict to validate using keys
    except ValidationError:
        pytest.fail("Response does not match expected data model")


@pytest.mark.parametrize(
    "query_str",
    [
        ("status=failed"),
        ("proposed_by=1000"),
        ("last_action_date=2025-01-01"),
        ("step_type=advanced"),
        ("leg_period=2021-2026"),
        ("leg_period=2021-2026&proposed_by=1000"),
    ],
)
def test_query_params(query_str):
    """
    Validates the query parameters used
    """
    response = client.get(f"/v1/bills?{query_str}")
    assert response.status_code == 200, f"Failed with {query_str}"


# TODO: Set-up extra forbidden query params
# def test_invalid_query_params():
#    """
#    Check API returns 422 if an unexpected query param is provided
#    """
#    response = client.get("/v1/bills?fakequery=fake")
#    assert response.status_code == 422, "Unexpected response code"
#    assert response.json()["detail"], "Missing error detail"

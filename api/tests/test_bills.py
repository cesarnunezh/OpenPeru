from fastapi.testclient import TestClient
from pydantic import ValidationError
from api.main import app
from estecon.backend.scrapers.schema import Bill
import pytest

client = TestClient(app)

VERSION = "v1"
ENDPOINT_NAME = "bills"


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}")
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
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}?{query_str}")
    assert response.status_code == 200, f"Failed with {query_str}"

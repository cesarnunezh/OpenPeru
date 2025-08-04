from fastapi.testclient import TestClient
from pydantic import ValidationError
from api.main import app
from estecon.backend.scrapers.schema import Bill
import pytest

client = TestClient(app)

VERSION = "v1"
ENDPOINT_NAME = "bills"
TEST_OBS = "2021_10300"


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}/{TEST_OBS}")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}/{TEST_OBS}")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]  # Check it's not an empty response object
    try:
        Bill(**data["data"])
    except ValidationError:
        pytest.fail("Response does not match expected data model")


@pytest.mark.parametrize("bill_id, response_code", [("9999_99999", 404), ("abc", 422)])
def test_invalid_path(bill_id, response_code):
    """
    Check API returns appropriate response codes for path parameteres.
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}/{bill_id}")
    assert response.status_code == response_code, "Unexpected response code"
    assert response.json()["detail"], "Missing error detail"

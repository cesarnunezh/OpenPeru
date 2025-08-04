from fastapi.testclient import TestClient
from pydantic import ValidationError
from api.main import app
from estecon.backend.scrapers.schema import Congresista
import pytest

client = TestClient(app)

VERSION = "v1"
ENDPOINT_NAME = "congresistas"
TEST_OBS = "1109"


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
        Congresista(**data["data"])
    except ValidationError:
        pytest.fail("Response does not match expected data model")


@pytest.mark.parametrize("congresista_id, response_code", [(1110, 404), ("abc", 422)])
def test_invalid_path(congresista_id, response_code):
    """
    Check API returns appropriate response codes for path parameteres.

    Note: FastAPI default behavior is to redirect /v1/congresistas/ to
        /v1/congresista, so not test is needed for an empty response.
    """
    response = client.get(f"/{VERSION}/{ENDPOINT_NAME}/{congresista_id}")
    assert response.status_code == response_code, "Unexpected response code"
    assert response.json()["detail"], "Missing error detail"

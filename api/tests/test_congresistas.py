from fastapi.testclient import TestClient
from pydantic import ValidationError, BaseModel
from ..main import app
import pytest

client = TestClient(app)


# SUggested approach from: https://stackoverflow.com/a/68726632
# TODO: Modify to use shared response format
class Congresista(BaseModel):
    id: int
    nombre: str
    leg_period: str
    party_name: str
    bancada_name: str
    dist_electoral: str
    condicion: str


def test_active_endpoint():
    """
    Check that the endpoint returns a repsonse active when hit with a valid
    request
    """
    response = client.get("/v1/congresistas")
    assert response.status_code == 200, "Endpoint does not return a valid response"
    data = response.json()
    assert data not in [{}, "", None, []], "Response body is empty"


def test_response_matches_model():
    """
    Validate response using the declared Pydantic model
    """
    response = client.get("/v1/congresistas")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    try:
        for congresista in data["data"]:
            Congresista(**congresista)  # Unpacks the dict to validate using keys
    except ValidationError:
        pytest.fail("Response does not match expected data model")


@pytest.mark.parametrize(
    "query_str",
    [
        ("leg_period=2021-2026"),
        ("leg_period=2016-2021"),
    ],
)
def test_query_params(query_str):
    """
    Validates the query parameters used
    """
    response = client.get(f"/v1/congresistas?{query_str}")
    assert response.status_code == 200, f"Failed with {query_str}"


# TODO: Set-up extra forbidden query params
# def test_invalid_query_params():
#    """
#    Check API returns 422 if an unexpected query param is provided
#    """
#    response = client.get("/v1/bills?fakequery=fake")
#    assert response.status_code == 422, "Unexpected response code"
#    assert response.json()["detail"], "Missing error detail"

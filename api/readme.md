# User Guide
This is a [FastAPI](https://fastapi.tiangolo.com/) API for Open Peru data.

### Launch the API
To launch the application locally, first confirm that uv is installed. Check the [readme](../README.md) in the root directory for instructions.
```bash
uv run fastapi dev
```
The API is not currently set-up for being run in a production environment.

### Testing
Testing the API can be done from tests within the API drectory.
```bash
cd api
uv run pytest
```
No additional plug-ins or software are needed.

# Components of this FastAPI application:

- Routes: All routes in the main.py folder, and send out test data for use in developing the frontend. They should be switched to an api/routes/ directory for each route family.
- Database: No database models are included.
- Validation: Pydantic schemas are currently only used to valdate outputs for testing and are stored in each test. Once they are used across the scraping and API directories, they can be accessed by

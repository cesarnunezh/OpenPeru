# Database Setup

This directory contains the Docker setup for the shared OpenCongress PostgreSQL
database and the raw data migration image.

This container should be run only once.

## Installing requirements

- Install Docker. Follow the instructions to install Docker Desktop [here](https://docs.docker.com/desktop/). If using WSL, follow [these instructions](https://docs.docker.com/desktop/features/wsl/). Then verify with:
  ```bash
  docker --version 
  ```

- Clone this repository and checkout `dev` branch.
  ```bash
  git clone git@github.com:openperu2026/dev-opencongress.git
  git switch dev
  ```

## Run PostgreSQL

We already have PostgreSQL server running with `pgvector`, `pg_similarity` and `unnaccent` extensions.

Be sure to establish the following connection settings in your .env variable:

```env
# DB configs
POSTGRES_USER=some_user_name
POSTGRES_PASSWORD=some_password
POSTGRES_DB=opencongress

# Server configs
POSTGRES_INTERNAL_HOST=server_host
POSTGRES_PORT=123456

DB_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_INTERNAL_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Migration SQLite -> PostgreSQL 
SQLITE_PATH=/app/data/raw/OpenPeruRaw.db
RAW_MIGRATION_IMAGE=cesarnunezh/opencongress-raw-migration:latest
```

## Run Migration

The migration image contains the old SQLite `OpenPeruRaw.db` seed data. The SQLite file is not committed to Git, so any contributor should use the published DockerHub image instead of building it locally.

Set the image tag in your .env file

```text
# Migration SQLite -> PostgreSQL 
SQLITE_PATH=/app/data/raw/OpenPeruRaw.db
RAW_MIGRATION_IMAGE=cesarnunezh/opencongress-raw-migration:latest
```

Run the migration:

```bash
make migration
```

## Maintainer Notes

Only the person publishing the shared seed image needs the local
`data/raw/OpenPeruRaw.db` file.

Build and push the image:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push \
  -f backend/database/migration/migration.Dockerfile \
  -t cesarnunezh/opencongress-raw-migration:latest \
  .

docker push cesarnunezh/opencongress-raw-migration:latest
```

After pushing a new seed image, other contributors can reset their local volume and rerun the migration.

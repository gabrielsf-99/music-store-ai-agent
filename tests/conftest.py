from pathlib import Path

import pytest
from psycopg import sql

from emporio.db.connection import connect
from emporio.ingest.pipeline import run

FIXTURE_DATA_DIR = Path(__file__).parent / "fixtures" / "data"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
TEST_SCHEMA = "emporio"


@pytest.fixture
def fixture_data_dir() -> Path:
    return FIXTURE_DATA_DIR


@pytest.fixture
def test_schema() -> str:
    return TEST_SCHEMA


@pytest.fixture(scope="session")
def database_url():
    """Ephemeral Postgres container, started only by tests that need a database."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE, driver=None) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def conn(database_url):
    with connect(database_url, TEST_SCHEMA) as conn:
        yield conn
        conn.rollback()
        drop = sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(TEST_SCHEMA))
        conn.execute(drop)
        conn.commit()


@pytest.fixture
def loaded_conn(conn, fixture_data_dir):
    """Connection with the synthetic fixture dataset already ingested."""
    run(fixture_data_dir, conn, TEST_SCHEMA)
    return conn

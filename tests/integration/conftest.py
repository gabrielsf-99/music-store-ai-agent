import pytest
from psycopg import sql
from testcontainers.community.postgres import PostgresContainer

from emporio.db.connection import connect

POSTGRES_IMAGE = "pgvector/pgvector:pg16"
TEST_SCHEMA = "emporio"


@pytest.fixture(scope="session")
def database_url():
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

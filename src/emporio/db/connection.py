import psycopg

from emporio.config import get_settings

CONNECT_TIMEOUT_SECONDS = 10


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)

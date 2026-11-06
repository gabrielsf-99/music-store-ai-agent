import psycopg
from psycopg import sql

from emporio.config import get_settings

CONNECT_TIMEOUT_SECONDS = 10


def connect(database_url: str | None = None, schema: str | None = None) -> psycopg.Connection:
    """Open a connection whose search_path points to the application schema.

    `extensions` is included because Supabase installs extensions there.
    """
    if database_url is None or schema is None:
        settings = get_settings()
        database_url = database_url or settings.database_url
        schema = schema or settings.db_schema

    conn = psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)
    # Outside a transaction so a later rollback does not undo it.
    conn.autocommit = True
    conn.execute(
        sql.SQL("SET search_path TO {}, public, extensions").format(sql.Identifier(schema))
    )
    conn.autocommit = False
    return conn

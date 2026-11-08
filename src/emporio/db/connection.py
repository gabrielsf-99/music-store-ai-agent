import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool

from emporio.config import get_settings

CONNECT_TIMEOUT_SECONDS = 10


def _resolve(database_url: str | None, schema: str | None) -> tuple[str, str]:
    if database_url is None or schema is None:
        settings = get_settings()
        database_url = database_url or settings.database_url
        schema = schema or settings.db_schema
    return database_url, schema


def set_search_path(conn: psycopg.Connection, schema: str) -> None:
    """Point unqualified names to the application schema.

    `extensions` is included because Supabase installs extensions there. Runs outside a
    transaction so a later rollback does not undo it.
    """
    autocommit = conn.autocommit
    conn.autocommit = True
    conn.execute(
        sql.SQL("SET search_path TO {}, public, extensions").format(sql.Identifier(schema))
    )
    conn.autocommit = autocommit


def connect(database_url: str | None = None, schema: str | None = None) -> psycopg.Connection:
    database_url, schema = _resolve(database_url, schema)
    conn = psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)
    set_search_path(conn, schema)
    return conn


def create_pool(
    database_url: str | None = None,
    schema: str | None = None,
    max_size: int = 5,
    autocommit: bool = False,
) -> ConnectionPool:
    """Connection pool. `autocommit=True` is what LangGraph's PostgresSaver requires.

    `prepare_threshold=None` disables prepared statements, which Supabase poolers reject.
    """
    database_url, schema = _resolve(database_url, schema)
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=max_size,
        kwargs={
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            "autocommit": autocommit,
            "prepare_threshold": None,
        },
        configure=lambda conn: set_search_path(conn, schema),
        open=True,
    )

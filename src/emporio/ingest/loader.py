"""Create the schema and replace all table contents in a single transaction."""

from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from emporio.ingest.cleaning import Dataset

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"

# Parents before children, so foreign keys are satisfied on insert.
LOAD_ORDER = ("categories", "products", "promotions", "customers", "orders", "order_items")


def apply_schema(conn: psycopg.Connection, schema: str) -> None:
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


def _insert(conn: psycopg.Connection, table: str, records: list[dict]) -> None:
    if not records:
        return
    columns = list(records[0])
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(columns)),
    )
    rows = [[Jsonb(r[c]) if isinstance(r[c], dict) else r[c] for c in columns] for r in records]
    with conn.cursor() as cur:
        cur.executemany(query, rows)


def load(conn: psycopg.Connection, data: Dataset, policy_chunks: list[dict], schema: str) -> None:
    tables = (*LOAD_ORDER, "policy_chunks")
    with conn.transaction():
        apply_schema(conn, schema)
        conn.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(map(sql.Identifier, tables))))
        for table in LOAD_ORDER:
            _insert(conn, table, getattr(data, table))
        _insert(conn, "policy_chunks", policy_chunks)

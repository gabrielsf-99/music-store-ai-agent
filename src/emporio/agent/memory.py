from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool


def create_checkpointer(autocommit_pool: ConnectionPool) -> PostgresSaver:
    """Conversation history in Postgres, keyed by thread_id. Creates its tables if needed."""
    saver = PostgresSaver(autocommit_pool)
    saver.setup()
    return saver

"""One agent per process, shared by all web sessions (each session has its own thread_id)."""

import atexit
import threading

from langgraph.graph.state import CompiledStateGraph

from emporio.agent.graph import build_agent
from emporio.agent.memory import create_checkpointer
from emporio.db.connection import create_pool

_lock = threading.Lock()
_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _graph
    with _lock:
        if _graph is None:
            pool = create_pool(max_size=10)
            memory_pool = create_pool(max_size=5, autocommit=True)
            atexit.register(pool.close)
            atexit.register(memory_pool.close)
            _graph = build_agent(pool, checkpointer=create_checkpointer(memory_pool))
        return _graph

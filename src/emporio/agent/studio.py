"""Graph exposed to `langgraph dev` / LangGraph Studio (see langgraph.json).

Same agent as the CLI and the web chat, but without our PostgresSaver: the LangGraph server
brings its own persistence for threads.
"""

from emporio.agent.graph import build_agent
from emporio.db.connection import create_pool

graph = build_agent(create_pool())

"""Terminal chat with the agent. Conversations are saved in Postgres.

Interactive:  uv run python -m emporio.cli
Scripted:     uv run python -m emporio.cli -m "Quanto custa o Takamine GD20?" -m "E no PIX?"
Resume:       uv run python -m emporio.cli --thread <id>
"""

import argparse
import json
import uuid

from langchain_core.messages import HumanMessage

from emporio.agent.graph import build_agent
from emporio.agent.memory import create_checkpointer
from emporio.db.connection import create_pool

EXIT_COMMANDS = {"sair", "exit", "quit"}


def _print_updates(graph, text: str, config: dict) -> None:
    for update in graph.stream({"messages": [HumanMessage(text)]}, config, stream_mode="updates"):
        for node, payload in update.items():
            if node == "guardrail" and payload.get("scope") != "in_scope":
                print(f"  [guardrail] {payload['scope']}")
            if node not in ("agent", "guardrail"):
                continue
            for message in payload.get("messages", []):
                for call in message.tool_calls:
                    args = json.dumps(call["args"], ensure_ascii=False)
                    print(f"  [tool] {call['name']}({args})")
                if message.text:
                    print(f"\nEmpório: {message.text}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-m", "--message", action="append", help="mensagem (pode repetir)")
    parser.add_argument("--thread", help="id de uma conversa anterior, para continuá-la")
    args = parser.parse_args(argv)

    thread_id = args.thread or f"cli-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    with create_pool() as pool, create_pool(max_size=2, autocommit=True) as memory_pool:
        graph = build_agent(pool, checkpointer=create_checkpointer(memory_pool))
        print(f"Conversa: {thread_id}  (para continuar depois: --thread {thread_id})")

        if args.message:
            for text in args.message:
                print(f"\nVocê: {text}")
                _print_updates(graph, text, config)
            return

        print("Empório da Música — digite 'sair' para encerrar.")
        while True:
            try:
                text = input("\nVocê: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text.lower() in EXIT_COMMANDS:
                break
            if text:
                _print_updates(graph, text, config)


if __name__ == "__main__":
    main()

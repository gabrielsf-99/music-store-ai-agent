"""Run the evaluation set against the agent and write a Markdown report.

uv run python -m evals.run                                   # model from LLM_MODEL
uv run python -m evals.run --models openai/gpt-6-luna-pro anthropic/claude-haiku-5.5
uv run python -m evals.run --cases catalog_price store_address

Uses the real ingested data (DATABASE_URL) and the OpenRouter key; each run costs tokens.
"""

import argparse
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from emporio.agent.graph import build_agent
from emporio.config import get_settings
from emporio.db.connection import create_pool
from evals.scoring import Summary, TurnResult, resolve_placeholders, score_turn, summarize

EVALS_DIR = Path(__file__).parent
DATASET = EVALS_DIR / "dataset.yaml"
REPORTS_DIR = EVALS_DIR / "reports"
MODELS_URL = "https://openrouter.ai/api/v1/models"

log = logging.getLogger("evals")


@dataclass
class TurnRecord:
    user: str
    answer: str
    tools: list[str]
    scope: str
    seconds: float
    result: TurnResult


@dataclass
class CaseRecord:
    id: str
    category: str
    turns: list[TurnRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and all(t.result.ok for t in self.turns)

    @property
    def problems(self) -> list[str]:
        if self.error:
            return [f"erro: {self.error}"]
        return [p for t in self.turns for p in t.result.problems]


def load_prices() -> dict[str, tuple[float, float]]:
    """USD per token (input, output) for each OpenRouter model."""
    data = httpx.get(MODELS_URL, timeout=30).raise_for_status().json()["data"]
    return {
        m["id"]: (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])) for m in data
    }


CONTACT_QUERIES = {
    "email": "SELECT c.email FROM orders JOIN customers c USING (customer_id) WHERE order_id = %s",
    "phone": "SELECT c.phone FROM orders JOIN customers c USING (customer_id) WHERE order_id = %s",
}


def contact_lookup(pool):
    def lookup(kind: str, order_id: int) -> str:
        with pool.connection() as conn:
            row = conn.execute(CONTACT_QUERIES[kind], (order_id,)).fetchone()
        if row is None:
            raise ValueError(f"order {order_id} not found for placeholder")
        return row[0]

    return lookup


def run_case(agent, case: dict, lookup) -> CaseRecord:
    record = CaseRecord(id=case["id"], category=case["category"])
    usage = UsageMetadataCallbackHandler()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "callbacks": [usage]}
    try:
        for turn in case["turns"]:
            text = resolve_placeholders(turn["user"], lookup)
            before = len(agent.get_state(config).values.get("messages", []))
            started = time.perf_counter()
            result = agent.invoke({"messages": [HumanMessage(text)]}, config)
            seconds = time.perf_counter() - started
            new = result["messages"][before:]
            tools = [c["name"] for m in new if isinstance(m, AIMessage) for c in m.tool_calls]
            answer = result["messages"][-1].text
            scope = result.get("scope", "in_scope")
            record.turns.append(
                TurnRecord(
                    user=turn["user"],  # the template, never the resolved contact
                    answer=answer,
                    tools=tools,
                    scope=scope,
                    seconds=seconds,
                    result=score_turn(turn, answer, tools, scope),
                )
            )
    except Exception as exc:  # one broken case must not stop the run
        log.exception("case %s failed", case["id"])
        record.error = f"{type(exc).__name__}: {exc}"
    for totals in usage.usage_metadata.values():
        record.input_tokens += totals.get("input_tokens", 0)
        record.output_tokens += totals.get("output_tokens", 0)
    return record


def evaluate_model(model: str, cases: list[dict], workers: int, price: tuple[float, float]):
    settings = get_settings().model_copy(update={"llm_model": model})
    with create_pool(max_size=workers + 1) as pool:
        agent = build_agent(pool, settings, checkpointer=InMemorySaver())
        lookup = contact_lookup(pool)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            records = list(executor.map(lambda c: run_case(agent, c, lookup), cases))

    cost = sum(r.input_tokens * price[0] + r.output_tokens * price[1] for r in records)
    errored = [
        [TurnResult(routing_ok=False, facts_ok=False)] * max(1, len(c["turns"]))
        for c, r in zip(cases, records, strict=True)
        if r.error
    ]
    summary = summarize(
        [[t.result for t in r.turns] for r in records if not r.error] + errored,
        [t.seconds for r in records for t in r.turns],
        cost,
    )
    return records, summary


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _num(value: float, decimals: int = 0) -> str:
    """pt-BR number: 48.289 / 11,0."""
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def summary_row(model: str, s: Summary, records: list[CaseRecord]) -> str:
    cost_per_case = s.cost_usd / s.cases if s.cases else 0
    tokens = sum(r.input_tokens + r.output_tokens for r in records)
    return (
        f"| `{model}` | {s.cases_passed}/{s.cases} | {_pct(s.routing_accuracy)} "
        f"| {_pct(s.facts_accuracy)} | {_num(s.latency_p50, 1)} s | {_num(s.latency_p95, 1)} s "
        f"| {_num(tokens)} | US$ {_num(s.cost_usd, 4)} | US$ {_num(cost_per_case, 5)} |"
    )


SUMMARY_HEADER = (
    "| Modelo | Casos ok | Roteamento | Fatos | Latência p50 | Latência p95 | Tokens "
    "| Custo total | Custo/caso |\n|---|---|---|---|---|---|---|---|---|"
)


def model_report(model: str, records: list[CaseRecord], summary: Summary, when: str) -> str:
    lines = [
        f"# Avaliação — `{model}`",
        "",
        f"Executada em {when}, com {summary.cases} casos de `evals/dataset.yaml`.",
        "Roteamento: guardrail e tools certos por turno. Fatos: turnos com fatos esperados que"
        " acertaram. Latência por turno (inclui guardrail e tools).",
        "",
        SUMMARY_HEADER,
        summary_row(model, summary, records),
        "",
        "## Por categoria",
        "",
        "| Categoria | Casos ok |",
        "|---|---|",
    ]
    for category in dict.fromkeys(r.category for r in records):
        group = [r for r in records if r.category == category]
        lines.append(f"| {category} | {sum(r.ok for r in group)}/{len(group)} |")
    lines += ["", "## Casos", "", "| Caso | Resultado | Latência | Tools | Problemas |"]
    lines.append("|---|---|---|---|---|")
    for r in records:
        seconds = sum(t.seconds for t in r.turns)
        tools = " → ".join(", ".join(t.tools) or "—" for t in r.turns) or "—"
        problems = "; ".join(r.problems).replace("|", "\\|") or ""
        status = "✅" if r.ok else "❌"
        lines.append(f"| `{r.id}` | {status} | {_num(seconds, 1)} s | {tools} | {problems} |")
    return "\n".join(lines) + "\n"


def comparison_report(results: dict, when: str) -> str:
    lines = [
        "# Comparação de modelos",
        "",
        f"Executada em {when}. Detalhes por modelo nos relatórios da mesma data.",
        "",
        SUMMARY_HEADER,
    ]
    for model, (records, summary) in results.items():
        lines.append(summary_row(model, summary, records))
    ids = [r.id for r in next(iter(results.values()))[0]]
    lines += ["", "## Casos", "", "| Caso | " + " | ".join(f"`{m}`" for m in results) + " |"]
    lines.append("|---|" + "---|" * len(results))
    for i, case_id in enumerate(ids):
        marks = ["✅" if records[i].ok else "❌" for records, _ in results.values()]
        lines.append(f"| `{case_id}` | " + " | ".join(marks) + " |")
    return "\n".join(lines) + "\n"


def _slug(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--models", nargs="+", help="modelos do OpenRouter (padrão: LLM_MODEL)")
    parser.add_argument("--cases", nargs="+", help="ids dos casos (padrão: todos)")
    parser.add_argument("--workers", type=int, default=4, help="casos em paralelo")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(message)s")

    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    if args.cases:
        cases = [c for c in cases if c["id"] in args.cases]
    models = args.models or [get_settings().llm_model]
    prices = load_prices()
    unknown = [m for m in models if m not in prices]
    if unknown:
        raise SystemExit(f"modelos não encontrados no OpenRouter: {', '.join(unknown)}")

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    when = datetime.now().strftime("%d/%m/%Y %H:%M")
    (REPORTS_DIR / "raw").mkdir(parents=True, exist_ok=True)
    results = {}
    for model in models:
        print(f"Avaliando {model} ({len(cases)} casos)...", flush=True)
        records, summary = evaluate_model(model, cases, args.workers, prices[model])
        results[model] = (records, summary)
        report = REPORTS_DIR / f"{stamp}-{_slug(model)}.md"
        report.write_text(model_report(model, records, summary, when), encoding="utf-8")
        raw = REPORTS_DIR / "raw" / f"{stamp}-{_slug(model)}.json"
        raw.write_text(
            json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  {summary.cases_passed}/{summary.cases} casos ok -> {report}")
        for r in records:
            if not r.ok:
                print(f"  ❌ {r.id}: {'; '.join(r.problems)}")

    if len(models) > 1:
        comparison = REPORTS_DIR / f"{stamp}-comparison.md"
        comparison.write_text(comparison_report(results, when), encoding="utf-8")
        print(f"Comparação -> {comparison}")


if __name__ == "__main__":
    main()

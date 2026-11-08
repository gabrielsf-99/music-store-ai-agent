"""Pure scoring of agent turns against the expectations in dataset.yaml."""

import re
import statistics
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

PLACEHOLDER = re.compile(r"\{order_(email|phone):(\d+)\}")


def normalize(text: str) -> str:
    """Lowercase, no accents, single spaces (also folds non-breaking spaces)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.split())


def resolve_placeholders(text: str, lookup: Callable[[str, int], str]) -> str:
    """Replace {order_email:N} / {order_phone:N} with `lookup(kind, order_id)`."""
    return PLACEHOLDER.sub(lambda m: lookup(m.group(1), int(m.group(2))), text)


@dataclass
class TurnResult:
    routing_ok: bool
    facts_ok: bool | None  # None when the turn has no fact expectations
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.routing_ok and self.facts_ok is not False


def score_turn(expect: dict, answer: str, tools: list[str], scope: str) -> TurnResult:
    problems = []

    accepted_scopes = expect.get("scope", "in_scope")
    if isinstance(accepted_scopes, str):
        accepted_scopes = [accepted_scopes]
    routing_ok = scope in accepted_scopes
    if not routing_ok:
        problems.append(f"guardrail: {scope} (esperado: {', '.join(accepted_scopes)})")

    if "tools" in expect:
        expected_tools = expect["tools"]
        called = sorted(set(tools))
        if expected_tools == [] and called:
            routing_ok = False
            problems.append(f"tools chamadas sem necessidade: {', '.join(called)}")
        elif expected_tools and not set(expected_tools) & set(called):
            routing_ok = False
            got = ", ".join(called) or "nenhuma"
            problems.append(f"tools: {got} (esperado uma de: {', '.join(expected_tools)})")

    text = normalize(answer)
    facts_ok = None
    if any(key in expect for key in ("facts", "facts_any", "forbid")):
        missing = [f for f in expect.get("facts", []) if normalize(f) not in text]
        any_facts = expect.get("facts_any", [])
        any_missing = bool(any_facts) and not any(normalize(f) in text for f in any_facts)
        present = [f for f in expect.get("forbid", []) if normalize(f) in text]
        facts_ok = not (missing or any_missing or present)
        if missing:
            problems.append(f"faltou: {', '.join(missing)}")
        if any_missing:
            problems.append(f"faltou um de: {', '.join(any_facts)}")
        if present:
            problems.append(f"não deveria conter: {', '.join(present)}")

    return TurnResult(routing_ok=routing_ok, facts_ok=facts_ok, problems=problems)


@dataclass
class Summary:
    cases: int
    cases_passed: int
    routing_accuracy: float
    facts_accuracy: float
    latency_p50: float
    latency_p95: float
    cost_usd: float


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


def summarize(
    turns_by_case: list[list[TurnResult]], latencies: list[float], cost_usd: float
) -> Summary:
    turns = [t for case in turns_by_case for t in case]
    with_facts = [t for t in turns if t.facts_ok is not None]
    return Summary(
        cases=len(turns_by_case),
        cases_passed=sum(all(t.ok for t in case) for case in turns_by_case),
        routing_accuracy=sum(t.routing_ok for t in turns) / len(turns) if turns else 0.0,
        facts_accuracy=sum(bool(t.facts_ok) for t in with_facts) / len(with_facts)
        if with_facts
        else 0.0,
        latency_p50=statistics.median(latencies) if latencies else 0.0,
        latency_p95=percentile(latencies, 95),
        cost_usd=cost_usd,
    )

"""Hybrid retrieval over the policy manual.

Subsections are ranked by vector similarity and by full-text match (Portuguese dictionary),
fused with Reciprocal Rank Fusion. The agent receives the best *top-level* sections in full,
because policy questions are often broad ("qual a garantia?") and the answer spans subsections.
"""

from dataclasses import dataclass

import psycopg

from emporio.rag.embeddings import Embedder, to_pgvector

DEFAULT_TOP_SECTIONS = 2
RRF_K = 60

_RANK_QUERY = """
WITH q AS (
    SELECT %(vector)s::vector AS v,
           replace(plainto_tsquery('portuguese', %(question)s)::text, '&', '|')::tsquery AS tq
),
ranked AS (
    SELECT section, row_number() OVER (ORDER BY embedding <=> q.v) AS position
    FROM policy_chunks, q
    UNION ALL
    SELECT section, row_number() OVER (ORDER BY ts_rank_cd(search_doc, q.tq) DESC)
    FROM policy_chunks, q
    WHERE search_doc @@ q.tq
)
SELECT c.section, c.top_section, sum(1.0 / (%(rrf_k)s + r.position)) AS score
FROM ranked r
JOIN policy_chunks c USING (section)
GROUP BY c.section, c.top_section
ORDER BY score DESC
"""

_SECTIONS_QUERY = """
SELECT section, top_section, title, parent_title, content
FROM policy_chunks
WHERE top_section = ANY(%s)
ORDER BY string_to_array(section, '.')::int[]
"""


@dataclass(frozen=True)
class PolicySection:
    section: str
    title: str
    content: str
    matched_subsections: list[str]
    score: float


def assemble_sections(
    ranked: list[tuple[str, str, float]], chunks: list[tuple], k: int
) -> list[PolicySection]:
    """Group ranked subsections into their top-level sections, best section first.

    `ranked`: (section, top_section, score), best first.
    `chunks`: (section, top_section, title, parent_title, content), in document order.
    """
    best_score: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for section, top, score in ranked:
        best_score.setdefault(top, float(score))
        matched.setdefault(top, []).append(section)
    tops = list(best_score)[:k]

    by_top: dict[str, list[tuple]] = {top: [] for top in tops}
    for chunk in chunks:
        if chunk[1] in by_top:
            by_top[chunk[1]].append(chunk)

    results = []
    for top in tops:
        parts, title = [], None
        for section, _, chunk_title, parent_title, content in by_top[top]:
            if section == top:
                title = chunk_title
                parts.append(content)
            else:
                title = title or parent_title
                parts.append(f"{section} {chunk_title}\n{content}")
        results.append(
            PolicySection(
                section=top,
                title=title or "",
                content="\n\n".join(parts),
                matched_subsections=matched[top],
                score=best_score[top],
            )
        )
    return results


def search_policies(
    conn: psycopg.Connection, embed: Embedder, question: str, k: int = DEFAULT_TOP_SECTIONS
) -> list[PolicySection]:
    params = {"vector": to_pgvector(embed([question])[0]), "question": question, "rrf_k": RRF_K}
    ranked = conn.execute(_RANK_QUERY, params).fetchall()
    tops = list(dict.fromkeys(top for _, top, _ in ranked))[:k]
    chunks = conn.execute(_SECTIONS_QUERY, (tops,)).fetchall()
    return assemble_sections(ranked, chunks, k)

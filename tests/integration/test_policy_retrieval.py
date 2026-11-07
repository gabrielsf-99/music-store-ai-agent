"""Hybrid policy retrieval against the synthetic manual (see POLICY_PAGES in tests/conftest.py)."""

import pytest

from emporio.rag.embeddings import embed_texts
from emporio.rag.retriever import search_policies

pytestmark = pytest.mark.integration


def test_policy_chunks_are_loaded_with_embeddings(loaded_conn):
    rows = loaded_conn.execute(
        "SELECT section, vector_dims(embedding) FROM policy_chunks ORDER BY section"
    ).fetchall()

    assert rows == [(s, 384) for s in ["1", "1.1", "2", "2.1", "3.1", "3.2", "4"]]


@pytest.mark.parametrize(
    ("question", "expected_section"),
    [
        ("Me arrependi da compra, posso devolver?", "3"),
        ("Em quantas vezes posso parcelar no cartão?", "2"),
        ("Qual é a garantia dos instrumentos?", "4"),
        ("Meu instrumento chegou com defeito", "3"),
    ],
)
def test_question_retrieves_expected_section_first(loaded_conn, question, expected_section):
    sections = search_policies(loaded_conn, embed_texts, question)

    assert sections[0].section == expected_section


def test_returns_full_top_level_section(loaded_conn):
    trocas = search_policies(loaded_conn, embed_texts, "posso devolver?")[0]

    assert trocas.title == "Trocas e Devoluções"
    assert "7 dias corridos" in trocas.content
    assert "30 dias corridos" in trocas.content

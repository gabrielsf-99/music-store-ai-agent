import pytest

from emporio.tools.catalog import match_categories

CATEGORIES = {
    1: "Guitarras",
    2: "Baixos",
    3: "Baterias e Percussão",
    4: "Teclados e Pianos",
    5: "Violões",
    6: "Instrumentos de Sopro (Madeiras)",
    7: "Instrumentos de Sopro (Metais)",
    8: "Cordas Orquestrais",
    9: "Ukuleles",
}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Violões", [5]),
        ("violão", [5]),
        ("VIOLAO", [5]),
        ("ukulele", [9]),
        ("guitarra", [1]),
        ("piano", [4]),
        ("bateria", [3]),
        ("sopro", [6, 7]),
    ],
)
def test_match_categories(query, expected):
    assert match_categories(CATEGORIES, query) == expected


@pytest.mark.parametrize("query", ["amplificador", "cordas de aço", "xyz"])
def test_match_categories_returns_empty_when_nothing_is_close(query):
    assert match_categories(CATEGORIES, query) == []

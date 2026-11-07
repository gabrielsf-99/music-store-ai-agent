from emporio.rag.retriever import assemble_sections

RANKED = [
    ("4.2", "4", 0.030),
    ("8.1", "8", 0.020),
    ("4", "4", 0.010),
    ("3.1", "3", 0.005),
]
CHUNKS = [
    ("4", "4", "Trocas", None, "Introdução das trocas."),
    ("4.1", "4", "Arrependimento", "Trocas", "Até 7 dias."),
    ("4.2", "4", "Defeito", "Trocas", "Até 30 dias."),
    ("8.1", "8", "Garantia Legal", "Garantia", "90 dias."),
]


def test_returns_best_top_level_sections_in_order():
    sections = assemble_sections(RANKED, CHUNKS, k=2)

    assert [s.section for s in sections] == ["4", "8"]
    assert sections[0].score == 0.030
    assert sections[0].matched_subsections == ["4.2", "4"]


def test_section_content_includes_every_subsection_in_document_order():
    trocas = assemble_sections(RANKED, CHUNKS, k=2)[0]

    assert trocas.title == "Trocas"
    assert trocas.content == (
        "Introdução das trocas.\n\n4.1 Arrependimento\nAté 7 dias.\n\n4.2 Defeito\nAté 30 dias."
    )


def test_title_comes_from_parent_when_section_has_no_intro():
    garantia = assemble_sections(RANKED, CHUNKS, k=2)[1]

    assert garantia.title == "Garantia"
    assert garantia.content == "8.1 Garantia Legal\n90 dias."

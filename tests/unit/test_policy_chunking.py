from emporio.ingest.pipeline import build_policy_chunks
from emporio.ingest.policies import clean_line, split_sections

# Shaped like pypdf's layout extraction: page furniture, column gaps, indented lists.
LAYOUT_TEXT = """\
Empório da Música Manual de Políticas e Procedimentos
Texto de capa, antes da primeira seção

1. Sobre a Loja
Texto da seção um.
1.1 Contato
          Campo                 Informação
 Telefone                (67) 0000-0000
2. Pagamento
    •    Parcelamento em até 3x
         sem juros.
2.1 Regras
    1.   Primeiro passo.
1. Item numerado sem indentação
2.2 Mais Regras
Texto.
                                   Página 2
Empório da Música Manual de Políticas e Procedimentos
continuação de 2.2
3. Garantia
Noventa dias.
"""


def _by_section(chunks):
    return {chunk.section: chunk for chunk in chunks}


def test_splits_on_numbered_headings_only():
    chunks = split_sections(LAYOUT_TEXT)

    assert [c.section for c in chunks] == ["1", "1.1", "2", "2.1", "2.2", "3"]


def test_numbered_list_items_stay_in_section_content():
    content = _by_section(split_sections(LAYOUT_TEXT))["2.1"].content

    assert content == "1. Primeiro passo.\n1. Item numerado sem indentação"


def test_page_header_and_footer_are_removed_and_section_continues():
    assert _by_section(split_sections(LAYOUT_TEXT))["2.2"].content == "Texto.\ncontinuação de 2.2"


def test_tables_and_bullets_become_readable_lines():
    sections = _by_section(split_sections(LAYOUT_TEXT))

    assert sections["1.1"].content == "Campo | Informação\nTelefone | (67) 0000-0000"
    assert sections["2"].content == "- Parcelamento em até 3x\nsem juros."


def test_subsections_carry_parent_title():
    chunk = _by_section(split_sections(LAYOUT_TEXT))["2.1"]

    assert chunk.top_section == "2"
    assert chunk.parent_title == "Pagamento"
    assert chunk.heading == "Pagamento > 2.1 Regras"
    assert chunk.embedding_text.startswith("Pagamento > 2.1 Regras\n")


def test_text_before_first_section_is_ignored():
    assert all("capa" not in c.content for c in split_sections(LAYOUT_TEXT))


def test_clean_line():
    assert clean_line("                                   Página 12") == ""
    assert clean_line("    •    Item") == "- Item"
    assert clean_line(" PIX        Pagamento à vista") == "PIX | Pagamento à vista"


def test_generated_pdf_is_extracted_and_split(fixture_data_dir):
    chunks = build_policy_chunks(fixture_data_dir)

    assert [c.section for c in chunks] == ["1", "1.1", "2", "2.1", "3.1", "3.2", "4"]
    defect = _by_section(chunks)["3.2"]
    assert "30 dias corridos" in defect.content
    assert "1. Entre em contato com a loja." in defect.content
    assert "Página" not in defect.content

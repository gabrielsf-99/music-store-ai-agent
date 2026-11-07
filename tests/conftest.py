import shutil
from pathlib import Path

import pytest
from psycopg import sql

from emporio.db.connection import connect
from emporio.ingest.pipeline import POLICIES_FILE, run

FIXTURE_CSV_DIR = Path(__file__).parent / "fixtures" / "data"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
TEST_SCHEMA = "emporio"

PAGE_HEADER = "Empório da Música Manual de Políticas e Procedimentos"

# Synthetic policy manual: (indent in mm, text). None starts a new page.
POLICY_PAGES = [
    (0, PAGE_HEADER),
    (0, "1. Sobre a Loja"),
    (0, "A Loja Exemplo vende apenas instrumentos musicais, sem acessórios."),
    (0, "1.1 Contato"),
    (0, "Telefone: (67) 0000-0000."),
    (0, "2. Formas de Pagamento"),
    (0, "Aceitamos PIX, cartão de crédito e boleto bancário."),
    (0, "2.1 Parcelamento"),
    (5, "- Parcelamento no cartão de crédito em até 10x sem juros."),
    (0, "3. Trocas e Devoluções"),
    (0, "3.1 Direito de Arrependimento"),
    (5, "- O cliente pode devolver a compra em até 7 dias corridos após o recebimento."),
    (0, "3.2 Produto com Defeito"),
    (5, "- Produtos com defeito de fabricação podem ser trocados em até 30 dias corridos."),
    (10, "1. Entre em contato com a loja."),
    (10, "2. Envie fotos do defeito."),
    (80, "Página 1"),
    None,
    (0, PAGE_HEADER),
    (0, "4. Garantia"),
    (0, "Todos os instrumentos têm garantia legal de 90 dias contra defeitos de fabricação."),
    (80, "Página 2"),
]


def write_policy_pdf(path: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    pdf.add_page()
    for entry in POLICY_PAGES:
        if entry is None:
            pdf.add_page()
            continue
        indent, text = entry
        pdf.set_x(pdf.l_margin + indent)
        pdf.cell(text=text, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


@pytest.fixture(scope="session")
def fixture_data_dir(tmp_path_factory) -> Path:
    """Synthetic CSVs plus a generated policy PDF."""
    data_dir = tmp_path_factory.mktemp("data")
    for csv_file in FIXTURE_CSV_DIR.glob("*.csv"):
        shutil.copy(csv_file, data_dir)
    write_policy_pdf(data_dir / POLICIES_FILE)
    return data_dir


@pytest.fixture
def test_schema() -> str:
    return TEST_SCHEMA


@pytest.fixture(scope="session")
def database_url():
    """Ephemeral Postgres container, started only by tests that need a database."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE, driver=None) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def conn(database_url):
    with connect(database_url, TEST_SCHEMA) as conn:
        yield conn
        conn.rollback()
        drop = sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(TEST_SCHEMA))
        conn.execute(drop)
        conn.commit()


@pytest.fixture
def loaded_conn(conn, fixture_data_dir):
    """Connection with the synthetic fixture dataset already ingested (real embeddings)."""
    run(fixture_data_dir, conn, TEST_SCHEMA)
    return conn

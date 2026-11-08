import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import psycopg

from emporio.ingest import cleaning
from emporio.ingest.checks import check_integrity, find_inconsistencies
from emporio.ingest.cleaning import Dataset, DataValidationError
from emporio.ingest.loader import LOAD_ORDER, load
from emporio.ingest.policies import PolicyChunk, extract_pdf_text, split_sections
from emporio.rag.embeddings import Embedder, embed_texts, to_pgvector

CLEANERS = {
    "categories": cleaning.clean_category,
    "products": cleaning.clean_product,
    "promotions": cleaning.clean_promotion,
    "customers": cleaning.clean_customer,
    "orders": cleaning.clean_order,
    "order_items": cleaning.clean_order_item,
}

POLICIES_FILE = "store_policies.pdf"
POLICIES_ALIASES = (POLICIES_FILE, "politicas_da_loja.pdf")
POLICIES_KEY = "policies"


class MissingInputFilesError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class IngestReport:
    counts: dict[str, int]
    warnings: list[str]


def _normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _matches_table(name: str, table: str) -> bool:
    """`orders.csv` or an exported name ending in it, e.g. `export - orders.csv`."""
    return re.fullmatch(rf"(.*[\s_-])?{table}\.csv", name) is not None


def locate_input_files(data_dir: Path) -> dict[str, Path]:
    """Path of each input file, keyed by table name (and `policies` for the PDF).

    Exact names win; otherwise accepts the policy manual as `políticas_da_loja.pdf` and CSVs
    whose name ends in ` - <table>.csv`, as the files are sometimes exported.
    """
    if not data_dir.is_dir():
        raise MissingInputFilesError(f"data folder not found: {data_dir} (see data/README.md)")
    files = {_normalize_name(p.name): p for p in data_dir.iterdir() if p.is_file()}
    found: dict[str, Path] = {}
    missing: list[str] = []
    for table in CLEANERS:
        exact = files.get(f"{table}.csv")
        candidates = [exact] if exact else [p for n, p in files.items() if _matches_table(n, table)]
        if len(candidates) > 1:
            names = ", ".join(sorted(p.name for p in candidates))
            raise MissingInputFilesError(f"more than one file for {table}.csv: {names}")
        if candidates:
            found[table] = candidates[0]
        else:
            missing.append(f"{table}.csv")
    policies = next((files[a] for a in POLICIES_ALIASES if a in files), None)
    if policies:
        found[POLICIES_KEY] = policies
    else:
        missing.append(POLICIES_FILE)
    if missing:
        raise MissingInputFilesError(
            f"missing input files in {data_dir}: {', '.join(missing)} (see data/README.md)"
        )
    return found


def read_csv(path: Path) -> list[cleaning.Row]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def build_dataset(data_dir: Path) -> Dataset:
    """Read, clean and validate all CSVs. Raises on any invalid data."""
    files = locate_input_files(data_dir)
    tables = {
        table: cleaning.clean_rows(files[table].name, read_csv(files[table]), clean)
        for table, clean in CLEANERS.items()
    }
    data = Dataset(**tables)
    check_integrity(data)
    return data


def build_policy_chunks(data_dir: Path) -> list[PolicyChunk]:
    path = locate_input_files(data_dir)[POLICIES_KEY]
    chunks = split_sections(extract_pdf_text(path))
    if not chunks:
        raise DataValidationError(f"{path.name}: no numbered sections found")
    return chunks


def run(
    data_dir: Path, conn: psycopg.Connection, schema: str, embed: Embedder = embed_texts
) -> IngestReport:
    data = build_dataset(data_dir)
    warnings = find_inconsistencies(data)
    chunks = build_policy_chunks(data_dir)
    vectors = embed([chunk.embedding_text for chunk in chunks])
    policy_records = [
        {
            "section": chunk.section,
            "top_section": chunk.top_section,
            "title": chunk.title,
            "parent_title": chunk.parent_title,
            "content": chunk.content,
            "embedding": to_pgvector(vector),
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    load(conn, data, policy_records, schema)
    counts = {table: len(getattr(data, table)) for table in LOAD_ORDER}
    counts["policy_chunks"] = len(policy_records)
    return IngestReport(counts=counts, warnings=warnings)

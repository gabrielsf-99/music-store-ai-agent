import csv
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
REQUIRED_FILES = (*(f"{table}.csv" for table in CLEANERS), POLICIES_FILE)


class MissingInputFilesError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class IngestReport:
    counts: dict[str, int]
    warnings: list[str]


def check_input_files(data_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (data_dir / name).is_file()]
    if missing:
        raise MissingInputFilesError(
            f"missing input files in {data_dir}: {', '.join(missing)} (see data/README.md)"
        )


def read_csv(path: Path) -> list[cleaning.Row]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def build_dataset(data_dir: Path) -> Dataset:
    """Read, clean and validate all CSVs. Raises on any invalid data."""
    check_input_files(data_dir)
    tables = {
        table: cleaning.clean_rows(f"{table}.csv", read_csv(data_dir / f"{table}.csv"), clean)
        for table, clean in CLEANERS.items()
    }
    data = Dataset(**tables)
    check_integrity(data)
    return data


def build_policy_chunks(data_dir: Path) -> list[PolicyChunk]:
    chunks = split_sections(extract_pdf_text(data_dir / POLICIES_FILE))
    if not chunks:
        raise DataValidationError(f"{POLICIES_FILE}: no numbered sections found")
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

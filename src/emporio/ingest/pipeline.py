import csv
from dataclasses import dataclass
from pathlib import Path

import psycopg

from emporio.ingest import cleaning
from emporio.ingest.checks import check_integrity, find_inconsistencies
from emporio.ingest.cleaning import Dataset
from emporio.ingest.loader import LOAD_ORDER, load

CLEANERS = {
    "categories": cleaning.clean_category,
    "products": cleaning.clean_product,
    "promotions": cleaning.clean_promotion,
    "customers": cleaning.clean_customer,
    "orders": cleaning.clean_order,
    "order_items": cleaning.clean_order_item,
}

REQUIRED_FILES = tuple(f"{table}.csv" for table in CLEANERS)


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


def run(data_dir: Path, conn: psycopg.Connection, schema: str) -> IngestReport:
    data = build_dataset(data_dir)
    warnings = find_inconsistencies(data)
    load(conn, data, schema)
    counts = {table: len(getattr(data, table)) for table in LOAD_ORDER}
    return IngestReport(counts=counts, warnings=warnings)

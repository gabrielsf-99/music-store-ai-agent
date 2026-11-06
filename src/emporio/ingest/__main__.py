"""Load the input CSVs into Postgres: `uv run python -m emporio.ingest [--data-dir data]`."""

import argparse
import logging
import sys
from pathlib import Path

from emporio.config import get_settings
from emporio.db.connection import connect
from emporio.ingest.cleaning import DataValidationError
from emporio.ingest.pipeline import MissingInputFilesError, check_input_files, run

log = logging.getLogger("emporio.ingest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    try:
        check_input_files(args.data_dir)
        schema = get_settings().db_schema
        with connect() as conn:
            report = run(args.data_dir, conn, schema)
    except (MissingInputFilesError, DataValidationError) as exc:
        log.error("%s", exc)
        return 1

    for warning in report.warnings:
        log.warning("%s", warning)
    for table, count in report.counts.items():
        log.info("%-12s %d rows", table, count)
    log.info("loaded into schema '%s'", schema)
    return 0


if __name__ == "__main__":
    sys.exit(main())

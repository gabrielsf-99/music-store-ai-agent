"""Database connectivity check: `uv run python -m emporio.db`."""

from emporio.db.connection import connect


def main() -> None:
    with connect() as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
    print(f"Connected: {version}")


if __name__ == "__main__":
    main()

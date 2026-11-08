import pytest

from emporio.ingest.pipeline import (
    CLEANERS,
    POLICIES_KEY,
    MissingInputFilesError,
    locate_input_files,
)


def _touch(folder, *names):
    for name in names:
        (folder / name).write_text("")


def test_exact_names(tmp_path):
    _touch(tmp_path, *(f"{t}.csv" for t in CLEANERS), "store_policies.pdf")

    files = locate_input_files(tmp_path)

    assert files["orders"].name == "orders.csv"
    assert files[POLICIES_KEY].name == "store_policies.pdf"


def test_original_and_exported_names(tmp_path):
    _touch(tmp_path, *(f"export - {t}.csv" for t in CLEANERS), "políticas_da_loja.pdf")

    files = locate_input_files(tmp_path)

    assert files["orders"].name == "export - orders.csv"
    assert files["order_items"].name == "export - order_items.csv"
    assert files[POLICIES_KEY].name == "políticas_da_loja.pdf"


def test_exact_name_wins_over_exported_one(tmp_path):
    _touch(tmp_path, *(f"{t}.csv" for t in CLEANERS), "export - orders.csv", "store_policies.pdf")

    assert locate_input_files(tmp_path)["orders"].name == "orders.csv"


def test_two_exported_files_for_the_same_table_are_rejected(tmp_path):
    _touch(tmp_path, *(f"{t}.csv" for t in CLEANERS if t != "orders"), "store_policies.pdf")
    _touch(tmp_path, "a - orders.csv", "b - orders.csv")

    with pytest.raises(MissingInputFilesError, match="more than one file for orders.csv"):
        locate_input_files(tmp_path)


def test_missing_files_are_listed(tmp_path):
    _touch(tmp_path, "categories.csv", "myorders.csv")

    with pytest.raises(MissingInputFilesError) as exc:
        locate_input_files(tmp_path)

    assert "orders.csv" in str(exc.value)
    assert "store_policies.pdf" in str(exc.value)
    assert "categories.csv," not in str(exc.value)


def test_missing_folder(tmp_path):
    with pytest.raises(MissingInputFilesError, match="data folder not found"):
        locate_input_files(tmp_path / "nope")

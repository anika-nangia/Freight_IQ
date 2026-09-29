import pytest

from app.data.loaders import clear_dataset_cache, load_bdi, read_bdi_file
from app.errors import DatasetError


def test_real_files_load_deduplicated_and_sorted():
    frame = load_bdi()
    assert len(frame) == 1236  # 3-year file is a subset of the 5-year file
    assert frame["date"].is_monotonic_increasing
    assert not frame["date"].duplicated().any()
    assert frame["price"].min() > 0
    assert str(frame["date"].iloc[0].date()) == "2021-09-27"
    assert str(frame["date"].iloc[-1].date()) == "2026-09-25"


def test_parses_thousands_and_percent(tmp_path):
    csv = tmp_path / "a.csv"
    csv.write_text('Date,Price,Open,High,Low,Vol.,Change %\n25-09-2026,"3,426.00","3,426.00","3,426.00","3,426.00",,-1.35%\n')
    frame = read_bdi_file(csv)
    assert frame["price"].iloc[0] == 3426.0
    assert frame["change_pct"].iloc[0] == -1.35


def test_bad_rows_dropped_and_missing_columns_rejected(tmp_path):
    good = tmp_path / "g.csv"
    good.write_text("Date,Price\n01-01-2026,100\nnot-a-date,5\n02-01-2026,abc\n")
    assert len(read_bdi_file(good)) == 1
    bad = tmp_path / "b.csv"
    bad.write_text("Foo,Bar\n1,2\n")
    with pytest.raises(DatasetError):
        read_bdi_file(bad)


def test_overlapping_files_are_merged(tmp_path):
    (tmp_path / "a.csv").write_text("Date,Price\n01-01-2026,100\n02-01-2026,101\n")
    (tmp_path / "b.csv").write_text("Date,Price\n02-01-2026,101\n03-01-2026,102\n")
    clear_dataset_cache()
    assert len(load_bdi(str(tmp_path))) == 3


def test_empty_directory_raises(tmp_path):
    clear_dataset_cache()
    with pytest.raises(DatasetError):
        load_bdi(str(tmp_path))

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import DATA_DIR, FIXTURES_DIR
from tst.loader import DATA_FILES, DataLoadError, LoadedData, file_hash, load_all
from tst.sim.ledger import ENGINE_ACCOUNTS


def test_real_data_loads(loaded: LoadedData) -> None:
    assert loaded.balance.company.base_monthly_cost_cents == 200_000
    assert loaded.balance.backup.every_n_turns == 12
    assert loaded.balance.backup.keep_periodic == 10
    assert [s.id for s in loaded.game_data.scenarios] == [
        "garage_bootstrap",
        "ex_big_tech_founders",
        "funded_spinout",
        "mineral_first_prospector",
    ]
    selectable = [s.id for s in loaded.game_data.scenarios if s.selectable]
    assert selectable == ["garage_bootstrap", "ex_big_tech_founders", "funded_spinout"]
    assert set(ENGINE_ACCOUNTS) <= loaded.game_data.account_codes()


def test_starting_cash_values_match_formulas(loaded: LoadedData) -> None:
    cash = {k: v.starting_cash_cents for k, v in loaded.balance.scenario.items()}
    assert cash == {
        "garage_bootstrap": 5_000_000,
        "ex_big_tech_founders": 40_000_000,
        "funded_spinout": 150_000_000,
        "mineral_first_prospector": 500_000_000,
    }
    mult = {k: v.starting_cash_mult_bp for k, v in loaded.balance.difficulty.items()}
    assert mult == {"easy": 15_000, "standard": 10_000, "hard": 6_000, "ironman": 10_000}


def test_hashes_cover_every_file(loaded: LoadedData) -> None:
    assert sorted(loaded.hashes) == sorted(DATA_FILES)
    for name, digest in loaded.hashes.items():
        assert digest == file_hash((DATA_DIR / name).read_bytes())
        assert len(digest) == 64


def test_hash_ignores_line_endings() -> None:
    assert file_hash(b"a: 1\r\nb: 2\r\n") == file_hash(b"a: 1\nb: 2\n")


@pytest.fixture
def data_copy(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(DATA_DIR, target)
    return target


def test_broken_fixture_file_fails_clearly(data_copy: Path) -> None:
    shutil.copy(FIXTURES_DIR / "broken_data" / "balance.yaml", data_copy / "balance.yaml")
    with pytest.raises(DataLoadError) as info:
        load_all(data_copy)
    message = str(info.value)
    assert message.startswith("balance.yaml:")
    assert "company.base_monthly_cost_cents" in message
    assert "company.surprise_key" in message
    assert "difficulty" in message


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        (
            "balance.yaml",
            "  funded_spinout:\n    starting_cash_cents: 150000000",
            "  funded_spinoff:\n    starting_cash_cents: 150000000",
            "no scenario.<id> block for ['funded_spinout']",
        ),
        ("scenarios.yaml", "available_in: v3", "available_in: v9", "available_in"),
        (
            "scenarios.yaml",
            "starting_equity_account: 3100_preferred_equity",
            "starting_equity_account: 1000_cash",
            "is not an equity account",
        ),
        ("accounts.yaml", "code: 6900_general_admin", "code: 6901_misc", "engine accounts"),
        ("accounts.yaml", "code: 1100_receivables", "code: 1000_cash", "duplicate account"),
        ("balance.yaml", "  hard:\n", "  harder:\n", "difficulty must define"),
        ("balance.yaml", "every_n_turns: 12", "every_n_turns: 0", "backup.every_n_turns"),
        ("balance.yaml", "backup:\n", "company:\n", "duplicate key"),
        ("scenarios.yaml", "scenarios:", "scenarioz:", "single top-level key"),
    ],
)
def test_bad_data_fails(data_copy: Path, file: str, old: str, new: str, expected: str) -> None:
    _replace(data_copy / file, old, new)
    with pytest.raises(DataLoadError) as info:
        load_all(data_copy)
    assert expected in str(info.value)


def test_missing_file_fails(data_copy: Path) -> None:
    (data_copy / "accounts.yaml").unlink()
    with pytest.raises(DataLoadError, match=r"accounts.yaml: file not found"):
        load_all(data_copy)

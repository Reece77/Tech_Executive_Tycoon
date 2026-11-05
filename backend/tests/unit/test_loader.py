from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import DATA_DIR, FIXTURES_DIR
from tst.loader import DATA_FILES, DataLoadError, LoadedData, file_hash, load_all
from tst.sim.ledger import ENGINE_ACCOUNTS


def test_real_data_loads(loaded: LoadedData) -> None:
    assert loaded.balance.company.base_monthly_cost_cents == 50_000
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
    events = [f"events/{p.name}" for p in (DATA_DIR / "events").glob("*.yaml")]  # M6
    assert (
        sorted(loaded.hashes) == sorted([*DATA_FILES, *events])
        and len(events) == 14  # M10b: crisis.yaml; M10c: executive.yaml; M11: research.yaml
    )  # M7a: founder.yaml; M10: lender.yaml; M12a: facility.yaml; M13: public.yaml
    # M14b: press.yaml
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


# --- M1a seed files -------------------------------------------------------------------------


def test_people_seed_data_loads(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert len(data.skills) == 25
    assert data.personality_keys == [
        "ambition",
        "loyalty",
        "professionalism",
        "temperament",
        "adaptability",
        "risk_appetite",
        "ego",
        "integrity",
        "sociability",
    ]
    assert data.hidden_keys == ["consistency", "burnout_risk", "big_moments", "poachability"]
    assert data.work_style_keys == ["builder", "operator", "researcher", "seller"]
    assert len(data.interests) == 13
    assert len(data.regions) == 7
    assert len(data.roles) == 15  # M12b: hardware engineer, chip designer, manufacturing engineer
    assert len(data.tags) == 9
    assert [b.key for b in data.backgrounds if b.selectable] == [
        "engineer",
        "salesperson",
        "academic",
        "ex_big_tech",
    ]
    assert [p.key for p in data.personality_presets] == [
        "visionary",
        "operator",
        "hustler",
        "scientist",
    ]
    # formulas.md section 1 worked example uses this role definition.
    engineer = data.role("software_engineer")
    assert engineer.primary == ("software_engineering", "infrastructure")
    assert engineer.secondary == ("data", "security", "communication", "product")
    assert engineer.salary_band_mid_cents["senior"] == 11_500_000


def test_names_cover_every_region(loaded: LoadedData) -> None:
    names = loaded.game_data.names
    assert set(names) == set(loaded.game_data.region_keys)
    for region, pool in names.items():
        assert len(pool.first) >= 60, region
        assert len(pool.last) >= 60, region
        assert len(set(pool.first)) == len(pool.first), region
        assert len(set(pool.last)) == len(pool.last), region


@pytest.mark.parametrize(
    ("file", "expected"),
    [
        ("skills.yaml", "skills.0.group"),
        ("personality.yaml", "hidden: Field required"),
        ("interests.yaml", "interests.0.key"),
        ("regions.yaml", "regions.0.salary_multiplier_bp"),
        ("roles.yaml", "salary_band_mid_cents must cover"),
        ("tags.yaml", "tags.0.boost.when.0.op"),
        ("backgrounds.yaml", "backgrounds.0.available_in"),
        ("names.yaml", "names.north_america.last"),
    ],
)
def test_broken_fixture_per_seed_file(data_copy: Path, file: str, expected: str) -> None:
    shutil.copy(FIXTURES_DIR / "broken_data" / file, data_copy / file)
    with pytest.raises(DataLoadError) as info:
        load_all(data_copy)
    message = str(info.value)
    assert message.startswith(f"{file}:"), message
    assert expected in message


@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        (
            "tags.yaml",
            "excludes: [quiet_genius]",
            "excludes: []",
            "'quiet_genius' excludes 'politician' but not the other way round",
        ),
        (
            "tags.yaml",
            '{ attr: ego, op: ">=", value: 15 }',
            '{ attr: coding, op: ">=", value: 15 }',
            "unknown personality traits ['coding']",
        ),
        (
            "roles.yaml",
            "primary: [software_engineering, infrastructure]",
            "primary: [software_engineering, plumbing]",
            "unknown skills ['plumbing']",
        ),
        (
            "roles.yaml",
            "work_style_weights: { builder: 6, operator: 2, researcher: 2, seller: 0 }",
            "work_style_weights: { builder: 6, operator: 2, researcher: 2 }",
            "work_style_weights must cover",
        ),
        (
            "backgrounds.yaml",
            "default_allocation: { software_engineering: 8,",
            "default_allocation: { software_engineering: 9,",
            "'engineer' default_allocation spends 71 points",
        ),
        (
            "backgrounds.yaml",
            "bonuses: { software_engineering: 3, infrastructure: 2 }",
            "bonuses: { software_engineering: 6, infrastructure: 2 }",
            "puts software_engineering at 19",
        ),
        (
            "backgrounds.yaml",
            "values: { ambition: 17, loyalty: 11,",
            "values: { ambition: 17,",
            "preset 'visionary': values must cover",
        ),
        ("balance.yaml", "    oceania: 3\n", "", "region_weights must cover exactly"),
        (
            "balance.yaml",
            "default_region: north_america",
            "default_region: atlantis",
            "founder.default_region 'atlantis'",
        ),
        ("names.yaml", "  oceania:", "  atlantis:", "names.yaml: regions must be exactly"),
        ("balance.yaml", "    - { from_age: 0, value: 45 }\n", "", "first band must start"),
    ],
)
def test_bad_seed_data_fails(data_copy: Path, file: str, old: str, new: str, expected: str) -> None:
    _replace(data_copy / file, old, new)
    with pytest.raises(DataLoadError) as info:
        load_all(data_copy)
    assert expected in str(info.value)

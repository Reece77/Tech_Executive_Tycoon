"""M52 sub-task 1 (ADR-0026, formulas.md 66.2): the custom-scenario schema, its canonical YAML
and hash, the files in `<saves>/scenarios/`, and import and export with clear refusals."""

from __future__ import annotations

from pathlib import Path

import pytest

from tst import scenario_files as sf
from tst.loader import LoadedData
from tst.sim.errors import (
    CustomScenarioExistsError,
    InvalidCustomScenarioError,
    UnknownCustomScenarioError,
)
from tst.sim.modes import custom
from tst.sim.modes.custom_config import CustomScenario


def _spec(loaded: LoadedData, key: str = "ev_maker") -> CustomScenario:
    return custom.from_historical(loaded.game_data.historical_scenario(key))  # type: ignore[arg-type]


@pytest.mark.parametrize("index", range(11))
def test_every_scenario_opens_valid_and_unchanged(loaded: LoadedData, index: int) -> None:
    h = loaded.game_data.historical[index]
    spec = custom.from_historical(h)
    assert custom.refusals(spec, loaded.balance, loaded.game_data) == []
    same = {k: v for k, v in h.model_dump().items() if k not in ("key", "sensible_wins")}
    mine = spec.model_dump(exclude={"key", "opened_from", "overrides", "format", "sensible_wins"})
    assert mine == same
    assert spec.opened_from == h.key


@pytest.mark.parametrize("year", [2008, 2010, 2030])
def test_a_blank_start_is_valid(loaded: LoadedData, year: int) -> None:
    spec = custom.blank(year, loaded.balance, loaded.game_data)
    assert custom.refusals(spec, loaded.balance, loaded.game_data) == []
    assert spec.goal is None and spec.staff == () and spec.products == ()


def test_canonical_text_ignores_how_the_file_was_written(loaded: LoadedData) -> None:
    spec = _spec(loaded)
    text = sf.canonical(spec)
    assert text.endswith("\n") and "\r" not in text
    # the same spec written with its defaults spelled out and its keys in another order
    raw = spec.model_dump(mode="json")
    shuffled = dict(reversed(list(raw.items())))
    again = sf.from_dict(shuffled)
    assert sf.canonical(again) == text
    assert sf.sha256(again) == sf.sha256(spec)
    assert len(sf.sha256(spec)) == 64
    # an integer quality is the same number as its float
    raw["products"][0]["quality"] = int(raw["products"][0]["quality"])
    assert sf.sha256(sf.from_dict(raw)) == sf.sha256(spec)


def test_a_change_changes_the_hash(loaded: LoadedData) -> None:
    spec = _spec(loaded)
    richer = spec.model_copy(update={"cash_dollars": spec.cash_dollars * 2})
    assert sf.sha256(richer) != sf.sha256(spec)


def test_files_save_list_read_and_delete(tmp_path: Path, loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = _spec(loaded)
    sf.write(tmp_path, spec, b, d, overwrite=False)
    path = tmp_path / "scenarios" / f"{spec.key}.yaml"
    assert path.read_text(encoding="utf-8") == sf.canonical(spec)
    assert [s.key for s in sf.list_specs(tmp_path, b, d)] == [spec.key]
    assert sf.read(tmp_path, spec.key, b, d) == spec
    with pytest.raises(CustomScenarioExistsError):
        sf.write(tmp_path, spec, b, d, overwrite=False)
    sf.write(tmp_path, spec, b, d, overwrite=True)
    sf.delete(tmp_path, spec.key)
    with pytest.raises(UnknownCustomScenarioError):
        sf.read(tmp_path, spec.key, b, d)


def test_export_then_import_under_another_name(tmp_path: Path, loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = _spec(loaded)
    sf.write(tmp_path, spec, b, d, overwrite=False)
    text = sf.export_text(tmp_path, spec.key, b, d)
    other = tmp_path / "other"
    got = sf.import_text(other, text, b, d)
    assert sf.sha256(got) == sf.sha256(spec)
    renamed = sf.import_text(other, text, b, d, slug="my-copy")
    assert renamed.key == "my-copy"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{not: [yaml", "not valid YAML"),
        ("- a list", "a YAML mapping"),
        ("key: a\nkey: b\n", "duplicate key"),
    ],
)
def test_import_refuses_what_is_not_a_scenario(
    tmp_path: Path, loaded: LoadedData, text: str, reason: str
) -> None:
    with pytest.raises(InvalidCustomScenarioError, match=reason):
        sf.import_text(tmp_path, text, loaded.balance, loaded.game_data)
    assert not (tmp_path / "scenarios").exists()


def test_import_names_unknown_fields_and_code(tmp_path: Path, loaded: LoadedData) -> None:
    raw = _spec(loaded).model_dump(mode="json")
    raw["overrides"] = {"script": "import os", "rivals": {}}
    raw["path"] = "/etc/passwd"
    import yaml

    with pytest.raises(InvalidCustomScenarioError) as err:
        sf.import_text(tmp_path, yaml.safe_dump(raw), loaded.balance, loaded.game_data)
    assert "overrides.script: not a field" in str(err.value)
    assert "path: not a field" in str(err.value)


def test_import_names_every_out_of_range_field(tmp_path: Path, loaded: LoadedData) -> None:
    raw = _spec(loaded).model_dump(mode="json")
    raw["cash_dollars"] = 10**13
    raw["overrides"] = {
        "markets": {"cloud_hosting": {"market_mult": 9.0}},
        "rivals": {"Nobody Inc": {"present": False}},
    }
    import yaml

    with pytest.raises(InvalidCustomScenarioError) as err:
        sf.import_text(tmp_path, yaml.safe_dump(raw), loaded.balance, loaded.game_data)
    text = str(err.value)
    assert "starting cash ($) is 1e+13: the editor allows 0 to 1e+10" in text
    assert "cloud_hosting: market x is 9" in text
    assert "'Nobody Inc' is not an incumbent" in text


def test_refused_combinations(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = _spec(loaded, "under_controls")
    fab = spec.fabs[0]
    early = spec.model_copy(update={"year": 2010, "fabs": (fab.model_copy(update={"node": "n3"}),)})
    reasons = custom.refusals(early, b, d)
    assert any("not yet in volume in January 2010" in r for r in reasons), reasons
    macro = CustomScenario.model_validate(
        {**spec.model_dump(), "overrides": {"world": {"confidence": 90.0}}}
    )
    assert any("history before 2026" in r for r in custom.refusals(macro, b, d))
    cars = CustomScenario.model_validate(
        {**spec.model_dump(), "overrides": {"markets": {"vehicles": {"market_mult": 1.5}}}}
    )
    assert any("follows its own data" in r for r in custom.refusals(cars, b, d))


def test_a_goal_needs_its_deadline(loaded: LoadedData) -> None:
    raw = _spec(loaded).model_dump(mode="json")
    raw.pop("deadline")
    with pytest.raises(InvalidCustomScenarioError, match="a goal needs a deadline"):
        sf.from_dict(raw)


def test_the_schema_names_no_hidden_value() -> None:
    """ADR-0026 point 3: no field of the editor's schema is a hidden value."""
    hidden = ("potential", "trait", "hidden", "true_grade", "grade", "personality", "ambition")

    def names(model: type) -> set[str]:
        out: set[str] = set()
        for name, f in model.model_fields.items():  # type: ignore[attr-defined]
            out.add(name)
            for arg in getattr(f.annotation, "__args__", (f.annotation,)):
                inner = getattr(arg, "__args__", (arg,))
                for t in inner:
                    if isinstance(t, type) and hasattr(t, "model_fields"):
                        out |= names(t)
        return out

    found = names(CustomScenario)
    assert not [n for n in found if any(h in n for h in hidden)], sorted(found)

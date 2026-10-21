from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.errors import (
    InvalidCompanyNameError,
    ScenarioUnavailableError,
    UnknownDifficultyError,
    UnknownScenarioError,
)
from tst.sim.ledger import CASH, apply_entries
from tst.sim.setup import PLAYER_COMPANY_ID, new_game, starting_cash_cents
from tst.sim.state import company_cash


@pytest.mark.parametrize(
    ("scenario", "difficulty", "expected"),
    [
        ("garage_bootstrap", "standard", 5_000_000),
        ("garage_bootstrap", "easy", 7_500_000),
        ("garage_bootstrap", "hard", 3_000_000),
        ("garage_bootstrap", "ironman", 5_000_000),
        ("ex_big_tech_founders", "standard", 40_000_000),
        ("funded_spinout", "hard", 90_000_000),
    ],
)
def test_starting_cash(loaded: LoadedData, scenario: str, difficulty: str, expected: int) -> None:
    assert starting_cash_cents(loaded.balance, scenario, difficulty) == expected


def test_unknown_scenario_and_difficulty(loaded: LoadedData) -> None:
    with pytest.raises(UnknownScenarioError):
        starting_cash_cents(loaded.balance, "nope", "standard")
    with pytest.raises(UnknownDifficultyError):
        starting_cash_cents(loaded.balance, "garage_bootstrap", "nightmare")


def _new(loaded: LoadedData, scenario_id: str, company_name: str = "Test Co"):  # type: ignore[no-untyped-def]
    scenario = loaded.game_data.scenario(scenario_id)
    assert scenario is not None
    return new_game(
        save_name="dev",
        master_seed=42,
        scenario=scenario,
        difficulty="standard",
        company_name=company_name,
        balance=loaded.balance,
    )


def test_new_game_garage(loaded: LoadedData) -> None:
    state, entries = _new(loaded, "garage_bootstrap", "  Test Co ")
    assert state.turn == 0
    assert state.player.id == PLAYER_COMPANY_ID
    assert state.player.name == "Test Co"
    assert state.player.stage == 0
    assert len(entries) == 1
    entry = entries[0]
    assert entry.turn == 0
    assert {(ln.account, ln.amount) for ln in entry.lines} == {
        (CASH, 5_000_000),
        ("3000_common_equity", -5_000_000),
    }
    assert company_cash(apply_entries({}, entries), PLAYER_COMPANY_ID) == 5_000_000


def test_funded_spinout_credits_preferred_equity(loaded: LoadedData) -> None:
    _, entries = _new(loaded, "funded_spinout")
    accounts = {ln.account for ln in entries[0].lines}
    assert accounts == {CASH, "3100_preferred_equity"}


def test_v3_scenario_not_selectable(loaded: LoadedData) -> None:
    with pytest.raises(ScenarioUnavailableError):
        _new(loaded, "mineral_first_prospector")


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_bad_company_name(loaded: LoadedData, name: str) -> None:
    with pytest.raises(InvalidCompanyNameError):
        _new(loaded, "garage_bootstrap", name)

"""M52 sub-task 2 (formulas.md 66.1, 66.4 target 2): a custom start through §63's start code.
Every scenarios.yaml entry opened in the editor and saved unchanged starts an identical game
(here the two whose world needs no dormant years, 12 months on seed 1; all eleven on seeds 1-3
are `tst.balance.m52.round_trips`, nightly), and each override takes effect at the start."""

from __future__ import annotations

import pytest

from tst import scenario_files as sf
from tst.balance import m52
from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.ledger import CASH
from tst.sim.modes import custom
from tst.sim.modes.custom_config import CustomScenario


@pytest.mark.parametrize("key", ["the_crash", "platform_war"])
def test_an_unchanged_scenario_plays_identically(key: str) -> None:
    (r,) = m52.round_trips(keys=[key], seeds=(1,), months=12)
    assert r.identical, r.first_difference


def _edited(loaded: LoadedData) -> CustomScenario:
    base = custom.from_historical(loaded.game_data.historical_scenario("platform_war"))  # type: ignore[arg-type]
    raw = base.model_dump(mode="json")
    raw["cash_dollars"] = base.cash_dollars * 3
    raw["goal"] = None
    raw["deadline"] = None
    raw["overrides"] = {
        "rivals": {
            "Microsoft": {"present": False},
            "Oracle": {"cash_mult": 2.0},
            "Salesforce": {"quality_delta": 15.0},
        },
        "markets": {"b2b_saas": {"market_mult": 2.0, "growth_delta": 0.05}},
        "added_rivals": [{"category": "dev_tools", "count": 2}],
        "world": {"eras": "seeded"},
        "rules": {"challenges": ["bootstrapped"]},
    }
    return sf.validate(sf.from_dict(raw), loaded.balance, loaded.game_data)


@pytest.fixture(scope="module")
def games(loaded: LoadedData) -> tuple[Game, Game]:
    return (
        m52.start_historical(loaded, "platform_war", 7),
        m52.start_custom(loaded, _edited(loaded), 7),
    )


def _company(game: Game, name: str) -> int:
    return next(c.id for c in game.state.companies if c.name == name)


def test_the_mode_record_names_the_custom_game(
    games: tuple[Game, Game], loaded: LoadedData
) -> None:
    _, edited = games
    mode = edited.state.mode
    assert mode is not None and mode.kind == "scenario" and mode.custom
    assert mode.scenario == "custom/platform-war"
    assert mode.scenario_sha256 == sf.sha256(_edited(loaded))
    assert mode.growth_delta == (("b2b_saas", 0.05),)
    assert mode.challenges == ("bootstrapped",) and mode.eras == "seeded"


def test_company_cash(games: tuple[Game, Game]) -> None:
    original, edited = games
    assert edited.cash == 3 * original.cash


def test_rivals_removed_richer_and_better(games: tuple[Game, Game]) -> None:
    original, edited = games
    ms = _company(edited, "Microsoft")
    assert edited.state.company(ms).failed_turn == edited.state.turn
    assert original.state.company(_company(original, "Microsoft")).failed_turn is None
    oracle = _company(edited, "Oracle")
    assert edited.balances[(oracle, CASH)] == 2 * original.balances[(oracle, CASH)]
    sf_e, sf_o = _company(edited, "Salesforce"), _company(original, "Salesforce")
    q_e = [p.quality for p in edited.state.company_products(sf_e)]
    q_o = [p.quality for p in original.state.company_products(sf_o)]
    assert q_e == [min(100.0, q + 15) for q in q_o]


def test_added_rivals_enter(games: tuple[Game, Game]) -> None:
    original, edited = games
    added = [c for c in edited.state.companies if c.rival_key[:1] == (custom.CUSTOM_KEY,)]
    assert len(added) == 2 and len(edited.state.companies) == len(original.state.companies) + 2
    for c in added:
        (p,) = edited.state.company_products(c.id)
        assert p.category == "dev_tools" and p.status == "live"


def test_the_market_and_its_growth(games: tuple[Game, Game], loaded: LoadedData) -> None:
    original, edited = games

    def saas(g: Game) -> float:
        return sum(m.addressable for m in g.state.markets if m.category == "b2b_saas")

    assert saas(edited) == pytest.approx(2 * saas(original))
    from tst.sim.research.eras import annual_growth

    g_e = annual_growth(edited.state, edited.loaded.game_data, "b2b_saas")
    g_o = annual_growth(original.state, original.loaded.game_data, "b2b_saas")
    assert g_e == pytest.approx(g_o + 0.05)


def test_the_edited_game_plays_and_is_seeded(loaded: LoadedData) -> None:
    """Same spec and seed, same game (ADR-0026 point 4)."""
    spec = _edited(loaded)
    a = m52.month_digests(m52.start_custom(loaded, spec, 3), 2)
    b = m52.month_digests(m52.start_custom(loaded, spec, 3), 2)
    assert a == b


def test_a_custom_game_with_no_goal_has_no_verdict(games: tuple[Game, Game]) -> None:
    _, edited = games
    edited.turn()
    assert edited.state.mode is not None and edited.state.mode.result is None

"""M31 (docs/formulas.md 44.1-44.3): platforms.yaml, the history's shares, developers, the
catalogue, network effects and lock-in (tests/platform_helpers.py)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tests.platform_helpers import HISTORY_END, START, platform_state
from tst.loader import DATA_FILES, LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.platforms import data as pdata
from tst.sim.platforms import formulas as pf
from tst.sim.platforms.config import PlatformsFile
from tst.sim.platforms.phase import by_region, platforms_month
from tst.sim.rng import RngFactory


def test_platforms_file_is_a_data_file() -> None:
    assert "platforms.yaml" in DATA_FILES


def test_every_year_of_every_region_sums_to_one(loaded: LoadedData) -> None:
    """Sub-task 1: regional shares sum to 1 in every year of the data."""
    pf_ = loaded.game_data.platforms
    assert pf_ is not None
    for region in loaded.game_data.region_keys:
        years = pf_.user_shares[region]
        assert sorted(years) == list(range(2010, 2026))
        for year, shares in years.items():
            assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6), (region, year)


def test_a_bad_row_fails_validation(loaded: LoadedData) -> None:
    raw = yaml.safe_load(Path("data/platforms.yaml").read_text(encoding="utf-8"))
    raw["user_shares"]["europe"][2014]["ios"] += 0.05
    with pytest.raises(ValueError, match="sum to"):
        PlatformsFile.model_validate(raw)


def test_every_fee_rule_and_platform_cites_a_source() -> None:
    """Acceptance 1: a source beside every value (fee rules carry it as a field; the rest as
    comments, checked here as a URL or an 'A' marker on the line)."""
    text = Path("data/platforms.yaml").read_text(encoding="utf-8").splitlines()
    for line in text:
        stripped = line.strip()
        if stripped.endswith(":"):  # a block's key, not a value
            continue
        if stripped.startswith(("store_opened:", "ended:", "open_source:")) or (
            ":" in stripped and stripped.split(":")[0] in ("consumer_apps", "fintech", "ai_models")
        ):
            assert "http" in line or "(A" in line or "A (" in line or "above" in line, line
    raw = yaml.safe_load("\n".join(text))
    for rule in raw["fee_rules"]:
        assert rule["source"].startswith("A (") or "http" in rule["source"], rule


@pytest.mark.parametrize("year", [2010, 2013, 2016, 2020, 2025])
def test_history_shares_equal_the_data(loaded: LoadedData, year: int) -> None:
    """Sub-task 2: every platform's users to 2025 equal platforms.yaml's year."""
    turn = ym_to_turn(year, 6)
    state, _ = platform_state(loaded, turn=turn)
    state = platforms_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    rows = by_region(state)
    shares = loaded.game_data.platforms.user_shares  # type: ignore[union-attr]
    for region in loaded.game_data.region_keys:
        for pid, row in rows[region].items():
            p = state.platform(pid)
            assert p is not None
            assert row.users == pytest.approx(shares[region][year].get(p.key, 0.0)), (region, p.key)


def test_ended_platforms_lose_their_users_after_the_history(loaded: LoadedData) -> None:
    state, _ = platform_state(loaded, turn=HISTORY_END)
    state = platforms_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    for _ in range(3):
        state = replace(state, turn=state.turn + 1)
        state = platforms_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    for row in state.platform_regions:
        p = state.platform(row.platform_id)
        assert p is not None
        if p.ended_turn is not None:
            assert row.rest == 0.0


def _months(loaded: LoadedData, seed: int, months: int) -> list[tuple[int, str, float, float]]:
    state, _ = platform_state(loaded, seed=seed, turn=HISTORY_END)
    rng = RngFactory(seed)
    for _ in range(months):
        state = platforms_month(state, rng, loaded.balance, loaded.game_data)
        state = replace(state, turn=state.turn + 1)
    return sorted((r.platform_id, r.region, r.users, r.dev_share) for r in state.platform_regions)


def test_the_same_seed_gives_the_same_shares(loaded: LoadedData) -> None:
    """Sub-task 3 (seeded): developers' noise is drawn from the seed only."""
    assert _months(loaded, 7, 6) == _months(loaded, 7, 6)
    assert _months(loaded, 7, 6) != _months(loaded, 8, 6)


def test_users_carry_on_from_december_2025(loaded: LoadedData) -> None:
    """The first computed month starts from the data (no jump in January 2026)."""
    state, _ = platform_state(loaded, turn=HISTORY_END)
    rng = RngFactory(1)
    state = platforms_month(state, rng, loaded.balance, loaded.game_data)
    before = {(r.platform_id, r.region): r.users for r in state.platform_regions}
    state = platforms_month(replace(state, turn=START), rng, loaded.balance, loaded.game_data)
    for r in state.platform_regions:
        p = state.platform(r.platform_id)
        assert p is not None
        if p.ended_turn is None:
            assert r.users == pytest.approx(before[(r.platform_id, r.region)], abs=0.02)
    for region, rows in by_region(state).items():
        assert sum(r.users for r in rows.values()) == pytest.approx(1.0, abs=0.01), region


# --- Formulas (44.2-44.4) --------------------------------------------------------------------


def test_attractiveness(loaded: LoadedData) -> None:
    pb = loaded.balance.platforms
    a, b = pb.reach_exp, pb.fee_exp
    assert pf.attractiveness(0.5, 0.3, 1.0, 1.0, pb) == pytest.approx(0.5**a * 0.7**b)
    assert pf.attractiveness(0.5, 0.1, 1.3, 0.9, pb) == pytest.approx(0.5**a * 0.9**b * 1.3 * 0.9)
    assert pf.attractiveness(0.0, 0.3, 1.0, 1.0, pb) == 0.0


def test_developer_shares_move_with_inertia(loaded: LoadedData) -> None:
    pb = loaded.balance.platforms
    out = pf.next_dev_shares({1: 0.5, 2: 0.5}, {1: 3.0, 2: 1.0}, pb)
    assert sum(out.values()) == pytest.approx(1.0)
    assert out[1] == pytest.approx(0.97 * 0.5 + 0.03 * 0.75)


def test_multi_homing(loaded: LoadedData) -> None:
    pb = loaded.balance.platforms
    assert pf.developer_months(0.1, 0.06, pb) == pytest.approx(0.35 + 0.65 * 0.1)
    assert pf.developer_months(0.1, 0.04, pb) == pytest.approx(0.65 * 0.1)


def test_catalogue_points_are_capped(loaded: LoadedData) -> None:
    pb = loaded.balance.platforms
    assert pf.catalogue_points(100, 100, pb) == 0.0
    assert pf.catalogue_points(150, 100, pb) == 0.0
    assert pf.catalogue_points(60, 100, pb) == pytest.approx(-10.0)
    assert pf.catalogue_points(0, 100, pb) == -25.0


def test_stay_probability(loaded: LoadedData) -> None:
    pb = loaded.balance.platforms
    assert pf.stay_probability(100, pb) == pytest.approx(0.85)
    assert pf.stay_probability(75, pb) == pytest.approx(0.75)
    assert pf.stay_probability(0, pb) == pytest.approx(0.45)


def test_replacement_conserves_users() -> None:
    out = pf.replace_users({1: 0.6, 2: 0.4}, {1: 0.85, 2: 0.5}, {1: 0.6, 2: 0.4}, 30)
    assert sum(out.values()) == pytest.approx(1.0)
    assert out[1] > 0.6  # the stickier platform gains


def test_fee_schedules_follow_the_history(loaded: LoadedData) -> None:
    """Sub-task 4: Apple's 15% after a subscriber's first year (June 2016), the Small Business
    Program (January 2021); Google's 15% subscriptions from day one (January 2022)."""
    state, _ = platform_state(loaded, turn=0)
    ios = next(p for p in state.platforms if p.key == "ios")
    play = next(p for p in state.platforms if p.key == "android_play")
    b, d = loaded.balance, loaded.game_data
    assert pdata.schedule(ios, "europe", ym_to_turn(2015, 1), b, d).standard == 0.30
    assert pdata.schedule(ios, "europe", ym_to_turn(2015, 1), b, d).sub_rate is None
    s2016 = pdata.schedule(ios, "europe", ym_to_turn(2016, 6), b, d)
    assert (s2016.sub_rate, s2016.sub_after_year) == (0.15, True)
    s2021 = pdata.schedule(ios, "europe", ym_to_turn(2021, 1), b, d)
    assert (s2021.small_rate, s2021.small_threshold_cents) == (0.15, 100_000_000)
    s2022 = pdata.schedule(play, "europe", ym_to_turn(2022, 1), b, d)
    assert (s2022.sub_rate, s2022.sub_after_year) == (0.15, False)
    korea = pdata.schedule(play, "east_asia", ym_to_turn(2022, 1), b, d)
    assert [(part, rate) for part, _, rate in korea.regulated] == [("south_korea", 0.26)]
    us = pdata.schedule(ios, "north_america", ym_to_turn(2025, 6), b, d)
    assert [(part, rate) for part, _, rate in us.regulated] == [("united_states", 0.0)]


def test_effective_fee(loaded: LoadedData) -> None:
    assert pf.effective_fee(0.3, None, False, None, False, 0.5, 0.6, []) == pytest.approx(0.3)
    # subscriptions after a year at 15%: 0.5 x 0.3 + 0.5 x (0.6 x 0.15 + 0.4 x 0.3)
    assert pf.effective_fee(0.3, None, False, 0.15, True, 0.5, 0.6, []) == pytest.approx(0.255)
    assert pf.effective_fee(0.3, 0.15, True, None, False, 0.5, 0.6, []) == pytest.approx(0.15)
    assert pf.effective_fee(0.3, None, False, None, False, 0.0, 0.0, [(0.5, 0.1)]) == pytest.approx(
        0.2
    )

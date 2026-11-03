"""M12b: historical hardware eras and future eras with seeded windows (docs/formulas.md
26.4; ADR-0019 15)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.research import eras, levels
from tst.sim.research.data import EraDef, ErasFile
from tst.sim.research.models import EraArrival, ResearchLead
from tst.sim.rng import RngFactory

SEEDS = range(1, 31)


def _future(loaded: LoadedData) -> list[tuple[int, EraDef]]:
    return [(i, e) for i, e in enumerate(loaded.game_data.eras.eras) if e.windowed]


def test_scheduled_month_is_seeded_and_inside_the_window(loaded: LoadedData) -> None:
    """The same seed gives the same month; every seed's month is inside the window (30
    seeds); across them both halves of each window occur."""
    for index, era in _future(loaded):
        start, n = levels.window_span(era)
        months = []
        for seed in SEEDS:
            a = levels.scheduled_turn(era, index, RngFactory(seed))
            assert a == levels.scheduled_turn(era, index, RngFactory(seed))
            assert start <= a < start + n, (era.key, seed)
            months.append(a)
        mid = start + n // 2
        assert any(m < mid for m in months) and any(m >= mid for m in months), era.key


def test_appending_an_era_moves_no_other_month(loaded: LoadedData) -> None:
    """Keys are positions in eras.yaml and eras are only appended (26.4)."""
    data = loaded.game_data
    extra = EraDef.model_validate(
        {
            "key": "humanoids",
            "label": "Humanoid robotics",
            "domain": "devices",
            "window": [[2030, 1], [2035, 12]],
        }
    )
    longer = ErasFile(eras=(*data.eras.eras, extra), base_growth=data.eras.base_growth)
    for seed in (1, 2, 3):
        rng = RngFactory(seed)
        before = [levels.scheduled_turn(e, i, rng) for i, e in enumerate(data.eras.eras)]
        after = [levels.scheduled_turn(e, i, rng) for i, e in enumerate(longer.eras)]
        assert after[: len(before)] == before


def test_loader_checks_the_window() -> None:
    base = {"key": "x", "label": "X", "domain": "devices"}
    with pytest.raises(ValidationError):
        EraDef.model_validate({**base, "arrival": [2026, 1], "window": [[2026, 1], [2027, 1]]})
    with pytest.raises(ValidationError):
        EraDef.model_validate(base)
    with pytest.raises(ValidationError):
        EraDef.model_validate({**base, "window": [[2025, 1], [2027, 1]]})
    with pytest.raises(ValidationError):
        EraDef.model_validate({**base, "window": [[2027, 1], [2026, 6]]})
    ok = EraDef.model_validate({**base, "window": [[2026, 1], [2028, 12]]})
    assert ok.arrival == (2027, 7)  # the public reference month: the midpoint


def test_future_era_arrives_on_its_scheduled_month(loaded: LoadedData) -> None:
    """No company reaches the threshold: the era arrives exactly at t_sched."""
    data, balance = loaded.game_data, loaded.balance
    index, era = _future(loaded)[0]
    rng = RngFactory(5)
    due = levels.scheduled_turn(era, index, rng)
    state = fresh_game(loaded)
    past = tuple(
        EraArrival(e.key, levels.historical_turn(e)) for e in data.eras.eras if not e.windowed
    )
    before, _ = eras.arrive_eras(
        replace(state, turn=due - 1, era_arrivals=past), data, balance, rng
    )
    assert before.era_arrival(era.key) is None
    after, logs = eras.arrive_eras(replace(state, turn=due, era_arrivals=past), data, balance, rng)
    arrival = after.era_arrival(era.key)
    assert arrival is not None and arrival.turn == due and arrival.company_id is None
    assert logs


def test_future_era_can_be_pulled_forward(loaded: LoadedData) -> None:
    """A company whose level reaches the threshold before t_sched causes it (21.4)."""
    data, balance = loaded.game_data, loaded.balance
    _, era = _future(loaded)[0]
    turn = ym_to_turn(2025, 6)
    past = tuple(
        EraArrival(e.key, levels.historical_turn(e)) for e in data.eras.eras if not e.windowed
    )
    state = replace(fresh_game(loaded), turn=turn, era_arrivals=past)
    need = levels.threshold(data, balance, era) - levels.baseline(state, data, balance, era.domain)
    lead = (ResearchLead(1, era.domain, need + 0.5),)
    after, _ = eras.arrive_eras(replace(state, research_leads=lead), data, balance, RngFactory(5))
    arrival = after.era_arrival(era.key)
    assert arrival is not None and arrival.company_id == 1 and arrival.turn == turn


def test_historical_hardware_eras_arrive_and_boost(loaded: LoadedData) -> None:
    """Smartphone ubiquity in January 2012 adds 15 points to devices' consumer growth for
    36 months; custom silicon gives devices with their own SoC +5 cap for everyone."""
    data, balance = loaded.game_data, loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2012, 1))
    rng = RngFactory(1)
    before = eras.annual_growth(state, data, "devices", "consumer")
    while state.era_arrival("smartphone_ubiquity") is None:
        state, _ = eras.arrive_eras(state, data, balance, rng)
    a = state.era_arrival("smartphone_ubiquity")
    assert a is not None and a.turn == ym_to_turn(2012, 1)
    assert eras.annual_growth(state, data, "devices", "consumer") == pytest.approx(before + 0.15)
    assert eras.annual_growth(state, data, "devices", "smb") == pytest.approx(
        eras.base_growth(data, "devices", 2012)
    )
    silicon = replace(
        state,
        turn=ym_to_turn(2021, 1),
        era_arrivals=(EraArrival("custom_silicon", ym_to_turn(2020, 11)),),
    )
    assert levels.era_cap_points(silicon, data, balance, 1, "devices") == 0  # no own SoC
    from tests.helpers import with_product

    own = with_product(
        silicon, category="chips_mobile_soc", prices={"device_oems": 4000}, root=False
    )
    assert levels.era_cap_points(own, data, balance, 1, "devices") == 5
    later = replace(own, turn=ym_to_turn(2022, 11))
    assert levels.era_cap_points(later, data, balance, 1, "devices") == 0  # 24 months on


def test_ai_accelerators_era_boosts_accelerator_demand(loaded: LoadedData) -> None:
    data = loaded.game_data
    state = replace(
        fresh_game(loaded),
        turn=ym_to_turn(2016, 6),
        era_arrivals=(EraArrival("ai_accelerators", ym_to_turn(2016, 5)),),
    )
    off = replace(state, era_arrivals=())
    on = eras.annual_growth(state, data, "chips_ai_accelerator", "hyperscalers")
    assert on == pytest.approx(
        eras.annual_growth(off, data, "chips_ai_accelerator", "hyperscalers") + 0.40
    )


def test_chip_demand_follows_its_markets(loaded: LoadedData) -> None:
    """Hyperscaler accelerators grow with AI models, server CPUs with cloud hosting (26.3)."""
    data = loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2023, 1))
    ai = eras.annual_growth(state, data, "ai_models")
    assert eras.annual_growth(state, data, "chips_ai_accelerator", "hyperscalers") == pytest.approx(
        ai
    )
    cloud = eras.annual_growth(state, data, "cloud_hosting")
    assert eras.annual_growth(state, data, "chips_server_cpu", "hyperscalers") == pytest.approx(
        cloud
    )
    devices = eras.annual_growth(state, data, "devices")
    assert eras.annual_growth(state, data, "chips_mobile_soc", "device_oems") == pytest.approx(
        devices
    )

"""M15r (Codex review 4 finding 6): the COO's assembly-plant pitch proposes a size the build
action accepts (the plant kind's own sizes, 26.8), and its case uses the assembly costs and
yield of 26.2. Approving it builds the plant."""

from __future__ import annotations

from tests.helpers import fresh_game
from tests.unit.test_hardware import RICH, _contract, _device, _founder, _pid
from tst.loader import LoadedData
from tst.sim.facilities import lifecycle
from tst.sim.hardware import formulas as hf
from tst.sim.org import pitches
from tst.sim.rng import RngFactory

CASH_CENTS = 10**13


def test_a_coo_plant_pitch_approved_builds_the_plant(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _device(fresh_game(loaded))
    state = _contract(state, _pid(state, "Pebble Phone"), 20_000)  # 24 months of 20,000
    (c,) = pitches.candidates(state, 1, ("plant",), CASH_CENTS, b, d, RICH, seat="coo")
    params = dict(c.params)
    kind = b.facility.kinds[b.hardware.plant_kind]
    assert params["units"] in kind.sizes and params["units"] == 20_000
    # the case: the fee saved less the plant's cost per good unit (fixed, variable and
    # depreciation over units x yield, 26.2), on the units the plant would run
    q = lifecycle.quote(state, 1, b.hardware.plant_kind, str(params["region"]), 20_000, b, d)
    per_good = hf.plant_cost_per_good_unit(
        20_000,
        20_000,
        b.hardware.plant_yield.base,
        kind.fixed_opex_cents,
        kind.variable_cents,
        q.capex_cents,
        kind.life_months,
    )
    assert per_good is not None
    assert c.central == (1_300.0 - per_good) * 20_000
    pitch = pitches.make_pitch(state, 1, "coo", _founder(state), c, b)
    before = len(state.company_facilities(1))
    rng = RngFactory(1)
    out = pitches.approve(
        state, pitch, _founder(state), rng, b, d, RICH, lambda n: lambda: rng.stream(0, "misc", n)
    )
    plants = [f for f in out.state.company_facilities(1) if f.kind == b.hardware.plant_kind]
    assert len(out.state.company_facilities(1)) == before + 1
    assert [f.capacity for f in plants] == [20_000]

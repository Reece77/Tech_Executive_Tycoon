"""M57r-A sub-task 1 (review 10 item 5, ruling 3): RNG keys come from stable identities.

Insertion tests: an unrelated auction, bank, region-file reorder or category reorder leaves every
existing entity's draws unchanged."""

from __future__ import annotations

from dataclasses import replace

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import GameData
from tst.sim.finserv import banks
from tst.sim.finserv.models import Bank
from tst.sim.fx import rates
from tst.sim.media.config import _year_share
from tst.sim.rng import RngFactory, text_key
from tst.sim.robotics.models import RoboIncident, incident_key
from tst.sim.state import GameState
from tst.sim.telecom import spectrum
from tst.sim.world import cycles

PLAYER = 1
NA = "north_america"
EU = "europe"


def _reordered(data: GameData) -> GameData:
    """The same data with regions.yaml's regions in reverse order."""
    return data.model_copy(update={"regions": tuple(reversed(data.regions))})


def _telecom_at(loaded: LoadedData, year: int) -> GameState:
    return replace(fresh_game(loaded), turn=ym_to_turn(year, 6))


def test_text_keys_are_stable_and_distinct() -> None:
    assert text_key("north_america") == text_key("north_america")
    assert text_key("north_america") != text_key("europe")
    assert 0 <= text_key("x") < 2**48
    # pinned: the derivation never changes (a change would reseed every save)
    assert text_key("north_america") == 40229695581008


def test_an_auctions_draws_ignore_its_storage_id(loaded: LoadedData) -> None:
    """Codex's reproduction: changing the C-band auction's id from 7 to 8 moved its price 5%."""
    b, d = loaded.balance, loaded.game_data
    a = d.telecom.auction("us_cband_2021")  # type: ignore[union-attr]
    assert a is not None
    prices = []
    for auction_id in (7, 8):
        state = _telecom_at(loaded, 2021)
        auction = replace(spectrum._from_def(a, auction_id, b.telecom.scale), turn=state.turn)
        other = replace(auction, id=auction_id - 1, key="an_unrelated_auction", turn=state.turn + 1)
        state = replace(state, telecom=replace(state.telecom, auctions=(other, auction)))
        state, _, _ = spectrum.run_month(state, RngFactory(42), b, d)
        prices.append(next(x for x in state.telecom.auctions if x.key == a.key).price_cents)
    assert prices[0] == prices[1] > 0
    first = spectrum._from_def(a, 7, b.telecom.scale)
    assert spectrum.auction_key(first) == spectrum.auction_key(replace(first, id=99))
    assert spectrum.auction_key(first)[1] == 2021


def _bank(bank_id: int, company_id: int = PLAYER, region: str = NA) -> Bank:
    return Bank(
        bank_id,
        company_id,
        region,
        "chartered",
        0,
        consumer_deposits_cents=1000 * 10**9,
        reserves_cents=200 * 10**9,
        loans=(("mortgage", 900 * 10**9),),
    )


def test_a_banks_key_ignores_ids_and_unrelated_banks(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    mine = _bank(5)
    alone = replace(state, finserv=replace(state.finserv, banks=(mine,)))
    later = replace(mine, id=40)  # an unrelated network or insurer took the ids before it
    crowded = replace(
        state,
        finserv=replace(state.finserv, banks=(_bank(1, region=EU), _bank(2, 2), later)),
    )
    assert banks.bank_key(alone, mine) == banks.bank_key(crowded, later)
    # a second bank of the same owner in the same region is the next ordinal
    again = replace(mine, id=60, status="applying")
    both = replace(state, finserv=replace(state.finserv, banks=(mine, again)))
    assert banks.bank_key(both, again)[-1] == banks.bank_key(both, mine)[-1] + 1


def test_a_stress_test_draws_the_same_whatever_the_banks_id(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    june = ym_to_turn(2018, 6)
    base = replace(fresh_game(loaded), turn=june)
    outs = []
    for bank_id, others in ((1, ()), (77, (_bank(3, region=EU),))):
        bank = _bank(bank_id)
        state = replace(base, finserv=replace(base.finserv, banks=(*others, bank)))
        out, _ = banks._stress(state, bank, RngFactory(1), 2.0, b, d)
        outs.append(out.stress)
    assert outs[0] == outs[1] and outs[0]


def test_fx_walks_ignore_the_region_files_order(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    start = b.fx.start_turn
    base = replace(fresh_game(loaded), turn=start)
    walks = []
    for data in (d, _reordered(d)):
        s = base
        for t in range(start, start + 6):
            s = rates.walk_month(replace(s, turn=t), RngFactory(9), b, data)
        walks.append(dict(s.fx.walk))
    assert walks[0] == walks[1] and walks[0]


def test_region_cycles_ignore_the_region_files_order(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    a, _ = cycles.cycles_month(state, RngFactory(5), b, d)
    r, _ = cycles.cycles_month(state, RngFactory(5), b, _reordered(d))
    by_region = {c.region: c for c in a.region_cycles}
    assert by_region == {c.region: c for c in r.region_cycles}


def test_an_incidents_key_survives_pruning() -> None:
    old = RoboIncident(
        turn=3, zone_id=1, company_id=PLAYER, city="Phoenix", serious=False, cost_cents=0
    )
    new = RoboIncident(
        turn=40, zone_id=2, company_id=PLAYER, city="Austin", serious=True, cost_cents=0
    )
    keys = [incident_key(i) for i in (old, new)]
    assert incident_key(new) == keys[1]  # the same whether `old` is still listed or pruned
    assert len(set(keys)) == 2
    # zone and month both matter, and a month before 2010 is a key too (ADR-0024)
    assert incident_key(replace(new, turn=41)) != keys[1]
    assert incident_key(replace(new, turn=-5)) not in keys


def test_year_share_sums_in_a_fixed_order() -> None:
    table = {2020: {"b": 0.1, "a": 0.2, "c": 0.7}, 2030: {"c": 0.5, "a": 0.25, "b": 0.25}}
    flipped = {y: dict(reversed(list(row.items()))) for y, row in table.items()}
    for region in "abc":
        assert _year_share(table, 2024.5, region) == _year_share(flipped, 2024.5, region)

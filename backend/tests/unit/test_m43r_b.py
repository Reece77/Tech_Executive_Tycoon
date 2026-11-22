"""M43r lane B (Codex review 9 findings 5, 7, 8, 9, 10, 12 and 13): classified contracts keep
their clearance, grounded lines hold their backlog, out-licensed programmes reach approval, RNG
keys are each entity's own, exact postings, caches that keep their inputs, and fixed-price
totals that settle the accepted price."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Any

import numpy as np
import pytest

from tests.helpers import fresh_game, with_product
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.government import delivery
from tst.sim.government.models import Contract
from tst.sim.ledger import GOVERNMENT_REVENUE, LedgerEntry
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.space import constellation as con
from tst.sim.space import flights, launch
from tst.sim.space.models import Constellation, LaunchSpec
from tst.sim.state import GameState
from tst.sim.vehicles.draws import gen as _VEHICLE_GEN  # the unpatched stream

PLAYER = 1


# --- finding 7: a grounded line's backlog waits ------------------------------------------------


def _vehicle_line(loaded: LoadedData, turn: int, pending: float) -> GameState:
    b = loaded.balance
    state = replace(fresh_game(loaded), turn=turn)
    p = Product(
        id=9001,
        company_id=PLAYER,
        category=b.space.launch,
        name="Rocket",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    from tst.sim.state import with_product as put

    state = put(state, p)
    spec = LaunchSpec(
        product_id=9001, company_id=PLAYER, payload_kg=20_000.0, reuse="expendable", pending=pending
    )
    return replace(state, space=replace(state.space, launch_specs=(spec,)))


def test_a_grounded_line_holds_its_backlog_until_cleared(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two flights owed; the first fails. Through the grounding nothing flies, no draw changes
    the line, and the backlog flies the month the grounding ends."""
    b = loaded.balance
    t0 = ym_to_turn(2027, 1)
    state = _vehicle_line(loaded, t0, pending=2.0)
    rng = RngFactory(5)
    monkeypatch.setattr(launch, "failure_rate", lambda *a: 1.0)
    state, flown, _, _ = flights.customer_flights(state, rng, b)
    spec = state.space.spec(9001)
    assert spec is not None and len(flown) == 1 and not flown[0].ok
    assert spec.grounded_until is not None and spec.grounded_until > t0 + 1
    assert spec.pending == pytest.approx(1.0) and spec.flights == 1
    monkeypatch.setattr(launch, "failure_rate", lambda *a: 0.0)
    held = spec
    for turn in range(t0 + 1, held.grounded_until):  # type: ignore[arg-type]
        state = replace(state, turn=turn)
        state, flown, _, _ = flights.customer_flights(state, rng, b)
        assert flown == []
        assert state.space.spec(9001) == held  # pending, flights and failures unchanged
    state = replace(state, turn=held.grounded_until)  # type: ignore[arg-type]
    state, flown, _, _ = flights.customer_flights(state, rng, b)
    spec = state.space.spec(9001)
    assert spec is not None and [r.ok for r in flown] == [True]
    assert spec.pending == pytest.approx(0.0) and spec.flights == 2


# --- finding 9: each entity's own draw --------------------------------------------------------


class _Spy:
    """A generator that records its Poisson draws by mean."""

    def __init__(self, gen: np.random.Generator, log: list[tuple[float, int]]) -> None:
        self._gen, self._log = gen, log

    def poisson(self, lam: float) -> int:
        n = int(self._gen.poisson(lam))
        self._log.append((lam, n))
        return n

    def __getattr__(self, name: str) -> Any:
        return getattr(self._gen, name)


def _incident_draws(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch, cars: dict[str, float]
) -> list[tuple[float, int]]:
    from tst.sim.vehicles import autonomy
    from tst.sim.vehicles import spec as vs
    from tst.sim.vehicles.models import VehicleSpec

    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2030, 1))
    state = with_product(state, category=b.vehicles.category, quality=60.0, name="Car")
    pid = max(p.id for p in state.products if p.company_id == PLAYER)
    spec = VehicleSpec(pid, 60.0, "nmc", 150.0, "l4", "own", "catl")
    state = replace(state, vehicle_specs=(spec,))
    log: list[tuple[float, int]] = []
    monkeypatch.setattr(autonomy.draws, "gen", lambda *a: _Spy(_VEHICLE_GEN(*a), log))
    monkeypatch.setattr(vs, "capable_level", lambda *a: "l4")
    monkeypatch.setattr(vs, "level_in", lambda *a: "l4")
    monkeypatch.setattr(autonomy, "cars_on_road", lambda s, p, region, *a: cars.get(region, 0.0))
    autonomy.incidents_month(state, RngFactory(11), b, d)
    return log


def test_a_regions_incident_draw_ignores_exposure_elsewhere(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exposure added only in an earlier region leaves a later region's draw unchanged."""
    regions = loaded.game_data.region_keys
    first, later = regions[0], regions[-1]
    alone = _incident_draws(loaded, monkeypatch, {later: 5.0e9})
    both = _incident_draws(loaded, monkeypatch, {first: 3.0e9, later: 5.0e9})
    lam = 5.0e9 * loaded.balance.vehicles.levels["l4"].incident_rate / 12 / 100_000
    assert [n for m, n in alone if m == pytest.approx(lam)] == [
        n for m, n in both if m == pytest.approx(lam)
    ]


def _bought_keys(loaded: LoadedData, constellations: tuple[Constellation, ...]) -> list[tuple]:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    from tst.sim.facilities.models import Facility
    from tst.sim.state import with_facility

    state = with_facility(
        state,
        Facility(
            id=8001,
            company_id=PLAYER,
            kind=b.space.plant_kind,
            region="north_america",
            capacity=100,
            on_time=100,
            ordered_turn=0,
            ready_turn=0,
            late_turn=0,
            capex_cents=0,
            input_index=1.0,
            capex_paid_cents=0,
            status="live",
        ),
    )
    state = replace(state, space=replace(state.space, constellations=constellations))
    keys: list[tuple] = []
    real_gen = con.draws.gen

    def spy(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
        keys.append(key)
        return real_gen(rng, turn, *key)

    import tst.sim.space.draws as sd

    old = sd.gen
    sd.gen = spy  # type: ignore[assignment]
    try:
        con.month(state, RngFactory(7), b, d, {}, {})
    finally:
        sd.gen = old  # type: ignore[assignment]
    return keys


def _sat(cid: int) -> Constellation:
    return Constellation(
        id=cid,
        company_id=PLAYER,
        name=f"C{cid}",
        kind="broadband",
        product_id=None,
        shells=2,
        mass_kg=300.0,
        life_months=60,
        d2d=False,
        insured=False,
        build_per_month=20,
        launches_per_month=2,
        vehicle_product_id=None,
        created_turn=ym_to_turn(2027, 1),
    )


def test_a_constellations_bought_launch_key_ignores_earlier_constellations(
    loaded: LoadedData,
) -> None:
    from tst.sim.space import draws

    alone = _bought_keys(loaded, (_sat(2),))
    both = _bought_keys(loaded, (_sat(1), _sat(2)))
    mine = [k for k in alone if k[:3] == (draws.FLIGHT, 0, 2)]
    assert mine and mine == [k for k in both if k[:3] == (draws.FLIGHT, 0, 2)]
    assert [k[3] for k in mine] == list(range(len(mine)))  # its own flight ordinal


# --- finding 10: exact postings -----------------------------------------------------------------


def test_a_generic_rivals_cogs_posts_exact_half_even_cents(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """50,000,030 cents x the shipped 55% generics COGS is 27,500,016.5: 27,500,016 cents."""
    from tests.pharma_helpers import base
    from tst.sim.pharma import rivals

    b, d = loaded.balance, loaded.game_data
    assert b.pharma.rivals.generics_cost_shares["5000_cogs"] == 0.55
    state = base(loaded, turn=ym_to_turn(2027, 1))
    generic = next(cid for cid, r in sorted(rivals.companies(state, d).items()) if r.generics)
    monkeypatch.setattr(
        rivals, "monthly_cents", lambda s, cid, *a: 50_000_030 if cid == generic else 0
    )
    entries, revenue = rivals.month(state, {}, 0, b, d)
    assert revenue == {generic: 50_000_030}
    cogs = [e for e in entries if e.lines[0].account == "5000_cogs"]
    assert [e.lines[0].amount for e in cogs] == [27_500_016]


def test_royalties_post_exact_half_even_cents(loaded: LoadedData) -> None:
    from tests.pharma_helpers import base, programme
    from tst.sim.pharma import licensing
    from tst.sim.pharma.models import Deal, DrugMonth

    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2027, 1))
    rival = next(c for c in state.rivals() if c.name == "Eli Lilly")
    p = programme(state, company_id=rival.id, stage="phase3", status="active")
    sales, rate = _half_cent_case()
    deal = Deal(
        id=1,
        kind="out_license",
        company_id=PLAYER,
        counterparty_id=rival.id,
        counterparty="Eli Lilly",
        turn=state.turn,
        programme_id=p.id,
        upfront_cents=0,
        milestones_cents=0,
        royalty=rate,
        share=0.0,
    )
    state = replace(state, pharma_programmes=(p,), pharma_deals=(deal,))
    month = DrugMonth(state.turn, p.id, rival.id, 0.0, sales, sales)
    _, entries, _ = licensing.month(state, (month,), b, d)
    paid = [e for e in entries if e.company_id == PLAYER]
    assert [e.lines[0].amount for e in paid] == [round(Fraction(sales) * Fraction(str(rate)))]


def _half_cent_case() -> tuple[int, float]:
    """1,092,350 cents at a 7% royalty is 76,464.5 cents exactly: half even 76,464, where the
    binary float's product rounds to 76,465."""
    sales, rate = 1_092_350, 0.07
    assert round(sales * rate) == 76_465 and round(Fraction(sales) * Fraction(7, 100)) == 76_464
    return sales, rate


# --- finding 12: caches keep their inputs -------------------------------------------------------


def _reuse(state: GameState, old_key: tuple, new_key: tuple) -> None:
    """Simulate a reused id: the memo entry made for one object now answers another's key."""
    state._memo[new_key] = state._memo[old_key]


def test_arrived_eras_recompute_for_other_rules_under_a_reused_id(loaded: LoadedData) -> None:
    from tst.sim.research import eras

    d = loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2030, 1))
    from tst.sim.research.models import EraArrival

    state = replace(state, era_arrivals=tuple(EraArrival(e.key, 0) for e in d.eras.eras[:3]))
    first = eras.arrived(state, d)
    assert first == eras.arrived(state, d)  # repeated calls with the same rules agree
    other = d.model_copy(update={"eras": d.eras.model_copy(update={"eras": d.eras.eras[:1]})})
    _reuse(state, ("arrived_eras", id(d)), ("arrived_eras", id(other)))
    fresh = replace(state)
    assert eras.arrived(state, other) == eras.arrived(fresh, other)
    assert eras.arrived(state, other) != first


def test_saturation_caches_recompute_for_other_rules_under_a_reused_id(
    loaded: LoadedData,
) -> None:
    from tst.sim.markets import saturation as sat

    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2030, 1))
    home = "north_america"
    values = sat.value_per_customer(state, d, home)
    assert values == sat.value_per_customer(state, d, home)
    cat = d.categories[0]
    m = cat.markets[0]
    bumped = cat.model_copy(
        update={
            "markets": (
                m.model_copy(update={"reference_price_cents": m.reference_price_cents * 3 + 7}),
                *cat.markets[1:],
            )
        }
    )
    other = d.model_copy(update={"categories": (bumped, *d.categories[1:])})
    _reuse(
        state,
        ("market_value_per_customer", id(d), home),
        ("market_value_per_customer", id(other), home),
    )
    fresh = replace(state)
    assert sat.value_per_customer(state, other, home) == sat.value_per_customer(fresh, other, home)
    keys = [(cat.key, home)]
    ceil = sat.ceilings(state, b, d, keys)
    assert ceil == sat.ceilings(state, b, d, keys)
    scale = b.economy_scale.model_copy(update={"money": b.economy_scale.money * 2})
    other_b = b.model_copy(update={"economy_scale": scale})
    wanted = tuple(sorted(set(keys)))
    _reuse(
        state,
        ("market_ceilings", id(d), id(b), wanted),
        ("market_ceilings", id(d), id(other_b), wanted),
    )
    assert sat.ceilings(state, other_b, d, keys) == sat.ceilings(replace(state), other_b, d, keys)


# --- finding 13: fixed-price totals -------------------------------------------------------------


@pytest.mark.parametrize("value", [12_000_007, 12_000_017, 12_000_012, 12_000_000, 11_999_995])
def test_a_fixed_price_contract_settles_its_exact_price(loaded: LoadedData, value: int) -> None:
    """Every month delivered, options exercised: the lifetime revenue is the price exactly, in
    the contract and the ledger (remainders above and below a half cent a month)."""
    b = loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    state = with_product(state, category="cloud_hosting", quality=95.0, name="GovCloud")
    pid = max(p.id for p in state.products if p.company_id == PLAYER)
    t0 = state.turn
    c = Contract(
        id=1,
        tender_id=900,
        company_id=PLAYER,
        product_id=pid,
        government="us",
        area="cloud",
        buyer="civil",
        contract="fixed_price",
        value_cents=value,
        start_turn=t0,
        base_end_turn=t0 + 18,
        end_turn=t0 + 24,
    )
    state = replace(state, gov_contracts=(c,))
    rng = RngFactory(3)
    ledger: list[LedgerEntry] = []
    for turn in range(t0, t0 + 25):
        state = replace(state, turn=turn)
        if turn == c.base_end_turn:
            k = state.gov_contracts[0]
            state = replace(state, gov_contracts=(replace(k, performance=100.0),))
        state, entries, _ = delivery.month(state, rng, b)
        ledger += entries
    done = state.gov_contracts[0]
    assert done.status == "completed" and done.months == 24 and done.options == "exercised"
    booked = -sum(
        line.amount for e in ledger for line in e.lines if line.account == GOVERNMENT_REVENUE
    )
    assert done.revenue_cents == booked == value


def _move_ids(cache: dict, old: object, new: object) -> None:
    """Simulate a reused id in a module cache: each entry keyed by `old`'s id answers `new`'s."""
    for key, value in list(cache.items()):
        if id(old) in key:
            cache[tuple(id(new) if k == id(old) else k for k in key)] = value


def test_fee_drag_recomputes_for_other_rules_under_a_reused_id(loaded: LoadedData) -> None:
    from tst.sim.platforms import fees

    b, d = loaded.balance, loaded.game_data
    category = sorted(b.platforms.app_categories)[0]
    first = fees.fee_drag(category, b, d)
    assert first == fees.fee_drag(category, b, d) > 0
    app = b.platforms.app_categories[category]
    cats = {**b.platforms.app_categories, category: app.model_copy(update={"paid_share": 0.0})}
    other = b.model_copy(
        update={"platforms": b.platforms.model_copy(update={"app_categories": cats})}
    )
    _move_ids(fees._DRAG, b, other)
    assert fees.fee_drag(category, other, d) == 0.0


def test_the_node_timeline_recomputes_for_other_rules_under_a_reused_id(
    loaded: LoadedData,
) -> None:
    from tst.sim.fabs import market, nodes

    b, d = loaded.balance, loaded.game_data
    nf = market.nodes_file(d)
    first = nodes.timeline(5, nf, b.fab)
    assert nodes.timeline(5, nf, b.fab) is first
    mult = b.fab.future_wafer_mult
    fb = b.fab.model_copy(
        update={"future_wafer_mult": mult.model_copy(update={"lo": mult.lo * 2, "hi": mult.hi * 2})}
    )
    _move_ids(nodes._CACHE, b.fab, fb)
    assert nodes.timeline(5, nf, fb) == nodes.build(5, nf, fb) != first

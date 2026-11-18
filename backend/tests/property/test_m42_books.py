"""Pharma's books balance (docs/formulas.md 55.4, M42 sub-task 5): with any efficacy, list
price, commercial support, modality, partner deal and month from launch to well past the loss
of exclusivity, every entry the sales and events months post balances (debits equal credits),
drug revenue is never negative, a company's booked drug sales equal its MRR, and an IRA pick or
the cliff never raises a drug's revenue."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.pharma_helpers import marketed
from tst.loader import load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import DRUG_SALES
from tst.sim.pharma import data as pd
from tst.sim.pharma import demand
from tst.sim.pharma.models import Deal, IraPick
from tst.sim.pharma.month import events_month, sales_month
from tst.sim.rng import RngFactory

LOADED = load_all(Path(__file__).resolve().parents[2] / "data")
B, D = LOADED.balance, LOADED.game_data
LAUNCH = ym_to_turn(2026, 1)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    efficacy=st.floats(0.0, 1.0),
    price=st.floats(0.2, 5.0),
    support=st.floats(0.0, 2.0),
    biologic=st.booleans(),
    months=st.integers(0, 30 * 12),
    partnered=st.booleans(),
    ira=st.booleans(),
    seed=st.integers(1, 5),
)
def test_pharma_entries_balance_through_launch_price_and_cliff(
    efficacy: float,
    price: float,
    support: float,
    biologic: bool,
    months: int,
    partnered: bool,
    ira: bool,
    seed: int,
) -> None:
    modality = "biologic" if biologic else "small_molecule"
    state = marketed(LOADED, turn=LAUNCH, efficacy=efficacy, modality=modality, approved=LAUNCH)
    drug = state.pharma_drugs[0]
    state = replace(
        state,
        turn=LAUNCH + months,
        pharma_drugs=(
            replace(drug, list_cents=max(1, round(drug.list_cents * price)), support=support),
        ),
    )
    p = state.pharma_programmes[0]
    if partnered:
        lilly = next(c for c in state.rivals() if c.name == "Eli Lilly")
        deal = Deal(1, "co_develop", p.company_id, lilly.id, lilly.name, LAUNCH, p.id, share=0.5)
        state = replace(
            state,
            pharma_deals=(deal,),
            pharma_programmes=(replace(p, partner_id=lilly.id, partner_share=0.5),),
        )
    if ira:
        state = replace(state, pharma_ira=(IraPick(pd.year_of(state.turn), p.id, p.name, 0.4),))
    after, entries, revenue = sales_month(state, B, D)
    rng = RngFactory(seed)
    _, more, _ = events_month(after, rng, B, D)
    for e in (*entries, *more):
        assert sum(line.amount for line in e.lines) == 0, e.memo
    player = state.player.id
    booked = -sum(
        line.amount
        for e in entries
        if e.company_id == player
        for line in e.lines
        if line.account == DRUG_SALES
    )
    assert booked == revenue.get(player, 0) >= 0
    # the IRA's discount and the cliff only ever lower revenue
    plain = replace(state, pharma_ira=())
    _, _, out = demand.month(plain, B, D)
    _, _, cut = demand.month(state, B, D)
    assert cut.revenue.get(player, 0) <= out.revenue.get(player, 0)
    later = replace(plain, turn=plain.turn + 12)
    loe = pd.loe_turn(plain, p, pd.US_REGION, D)
    assert loe is not None
    if plain.turn >= loe + 24:
        before = demand.month(replace(plain, turn=loe - 1), B, D)[2].revenue.get(player, 0)
        assert demand.month(later, B, D)[2].revenue.get(player, 0) <= before

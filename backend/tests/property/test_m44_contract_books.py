"""M44 sub-task 3 property test (formulas.md 57.2): government contracts' books balance. For any
contract type, value, term, area, months and seed: every ledger entry balances, cash moves by
exactly revenue less delivery cost, cost-plus revenue is the cost plus the fee (to a cent's
rounding), fixed-price and IDIQ revenue never depends on the overrun, and performance stays in
0-100. Revenue and cost are integer cents."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401  (government.actions is imported through the actions package)
from tests.helpers import fresh_game, with_product
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.government import delivery
from tst.sim.government.models import Contract
from tst.sim.ledger import CASH, CONTRACT_COSTS, GOVERNMENT_REVENUE
from tst.sim.rng import RngFactory

PLAYER = 1


@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    kind=st.sampled_from(["fixed_price", "cost_plus", "idiq"]),
    area=st.sampled_from(["cloud", "ai", "space", "chips", "devices", "cyber"]),
    value=st.integers(min_value=1, max_value=10**13),
    term=st.integers(min_value=1, max_value=120),
    months=st.integers(min_value=1, max_value=18),
    seed=st.integers(min_value=1, max_value=10**6),
)
def test_contract_books_balance(
    loaded: LoadedData, kind: str, area: str, value: int, term: int, months: int, seed: int
) -> None:
    b = loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    state = with_product(state, category="cloud_hosting", quality=70, name="P")
    pid = max(p.id for p in state.products if p.company_id == PLAYER)
    c = Contract(
        id=1,
        tender_id=1,
        company_id=PLAYER,
        product_id=pid,
        government="us",
        area=area,  # type: ignore[arg-type]
        buyer="defence",
        contract=kind,
        value_cents=value,
        start_turn=state.turn,  # type: ignore[arg-type]
        base_end_turn=state.turn + term,
        end_turn=state.turn + term,
    )
    state = replace(state, gov_contracts=(c,))
    rng = RngFactory(seed)
    revenue = cost = cash = 0
    for _ in range(months):
        state, entries, _ = delivery.month(state, rng, b)
        for e in entries:
            assert sum(line.amount for line in e.lines) == 0
            for line in e.lines:
                assert isinstance(line.amount, int)
                if line.account == GOVERNMENT_REVENUE:
                    revenue -= line.amount
                elif line.account == CONTRACT_COSTS:
                    cost += line.amount
                elif line.account == CASH:
                    cash += line.amount
        m = state.gov_contracts[0].month
        if m is not None and kind == "cost_plus" and m.cost_cents:
            assert (
                abs(m.revenue_cents - m.cost_cents * (1 + b.government.delivery.cost_plus_fee))
                <= 1 + m.cost_cents * 1e-12
            )
        if m is not None and kind == "fixed_price":
            assert abs(m.revenue_cents - value / term) <= 1
        assert 0 <= state.gov_contracts[0].performance <= 100
        state = replace(state, turn=state.turn + 1)
    assert cash == revenue - cost
    assert state.gov_contracts[0].revenue_cents == revenue

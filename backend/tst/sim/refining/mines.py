"""Own-group mines feeding refineries (docs/formulas.md 36.1 with 35.3; wired at M20's merge
after M19).

Mines sell in phase 5 (M19), refineries run in phase 4. So a mine's output reaches the group's
refineries by **replacing** what they bought at spot this month: after the mine has supplied its
own designated buyer (35.3), each live plant of the group whose input is a concentrate of the
mine's commodity (`refining.goods.<input>.source`, priced by share) takes, in facility order, up
to the spot input it bought this month. A tonne of mine product is the concentrate for a tonne
of the refined good (`input_per_output` concentrate units a refined unit), so the refinery's
spot purchase is reversed at the concentrate's price and it pays the mine the transfer price
(the mine's own price kind and margin, 31.6; market = the concentrate's price), between two
companies through 5900 and 4300, inside one company not at all (the mine's cost is already in
its month). Next month that volume keeps 100% allocation in a shortage (`Refinery.mine_fed`).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.group import formulas as gf
from tst.sim.ledger import CASH, COGS, LedgerEntry, LedgerLine
from tst.sim.refining import goods as rg
from tst.sim.refining.plants import intercompany, live_refineries, recipe_of
from tst.sim.state import GameState, with_refinery

EPS = 1e-9  # tunable-exempt: float tolerance on volumes
KG_PER_T = 1000.0  # tunable-exempt: unit conversion (M19's prices.per_t)


def _per_t(unit: str) -> float:
    return KG_PER_T if unit == "kg" else 1.0


def feed_from_mine(
    state: GameState,
    mine_company: int,
    commodity: str,
    left_t: float,
    unit_cost_cents_t: float,
    price_kind: str,
    margin: float | None,
    group: set[int],
    name: str,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, float, list[LedgerEntry]]:
    """The module docstring: (state, tonnes of mine product the group's refineries took,
    entries). `unit_cost_cents_t` is the mine's cash cost a tonne this month."""
    entries: list[LedgerEntry] = []
    taken_t = 0.0
    turn = state.turn
    for ref, facility in list(live_refineries(state)):
        if left_t - taken_t <= EPS or facility.company_id not in group:
            continue
        r = recipe_of(ref, balance)
        spec = balance.refining.goods.get(r.input_good) if r.input_good else None
        if spec is None or spec.source != commodity or spec.priced_by != "share":
            continue
        pm = ref.month
        if pm is None or pm.turn != turn or pm.input_spot <= EPS:
            continue
        per_t = _per_t(rg.volume_unit(r.output_good, balance, data))
        conc_per_t = per_t * r.input_per_output  # concentrate units a tonne of mine product
        conc = min(pm.input_spot, (left_t - taken_t) * conc_per_t)
        tonnes = conc / conc_per_t
        conc_price = rg.price_cents(state, r.input_good, balance, data)  # type: ignore[arg-type]
        spot_cents = round(conc * conc_price)
        market_t = round(conc_price * conc_per_t)
        price_t = gf.transfer_price_cents(
            price_kind, round(unit_cost_cents_t), market_t, balance, margin
        )
        paid = round(tonnes * price_t) if facility.company_id != mine_company else 0
        if spot_cents > 0:  # its spot purchase came from the group instead
            entries.append(
                LedgerEntry(
                    turn,
                    facility.company_id,
                    f"{name}: concentrate to the group's plant",
                    (LedgerLine(CASH, spot_cents), LedgerLine(COGS, -spot_cents)),
                )
            )
        entries += intercompany(turn, mine_company, facility.company_id, f"{name}: in-group", paid)
        month = replace(
            pm,
            input_spot=pm.input_spot - conc,
            input_group=pm.input_group + conc,
            input_cents=pm.input_cents - spot_cents + paid,
        )
        if month.output > EPS:
            month = replace(month, unit_cost_cents=month.cost_cents / month.output)
        state = with_refinery(state, replace(ref, month=month, mine_fed=ref.mine_fed + conc))
        taken_t += tonnes
    return state, taken_t, entries


def start_month(state: GameState) -> GameState:
    """Phase 4, before the plants run: last month's mine feed becomes this month's protected
    volume (`mine_protected`) and the feed count starts again."""
    if not any(r.mine_fed or r.mine_protected for r in state.refineries):
        return state
    for ref in state.refineries:
        if ref.mine_fed or ref.mine_protected:
            state = with_refinery(state, replace(ref, mine_protected=ref.mine_fed, mine_fed=0.0))
    return state

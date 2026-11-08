"""The conglomerate discount (docs/formulas.md 31.7): a listed holding company's value is the
sum of its parts x (1 - d). The parts: each company it controls at its value (a listed one at
its market cap; otherwise V_f, 28.1) x the group's effective stake, and its other stakes at
their carrying amounts. d = clamp(base + per_segment x (segments - 1) - synergy x intra-group
share, min, max): segments are the distinct product categories the group sells in; the
intra-group share is the year's transfer-priced supply over the group's revenue."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.group import formulas as gf
from tst.sim.group.transfer import complaint_against, intra_group_share
from tst.sim.ledger import LedgerBalances
from tst.sim.mna import valuation
from tst.sim.money import exact
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, group_companies, group_members


@dataclass(frozen=True, slots=True)
class Discount:
    parts_cents: int
    segments: int
    intra_share: Fraction
    discount: Fraction

    @property
    def value_cents(self) -> int:
        return gf.discounted_cents(self.parts_cents, self.discount)


def segments(state: GameState, root: int) -> int:
    """Distinct categories the group's companies sell in (31.7's unrelated segments)."""
    cats = {
        p.category
        for c in group_companies(state, root)
        for p in state.company_products(c.id)
        if p.status in SELLING
    }
    return max(len(cats), 1)


def part_cents(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    public: bool = False,
) -> int:
    """One company's value (28.1) for the sum of the parts, less a standing complaint's
    discount (31.6). `public` (what the API shows, 31.10): a private company at its displayed
    range's midpoint, never its V_f."""
    cap = valuation.market_cap_cents(state, company_id, balances, balance, data)
    if cap is not None:
        value = cap
    elif public:
        low, high = valuation.value_range_cents(state, company_id, balances, balance, data)
        value = (low + high) // 2
    else:
        value = valuation.fundamental_value_cents(state, company_id, balances, balance, data)
    if complaint_against(state, company_id):
        value = round(value * (1 - exact(balance.group.complaint_discount)))
    return value


def conglomerate(
    state: GameState,
    root: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    public: bool = False,
) -> Discount:
    turn = state.turn
    parts = Fraction(0)
    for m in group_members(state, root):
        if m.end is not None or not state.company(m.company_id).alive:
            continue
        parts += m.effective_at(turn) * part_cents(
            state, m.company_id, balances, balance, data, public
        )
    parts += sum(x.carrying_cents for x in state.stakes if x.is_open and x.owner_id == root)
    revenue = sum(sum(c.mrr_history[-MONTHS_PER_YEAR:]) for c in group_companies(state, root))
    share = intra_group_share(state, revenue)
    n = segments(state, root)
    return Discount(round(parts), n, share, gf.conglomerate_discount(n, share, balance))

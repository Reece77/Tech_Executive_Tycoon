"""What regulators measure (docs/formulas.md 48.1, 48.3), once a month: each group's market
shares by category and region, its platforms' users, its turnover by region and in the world.
Groups: a company's customers and revenue count for its ultimate owner (31.1, as antitrust's)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import INTERCOMPANY_SALES, LedgerEntry
from tst.sim.platforms.phase import home_of, live_in
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, owner_of

OPERATING_END: Final = "4900"  # tunable-exempt: other income and below are not turnover


@dataclass(frozen=True, slots=True)
class View:
    home: str | None
    # (category, region) -> owner -> share of the region's customers in the category
    category_shares: dict[tuple[str, str], dict[int, float]] = field(default_factory=dict)
    # (owner, region) -> the largest share of a region's users on a platform it owns (device
    # platforms: of device users; developer platforms: of their category's)
    users: dict[tuple[int, str], float] = field(default_factory=dict)
    # (owner, region) -> monthly revenue in the region, cents
    region_month: dict[tuple[int, str], int] = field(default_factory=dict)
    # owner -> trailing-year revenue, cents
    world_year: dict[int, int] = field(default_factory=dict)
    # M60: values derived from the fields above, kept on first use (never compared or shown)
    _kept: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def max_share(self, owner: int, region: str) -> tuple[float, str | None]:
        """The owner's largest share in the region (a category, or its platforms' users).
        M60: every owner's and region's at once on first use, scanning the categories in the
        same order with the same comparisons, so the same (share, market)."""
        kept: dict[tuple[int, str], tuple[float, str | None]] | None = self._kept.get("max_share")
        if kept is None:
            kept = {}
            for (category, r), owners in self.category_shares.items():
                for o, share in owners.items():
                    key = (o, r)
                    top = kept.get(key)
                    if top is None:
                        u = self.users.get(key, 0.0)
                        top = (u, "devices" if u > 0 else None)
                    if share > top[0]:
                        top = (share, category)
                    kept[key] = top
            self._kept["max_share"] = kept
        hit = kept.get((owner, region))
        if hit is not None:
            return hit
        users = self.users.get((owner, region), 0.0)
        return users, "devices" if users > 0 else None

    def region_year(self, owner: int, region: str) -> int:
        """The owner's trailing-year revenue in the region: its revenue (`world_year`) split by
        its segments' customers x price there (the books keep no regional split)."""
        totals: dict[int, int] | None = self._kept.get("owner_month")
        if totals is None:  # M60: every owner's at once (integers: any order sums the same)
            totals = {}
            for (o, _r), v in self.region_month.items():
                totals[o] = totals.get(o, 0) + v
            self._kept["owner_month"] = totals
        total = totals.get(owner, 0)
        if total <= 0:
            return 0
        return round(
            self.world_year.get(owner, 0) * self.region_month.get((owner, region), 0) / total
        )


def booked_revenue(entries: Iterable[LedgerEntry], data: GameData) -> dict[int, int]:
    """Each company's revenue booked this month: credits to its operating revenue accounts
    (4000-4899, not intercompany sales), the regulators' turnover (`mrr_history` leaves out
    hardware sales)."""
    revenue = {a.code for a in data.accounts if a.type == "revenue"}
    out: dict[int, int] = {}
    for e in entries:
        for line in e.lines:
            code = line.account
            if code in revenue and code < OPERATING_END and code != INTERCOMPANY_SALES:
                out[e.company_id] = out.get(e.company_id, 0) - line.amount
    return out


def record_turnover(state: GameState, entries: Iterable[LedgerEntry], data: GameData) -> GameState:
    month = booked_revenue(entries, data)
    old = dict(state.reg_turnover)
    books = [c.id for c in state.ledger_companies()]
    rows = tuple(
        (cid, (*old.get(cid, ()), max(0, month.get(cid, 0)))[-MONTHS_PER_YEAR:]) for cid in books
    )
    return replace(state, reg_turnover=rows)


def turnover_year(state: GameState, owner: int) -> int:
    """The group's booked revenue over the last 12 months (its companies under `owner`)."""
    rows = dict(state.reg_turnover)
    return sum(sum(rows.get(c.id, ())) for c in state.companies if owner_of(state, c.id) == owner)


def view(state: GameState, balance: Balance, data: GameData) -> View:
    home = home_of(state, balance, data)
    customers: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    revenue: dict[tuple[int, str], float] = defaultdict(float)
    alive = {c.id for c in state.companies if c.alive and not c.is_chain}
    for product in state.products:
        if product.status not in SELLING or product.company_id not in alive:
            continue
        owner = owner_of(state, product.company_id)
        if home is not None:
            for s in state.segments_of(product.id):
                customers[(product.category, home)][owner] += s.customers
                # money-exact: estimate (a regional split of booked turnover, never posted)
                revenue[(owner, home)] += s.customers * (s.price_cents or 0)
        for r in state.regional_segments_of(product.id):
            customers[(product.category, r.region)][owner] += r.customers
            # money-exact: estimate (a regional split of booked turnover, never posted)
            revenue[(owner, r.region)] += r.customers * (r.price_cents or 0)
    by_category = {}
    for key, owners in customers.items():
        total = sum(owners.values())
        if total > 0:
            by_category[key] = {o: n / total for o, n in owners.items()}
    users: dict[tuple[int, str], float] = {}
    by_id = {p.id: p for p in state.platforms}
    for row in state.platform_regions:
        p = by_id.get(row.platform_id)
        if p is None or p.owner_id is None:
            continue
        if not live_in(p, row.region, state.turn):
            continue
        owner_region = (owner_of(state, p.owner_id), row.region)
        users[owner_region] = max(users.get(owner_region, 0.0), row.users)
    world: dict[int, int] = defaultdict(int)
    rows = dict(state.reg_turnover)
    for c in state.companies:
        if c.id in alive:
            world[owner_of(state, c.id)] += sum(rows.get(c.id, ()))
    return View(
        home=home,
        category_shares=by_category,
        users=users,
        region_month={k: round(v) for k, v in revenue.items()},
        world_year=dict(world),
    )

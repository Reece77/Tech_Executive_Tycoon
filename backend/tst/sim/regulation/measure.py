"""What regulators measure (docs/formulas.md 48.1, 48.3), once a month: each group's market
shares by category and region, its platforms' users, its turnover by region and in the world.
Groups: a company's customers and revenue count for its ultimate owner (31.1, as antitrust's)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.platforms.phase import home_of, live_in
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, owner_of


@dataclass(frozen=True, slots=True)
class View:
    home: str | None
    # (category, region) -> owner -> share of the region's customers in the category
    shares: dict[tuple[str, str], dict[int, float]] = field(default_factory=dict)
    # (owner, region) -> the largest share of a region's users on a platform it owns (device
    # platforms: of device users; developer platforms: of their category's)
    users: dict[tuple[int, str], float] = field(default_factory=dict)
    # (owner, region) -> monthly revenue in the region, cents
    region_month: dict[tuple[int, str], int] = field(default_factory=dict)
    # owner -> trailing-year revenue, cents
    world_year: dict[int, int] = field(default_factory=dict)

    def max_share(self, owner: int, region: str) -> tuple[float, str | None]:
        """The owner's largest share in the region (a category, or its platforms' users)."""
        best = self.users.get((owner, region), 0.0)
        market = "devices" if best > 0 else None
        for (category, r), owners in self.shares.items():
            if r == region and owners.get(owner, 0.0) > best:
                best, market = owners[owner], category
        return best, market

    def region_year(self, owner: int, region: str) -> int:
        return self.region_month.get((owner, region), 0) * MONTHS_PER_YEAR


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
                revenue[(owner, home)] += s.customers * (s.price_cents or 0)
        for r in state.regional_segments_of(product.id):
            customers[(product.category, r.region)][owner] += r.customers
            revenue[(owner, r.region)] += r.customers * (r.price_cents or 0)
    shares = {}
    for key, owners in customers.items():
        total = sum(owners.values())
        if total > 0:
            shares[key] = {o: n / total for o, n in owners.items()}
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
    for c in state.companies:
        if c.id in alive:
            world[owner_of(state, c.id)] += sum(c.mrr_history[-MONTHS_PER_YEAR:])
    return View(
        home=home,
        shares=shares,
        users=users,
        region_month={k: round(v) for k, v in revenue.items()},
        world_year=dict(world),
    )

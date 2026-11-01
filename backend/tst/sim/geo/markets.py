"""Reach in a region (docs/formulas.md 19.5): awareness abroad and where sellers sell.

Built once per phase 5 from the state at its start. Rivals sell by region without offices
(M9 brief): full awareness and every seller everywhere, as before M9.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region, work_region
from tst.sim.geo.formulas import relative_row
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class ReachContext:
    home: str
    player_id: int
    regions_of: Mapping[int, str]  # the player's staff: person id -> region they work in
    present: frozenset[str]  # regions with a player office or presence_people working there
    neighbours: Mapping[str, str]
    indexes: Mapping[str, float]  # region -> price index relative to the home region
    foreign_awareness: float
    neighbour_sellers: float

    def price_index(self, region: str) -> float:
        return 1.0 if region == self.home else self.indexes[region]

    def awareness_factor(self, company_id: int, region: str) -> float:
        """x foreign_awareness on self-serve awareness without local presence (19.5)."""
        if company_id != self.player_id or region == self.home or region in self.present:
            return 1.0
        return self.foreign_awareness

    def splits(self, company_id: int) -> bool:
        """Whether the company's sellers sell only where they work (the player's)."""
        return company_id == self.player_id

    def seller_weights(self, sellers: Iterable[int], region: str) -> dict[int, float]:
        """Sellers working in `region` count 1, those in its neighbour 0.5 (19.5)."""
        out: dict[int, float] = {}
        neighbour = self.neighbours[region]
        for person_id in sellers:
            where = self.regions_of.get(person_id)
            if where == region:
                out[person_id] = 1.0
            elif where == neighbour:
                out[person_id] = self.neighbour_sellers
        return out


def presence_regions(
    state: GameState, regions_of: Mapping[int, str], balance: Balance, data: GameData
) -> frozenset[str]:
    """Regions where the player has an open office or at least presence_people working."""
    present = {data.city(o.city).region for o in state.company_offices(state.player.id)}
    counts: dict[str, int] = {}
    for region in regions_of.values():
        counts[region] = counts.get(region, 0) + 1
    present |= {r for r, n in counts.items() if n >= balance.markets.presence_people}
    return frozenset(present)


def player_regions(state: GameState, balance: Balance, data: GameData) -> dict[int, str]:
    """Where each of the player's staff works, by region."""
    return {
        e.person_id: work_region(state, state.person(e.person_id), balance, data)
        for e in state.staff(state.player.id)
    }


def reach_context(state: GameState, balance: Balance, data: GameData) -> ReachContext | None:
    """None without cities.yaml (test data): v1's markets only."""
    if not data.cities or not data.region_markets:
        return None
    home = home_region(state, balance, data)
    regions_of = player_regions(state, balance, data)
    return ReachContext(
        home=home,
        player_id=state.player.id,
        regions_of=regions_of,
        present=presence_regions(state, regions_of, balance, data),
        neighbours={m.region: m.neighbour for m in data.region_markets},
        indexes={r: relative_row(r, home, data)[1] for r in data.region_keys},
        foreign_awareness=balance.markets.foreign_awareness,
        neighbour_sellers=balance.markets.neighbour_sellers,
    )

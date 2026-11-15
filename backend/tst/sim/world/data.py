"""What the data says about chain companies (docs/formulas.md 41.1), as pure functions.

Capacity of a good in a month to December 2025 is the data's: a named supplier holds its
suppliers.yaml share of `chain_companies.yaml`'s world supply while it sells the good (its
from/until window); a foundry holds its nodes.yaml capacity (thousand wafer starts a month, as
wafers a year); the good's "other producers" hold the rest. So the companies' capacity sums to
world supply in every month (41.8 target 1's capacity totals).

The chain companies of a game are, in this order: chain_companies.yaml's `companies` (each
with the goods it sells in the last history month), then one "other producers" company per good
(commodities.yaml's order, then foundry wafers, then M32's power goods by region), then M32's
power producers (power.yaml's order). A company's position in that list is its stable key
(`rival_key = (CHAIN_KEY, position)`, ADR-0013); M32's are after every earlier one, so no earlier
key moves (ADR-0022 7).

M32 (46.7): each region's power is a good `power_<region>` in MWh a year. Its world capacity is
the region's generation (power.yaml, TWh linear by year to 2025); a named producer holds its
capacity in GW x 8,760 x its mix's fleet capacity factors, and the region's other generators the
rest; demand grows at the region's `demand_growth`, new capacity takes power.yaml `build_months`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.data_models import GameData
from tst.sim.fabs import nodes as nd
from tst.sim.world.config import FOUNDRY_GOOD, ChainCompaniesFile, Personality

THOUSAND: Final = 1000  # tunable-exempt: nodes.yaml capacity is in thousand starts a month
MONTHS: Final = 12  # tunable-exempt: calendar
OTHER_PREFIX: Final = "other_"  # tunable-exempt: an aggregate producer's key is other_<good>
OTHER_PERSONALITY: Final[Personality] = "fast_follower"  # tunable-exempt: the aggregate's
MAX_NAMED: Final = 0.9  # tunable-exempt: named producers' share of a region's generation at most


@dataclass(frozen=True, slots=True)
class ChainSpec:
    """One chain company of the game, from the data."""

    index: int  # its stable key's position
    key: str  # suppliers.yaml / nodes.yaml key, or other_<good>
    name: str
    country: str
    region: str
    personality: Personality
    cost: float
    goods: tuple[str, ...]  # what it produces in the last history month
    is_other: bool = False
    is_foundry: bool = False


def chain_file(data: GameData) -> ChainCompaniesFile:
    if data.chain_companies is None:
        raise RuntimeError("chain_companies.yaml is not loaded")
    return data.chain_companies


POWER_PREFIX: Final = "power_"  # tunable-exempt: a region's power good is power_<region>
TWH: Final = 1_000_000  # tunable-exempt: MWh a TWh
HOURS: Final = 8760  # tunable-exempt: hours a year


def power_goods(data: GameData) -> tuple[str, ...]:
    """M32: one good per region (regions.yaml order) when power.yaml is loaded."""
    if data.power is None:
        return ()
    return tuple(POWER_PREFIX + r.key for r in data.power.regions)


def is_power_good(good: str) -> bool:
    return good.startswith(POWER_PREFIX)


def power_region(good: str) -> str:
    return good.removeprefix(POWER_PREFIX)


def producer_mwh(data: GameData, key: str) -> float:
    """A named power producer's energy a year at its fleet's capacity factors."""
    assert data.power is not None
    p = next(x for x in data.power.producers if x.key == key)
    cf = data.power.fleet_capacity_factor
    return p.gw * 1000 * HOURS * sum(share * cf[tech] for tech, share in p.mix.items())


def producer_region(data: GameData, key: str) -> str:
    assert data.power is not None and data.countries is not None
    p = next(x for x in data.power.producers if x.key == key)
    return data.countries.country(p.country).region


def demand_growth(data: GameData, good: str) -> float:
    if is_power_good(good):
        assert data.power is not None
        return data.power.region(power_region(good)).demand_growth
    return chain_file(data).demand_growth[good]


def build_months(data: GameData, good: str) -> int:
    if is_power_good(good):
        assert data.power is not None
        return data.power.build_months
    return chain_file(data).build_months[good]


def has_world(data: GameData) -> bool:
    return (
        data.chain_companies is not None
        and data.suppliers is not None
        and data.nodes is not None
        and data.commodities is not None
        and data.countries is not None
    )


def commodity_goods(data: GameData) -> tuple[str, ...]:
    assert data.commodities is not None
    return tuple(g.key for g in data.commodities.goods)


def all_goods(data: GameData) -> tuple[str, ...]:
    return (*commodity_goods(data), FOUNDRY_GOOD, *power_goods(data))


def named_shares(data: GameData, good: str, turn: int) -> dict[str, float]:
    """Each named supplier's share of a commodity's world supply in `turn` (suppliers.yaml)."""
    assert data.suppliers is not None
    return {
        s.key: s.goods[good].share
        for s in data.suppliers.suppliers
        if good in s.goods and s.sells(good, turn)
    }


def foundry_wafers(data: GameData, key: str, turn: int) -> float:
    """A named foundry's capacity in `turn` to December 2025, wafers a year."""
    assert data.nodes is not None
    f = next(f for f in data.nodes.foundries if f.key == key)
    return nd.history_capacity(f, min(turn, nd.HISTORY_END)) * THOUSAND * MONTHS


def world_capacity(data: GameData, good: str, turn: int) -> float:
    """World capacity of a good a year in `turn` (to December 2025; held after)."""
    turn = min(turn, nd.HISTORY_END)
    chain = chain_file(data)
    if is_power_good(good):
        assert data.power is not None
        from tst.sim.calendar import turn_to_ym
        from tst.sim.power.config import interp

        twh = data.power.region(power_region(good)).generation_twh
        year, month = turn_to_ym(turn)
        return interp(twh, year + (month - 1) / 12) * TWH
    if good == FOUNDRY_GOOD:
        assert data.nodes is not None
        named = sum(foundry_wafers(data, f.key, turn) for f in data.nodes.foundries)
        return named / (1 - chain.foundry_other_share)
    return chain.supply_at(good, turn)


def capacities(data: GameData, good: str, turn: int) -> dict[str, float]:
    """Every producer's capacity of `good` a year in `turn` (to December 2025): the named ones
    by key and the rest as other_<good>. They sum to `world_capacity`."""
    world = world_capacity(data, good, turn)
    if is_power_good(good):
        assert data.power is not None
        region = power_region(good)
        named = {
            p.key: producer_mwh(data, p.key)
            for p in data.power.producers
            if producer_region(data, p.key) == region
        }
        total = sum(named.values())
        if total > world * MAX_NAMED:  # the data's named fleets at most this of the region
            named = {k: v * world * MAX_NAMED / total for k, v in named.items()}
        out = dict(named)
        out[OTHER_PREFIX + good] = world - sum(out.values())
        return out
    if good == FOUNDRY_GOOD:
        assert data.nodes is not None
        out = {f.key: foundry_wafers(data, f.key, turn) for f in data.nodes.foundries}
    else:
        out = {k: share * world for k, share in named_shares(data, good, turn).items()}
    out[OTHER_PREFIX + good] = world - sum(out.values())
    return out


def country_region(data: GameData, country: str) -> str:
    assert data.countries is not None
    return data.countries.country(country).region


def specs(data: GameData) -> tuple[ChainSpec, ...]:
    """The game's chain companies, in stable-key order (module docstring)."""
    assert data.suppliers is not None and data.nodes is not None and data.countries is not None
    chain = chain_file(data)
    last = nd.HISTORY_END
    foundries = {f.key: f for f in data.nodes.foundries}
    out: list[ChainSpec] = []
    for c in chain.companies:
        country = c.country or data.countries.sites[c.key]
        if c.key in foundries:
            name, is_foundry = foundries[c.key].name, True
            goods: tuple[str, ...] = (FOUNDRY_GOOD,)
        else:
            s = data.suppliers.supplier(c.key)
            assert s is not None
            name, is_foundry = s.name, False
            goods = tuple(g for g in commodity_goods(data) if g in s.goods and s.sells(g, last))
        out.append(
            ChainSpec(
                index=len(out),
                key=c.key,
                name=c.name or name,
                country=country,
                region=country_region(data, country),
                personality=c.personality,
                cost=c.cost,
                goods=goods,
                is_foundry=is_foundry,
            )
        )
    for good in all_goods(data):
        if is_power_good(good):
            assert data.power is not None
            po = data.power.others[power_region(good)]
            out.append(
                ChainSpec(
                    index=len(out),
                    key=OTHER_PREFIX + good,
                    name=f"Other {label(data, good)} generators",
                    country=po.country,
                    region=country_region(data, po.country),
                    personality=OTHER_PERSONALITY,
                    cost=po.cost,
                    goods=(good,),
                    is_other=True,
                )
            )
            continue
        o = chain.others[good]
        out.append(
            ChainSpec(
                index=len(out),
                key=OTHER_PREFIX + good,
                name=f"Other {label(data, good)} producers",
                country=o.country,
                region=country_region(data, o.country),
                personality=OTHER_PERSONALITY,
                cost=o.cost,
                goods=(good,),
                is_other=True,
                is_foundry=good == FOUNDRY_GOOD,
            )
        )
    if data.power is not None:  # M32 (46.7): named power producers, after every earlier key
        for p in data.power.producers:
            region = producer_region(data, p.key)
            out.append(
                ChainSpec(
                    index=len(out),
                    key=p.key,
                    name=p.name,
                    country=p.country,
                    region=region,
                    personality=p.personality,
                    cost=p.cost,
                    goods=(POWER_PREFIX + region,),
                )
            )
    return tuple(out)


def label(data: GameData, good: str) -> str:
    if is_power_good(good):
        return f"{data.region(power_region(good)).label} power"
    if good == FOUNDRY_GOOD:
        return "foundry wafer"
    assert data.commodities is not None
    return data.commodities.good(good).label


def spec_of(data: GameData, key: str) -> ChainSpec | None:
    return next((s for s in specs(data) if s.key == key), None)

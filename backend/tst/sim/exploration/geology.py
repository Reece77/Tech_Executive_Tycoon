"""Geology at game start (docs/formulas.md 34.1): blocks, their hidden deposits, the ore body's
drill positions, and suppliers' starting licences.

Every block draws the same fixed list of numbers on stream `geology` (turn 0, key (region index,
block index)) whether or not it holds a deposit, so appending a commodity or a region to the
data never changes another block (ADR-0013)."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.exploration.config import GeologyFile
from tst.sim.exploration.m17 import buyers_of
from tst.sim.exploration.models import GeoBlock, SupplierLicence
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

GEOLOGY_TURN = 0  # tunable-exempt: deposits are drawn as at January 2010 whatever the start
CELLS_TAG = 1  # key (region, block, 1): the ore body's drill positions
SIGNAL_TAG = 2  # key (region, block, 2): the suppliers' view of a block (34.4)


def _pick(weights: dict[str, float], u: float) -> str:
    total = sum(weights.values())
    acc = 0.0
    for key, w in weights.items():
        acc += w / total
        if u < acc:
            return key
    return next(reversed(weights))


def draw_block(
    gen: np.random.Generator, region: str, index: int, geo: GeologyFile, balance: Balance
) -> GeoBlock:
    """One block (34.1): at most one deposit, of commodity c with chance prospectivity x
    deposit_rate (one uniform picks it), then its type, tonnage, grade, recovery, depth,
    distance to infrastructure, permitting difficulty and community sensitivity."""
    gb = balance.geology
    ground = geo.regions[region]
    u_dep, u_kind, u_rec, u_depth, u_infra = (float(x) for x in gen.random(5))
    z_t, z_g, z_diff, z_sens = (float(x) for x in gen.standard_normal(4))
    lo, hi = gb.depth_m
    depth = lo + (hi - lo) * u_depth
    ilo, ihi = gb.infra_km
    infra = math.exp(math.log(ilo) + (math.log(ihi) - math.log(ilo)) * u_infra)
    difficulty = math.exp(gb.difficulty_sd * z_diff)
    sensitivity = min(1.0, max(0.0, ground.sensitivity + gb.sensitivity_sd * z_sens))
    block = GeoBlock(
        region=region,
        index=index,
        depth_m=depth,
        true_infra_km=infra,
        true_difficulty=difficulty,
        true_sensitivity=sensitivity,
    )
    acc = 0.0
    for c in geo.commodities:
        p = ground.prospectivity[c.key]
        acc += p * gb.deposit_rate
        if u_dep < acc:
            lift = 1 - gb.size_lift / 2 + gb.size_lift * p
            rlo, rhi = c.recovery
            return replace(
                block,
                true_commodity=c.key,
                true_kind=_pick(geo.kinds_of(region, c.key), u_kind),
                true_tonnage_mt=c.tonnage_median_mt * lift * math.exp(c.tonnage_sd * z_t),
                true_grade=min(
                    0.9, c.grade_median * gb.grade_scale * lift * math.exp(c.grade_sd * z_g)
                ),
                true_recovery=rlo + (rhi - rlo) * u_rec,
            )
    return block


def generate_blocks(rng: RngFactory, balance: Balance, data: GameData) -> tuple[GeoBlock, ...]:
    geo = data.geology
    if geo is None:
        return ()
    out = []
    for r, region in enumerate(data.region_keys):
        for b in range(balance.geology.blocks_per_region):
            gen = rng.stream(GEOLOGY_TURN, "geology", r, b)
            out.append(draw_block(gen, region, b, geo, balance))
    return tuple(sorted(out, key=lambda b: (b.region, b.index)))  # the database's order


def cell_deviations(
    rng: RngFactory, region_index: int, block: int, cells: int
) -> tuple[float, ...]:
    """The ore body's drill positions (34.2, M18 decision): standard normal deviations of each
    position's log grade from the deposit's, re-centred and re-scaled so their mean is exactly
    0 and their sd exactly 1. The deposit's true grade is then the geometric mean of its
    positions, which the running mean of distinct holes converges to."""
    z = rng.stream(GEOLOGY_TURN, "geology", region_index, block, CELLS_TAG).standard_normal(cells)
    z = z - z.mean()
    sd = float(z.std())
    return tuple(float(x) / sd for x in z) if sd > 0 else tuple(0.0 for _ in z)


def supplier_licences(
    rng: RngFactory, blocks: tuple[GeoBlock, ...], balance: Balance, data: GameData
) -> tuple[SupplierLicence, ...]:
    """34.4: in each region, for each commodity some supplier produces, its suppliers in turn
    licence the `supplier_blocks` free blocks with the highest signal: what a desk study at a
    range factor of 1 would score, never the truth itself (so a held block says no more than a
    desk study would)."""
    geo, db = data.geology, balance.exploration.desk
    if geo is None or balance.geology.supplier_blocks == 0:
        return ()
    out: list[SupplierLicence] = []
    held: set[tuple[str, int]] = set()
    for r, region in enumerate(data.region_keys):
        mine = [b for b in blocks if b.region == region]
        noise = {
            b.index: rng.stream(GEOLOGY_TURN, "geology", r, b.index, SIGNAL_TAG).standard_normal(
                len(geo.commodities)
            )
            for b in mine
        }
        for c, commodity in enumerate(geo.commodities):
            own = [s for s in buyers_of(data, commodity.key) if commodity.key in s.goods]
            if not own:
                continue
            scored = sorted(
                (
                    -(
                        (db.signal if b.true_commodity == commodity.key else 0.0)
                        + db.noise_sd * float(noise[b.index][c])
                    ),
                    b.index,
                )
                for b in mine
                if (region, b.index) not in held
            )
            for n, (_, index) in enumerate(scored[: balance.geology.supplier_blocks]):
                s = own[(r + n) % len(own)]
                held.add((region, index))
                out.append(SupplierLicence(region, index, s.key, s.name))
    return tuple(sorted(out, key=lambda x: (x.region, x.block)))  # the database's order


def with_geology(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """A new game's geology (any start: campaign, Sandbox or scenario)."""
    blocks = generate_blocks(rng, balance, data)
    return replace(
        state, geo_blocks=blocks, supplier_licences=supplier_licences(rng, blocks, balance, data)
    )


def block_of(state: GameState, region: str, index: int) -> GeoBlock | None:
    for b in state.geo_blocks:
        if b.region == region and b.index == index:
            return b
    return None

"""M53's balance targets (docs/formulas.md 62.5), printed by tools/m53_targets.py.

Each seed's world is played by the engine from January 2010 with the player's company doing nothing
until the script's start (so history holds); then:

2. **Spectrum is scarce and dear:** (a) every area's seeded auctions from 2026 (the model's own
   draws, stream telecom, `tst.sim.telecom.spectrum`), run without the player: the winning price
   over the reserve in the contested ones (demand above the blocks at the reserve), median at
   least 1.5; (b) a player with a national 4G network in North America from January 2016 (low
   band, 20 MHz in the United States) and a mobile line adds 5G radios when 5G arrives, in one arm
   with 100 MHz of mid-band from January 2021 (C-band) and in the other without: five years after
   5G's arrival (April 2024) the arm without holds at least 20% less of the mobile market than the
   arm with (its share lost to the generation, against the same network with mid-band; the line
   is still winning customers from its 2016 launch, so its own share at 5G's arrival is no
   baseline: decision 9).
3. **Networks are capital-heavy:** from January 2026 the player buys spectrum in the United States
   (20 MHz low and 100 MHz mid at the seeded reserve's price a MHz-pop x 2) and builds a national
   5G network there (a national grid's sites, in two years), its mobile line at the market's
   reference price: the months from its first build to cumulative cash at or above zero, median
   at least 60.
4. **Bans bite:** a player that built its North American 4G network on Huawei radios in January
   2016 replaces them with Ericsson's before the US deadline: the replacement's capex over the
   network's capex, at least 10%.
5. **Turn time:** the mean wall-clock time of a turn from 2026 to 2035 in target 3's worlds (the
   guards themselves are M30's `make check-timing`).
"""

from __future__ import annotations

import pickle
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from statistics import median
from typing import Final

import tst.sim.actions  # noqa: F401
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_product, with_product_region, with_segments
from tst.sim.telecom import spectrum
from tst.sim.telecom.actions import AddRadios, BuildTowers, ReplaceRadios
from tst.sim.telecom.models import SpectrumLicence

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**15
NA: Final = "north_america"
US: Final = "united_states"
QUALITY: Final = 70.0
START_2016: Final = ym_to_turn(2016, 1)
NR_ARRIVAL: Final = ym_to_turn(2019, 4)
MID_BAND: Final = ym_to_turn(2021, 1)
SHARE_END: Final = NR_ARRIVAL + 60
START_2026: Final = ym_to_turn(2026, 1)
END: Final = ym_to_turn(2039, 12)
TIMING_END: Final = ym_to_turn(2035, 12)
PRICE_RATIO: Final = 1.5
SHARE_LOSS: Final = 0.20
PAYBACK_MONTHS: Final = 60
BAN_SHARE: Final = 0.10
TOWER_CHUNK: Final = 5000  # the largest tower order
SPECTRUM_PREMIUM: Final = 2.0  # the script pays twice the seeded reserve a MHz-pop (A)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def _world_bytes(seed: int, until: int) -> bytes:
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    while g.state.turn < until:
        g.turn()
    return pickle.dumps((g.state, g.balances))


def world(seed: int, until: int) -> Game:
    state, balances = pickle.loads(_world_bytes(seed, until))
    g = Game(loaded(), state, balances)
    g.state = with_company(g.state, replace(g.state.player, stage=4))
    return g


def _mobile_line(state: GameState) -> tuple[GameState, int]:
    d = loaded().game_data
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=loaded().balance.telecom.mobile,
        name="Nova Mobile",
        status="live",
        quality=QUALITY,
        feature_points=0.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
        held_feature=QUALITY,
    )
    cat = d.category(p.category)
    segs = tuple(
        ProductSegment(pid, m.segment, m.reference_price_cents, 0.0, False, state.turn)
        for m in cat.markets
    )
    state = replace(with_product(state, p), next_ids=ids)
    regional = tuple(
        RegionalSegment(pid, r, s.segment, None, 0.0, False, state.turn)
        for r in d.region_keys
        if r != NA
        for s in segs
    )
    state = with_segments(state, list(segs), list(regional))
    for r in d.region_keys:
        if r != NA:
            state = with_product_region(state, ProductRegion(pid, r, state.turn, state.turn))
    return state, pid


def _licence(state: GameState, band: str, mhz: float, price_cents: int) -> GameState:
    t = state.telecom
    lic = SpectrumLicence(
        id=t.next_licence_id(),
        company_id=PLAYER,
        region=NA,
        area=US,
        band=band,  # type: ignore[arg-type]
        mhz=mhz,
        auction_id=0,
        paid_cents=price_cents,
        turn=state.turn,
        expires_turn=state.turn + 15 * 12,
    )
    return replace(state, telecom=replace(t, licences=(*t.licences, lic)))


def _reserve_price(band: str, mhz: float) -> int:
    """The script's spectrum price: the seeded reserve a MHz-pop x SPECTRUM_PREMIUM, US people."""
    b, d = loaded().balance, loaded().game_data
    r = d.telecom.region(NA)  # type: ignore[union-attr]
    a = r.area(US)
    assert a is not None
    people = r.mobile_at(2025.0) * 1_000_000 * a.share
    per = b.telecom.auction.seeded_reserve_cents_mhz_pop[band]
    return round(per * mhz * people * b.telecom.scale * SPECTRUM_PREMIUM)


def _pay(g: Game, cents: int, memo: str) -> None:
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) - cents


def _build(g: Game, sites: int, gen: str, vendor: str, overlay: bool = False) -> None:
    left = sites
    sizes = sorted(loaded().balance.facility.kinds["tower"].sizes or ())
    while left > 0:
        size = max((s for s in sizes if s <= left), default=sizes[0])
        action = AddRadios if overlay else BuildTowers
        ok = g.act(action(g.founder_id, NA, size, gen, vendor))
        g.state = replace(g.state, person_states=_rested(g.state))
        if not ok:
            raise RuntimeError(f"build refused: {dict(g.refused)}")
        left -= size


def _rested(state: GameState) -> tuple[PersonState, ...]:
    """The founder's energy back (the script acts beyond a month's energy)."""
    return tuple(
        replace(ps, energy=loaded().balance.founder.energy_per_month)
        if ps.energy is not None
        else ps
        for ps in state.person_states
    )


def national_sites() -> int:
    b, d = loaded().balance, loaded().game_data
    full = d.telecom.region(NA).sites_full * b.telecom.scale  # type: ignore[union-attr]
    sizes = sorted(b.facility.kinds["tower"].sizes or ())
    return round(full / sizes[0]) * sizes[0]


def mobile_share(state: GameState, pid: int) -> float:
    cat = loaded().balance.telecom.mobile
    mine = sum(s.customers for s in state.segments_of(pid))
    total = 0.0
    for p in state.products:
        if p.category == cat:
            total += sum(s.customers for s in state.segments_of(p.id))
    return mine / total if total > 0 else 0.0


# --- target 2 ---------------------------------------------------------------------------------


def contested_ratios(seed: int, per_area: int = 3) -> list[float]:
    """Seeded auctions' winning price over reserve where demand exceeded the blocks (2a)."""
    b, d = loaded().balance, loaded().game_data
    g = world(seed, START_2026)
    state = g.state
    rng = RngFactory(state.save_meta.master_seed)
    out = []
    aid = 10_000
    for r in d.telecom.regions:  # type: ignore[union-attr]
        for a in r.areas:
            if a.method != "auction":
                continue
            for n in range(per_area):
                aid += 1
                auc = spectrum._seeded_auction(
                    state, rng, r.key, a.key, START_2026 + n * 12, n, aid, b, d
                )
                bidders = spectrum._rival_bidders(state, auc, rng, b, d)
                if sum(x.blocks for x in bidders) <= auc.blocks:
                    continue  # not contested
                ab = b.telecom.auction
                _, price, _ = spectrum.clock(
                    bidders, auc.blocks, auc.reserve_cents, ab.increment, ab.max_rounds
                )
                out.append(price / auc.reserve_cents)
    return out


def share_arm(seed: int, mid_band: bool) -> tuple[float, float]:
    """(share at 5G's arrival, share five years on) for 2b's arm."""
    g = world(seed, START_2016)
    s, pid = _mobile_line(g.state)
    s = _licence(s, "low", 20.0, _reserve_price("low", 20.0))
    g.state = s
    _build(g, national_sites(), "g4", "ericsson")
    at_arrival = 0.0
    while g.state.turn <= SHARE_END:
        if g.state.turn == NR_ARRIVAL:
            at_arrival = mobile_share(g.state, pid)
            _build(g, national_sites(), "g5", "ericsson", overlay=True)
        if mid_band and g.state.turn == MID_BAND:
            g.state = _licence(g.state, "mid", 100.0, _reserve_price("mid", 100.0))
        g.turn()
    return at_arrival, mobile_share(g.state, pid)


# --- targets 3 and 5 ----------------------------------------------------------------------------


def payback_run(seed: int) -> tuple[int | None, float]:
    """(months from the first build to payback, or None by END; mean seconds a turn 2026-35)."""
    g = world(seed, START_2026)
    s, _ = _mobile_line(g.state)
    for band, mhz in (("low", 20.0), ("mid", 100.0)):
        price = _reserve_price(band, mhz)
        s = _licence(s, band, mhz, price)
        g.state = s
        _pay(g, price, "spectrum")
        s = g.state
    g.state = s
    start = g.state.turn
    half = national_sites() // 2
    _build(g, half, "g5", "ericsson")
    times = []
    built_second = False
    while g.state.turn <= END:
        if not built_second and g.state.turn >= start + 12:
            _build(g, national_sites() - half, "g5", "ericsson")
            built_second = True
        t0 = time.perf_counter()
        g.turn()
        if g.state.turn - 1 <= TIMING_END:
            times.append(time.perf_counter() - t0)
        paid = next((t for c, r, t in g.state.telecom.paid_back if c == PLAYER and r == NA), None)
        if paid is not None:
            return paid - start, sum(times) / len(times)
    return None, sum(times) / max(1, len(times))


# --- target 4 -----------------------------------------------------------------------------------


def ban_run(seed: int) -> float:
    """The replacement's capex over the network's (target 4)."""
    d = loaded().game_data
    g = world(seed, START_2016)
    s, _ = _mobile_line(g.state)
    g.state = _licence(s, "low", 20.0, _reserve_price("low", 20.0))
    _build(g, national_sites(), "g4", "huawei")
    deadline = next(b.replace_turn for b in d.telecom.bans if b.key == "us_huawei")  # type: ignore[union-attr]
    assert deadline is not None
    replace_at = deadline - 12
    while g.state.turn < replace_at:
        g.turn()
    from tst.sim.telecom import equipment as eq

    for r in [x for x in g.state.telecom.radios if x.vendor == "huawei"]:
        f = g.state.facility(r.facility_id)
        assert f is not None
        owed = eq.at_risk_sites(g.state, r, d)
        sizes = sorted(loaded().balance.facility.kinds["radio"].sizes or ())
        size = min((x for x in sizes if x >= owed), default=sizes[-1])
        size = min(size, f.capacity)
        if size not in sizes:
            size = max(x for x in sizes if x <= f.capacity)
        g.act(ReplaceRadios(g.founder_id, r.facility_id, "ericsson", size))
        g.state = replace(g.state, person_states=_rested(g.state))
    while g.state.turn <= deadline:
        g.turn()
    kinds = loaded().balance.telecom
    replaced = sum(
        f.capex_cents
        for r in g.state.telecom.radios
        if r.vendor == "ericsson" and (f := g.state.facility(r.facility_id)) is not None
    )
    network = sum(
        f.capex_cents
        for f in g.state.facilities
        if f.company_id == PLAYER and f.kind in (kinds.tower_kind,)
    )
    return replaced / network if network else 0.0


# --- the run ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedRun:
    seed: int
    ratios: tuple[float, ...]
    with_mid: tuple[float, float]
    without_mid: tuple[float, float]
    payback_months: int | None
    turn_seconds: float
    ban_share: float


def run_seed(seed: int) -> SeedRun:
    months, secs = payback_run(seed)
    return SeedRun(
        seed=seed,
        ratios=tuple(contested_ratios(seed)),
        with_mid=share_arm(seed, True),
        without_mid=share_arm(seed, False),
        payback_months=months,
        turn_seconds=secs,
        ban_share=ban_run(seed),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> list[SeedRun]:
    if workers <= 1:
        return [run_seed(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_seed, seeds))


def _loss(without: tuple[float, float], with_mid: tuple[float, float]) -> float:
    """The share the arm without mid-band holds less than the arm with, five years on."""
    return 1.0 - without[1] / with_mid[1] if with_mid[1] > 0 else 0.0


def report(runs: list[SeedRun]) -> str:
    ratios = [r for x in runs for r in x.ratios]
    losses = [_loss(x.without_mid, x.with_mid) for x in runs]
    paid = [x.payback_months for x in runs]
    never = sum(1 for p in paid if p is None)
    known = sorted(p for p in paid if p is not None)
    med = median(known) if known and never < len(paid) / 2 else None
    lines = [
        "M53 targets (formulas.md 62.5), seeds " + ", ".join(str(x.seed) for x in runs),
        f"T2a contested auctions: median winning price {median(ratios):.2f}x the reserve "
        f"({len(ratios)} auctions, {min(ratios):.2f}-{max(ratios):.2f}); band >= {PRICE_RATIO}: "
        f"{'met' if median(ratios) >= PRICE_RATIO else 'MISSED'}",
        f"T2b without mid-band: {median(losses):.0%} less of the mobile market in April 2024 than "
        f"with it (median; {min(losses):.0%}-{max(losses):.0%}; shares "
        f"{median(x.without_mid[1] for x in runs):.1%} against "
        f"{median(x.with_mid[1] for x in runs):.1%}, from {median(x.with_mid[0] for x in runs):.1%}"
        f" at 5G's arrival); band >= {SHARE_LOSS:.0%}: "
        f"{'met' if median(losses) >= SHARE_LOSS else 'MISSED'}",
        f"T3 national 5G network, North America from January 2026: payback "
        f"{'never' if med is None else f'{med:.0f} months'} (median; {known}, {never} never by "
        f"December 2039); band >= {PAYBACK_MONTHS} months: "
        f"{'met' if med is None or med >= PAYBACK_MONTHS else 'MISSED'}",
        f"T4 rip-and-replace: replacement capex {median(x.ban_share for x in runs):.1%} of the "
        f"network's (median); band >= {BAN_SHARE:.0%}: "
        f"{'met' if median(x.ban_share for x in runs) >= BAN_SHARE else 'MISSED'}",
        f"T5 turn time: {median(x.turn_seconds for x in runs) * 1000:.0f} ms a turn (median, "
        "2026-2035, with a national network); the guards are make check-timing",
    ]
    return "\n".join(lines)

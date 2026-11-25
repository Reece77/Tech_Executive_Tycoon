"""Equipment and bans (docs/formulas.md 62.3).

**A radio's price** (a site's radios of a generation) is the generation's radio cost this year
(telecom.yaml) x the vendor's `price_mult` x the market good `equipment`'s index; from the
player's own `network_equipment` line (vendor "own") it is that line's unit cost (its BOM with
its chips, tst.sim.hardware), so a group that makes its own chips and radios builds cheaper.
A tower adds the site's civil works (mast, power and backhaul) at the year's cost.

**Bans** (telecom.yaml's from their dates, and seeded ones from `telecom.start`, drawn on stream
telecom (0, 3, area index), hidden until announced) exclude a vendor in a licence area. In a
region, a vendor's **banned share** is the sum of its bans' area share x scope:

- from a ban's `no_new` month no new radios from the vendor where its banned share there reaches
  `ban.refuse_share` (the order is refused with the ban's name); below it they may be bought, and
  owe replacement with the rest;
- from its `replace_by` month a record with that vendor owes `ceil(sites x banned share)` sites
  replaced (rip-and-replace: a `radio` order from another vendor that, when live, counts as
  replaced); sites owed but not replaced are switched off (`dark`) until they are;
- a programme (`reimburse`) pays that share of a replacement's capex when it goes live (other
  income, 4900).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import goods
from tst.sim.log import LogItem, inbox_item
from tst.sim.products.models import SELLING, Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.telecom import draws
from tst.sim.telecom.config import OWN_SUPPLIER, BanDef
from tst.sim.telecom.data import end_year_at, file, in_telecom, region_index
from tst.sim.telecom.models import RadioNetwork, SeededBan

SEEDED_VENDORS: Final = ("huawei", "zte")  # tunable-exempt: the vendors seeded bans name (39)


def own_line(state: GameState, company_id: int, balance: Balance) -> Product | None:
    """The company's live network_equipment line, or None."""
    cat = balance.telecom.equipment
    for p in state.products:
        if p.category == cat and p.company_id == company_id and p.status in SELLING:
            return p
    return None


def radio_cents(
    state: GameState,
    company_id: int,
    generation: str,
    vendor: str,
    balance: Balance,
    data: GameData,
) -> float:
    """A site's radios of `generation` from `vendor` (module docstring)."""
    f = file(data)
    year = end_year_at(state.turn)
    if vendor == OWN_SUPPLIER:
        from tst.sim.hardware.production import unit_bom_cents

        p = own_line(state, company_id, balance)
        assert p is not None
        return unit_bom_cents(state, p, balance, data)
    v = f.vendor(vendor)
    assert v is not None
    index = goods.current(state, "equipment", data).index
    return f.generation(generation).radio_at(year) * v.price_mult * index


def civil_cents(state: GameState, data: GameData) -> float:
    index = goods.current(state, "equipment", data).index
    return file(data).site_civil_at(end_year_at(state.turn)) * index


# --- Bans ----------------------------------------------------------------------------------------


def _bans(state: GameState, data: GameData) -> list[BanDef | SeededBan]:
    return [*file(data).bans, *state.telecom.world.bans]


def _share(ban: BanDef | SeededBan, data: GameData) -> float:
    r = file(data).region(ban.region)
    a = r.area(ban.area)
    scope = ban.scope if isinstance(ban, BanDef) else 1.0
    return (a.share if a is not None else 0.0) * scope


def _no_new(ban: BanDef | SeededBan) -> int:
    return ban.no_new_turn if isinstance(ban, BanDef) else ban.announced_turn


def _replace(ban: BanDef | SeededBan) -> int | None:
    return ban.replace_turn


def banned_new_share(state: GameState, region: str, vendor: str, data: GameData) -> float:
    """The vendor's share of the region that may not buy new radios from it now."""
    return min(
        1.0,
        sum(
            _share(b, data)
            for b in _bans(state, data)
            if b.vendor == vendor and b.region == region and state.turn >= _no_new(b)
        ),
    )


def refusing_ban(
    state: GameState, region: str, vendor: str, balance: Balance, data: GameData
) -> str | None:
    """The ban that refuses a new radio order from the vendor in the region, if any."""
    if banned_new_share(state, region, vendor, data) < balance.telecom.ban.refuse_share:
        return None
    for b in _bans(state, data):
        if b.vendor == vendor and b.region == region and state.turn >= _no_new(b):
            return b.label if isinstance(b, BanDef) else f"{vendor} ban ({b.area})"
    return None


def owed_share(state: GameState, region: str, vendor: str, data: GameData) -> float:
    """The vendor's share of the region whose radios must be replaced by now."""
    return min(
        1.0,
        sum(
            _share(b, data)
            for b in _bans(state, data)
            if b.vendor == vendor
            and b.region == region
            and (t := _replace(b)) is not None
            and state.turn >= t
        ),
    )


def owed_sites(state: GameState, record: RadioNetwork, data: GameData) -> int:
    f = state.facility(record.facility_id)
    live = f.live_capacity(state.turn) if f is not None else 0
    share = owed_share(state, record.region, record.vendor, data)
    return math.ceil(live * share - 1e-9) if share > 0 else 0  # tunable-exempt: tolerance


def at_risk_sites(state: GameState, record: RadioNetwork, data: GameData) -> int:
    """Sites any announced ban will make it replace (shown before the deadline)."""
    f = state.facility(record.facility_id)
    live = f.live_capacity(state.turn) if f is not None else 0
    share = min(
        1.0,
        sum(
            _share(b, data)
            for b in _bans(state, data)
            if b.vendor == record.vendor
            and b.region == record.region
            and _replace(b) is not None
            and state.turn >= b.announced_turn
        ),
    )
    return math.ceil(live * share - 1e-9) if share > 0 else 0  # tunable-exempt: tolerance


def dark_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Each record's dark sites: owed by the deadlines and not yet replaced."""
    t = state.telecom
    if not t.radios:
        return state, []
    logs: list[LogItem] = []
    out = []
    changed = False
    for r in t.radios:
        dark = max(0, owed_sites(state, r, data) - r.replaced)
        if dark != r.dark:
            changed = True
            if dark > r.dark:
                logs.append(
                    inbox_item(
                        state.turn,
                        r.company_id,
                        "telecom_sites_dark",
                        sites=f"{dark:,}",
                        vendor=_vendor_label(r.vendor, data),
                        region=data.region(r.region).label,
                    )
                )
            r = replace(r, dark=dark)
        out.append(r)
    if not changed:
        return state, []
    return replace(state, telecom=replace(t, radios=tuple(out))), logs


def _vendor_label(vendor: str, data: GameData) -> str:
    if vendor == OWN_SUPPLIER:
        return "your own"
    v = file(data).vendor(vendor)
    return v.label if v is not None else vendor


def seeded_bans_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """At telecom.start: each auctioning area's seeded ban (hidden until announced); from then,
    the month one is announced, an inbox note for a company with telecom."""
    tb = balance.telecom
    t = state.telecom
    logs: list[LogItem] = []
    if state.turn == tb.start_turn and not t.world.bans:
        bans = []
        f = file(data)
        banned = {(b.region, b.area, b.vendor) for b in f.bans}
        for r in f.regions:
            for i, a in enumerate(r.areas):
                g = draws.gen(
                    rng, state.turn, draws.WORLD, draws.BAN, region_index(r.key, data) * 100 + i
                )
                if g.random() >= tb.ban.seeded_chance:
                    continue
                vendor = SEEDED_VENDORS[int(g.integers(0, len(SEEDED_VENDORS)))]
                if (r.key, a.key, vendor) in banned:
                    continue
                w, rw = tb.ban.seeded_window, tb.ban.seeded_replace_years
                start = state.turn + round((w.lo + (w.hi - w.lo) * g.random()) * 12)
                years = rw.lo + (rw.hi - rw.lo) * g.random()
                bans.append(SeededBan(vendor, r.key, a.key, start, start + round(years * 12)))
        t = replace(t, world=replace(t.world, bans=tuple(bans)))
        state = replace(state, telecom=t)
    for b in state.telecom.world.bans:
        if b.announced_turn != state.turn:
            continue
        for c in state.companies:
            if c.is_player and c.alive and in_telecom(state, c.id, balance):
                logs.append(
                    inbox_item(
                        state.turn,
                        c.id,
                        "telecom_ban_announced",
                        vendor=_vendor_label(b.vendor, data),
                        region=data.region(b.region).label,
                        area=b.area,
                    )
                )
    return state, logs

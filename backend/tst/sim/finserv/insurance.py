"""Insurers (docs/formulas.md 64.3). Amounts are integer cents; ratios are floats multiplied into
money only through `times`.

**Premiums** are an insurance line's revenue (phase 5's ordinary booking: price x policies).
**Claims** a month, by line = premiums x the claims ratio:

    claims ratio = (combined ratio - expense share) x (reference price / price) ** price_elasticity
                   x (1 - skill_cut x team skill)

with the combined ratio the data's year (to 2025; it holds the year's catastrophes), then the
line's mean over `insurance.base_years` plus a catastrophe's points in the month one happens
(property only; stream finserv (1, region index, year), drawn in its month: each month a region's
chance is 1 - (1 - cat.chance) ** (1/12), and a hit adds a year's `cat.extra` points to that
month's property claims there, x `cat.region_mult` for the hit region's own share). The team skill
is the line's builders' finance and data skills (0-1).

**The float.** Claims are reserved when incurred (Dr 5510 claims, Cr 2320 reserves) and paid by
`claims_lag_months` (a line's reserves / lag a month: Dr 2320, Cr 1330). The reserves' cash is
invested: the month's premiums less expenses' cash stays with the company, and an amount equal to
the change in reserves moves from cash into 1330 (Dr 1330, Cr cash). 1330 earns the region's
policy rate + `float_spread` (Dr 1330, Cr 4520). Own funds = 1330 - 2320.

**Solvency** (64.3): required = a year's premiums x premium_share + reserves x reserve_share
(Solvency II in Europe from 2016, finance_services.yaml); below it the insurer writes no new
business (tst.sim.finserv.gates).

**Rivals'** insurance lines post the same claims ratio, paid at once (no float), so their margins
follow the data.
"""

from __future__ import annotations

from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import draws
from tst.sim.finserv.config import series_at
from tst.sim.finserv.data import MONTHS, PCT, file, team_skill, year_at
from tst.sim.finserv.models import Catastrophe, InsuranceMonth, Insurer
from tst.sim.fx.rates import policy_rate
from tst.sim.ledger import CASH, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import ceil_div, times, times_over
from tst.sim.products.models import SELLING, Product
from tst.sim.rng import RngFactory, text_key
from tst.sim.state import GameState

INVESTMENTS: Final = "1330_insurer_investments"
RESERVES: Final = "2320_claims_reserves"
INVESTMENT_INCOME: Final = "4520_investment_income"
CLAIMS: Final = "5510_claims"
CAT_KEY: Final = 1  # ADR-0013: finserv (1, region index, year)
SKILLS: Final = ("finance", "data")  # tunable-exempt: the pricing team's skills


def line_of(segment: str) -> str:
    return segment.removeprefix("ins_")


def combined_ratio(state: GameState, line: str, balance: Balance, data: GameData) -> float:
    """The line's combined ratio, a fraction, before this month's catastrophes."""
    f = file(data).insurance
    pts = f.combined_ratio[line]
    if state.turn < balance.finserv.start_turn:
        return series_at(pts, year_at(state.turn)) / PCT
    ib = balance.finserv.insurance
    lo, hi = int(ib.base_years.lo), int(ib.base_years.hi)
    return sum(series_at(pts, float(y)) for y in range(lo, hi + 1)) / (hi - lo + 1) / PCT


def cat_extra(state: GameState, region: str) -> float:
    """Points a catastrophe adds to property's combined ratio this month (0 without one)."""
    return sum(
        c.extra for c in state.finserv.world.cats if c.turn == state.turn and c.region == region
    )


def draw_cats(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """This month's catastrophes, from `finserv.start` (module docstring): drawn now, stored only
    once they have happened."""
    from dataclasses import replace

    if state.turn < balance.finserv.start_turn:
        return state
    cb = balance.finserv.insurance.cat
    year = turn_to_ym(state.turn)[0]
    chance = 1.0 - dmath.pow(1.0 - cb.chance, 1.0 / MONTHS)
    shares = file(data).insurance.cat_region_share
    cats = list(state.finserv.world.cats)
    for region in data.region_keys:
        g = draws.gen(rng, state.turn, CAT_KEY, text_key(region), year, state.turn)
        if float(g.random()) >= chance * shares[region] * len(shares):
            continue
        extra = cb.extra.lo + (cb.extra.hi - cb.extra.lo) * float(g.random())
        cats.append(Catastrophe(state.turn, region, extra * cb.region_mult * MONTHS))
    if len(cats) == len(state.finserv.world.cats):
        return state
    world = replace(state.finserv.world, cats=tuple(cats))
    return replace(state, finserv=replace(state.finserv, world=world))


def claims_ratio(
    state: GameState,
    product: Product,
    segment: str,
    region: str,
    price: int,
    balance: Balance,
    data: GameData,
    skill: float,
) -> float:
    ib = balance.finserv.insurance
    line = line_of(segment)
    f = file(data).insurance
    combined = combined_ratio(state, line, balance, data)
    if line == "property":
        combined += cat_extra(state, region) / PCT
    base = combined - f.expense_share[line]
    ref = data.category(product.category).market(segment).reference_price_cents
    index = data.region_market(region).price_index
    rel = (ref * index) / price if price > 0 else 1.0  # money-exact: ratio
    return max(0.0, base * dmath.pow(rel, ib.price_elasticity) * (1.0 - ib.skill_cut * skill))


def _lines(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> list[tuple[Product, str, str, int, float]]:
    """(line, segment, region, price, policies) of the company's insurance lines."""
    home = home_region_of(state, balance, data)
    cat = balance.finserv.insurance_category
    out = []
    for p in state.company_products(company_id):
        if p.category != cat or p.status not in SELLING:
            continue
        for s in state.segments_of(p.id):
            if s.price_cents:
                out.append((p, s.segment, home, s.price_cents, s.customers))
        for r in state.regional_segments_of(p.id):
            if r.price_cents:
                out.append((p, r.segment, r.region, r.price_cents, r.customers))
    return out


def premiums_cents(state: GameState, company_id: int, balance: Balance, data: GameData) -> int:
    return sum(times(price, n) for _, _, _, price, n in _lines(state, company_id, balance, data))


def required_cents(state: GameState, insurer: Insurer, balance: Balance, data: GameData) -> int:
    """What the solvency rules ask (module docstring), at the insurer's licensed regions' rules
    weighted by its premiums there."""
    year = times(premiums_cents(state, insurer.company_id, balance, data), MONTHS)
    regions = [x.region for x in insurer.licences] or ["north_america"]
    rule = max(
        (file(data).insurance.solvency_at(r, state.turn) for r in regions),
        key=lambda r: r.premium_share,
    )
    return times(year, rule.premium_share) + times(insurer.reserves_cents, rule.reserve_share)


def solvent(state: GameState, insurer: Insurer, balance: Balance, data: GameData) -> bool:
    return insurer.own_funds_cents >= required_cents(state, insurer, balance, data)


def insurer_month(
    state: GameState, insurer: Insurer, balance: Balance, data: GameData
) -> tuple[Insurer, list[LedgerEntry], list[LogItem], InsuranceMonth]:
    """The player's insurer's month: licences decided, claims reserved and paid, float invested
    and earning (module docstring)."""
    from dataclasses import replace

    ib = balance.finserv.insurance
    f = file(data).insurance
    logs: list[LogItem] = []
    licences = []
    for lic in insurer.licences:
        if (
            lic.status == "applying"
            and lic.active_turn is not None
            and state.turn >= lic.active_turn
        ):
            lic = replace(lic, status="active")
            logs.append(
                inbox_item(
                    state.turn,
                    insurer.company_id,
                    "insurance_licensed",
                    region=data.region(lic.region).label,
                )
            )
        licences.append(lic)
    insurer = replace(insurer, licences=tuple(licences))
    claims: dict[str, int] = {}
    premiums = 0
    cat_hit = False
    for p, seg, region, price, n in _lines(state, insurer.company_id, balance, data):
        prem = times(price, n)
        premiums += prem
        skill = team_skill(state, p, SKILLS, balance, data)
        ratio = claims_ratio(state, p, seg, region, price, balance, data, skill)
        line = line_of(seg)
        claims[line] = claims.get(line, 0) + times(prem, ratio)
        cat_hit = cat_hit or (line == "property" and cat_extra(state, region) > 0)
    reserves = dict(insurer.reserves_by_line)
    paid = 0
    for line in sorted(set(reserves) | set(claims)):
        r = reserves.get(line, 0)
        # rounded up (M57r-A, review 10 item 8): a reserve clears completely once claims stop
        pay = ceil_div(r, max(1, f.claims_lag_months[line])) if r > 0 else 0
        reserves[line] = r - pay + claims.get(line, 0)
        paid += pay
    incurred = sum(claims.values())
    total_reserves = sum(reserves.values())
    invest = total_reserves - insurer.reserves_cents + paid  # cash into 1330: the new reserves
    region = next((x.region for x in insurer.licences), "north_america")
    rate = (policy_rate(state, region, balance, data) + ib.float_spread) / PCT
    income = times_over(insurer.investments_cents, MONTHS, max(0.0, rate))
    lines = [
        LedgerLine(CLAIMS, incurred),
        LedgerLine(RESERVES, -incurred),
        LedgerLine(RESERVES, paid),
        LedgerLine(INVESTMENTS, -paid),
        LedgerLine(INVESTMENTS, invest),
        LedgerLine(CASH, -invest),
        LedgerLine(INVESTMENTS, income),
        LedgerLine(INVESTMENT_INCOME, -income),
    ]
    merged: dict[str, int] = {}
    for x in lines:
        merged[x.account] = merged.get(x.account, 0) + x.amount
    rows = tuple(LedgerLine(a, v) for a, v in merged.items() if v)
    entries = (
        [
            LedgerEntry(
                turn=state.turn,
                company_id=insurer.company_id,
                memo="Insurer: claims, float and investment income",
                lines=rows,
            )
        ]
        if rows
        else []
    )
    was_solvent = solvent(state, insurer, balance, data)
    insurer = replace(
        insurer,
        investments_cents=insurer.investments_cents - paid + invest + income,
        reserves_cents=total_reserves,
        reserves_by_line=tuple(sorted(reserves.items())),
    )
    need = required_cents(state, insurer, balance, data)
    if was_solvent and insurer.own_funds_cents < need and premiums > 0:
        logs.append(
            inbox_item(
                state.turn,
                insurer.company_id,
                "insurance_insolvent",
                own_cents=insurer.own_funds_cents,
                required_cents=need,
            )
        )
    record = InsuranceMonth(
        turn=state.turn,
        company_id=insurer.company_id,
        premiums_cents=premiums,
        claims_cents=incurred,
        paid_cents=paid,
        investment_income_cents=income,
        float_cents=total_reserves,
        own_funds_cents=insurer.own_funds_cents,
        required_cents=need,
        combined_ratio=(incurred / premiums if premiums else 0.0),  # money-exact: ratio
        catastrophe=cat_hit,
    )
    return insurer, entries, logs, record


def rival_claims(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    """Rivals' insurance lines' claims this month (paid at once), at the data's claims ratio."""
    cat = balance.finserv.insurance_category
    home = home_region_of(state, balance, data)
    ledger = {c.id for c in state.ledger_companies() if not c.is_player}
    by_company: dict[int, int] = {}
    for p in state.products:
        if p.category != cat or p.company_id not in ledger or p.status not in SELLING:
            continue
        rows = [(s.segment, home, s.price_cents, s.customers) for s in state.segments_of(p.id)]
        rows += [
            (r.segment, r.region, r.price_cents, r.customers)
            for r in state.regional_segments_of(p.id)
        ]
        for seg, region, price, n in rows:
            if not price or n <= 0:
                continue
            prem = times(price, n)
            ratio = claims_ratio(state, p, seg, region, price, balance, data, 0.0)
            by_company[p.company_id] = by_company.get(p.company_id, 0) + times(prem, ratio)
    return [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=cid,
            memo="Insurance claims",
            debit=CLAIMS,
            credit=CASH,
            amount=v,
        )
        for cid, v in sorted(by_company.items())
        if v > 0
    ]

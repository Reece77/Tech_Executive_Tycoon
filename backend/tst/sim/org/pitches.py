"""Executives' pitches: big moves they propose for the founder to approve (docs/formulas.md
27.1, M13b; ADR-0015).

In phase 2, after the seats' monthly rules, each executive with authority (and the CEO, for
the functions no seat holder with authority covers) may pitch once a quarter: in a quarter's
first month, with probability clamp(0.45 + 0.04 (ambition - 10), 0.15, 0.9) from their true
ambition (stream `pitch`, key (person id,), first uniform). They pitch the best candidate of
their function with probability clamp(0.55 + 0.03 s, 0.6, 0.98) from their true seat score
(second uniform), else the second best.

Every candidate is scored, and every number a pitch shows is computed, from what the company
can see (ADR-0015, ADR-0007): displayed skill midpoints, public market sizes and prices, its
own customers and costs. The low and high cases widen for an executive the company rates
lower (its displayed seat score). True ambition and true score decide only whether there is
a pitch and which candidate; they never reach a number (27.6).

Approving runs the move through the normal actions with the executive as actor (their energy,
the seat's guardrails), or the founder for a Chair's decision (a buyback). On Holiday a pitch
whose cost over pitch.cost_months is under the spend limit goes ahead in phase 2. A pitch
still pending at its executive's next quarterly draw lapses. Approved pitches are scored
against their low case pitch.record_months after approval: hit, miss, or too early when
what they created is not yet operating.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final

import numpy as np

from tst.sim.actions import (
    Action,
    AssignUnit,
    BuildFacility,
    CreatePlan,
    CreateProduct,
    CreateUnit,
    LaunchInRegion,
    LeaseOffice,
    SetPrice,
    StartProject,
    SunsetProduct,
    apply_action,
)
from tst.sim.data_models import Balance, CategoryDef, GameData
from tst.sim.errors import SimError
from tst.sim.events.models import Modifier
from tst.sim.facilities import compute, lifecycle
from tst.sim.facilities import formulas as ff
from tst.sim.geo import formulas as gf
from tst.sim.hiring.formulas import market_mid_cents
from tst.sim.ledger import CASH, MARKETING, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents, format_money
from tst.sim.org.delegates import delegate_draws
from tst.sim.org.executives import displayed_score
from tst.sim.org.formulas import (
    auto_approve_limit,
    auto_approves,
    case_spread,
    decision_quality,
    decline_morale,
    pitch_chance,
    pitch_pick,
)
from tst.sim.org.models import CaseUnit, Pitch, PitchKind
from tst.sim.people.reveal import revealed_range
from tst.sim.products.formulas import coord_factor
from tst.sim.products.models import SELLING
from tst.sim.research import levels
from tst.sim.rng import RngFactory
from tst.sim.scale import clamp_morale
from tst.sim.state import GameState, with_modifier, with_person_state, with_pitch

MONTHS_PER_QUARTER: Final = 3  # tunable-exempt: calendar
MONTHS_PER_YEAR: Final = 12  # tunable-exempt: calendar
PCT: Final = 100  # tunable-exempt: percent
SCORE_MAX: Final = 100.0  # tunable-exempt: quality and brand scale
ATTR_MAX: Final = 20.0  # tunable-exempt: attribute scale
NEUTRAL_FIT: Final = 0.5  # tunable-exempt: fit with no builders to judge
# Candidates of every kind are ranked by an estimated value over 24 months in cents (27.1):
# a monthly case x pitch.record_months; research by the quality-cap lift it buys on the revenue it feeds; an
# office by the builder pay of the roles it fills (x its city's talent weight); a campaign by
# its customers' revenue. Returning cash (a buyback) ranks below every growth move.
RETURN_SCORE: Final = 1.0  # tunable-exempt: ranks a buyback last, after any growth move
DRAWS: Final = 2  # uniforms on the pitch stream a draw month: whether, then which (27.1)
CHAIR_KINDS: Final = frozenset({"buyback"})  # approved as the Chair, not the executive (25.6)
# The pitch kinds of each seat (27.1); the CEO pitches those of the functions it runs.
SEAT_KINDS: Final[dict[str, tuple[PitchKind, ...]]] = {
    "cpo": ("new_product", "sunset"),
    "cro": ("region",),
    "cto": ("research", "data_centre"),
    "coo": ("office", "plant"),
    "cmo": ("campaign",),
    "cfo": ("buyback",),
}
CEO_SCOPE_SEAT: Final = {"products": "cpo"}  # the CEO's products scope pitches as the CPO
KIND_SEAT: Final = {k: seat for seat, kinds in SEAT_KINDS.items() for k in kinds}
BUILDER = "builder"
BUILDER_ROLE = "software_engineer"
PLAN_CHANNEL = "any"
MANUFACTURING_KIND = "assembly"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One move an executive could pitch, with its displayed numbers (27.1)."""

    kind: PitchKind
    params: tuple[tuple[str, int | str], ...]
    title: str
    why: str
    score: float  # higher is better; the central case's value
    central: float  # the case at 24 months, in `unit`
    unit: CaseUnit
    capex_cents: int = 0
    monthly_cents: int = 0
    hires: int = 0
    risk: str = ""

    def cost_cents(self, months: int) -> int:
        return self.capex_cents + self.monthly_cents * months


# --- Displayed knowledge ----------------------------------------------------------------------


def _mid(state: GameState, company: int, person_id: int, key: str) -> float | None:
    person = state.person(person_id)
    reveal = state.reveal(company, person_id)
    if person.is_founder:
        return float(person.skills[key]) if key in person.skills.as_dict() else None
    if reveal is None:
        return None
    lo, hi = revealed_range(person, reveal, key)
    return (lo + hi) / 2


def _builders(state: GameState, company: int, data: GameData) -> list[int]:
    out = []
    for e in state.staff(company):
        if e.status != "active":
            continue
        if state.person(e.person_id).is_founder or data.role(e.role).product_function == BUILDER:
            out.append(e.person_id)
    return out


def category_fit(state: GameState, company: int, category: CategoryDef, data: GameData) -> float:
    """The company's displayed skill match for a category's builder skills, 0-1 (27.1): the
    mean over its builders of the dev-weighted displayed skill midpoints / 20."""
    weights = category.dev_weights
    total = sum(weights.values())
    scores = []
    for pid in _builders(state, company, data):
        vals = [(w, _mid(state, company, pid, k)) for k, w in weights.items()]
        if any(v is None for _, v in vals) or total <= 0:
            continue
        scores.append(sum(w * float(v or 0.0) for w, v in vals) / total / ATTR_MAX)
    return sum(scores) / len(scores) if scores else NEUTRAL_FIT


def shown_seat_score(
    state: GameState, company: int, person_id: int, seat: str, b: Balance
) -> float:
    """The seat score from displayed ranges (18.8); the CEO's from its weights (25.6)."""
    if seat == "ceo":
        weights = b.ceo.weights
        vals = [(w, _mid(state, company, person_id, k)) for k, w in weights.items()]
        known = [(w, v) for w, v in vals if v is not None]
        total = sum(w for w, _ in known)
        return sum(w * v for w, v in known) / total if total else b.exec_seats.score_mid
    return displayed_score(state, company, person_id, seat, b)


def product_mrr(state: GameState, product_id: int, region: str | None = None) -> int:
    """A product's monthly revenue at its current customers and prices, at home and abroad (or
    in one region)."""
    total = 0.0
    if region is None:
        total += sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product_id))
        rows = state.regional_segments_of(product_id)
    else:
        rows = state.regional_segments_of(product_id, region)
    total += sum(s.customers * (s.price_cents or 0) for s in rows)
    return round(total)


def _price_per_customer(state: GameState, product_id: int) -> float:
    customers = _customers(state, product_id)
    return product_mrr(state, product_id) / customers if customers > 0 else 0.0


def _customers(state: GameState, product_id: int) -> float:
    return sum(s.customers for s in state.segments_of(product_id)) + sum(
        s.customers for s in state.regional_segments_of(product_id)
    )


def _salary_month(role: str, b: Balance, data: GameData) -> int:
    mid = data.role(role).salary_band_mid_cents["mid"]
    bp = data.region(b.founder.default_region).salary_multiplier_bp
    return round(market_mid_cents(mid, bp) / MONTHS_PER_YEAR)


def _builder_room(state: GameState, company: int, cap: float, data: GameData) -> int:
    have = sum(
        1
        for e in state.staff(company)
        if not state.person(e.person_id).is_founder
        and data.role(e.role).product_function == BUILDER
    )
    return max(0, int(cap) - have)


def _guard(state: GameState, company: int, seat: str, key: str, b: Balance) -> object:
    a = state.authority(company, seat)
    rails = dict(a.guardrails) if a is not None else {}
    if key in rails:
        return rails[key]
    value = b.exec_authority.defaults[seat].get(key)
    return tuple(value) if isinstance(value, list) else value


# --- Candidates by seat (27.1) -----------------------------------------------------------------


def _new_products(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    allowed = set(_guard(state, company, "cpo", "categories", b) or ())  # type: ignore[call-overload]
    mine = {p.category for p in state.company_products(company) if p.status != "retired"}
    cap = float(_guard(state, company, "cpo", "headcount_cap", b) or 0)  # type: ignore[arg-type]
    team = min(pb.team_builders, int(cap))
    if team < 1:
        return []
    year = state.turn // MONTHS_PER_YEAR
    out = []
    for cat in data.categories:
        if cat.key in mine or cat.capacity_market or cat.assembly_market or cat.sells_units:
            continue
        if allowed and cat.key not in allowed:
            continue
        best: tuple[float, str, float, int] | None = None
        for m in cat.markets:
            market = state.market(cat.key, m.segment)
            if market is None:
                continue
            rivals = sum(
                1
                for s in state.product_segments
                if s.segment == m.segment
                and (p := state.product(s.product_id)) is not None
                and p.category == cat.key
                and p.status in SELLING
                and s.customers > 0
            )
            customers = market.addressable * pb.new_product_share / (1 + rivals)
            revenue = customers * m.reference_price_cents
            if best is None or revenue > best[0]:
                best = (revenue, m.segment, market.addressable, rivals)
        if best is None:
            continue
        revenue, segment, addressable, rivals = best
        lead = max(
            (
                state.research_lead(company, d)
                for d in levels.domain_keys(data)
                if cat.key in levels.feeds(data, d)
            ),
            default=0.0,
        )
        fit = category_fit(state, company, cat, data) * (1 + 0.01 * lead)  # tunable-exempt: 27.1
        growth = cat.growth_in(2010 + year)  # tunable-exempt: turn 0 is January 2010
        central = revenue * fit * (1 + growth) ** 2
        monthly = team * _salary_month(BUILDER_ROLE, b, data)
        label = data.segment(segment).label
        out.append(
            Candidate(
                kind="new_product",
                params=(("category", cat.key), ("segment", segment), ("team", team)),
                title=f"a new {cat.label} product for {label}",
                why=(
                    f"{label} has {addressable:,.0f} potential customers at "
                    f"{format_money(cat.market(segment).reference_price_cents)} a month, "
                    f"growing {growth:.0%} a year, with {rivals} products selling there; "
                    f"our team fits it {fit:.0%}"
                ),
                score=central * b.pitch.record_months,
                central=central,
                unit="cents_month",
                monthly_cents=monthly,
                hires=team,
                risk="revenue starts only once quality reaches launch level",
            )
        )
    return out


def _sunsets(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    protected = set(_guard(state, company, "cpo", "protected_products", b) or ())  # type: ignore[call-overload]
    out = []
    for p in state.company_products(company):
        if p.status != "live" or p.id in protected or not p.rotting:
            continue
        if p.launched_turn is None or state.turn - p.launched_turn < b.pitch.sunset_months:
            continue
        saving = p.marketing_budget_cents + round(
            sum(
                s.customers * data.category(p.category).market(s.segment).hosting_cents
                for s in state.segments_of(p.id)
            )
        )
        out.append(
            Candidate(
                kind="sunset",
                params=(("product_id", p.id),),
                title=f"sunsetting {p.name}",
                why=(
                    f"{p.name} has nobody working on it, earns "
                    f"{format_money(product_mrr(state, p.id))} a month and costs "
                    f"{format_money(saving)} a month to run"
                ),
                score=saving * b.pitch.record_months,
                central=saving,
                unit="cents_month",
                risk="its customers leave as it winds down",
            )
        )
    return out


def _regions(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    home = compute.home_region_of(state, b, data)
    offices = {data.city(o.city).region for o in state.company_offices(company)}
    out = []
    for p in state.company_products(company):
        if p.status not in SELLING or compute.is_capacity_product(p, data):
            continue
        cat = data.category(p.category)
        launched = {r.region for r in state.regions_of(p.id)}
        home_share = [
            (s.segment, s.customers / m.addressable, s.price_cents or 0)
            for s in state.segments_of(p.id)
            if (m := state.market(p.category, s.segment)) is not None and m.addressable > 0
        ]
        if not home_share:
            continue
        for region in data.region_keys:
            if region == home or region in launched:
                continue
            fit = 1.0 if region in offices else pb.region_fit_without_office
            central = 0.0
            for segment, share, price in home_share:
                rm = state.regional_market(p.category, segment, region)
                if rm is None or price <= 0:
                    continue
                local = gf.regional_price_cents(price, region, home, data)
                central += rm.addressable * share * fit * local
            if central <= 0:
                continue
            cost = gf.localization_cents(cat.scope, b)
            label = data.region(region).label
            out.append(
                Candidate(
                    kind="region",
                    params=(("product_id", p.id), ("region", region)),
                    title=f"launching {p.name} in {label}",
                    why=(
                        f"{p.name} holds {sum(s for _, s, _ in home_share) / len(home_share):.1%} "
                        f"of its home segments; {label} at that share is about "
                        f"{format_money(round(central))} a month"
                        + ("" if region in offices else ", with no office there")
                    ),
                    score=central * b.pitch.record_months,
                    central=central,
                    unit="cents_month",
                    capex_cents=cost,
                    risk=f"it sells there only after {b.markets.localize_months} months of "
                    "localization",
                )
            )
    return out


def _research(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb, rnd = b.pitch, b.rnd
    active = {p.domain for p in state.active_projects(company)}
    out = []
    for d in levels.domain_keys(data):
        if d in active or d not in pb.research_roles:
            continue
        cats = set(levels.feeds(data, d))
        live = [p for p in state.company_products(company) if p.status in SELLING]
        revenue = sum(product_mrr(state, p.id) for p in live if p.category in cats)
        room = sum(
            (SCORE_MAX - p.quality) / SCORE_MAX * product_mrr(state, p.id)
            for p in live
            if p.category in cats
        )
        if revenue <= 0:
            continue
        n = pb.team_builders
        output = coord_factor(n, b.products) * n  # n researchers at skill 10 (r / 10 = 1)
        lead = state.research_lead(company, d)
        start = lead
        for _ in range(pb.record_months):
            lead = (lead + rnd.rate * output / (1 + lead / rnd.half)) * (1 - rnd.decay)
        gain = lead - start
        role = pb.research_roles[d]
        domain = levels.domain_def(data, d)
        monthly = n * (_salary_month(role, b, data) + domain.budget_cents)
        out.append(
            Candidate(
                kind="research",
                params=(("domain", d), ("team", n), ("role", role)),
                title=f"a {domain.label} research team",
                why=(
                    f"{format_money(revenue)} a month of our revenue is in the markets "
                    f"{domain.label} feeds, with room to grow quality; our lead is "
                    f"{start:.0f} points"
                ),
                score=room * b.pitch.record_months * min(1.0, gain * rnd.cap_per_point),
                central=gain,
                unit="points",
                monthly_cents=monthly,
                hires=n,
                risk="a research lead pays only through products' quality and features",
            )
        )
    return out


def _data_centres(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    if any(compute.is_compute(f, b) for f in state.company_facilities(company)):
        return []
    home = compute.home_region_of(state, b, data)
    need = sum(
        n.units
        for n in compute.needs(state, company, b, data)
        if n.good == b.compute.plain_good and compute.serves(n.region, home, data)
    )
    sizes = [s for s in sorted(b.facility.sizes) if need >= pb.dc_use * s]
    if not sizes:
        return []
    size = sizes[-1]
    kind_key = next(k for k, v in b.facility.kinds.items() if v.output_good == b.compute.plain_good)
    kind = b.facility.kinds[kind_key]
    q = lifecycle.quote(state, company, kind_key, home, size, b, data)
    monthly = ff.monthly_cost_cents(size, q.capex_cents, kind.life_months, kind.opex_per_unit_cents)
    spot = compute.spot_unit_cents(state, b.compute.plain_good, b, data)
    used = min(need, size)
    saving = spot * used - monthly
    if saving <= 0:
        return []
    return [
        Candidate(
            kind="data_centre",
            params=(("facility_kind", kind_key), ("region", home), ("units", size)),
            title=f"a {size:,}-CU data centre in {data.region(home).label}",
            why=(
                f"our products use {need:,.0f} CU a month at {format_money(round(spot))} a CU "
                f"spot; own capacity costs {format_money(round(monthly / size))} a CU at full use"
            ),
            score=saving * b.pitch.record_months,
            central=saving,
            unit="cents_month",
            capex_cents=q.capex_cents,
            monthly_cents=size * kind.opex_per_unit_cents,
            risk=f"it takes {q.build_months} months to build, and costs the same if demand falls",
        )
    ]


def _offices(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    unfilled = 0
    roles: set[str] = set()
    for p in state.plans:
        if p.company_id == company and p.status == "active":
            pending = sum(1 for o in state.pending_offers(company) if o.plan_id == p.id)
            unfilled += max(0, p.target - p.hired - pending)
            roles.add(p.role)
    if unfilled <= 0:
        return []
    have = {o.city for o in state.company_offices(company)}
    out = []
    for city in data.cities:
        if city.key in have:
            continue
        depth = city.talent_weight
        people = min(unfilled, pb.office_seats)
        rent = round(
            b.payroll.office_cost_per_head_cents * b.office.lease_discount * city.rent_index
        )
        out.append(
            Candidate(
                kind="office",
                params=(("city", city.key), ("seats", pb.office_seats)),
                title=f"a {pb.office_seats}-seat office in {city.label}",
                why=(
                    f"{unfilled} roles in our hiring plans are still open; {city.label}'s "
                    f"talent pool weighs {depth:.1f}"
                ),
                score=people * depth * _salary_month(BUILDER_ROLE, b, data) * b.pitch.record_months,
                central=people,
                unit="people",
                monthly_cents=rent * pb.office_seats,
                risk="the lease runs whether or not we fill the seats",
            )
        )
    return out


def _plants(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    plant = b.hardware.plant_kind
    if any(f.kind == plant for f in state.company_facilities(company)):
        return []
    contracts = [
        c
        for c in state.production_contracts
        if c.company_id == company
        and c.kind == MANUFACTURING_KIND
        and c.end_turn - state.turn + 1 >= pb.plant_months
    ]
    units = sum(c.units for c in contracts)
    sizes = [s for s in sorted(b.facility.sizes) if units >= pb.plant_share * s]
    if not contracts or not sizes:
        return []
    size = sizes[-1]
    fee = sum(c.units * c.price_cents for c in contracts) / units
    home = compute.home_region_of(state, b, data)
    kind = b.facility.kinds[plant]
    q = lifecycle.quote(state, company, plant, home, size, b, data)
    fixed = q.capex_cents / kind.life_months + kind.fixed_opex_cents
    per_unit = fixed / min(units, size)
    saving = (fee - per_unit) * min(units, size)
    if saving <= 0:
        return []
    return [
        Candidate(
            kind="plant",
            params=(("facility_kind", plant), ("region", home), ("units", size)),
            title=f"a {size:,}-unit assembly plant in {data.region(home).label}",
            why=(
                f"our contract manufacturers assemble {units:,} units a month at "
                f"{format_money(round(fee))} a unit; our own plant would cost about "
                f"{format_money(round(per_unit))} a unit"
            ),
            score=saving * b.pitch.record_months,
            central=saving,
            unit="cents_month",
            capex_cents=q.capex_cents,
            monthly_cents=kind.fixed_opex_cents,
            risk=f"it takes {q.build_months} months to build and needs manufacturing engineers",
        )
    ]


def _campaigns(state: GameState, company: int, b: Balance, data: GameData) -> list[Candidate]:
    pb = b.pitch
    out = []
    for p in state.company_products(company):
        if p.status not in SELLING or compute.is_capacity_product(p, data):
            continue
        gap = SCORE_MAX - p.brand
        customers = _customers(state, p.id)
        if gap < pb.campaign_brand_gap or customers <= 0:
            continue
        push = max(pb.campaign_min_cents, round(p.marketing_budget_cents * pb.campaign_share))
        lift = customers * pb.campaign_lift * gap / SCORE_MAX
        out.append(
            Candidate(
                kind="campaign",
                params=(("product_id", p.id), ("cents", push * pb.campaign_months)),
                title=f"a {pb.campaign_months}-month campaign for {p.name}",
                why=(
                    f"{p.name}'s brand is {p.brand:.0f} of 100 with {customers:,.0f} "
                    f"customers; a campaign of {format_money(push)} a month lifts awareness "
                    f"{pb.campaign_awareness_pct:g}%"
                ),
                score=lift * _price_per_customer(state, p.id) * b.pitch.record_months,
                central=lift,
                unit="customers",
                capex_cents=push * pb.campaign_months,
                risk="the lift fades when the campaign ends",
            )
        )
    return out


def _buyback(
    state: GameState, company: int, cash: Cents, b: Balance, data: GameData
) -> list[Candidate]:
    from tst.sim.finance.statements import projected_net_burn
    from tst.sim.state import listing_of

    if listing_of(state, company) is None:
        return []
    burn = max(projected_net_burn(state, company, b, data), 0)
    months = float(_guard(state, company, "cfo", "repay_above_months", b) or 0)  # type: ignore[arg-type]
    spare = cash - months * burn
    if spare <= 0:
        return []
    amount = round(spare * b.pitch.buyback_share)
    return [
        Candidate(
            kind="buyback",
            params=(("amount_cents", amount),),
            title=f"a {format_money(amount)} share buyback",
            why=(
                f"cash is {format_money(cash)}, more than {months:g} months of burn "
                f"({format_money(burn)} a month)"
            ),
            score=RETURN_SCORE,
            central=amount,
            unit="cents",
            capex_cents=amount,
            risk="cash spent on shares is not there for a downturn",
        )
    ]


def candidates(
    state: GameState,
    company: int,
    kinds: tuple[PitchKind, ...],
    cash: Cents,
    b: Balance,
    data: GameData,
) -> list[Candidate]:
    """Every candidate of these kinds, best first; ties by kind order then params (27.1)."""
    makers: dict[PitchKind, Callable[[], list[Candidate]]] = {
        "new_product": lambda: _new_products(state, company, b, data),
        "sunset": lambda: _sunsets(state, company, b, data),
        "region": lambda: _regions(state, company, b, data),
        "research": lambda: _research(state, company, b, data),
        "data_centre": lambda: _data_centres(state, company, b, data),
        "office": lambda: _offices(state, company, b, data),
        "plant": lambda: _plants(state, company, b, data),
        "campaign": lambda: _campaigns(state, company, b, data),
        "buyback": lambda: _buyback(state, company, cash, b, data),
    }
    out: list[tuple[float, int, str, Candidate]] = []
    for i, kind in enumerate(kinds):
        maker = makers.get(kind)
        for c in maker() if maker else []:
            out.append((-c.score, i, repr(c.params), c))
    out.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[-1] for t in out]


# --- Making a pitch -----------------------------------------------------------------------------


def make_pitch(
    state: GameState, company: int, seat: str, holder: int, c: Candidate, b: Balance
) -> Pitch:
    """The pitch's numbers from the candidate and the displayed seat score (27.1)."""
    spread = case_spread(shown_seat_score(state, company, holder, seat, b), b.pitch)
    low = math.floor(c.central * (1 - spread))
    high = math.ceil(c.central * (1 + spread))
    if c.unit == "cents":  # an amount, not an estimate: no spread (a buyback)
        low = high = round(c.central)
    pid = state.next_ids.pitch
    return Pitch(
        id=pid,
        company_id=company,
        seat=seat,
        person_id=holder,
        turn=state.turn,
        kind=c.kind,
        params=tuple(sorted(c.params)),
        title=c.title,
        why=c.why,
        cost_cents=c.cost_cents(b.pitch.cost_months),
        capex_cents=c.capex_cents,
        monthly_cents=c.monthly_cents,
        hires=c.hires,
        unit=c.unit,
        low=max(0, low),
        high=max(0, high),
        risk=c.risk,
    )


def case_text(unit: CaseUnit, value: int) -> str:
    match unit:
        case "cents_month":
            return f"{format_money(value)} a month"
        case "cents":
            return format_money(value)
        case "points":
            return f"{value} lead points"
        case "people":
            return f"{value} people"
        case _:
            return f"{value:,} customers"


def pitch_text(state: GameState, p: Pitch) -> str:
    """What the inbox item says, in the executive's voice (27.1)."""
    person = state.person(p.person_id)
    cost = (f"{format_money(p.capex_cents)} up front" if p.capex_cents else "") + (
        (", " if p.capex_cents else "") + f"{format_money(p.monthly_cents)} a month"
        if p.monthly_cents
        else ""
    )
    hires = f", {p.hires} hire{'s' if p.hires != 1 else ''}" if p.hires else ""
    return (
        f"{person.first_name} pitches {p.title}: {p.why}. Cost: {cost or 'none'}{hires}. "
        f"In 24 months: {case_text(p.unit, p.low)} to {case_text(p.unit, p.high)}. "
        f"Risk: {p.risk}."
    )


# --- Approving ----------------------------------------------------------------------------------


type Draws = Callable[[int], Callable[[], np.random.Generator]]


@dataclass(slots=True)
class Applied:
    state: GameState
    balances: dict[tuple[int, str], Cents]
    entries: list[LedgerEntry]
    logs: list[LogItem]
    actions: list[Action]
    target_id: int | None = None


def _do(
    out: Applied, action: Action, rng: RngFactory, b: Balance, data: GameData, draws: Draws
) -> None:
    result = apply_action(
        out.state,
        action,
        rng,
        b,
        data,
        out.balances,
        seq=0,
        draws=draws(len(out.actions)),
    )
    from tst.sim.ledger import apply_entries

    out.state = result.new_state
    out.balances = dict(apply_entries(out.balances, result.ledger_entries))
    out.entries += result.ledger_entries
    out.logs += result.log_items
    out.actions.append(action)


def execute(
    state: GameState,
    pitch: Pitch,
    founder: int,
    rng: RngFactory,
    b: Balance,
    data: GameData,
    balances: LedgerBalances,
    draws: Draws,
) -> Applied:
    """Run an approved pitch's actions in order (27.1); raises the first refusal's SimError and
    then nothing changes. The executive acts, or the founder for a Chair's decision."""
    actor = founder if pitch.kind in CHAIR_KINDS else pitch.person_id
    out = Applied(state, dict(balances), [], [], [])
    p = dict(pitch.params)
    ps = out.state.person_state(actor)
    if actor != founder and ps.energy is None:  # an executive's own energy (24.1)
        out.state = with_person_state(
            out.state, replace(ps, energy=b.exec_authority.energy_per_month)
        )
    company = pitch.company_id
    match pitch.kind:
        case "new_product":
            cat = data.category(str(p["category"]))
            segment = str(p["segment"])
            name = new_product_name(out.state, company, cat)
            unit_id = out.state.next_ids.unit
            _do(out, CreateUnit(actor, "team", f"{name} team"), rng, b, data, draws)
            product_id = out.state.next_ids.product
            _do(out, CreateProduct(actor, name, cat.key, (segment,)), rng, b, data, draws)
            price = cat.market(segment).reference_price_cents
            _do(out, SetPrice(actor, product_id, segment, price), rng, b, data, draws)
            _do(out, AssignUnit(actor, product_id, unit_id), rng, b, data, draws)
            _plan(out, actor, BUILDER_ROLE, int(p["team"]), unit_id, b, rng, data, draws)
            out.target_id = product_id
        case "sunset":
            _do(out, SunsetProduct(actor, int(p["product_id"])), rng, b, data, draws)
            out.target_id = int(p["product_id"])
        case "region":
            _do(
                out,
                LaunchInRegion(actor, int(p["product_id"]), str(p["region"])),
                rng,
                b,
                data,
                draws,
            )
            out.target_id = int(p["product_id"])
        case "research":
            domain = levels.domain_def(data, str(p["domain"]))
            unit_id = out.state.next_ids.unit
            _do(out, CreateUnit(actor, "team", f"{domain.label} research"), rng, b, data, draws)
            _plan(out, actor, str(p["role"]), int(p["team"]), unit_id, b, rng, data, draws)
            _do(out, StartProject(actor, unit_id, domain.key), rng, b, data, draws)
            out.target_id = unit_id
        case "data_centre" | "plant":
            fid = out.state.next_ids.facility
            _do(
                out,
                BuildFacility(actor, str(p["facility_kind"]), str(p["region"]), int(p["units"])),
                rng,
                b,
                data,
                draws,
            )
            out.target_id = fid
        case "office":
            oid = out.state.next_ids.office
            _do(out, LeaseOffice(actor, str(p["city"]), int(p["seats"])), rng, b, data, draws)
            out.target_id = oid
        case "campaign":
            _campaign(out, pitch, b)
            out.target_id = int(p["product_id"])
        case "buyback":
            from tst.sim.actions import Buyback

            _do(out, Buyback(actor, int(p["amount_cents"])), rng, b, data, draws)
    return out


def _plan(
    out: Applied,
    actor: int,
    role: str,
    wanted: int,
    unit_id: int,
    b: Balance,
    rng: RngFactory,
    data: GameData,
    draws: Draws,
) -> None:
    ratio = min(
        int(b.exec_authority.defaults["cto"]["max_salary_ratio_bp"]), b.delegates.max_ratio_bp
    )
    plan = CreatePlan(actor, actor, role, wanted, PLAN_CHANNEL, ratio, 0, unit_id)  # type: ignore[arg-type]
    _do(out, plan, rng, b, data, draws)


def _campaign(out: Applied, pitch: Pitch, b: Balance) -> None:
    """A campaign: its spend now (marketing), and awareness and brand-target modifiers on the
    product for pitch.campaign_months (23.2)."""
    pb = b.pitch
    product_id = int(pitch.param("product_id"))
    cents = int(pitch.param("cents"))
    product = out.state.product(product_id)
    if product is None or product.status not in SELLING:
        raise _Refused("the product is no longer selling")
    if account_balance(out.balances, pitch.company_id, CASH) < cents:
        from tst.sim.errors import InsufficientCashError

        raise InsufficientCashError(f"the campaign costs {format_money(cents)}")
    entry = LedgerEntry.transfer(
        turn=out.state.turn,
        company_id=pitch.company_id,
        memo=f"Campaign: {product.name}",
        debit=MARKETING,
        credit=CASH,
        amount=cents,
    )
    from tst.sim.ledger import apply_entries

    out.entries.append(entry)
    out.balances = dict(apply_entries(out.balances, (entry,)))
    state = out.state
    for stat, pct in (
        ("awareness", pb.campaign_awareness_pct),
        ("brand_target", pb.campaign_brand_pct),
    ):
        mid, ids = state.next_ids.take("modifier")
        state = with_modifier(
            replace(state, next_ids=ids),
            Modifier(
                mid,
                pitch.company_id,
                None,
                f"product:{product_id}",
                stat,
                pct,
                state.turn,
                state.turn + pb.campaign_months,
            ),
        )
    out.state = state


class _Refused(SimError):
    """A pitch that can no longer be carried out."""

    code = "pitch_refused"


def new_product_name(state: GameState, company: int, cat: CategoryDef) -> str:
    """'<Company> <Category>', numbered if the name is taken."""
    base = f"{state.company(company).name} {cat.label.split(' ')[0]}"
    names = {p.name for p in state.company_products(company)}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def measure(state: GameState, pitch: Pitch, b: Balance, data: GameData) -> int | None:
    """The tracked measure of an approved pitch now, in its unit; None while what it created
    is not yet operating (27.1)."""
    p = dict(pitch.params)
    target = pitch.target_id
    match pitch.kind:
        case "new_product":
            product = state.product(target) if target is not None else None
            if product is None or product.status not in SELLING:
                return None
            return product_mrr(state, product.id)
        case "sunset":
            product = state.product(int(p["product_id"]))
            done = product is None or product.status in ("sunsetting", "retired")
            return pitch.baseline if done else 0
        case "region":
            pid, region = int(p["product_id"]), str(p["region"])
            if not any(r.region == region for r in state.regions_of(pid)):
                return None
            return product_mrr(state, pid, region)
        case "research":
            return max(
                0, round(state.research_lead(pitch.company_id, str(p["domain"])) - pitch.baseline)
            )
        case "data_centre" | "plant":
            f = state.facility(target) if target is not None else None
            if f is None or f.status != "live":
                return None
            return pitch.high if pitch.kind == "plant" else _dc_saving(state, f, b, data)
        case "office":
            office = state.office(target) if target is not None else None
            if office is None or office.status != "open":
                return None
            from tst.sim.geo.offices import office_members

            return len(office_members(state, pitch.company_id).get(office.id, ()))
        case "campaign":
            return max(0, round(_customers(state, int(p["product_id"])) - pitch.baseline))
        case "buyback":
            return pitch.low
    return None


def _dc_saving(state: GameState, f: object, b: Balance, data: GameData) -> int:
    from tst.sim.facilities.models import Facility

    assert isinstance(f, Facility)
    alloc = compute.allocate(state, f.company_id, b, data)
    used = alloc.own.get(f.id, 0.0)
    kind = b.facility.kinds[f.kind]
    spot = compute.spot_unit_cents(state, b.compute.plain_good, b, data)
    monthly = ff.monthly_cost_cents(
        f.capacity, f.capex_cents, kind.life_months, kind.opex_per_unit_cents
    )
    return round(spot * used - monthly)


def baseline_of(state: GameState, pitch: Pitch) -> int:
    """The tracked measure's starting point, read when the pitch is approved."""
    p = dict(pitch.params)
    match pitch.kind:
        case "research":
            return round(state.research_lead(pitch.company_id, str(p["domain"])))
        case "campaign":
            return round(_customers(state, int(p["product_id"])))
        case "sunset":
            return pitch.low  # the saving it promised; met once the product is sunset
    return 0


def follow_through(state: GameState, b: Balance, data: GameData) -> GameState:
    """Phase 2: approved pitches pitch.record_months after approval are scored hit (at or
    above their low case), miss, or too early (27.1)."""
    for pitch in state.pitches:
        if not pitch.approved or pitch.outcome is not None or pitch.resolved_turn is None:
            continue
        if state.turn < pitch.resolved_turn + b.pitch.record_months:
            continue
        value = measure(state, pitch, b, data)
        outcome = "too_early" if value is None else ("hit" if value >= pitch.low else "miss")
        state = with_pitch(
            state,
            replace(pitch, outcome=outcome, outcome_turn=state.turn, measured=value),  # type: ignore[arg-type]
        )
    return state


def record(state: GameState, person_id: int) -> tuple[int, int, int]:
    """(hits, misses, too early) of an executive's scored pitches (27.1)."""
    scored = [p for p in state.pitches if p.person_id == person_id and p.outcome is not None]
    return (
        sum(1 for p in scored if p.outcome == "hit"),
        sum(1 for p in scored if p.outcome == "miss"),
        sum(1 for p in scored if p.outcome == "too_early"),
    )


# --- Answering ------------------------------------------------------------------------------------


def close(state: GameState, pitch: Pitch, status: str, b: Balance) -> GameState:
    """Close a pitch; a decline costs its executive morale once, more at high ego (27.1)."""
    state = with_pitch(state, replace(pitch, status=status, resolved_turn=state.turn))  # type: ignore[arg-type]
    if status == "declined":
        person = state.person(pitch.person_id)
        ps = state.person_state(pitch.person_id)
        drop = decline_morale(person.personality["ego"], b.pitch)
        if ps.morale is not None:
            state = with_person_state(state, replace(ps, morale=clamp_morale(ps.morale - drop)))
    return state


def approve(
    state: GameState,
    pitch: Pitch,
    founder: int,
    rng: RngFactory,
    b: Balance,
    data: GameData,
    balances: LedgerBalances,
    draws: Draws,
    *,
    status: str = "approved",
) -> Applied:
    """Carry out the pitch and mark it approved, with its tracking baseline (27.1)."""
    out = execute(state, pitch, founder, rng, b, data, balances, draws)
    done = replace(
        pitch,
        status=status,  # type: ignore[arg-type]
        resolved_turn=out.state.turn,
        target_id=out.target_id,
        baseline=baseline_of(state, pitch),
    )
    out.state = with_pitch(out.state, done)
    return out


# --- Phase 2 ------------------------------------------------------------------------------------


def is_draw_month(turn: int) -> bool:
    """A quarter's first month (January, April, July, October)."""
    return turn % MONTHS_PER_QUARTER == 0


def pitch_month(
    run: object,
    company: int,
    seat: str,
    holder: int,
    kinds: tuple[PitchKind, ...],
    true_score: float,
    at_controls: bool,
) -> None:
    """One executive's quarterly pitch (27.1): lapse a still-pending pitch, draw, choose,
    then pend or (on Holiday, under the limit) carry it out."""
    from tst.sim.org.delegates import DelegateRun

    assert isinstance(run, DelegateRun)
    state, b, data = run.state, run.balance, run.data
    if not is_draw_month(state.turn) or not kinds:
        return
    for p in state.pending_pitches(company):
        if p.person_id == holder:
            run.state = state = with_pitch(
                state, replace(p, status="lapsed", resolved_turn=state.turn)
            )
    gen = run.rng.stream(state.turn, "pitch", holder)
    u_pitch, u_quality = (float(gen.random()) for _ in range(DRAWS))
    ambition = state.person(holder).personality["ambition"]  # true, never shown (27.6)
    if u_pitch >= pitch_chance(ambition, b.pitch):
        return
    cash = account_balance(run.balances, company, CASH)
    ranked = candidates(state, company, kinds, cash, b, data)
    pick = pitch_pick(
        len(ranked), u_quality, decision_quality(true_score, b.exec_authority.quality)
    )
    if pick is None:
        return
    pitch = make_pitch(state, company, seat, holder, ranked[pick], b)
    run.state = state = replace(state, next_ids=state.next_ids.take("pitch")[1])
    run.state = state = with_pitch(state, pitch)
    person = state.person(holder)
    name = f"{person.first_name} {person.last_name}"
    policy = state.pitch_policy(company)
    limit = auto_approve_limit(cash, policy.auto_approve_cents, b.pitch)
    if auto_approves(pitch.cost_cents, limit, on_holiday=not at_controls):
        founder = state.founder_of(company)
        turn = state.turn

        def draws(n: int) -> Callable[[], np.random.Generator]:
            return lambda: delegate_draws(run.rng, turn, holder, PITCH_ACTION_KEY + n)

        try:
            out = approve(
                state,
                pitch,
                founder.id if founder else holder,
                run.rng,
                b,
                data,
                run.balances,
                draws,
                status="auto_approved",
            )
        except SimError as exc:
            run.logs.append(_item(state, pitch, name, f" It could not go ahead: {exc}."))
            return
        run.state, run.balances = out.state, out.balances
        run.entries += out.entries
        run.logs += out.logs
        run.taken += [(company, a) for a in out.actions]
        run.logs.append(
            inbox_item(
                state.turn,
                company,
                "pitch_went_ahead",
                link_kind="person",
                link_id=holder,
                name=name,
                what=pitch.title,
                detail=pitch_text(state, pitch),
                cost_cents=pitch.cost_cents,
            )
        )
        return
    run.logs.append(_item(state, pitch, name, ""))


PITCH_ACTION_KEY: Final = 3_000_000  # tunable-exempt: delegate-stream key offset for pitches
ANSWER_KEY: Final = 4_000_000  # tunable-exempt: the same for a pitch the founder approves
ANSWER_STEPS: Final = 100  # tunable-exempt: actions one approval may take, per action seq


def _item(state: GameState, pitch: Pitch, name: str, extra: str) -> LogItem:
    return inbox_item(
        state.turn,
        pitch.company_id,
        "exec_pitch",
        link_kind="person",
        link_id=pitch.person_id,
        name=name,
        what=pitch.title,
        detail=pitch_text(state, pitch) + extra,
    )

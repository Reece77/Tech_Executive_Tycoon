"""Talent with egos (docs/formulas.md 65.6).

**Creative leads on offer.** Each January `talent.pool_size` leads come on offer for
`pool_months`. The n-th of a year is regenerated from stream media (4, year, n) whenever it is
read: a person of role `creative_lead` (tst.sim.people.generator, as a search's candidate), then
creative and vision ~ N(`attribute_mean`, `attribute_sd`) and the hidden ego and loyalty = the
person's shown ego and loyalty traits + N(0, `trait_sd`), all clamped to 1-20. Nothing is stored
but the offer's (year, n) until the lead is signed, so no other person's draws change.

**Overall deals.** Signing employs the lead for a term at a fee a year: `base_fee_cents` x scale x
((creative + vision) / 20) ** `fee_exponent` x (1 + `reputation_fee` x reputation); `upfront_share`
of the deal's total is paid at signing (6000) and the rest is the lead's salary (payroll). During
the deal the studio has first look: only its signed leads lead its titles. At the term's end the
employment ends.

**Egos.** Overruling a lead's choices on a title, cutting its budget or moving its date lowers the
lead's morale by `overrule_morale` / `cut_morale` / `move_morale` x ego / 20. Below `walk_morale`,
each such event may make the lead walk: chance `walk_chance` x (21 - loyalty) / 20 x (walk_morale -
morale) / walk_morale (stream media (1, person id, title id, n)). A lead who walks leaves for the
media rival with the most video subscribers, which gains their next title (a catalogue bonus); the
title loses its lead. Morale lowers quality through the lead's factor (tst.sim.media.titles).

**Reputation.** At release the lead's reputation += `hit_reputation` x (audience / expected - 1),
clamped to `reputation_range`: a hit raises their fee.

**Strikes.** The 2023 strikes are history (media.yaml); from `media.start` each region's January
draws (stream media (2, region index, year)) may seed a strike of `strike_months` months, pausing
production there.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.media import draws
from tst.sim.media.data import MONTHS, file, region_index
from tst.sim.media.models import CreativeLead, LeadOffer, RivalBonus, Title, WorldDraw
from tst.sim.money import times
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment, Person
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.scale import clamp_attr
from tst.sim.state import GameState, with_employment, with_person, with_person_state, with_reveal

SALARIES: Final = "6000_salaries"
LEVELS: Final = ("senior", "staff", "principal")  # tunable-exempt: a lead's level, drawn evenly
STRIKE = "strike"  # tunable-exempt: WorldDraw kinds
STRIKE_MONTHS = "strike_months"
LAW = "law"
FINE = "fine"
EGO_SCALE: Final = 20.0  # tunable-exempt: the attribute scale's top
LOYALTY_TOP: Final = 21.0  # tunable-exempt: (21 - loyalty) / 20, as resignations' (10)
JANUARY: Final = 1


@dataclass(frozen=True, slots=True)
class Candidate:
    """A lead on offer as the engine reads it (hidden ego and loyalty included: never shown)."""

    person: Person
    creative: float
    vision: float
    ego: float
    loyalty: float


def candidate(
    offer: LeadOffer, rng: RngFactory, balance: Balance, data: GameData, person_id: int = 0
) -> Candidate:
    """The offer's lead (module docstring), the same every time it is read."""
    tb = balance.media.talent
    g = draws.gen(rng, offer.turn, draws.LEAD, offer.year, offer.n)
    level = LEVELS[int(g.integers(0, len(LEVELS)))]
    region = data.region_keys[int(g.integers(0, len(data.region_keys)))]
    role = data.role(balance.media.lead_role)
    person = generate_person(g, data, balance, offer.turn, role, level, region, person_id=person_id)
    creative = clamp_attr(float(g.normal(tb.attribute_mean, tb.attribute_sd)))
    vision = clamp_attr(float(g.normal(tb.attribute_mean, tb.attribute_sd)))
    ego = clamp_attr(person.personality["ego"] + float(g.normal(0.0, tb.trait_sd)))
    loyalty = clamp_attr(person.personality["loyalty"] + float(g.normal(0.0, tb.trait_sd)))
    return Candidate(person, creative, vision, ego, loyalty)


def fee_cents(creative: float, vision: float, reputation: float, balance: Balance) -> int:
    """An overall deal's fee a year (module docstring)."""
    tb = balance.media.talent
    mult = float(dmath.pow((creative + vision) / EGO_SCALE, tb.fee_exponent))
    rep = 1.0 + tb.reputation_fee * reputation  # money-exact: ratio
    return times(tb.base_fee_cents, balance.media.scale, mult, rep)


def pool_month(state: GameState, balance: Balance) -> GameState:
    """Each January: this year's leads come on offer; offers past `pool_months` expire."""
    tb = balance.media.talent
    year, month = turn_to_ym(state.turn)
    offers = [o for o in state.media.offers if o.status != "expired"]
    kept = []
    for o in offers:
        if o.status == "open" and state.turn - o.turn >= tb.pool_months:
            continue  # expired: dropped
        kept.append(o)
    if month == JANUARY and not any(o.year == year for o in kept):
        kept += [LeadOffer(year=year, n=n, turn=state.turn) for n in range(tb.pool_size)]
    if tuple(kept) == state.media.offers:
        return state
    return replace(state, media=replace(state.media, offers=tuple(kept)))


def sign(
    state: GameState,
    offer: LeadOffer,
    company_id: int,
    years: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], CreativeLead]:
    """Sign an offer's lead to an overall deal (module docstring)."""
    person_id, ids = state.next_ids.take("person")
    emp_id, ids = ids.take("employment")
    state = replace(state, next_ids=ids)
    c = candidate(offer, rng, balance, data, person_id=person_id)
    fee = fee_cents(c.creative, c.vision, 0.0, balance)
    tb = balance.media.talent
    upfront = times(fee, years, tb.upfront_share)
    salary = fee - times(fee, tb.upfront_share)
    person = replace(c.person, salary_expectation_cents=salary)
    state = with_person(state, person)
    state = with_employment(
        state,
        Employment(
            id=emp_id,
            person_id=person_id,
            company_id=company_id,
            role=balance.media.lead_role,
            level=person.level or LEVELS[0],
            salary_cents=salary,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    state = with_person_state(
        state, PersonState(person_id=person_id, morale=balance.morale.new_hire)
    )
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=company_id,
            person=person,
            turn=state.turn,
            rng=rng,
            data=data,
            balance=balance,
        ),
    )
    lead = CreativeLead(
        person_id=person_id,
        creative=c.creative,
        vision=c.vision,
        ego=c.ego,
        loyalty=c.loyalty,
        company_id=company_id,
        deal_from=state.turn,
        deal_to=state.turn + years * MONTHS,
        fee_cents=fee,
    )
    offers = tuple(
        replace(o, status="signed", person_id=person_id) if o == offer else o
        for o in state.media.offers
    )
    media = replace(state.media, leads=(*state.media.leads, lead), offers=offers)
    state = replace(state, media=media)
    entries = []
    if upfront:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company_id,
                memo=f"Overall deal (up front): {person.first_name} {person.last_name}",
                debit=SALARIES,
                credit=CASH,
                amount=upfront,
            )
        )
    return state, entries, lead


def with_lead(state: GameState, lead: CreativeLead) -> GameState:
    leads = tuple(lead if x.person_id == lead.person_id else x for x in state.media.leads)
    return replace(state, media=replace(state.media, leads=leads))


def _walk_to(state: GameState, balance: Balance, data: GameData) -> int | None:
    """The media rival with the most video subscribers."""
    best: tuple[float, int] | None = None
    for p in state.products:
        if p.category != balance.media.streaming:
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or not company.alive:
            continue
        subs = sum(s.customers for s in state.segments_of(p.id)) + sum(
            s.customers for s in state.regional_segments_of(p.id)
        )
        if best is None or (subs, -company.id) > (best[0], -best[1]):
            best = (subs, company.id)
    return best[1] if best is not None else None


def walk(
    state: GameState, lead: CreativeLead, title: Title | None, balance: Balance, data: GameData
) -> tuple[GameState, LogItem]:
    """The lead walks (module docstring)."""
    company_id = lead.company_id
    assert company_id is not None
    to = _walk_to(state, balance, data)
    job = state.employment_of(lead.person_id)
    if job is not None and job.status != "ended":
        state = with_employment(
            state, replace(job, status="ended", end_turn=state.turn, end_reason="poached")
        )
    state = with_lead(state, replace(lead, company_id=None, walked_turn=state.turn, walked_to=to))
    if to is not None:
        from tst.sim.media.streaming import title_value_cents

        value = title_value_cents(balance.media.kind("series"), balance)
        bonus = RivalBonus(company_id=to, value_cents=value, turn=state.turn)
        state = replace(
            state, media=replace(state.media, rival_bonus=(*state.media.rival_bonus, bonus))
        )
    if title is not None:
        titles = tuple(
            replace(t, walked_turn=state.turn) if t.id == title.id else t
            for t in state.media.titles
        )
        state = replace(state, media=replace(state.media, titles=titles))
    person = state.person(lead.person_id)
    rival = state.company(to) if to is not None else None
    log = inbox_item(
        state.turn,
        company_id,
        "media_lead_walked",
        link_kind="person",
        link_id=lead.person_id,
        name=f"{person.first_name} {person.last_name}",
        title=title.name if title is not None else "their slate",
        rival=rival.name if rival is not None else "another studio",
    )
    return state, log


def react(
    state: GameState,
    title: Title,
    what: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """A lead's reaction to an overrule, a budget cut or a moved date on their title (module
    docstring). `what`: overrule, cut or move."""
    tb = balance.media.talent
    if title.lead_person_id is None:
        return state, []
    lead = state.media.lead(title.lead_person_id)
    if lead is None or lead.company_id != title.company_id:
        return state, []
    base = {"overrule": tb.overrule_morale, "cut": tb.cut_morale, "move": tb.move_morale}[what]
    ps = state.person_state(lead.person_id)
    lost = base * lead.ego / EGO_SCALE
    morale = max(0.0, (ps.morale or 0.0) - lost)
    state = with_person_state(state, replace(ps, morale=morale))
    title = replace(title, grievance=title.grievance + lost)
    titles = tuple(title if t.id == title.id else t for t in state.media.titles)
    state = replace(state, media=replace(state.media, titles=titles))
    logs: list[LogItem] = []
    person = state.person(lead.person_id)
    name = f"{person.first_name} {person.last_name}"
    logs.append(
        inbox_item(
            state.turn,
            title.company_id,
            "media_lead_unhappy",
            link_kind="person",
            link_id=lead.person_id,
            name=name,
            title=title.name,
        )
    )
    if morale < tb.walk_morale:
        g = draws.gen(rng, state.turn, draws.REACTION, lead.person_id, title.id, title.events)
        chance = (
            tb.walk_chance
            * (LOYALTY_TOP - lead.loyalty)
            / EGO_SCALE
            * (tb.walk_morale - morale)
            / tb.walk_morale
        )
        if float(g.random()) < chance:
            state, log = walk(state, lead, title, balance, data)
            logs.append(log)
    return state, logs


def after_release(state: GameState, title: Title, ratio: float, balance: Balance) -> GameState:
    """A released title's lead: reputation and titles together (module docstring)."""
    if title.lead_person_id is None:
        return state
    lead = state.media.lead(title.lead_person_id)
    if lead is None or lead.company_id != title.company_id:
        return state
    tb = balance.media.talent
    rep = lead.reputation + tb.hit_reputation * (ratio - 1.0)
    rep = min(tb.reputation_range.hi, max(tb.reputation_range.lo, rep))
    return with_lead(state, replace(lead, reputation=rep, titles=lead.titles + 1))


def deals_month(state: GameState) -> GameState:
    """Overall deals that reach their term end: the employment ends."""
    for lead in state.media.leads:
        if lead.company_id is None or lead.deal_to is None or state.turn < lead.deal_to:
            continue
        job = state.employment_of(lead.person_id)
        if job is not None and job.status != "ended":
            state = with_employment(
                state, replace(job, status="ended", end_turn=state.turn, end_reason="resigned")
            )
        state = with_lead(state, replace(lead, company_id=None))
    return state


def left_month(state: GameState) -> GameState:
    """A signed lead whose employment ended another way (resigned, poached, fired) is no longer
    the company's."""
    for lead in state.media.leads:
        if lead.company_id is None:
            continue
        job = state.employment_of(lead.person_id)
        if job is None or job.status == "ended" or job.company_id != lead.company_id:
            state = with_lead(state, replace(lead, company_id=None))
    return state


def region_year_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """Each January from `media.start`: every region's draws (stream media (2, region index,
    year)): a seeded strike (its month and length) and the divest-or-ban law's draw."""
    tb = balance.media.talent
    year, month = turn_to_ym(state.turn)
    if state.turn < balance.media.start_turn or month != JANUARY:
        return state
    if any(d.kind == LAW and d.year == year for d in state.media.draws):
        return state
    rows = list(state.media.draws)
    for region in data.region_keys:
        g = draws.gen(rng, state.turn, draws.REGION, region_index(region, data), year)
        u = [float(x) for x in g.random(5)]  # tunable-exempt: five draws
        u_strike, u_month, u_len, u_law, u_fine = u
        if u_strike < tb.strike_chance:
            start = ym_to_turn(year, 1 + int(u_month * MONTHS))
            months = round(
                tb.strike_months.lo + (tb.strike_months.hi - tb.strike_months.lo) * u_len
            )
            rows.append(WorldDraw(STRIKE, year, region, float(start)))
            rows.append(WorldDraw(STRIKE_MONTHS, year, region, float(months)))
        rows.append(WorldDraw(LAW, year, region, u_law))
        rows.append(WorldDraw(FINE, year, region, u_fine))
    return replace(state, media=replace(state.media, draws=tuple(rows)))


def seeded_strike_on(state: GameState, region: str, data: GameData) -> bool:
    m = state.media
    for d in m.draws:
        if d.kind != STRIKE or d.key != region:
            continue
        months = m.draw(STRIKE_MONTHS, d.year, region) or 0.0
        if d.value <= state.turn < d.value + months:
            return True
    return False


def strikes_now(state: GameState, data: GameData) -> list[str]:
    """Regions with a strike this month (dated or seeded): shown once in force."""
    out = []
    for region in data.region_keys:
        dated = any(s.region == region and s.active(state.turn) for s in file(data).strikes)
        if dated or seeded_strike_on(state, region, data):
            out.append(region)
    return out

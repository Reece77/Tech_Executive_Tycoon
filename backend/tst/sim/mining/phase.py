"""Mines' months (docs/formulas.md 35.2-35.5).

- **Phase 4** (`build_month`): construction capex (at the estimate's rate until the cost to
  complete is revised, then the rest), completion, restarts; resource-nationalism events
  (history, then stream `region_risk`); arbitration awards; rivals' bids (35.5).
- **Phase 5** (`operate_month`, after the markets so the group's commodity use is known):
  each producing mine's output, grade, costs, sales (the group at the transfer price, its
  contracts and offtakes, then spot), royalties, a state partner's share, depletion and the
  reclamation provision; price crashes and accidents (35.4); closed mines' reclamation.

A game with no mine and no rival bid skips both, so a company that never mines plays exactly
as before (35.6 target 6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.commodities import costs as commodity_costs
from tst.sim.commodities import power
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.exploration.geology import cell_deviations
from tst.sim.facilities import formulas as ff
from tst.sim.group import formulas as gf
from tst.sim.ledger import (
    ARO,
    CASH,
    COGS,
    COMMODITY_REVENUE,
    DEPLETION,
    GENERAL_ADMIN,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    MINERAL_PROPERTIES,
    ROYALTIES,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.mining import formulas as mf
from tst.sim.mining import prices, risk
from tst.sim.mining.actions import LINK, close_entries, closed, group_ids, mine_name
from tst.sim.mining.draws import ACCIDENT, GRADE, PROTEST, mining_draws
from tst.sim.mining.models import HISTORY_MONTHS, Mine, MineMonth
from tst.sim.money import format_money, times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_mine, with_mine_deal, with_queued

CENTS: Final = 100  # tunable-exempt: cents a dollar
MT: Final = 1e6  # tunable-exempt: t a Mt
EPS: Final = 1e-9  # tunable-exempt: float tolerance on tonnages
CELLS_TAG: Final = 1  # tunable-exempt: M18's geology key (r, b, 1), the ore body's positions
ACCIDENT_TEMPLATES: Final = ("mine_tailings_failure", "mine_fatal_accident")
CRASH_TEMPLATE: Final = "mine_price_crash"
SENSITIVITY_MID: Final = 0.5  # tunable-exempt: M18's protest_rate is quoted at this sensitivity


def active(state: GameState) -> bool:
    return bool(state.mines) or any(b.status == "open" for b in state.rival_bids)


# --- Phase 4 ---------------------------------------------------------------------------------


def build_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if not state.mines and not state.projects:
        return state, (), ()
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for mine in sorted(state.mines, key=lambda m: m.id):
        if mine.status == "building":
            state, more, notes = _construction(state, mine, balance, data)
        elif mine.status == "restarting" and mine.restart_due is not None:
            more, notes = [], []
            if state.turn >= mine.restart_due:
                state = with_mine(state, replace(mine, status="producing", restart_due=None))
                notes = [_item(state, mine, "mine_restarted", data)]
        else:
            continue
        entries += more
        logs += notes
    if state.mines:
        state, more, notes = risk.region_month(state, rng, balance, data)
        entries += more
        logs += notes
    state, notes = risk.rival_bids_month(state, rng, balance, data)
    logs += notes
    return state, tuple(entries), tuple(logs)


def _item(
    state: GameState, mine: Mine, template: str, data: GameData, **params: str | int
) -> LogItem:
    return inbox_item(
        state.turn,
        state.player.id,
        template,
        link_kind=LINK,
        link_id=mine.id,
        mine=mine_name(mine, data),
        **params,
    )


def _construction(
    state: GameState, mine: Mine, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """35.2: capex at the estimate's monthly rate; at `reveal_at` of construction the cost to
    complete is revised (the hidden overrun shown); then the rest over the months left; the
    mine produces from `ready_turn`."""
    turn = state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if turn < mine.ready_turn:
        reveal = mf.reveal_month(mine.ordered_turn, mine.ready_turn, balance.mining.reveal_at)
        if mine.revised_cents is None and turn >= reveal:
            mine = replace(mine, revised_cents=mine.hidden_total_cents)
            pct = round(100 * (mine.hidden_total_cents / mine.estimate_cents - 1))
            logs.append(
                _item(
                    state,
                    mine,
                    "mine_cost_revised",
                    data,
                    capex_cents=mine.hidden_total_cents,
                    pct=f"{pct:+d}%",
                )
            )
        if mine.revised_cents is None:  # at the estimate's rate: nothing shows the overrun
            pay = round(mine.estimate_cents / (mine.ready_turn - mine.ordered_turn))
        else:
            pay = mf.capex_payment(
                mine.revised_cents, mine.capex_paid_cents, mine.ready_turn - turn
            )
        if pay > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=mine.company_id,
                    memo=f"Capex: {mine_name(mine, data)}",
                    debit=MINERAL_PROPERTIES,
                    credit=CASH,
                    amount=pay,
                )
            )
            mine = replace(mine, capex_paid_cents=mine.capex_paid_cents + pay)
        return with_mine(state, mine), entries, logs
    mine = replace(mine, status="producing")
    if mine.revised_cents is None:
        mine = replace(mine, revised_cents=mine.hidden_total_cents)
    facility = state.facility(mine.id)
    if facility is not None:
        state = with_facility(state, replace(facility, status="live"))
    logs.append(_item(state, mine, "mine_built", data, capex_cents=mine.capex_paid_cents))
    return with_mine(state, mine), entries, logs


# --- Phase 5 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Crew:
    staff: int
    needed: int
    coverage: float
    skill: float  # true mean skill: engine only (ADR-0007)
    reliability: float


def crew(state: GameState, mine: Mine, balance: Balance) -> Crew:
    """Mining engineers in the unit staffing the mine (any company of the group may employ
    them, M19 decision): coverage and the mean of `mining.staff_skills` set reliability as a
    data centre's (22.2) and the accident rate (35.4)."""
    mb = balance.mining
    facility = state.facility(mine.id)
    needed = mf.staff_needed(mine.capacity_t, mb.staff_per_kt)
    people = []
    if facility is not None and facility.unit_id is not None:
        unit = state.unit(facility.unit_id)
        roles = set(balance.facility.kinds["mine"].staff_roles)
        if unit is not None:
            people = [
                e
                for e in state.staff(unit.company_id)
                if e.unit_id == unit.id and e.role in roles and e.status == "active"
            ]
    skills = [
        sum(state.person(e.person_id).skills[s] for s in mb.staff_skills) / len(mb.staff_skills)
        for e in people
    ]
    mean = sum(skills) / len(skills) if skills else 0.0
    cover = ff.coverage(len(people), needed)
    fb = balance.facility
    rel = ff.reliability(cover, mean, fb.reliability_floor, fb.reliability_skill) / 100
    return Crew(len(people), needed, cover, mean, rel)


def _ref(mine: Mine, data: GameData) -> tuple[float, float]:
    """(the commodity's typical cost a t of product at the median, its reference grade x
    recovery)."""
    assert data.geology is not None
    c = data.geology.commodity(mine.commodity)
    return c.opex_per_t_usd, c.grade_median * sum(c.recovery) / 2


def ore_cost(mine: Mine, balance: Balance, data: GameData, kind: str) -> float:
    opex, ref = _ref(mine, data)
    fb = balance.exploration.feasibility
    return mf.ore_cost_usd_t(
        opex, fb.kind_opex[kind], ref, balance.mining.subtypes[mine.subtype].opex_mult
    )


def kind_of(state: GameState, mine: Mine) -> str:
    project = next((p for p in state.projects if p.id == mine.project_id), None)
    return (project.kind if project else None) or (
        "brine" if mine.subtype == "brine" else "hard_rock"
    )


def fixed_usd(state: GameState, mine: Mine, balance: Balance, data: GameData) -> float:
    mb = balance.mining
    sub = mb.subtypes[mine.subtype]
    annual = mf.annual_cost_usd(
        mine.ore_capacity_mt, ore_cost(mine, balance, data, kind_of(state, mine))
    )
    return mf.fixed_month_usd(annual, sub.fixed_share, mb.accident.safety_cost[mine.safety])


def grade_now(
    state: GameState, mine: Mine, rng: RngFactory, balance: Balance, data: GameData
) -> float:
    """35.3: the deposit's true grade along its profile (M18's drill positions, in the order the
    ore body is mined) with a month's noise; the reconciled grade is public once mined."""
    mb = balance.mining
    r = data.region_keys.index(mine.region)
    cells = cell_deviations(rng, r, mine.block, balance.geology.cells)
    share = mine.ore_mined_mt / mine.hidden_ore_mt if mine.hidden_ore_mt > 0 else 1.0
    dev = cells[min(len(cells) - 1, int(share * len(cells)))]
    z = float(mining_draws(rng, state.turn, mine.id, GRADE).standard_normal())
    assert data.geology is not None
    sd = data.geology.commodity(mine.commodity).hole_sd
    return mine.hidden_grade * math.exp(mb.profile_share * sd * dev + mb.grade_noise * z)


def months_producing(mine: Mine, turn: int) -> int:
    return max(0, turn - mine.ready_turn)


def operate_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if not state.mines:
        return state, (), ()
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    queued: set[str] = set()  # at most one crash and one accident event a month (35.4)
    uses: dict[int, dict[str, float]] = {}
    for mine in sorted(state.mines, key=lambda m: m.id):
        if mine.status in ("producing", "care", "restarting"):
            state, more, notes = _operate(state, mine, rng, balance, data, uses, queued)
        elif mine.status == "seized":
            state, more, notes = risk.arbitration_month(state, mine, rng, balance, data)
        elif mine.status == "closed" and mine.aro_paid_cents < mine.aro_cents:
            state, more, notes = _reclaim(state, mine, balance, data)
        else:
            continue
        entries += more
        logs += notes
    return state, tuple(e for e in entries if any(x.amount for x in e.lines)), tuple(logs)


def _reclaim(
    state: GameState, mine: Mine, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """35.3: reclamation is paid in equal parts over `reclamation_months` after closure."""
    assert mine.closed_turn is not None
    left = mine.aro_cents - mine.aro_paid_cents
    months_left = mine.closed_turn + balance.mining.reclamation_months - state.turn
    pay = (
        left
        if months_left <= 1
        else min(left, math.ceil(mine.aro_cents / balance.mining.reclamation_months))
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=mine.company_id,
        memo=f"Reclamation: {mine_name(mine, data)}",
        debit=ARO,
        credit=CASH,
        amount=pay,
    )
    mine = replace(mine, aro_paid_cents=mine.aro_paid_cents + pay)
    logs = []
    if mine.aro_paid_cents >= mine.aro_cents:
        logs.append(_item(state, mine, "mine_reclaimed", data, reclamation_cents=mine.aro_cents))
    return with_mine(state, mine), [entry], logs


def buyer_use_t(
    state: GameState,
    buyer: int,
    good: str,
    balance: Balance,
    data: GameData,
    uses: dict[int, dict[str, float]],
) -> float:
    if buyer not in uses:
        uses[buyer] = commodity_costs.company_use(state, buyer, balance, data)
    return prices.use_t(uses[buyer].get(good, 0.0), good, data)


def _operate(
    state: GameState,
    mine: Mine,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    uses: dict[int, dict[str, float]],
    queued: set[str],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    mb = balance.mining
    sub = mb.subtypes[mine.subtype]
    turn, company = state.turn, mine.company_id
    name = mine_name(mine, data)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    spot = prices.spot_usd_t(state, mine.commodity, data, balance)
    kind = kind_of(state, mine)
    fixed = fixed_usd(state, mine, balance, data)
    team = crew(state, mine, balance)
    running = mine.status == "producing" and not (
        mine.stopped_until is not None and turn <= mine.stopped_until
    )
    if mine.status == "care":
        fixed *= mb.crash.care_fixed
    ore_mt = grade = product = 0.0
    if running:
        ramp = mf.ramp_share(sub, months_producing(mine, turn))
        ore_mt = min(mine.ore_capacity_mt / 12 * ramp * team.reliability, mine.hidden_ore_left_mt)
        grade = grade_now(state, mine, rng, balance, data)
        product = ore_mt * MT * grade * mine.hidden_recovery
    variable = mf.variable_usd(
        ore_mt * MT,
        ore_cost(mine, balance, data, kind),
        sub.fixed_share,
        mb.energy_share,
        power.index(state, mine.region, data),
    )
    sustaining = mb.sustaining_share * mine.capex_paid_cents / CENTS / 12 if running else 0.0
    cash_cost = round((fixed + variable + sustaining) * CENTS)
    if cash_cost:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Mine operations: {name}",
                debit=COGS,
                credit=CASH,
                amount=cash_cost,
            )
        )
    # --- sales (35.3): the group, then contracts and offtakes, then spot ---
    left = product
    revenue = 0
    banned = mine.ban_until is not None and turn <= mine.ban_until
    unit_cost_cents = round(cash_cost / product) if product > EPS else 0
    if left > EPS and mine.buyer_id is not None and mine.buyer_id in group_ids(state):
        buyer_region = _company_region(state, mine.buyer_id, data)
        if not banned or buyer_region == mine.region:
            q = min(left, buyer_use_t(state, mine.buyer_id, mine.commodity, balance, data, uses))
            if q > EPS:
                market = round(spot * CENTS)
                price = gf.transfer_price_cents(
                    mine.price_kind, unit_cost_cents, market, balance, mine.margin
                )
                paid, spot_value = round(q * price), round(q * market)
                buyer = state.company(mine.buyer_id).name
                entries += [
                    LedgerEntry(
                        turn,
                        mine.buyer_id,
                        f"{name}: supplied in-group",
                        (
                            LedgerLine(CASH, spot_value - paid),
                            LedgerLine(COGS, -spot_value),
                            LedgerLine(INTERCOMPANY_PURCHASES, paid),
                        ),
                    ),
                    LedgerEntry(
                        turn,
                        company,
                        f"{name}: supplied to {buyer}",
                        (LedgerLine(CASH, paid), LedgerLine(INTERCOMPANY_SALES, -paid)),
                    ),
                ]
                uses[mine.buyer_id][mine.commodity] = uses[mine.buyer_id].get(
                    mine.commodity, 0.0
                ) - (
                    q * prices.per_t(data.commodities.good(mine.commodity).volume_unit)  # type: ignore[union-attr]
                )
                left -= q
                revenue += paid
    if left > EPS and state.refineries and not banned:  # M20 (36.1): the group's refineries
        from tst.sim.refining.mines import feed_from_mine

        state, fed, fed_entries = feed_from_mine(
            state,
            company,
            mine.commodity,
            left,
            unit_cost_cents,
            mine.price_kind,
            mine.margin,
            group_ids(state),
            name,
            balance,
            data,
        )
        entries += fed_entries
        left -= fed
    for deal in sorted(state.mine_deals, key=lambda d: d.id):
        if deal.mine_id != mine.id or not deal.running(turn) or left <= EPS:
            continue
        q = min(left, deal.volume_t_year / 12)
        p = deal.price_for(spot)
        cents = round(q * p * CENTS)
        state = with_mine_deal(state, replace(deal, delivered_t=deal.delivered_t + q, last_usd_t=p))
        if cents:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"{name}: {deal.kind} with {deal.buyer}",
                    debit=CASH,
                    credit=COMMODITY_REVENUE,
                    amount=cents,
                )
            )
        revenue += cents
        left -= q
    if left > EPS:
        share = mb.nationalization.ban_price_share if banned else 1.0
        cents = round(left * spot * share * CENTS)
        if cents:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"{name}: spot sales"
                    + (" inside the region (export ban)" if banned else ""),
                    debit=CASH,
                    credit=COMMODITY_REVENUE,
                    amount=cents,
                )
            )
        revenue += cents
    # --- royalties at market value, a state partner's share (35.3, 35.4) ---
    royalty = mf.royalty_cents(round(product * spot * CENTS), data.region(mine.region).royalty_rate)
    if royalty:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Royalties: {name}",
                debit=ROYALTIES,
                credit=CASH,
                amount=royalty,
            )
        )
    margin = revenue - cash_cost - royalty
    if mine.state_share > 0 and margin > 0:
        state_cut = times(margin, mine.state_share)
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"State partner's share: {name}",
                debit=ROYALTIES,
                credit=CASH,
                amount=state_cut,
            )
        )
    # --- depletion (units of production on the estimated tonnage) and reclamation ---
    est_left = max(EPS, estimated_ore(state, mine, balance) - mine.ore_mined_mt)
    depletion = 0
    if ore_mt > 0 and mine.book_cents > 0:
        depletion = min(mine.book_cents, round(mine.book_cents * min(1.0, ore_mt / est_left)))
    if depletion:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Depletion: {name}",
                debit=DEPLETION,
                credit=MINERAL_PROPERTIES,
                amount=depletion,
            )
        )
    provision = mf.reclamation_cents(product, mb.reclamation_per_t_cents[mine.subtype])
    if provision:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Reclamation provision: {name}",
                debit=COGS,
                credit=ARO,
                amount=provision,
            )
        )
    cost_t = (cash_cost + royalty) / CENTS / product if product > EPS else 0.0
    month = MineMonth(
        turn=turn,
        output_t=product,
        grade=grade,
        price_usd_t=spot,
        cost_usd_t=cost_t,
        revenue_cents=revenue,
        margin_cents=margin,
    )
    mine = replace(
        mine,
        ore_mined_mt=mine.ore_mined_mt + ore_mt,
        product_t=mine.product_t + product,
        first_output_turn=mine.first_output_turn
        if mine.first_output_turn is not None or product <= EPS
        else turn,
        depleted_cents=mine.depleted_cents + depletion,
        aro_cents=mine.aro_cents + provision,
        history=(*mine.history, month)[-HISTORY_MONTHS:],
    )
    if mine.first_output_turn == turn:
        logs.append(_item(state, mine, "mine_first_output", data, output=f"{product:,.0f}"))
    # --- crash (35.4): price under the all-in cost for months_below months running ---
    aisc = cost_t if product > EPS else _last_cost(mine)
    below = aisc > 0 and spot < aisc
    mine = replace(
        mine,
        below_months=mine.below_months + 1 if below else 0,
        crash_answered=mine.crash_answered and below,
    )
    if (
        mine.status == "producing"
        and mine.below_months >= mb.crash.months_below
        and not mine.crash_answered
        and mine.crash_turn is None
        and CRASH_TEMPLATE not in queued
    ):
        queued.add(CRASH_TEMPLATE)
        state = _queue(state, CRASH_TEMPLATE)
        mine = replace(mine, crash_turn=turn + 1)
        logs.append(
            _item(
                state,
                mine,
                "mine_price_below_cost",
                data,
                months=mine.below_months,
                price=f"${mf.usd_per_lb(spot):,.2f}/lb"
                if mine.commodity == "copper"
                else format_money(round(spot * CENTS)) + "/t",
            )
        )
    # --- accidents and protests (35.4) ---
    if running and ore_mt > 0:
        state, mine, more, notes = _accident(state, mine, team, rng, balance, data, queued)
        entries += more
        logs += notes
    if mine.status == "producing":
        state, mine, notes = _protest(state, mine, rng, balance, data, queued)
        logs += notes
    state = with_mine(state, mine)
    # --- depleted: the mine closes, reclamation follows (35.3) ---
    if mine.hidden_ore_left_mt <= EPS and mine.status == "producing":
        entries += close_entries(state, mine, data)
        state = closed(state, mine, "depleted")
        logs.append(
            _item(
                state,
                mine,
                "mine_depleted",
                data,
                reclamation_cents=mine.aro_cents - mine.aro_paid_cents,
            )
        )
    return state, entries, logs


def _last_cost(mine: Mine) -> float:
    for m in reversed(mine.history):
        if m.output_t > EPS:
            return m.cost_usd_t
    return 0.0


def estimated_ore(state: GameState, mine: Mine, balance: Balance) -> float:
    """The revealed tonnage: the project's resource estimate (its centre); a mine without
    one (a rival's, bought) has its capacity over the feasibility life."""
    project = next((p for p in state.projects if p.id == mine.project_id), None)
    if project is None or project.est_tonnage_center is None:
        return mine.ore_capacity_mt * balance.exploration.feasibility.life_years
    return math.exp(project.est_tonnage_center)


def _company_region(state: GameState, company_id: int, data: GameData) -> str | None:
    city = state.company(company_id).hq_city
    if city is None:
        return None
    return next((c.region for c in data.cities if c.key == city), None)


def _queue(state: GameState, template: str) -> GameState:
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=state.player.id,
            template_id=template,
            due_turn=state.turn + 1,
            source_event_id=None,
        ),
    )


def _accident(
    state: GameState,
    mine: Mine,
    team: Crew,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    queued: set[str],
) -> tuple[GameState, Mine, list[LedgerEntry], list[LogItem]]:
    """35.4: an accident or spill with the month's chance; always a fine, brand and
    credibility down; a critical event (one a month) asks what to do next."""
    ab = balance.mining.accident
    sub = balance.mining.subtypes[mine.subtype]
    gen = mining_draws(rng, state.turn, mine.id, ACCIDENT)
    u, u_kind = (float(x) for x in gen.random(2))
    chance = mf.accident_chance(sub.accident_base, team.skill, team.coverage, mine.safety, ab)
    if u >= chance:
        return state, mine, [], []
    entries = [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=mine.company_id,
            memo=f"Fine: an accident at {mine_name(mine, data)}",
            debit=GENERAL_ADMIN,
            credit=CASH,
            amount=ab.fine_cents,
        )
    ]
    state = risk.reputation_hit(state, mine, balance)
    mine = replace(mine, accidents=mine.accidents + 1)
    template = ACCIDENT_TEMPLATES[int(u_kind * len(ACCIDENT_TEMPLATES))]
    logs = [_item(state, mine, "mine_accident", data, fine_cents=ab.fine_cents)]
    if "accident" not in queued and mine.accident_turn is None:
        queued.add("accident")
        state = _queue(state, template)
        mine = replace(mine, accident_turn=state.turn + 1)
    return state, mine, entries, logs


def _protest(
    state: GameState,
    mine: Mine,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    queued: set[str],
) -> tuple[GameState, Mine, list[LogItem]]:
    """35.4: a community protest at an operating mine with M18's monthly chance x the
    deposit's hidden sensitivity / 0.5, halved by a benefit agreement; one a month."""
    from tst.sim.exploration.geology import block_of
    from tst.sim.mining.risk import PROTEST_TEMPLATE

    pb = balance.exploration.permitting
    u = float(mining_draws(rng, state.turn, mine.id, PROTEST).random())
    if mine.protest_turn is not None or PROTEST_TEMPLATE in queued:
        return state, mine, []
    block = block_of(state, mine.region, mine.block)
    sensitivity = block.true_sensitivity if block is not None else SENSITIVITY_MID
    chance = pb.protest_rate * sensitivity / SENSITIVITY_MID
    if mine.benefit:
        chance *= 1 - pb.benefit_odds
    if u >= chance:
        return state, mine, []
    queued.add(PROTEST_TEMPLATE)
    state = _queue(state, PROTEST_TEMPLATE)
    mine = replace(mine, protest_turn=state.turn + 1, protests=mine.protests + 1)
    return state, mine, [_item(state, mine, "mine_protest_started", data)]


def would_be_cost_usd_t(state: GameState, mine: Mine, balance: Balance, data: GameData) -> float:
    """The all-in sustaining cost a t at capacity and the design grade (revealed numbers):
    what the Mines screen shows before the mine produces."""
    mb = balance.mining
    sub = mb.subtypes[mine.subtype]
    kind = kind_of(state, mine)
    oc = ore_cost(mine, balance, data, kind)
    fixed = fixed_usd(state, mine, balance, data) * 12
    ore_t = mine.ore_capacity_mt * MT
    var = mf.variable_usd(
        ore_t, oc, sub.fixed_share, mb.energy_share, power.index(state, mine.region, data)
    )
    sustaining = mb.sustaining_share * mine.capex_cents / CENTS
    spot = prices.spot_usd_t(state, mine.commodity, data, balance)
    royalty = spot * data.region(mine.region).royalty_rate
    return (fixed + var + sustaining) / mine.capacity_t + royalty

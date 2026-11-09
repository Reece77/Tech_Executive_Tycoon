"""Critical mine events and rival miners (docs/formulas.md 35.4-35.5).

- **Resource nationalism**: to December 2025 the events of nationalization_history.yaml; after
  it, each month and region one generator on stream `region_risk` (key: the region's index)
  draws a uniform per geology.yaml commodity, in that order, then the kind and the months: a
  (region, commodity) event comes with chance `monthly_base x resource_nationalism x strategic
  weight`. The events are a pure function of the seed and the month (the screen recomputes
  them). An export ban limits the region's mines of the commodity to selling inside the region;
  a takeover is a critical event: accept a state partner, fight (seizure and arbitration), or
  sell out.
- **Accidents and price crashes** are raised in phase 5 (tst.sim.mining.phase); their answers
  are applied here (`mining_step`).
- **Rival miners** (35.5): M17's suppliers hold abstract capacity in their region (their share
  of world output), following prices with a lag and cut by the region's events; they bid for
  the group's permitted projects and mines.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.commodities.config import SupplierGood
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.exploration import pipeline as xp
from tst.sim.ledger import (
    ARO,
    CASH,
    DISPOSAL,
    GENERAL_ADMIN,
    MINERAL_PROPERTIES,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.mining import prices
from tst.sim.mining.actions import LINK, closed, group_ids, mine_name
from tst.sim.mining.draws import BID, CHOICE, mining_draws, region_draws
from tst.sim.mining.models import Mine, MineDeal, RivalBid
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    life_of,
    listed_id,
    with_life,
    with_mine,
    with_mine_deal,
    with_product,
    with_queued,
    with_rival_bid,
)

TAKEOVER_TEMPLATE: Final = "mine_takeover"
STEPS: Final = (
    "investigate",
    "compensate",
    "contest",
    "partner",
    "fight",
    "sell_out",
    "care",
    "hedge",
    "keep",
)
EXTRA_DRAWS: Final = 2  # tunable-exempt: after the commodities, the kind and months uniforms
BID_MONTHS: Final = 3  # tunable-exempt: a rival's bid stays open this many months
PROJECT_BID, MINE_BID = 0, 1  # tunable-exempt: the bid draws' third key
BRAND_MAX: Final = 100.0  # tunable-exempt: the brand scale
YEAR: Final = 12  # tunable-exempt: calendar
EVENT_YEARS: Final = 5  # tunable-exempt: how far back an event can still cut rivals' output


# --- Resource nationalism (35.4) ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegionEvent:
    turn: int
    region: str
    commodity: str | None
    kind: str  # nationalization or export_ban
    months: int
    title: str
    seeded: bool


def _label(data: GameData, key: str | None) -> str:
    if key is None or data.geology is None:
        return "minerals"
    return data.geology.commodity(key).label.lower()


def region_events(
    rng: RngFactory, turn: int, balance: Balance, data: GameData
) -> list[RegionEvent]:
    """The month's events: history to its last month, then seeded (module docstring)."""
    hist = data.nationalization
    if hist is None or data.geology is None:
        return []
    if turn <= hist.last_turn:
        return [
            RegionEvent(e.turn, e.region, e.commodity, e.kind, e.months, e.title, False)
            for e in hist.events
            if e.turn == turn
        ]
    nb = balance.mining.nationalization
    commodities = [c.key for c in data.geology.commodities]
    out: list[RegionEvent] = []
    for r, region in enumerate(data.region_keys):
        gen = region_draws(rng, turn, r)
        us = [float(x) for x in gen.random(len(commodities) + EXTRA_DRAWS)]
        u_kind, u_months = us[len(commodities)], us[len(commodities) + 1]
        nat = data.region(region).resource_nationalism
        for c, u in zip(commodities, us, strict=False):
            if u >= nb.monthly_base * nat * balance.mining.strategic.get(c, 0.0):
                continue
            ban = u_kind < nb.ban_share
            months = round(nb.ban_months.lo + (nb.ban_months.hi - nb.ban_months.lo) * u_months)
            where = data.region(region).label
            title = (
                f"A government in {where} bans exports of unprocessed {_label(data, c)}"
                if ban
                else f"A government in {where} moves to take a stake in {_label(data, c)} mines"
            )
            out.append(
                RegionEvent(
                    turn,
                    region,
                    c,
                    "export_ban" if ban else "nationalization",
                    months if ban else 0,
                    title,
                    True,
                )
            )
    return out


def region_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    logs: list[LogItem] = []
    queued = False
    group = group_ids(state)
    for event in region_events(rng, state.turn, balance, data):
        hit = [
            m
            for m in sorted(state.mines, key=lambda m: m.id)
            if m.is_open
            and m.company_id in group
            and m.region == event.region
            and m.commodity == event.commodity
        ]
        for mine in hit:
            if event.kind == "export_ban":
                until = state.turn + event.months - 1
                mine = replace(mine, ban_until=max(until, mine.ban_until or until))
                logs.append(
                    inbox_item(
                        state.turn,
                        state.player.id,
                        "mine_export_ban",
                        link_kind=LINK,
                        link_id=mine.id,
                        mine=mine_name(mine, data),
                        title=event.title,
                        months=event.months,
                    )
                )
            elif mine.state_share == 0 and mine.takeover_turn is None:
                if not queued:
                    queued = True
                    state = _queue(state, TAKEOVER_TEMPLATE)
                mine = replace(mine, takeover_turn=state.turn + 1)
                logs.append(
                    inbox_item(
                        state.turn,
                        state.player.id,
                        "mine_takeover_threat",
                        link_kind=LINK,
                        link_id=mine.id,
                        mine=mine_name(mine, data),
                        title=event.title,
                    )
                )
            state = with_mine(state, mine)
    return state, [], logs


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


def arbitration_month(
    state: GameState, mine: Mine, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """35.4, fight: legal costs a month until the award; then, with chance `award_win`, an
    award of `award_share` of the book value at seizure."""
    nb = balance.mining.nationalization
    turn, name = state.turn, mine_name(mine, data)
    assert mine.arbitration_due is not None
    if turn < mine.arbitration_due:
        entry = LedgerEntry.transfer(
            turn=turn,
            company_id=mine.company_id,
            memo=f"Arbitration: {name}",
            debit=GENERAL_ADMIN,
            credit=CASH,
            amount=nb.arbitration_legal_cents,
        )
        return state, [entry], []
    gen = mining_draws(rng, turn, mine.id, CHOICE)
    u_win, u_share = (float(x) for x in gen.random(2))
    award = 0
    if u_win < nb.award_win:
        share = nb.award_share.lo + (nb.award_share.hi - nb.award_share.lo) * u_share
        award = round(mine.seized_book_cents * share)
    entries = []
    if award:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=mine.company_id,
                memo=f"Arbitration award: {name}",
                debit=CASH,
                credit=DISPOSAL,
                amount=award,
            )
        )
    state = with_mine(state, replace(mine, status="closed", closed_turn=turn, arbitration_due=None))
    log = inbox_item(
        turn,
        state.player.id,
        "mine_award" if award else "mine_award_lost",
        link_kind=LINK,
        link_id=mine.id,
        mine=name,
        amount_cents=award,
    )
    return state, entries, [log]


# --- Answers (35.4) -----------------------------------------------------------------------------


def reputation_hit(state: GameState, mine: Mine, balance: Balance) -> GameState:
    """An accident always costs brand (every product of the mine's group) and credibility (the
    group's listed company)."""
    from tst.sim.press.moments import adjust_credibility

    ab = balance.mining.accident
    group = group_ids(state)
    for p in state.products:
        if p.company_id in group and p.status != "retired":
            state = with_product(
                state, replace(p, brand=max(0.0, min(BRAND_MAX, p.brand - ab.brand_hit)))
            )
    return adjust_credibility(
        state, listed_id(state), -ab.credibility_hit, "a mine accident", balance
    )


def _event_mines(state: GameState, event: GameEvent) -> list[Mine]:
    t = event.turn
    template = event.template_id or ""
    out = []
    for m in sorted(state.mines, key=lambda m: m.id):
        if (
            (template == TAKEOVER_TEMPLATE and m.takeover_turn == t)
            or (
                template.startswith("mine_")
                and template not in (TAKEOVER_TEMPLATE, "mine_price_crash")
                and m.accident_turn == t
            )
            or (template == "mine_price_crash" and m.crash_turn == t)
        ):
            out.append(m)
    return out


def _persona(state: GameState, trait: str, value: float, why: str, balance: Balance) -> GameState:
    founder = state.founder_of(state.player.id)
    if founder is None or not value:
        return state
    from tst.sim.founder.persona import raise_trait
    from tst.sim.founder.stress import new_life

    life = life_of(state, founder.id) or new_life(founder.id, balance)
    return with_life(state, raise_trait(life, trait, value, why, state.turn, balance))


def mining_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A mine event's answer, applied by the engine (35.4)."""
    mb = balance.mining
    ab, nb, cb = mb.accident, mb.nationalization, mb.crash
    turn = state.turn
    rng = RngFactory(state.save_meta.master_seed)  # the save's own streams (ADR-0002)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for mine in _event_mines(state, event):
        name, cid = mine_name(mine, data), mine.company_id

        def pay(
            memo: str, cents: int, debit: str = GENERAL_ADMIN, cid: int = cid, name: str = name
        ) -> None:
            if cents:
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=cid,
                        memo=f"{memo}: {name}",
                        debit=debit,
                        credit=CASH,
                        amount=cents,
                    )
                )

        if step in ("investigate", "compensate", "contest"):
            if step == "investigate":
                mine = replace(mine, stopped_until=turn + ab.stop_months - 1)
                pay("Investigation fine", round(ab.fine_cents * ab.stop_fine_share))
            elif step == "compensate":
                pay("Compensation", ab.compensate_cents)
                state = _persona(
                    state, "beloved", ab.beloved, "compensated a mine accident", balance
                )
            else:
                state = _persona(
                    state, "ruthless", ab.ruthless, "contested a mine accident", balance
                )
                u = float(mining_draws(rng, turn, mine.id, CHOICE).random())
                if u < ab.contest_risk:
                    pay("Court ruling", round(ab.fine_cents * ab.contest_fine_mult))
                    logs.append(_item(state, mine, "mine_court_lost", name))
            mine = replace(mine, accident_turn=None)
        elif step in ("partner", "fight", "sell_out"):
            mine = replace(mine, takeover_turn=None)
            book = mine.book_cents
            owed = mine.aro_cents - mine.aro_paid_cents
            if step == "partner":
                u = float(mining_draws(rng, turn, mine.id, CHOICE).random())
                share = nb.partner_share.lo + (nb.partner_share.hi - nb.partner_share.lo) * u
                sold = round(book * share)
                if sold:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=cid,
                            memo=f"State partner buys {share:.0%}: {name}",
                            debit=CASH,
                            credit=MINERAL_PROPERTIES,
                            amount=sold,
                        )
                    )
                mine = replace(mine, state_share=share, depleted_cents=mine.depleted_cents + sold)
                logs.append(_item(state, mine, "mine_state_partner", name, pct=f"{share:.0%}"))
            else:
                proceeds = round(book * nb.sell_out_share) if step == "sell_out" else 0
                lines = [
                    LedgerLine(CASH, proceeds),
                    LedgerLine(ARO, owed),
                    LedgerLine(MINERAL_PROPERTIES, -book),
                    LedgerLine(DISPOSAL, book - owed - proceeds),
                ]
                lines = [x for x in lines if x.amount]
                if len(lines) >= 2:
                    entries.append(
                        LedgerEntry(
                            turn,
                            cid,
                            f"{'Sold to the state' if proceeds else 'Seized'}: {name}",
                            tuple(lines),
                        )
                    )
                gone = replace(mine, aro_paid_cents=mine.aro_cents)  # the state takes the duty
                state = closed(state, gone, "sold_to_state" if step == "sell_out" else "seized")
                mine = state.mine(mine.id) or gone
                if step == "fight":
                    u = float(mining_draws(rng, turn, mine.id, CHOICE).random())
                    span = nb.arbitration_months
                    months = round(span.lo + (span.hi - span.lo) * u)
                    mine = replace(
                        mine,
                        status="seized",
                        close_reason="seized",
                        seized_book_cents=book,
                        arbitration_due=turn + months,
                    )
                    logs.append(_item(state, mine, "mine_seized", name, months=months))
                else:
                    logs.append(
                        _item(state, mine, "mine_sold_to_state", name, amount_cents=proceeds)
                    )
        elif step in ("care", "hedge", "keep"):
            mine = replace(mine, crash_turn=None, crash_answered=True)
            if step == "care" and mine.status == "producing":
                mine = replace(mine, status="care", care_since=turn)
                logs.append(_item(state, mine, "mine_care", name))
            elif step == "hedge":
                spot = prices.spot_usd_t(state, mine.commodity, data, balance)
                deal = MineDeal(
                    id=max((d.id for d in state.mine_deals), default=0) + 1,
                    mine_id=mine.id,
                    kind="offtake",
                    buyer="A refiner (hedge)",
                    signed_turn=turn,
                    end_turn=turn + cb.hedge_years * 12 - 1,
                    volume_t_year=mine.capacity_t * cb.hedge_share,
                    signing_usd_t=spot,
                    floor_usd_t=spot * (1 - mb.sale.collar),
                    ceiling_usd_t=spot * (1 + mb.sale.collar),
                    last_usd_t=spot,
                )
                state = with_mine_deal(state, deal)
        state = with_mine(state, mine)
    return state, entries, logs


def _item(state: GameState, mine: Mine, template: str, name: str, **params: str | int) -> LogItem:
    return inbox_item(
        state.turn, state.player.id, template, link_kind=LINK, link_id=mine.id, mine=name, **params
    )


# --- Rival miners (35.5) -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RivalCapacity:
    supplier: str
    name: str
    commodity: str
    region: str
    start_share: float  # share of world output at the start
    capacity_share: float  # now, after expansions and cuts
    output_share: float  # this month's output (crashes and events cut it)


def rival_capacity(
    rng: RngFactory, turn: int, state: GameState, balance: Balance, data: GameData
) -> list[RivalCapacity]:
    """35.5, a pure function of the price path and the region's events: capacity expands by
    `expand` `lag_months` after a year's mean price index tops `spike`; output is cut by `cut`
    in a month under `crash`, and by `rival_cut` while an event of the commodity runs in the
    supplier's region. Capacity stays within [floor, cap] x its start."""
    rb = balance.mining.rivals
    if data.suppliers is None or data.geology is None or data.commodity_history is None:
        return []
    explored = {c.key for c in data.geology.commodities}
    out = []
    events: list[RegionEvent] = []
    for t in range(max(0, turn - EVENT_YEARS * YEAR), turn + 1):
        events += region_events(rng, t, balance, data)
    for s in data.suppliers.suppliers:
        for good, share in _shares(s.goods):
            if good not in explored:
                continue
            idx = [_index_at(state, good, t, data, balance) for t in range(turn + 1)]
            cap, last_start = 1.0, -YEAR
            pending: list[int] = []
            for t in range(turn + 1):
                cap += rb.expand * sum(1 for due in pending if due == t)
                window = idx[max(0, t + 1 - YEAR) : t + 1]
                if len(window) == YEAR and sum(window) / YEAR > rb.spike and t - last_start >= YEAR:
                    pending.append(t + rb.lag_months)
                    last_start = t
                cap = min(rb.cap, max(rb.floor, cap))
            output = cap * (1 - rb.cut if idx[turn] < rb.crash else 1.0)
            if any(
                e.region == s.region and e.commodity == good and e.turn + max(e.months, 12) > turn
                for e in events
            ):
                output *= 1 - balance.mining.nationalization.rival_cut
            out.append(
                RivalCapacity(s.key, s.name, good, s.region, share, share * cap, share * output)
            )
    return out


def _shares(goods: Mapping[str, SupplierGood]) -> list[tuple[str, float]]:
    return [(g, v.share) for g, v in goods.items()]


def _index_at(state: GameState, good: str, t: int, data: GameData, balance: Balance) -> float:
    from tst.sim.commodities import commodity

    try:
        return commodity.price(state, good, t, data, balance) / commodity.mean_of(data, good)
    except commodity.FutureMonthError:  # a seeded month the state no longer holds: today's
        return commodity.index_now(state, good, data)


def rival_bids_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """35.5: a supplier of the commodity bids for a permitted project with no mine (at
    `buy_share` of M18's sale price) or a producing mine (at `mine_bid` of its book value),
    with chance `buy_monthly` a month each; a bid stays open BID_MONTHS months."""
    rb = balance.mining.rivals
    turn = state.turn
    logs: list[LogItem] = []
    for bid in state.rival_bids:
        if bid.status == "open" and turn > bid.expires_turn:
            state = with_rival_bid(state, replace(bid, status="lapsed"))
    group = group_ids(state)
    open_for = {(b.project_id, b.mine_id) for b in state.rival_bids if b.status == "open"}
    built = {m.project_id for m in state.mines}
    next_id = max((b.id for b in state.rival_bids), default=0) + 1
    for p in sorted(state.projects, key=lambda p: p.id):
        if p.status != "permitted" or p.company_id not in group or p.id in built:
            continue
        if (p.id, None) in open_for:
            continue
        if float(mining_draws(rng, turn, p.id, BID, PROJECT_BID).random()) >= rb.buy_monthly:
            continue
        buyer = xp.buyer_for(p, data, turn)
        price = round(xp.sale_price_cents(state, p, balance, data) * rb.buy_share)
        if buyer is None or price <= 0:
            continue
        bid = RivalBid(next_id, p.company_id, buyer[0], p.id, None, price, turn, turn + BID_MONTHS)
        next_id += 1
        state = with_rival_bid(state, bid)
        logs.append(
            inbox_item(
                turn,
                state.player.id,
                "rival_bid",
                link_kind="exploration",
                link_id=p.id,
                bidder=buyer[1],
                asset=xp.label_of(p),
                amount_cents=price,
            )
        )
    for m in sorted(state.mines, key=lambda m: m.id):
        if m.status != "producing" or m.company_id not in group or (None, m.id) in open_for:
            continue
        if float(mining_draws(rng, turn, m.id, BID, MINE_BID).random()) >= rb.buy_monthly:
            continue
        project = next((p for p in state.projects if p.id == m.project_id), None)
        buyer = xp.buyer_for(project, data, turn) if project is not None else None
        price = round(m.book_cents * rb.mine_bid)
        if buyer is None or price <= 0:
            continue
        bid = RivalBid(next_id, m.company_id, buyer[0], None, m.id, price, turn, turn + BID_MONTHS)
        next_id += 1
        state = with_rival_bid(state, bid)
        logs.append(
            inbox_item(
                turn,
                state.player.id,
                "rival_bid",
                link_kind=LINK,
                link_id=m.id,
                bidder=buyer[1],
                asset=mine_name(m, data),
                amount_cents=price,
            )
        )
    return state, logs


def ban_active(mine: Mine, turn: int) -> bool:
    return mine.ban_until is not None and turn <= mine.ban_until

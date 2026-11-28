"""Break-ups and unbundling (docs/formulas.md 48.4): rare, visible, warned years ahead.

**Preconditions** for a group, a regulator and a market: the regulator's law allows structural
remedies (`structural`) and its strictness is at least `structural.min_strictness`; and either a
ruling against the group in that market within `ruling_years` whose remedy it now breaches, or
two rulings against it there (history's count) within `two_rulings_years`.

**Warning signs.** While the preconditions hold, a watch keeps signs: the first at once, then one
every `warning_every` months, in order: press coverage (29), a regulator's report naming the
remedy, a political event, the board's concern (14). When the preconditions lapse, the watch and
its signs end.

**The order.** A ruling against the group in the market may be structural only with the
preconditions holding and the watch's first sign at least `warning_months` old; then with
`structural.chance` (stream `regulation`, (1, case, STRUCTURAL)). The order names the unit (the
platform's operating system and store, a subsidiary selling in the market, or the group's
products in the market). Within `window_months` the group spins it off (31.5: a subsidiary of a
listed holding company) or sells it (28: to the rival with the largest share in the market, at
`sale_multiple` x the unit's trailing-year revenue); an appeal (12-36 months, odds shown as a
range) moves the deadline back by its length. After the deadline, each month brings a periodic
penalty: the regime's `periodic_share` x the group's average daily turnover x `periodic_days`.
Rivals appeal once if their personality contests, then sell.

Property (48.4, tested): no order without the preconditions and `warning_months` of warnings."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.ledger import CASH, DISPOSAL, FINES, GOODWILL, LedgerBalances, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.products.models import SELLING
from tst.sim.regulation import data as rdata
from tst.sim.regulation import draws
from tst.sim.regulation import strictness as strict
from tst.sim.regulation.config import RegulatorDef
from tst.sim.regulation.duties import breaches, platforms_in
from tst.sim.regulation.measure import turnover_year
from tst.sim.regulation.models import Case, Order, WarningSign, Watch
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, owner_of, with_product, with_queued

SIGNS: Final[tuple[WarningSign, ...]] = ("press", "report", "political", "board")
ORDER_EVENT: Final = "regulation_order"
LINK: Final = "regulation"
DAYS_A_YEAR: Final = 365  # tunable-exempt: calendar


def conditions(
    state: GameState,
    company_id: int,
    reg: RegulatorDef,
    market: str,
    balance: Balance,
    data: GameData,
) -> bool:
    """The preconditions (module docstring), before any new ruling."""
    sb = balance.regulation.structural
    if not reg.structural or strict.strictness(state, reg, balance, data) < sb.min_strictness:
        return False
    breached = set(breaches(state, company_id, reg))
    recent = state.turn - sb.ruling_years * MONTHS_PER_YEAR
    ruled = [
        c
        for c in state.reg_cases
        if c.company_id == company_id
        and c.regulator == reg.key
        and c.ruled_turn is not None
        and c.outcome not in ("annulled", "dismissed")
        and c.market == market
    ]
    if any(
        c.ruled_turn is not None and c.ruled_turn > recent and c.remedy in breached for c in ruled
    ):
        return True
    ten = state.turn - sb.two_rulings_years * MONTHS_PER_YEAR
    history = [
        t for t in rdata.history_rulings(state, data, company_id, reg.key, state.turn) if t > ten
    ]
    return len([c for c in ruled if (c.ruled_turn or 0) > ten]) + len(history) >= 2


def watch_of(state: GameState, company_id: int, regulator: str, market: str) -> Watch | None:
    return next(
        (
            w
            for w in state.reg_watches
            if (w.company_id, w.regulator, w.market) == (company_id, regulator, market)
        ),
        None,
    )


def markets_of(state: GameState, company_id: int, regulator: str) -> set[str]:
    return {
        c.market
        for c in state.reg_cases
        if c.company_id == company_id and c.regulator == regulator and c.ruled_turn is not None
    }


def watches_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Warning signs begin, build and end with the preconditions (module docstring)."""
    sb = balance.regulation.structural
    logs: list[LogItem] = []
    keep: list[Watch] = []
    pairs = sorted({(c.company_id, c.regulator) for c in state.reg_cases})
    for company_id, regulator in pairs:
        reg = rdata.file(data).regulator(regulator)
        for market in sorted(markets_of(state, company_id, regulator)):
            w = watch_of(state, company_id, regulator, market)
            if not conditions(state, company_id, reg, market, balance, data):
                continue
            if w is None:
                w = Watch(company_id, regulator, market, state.turn)
            last = w.signs[-1][1] if w.signs else None
            if last is None or state.turn - last >= sb.warning_every:
                sign = SIGNS[len(w.signs) % len(SIGNS)]
                w = replace(w, signs=(*w.signs, (sign, state.turn)))
                if company_id == state.player.id:
                    logs.append(
                        inbox_item(
                            state.turn, company_id, f"regulation_warning_{sign}", link_kind=LINK,
                            regulator=reg.name, market=market.replace("_", " "),
                        )
                    )  # fmt: skip
            keep.append(w)
    return replace(state, reg_watches=tuple(keep)), logs


def may_order(
    state: GameState, case: Case, reg: RegulatorDef, balance: Balance, data: GameData
) -> bool:
    """A ruling may be structural (module docstring): preconditions and old enough warnings."""
    w = watch_of(state, case.company_id, reg.key, case.market)
    if w is None or not w.signs:
        return False
    if state.turn - w.first_turn < balance.regulation.structural.warning_months:
        return False
    return conditions(state, case.company_id, reg, case.market, balance, data)


def _unit(
    state: GameState, company_id: int, reg: RegulatorDef, market: str
) -> tuple[str, int | None, tuple[int, ...], str]:
    """What the order names: the platform's OS and store, a subsidiary, or the products."""
    if market == "devices":
        for p in platforms_in(state, company_id, reg.region):
            if p.product_id is not None and not p.historical:
                return "platform", p.id, (p.product_id,), f"{p.name} and {p.store}"
    group = [c for c in state.companies if owner_of(state, c.id) == company_id]
    products = [
        p
        for p in state.products
        if p.category == market and p.status in SELLING and any(p.company_id == c.id for c in group)
    ]
    subs = {p.company_id for p in products if p.company_id != company_id}
    if len(subs) == 1:
        sub = next(iter(subs))
        return (
            "company",
            sub,
            tuple(p.id for p in products if p.company_id == sub),
            state.company(sub).name,
        )
    if not products and market == "devices":
        owned = platforms_in(state, company_id, reg.region)
        if owned:
            p = owned[0]
            return "platform", p.id, (), f"{p.name} and {p.store}"
    label = ", ".join(sorted(p.name for p in products)) or market.replace("_", " ")
    return "products", None, tuple(p.id for p in products), label


def next_order_id(state: GameState) -> int:
    return max([0, *(o.id for o in state.reg_orders)]) + 1


def with_order(state: GameState, order: Order) -> GameState:
    orders = tuple(order if o.id == order.id else o for o in state.reg_orders)
    if all(o.id != order.id for o in state.reg_orders):
        orders = (*orders, order)
    return replace(state, reg_orders=orders)


def order(
    state: GameState, case: Case, reg: RegulatorDef, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A structural order on the case's group (module docstring)."""
    kind, unit_id, products, label = _unit(state, case.company_id, reg, case.market)
    w = watch_of(state, case.company_id, reg.key, case.market)
    o = Order(
        id=next_order_id(state),
        company_id=case.company_id,
        regulator=reg.key,
        case_id=case.id,
        unit_kind=kind,  # type: ignore[arg-type]
        unit_id=unit_id,
        product_ids=products,
        unit_label=label,
        ordered_turn=state.turn,
        deadline_turn=state.turn + balance.regulation.structural.window_months,
        warned_from=w.first_turn if w is not None else state.turn,
    )
    state = with_order(state, o)
    return _ask(state, o)


def _ask(state: GameState, o: Order) -> tuple[GameState, list[LogItem]]:
    if o.company_id != state.player.id:
        return state, []
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=o.company_id,
            template_id=ORDER_EVENT,
            due_turn=state.turn + 1,
            source_event_id=None,
        ),
    )
    return with_order(state, replace(o, asked_turn=state.turn + 1, asked_template=ORDER_EVENT)), []


def unit_revenue_cents(state: GameState, o: Order) -> int:
    """The unit's trailing year of revenue: its products' customers x price, x 12, exact."""
    month = Fraction(0)
    for pid in o.product_ids:
        for seg in state.segments_of(pid):
            month += exact(seg.customers) * (seg.price_cents or 0)
        for reg in state.regional_segments_of(pid):
            month += exact(reg.customers) * (reg.price_cents or 0)
    return round(month * MONTHS_PER_YEAR)


def buyer_of(state: GameState, o: Order) -> int | None:
    """The rival with the largest share in the unit's market (28.4's divestiture buyer)."""
    market = next((c.market for c in state.reg_cases if c.id == o.case_id), "devices")
    group = {c.id for c in state.companies if owner_of(state, c.id) == o.company_id}
    books = {c.id for c in state.ledger_companies()}
    totals: dict[int, float] = {}
    for p in state.products:
        if p.category != market or p.status not in SELLING or p.company_id in group:
            continue
        if p.company_id not in books:
            continue
        n = sum(s.customers for s in state.segments_of(p.id)) + sum(
            r.customers for r in state.regional_segments_of(p.id)
        )
        totals[p.company_id] = totals.get(p.company_id, 0.0) + n
    if not totals:
        return None
    return sorted(totals.items(), key=lambda x: (-x[1], x[0]))[0][0]


def sell(
    state: GameState, o: Order, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """The unit goes to the buyer with its customers, for `sale_multiple` x its year's revenue."""
    buyer = buyer_of(state, o)
    if buyer is None:
        return state, [], []
    price = round(unit_revenue_cents(state, o) * exact(balance.regulation.structural.sale_multiple))
    sold = []
    for pid in o.product_ids:
        product = state.product(pid)
        if product is not None:
            sold.append(product)
            state = with_product(state, replace(product, company_id=buyer))
    # M57r-A (review 10 item 17): a bank's or insurer's charter and books go with its line
    from tst.sim.finserv.charters import on_sale

    state, charter_entries = on_sale(state, o.company_id, sold, balance, data)
    state = replace(
        state,
        units=tuple(
            replace(u, product_id=None) if u.product_id in o.product_ids else u for u in state.units
        ),
    )
    if o.unit_kind == "platform" and o.unit_id is not None:
        state = replace(
            state,
            platforms=tuple(
                replace(p, owner_id=buyer, owner_label=state.company(buyer).name)
                if p.id == o.unit_id
                else p
                for p in state.platforms
            ),
        )
    entries = []
    if price > 0:
        entries = [
            LedgerEntry.transfer(
                turn=state.turn, company_id=o.company_id, memo=f"Ordered sale of {o.unit_label}",
                debit=CASH, credit=DISPOSAL, amount=price,
            ),
            LedgerEntry.transfer(
                turn=state.turn, company_id=buyer, memo=f"Purchase of {o.unit_label}",
                debit=GOODWILL, credit=CASH, amount=price,
            ),
        ]  # fmt: skip
    entries += charter_entries
    state = with_order(state, replace(o, status="sold", closed_turn=state.turn))
    logs = []
    if o.company_id == state.player.id:
        logs.append(
            inbox_item(
                state.turn, o.company_id, "regulation_order_done", link_kind=LINK,
                unit=o.unit_label, how="sold", buyer=state.company(buyer).name, price_cents=price,
            )
        )  # fmt: skip
    return state, entries, logs


def can_spin_off(state: GameState, o: Order) -> bool:
    from tst.sim.group.subsidiaries import is_subsidiary
    from tst.sim.state import holding_of

    return (
        o.unit_kind == "company"
        and o.unit_id is not None
        and holding_of(state) is not None
        and is_subsidiary(state, o.unit_id)
    )


def spin_off(
    state: GameState,
    o: Order,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """31.5's spin-off of the ordered subsidiary (none kept), when it can be done."""
    from tst.sim.errors import SimError
    from tst.sim.group.capital import SpinOff
    from tst.sim.group.capital import spin_off as do_spin_off

    if balances is None or not can_spin_off(state, o) or o.unit_id is None:
        return state, [], [
            inbox_item(
                state.turn, o.company_id, "regulation_spin_off_unavailable", link_kind=LINK,
                unit=o.unit_label,
            )
        ]  # fmt: skip
    founder = state.founder_of(state.player.id)
    try:
        out = do_spin_off(
            state, SpinOff(founder.id if founder else 0, o.unit_id, 0), balances, balance, data
        )
    except SimError:
        return state, [], []
    state = with_order(out.state, replace(o, status="spun_off", closed_turn=state.turn))
    return state, list(out.entries), list(out.log)


def appeal(state: GameState, o: Order, rng: RngFactory, balance: Balance) -> GameState:
    lo, hi = balance.regulation.structural.appeal_months
    gen = draws.gen(rng, state.turn, draws.ORDER, o.id, draws.STAGE_LENGTH)
    until = state.turn + lo + int(gen.integers(hi - lo + 1))
    return with_order(state, replace(o, status="appealing", appeal_until=until))


def orders_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Appeals decide; rivals act; open orders past their deadline pay periodic penalties."""
    sb = balance.regulation.structural
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for o in sorted(state.reg_orders, key=lambda x: x.id):
        o = next(x for x in state.reg_orders if x.id == o.id)
        if o.status == "appealing" and o.appeal_until is not None and o.appeal_until <= state.turn:
            gen = draws.gen(rng, state.turn, draws.ORDER, o.id, draws.OUTCOME)
            lo, hi = sb.appeal_win
            odds = lo + (hi - lo) * float(gen.random())
            length = o.appeal_until - (o.asked_turn or o.ordered_turn)
            if float(gen.random()) < odds:
                state = with_order(state, replace(o, status="overturned", closed_turn=state.turn))
                if o.company_id == state.player.id:
                    logs.append(
                        inbox_item(
                            state.turn, o.company_id, "regulation_order_overturned",
                            link_kind=LINK, unit=o.unit_label,
                        )
                    )  # fmt: skip
                continue
            o = replace(o, status="open", deadline_turn=o.deadline_turn + max(0, length))
            state = with_order(state, o)
            state, more = _ask(state, o)
            logs += more
        if o.status == "open" and o.company_id != state.player.id:
            fights = state.company(o.company_id).personality in balance.regulation.rivals.contest
            if fights and o.appeal_until is None:
                state = appeal(state, o, rng, balance)
                continue
            state, more_e, more_l = sell(state, o, balance, data)
            entries += more_e
            logs += more_l
            continue
        if o.status == "open" and state.turn > o.deadline_turn:
            cents = periodic_cents(state, o, balance, data)
            if cents > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn, company_id=o.company_id,
                        memo=f"Periodic penalty: {o.unit_label}", debit=FINES, credit=CASH,
                        amount=cents,
                    )
                )  # fmt: skip
    return state, entries, logs


def periodic_cents(state: GameState, o: Order, balance: Balance, data: GameData) -> int:
    regime = rdata.regime_of(data, o.regulator)
    share = (
        regime.periodic_share
        if regime is not None
        else balance.regulation.fine.default_max_share / 2
    )
    turnover = turnover_year(state, o.company_id)
    return round(share * turnover / DAYS_A_YEAR * balance.regulation.structural.periodic_days)

"""Rivals form groups (docs/formulas.md 41.3).

**Deals** (a quarter's first month from 2026): incumbents and named chain companies that no one
owns, with cash above `groups.cash_months` of costs, each draw (stream world, key
(3, *rival_key)) whether to buy this quarter (`rival_mna_rate`). A buyer considers the chain
companies no one owns and, if it is an incumbent, the other incumbents no one owns; it scores
each it can pay for from cash beyond that buffer by its personality's preference for the deal's
kind over the price: **vertical** (an incumbent selling devices or chips buying a producer of an
input it secures, or of foundry wafers), **horizontal** (a chain company buying another making
one of its goods, or an incumbent another in one of its categories) or **other**. The price is
the target's value x (1 + `groups.premium`): a chain company's `ev_multiple` x a year's EBITDA
less net debt, an incumbent's market cap or V_f (28.1).

**Antitrust** (28.4's test and lines, `antitrust.*`): for two chain companies, the groups'
combined share of a good's world capacity; for two incumbents, 28.4's customers test. Cleared
deals close at once; a review lasts `groups.review_months` and is blocked with 28.4's chance;
at or over the block line the deal is blocked. **Closing:** the buyer pays cash into 1810; the
target joins its group (an `Ownership`), runs under a mandate by the buyer's personality
(`groups.mandate`) and takes that mandate's personality for its decisions.

**Spin-offs** (December): a listed rival owner whose group's conglomerate discount (31.7, its
segments being its distinct goods and categories) exceeds `spinoff_discount` spins off its
least related subsidiary to its shareholders (its 1810 book against equity), one a year.

**Supply security** (January): each incumbent selling devices or chips needs, of each
`groups.security_goods` input, its share (by revenue among them) of `security_need` x the
good's world demand. Below `security_cover` of it under offtakes, it signs one with the producer
of the good with most capacity not already contracted, up to `security_target`, for
`security_years`. In a shortage the player's spot purchases get what those contracts leave
(tst.sim.commodities.commodity.world_month).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.group.formulas import conglomerate_discount
from tst.sim.group.models import Ownership
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    DEBT,
    INVESTMENT_SUBSIDIARIES,
    AccountCode,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.mna import antitrust, valuation
from tst.sim.mna import formulas as mf
from tst.sim.mna.deals import monthly_costs_cents
from tst.sim.money import Cents, format_money
from tst.sim.products.models import SELLING
from tst.sim.rivals.models import INCUMBENT_KEY
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, owner_at, with_company, with_ownership
from tst.sim.world import data as wd
from tst.sim.world import draws
from tst.sim.world import operate as wo
from tst.sim.world import query as wq
from tst.sim.world.config import FOUNDRY_GOOD, MandateKind
from tst.sim.world.models import DealKind, RivalDeal, RivalMandate, WorldOfftake
from tst.sim.world.news import Item

QUARTER: Final = 3  # tunable-exempt: months a quarter
DEAL_DRAWS: Final = 3  # tunable-exempt: whether, the review's length, its outcome
MONTHS: Final = 12  # tunable-exempt: calendar
JANUARY, DECEMBER = 0, 11  # tunable-exempt: month indexes
MANDATE_PERSONALITY: Final[dict[str, str]] = {  # tunable-exempt: 28.5's directives
    "grow": "aggressive",
    "margin": "premium",
    "cash": "cost_leader",
}


# --- Who is what -------------------------------------------------------------------------------


def is_incumbent(c: CompanyState) -> bool:
    return c.rival_key[:1] == (INCUMBENT_KEY,)


def unowned(state: GameState, company_id: int) -> bool:
    return owner_at(state, company_id) is None and state.company(company_id).parent_id is None


def chain_goods(state: GameState, company_id: int) -> set[str]:
    return {
        f.good
        for f in state.world_facilities
        if f.company_id == company_id and f.status != "closed"
    }


def categories(state: GameState, company_id: int) -> set[str]:
    return {p.category for p in state.company_products(company_id) if p.status in SELLING}


def hardware(state: GameState, company_id: int, data: GameData) -> bool:
    """An incumbent selling devices, servers or chips (unit-sale categories, 26.1)."""
    return any(data.category(c).sells_units for c in categories(state, company_id))


def deal_kind(
    state: GameState, buyer: CompanyState, target: CompanyState, balance: Balance, data: GameData
) -> DealKind:
    if target.is_chain:
        goods = chain_goods(state, target.id)
        if buyer.is_chain:
            return "horizontal" if goods & chain_goods(state, buyer.id) else "other"
        inputs = {*balance.world.groups.security_goods, FOUNDRY_GOOD}
        return "vertical" if hardware(state, buyer.id, data) and goods & inputs else "other"
    return "horizontal" if categories(state, buyer.id) & categories(state, target.id) else "other"


# --- Values ------------------------------------------------------------------------------------


def chain_value_cents(
    state: GameState, company_id: int, balances: Mapping[tuple[int, AccountCode], Cents],
    balance: Balance,
) -> int:  # fmt: skip
    """A chain company's value: `ev_multiple` x a year's EBITDA less net debt, at least 0."""
    rec = wq.chain_record(state, company_id)
    if rec is None or not rec.ebitda:
        return 0
    year = sum(rec.ebitda) * MONTHS // len(rec.ebitda)
    net_debt = -account_balance(balances, company_id, DEBT) - account_balance(
        balances, company_id, CASH
    )
    return max(0, round(year * balance.world.ev_multiple) - net_debt)


def value_cents(
    state: GameState,
    company_id: int,
    balances: Mapping[tuple[int, AccountCode], Cents],
    balance: Balance,
    data: GameData,
) -> int:
    """What a rival pays for before its premium (hidden, 41.9)."""
    if state.company(company_id).is_chain:
        return chain_value_cents(state, company_id, balances, balance)
    cap = valuation.market_cap_cents(state, company_id, balances, balance, data)
    if cap is not None:
        return cap
    return valuation.fundamental_value_cents(state, company_id, balances, balance, data)


def costs_cents(state: GameState, company_id: int, balance: Balance, data: GameData) -> int:
    """A month's costs: a chain company's last month's, an incumbent's 15.3 cost."""
    rec = wq.chain_record(state, company_id)
    if rec is not None:
        return rec.costs_cents
    return monthly_costs_cents(state, company_id, balance, data)


# --- Antitrust ---------------------------------------------------------------------------------


def capacity_share(state: GameState, buyer_id: int, target_id: int) -> float:
    """The two groups' highest combined share of a good's world capacity (live)."""
    owner = antitrust.owner_of
    a, b = owner(state, buyer_id), owner(state, target_id)
    best = 0.0
    totals: dict[str, float] = {}
    by: dict[tuple[str, int], float] = {}
    for f in state.world_facilities:
        if f.status != "live":
            continue
        totals[f.good] = totals.get(f.good, 0.0) + f.capacity
        o = owner(state, f.company_id)
        by[(f.good, o)] = by.get((f.good, o), 0.0) + f.capacity
    for good, total in totals.items():
        mine, theirs = by.get((good, a), 0.0), by.get((good, b), 0.0)
        if mine > 0 and theirs > 0 and total > 0:
            best = max(best, (mine + theirs) / total)
    return best


def deal_share(
    state: GameState, buyer: CompanyState, target: CompanyState, balance: Balance, data: GameData
) -> float:
    if buyer.is_chain or target.is_chain:
        return capacity_share(state, buyer.id, target.id)
    share, _ = antitrust.combined_share(state, buyer.id, target.id, balance, data)
    return share


# --- Deals -------------------------------------------------------------------------------------


def groups_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    state, e, n = _reviews_end(state, balance, balances)
    entries += e
    news += n
    month = state.turn % MONTHS
    if state.turn % QUARTER == 0:
        state, e, n = _new_deals(state, rng, balance, data, balances)
        entries += e
        news += n
    if month == DECEMBER:
        state, e, n = _spinoffs(state, balance, data, balances)
        entries += e
        news += n
    if month == JANUARY:
        state, n = _security(state, balance, data)
        news += n
    return state, entries, news


def _new_deals(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    wb = balance.world
    gb = wb.groups
    turn = state.turn
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    running = {d.target_id for d in state.rival_deals if d.status == "review"}
    running |= {d.buyer_id for d in state.rival_deals if d.status == "review"}
    bought: set[int] = set()
    chain_targets = [c for c in state.chain() if not _aggregate(state, c.id)]
    buyers = [
        c
        for c in sorted((*state.rivals(), *chain_targets), key=lambda c: c.id)
        if (is_incumbent(c) or c.is_chain) and unowned(state, c.id)
    ]
    for buyer in buyers:
        if buyer.id in running or buyer.id in bought or not unowned(state, buyer.id):
            continue
        gen = draws.gen(rng, turn, draws.DEALS, *buyer.rival_key, draws.DEAL_TAG)
        u_rate, u_review, u_block = (float(x) for x in gen.random(DEAL_DRAWS))
        if u_rate >= wb.rival_mna_rate:
            continue
        cash = account_balance(balances, buyer.id, CASH)
        buffer = gb.cash_months * costs_cents(state, buyer.id, balance, data)
        if cash <= buffer:
            continue
        pool = [*chain_targets, *(state.rivals() if is_incumbent(buyer) else ())]
        best: tuple[float, int, CompanyState, int, DealKind] | None = None
        for target in pool:
            if (
                target.id == buyer.id
                or target.id in running
                or target.id in bought
                or not target.alive
                or not unowned(state, target.id)
                or not (target.is_chain or is_incumbent(target))
            ):
                continue
            price = round(value_cents(state, target.id, balances, balance, data) * (1 + gb.premium))
            if price <= 0 or price > cash - buffer:
                continue
            kind = deal_kind(state, buyer, target, balance, data)
            fit = gb.fit[buyer.personality or "fast_follower"].get(kind, 0.0)
            if fit <= 0:  # 41.3: buyers seek targets that supply them or share their markets
                continue
            score = fit / price
            if best is None or (score, -target.id) > (best[0], -best[1]):
                best = (score, target.id, target, price, kind)
        if best is None:
            continue
        _, _, target, price, kind = best
        share = deal_share(state, buyer, target, balance, data)
        outcome = mf.antitrust_outcome(share, balance.antitrust)
        year = turn_to_ym(turn)[0]
        deal_id = max((d.id for d in state.rival_deals), default=0) + 1
        if outcome == "blocked":
            deal = RivalDeal(
                deal_id, turn, buyer.id, target.id, price, kind, "blocked", turn, share
            )
            state = replace(state, rival_deals=(*state.rival_deals, deal))
            news.append(
                Item(
                    "blocked",
                    f"Regulators block {buyer.name}'s bid for {target.name}",
                    buyer.id,
                    target.id,
                )
            )
            continue
        if outcome == "review":
            months = int(gb.review_months.lo) + min(
                int(gb.review_months.hi - gb.review_months.lo),
                int(u_review * (gb.review_months.hi - gb.review_months.lo + 1)),
            )
            blocked = u_block < mf.block_probability(share, year, balance.antitrust)
            deal = RivalDeal(
                deal_id, turn, buyer.id, target.id, price, kind, "review", turn + months, share
            )
            if blocked:  # the outcome is drawn now and shown at the review's end (28.4)
                deal = replace(deal, share=-share)
            state = replace(state, rival_deals=(*state.rival_deals, deal))
            running |= {buyer.id, target.id}
            news.append(
                Item(
                    "review",
                    f"{buyer.name} agrees to buy {target.name}; regulators open a review",
                    buyer.id,
                    target.id,
                )
            )
            continue
        deal = RivalDeal(deal_id, turn, buyer.id, target.id, price, kind, "closed", turn, share)
        state = replace(state, rival_deals=(*state.rival_deals, deal))
        state, e, n = _close(state, deal, balance, balances)
        entries += e
        news += n
        bought |= {buyer.id, target.id}
    return state, entries, news


def _aggregate(state: GameState, company_id: int) -> bool:
    """An "other producers" company: never bought, never a buyer."""
    rec = wq.chain_record(state, company_id)
    return rec is not None and rec.is_other


def _reviews_end(
    state: GameState, balance: Balance, balances: Mapping[tuple[int, AccountCode], Cents]
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    for deal in state.rival_deals:
        if deal.status != "review" or deal.close_turn > state.turn:
            continue
        buyer, target = state.company(deal.buyer_id), state.company(deal.target_id)
        cash = account_balance(balances, buyer.id, CASH)
        if deal.share < 0 or not buyer.alive or not target.alive or cash < deal.price_cents:
            done = replace(deal, status="blocked", share=abs(deal.share))
            state = _with_deal(state, done)
            news.append(
                Item(
                    "blocked",
                    f"{buyer.name}'s purchase of {target.name} is blocked after review",
                    buyer.id,
                    target.id,
                )
            )
            continue
        done = replace(deal, status="closed")
        state = _with_deal(state, done)
        state, e, n = _close(state, done, balance, balances)
        entries += e
        news += n
    return state, entries, news


def _with_deal(state: GameState, deal: RivalDeal) -> GameState:
    return replace(
        state, rival_deals=tuple(deal if d.id == deal.id else d for d in state.rival_deals)
    )


def _close(
    state: GameState,
    deal: RivalDeal,
    balance: Balance,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    buyer, target = state.company(deal.buyer_id), state.company(deal.target_id)
    entries = [
        LedgerEntry(
            state.turn,
            buyer.id,
            f"{buyer.name}: buys {target.name} (41.3)",
            (
                LedgerLine(INVESTMENT_SUBSIDIARIES, deal.price_cents),
                LedgerLine(CASH, -deal.price_cents),
            ),
        )
    ]
    equity = sum(
        v for (cid, acc), v in balances.items() if cid == target.id and acc.startswith("3")
    )
    oid = max((o.id for o in state.ownerships), default=0) + 1
    state = with_ownership(
        state,
        Ownership(
            id=oid,
            company_id=target.id,
            owner_id=buyer.id,
            from_turn=state.turn,
            book_cents=deal.price_cents,
            equity_cents=equity,
        ),
    )
    kind: MandateKind = balance.world.groups.mandate[buyer.personality or "fast_follower"]
    mandates = tuple(m for m in state.rival_mandates if m.company_id != target.id)
    mandate = RivalMandate(target.id, buyer.id, kind, state.turn)
    state = replace(state, rival_mandates=(*mandates, mandate))
    state = with_company(state, replace(target, personality=MANDATE_PERSONALITY[kind]))
    news = [
        Item(
            "deal",
            f"{buyer.name} buys {target.name} for {format_money(deal.price_cents)} "
            f"({deal.kind}); it will run for {kind}",
            buyer.id,
            target.id,
        )
    ]
    return state, entries, news


# --- Spin-offs ---------------------------------------------------------------------------------


def subsidiaries(state: GameState, owner_id: int) -> list[Ownership]:
    return [o for o in state.ownerships if o.owner_id == owner_id and o.is_open]


def segments(state: GameState, company_ids: list[int]) -> set[str]:
    out: set[str] = set()
    for cid in company_ids:
        out |= chain_goods(state, cid) | categories(state, cid)
    return out


def _spinoffs(
    state: GameState,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    owners = sorted({m.owner_id for m in state.rival_mandates})
    for owner_id in owners:
        owner = state.company(owner_id)
        held = [o for o in subsidiaries(state, owner_id) if state.company(o.company_id).alive]
        if not held or not owner.alive or not valuation.is_listed(state, owner_id, data):
            continue
        seg = segments(state, [owner_id, *(o.company_id for o in held)])
        d = float(conglomerate_discount(len(seg), 0.0, balance))
        if d <= balance.world.spinoff_discount:
            continue
        mine = segments(state, [owner_id])
        o = min(
            held,
            key=lambda x: (len(segments(state, [x.company_id]) & mine), -x.company_id),
        )
        sub = state.company(o.company_id)
        state = with_ownership(state, replace(o, to_turn=state.turn, end_reason="spun_off"))
        state = replace(
            state, rival_mandates=tuple(m for m in state.rival_mandates if m.company_id != sub.id)
        )
        book = max(0, account_balance(balances, owner_id, INVESTMENT_SUBSIDIARIES))
        part = min(book, o.book_cents)
        if part > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    owner_id,
                    f"{owner.name}: spins off {sub.name} (41.3)",
                    (LedgerLine(COMMON_EQUITY, part), LedgerLine(INVESTMENT_SUBSIDIARIES, -part)),
                )
            )
        news.append(
            Item(
                "spinoff",
                f"{owner.name} spins off {sub.name} (a conglomerate discount of {d:.0%})",
                owner_id,
                sub.id,
            )
        )
    return state, entries, news


# --- Supply security ---------------------------------------------------------------------------


def _security(state: GameState, balance: Balance, data: GameData) -> tuple[GameState, list[Item]]:
    gb = balance.world.groups
    turn = state.turn
    rivals = [c for c in state.rivals() if is_incumbent(c) and hardware(state, c.id, data)]
    if not rivals:
        return state, []
    revenue = {c.id: max(c.mrr_history[-1] if c.mrr_history else 0, 0) for c in rivals}
    total = sum(revenue.values())
    if total <= 0:
        return state, []
    offtakes = list(state.world_offtakes)
    news: list[Item] = []
    for good in gb.security_goods:
        world = wq.world_good(state, good)
        if world is None:
            continue
        demand = wo.baseline(state, good, turn, balance, data)
        for c in rivals:
            need = gb.security_need * demand * revenue[c.id] / total
            if need <= 0:
                continue
            cover = sum(
                o.volume
                for o in offtakes
                if o.buyer_id == c.id and o.good == good and o.end_turn >= turn
            )
            if cover >= gb.security_cover * need:
                continue
            free: dict[int, float] = {}
            for f in state.world_facilities:
                if f.good == good and f.status == "live" and state.company(f.company_id).alive:
                    free[f.company_id] = free.get(f.company_id, 0.0) + f.capacity
            for o in offtakes:
                if o.good == good and o.end_turn >= turn and o.seller_id in free:
                    free[o.seller_id] -= o.volume
            if not free:
                continue
            seller = max(free, key=lambda k: (free[k], -k))
            volume = min(gb.security_target * need - cover, max(0.0, free[seller]))
            if volume <= 0:
                continue
            oid = max((o.id for o in offtakes), default=0) + 1
            offtakes.append(
                WorldOfftake(
                    oid, c.id, seller, good, volume, turn, turn + gb.security_years * MONTHS - 1
                )
            )
            news.append(
                Item(
                    "offtake",
                    f"{c.name} signs a {gb.security_years}-year {wd.label(data, good)} offtake "
                    f"with {state.company(seller).name}",
                    c.id,
                    seller,
                    good=good,
                )
            )
    return replace(state, world_offtakes=tuple(offtakes)), news

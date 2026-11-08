"""Capital actions (docs/formulas.md 31.5): selling a stake in a subsidiary, buying out its
minorities, a carve-out, a spin-off, stakes in listed rivals and corporate venture
investments. Prices come from public numbers only: a listed company's market cap, else the
midpoint of its displayed value range (28.1; 31.10 never shows a true value). Every cash
movement is a balanced entry; a stake change keeps control and so is an equity transaction
on the owner's books (no gain or loss), and the holding's basis is rebased.

The founder takes these as Chair (the holding company once formed, else the player's company
pays and is paid)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GroupRuleError
from tst.sim.finance.captable import founder_bp
from tst.sim.finance.models import CapEntry
from tst.sim.group import formulas as gf
from tst.sim.group.draws import group_draws
from tst.sim.group.models import FULL_STAKE_BP, GroupListing, Ownership, PersonalStake, Stake
from tst.sim.group.ownership import carrying_cents, equity_cents
from tst.sim.group.stakes import account_of
from tst.sim.group.subsidiaries import is_subsidiary
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    FINANCIAL_INVESTMENTS,
    INVESTMENT_SUBSIDIARIES,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna import valuation
from tst.sim.mna.models import RivalListing
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    group_listing,
    holding_of,
    listed_id,
    owner_at,
    owner_of,
    rival_listing,
    with_company,
    with_ownership,
    with_rival_listing,
    with_stake,
)

LINK: Final = "group"
BASE_SHARES = 10_000_000  # tunable-exempt: a subsidiary's shares when its cap table opens
FIRM_TAG = 2  # tunable-exempt: stream group sub-key of a stake sale's buyer


@dataclass(frozen=True, slots=True)
class SellStake:
    """Sell `stake_bp` of a subsidiary to investors (31.5); control stays (51% or more)."""

    actor_id: int
    company_id: int
    stake_bp: int
    kind: Literal["sell_stake"] = "sell_stake"


@dataclass(frozen=True, slots=True)
class BuyOutMinorities:
    actor_id: int
    company_id: int
    kind: Literal["buy_out_minorities"] = "buy_out_minorities"


@dataclass(frozen=True, slots=True)
class CarveOut:
    """List `stake_bp` (10-40%) of a subsidiary (31.5); the group keeps control."""

    actor_id: int
    company_id: int
    stake_bp: int
    kind: Literal["carve_out"] = "carve_out"


@dataclass(frozen=True, slots=True)
class SpinOff:
    """Give a subsidiary's shares to the holding company's shareholders (31.5), keeping
    `keep_bp` (at most 19.9%)."""

    actor_id: int
    company_id: int
    keep_bp: int = 0
    kind: Literal["spin_off"] = "spin_off"


@dataclass(frozen=True, slots=True)
class BuyStake:
    """Buy a listed rival's shares on the market up to `to_bp` (31.5)."""

    actor_id: int
    company_id: int
    to_bp: int
    kind: Literal["buy_stake"] = "buy_stake"


@dataclass(frozen=True, slots=True)
class VentureInvest:
    """Invest `cents` in a startup's round (31.5, 15.4) for 5-25% at its post-money value."""

    actor_id: int
    company_id: int
    cents: int
    kind: Literal["venture_invest"] = "venture_invest"


type CapitalAction = SellStake | BuyOutMinorities | CarveOut | SpinOff | BuyStake | VentureInvest
CAPITAL_ACTIONS = (SellStake, BuyOutMinorities, CarveOut, SpinOff, BuyStake, VentureInvest)


def value_cents(
    state: GameState, company_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> int:
    """A company's public value (28.1): its market cap if listed, else the midpoint of its
    displayed value range."""
    cap = valuation.market_cap_cents(state, company_id, balances, balance, data)
    if cap is not None:
        return cap
    low, high = valuation.value_range_cents(state, company_id, balances, balance, data)
    return (low + high) // 2


def _held(state: GameState, company_id: int) -> Ownership:
    if not is_subsidiary(state, company_id):
        raise GroupRuleError("only a subsidiary run by its own CEO can do that")
    held = owner_at(state, company_id)
    assert held is not None
    return held


def _cap_table(state: GameState, company_id: int, owner: Ownership) -> GameState:
    """A subsidiary's cap table opens the first time outsiders buy in (31.4): its owner's
    entry for every share."""
    if state.company_cap(company_id):
        return state
    entry = CapEntry(
        id=max((e.id for e in state.cap_entries), default=0) + 1,
        company_id=company_id,
        holder_kind="group",
        share_class="common",
        shares=round(Fraction(owner.stake_at(), FULL_STAKE_BP) * BASE_SHARES),
        acquired_turn=owner.from_turn,
        name=state.company(owner.owner_id).name,
    )
    rest = BASE_SHARES - entry.shares
    out = replace(state, cap_entries=(*state.cap_entries, entry))
    if rest:
        out = _add_holder(out, company_id, rest, "group", None, "Outside shareholders")
    return out


def _add_holder(
    state: GameState, company_id: int, shares: int, kind: str, firm: str | None, name: str | None
) -> GameState:
    for e in state.company_cap(company_id):
        if e.holder_kind == kind and e.firm == firm and e.name == name:
            moved = replace(e, shares=e.shares + shares)
            return replace(
                state, cap_entries=tuple(moved if x.id == e.id else x for x in state.cap_entries)
            )
    entry = CapEntry(
        id=max((e.id for e in state.cap_entries), default=0) + 1,
        company_id=company_id,
        holder_kind=kind,  # type: ignore[arg-type]
        share_class="common",
        shares=shares,
        acquired_turn=state.turn,
        firm=firm,
        name=name,
    )
    return replace(state, cap_entries=(*state.cap_entries, entry))


def _owner_shares(state: GameState, company_id: int, owner_name: str, delta: int) -> GameState:
    for e in state.company_cap(company_id):
        if e.holder_kind == "group" and e.name == owner_name:
            moved = replace(e, shares=e.shares + delta)
            return replace(
                state, cap_entries=tuple(moved if x.id == e.id else x for x in state.cap_entries)
            )
    return state


def _sell(
    state: GameState,
    held: Ownership,
    sell_bp: int,
    price: int,
    memo: str,
    balances: LedgerBalances,
    data: GameData,
) -> tuple[GameState, LedgerEntry]:
    """The owner sells `sell_bp` of the company for `price` (31.5): its investment falls by
    that share, the difference is equity (control is kept); the holding is rebased."""
    stake = held.stake_at()
    carrying = carrying_cents(held, balances, data)
    out = round(Fraction(sell_bp, stake) * carrying)
    lines = [LedgerLine(CASH, price), LedgerLine(INVESTMENT_SUBSIDIARIES, -out)]
    if price - out:
        lines.append(LedgerLine(COMMON_EQUITY, -(price - out)))
    entry = LedgerEntry(state.turn, held.owner_id, memo, tuple(x for x in lines if x.amount))
    rebase = (
        state.turn,
        stake - sell_bp,
        carrying - out,
        equity_cents(balances, held.company_id, data),
    )
    state = with_ownership(state, replace(held, rebases=(*held.rebases, rebase)))
    return state, entry


def sell_stake(
    state: GameState,
    action: SellStake,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    gb = balance.group
    held = _held(state, action.company_id)
    stake = held.stake_at()
    floor = FULL_STAKE_BP - round(exact(gb.max_sale) * FULL_STAKE_BP)
    if action.stake_bp <= 0 or stake - action.stake_bp < floor:
        raise GroupRuleError(
            f"the group keeps control: it can hold no less than {floor / 100:.0f}%"
        )
    cid = action.company_id
    value = value_cents(state, cid, balances, balance, data)
    listed = valuation.is_listed(state, cid, data)
    price = gf.stake_price_cents(value, action.stake_bp, 0.0 if listed else gb.private_discount)
    company = state.company(cid)
    gen = group_draws(rng, state.turn, company, FIRM_TAG)
    firm = data.investors[int(gen.integers(0, len(data.investors)))]
    state = _cap_table(state, cid, held)
    sold = round(Fraction(action.stake_bp, FULL_STAKE_BP) * BASE_SHARES)
    owner_name = state.company(held.owner_id).name
    state = _owner_shares(state, cid, owner_name, -sold)
    state = _add_holder(state, cid, sold, "firm", firm.key, None)
    state, entry = _sell(
        state,
        held,
        action.stake_bp,
        price,
        f"Sold {action.stake_bp / 100:.0f}% of {company.name}",
        balances,
        data,
    )
    log = inbox_item(
        state.turn,
        state.player.id,
        "stake_sold",
        link_kind=LINK,
        company=company.name,
        pct=f"{action.stake_bp / 100:.0f}%",
        buyer=firm.name,
        price_cents=price,
    )
    return Outcome(state, (entry,), (log,))


def buy_out(
    state: GameState,
    action: BuyOutMinorities,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    held = _held(state, action.company_id)
    minority = FULL_STAKE_BP - held.stake_at()
    if minority <= 0:
        raise GroupRuleError("the group already owns all of it")
    cid = action.company_id
    value = value_cents(state, cid, balances, balance, data)
    price = gf.buyout_cents(value, minority, balance.group.buyout_premium)
    owner = held.owner_id
    if account_balance(balances, owner, CASH) < price:
        raise GroupRuleError(f"{state.company(owner).name} does not have the cash")
    carrying = carrying_cents(held, balances, data)
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=owner,
        memo=f"Bought out the minorities of {state.company(cid).name}",
        debit=INVESTMENT_SUBSIDIARIES,
        credit=CASH,
        amount=price,
    )
    rebase = (state.turn, FULL_STAKE_BP, carrying + price, equity_cents(balances, cid, data))
    state = with_ownership(state, replace(held, rebases=(*held.rebases, rebase)))
    # the cap table is the owner's again; a carve-out is delisted
    owner_name = state.company(owner).name
    others = sum(
        e.shares
        for e in state.company_cap(cid)
        if not (e.holder_kind == "group" and e.name == owner_name)
    )
    state = replace(
        state,
        cap_entries=tuple(
            e
            for e in state.cap_entries
            if e.company_id != cid or (e.holder_kind == "group" and e.name == owner_name)
        ),
    )
    state = _owner_shares(state, cid, owner_name, others)
    state = replace(
        state,
        group_listings=tuple(x for x in state.group_listings if x.company_id != cid),
        rival_listings=tuple(x for x in state.rival_listings if x.company_id != cid),
    )
    log = inbox_item(
        state.turn,
        state.player.id,
        "minorities_bought_out",
        link_kind=LINK,
        company=state.company(cid).name,
        price_cents=price,
    )
    return Outcome(state, (entry,), (log,))


def carve_out(
    state: GameState, action: CarveOut, balances: LedgerBalances, balance: Balance, data: GameData
) -> Outcome:
    gb = balance.group
    low, high = (round(exact(x) * FULL_STAKE_BP) for x in gb.carve_out)
    if not low <= action.stake_bp <= high:
        raise GroupRuleError(f"a carve-out lists {low / 100:.0f}-{high / 100:.0f}% of the company")
    cid = action.company_id
    held = _held(state, cid)
    if group_listing(state, cid) is not None:
        raise GroupRuleError("it is already listed")
    floor = FULL_STAKE_BP - round(exact(gb.max_sale) * FULL_STAKE_BP)
    if held.stake_at() - action.stake_bp < floor:
        raise GroupRuleError(f"the group keeps control: no less than {floor / 100:.0f}%")
    value = value_cents(state, cid, balances, balance, data)
    price = gf.stake_price_cents(value, action.stake_bp)
    state = _cap_table(state, cid, held)
    sold = round(Fraction(action.stake_bp, FULL_STAKE_BP) * BASE_SHARES)
    owner_name = state.company(held.owner_id).name
    state = _owner_shares(state, cid, owner_name, -sold)
    state = _add_holder(state, cid, sold, "group", None, "Public float")
    company = state.company(cid)
    state, entry = _sell(
        state, held, action.stake_bp, price, f"Carve-out of {company.name}", balances, data
    )
    state = replace(
        state,
        group_listings=(
            *state.group_listings,
            GroupListing(cid, state.turn, "carve_out", BASE_SHARES),
        ),
    )
    if rival_listing(state, cid) is None:
        state = with_rival_listing(state, RivalListing(cid))
    log = inbox_item(
        state.turn,
        state.player.id,
        "carve_out_listed",
        link_kind=LINK,
        company=company.name,
        pct=f"{action.stake_bp / 100:.0f}%",
        price_cents=price,
    )
    return Outcome(state, (entry,), (log,))


def spin_off(
    state: GameState, action: SpinOff, balances: LedgerBalances, balance: Balance, data: GameData
) -> Outcome:
    gb = balance.group
    held_by = holding_of(state)
    if held_by is None:
        raise GroupRuleError("a spin-off needs a listed holding company to give the shares to")
    cid = action.company_id
    held = _held(state, cid)
    if held.owner_id != listed_id(state):
        raise GroupRuleError("only a direct subsidiary of the holding company can be spun off")
    keep_max = round(exact(gb.spin_keep) * FULL_STAKE_BP)
    if not 0 <= action.keep_bp <= min(keep_max, held.stake_at()):
        raise GroupRuleError(f"the group may keep at most {keep_max / 100:.1f}%")
    stake = held.stake_at()
    carrying = carrying_cents(held, balances, data)
    kept = round(Fraction(action.keep_bp, stake) * carrying)
    company = state.company(cid)
    lines = [
        LedgerLine(INVESTMENT_SUBSIDIARIES, -carrying),
        LedgerLine(FINANCIAL_INVESTMENTS, kept),
        LedgerLine(COMMON_EQUITY, carrying - kept),  # a distribution to shareholders
    ]
    entry = LedgerEntry(
        state.turn,
        held.owner_id,
        f"Spin-off of {company.name}",
        tuple(x for x in lines if x.amount) or (LedgerLine(CASH, 0),) * 2,
    )
    state = with_ownership(state, replace(held, to_turn=state.turn, end_reason="spun_off"))
    state = with_company(state, replace(company, parent_id=None))
    state = replace(
        state,
        mandates=tuple(m for m in state.mandates if m.company_id != cid),
        group_pitches=tuple(
            replace(p, status="lapsed", resolved_turn=state.turn)
            if p.company_id == cid and p.status == "pending"
            else p
            for p in state.group_pitches
        ),
        group_listings=(
            *tuple(x for x in state.group_listings if x.company_id != cid),
            GroupListing(cid, state.turn, "spin_off", BASE_SHARES),
        ),
    )
    if rival_listing(state, cid) is None:
        state = with_rival_listing(state, RivalListing(cid))
    if action.keep_bp:
        state = with_stake(
            state, Stake(0, held.owner_id, cid, action.keep_bp, kept, kept, state.turn, "retained")
        )
    # the founder's pro-rata part of what was given out, in their own name (31.5)
    founder = state.founder_of(held.owner_id)
    given = stake - action.keep_bp
    mine = (
        round(Fraction(founder_bp(state, held.owner_id), FULL_STAKE_BP) * given) if founder else 0
    )
    if founder is not None and mine > 0:
        state = replace(
            state,
            personal_stakes=(
                *state.personal_stakes,
                PersonalStake(founder.id, cid, mine, state.turn),
            ),
        )
    log = inbox_item(
        state.turn,
        state.player.id,
        "spun_off",
        link_kind=LINK,
        company=company.name,
        kept=f"{action.keep_bp / 100:.1f}%",
        yours=f"{mine / 100:.2f}%",
    )
    entries = (entry,) if any(x.amount for x in entry.lines) else ()
    return Outcome(state, entries, (log,))


def _stake_of(state: GameState, owner: int, company_id: int) -> Stake | None:
    return next(
        (
            x
            for x in state.stakes
            if x.is_open and x.owner_id == owner and x.company_id == company_id
        ),
        None,
    )


def buy_stake(
    state: GameState, action: BuyStake, balances: LedgerBalances, balance: Balance, data: GameData
) -> Outcome:
    gb = balance.group
    owner = listed_id(state)
    cid = action.company_id
    company = state.company(cid)
    if (
        company.is_player
        or company.parent_id is not None
        or not valuation.is_listed(state, cid, data)
    ):
        raise GroupRuleError("you can buy on the market only in a listed rival")
    if owner_of(state, cid) == owner:
        raise GroupRuleError("it is already the group's")
    stake = _stake_of(state, owner, cid)
    have = stake.stake_bp if stake is not None else 0
    offer_at = round(exact(gb.offer_at) * FULL_STAKE_BP)
    top = min(round(exact(gb.stake_max) * FULL_STAKE_BP), offer_at)
    if have >= offer_at:
        raise GroupRuleError(
            f"at {offer_at / 100:.0f}% the group must make a full offer (Deals) or buy no more"
        )
    if not have < action.to_bp <= top:
        raise GroupRuleError(f"buy up to {top / 100:.0f}% on the market; from there a full offer")
    cap = valuation.market_cap_cents(state, cid, balances, balance, data)
    assert cap is not None
    price = gf.market_stake_cents(cap, have, action.to_bp, gb.stake_impact)
    if account_balance(balances, owner, CASH) < price:
        raise GroupRuleError(f"{state.company(owner).name} does not have the cash")
    new = Stake(
        stake.id if stake else 0,
        owner,
        cid,
        action.to_bp,
        (stake.cost_cents if stake else 0) + price,
        (stake.carrying_cents if stake else 0) + price,
        stake.from_turn if stake else state.turn,
        "market",
        disclosed_bp=stake.disclosed_bp if stake else 0,
    )
    entries: list[LedgerEntry] = []
    target = account_of(new, balance)
    if stake is not None and account_of(stake, balance) != target:  # 20%: to the equity method
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=owner,
                memo=f"{company.name} is now an associate",
                debit=target,
                credit=account_of(stake, balance),
                amount=stake.carrying_cents,
            )
        )
    entries.append(
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=owner,
            memo=f"Shares of {company.name}",
            debit=target,
            credit=CASH,
            amount=price,
        )
    )
    logs: list[LogItem] = []
    for line in gb.disclosures:
        bp = round(exact(line) * FULL_STAKE_BP)
        if have < bp <= action.to_bp:
            logs.append(
                inbox_item(
                    state.turn,
                    state.player.id,
                    "stake_disclosed",
                    link_kind=LINK,
                    company=company.name,
                    pct=f"{bp / 100:.0f}%",
                )
            )
            new = replace(new, disclosed_bp=bp)
    state = with_stake(state, new)
    return Outcome(state, tuple(entries), tuple(logs))


def venture(
    state: GameState,
    action: VentureInvest,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    gb = balance.group
    owner = listed_id(state)
    cid = action.company_id
    company = state.company(cid)
    if (
        not company.is_startup
        or not company.alive
        or company.parent_id is not None
        or valuation.is_listed(state, cid, data)
    ):
        raise GroupRuleError("corporate venture invests in a private startup's round")
    if action.cents <= 0 or account_balance(balances, owner, CASH) < action.cents:
        raise GroupRuleError("not enough cash for that")
    pre = value_cents(state, cid, balances, balance, data)
    old = _stake_of(state, owner, cid)
    bp = round(Fraction(action.cents, pre + action.cents) * FULL_STAKE_BP)
    total = bp + (round(Fraction(old.stake_bp) * pre / (pre + action.cents)) if old else 0)
    low, high = (round(exact(x) * FULL_STAKE_BP) for x in gb.venture)
    if not low <= total <= high:
        raise GroupRuleError(
            f"a venture stake is {low / 100:.0f}-{high / 100:.0f}% of the startup at its "
            "post-money value"
        )
    new = Stake(
        old.id if old else 0,
        owner,
        cid,
        total,
        (old.cost_cents if old else 0) + action.cents,
        (old.carrying_cents if old else 0) + action.cents,
        old.from_turn if old else state.turn,
        "venture",
    )
    account = account_of(new, balance)
    entries = [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=owner,
            memo=f"Venture investment in {company.name}",
            debit=account,
            credit=CASH,
            amount=action.cents,
        ),
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=cid,
            memo=f"Funding round: {state.company(owner).name}",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=action.cents,
        ),
    ]
    if old is not None and account_of(old, balance) != account:
        entries.insert(
            0,
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=owner,
                memo=f"{company.name} is now an associate",
                debit=account,
                credit=account_of(old, balance),
                amount=old.carrying_cents,
            ),
        )
    state = with_stake(state, new)
    # information rights: its key people as ranges, by the scouting rules (28.2's diligence)
    from tst.sim.rivals.ceo_knowledge import learn_of_ceo

    for e in state.staff(cid):
        state = learn_of_ceo(state, e.person_id, "rival_diligence", rng, balance, data)
    log = inbox_item(
        state.turn,
        state.player.id,
        "venture_invested",
        link_kind=LINK,
        company=company.name,
        amount_cents=action.cents,
        pct=f"{total / 100:.1f}%",
    )
    return Outcome(state, tuple(entries), (log,))

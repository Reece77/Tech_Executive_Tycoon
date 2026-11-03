"""The IPO flow, the Stock tab and the CEO seat (M13, docs/formulas.md 25.8). Reads state
and published numbers only: the book as a word, never its draw; analysts' targets, never V_f;
the share price, never the sentiment behind it or the triggers' thresholds."""

from __future__ import annotations

from collections.abc import Sequence

from tst.api.schemas.public import (
    AnalystOut,
    BankOut,
    CapitalOut,
    CeoCandidateOut,
    CeoDecisionOut,
    CeoOut,
    DriverOut,
    GuidanceRowOut,
    IpoOut,
    IpoStepOut,
    NextGuidanceOut,
    PriceOptionOut,
    PublicOut,
    SharePointOut,
    StockOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.finance import macro
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.ledger import LedgerBalances
from tst.sim.markets_public import capital, ipo
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.config import CEO_SCOPES
from tst.sim.markets_public.describe import consensus_rating
from tst.sim.markets_public.models import Listing, PublicCompany, ShareMonth
from tst.sim.markets_public.public import consensus, guidance_problem, outstanding_shares
from tst.sim.org.executives import level_allowed
from tst.sim.state import GameState, ceo_of, listing_of, public_of

PCT = 100
BP = 10_000
QUARTER = 3


def quarter_label(turn: int) -> str:
    year, month = turn_to_ym(turn)
    return f"Q{(month - 1) // QUARTER + 1} {year}"


def _reputation(quality: float) -> str:
    if quality > 1.0:
        return "a premium name: prices higher"
    if quality < 1.0:
        return "cheaper, and prices lower"
    return "a solid name"


def _representative_demand(word: str, data: LoadedData) -> float:
    """The middle of the word's band: what the player can infer from the word (25.8)."""
    ib = data.balance.ipo
    lo = ib.demand.bounds.lo
    for band in ib.demand_words:
        if band.word == word:
            return (lo + band.below) / 2
        lo = band.below
    return lo * (1 + ib.raise_pct)


def _first_day_words(r: float) -> str:
    if r >= 0.05:  # tunable-exempt: words for an estimate
        return f"likely to rise, about {r:+.0%} (est.)"
    if r <= -0.05:  # tunable-exempt: words for an estimate
        return f"likely to fall, about {r:+.0%} (est.)"
    return "likely flat (est.)"


def _steps(listing: Listing, data: LoadedData) -> list[IpoStepOut]:
    order = ["hired", "filing", "roadshow", "pricing", "priced", "listed"]
    at = order.index(listing.status) if listing.status in order else len(order)
    bank = data.game_data.bank(listing.bank).name

    def state_of(index: int) -> str:
        if listing.status == "pulled":
            return "done" if index < 3 else "next"  # tunable-exempt: steps before pricing
        return "done" if at > index else ("now" if at == index else "next")

    roadshow = f"{listing.ambition or '...'} ambition, sell {listing.share_choice or '...'}, " + (
        "dual-class"
        if listing.dual_class
        else "one class"
        if listing.dual_class is not None
        else "..."
    )
    filing = (
        "restated a metric (a month later)"
        if listing.filed_late
        else "filed on time"
        if listing.filed_late is not None
        else "the regulator's questions"
    )
    return [
        IpoStepOut(
            key="banks",
            label="Banks hired",
            state="done",
            detail=f"{bank}, {format_turn(listing.hired_turn)}",
        ),
        IpoStepOut(key="filing", label="S-1 filed", state=state_of(1), detail=filing),
        IpoStepOut(key="roadshow", label="Roadshow", state=state_of(2), detail=roadshow),
        IpoStepOut(
            key="pricing", label="Pricing", state=state_of(3), detail="the book and the price"
        ),
        IpoStepOut(
            key="listing",
            label="Listing day",
            state=state_of(4),
            detail="the month after pricing is set",
        ),
    ]


def ipo_out(state: GameState, company_id: int, data: LoadedData) -> IpoOut | None:
    listing = listing_of(state, company_id)
    if listing is None:
        return None
    ib = data.balance.ipo
    bank = data.game_data.bank(listing.bank)
    word = pf.demand_word(listing.demand, ib) if listing.demand is not None else None
    shares_before = listing.shares_before or fd_shares(state, company_id)
    share = ib.share_sold[listing.share_choice] if listing.share_choice else None
    new = listing.new_shares or (pf.new_shares(shares_before, share) if share else 0)
    after = shares_before + new
    price = listing.price_cents or None
    company = state.company(company_id)
    arr = (company.mrr_history[-1] if company.mrr_history else 0) * 12  # tunable-exempt
    cap = (price or 0) * after
    founder = state.founder_of(company_id)
    stake = person_shares(state, company_id, founder.id) if founder else 0
    options: list[PriceOptionOut] = []
    if listing.status == "pricing" and price and word is not None:
        d = _representative_demand(word, data)
        strong = listing.demand is not None and listing.demand >= ib.raise_min_demand
        for choice, label, factor, available, note in (
            ("range", "Price at the suggestion", 1.0, True, ""),
            (
                "raise",
                "Raise 10%",
                1 + ib.raise_pct,
                strong,
                "" if strong else "only with strong demand",
            ),
            (
                "cut",
                "Cut 15%",
                1 - ib.cut_pct,
                not strong,
                "" if not strong else "the book does not need it",
            ),
        ):
            p = round(price * factor)
            gross = p * new
            r = pf.first_day_return(
                d, ib.ambition[listing.ambition or "middle"] * factor, ib.first_day
            )
            options.append(
                PriceOptionOut(
                    choice=choice,
                    label=label,
                    price_cents=p,
                    gross_cents=gross,
                    net_cents=gross - pf.fee_cents(gross, bank.fee),
                    first_day=_first_day_words(r),
                    available=available,
                    note=note,
                )
            )
        owed = round(pf.fee_cents(price * new, bank.fee) * ib.pull_fee_share)
        options.append(
            PriceOptionOut(
                choice="pull",
                label="Pull the IPO",
                price_cents=0,
                gross_cents=0,
                net_cents=-owed,
                first_day="no listing; board confidence falls",
                available=True,
                note=f"fees of ${owed / PCT:,.0f} are owed",
            )
        )
    return IpoOut(
        status=listing.status,
        bank=bank.name,
        fee_pct=bank.fee * PCT,
        hired=format_turn(listing.hired_turn),
        steps=_steps(listing, data),
        ambition=listing.ambition,
        share_sold_pct=share * PCT if share else None,
        dual_class=listing.dual_class,
        demand=word,
        price_cents=price,
        new_shares=new,
        shares_after=after,
        implied_cap_cents=cap,
        price_to_sales=round(cap / arr, 1) if arr and cap else None,
        stake_pct_after=stake * PCT / after if after else 0.0,
        stake_value_cents=stake * (listing.close_cents or price or 0),
        options=options,
        listed=format_turn(listing.listed_turn) if listing.listed_turn is not None else None,
        first_day_pct=listing.first_day_return * PCT
        if listing.first_day_return is not None
        else None,
        pulled=format_turn(listing.pulled_turn) if listing.pulled_turn is not None else None,
    )


def _drivers(
    state: GameState, company_id: int, public: PublicCompany, data: LoadedData
) -> list[DriverOut]:
    """Share price drivers as words (25.8): never the formula's terms."""
    company = state.company(company_id)
    history = company.mrr_history
    growth = (
        history[-1] / history[-13] - 1 if len(history) > 12 and history[-13] > 0 else 0.0
    )  # tunable-exempt
    ops = company.op_history[-12:]  # tunable-exempt: a year
    revs = history[-len(ops) :] if ops else ()
    margin = sum(ops) / sum(revs) if ops and sum(revs) > 0 else 0.0
    rate = macro.base_rate(state, data.game_data)
    climate = macro.venture_climate(state, data.game_data)

    def word(x: float, hi: float, lo: float) -> str:
        return "lifts" if x >= hi else "weighs on" if x <= lo else "neutral"

    recent = public.results[-1] if public.results else None
    return [
        DriverOut(
            label="Revenue growth",
            effect=word(growth, 0.3, 0.1),
            detail=f"{growth:+.0%} over the year",
        ),
        DriverOut(
            label="Operating margin",
            effect=word(margin, 0.1, -0.05),
            detail=f"{margin:+.0%} over the year",
        ),
        DriverOut(
            label="Interest rates", effect=word(-rate, -1.5, -4.0), detail=f"base rate {rate:.2f}%"
        ),
        DriverOut(
            label="Market mood",
            effect=word(climate, 1.15, 0.9),
            detail="the venture and growth-stock climate",
        ),
        DriverOut(
            label="Last earnings",
            effect={"beat": "lifts", "miss": "weighs on"}.get(recent or "", "neutral"),
            detail=f"last quarter: {recent}" if recent else "no report yet",
        ),
    ]


def stock_out(
    state: GameState,
    company_id: int,
    months: Sequence[ShareMonth],
    data: LoadedData,
) -> StockOut | None:
    public = public_of(state, company_id)
    if public is None:
        return None
    b = data.balance
    shares = fd_shares(state, company_id)
    founder = state.founder_of(company_id)
    stake = person_shares(state, company_id, founder.id) if founder else 0
    ordered = sorted(months, key=lambda m: m.turn)
    prev = ordered[-2].price_cents if len(ordered) > 1 else None
    names = b.public.analysts.firms
    analysts = [
        AnalystOut(firm=names[a.index], rating=a.rating, target_cents=a.target_cents)
        for a in public.analysts
    ]
    targets = [a.target_cents for a in public.analysts]
    rows = [
        GuidanceRowOut(
            quarter=quarter_label(g.quarter_turn),
            by_player=g.by_player,
            revenue_cents=g.revenue_cents,
            margin_pct=g.margin_bp / PCT,
            actual_revenue_cents=g.actual_revenue_cents,
            actual_margin_pct=g.actual_margin_bp / PCT if g.actual_margin_bp is not None else None,
            result=g.result,
            price_before_cents=g.price_before_cents,
            price_after_cents=g.price_after_cents,
        )
        for g in sorted(state.guidance, key=lambda g: g.quarter_turn)
        if g.company_id == company_id
    ]
    start = ipo.quarter_start(state.turn)
    upcoming = start if state.turn == start else start + QUARTER
    rev, margin = consensus(state, company_id)
    problem = guidance_problem(state, company_id, rev, b)
    current = next(
        (g for g in state.guidance if g.company_id == company_id and g.quarter_turn == state.turn),
        None,
    )
    next_guidance = NextGuidanceOut(
        quarter=quarter_label(upcoming),
        can_set=problem is None,
        problem=problem,
        consensus_revenue_cents=rev,
        consensus_margin_pct=margin / PCT,
        set_revenue_cents=current.revenue_cents if current and current.by_player else None,
        set_margin_pct=current.margin_bp / PCT if current and current.by_player else None,
        band_pct=b.public.earnings.guidance_band * PCT,
        energy=b.public.earnings.guidance_energy,
        hint=(
            "Guiding above the consensus lifts nothing now but makes a miss likelier; "
            "a miss cuts the price and the board's confidence."
        ),
    )
    cb = b.public.capital
    float_shares = sum(
        e.shares
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == ipo.PUBLIC_HOLDERS
    )
    rating = consensus_rating(public)
    board_line = {
        "buy": "Analysts rate the stock a buy: directors are more patient.",
        "sell": "Analysts rate the stock a sell: directors are less patient.",
    }.get(rating or "", "Directors' patience follows the analysts' consensus.")
    board_line += (
        " Each beat lifts every director's confidence; each miss cuts it, and two in a row "
        "cut it further."
    )
    return StockOut(
        ticker=public.ticker,
        price_cents=public.price_cents,
        change_pct=(public.price_cents / prev - 1) * PCT if prev else None,
        market_cap_cents=public.price_cents * shares,
        shares=shares,
        listing_price_cents=public.listing_price_cents,
        listed=format_turn(public.listed_turn),
        dual_class=public.dual_class,
        stake_shares=stake,
        stake_pct=stake * PCT / shares if shares else 0.0,
        stake_value_cents=stake * public.price_cents,
        history=[
            SharePointOut(
                turn=m.turn,
                label=format_turn(m.turn),
                price_cents=m.price_cents,
                market_cap_cents=m.market_cap_cents,
                mark=m.mark,
            )
            for m in ordered
        ],
        analysts=analysts,
        buys=sum(1 for a in public.analysts if a.rating == "buy"),
        holds=sum(1 for a in public.analysts if a.rating == "hold"),
        sells=sum(1 for a in public.analysts if a.rating == "sell"),
        average_target_cents=round(sum(targets) / len(targets)) if targets else None,
        guidance=rows,
        next_guidance=next_guidance,
        capital=CapitalOut(
            buyback_price_cents=capital.buyback_price_cents(public, b),
            buyback_max_shares=min(int(shares * cb.buyback_max_share), float_shares),
            buyback_energy=cb.buyback_energy,
            dividend_declared_cents=public.dividend_cents,
            dividend_energy=cb.dividend_energy,
            shares_outstanding=outstanding_shares(state, company_id),
            secondary_price_cents=round(public.price_cents * (1 - cb.secondary_discount)),
            secondary_max_shares=int(shares * cb.secondary_max_share),
            secondary_fee_pct=cb.secondary_fee * PCT,
            secondary_energy=cb.secondary_energy,
        ),
        board_line=board_line,
        drivers=_drivers(state, company_id, public, data),
    )


def ceo_out(state: GameState, company_id: int, data: LoadedData) -> CeoOut:
    b = data.balance
    company = state.company(company_id)
    ceo = ceo_of(state, company_id)
    seat_open = company.stage >= b.ceo.min_stage
    problem = None if seat_open else "A CEO can be appointed once the company is public."
    candidates = []
    if seat_open and ceo is None:
        for e in state.staff(company_id):
            person = state.person(e.person_id)
            if person.is_founder or e.status != "active" or not level_allowed(e.level, b):
                continue
            role = data.game_data.role(e.role).label if e.role != "founder" else e.role
            candidates.append(
                CeoCandidateOut(
                    person_id=person.id,
                    name=f"{person.first_name} {person.last_name}",
                    role=role,
                    level=e.level,
                )
            )
    holder = state.person(ceo.person_id) if ceo else None
    decisions = [
        CeoDecisionOut(
            id=d.id,
            turn=d.turn,
            label=format_turn(d.turn),
            scope=d.scope,
            text=d.text,
            mistake=d.mistake,
            can_override=bool(d.undo) and d.overridden_turn is None and ceo is not None,
            overridden=d.overridden_turn is not None,
        )
        for d in sorted(state.ceo_decisions, key=lambda d: -d.id)
        if d.company_id == company_id
    ]
    return CeoOut(
        seat_open=seat_open,
        problem=problem,
        person_id=ceo.person_id if ceo else None,
        name=f"{holder.first_name} {holder.last_name}" if holder else None,
        since=format_turn(ceo.since_turn) if ceo else None,
        scopes=list(ceo.scopes) if ceo else [],
        all_scopes=list(CEO_SCOPES),
        decisions=decisions,
        candidates=candidates,
        appoint_energy=b.ceo.appoint_energy,
        override_energy=b.ceo.override_energy,
        chair_energy=b.ceo.chair_energy,
    )


def public_out(
    state: GameState,
    months: Sequence[ShareMonth],
    data: LoadedData,
    balances: LedgerBalances | None = None,
) -> PublicOut:
    company_id = state.player.id
    b = data.balance
    problem = ipo.eligibility_problem(state, company_id, b)
    return PublicOut(
        stage=state.player.stage,
        eligible=problem is None,
        problem=problem,
        banks=[
            BankOut(
                key=bank.key,
                name=bank.name,
                fee_pct=bank.fee * PCT,
                reputation=_reputation(bank.quality),
            )
            for bank in data.game_data.banks
        ],
        hire_energy=b.ipo.hire_energy,
        ipo=ipo_out(state, company_id, data),
        stock=stock_out(state, company_id, months, data),
        ceo=ceo_out(state, company_id, data),
    )

"""What achievements are judged on (M25 section 2): facts about the player's company read
from committed public state and stored month-end snapshots. Each field is a condition kind in
achievements.yaml. Nothing here is a hidden value: a listed company's market cap is its share
price times its shares, never the hidden fair value."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.db import repository
from tst.db.models import TurnSnapshotRow
from tst.loader import LoadedData
from tst.profile.kinds import Facts
from tst.sim.state import GameState, company_cash

FIRST_YEAR = 12  # tunable-exempt: months in a company's first year
INTEGRATION_YEAR = 12  # tunable-exempt: an integration is clean after a year with nobody gone


def _first_year_profitable(session: Session, company: int, founded: int) -> bool:
    rows = session.scalars(
        select(TurnSnapshotRow).where(
            TurnSnapshotRow.company_id == company,
            TurnSnapshotRow.turn >= founded,
            TurnSnapshotRow.turn < founded + FIRST_YEAR,
        )
    )
    return any(
        int(r.kpis.get("mrr_cents") or 0) > 0 and int(r.kpis.get("monthly_burn_cents") or 0) == 0
        for r in rows
    )


def _datacentre_use(state: GameState, company: int, data: LoadedData) -> float:
    facilities = state.company_facilities(company)
    if not facilities:
        return 0.0
    from tst.sim.facilities import compute

    b, d = data.balance, data.game_data
    alloc = compute.allocate(state, company, b, d)
    best = 0.0
    for f in facilities:
        if not compute.is_compute(f, b):
            continue
        live = f.live_capacity(state.turn)
        if live > 0:
            used = alloc.own.get(f.id, 0.0) + alloc.sold.get(f.id, 0.0)
            best = max(best, used / live)
    return best


def downturn_watch(state: GameState, watch: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """A downturn lived through without firing anyone (stored per save in the profile):
    remembers the month a downturn began, and when it is over checks that no employment of
    the player's ended as "fired" in between."""
    macro = state.macro
    begun = macro.downturn_turn if macro is not None else None
    company = state.player.id
    if begun is not None:
        return False, {"downturn_from": begun}
    since = watch.get("downturn_from")
    if since is None:
        return False, {}
    fired = any(
        e.company_id == company
        and e.end_reason == "fired"
        and e.end_turn is not None
        and e.end_turn >= since
        for e in state.employments
    )
    return not fired, {}


def facts_of(
    session: Session, state: GameState, data: LoadedData, watch: dict[str, Any]
) -> tuple[Facts, dict[str, Any]]:
    """The facts at the committed state, and the save's updated watch (downturn) record."""
    player = state.player
    company = player.id
    snap = repository.latest_snapshot(session, company)
    cash = company_cash(repository.current_balances(session, state.turn), company)
    products = state.company_products(company)
    product_ids = {p.id for p in products}
    customers = sum(s.customers for s in state.product_segments if s.product_id in product_ids)
    holding = next((h for h in state.holdings if h.operating_id == company), None)
    listed_ids = {company} | ({holding.company_id} if holding is not None else set())
    caps = [
        m.price_cents * m.shares
        for m in state.share_months
        if m.company_id in listed_ids
        and m.turn
        == max((x.turn for x in state.share_months if x.company_id == m.company_id), default=-1)
    ]
    score = max((s.score for s in state.scores if s.company_id == company), default=0)
    latest_score = max(
        (s for s in state.scores if s.company_id == company), key=lambda s: s.turn, default=None
    )
    founder = state.founder_of(company)
    life = (
        next((f for f in state.founder_lives if f.person_id == founder.id), None)
        if founder is not None
        else None
    )
    foundation = (
        next((f for f in state.foundations if f.person_id == founder.id), None)
        if founder is not None
        else None
    )
    owners = {company} | ({holding.company_id} if holding is not None else set())
    mode = state.mode
    survived, watch = downturn_watch(state, watch)
    facts = Facts(
        products_launched=sum(1 for p in products if p.launched_turn is not None),
        customers=round(customers),
        headcount=len(state.staff(company)),
        arr_cents=snap.arr_cents if snap is not None else 0,
        cash_cents=cash,
        stage=player.stage,
        months_running=state.turn - player.founded_turn,
        company_score=latest_score.score if latest_score is not None else score,
        market_cap_cents=max(caps, default=0),
        eras_caused=sum(1 for a in state.era_arrivals if a.company_id == company),
        datacentre_use=_datacentre_use(state, company, data),
        acquisitions=sum(1 for a in state.acquisitions if a.acquirer_id in owners),
        clean_integrations=sum(
            1
            for a in state.acquisitions
            if a.acquirer_id in owners
            and a.mode == "integrate"
            and a.key_people > 0
            and a.departed == 0
            and state.turn - a.closed_turn >= INTEGRATION_YEAR
        ),
        subsidiaries=(
            sum(
                1
                for o in state.ownerships
                if o.owner_id == holding.company_id and o.to_turn is None
            )
            if holding is not None
            else 0
        ),
        exits=len(state.ventures),
        promises_kept=sum(
            1 for p in state.promises if p.company_id in owners and p.status == "kept"
        ),
        foundation_grant_cents=foundation.last_grant_cents if foundation is not None else 0,
        profitable_in_first_year=_first_year_profitable(session, company, player.founded_turn),
        listed=any(p.company_id in listed_ids for p in state.public_companies),
        own_chip_in_own_device=any(
            m.company_id == company and m.own_chips > 0 for m in state.production
        ),
        refounded=bool(state.ventures) and all(v.company_id != company for v in state.ventures),
        downturn_without_layoffs=survived,
        burnout_recovered=life is not None
        and life.burnouts > 0
        and not life.burnout
        and life.recovered_turn is not None,
        rounds_closed=frozenset(
            str(r.series)
            for r in state.rounds
            if r.company_id == company and r.closed_turn is not None
        ),
        scenario_won=frozenset(
            {mode.scenario}
            if mode is not None
            and mode.kind == "scenario"
            and mode.result == "success"
            and mode.scenario is not None
            else set()
        ),
    )
    return facts, watch

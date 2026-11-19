"""Government's place in the turn (docs/formulas.md 57).

**Phase 5, after the markets** (`month`), in this order:

1. the named tenders (once) and, each January, the year's seeded budgets and tenders;
2. tenders closing this month stop taking bids; tenders due are awarded (awards.award); a named
   tender's record protest holds it to its record's cancellation (JEDI) or award; a player's win
   may draw a rival's protest;
3. protests decided this month: sustained re-competes the tender once (a new award at once),
   denied lets the award stand;
4. awards that stand start the player's contracts (and their reputation effects, 57.4);
5. contracts deliver (books), clearances are decided, closed tenders are pruned.

A game without government.yaml does nothing here. A company that never bids plays exactly as
before: tenders and rivals' awards are records only (no books, no state another system reads),
and nothing here touches a company without bids, contracts or clearances (57.6 target 1)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.government import awards, clearances, delivery, reputation, tenders
from tst.sim.government.data import enabled, file
from tst.sim.government.models import Bid, Protest, Tender
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def _set_tender(state: GameState, tender: Tender) -> GameState:
    return replace(state, tenders=tuple(tender if t.id == tender.id else t for t in state.tenders))


def _player_bid(state: GameState, tender_id: int) -> Bid | None:
    return next(
        (
            b
            for b in state.gov_bids
            if b.tender_id == tender_id and b.status in ("won", "lost", "submitted", "disqualified")
        ),
        None,
    )


def _stand(
    state: GameState, tender: Tender, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """The award stands: the player's contract when it won."""
    bid = _player_bid(state, tender.id)
    current = state.tender(tender.id)
    if bid is None or bid.status != "won" or current is None:
        return state, []
    state, contract = delivery.start(state, current, bid, balance, data)
    logs = [inbox_item(state.turn, bid.company_id, "contract_won", tender=current.title)]
    if current.buyer == "defence":
        state, more = reputation.on_defence_award(state, contract, rng, balance, data)
        logs += more
    return state, logs


def _award(
    state: GameState, tender: Tender, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    out = awards.award(state, tender, rng, balance, data)
    state = out.state
    logs = list(out.logs)
    hist = (
        next((h for h in file(data).tenders if h.key == tender.key), None) if tender.key else None
    )
    current = state.tender(tender.id)
    assert current is not None
    if hist is not None and hist.protested_by and tender.round == 0:
        until = hist.cancelled
        from tst.sim.facilities.config import month_to_turn

        end = month_to_turn(until) if until is not None else state.turn + 1
        protest = Protest(
            tender_id=tender.id,
            by=hist.protested_by[0],
            company_id=None,
            turn=state.turn,
            until=end,
            sustain=until is not None,
        )
        state = replace(state, protests=(*state.protests, protest))
        return _set_tender(state, replace(current, status="protested", protest_until=end)), logs
    drawn = awards.rival_protest(state, current, out, rng, balance, data)
    if drawn is not None:
        protest = drawn
        state = replace(state, protests=(*state.protests, protest))
        state = _set_tender(
            state, replace(current, status="protested", protest_until=protest.until)
        )
        bid = _player_bid(state, tender.id)
        if bid is not None:
            logs.append(
                inbox_item(
                    state.turn,
                    bid.company_id,
                    "award_protested",
                    tender=current.title,
                    by=protest.by,
                )
            )
        return state, logs
    state, more = _stand(state, current, rng, balance, data)
    return state, logs + more


def _resolve(
    state: GameState, tender: Tender, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    protest = next(
        (
            p
            for p in reversed(state.protests)
            if p.tender_id == tender.id and p.outcome == "pending"
        ),
        None,
    )
    logs: list[LogItem] = []
    hist = (
        next((h for h in file(data).tenders if h.key == tender.key), None) if tender.key else None
    )
    sustained = protest is not None and protest.sustain
    if protest is not None:
        state = replace(
            state,
            protests=tuple(
                replace(p, outcome="sustained" if sustained else "denied") if p is protest else p
                for p in state.protests
            ),
        )
        bid = _player_bid(state, tender.id)
        if bid is not None:
            logs.append(
                inbox_item(
                    state.turn,
                    bid.company_id,
                    "protest_decided",
                    tender=tender.title,
                    outcome="sustained" if sustained else "denied",
                )
            )
    if (
        hist is not None
        and hist.cancelled is not None
        and sustained
        and protest is not None
        and protest.company_id is None
    ):
        return _set_tender(state, replace(tender, status="cancelled", protest_until=None)), logs
    if sustained and tender.round == 0:
        again = replace(
            tender, round=1, award_turn=state.turn, status="evaluating", protest_until=None
        )
        state = _set_tender(state, again)
        bids = tuple(
            replace(b, status="submitted", terms=None, reasons=())
            if b.tender_id == tender.id and b.status in ("won", "lost")
            else b
            for b in state.gov_bids
        )
        state = replace(state, gov_bids=bids)
        out = awards.award(state, again, rng, balance, data)
        state = out.state
        logs += list(out.logs)
        current = state.tender(tender.id)
        assert current is not None
        state, more = _stand(state, current, rng, balance, data)
        return state, logs + more
    state = _set_tender(state, replace(tender, status="awarded", protest_until=None))
    current = state.tender(tender.id)
    assert current is not None
    state, more = _stand(state, current, rng, balance, data)
    return state, logs + more


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(data):
        return state, [], []
    state = tenders.add_history(state, balance, data)
    state = tenders.draw_year(state, rng, balance, data)
    turn = state.turn
    logs: list[LogItem] = []
    for tender in tuple(state.tenders):
        current = state.tender(tender.id)
        if current is None:
            continue
        if current.status == "open" and turn >= current.close_turn:
            current = replace(current, status="evaluating")
            state = _set_tender(state, current)
        if current.status == "evaluating" and turn >= current.award_turn:
            state, more = _award(state, current, rng, balance, data)
            logs += more
        elif (
            current.status == "protested"
            and current.protest_until is not None
            and turn >= current.protest_until
        ):
            state, more = _resolve(state, current, rng, balance, data)
            logs += more
    state, entries, more = delivery.month(state, rng, balance)
    logs += more
    state, more = clearances.month(state)
    logs += more
    state = tenders.prune(state, balance)
    return state, entries, logs

"""Negotiation routes (docs/formulas.md 58; M47, ADR-0023): open talks on a deal, play a
round, take the counterpart's offer, skip at the median. Conversations run between turns; their
outcome reaches the game through the deal's own action."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.negotiations import (
    NegotiationListOut,
    NegotiationModeOut,
    NegotiationMoveOut,
    NegotiationOpenIn,
    NegotiationOut,
    NegotiationRangeOut,
    NegotiationRoundIn,
    NegotiationRoundOut,
    NegotiationSummaryOut,
    NegotiationTermOut,
)
from tst.conversations import common, service
from tst.conversations.view import PublicMove
from tst.sim.calendar import format_turn

router = APIRouter(prefix="/api/saves/{save_id}/negotiations", tags=["negotiations"])


def _mode(m: common.ModeInfo) -> NegotiationModeOut:
    return NegotiationModeOut(
        mode=m.mode, reason=m.reason, cap_cents=m.cap_cents, spent_cents=round(m.spent_cents, 4)
    )


def _move(m: PublicMove) -> NegotiationMoveOut:
    return NegotiationMoveOut(kind=m.kind, term=m.term, other=m.other, fact=m.fact, words=m.words)


def negotiation_out(t: service.Talks) -> NegotiationOut:
    v = t.view
    said = {n: (msg, src, reply, by) for n, msg, src, reply, by in t.messages}
    return NegotiationOut(
        negotiation_id=t.id,
        kind=v.kind,
        subject=v.subject,
        status=t.status,
        opened_turn=t.opened_turn,
        date_label=format_turn(t.opened_turn),
        cooldown_until=t.cooldown_until,
        error=t.error,
        terms=[
            NegotiationTermOut(
                key=x.key, label=x.label, unit=x.unit, wants=x.wants, base_shown=x.base_shown
            )
            for x in v.terms
        ],
        counterpart_name=v.counterpart_name,
        counterpart_role=v.counterpart_role,
        counterpart_organisation=v.counterpart_organisation,
        counterpart_style=v.counterpart_style,
        relationship=v.relationship,
        facts=list(v.facts),
        used_facts=list(v.used_facts),
        persona=list(v.persona),
        opening=list(v.opening),
        opening_shown=list(v.opening_shown),
        opening_line=t.opening_line,
        counter=list(v.counter),
        counter_shown=list(v.counter_shown),
        offer=None if v.offer is None else list(v.offer),
        offer_shown=list(v.offer_shown),
        ranges=[NegotiationRangeOut(lo=r.lo, hi=r.hi, shown=r.shown) for r in v.ranges],
        mood=v.mood,
        rounds=[
            NegotiationRoundOut(
                n=r.n,
                offer=list(r.offer),
                offer_shown=list(r.offer_shown),
                claimed=[_move(m) for m in r.claimed],
                moves=[_move(m) for m in r.moves],
                counter_before=list(r.counter_before),
                counter=list(r.counter),
                counter_shown=list(r.counter_shown),
                outcome=r.outcome,
                reason=r.reason,
                reason_words=r.reason_words,
                mood=r.mood,
                relationship_change=r.relationship_change,
                message=said.get(r.n, ("", "", "", ""))[0],
                message_source=said.get(r.n, ("", "", "", ""))[1],
                reply=said.get(r.n, ("", "", "", ""))[2],
                reply_source=said.get(r.n, ("", "", "", ""))[3],
            )
            for r in v.rounds
        ],
        suggestions=list(t.suggestions),
        final=None if v.final is None else list(v.final),
        final_shown=list(v.final_shown),
        mode=_mode(t.mode),
    )


@router.get(
    "", response_model=NegotiationListOut, responses=ERRORS, operation_id="listNegotiations"
)
def list_negotiations(save_id: str, settings: SettingsDep, data: DataDep) -> NegotiationListOut:
    """This save's negotiations, newest first, and whether conversations use the LLM now."""
    path = _path(settings, save_id)
    talks = service.listing(path, data)
    return NegotiationListOut(
        mode=_mode(common.mode_info(path.parent, data)),
        items=[
            NegotiationSummaryOut(
                negotiation_id=t.id,
                kind=t.view.kind,
                subject=t.view.subject,
                status=t.status,
                opened_turn=t.opened_turn,
                date_label=format_turn(t.opened_turn),
                counterpart_name=t.view.counterpart_name,
                counterpart_organisation=t.view.counterpart_organisation,
                rounds=len(t.view.rounds),
                final_shown=list(t.view.final_shown),
            )
            for t in talks
        ],
    )


@router.post("", response_model=NegotiationOut, responses=ERRORS, operation_id="openNegotiation")
def open_negotiation(
    save_id: str, body: NegotiationOpenIn, settings: SettingsDep, data: DataDep
) -> NegotiationOut:
    """Open talks on a deal the game prices (or resume this month's open talks on it)."""
    path = _path(settings, save_id)
    return negotiation_out(service.open_talks(path, data, body.kind, dict(body.params)))


@router.get(
    "/{negotiation_id}",
    response_model=NegotiationOut,
    responses=ERRORS,
    operation_id="getNegotiation",
)
def get_negotiation(
    save_id: str, negotiation_id: int, settings: SettingsDep, data: DataDep
) -> NegotiationOut:
    """The negotiation and, once it is over, its debrief: every round's moves and what they did,
    the final terms against the opening offer and the revealed range."""
    return negotiation_out(service.get(_path(settings, save_id), data, negotiation_id))


@router.post(
    "/{negotiation_id}/rounds",
    response_model=NegotiationOut,
    responses=ERRORS,
    operation_id="playNegotiationRound",
)
def play_round(
    save_id: str,
    negotiation_id: int,
    body: NegotiationRoundIn,
    settings: SettingsDep,
    data: DataDep,
) -> NegotiationOut:
    """One round: free text (scored by the LLM into moves) or template moves, with an offer."""
    t = service.play(
        _path(settings, save_id),
        data,
        negotiation_id,
        body.offer,
        message=body.message,
        moves=None if body.moves is None else [m.model_dump(exclude_none=True) for m in body.moves],
        source=body.source,
    )
    return negotiation_out(t)


@router.post(
    "/{negotiation_id}/accept",
    response_model=NegotiationOut,
    responses=ERRORS,
    operation_id="acceptNegotiationOffer",
)
def accept_offer(
    save_id: str, negotiation_id: int, settings: SettingsDep, data: DataDep
) -> NegotiationOut:
    """Take the counterpart's offer as shown: the deal executes through its own action."""
    return negotiation_out(service.accept(_path(settings, save_id), data, negotiation_id))


@router.post(
    "/{negotiation_id}/skip",
    response_model=NegotiationOut,
    responses=ERRORS,
    operation_id="skipNegotiation",
)
def skip_negotiation(
    save_id: str, negotiation_id: int, settings: SettingsDep, data: DataDep
) -> NegotiationOut:
    """Skip: the deal closes at the median outcome, as the game prices it today (58.4)."""
    return negotiation_out(service.skip(_path(settings, save_id), data, negotiation_id))

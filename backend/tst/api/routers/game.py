"""Save-scoped game routes (M1b): people, recruitment, inbox, founder energy.

Every action runs through `repository.run_action` with the founder as actor (ADR-0014): one
short transaction, logged to decision_log. Responses carry ranges, never true values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from tst.api import former_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.saves import ERRORS
from tst.api.schemas.people import (
    ActionOut,
    CheckOut,
    EnergyOut,
    FireOut,
    FormerProfileOut,
    InboxBulkOut,
    InboxItemOut,
    InboxOut,
    OfferIn,
    OfferOut,
    OfferPreviewOut,
    PersonProfileOut,
    PersonSummaryOut,
    SearchIn,
    SearchOut,
)
from tst.db import inbox, repository
from tst.db.events import written_text
from tst.db.mappers import search_from_row
from tst.db.models import SearchRow
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    CloseSearch,
    Fire,
    Interview,
    MakeOffer,
    OpenSearch,
    ReferenceCheck,
    WithdrawOffer,
)
from tst.sim.errors import InvalidActionError, UnknownCandidateError, UnknownOfferError
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.options import offer_shares, pool_left_bp, pool_left_shares
from tst.sim.hiring.rules import offer_preview
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["game"])


def _path(settings: SettingsDep, save_id: str) -> Path:
    return repository.existing_save_path(settings.resolved_save_dir(), save_id)


def _state(path: Path) -> GameState:
    with repository.read_session(path) as session:
        return repository.read_state(session)


def _founder_id(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise InvalidActionError("this save has no founder to act")
    return founder.id


def _act(path: Path, data: LoadedData, action: Action) -> tuple[ActionResult, ActionOut]:
    result = repository.run_action(path, data, action)
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, result.new_state.player.id)
    return result, ActionOut(energy=views.energy(result.new_state, data), unread_inbox=unread)


# --- People ---------------------------------------------------------------------------------


@router.get(
    "/people", response_model=list[PersonSummaryOut], responses=ERRORS, operation_id="listPeople"
)
def list_people(save_id: str, settings: SettingsDep, data: DataDep) -> list[PersonSummaryOut]:
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        company = state.player.id
        checks = views.checks_by_person(session, company)
    return [
        views.person_summary(state, company, e.person_id, data, checks)
        for e in sorted(state.staff(company), key=lambda e: e.person_id)
    ]


@router.get(
    "/people/{person_id}",
    response_model=PersonProfileOut,
    responses=ERRORS,
    operation_id="getPerson",
)
def get_person(
    save_id: str, person_id: int, settings: SettingsDep, data: DataDep
) -> PersonProfileOut:
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        return views.person_profile(session, state, state.player.id, person_id, data)


@router.get(
    "/people/{person_id}/former",
    response_model=FormerProfileOut,
    responses=ERRORS,
    operation_id="getFormerPerson",
)
def get_former_person(
    save_id: str, person_id: int, settings: SettingsDep, data: DataDep
) -> FormerProfileOut:
    """Someone who has left (M7c): read-only, as the player knew them when they left."""
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        return former_views.former_profile(session, state.player.id, person_id, data)


@router.post(
    "/people/{person_id}/fire", response_model=FireOut, responses=ERRORS, operation_id="firePerson"
)
def fire_person(save_id: str, person_id: int, settings: SettingsDep, data: DataDep) -> FireOut:
    path = _path(settings, save_id)
    result, out = _act(path, data, Fire(_founder_id(_state(path)), person_id))
    severance = sum(ln.amount for e in result.ledger_entries for ln in e.lines if ln.amount > 0)
    return FireOut(**out.model_dump(), severance_cents=severance)


# --- Recruitment ----------------------------------------------------------------------------


@router.get(
    "/recruitment/searches",
    response_model=list[SearchOut],
    responses=ERRORS,
    operation_id="listSearches",
)
def list_searches(save_id: str, settings: SettingsDep, data: DataDep) -> list[SearchOut]:
    """Open searches, plus closed ones whose candidates are still available, newest first."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        company = state.player.id
        live = {c.search_id for c in state.open_candidates(company)}
        open_ids = {s.id for s in state.open_searches(company)}
        closed = [
            search_from_row(row)
            for row in session.scalars(
                select(SearchRow).where(
                    SearchRow.id.in_(live - open_ids), SearchRow.company_id == company
                )
            )
        ]
    searches = sorted([*state.open_searches(company), *closed], key=lambda s: -s.id)
    return [views.search_out(state, s, data) for s in searches]


@router.post(
    "/recruitment/searches",
    response_model=SearchOut,
    status_code=201,
    responses=ERRORS,
    operation_id="openSearch",
)
def open_search(save_id: str, body: SearchIn, settings: SettingsDep, data: DataDep) -> SearchOut:
    path = _path(settings, save_id)
    action = OpenSearch(
        _founder_id(_state(path)),
        body.role,
        body.channel,  # type: ignore[arg-type]
        rival_id=body.rival_id,
        level=body.level,
        city=body.city,
        unit_id=body.unit_id,
        interest=body.interest,
    )
    result, _ = _act(path, data, action)
    search = max(result.new_state.searches, key=lambda s: s.id)
    return views.search_out(result.new_state, search, data)


@router.post(
    "/recruitment/searches/{search_id}/close",
    response_model=SearchOut,
    responses=ERRORS,
    operation_id="closeSearch",
)
def close_search(save_id: str, search_id: int, settings: SettingsDep, data: DataDep) -> SearchOut:
    path = _path(settings, save_id)
    result, _ = _act(path, data, CloseSearch(_founder_id(_state(path)), search_id))
    search = result.new_state.search(search_id)
    assert search is not None
    return views.search_out(result.new_state, search, data)


@router.get(
    "/recruitment/candidates",
    response_model=list[PersonSummaryOut],
    responses=ERRORS,
    operation_id="listCandidates",
)
def list_candidates(save_id: str, settings: SettingsDep, data: DataDep) -> list[PersonSummaryOut]:
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        company = state.player.id
        checks = views.checks_by_person(session, company)
    return [
        views.person_summary(state, company, c.person_id, data, checks)
        for c in state.open_candidates(company)
    ]


def _check(
    save_id: str, candidate_id: int, settings: SettingsDep, data: DataDep, kind: str
) -> CheckOut:
    path = _path(settings, save_id)
    before = _state(path)
    actor = _founder_id(before)
    action = (
        Interview(actor, candidate_id)
        if kind == "interview"
        else ReferenceCheck(actor, candidate_id)
    )
    repository.run_action(path, data, action)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        company = state.player.id
        profile = views.person_profile(session, state, company, candidate_id, data)
    learned = views.learned(before, state, company, candidate_id, kind, data)
    return CheckOut(**profile.model_dump(), learned=learned)


@router.post(
    "/recruitment/candidates/{candidate_id}/interview",
    response_model=CheckOut,
    responses=ERRORS,
    operation_id="interviewCandidate",
)
def interview(save_id: str, candidate_id: int, settings: SettingsDep, data: DataDep) -> CheckOut:
    """Interview a candidate; the response says what it taught (M4c)."""
    return _check(save_id, candidate_id, settings, data, "interview")


@router.post(
    "/recruitment/candidates/{candidate_id}/reference-check",
    response_model=CheckOut,
    responses=ERRORS,
    operation_id="referenceCheck",
)
def reference_check(
    save_id: str, candidate_id: int, settings: SettingsDep, data: DataDep
) -> CheckOut:
    """Check a candidate's references; the response says what it taught (M4c)."""
    return _check(save_id, candidate_id, settings, data, "reference_check")


@router.post(
    "/recruitment/candidates/{candidate_id}/offer",
    response_model=OfferOut,
    status_code=201,
    responses=ERRORS,
    operation_id="makeOffer",
)
def make_offer(
    save_id: str, candidate_id: int, body: OfferIn, settings: SettingsDep, data: DataDep
) -> OfferOut:
    path = _path(settings, save_id)
    action = MakeOffer(_founder_id(_state(path)), candidate_id, body.salary_cents, body.equity_bp)
    result, _ = _act(path, data, action)
    offer = result.new_state.pending_offer_for(candidate_id)
    assert offer is not None
    return OfferOut(
        offer_id=offer.id,
        candidate_id=offer.candidate_id,
        salary_cents=offer.salary_cents,
        equity_bp=offer.equity_bp,
        made_turn=offer.made_turn,
        status=offer.status,
    )


@router.post(
    "/recruitment/candidates/{candidate_id}/offer-preview",
    response_model=OfferPreviewOut,
    responses=ERRORS,
    operation_id="previewOffer",
)
def preview_offer(
    save_id: str, candidate_id: int, body: OfferIn, settings: SettingsDep, data: DataDep
) -> OfferPreviewOut:
    """The offer dialog's hint and rule checks. No energy, no randomness, nothing saved."""
    state = _state(_path(settings, save_id))
    candidate = state.candidate(candidate_id)
    if candidate is None or candidate.company_id != state.player.id:
        raise UnknownCandidateError(f"no open candidate {candidate_id}")
    preview = offer_preview(
        state,
        candidate,
        body.salary_cents,
        body.equity_bp,
        data.balance,
        data.game_data,
        actor_id=_founder_id(state),
    )
    company = state.player.id
    pool_left = pool_left_bp(state, company)
    pending = state.pending_offer_for(candidate_id)
    options = offer_shares(state, company, body.equity_bp)
    fd = fd_shares(state, company)
    replaced = offer_shares(state, company, pending.equity_bp) if pending else 0
    return OfferPreviewOut(
        hint=preview.hint,
        ratio=preview.ratio,
        floor_cents=preview.floor_cents,
        expectation_cents=preview.expectation_cents,
        problems=list(preview.problems),
        option_pool_left_bp=max(pool_left + (pending.equity_bp if pending else 0), 0),
        options=options,
        fraction=options / fd if fd else 0.0,
        options_left=pool_left_shares(state, company) + replaced,
        fd_shares=fd,
        reasons=views.offer_reasons(
            state,
            state.person(candidate.person_id),
            state.player.id,
            preview.ratio,
            body.equity_bp,
            data,
        ),
    )


@router.post(
    "/recruitment/offers/{offer_id}/withdraw",
    response_model=OfferOut,
    responses=ERRORS,
    operation_id="withdrawOffer",
)
def withdraw_offer(save_id: str, offer_id: int, settings: SettingsDep, data: DataDep) -> OfferOut:
    path = _path(settings, save_id)
    result, _ = _act(path, data, WithdrawOffer(_founder_id(_state(path)), offer_id))
    offer = result.new_state.offer(offer_id)
    if offer is None:
        raise UnknownOfferError(f"no offer {offer_id}")
    return OfferOut(
        offer_id=offer.id,
        candidate_id=offer.candidate_id,
        salary_cents=offer.salary_cents,
        equity_bp=offer.equity_bp,
        made_turn=offer.made_turn,
        status=offer.status,
    )


# --- Inbox and founder ----------------------------------------------------------------------


@router.get("/inbox", response_model=InboxOut, responses=ERRORS, operation_id="getInbox")
def get_inbox(
    save_id: str,
    settings: SettingsDep,
    unread_only: bool = False,
    kind: Annotated[list[str] | None, Query()] = None,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    archived: bool = False,
    needs_you: bool = False,
) -> InboxOut:
    """Newest first. `limit` and `offset` page through a long inbox (M2b); repeat `kind` to
    keep only those message kinds, across every page (M3b). Archived items are hidden;
    `archived=true` shows only them (M4c). `needs_you` keeps what waits for the player: open
    major and critical events and waiting proposals and pitches (M29, 42.4)."""
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        player = state.player
        only = inbox.needs_you(state) if needs_you else None
        items = inbox.list_inbox(
            session,
            player.id,
            unread_only=unread_only,
            kinds=kind,
            limit=limit,
            offset=offset,
            archived=archived,
            only=only,
        )
        return InboxOut(
            unread=inbox.unread_count(session, player.id),
            total=inbox.inbox_total(
                session,
                player.id,
                unread_only=unread_only,
                kinds=kind,
                archived=archived,
                only=only,
            ),
            offset=offset,
            items=[
                views.inbox_item(m).model_copy(
                    update={"quote": written_text(session, "exit_line", m.turn, m.link_id)}
                )
                if m.template == "resigned" and m.link_id is not None
                else views.inbox_item(m)
                for m in items
            ],
        )


@router.get(
    "/inbox/{item_id}", response_model=InboxItemOut, responses=ERRORS, operation_id="getInboxItem"
)
def get_inbox_item(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    """One message, archived or not, wherever it falls in the pages (M7c deep links)."""
    with repository.read_session(_path(settings, save_id)) as session:
        player = repository.read_state(session).player
        return views.inbox_item(inbox.get_item(session, player.id, item_id))


@router.post(
    "/inbox/read-all",
    response_model=InboxBulkOut,
    responses=ERRORS,
    operation_id="markInboxAllRead",
)
def mark_inbox_all_read(save_id: str, settings: SettingsDep) -> InboxBulkOut:
    """Mark every message read (M4c). UI state: no energy, nothing in decision_log."""
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        changed = inbox.mark_all_read(session, player.id)
        return InboxBulkOut(changed=changed, unread=inbox.unread_count(session, player.id))


@router.post(
    "/inbox/archive-read",
    response_model=InboxBulkOut,
    responses=ERRORS,
    operation_id="archiveInboxRead",
)
def archive_inbox_read(save_id: str, settings: SettingsDep) -> InboxBulkOut:
    """Archive every read message (M4c)."""
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        changed = inbox.archive_read(session, player.id)
        return InboxBulkOut(changed=changed, unread=inbox.unread_count(session, player.id))


@router.post(
    "/inbox/{item_id}/archive",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="archiveInboxItem",
)
def archive_inbox_item(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    """Archive one message; it is marked read too (M4c)."""
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.archive(session, player.id, item_id))


@router.post(
    "/inbox/{item_id}/unarchive",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="unarchiveInboxItem",
)
def unarchive_inbox_item(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    """Bring an archived message back to the inbox (M4c)."""
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.archive(session, player.id, item_id, archived=False))


@router.post(
    "/inbox/{item_id}/read",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="markInboxRead",
)
def mark_inbox_read(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.mark_read(session, player.id, item_id))


@router.post(
    "/inbox/{item_id}/unread",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="markInboxUnread",
)
def mark_inbox_unread(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.mark_read(session, player.id, item_id, read=False))


@router.post(
    "/inbox/{item_id}/bookmark",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="bookmarkInboxItem",
)
def bookmark_inbox_item(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    """Star a message: it stays in the inbox, never auto-archived (23.1, M10b)."""
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.bookmark(session, player.id, item_id))


@router.post(
    "/inbox/{item_id}/unbookmark",
    response_model=InboxItemOut,
    responses=ERRORS,
    operation_id="unbookmarkInboxItem",
)
def unbookmark_inbox_item(save_id: str, item_id: int, settings: SettingsDep) -> InboxItemOut:
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        player = repository.load_state(session).player
        return views.inbox_item(inbox.bookmark(session, player.id, item_id, bookmarked=False))


@router.get(
    "/founder/energy", response_model=EnergyOut, responses=ERRORS, operation_id="getFounderEnergy"
)
def founder_energy(save_id: str, settings: SettingsDep, data: DataDep) -> EnergyOut:
    return views.energy(_state(_path(settings, save_id)), data)

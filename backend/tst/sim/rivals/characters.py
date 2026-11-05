"""Rival founders as characters (docs/formulas.md 29.4, M14b): each rival's named CEO (see
tst.sim.press.names.rival_ceo_id), their public statements and jabs, and the feud between
the player's founder and each rival CEO, with rivalry's effect on the rival's decisions.

Draws come from stream `press` keyed by the rival's stable key (ADR-0013 amendment), one
generator a month per rival that speaks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.press import moments
from tst.sim.press.draws import press_gen
from tst.sim.press.models import Feud, Statement
from tst.sim.press.names import rival_ceo_id, rival_ceo_name
from tst.sim.rivals.models import RivalMove, stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, feud_of, player_companies, with_feud, with_statement

SELLING = ("live", "sunset")
# A CEO speaks at their company's launches, releases (quality and feature pushes) and price cuts
SPEAKING_MOVES = ("price_cut", "launched", "enter_segment", "feature_push", "quality_push")
STATEMENT_MEMORY = 24  # tunable-exempt: months of statements kept in the live state
SCALE = 100  # tunable-exempt: the feud's 0-100 scale
ANSWERING = ("aggressive",)  # personalities that answer a bold claim naming them (29.1)

# Statements in each personality's voice (29.4): {rival} is their company, {product} the
# product the move is about, {company} the player's company.
VOICE: dict[str, dict[str, str]] = {
    "aggressive": {
        "statement": "We are coming for every customer in this market, starting now.",
        "jab": "{company} talks a good game. Our numbers do the talking.",
        "answer": "Big words from {company}. Customers will decide, and they are choosing us.",
    },
    "premium": {
        "statement": "Quality wins in the end. This is the best work we have shipped.",
        "jab": "Some companies race to the bottom. {company} is welcome to it.",
        "answer": "We let our products speak for themselves.",
    },
    "fast_follower": {
        "statement": "We listened to customers and built what they asked for.",
        "jab": "{company} had a head start. That is all it was.",
        "answer": "Every market leader gets caught eventually.",
    },
    "cost_leader": {
        "statement": "Same job, lower bill. That is the whole pitch.",
        "jab": "Ask {company}'s customers what they pay, then ask ours.",
        "answer": "Customers care about price, not press conferences.",
    },
}


def _voice(state: GameState, rival_id: int, kind: str) -> str:
    personality = state.company(rival_id).personality or "aggressive"
    return VOICE.get(personality, VOICE["aggressive"])[kind]


# --- Feuds -------------------------------------------------------------------------------------


def add_feud(
    state: GameState,
    company_id: int,
    rival_id: int,
    delta: float,
    cause: str,
    balance: Balance,
) -> GameState:
    """The feud between `company_id`'s founder and `rival_id`'s CEO moves by `delta` (29.4);
    reaching rivalry raises a `rivalry` press moment. M14 calls this for a hostile bid
    (`balance.feud.hostile_bid`)."""
    fb = balance.feud
    feud = feud_of(state, company_id, rival_id) or Feud(company_id, rival_id)
    score = max(0.0, min(float(SCALE), feud.score + delta))
    causes = feud.causes
    if delta > 0:
        causes = (*causes, (state.turn, delta, cause))[-fb.causes_kept :]
    crossed = feud.score < fb.rivalry <= score
    feud = replace(
        feud,
        score=score,
        causes=causes,
        rivalry_turn=state.turn if crossed else feud.rivalry_turn,
    )
    state = with_feud(state, feud)
    if crossed:
        state = moments.queue_moment(state, company_id, "rivalry", {"rival_id": rival_id})
    return state


def in_rivalry(state: GameState, rival_id: int, balance: Balance) -> bool:
    return any(
        f.rival_id == rival_id and f.score >= balance.feud.rivalry
        for f in state.feuds
        if state.company(f.company_id).is_player
    )


def rivalry_mult(state: GameState, rival_id: int, balance: Balance) -> float:
    """A rival in a rivalry weights actions against the player's products x feud.target_mult
    (29.4)."""
    return balance.feud.target_mult if in_rivalry(state, rival_id, balance) else 1.0


def bold_mention(
    state: GameState, company_id: int, rival_id: int, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A bold answer named the rival's CEO: the feud grows, and an aggressive rival answers
    (29.1, 29.4)."""
    state = add_feud(
        state, company_id, rival_id, balance.feud.bold_mention, "a bold claim named them", balance
    )
    logs: list[LogItem] = []
    if state.company(rival_id).personality in ANSWERING:
        state, logged = _speak(state, rival_id, "answer", None, company_id)
        logs += logged
    return state, logs


def _speak(
    state: GameState,
    rival_id: int,
    kind: str,
    product_id: int | None,
    player_id: int,
    notify: bool = True,
) -> tuple[GameState, list[LogItem]]:
    ceo = rival_ceo_id(state, rival_id)
    if ceo is None:
        return state, []
    rival = state.company(rival_id)
    product = state.product(product_id) if product_id is not None else None
    text = _voice(state, rival_id, kind).format(
        company=state.company(player_id).name,
        rival=rival.name,
        product=product.name if product is not None else rival.name,
    )
    sid, ids = state.next_ids.take("statement")
    state = with_statement(
        replace(state, next_ids=ids),
        Statement(sid, rival_id, ceo, state.turn, kind, text, product_id),  # type: ignore[arg-type]
    )
    if not notify:  # recorded on the Rival screen only
        return state, []
    name = rival_ceo_name(state, rival_id) or rival.name
    log = inbox_item(
        state.turn,
        player_id,
        "rival_statement",
        link_kind="rival",
        link_id=rival_id,
        name=name,
        rival=rival.name,
        text=text,
    )
    return state, [log]


def _player_segments(state: GameState, company_id: int) -> dict[tuple[str, str], int]:
    """(category, segment) -> a live player product selling there."""
    out: dict[tuple[str, str], int] = {}
    for p in state.company_products(company_id):
        if p.status in SELLING:
            for seg in state.segments_of(p.id):
                out.setdefault((p.category, seg.segment), p.id)
    return out


def feud_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    rival_moves: Iterable[RivalMove],
) -> tuple[GameState, list[LogItem]]:
    """Phase 12 (29.4): feuds decay; head-to-head launches and poaching either way add to
    them; rivals' CEOs speak at their own launches and price cuts, and jab at the player in
    a segment both sell in, opening a `jab` press moment."""
    fb, pb = balance.feud, balance.press
    logs: list[LogItem] = []
    for feud in list(state.feuds):
        if feud.score > 0:
            state = with_feud(state, replace(feud, score=max(0.0, feud.score - fb.decay)))
    for company in player_companies(state):
        cid = company.id
        mine = _player_segments(state, cid)
        # the player's launches this month against rivals already in the segment
        for p in state.company_products(cid):
            if p.launched_turn != state.turn:
                continue
            rivals = {
                other.company_id
                for seg in state.segments_of(p.id)
                for other in state.products
                if other.company_id != cid
                and other.category == p.category
                and other.status in SELLING
                and state.product_segment(other.id, seg.segment) is not None
                and state.company(other.company_id).is_rival
            }
            for rival_id in sorted(rivals):
                state = add_feud(
                    state,
                    cid,
                    rival_id,
                    fb.head_to_head,
                    f"{p.name} launched against them",
                    balance,
                )
        # poaching either way this month
        for e in state.employments:
            if e.end_turn != state.turn or e.end_reason != "poached" or e.company_id != cid:
                continue
            new = next(
                (
                    x
                    for x in state.employments
                    if x.person_id == e.person_id
                    and x.start_turn == state.turn
                    and x.company_id != cid
                ),
                None,
            )
            if new is not None and state.company(new.company_id).is_rival:
                state = add_feud(
                    state, cid, new.company_id, fb.poach, "they poached one of your people", balance
                )
        for e in state.employments:
            if e.company_id != cid or e.start_turn != state.turn:
                continue
            old = next(
                (
                    x
                    for x in state.employments
                    if x.person_id == e.person_id
                    and x.company_id != cid
                    and x.end_turn == state.turn
                ),
                None,
            )
            if old is not None and state.company(old.company_id).is_rival:
                state = add_feud(
                    state, cid, old.company_id, fb.poach, "you hired one of their people", balance
                )
        # rivals' statements and jabs
        spoken: set[int] = set()
        for move in rival_moves:
            if move.action not in SPEAKING_MOVES or move.company_id in spoken:
                continue
            rival = state.company(move.company_id)
            if not rival.is_rival or not rival.alive or rival_ceo_id(state, rival.id) is None:
                continue
            spoken.add(rival.id)
            gen = press_gen(rng, state.turn, *stream_key(rival.id, rival.rival_key))
            if float(gen.random()) >= pb.statement_chance:
                continue
            product = state.product(move.product_id) if move.product_id is not None else None
            target = (
                mine.get((product.category, move.segment))
                if product is not None and move.segment is not None
                else None
            )
            current = feud_of(state, cid, rival.id)
            score = current.score if current is not None else 0.0
            chance = pb.jab_base + pb.jab_feud * score / SCALE
            if target is not None and float(gen.random()) < chance:
                state, logged = _speak(state, rival.id, "jab", move.product_id, cid)
                state = moments.queue_moment(
                    state,
                    cid,
                    "jab",
                    {"rival_id": rival.id, "product_id": target, "segment": move.segment or ""},
                )
            else:  # the inbox hears only of statements in markets the player sells in
                state, logged = _speak(
                    state, rival.id, "statement", move.product_id, cid, notify=target is not None
                )
            logs += logged
    keep = state.turn - STATEMENT_MEMORY
    state = replace(state, statements=tuple(s for s in state.statements if s.turn > keep))
    return state, logs

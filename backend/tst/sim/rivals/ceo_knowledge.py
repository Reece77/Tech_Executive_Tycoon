"""What the player learns of rival CEOs (M15b addendum 11): a rival CEO's profile shows
ranges, like anyone else's, narrowed by the scouting rules. Public appearances (statements,
jabs, feud answers) reveal a little; a poach search opened on the CEO's company and diligence
done on it reveal more. Never true values: the API reads only the reveal record.

Applied once at month end (phase 11) from what the month recorded, so every knowledge record
is created where reveal records always are (`new_reveal_state`, stream `reveal`)."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.people.reveal import apply_knowledge_action, new_reveal_state
from tst.sim.press.names import rival_ceo_id
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_reveal

SCOUT_SKILL = "judgment_of_talent"


def _scout(state: GameState) -> float:
    """The founder reads rival CEOs: the player's founder's judgment of talent."""
    founder = state.founder_of(state.player.id)
    return founder.skills[SCOUT_SKILL] if founder is not None else 0.0


def learn_of_ceo(
    state: GameState,
    person_id: int,
    action: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GameState:
    """One knowledge action by the player on a rival CEO, creating the record if needed."""
    player = state.player.id
    reveal = state.reveal(player, person_id)
    if reveal is None:
        reveal = new_reveal_state(
            observer_company_id=player,
            person=state.person(person_id),
            turn=state.turn,
            rng=rng,
            data=data,
            balance=balance,
        )
    reveal = apply_knowledge_action(
        reveal,
        action,
        _scout(state),
        balance,
        turn=state.turn,
        skill_keys=frozenset(data.skill_keys),
    )
    return with_reveal(state, reveal)


def month_events(state: GameState) -> list[tuple[int, str]]:
    """(rival CEO person id, action) for this month, in a fixed order: statements by id,
    poach searches by id, diligence by target id."""
    player = state.player.id
    out: list[tuple[int, str]] = []
    for s in sorted(state.statements, key=lambda x: x.id):
        if s.turn == state.turn:
            out.append((s.person_id, "public_appearance"))
    for search in state.searches:
        if (
            search.company_id == player
            and search.rival_id is not None
            and search.opened_turn == state.turn
            and (ceo := rival_ceo_id(state, search.rival_id)) is not None
        ):
            out.append((ceo, "rival_approach"))
    for f in sorted(state.target_files, key=lambda x: x.target_id):
        if (
            f.acquirer_id == player
            and f.diligence_done_turn == state.turn
            and (ceo := rival_ceo_id(state, f.target_id)) is not None
        ):
            out.append((ceo, "rival_diligence"))
    return out


def ceo_knowledge_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """Phase 11: the month's appearances, approaches and diligence narrow the player's
    ranges on those rival CEOs. Someone the player employs is skipped (their own reveal
    already runs on employed months)."""
    player = state.player.id
    for person_id, action in month_events(state):
        if any(e.person_id == person_id for e in state.staff(player)):
            continue
        state = learn_of_ceo(state, person_id, action, rng, balance, data)
    return state

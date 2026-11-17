"""The campaign length and the standard campaign's end (docs/formulas.md 52.1).

A **standard** campaign runs 360 turns, January 2010 to December 2039. When December 2039 has
been played it is *at its end*: a derived condition, never stored, so the state after December
2039 is the same in a standard and a dynasty game (52.5 target 1). Then only the choice is
allowed: end it (`EndCampaign`, game state `campaign_end`) or continue in dynasty mode
(`ContinueDynasty`), which a standard game can also choose at any time before.

A **dynasty** game runs to December 2069; after that month it is over (`dynasty_end`), the
save open for browsing. Every game that reaches 2070 ends there (a Sandbox too): no system's
data continues past it (52.2; sandbox after 2069 is out of scope).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance
from tst.sim.errors import CampaignEndError, InvalidActionError
from tst.sim.modes.models import CampaignLength, GameMode
from tst.sim.state import GameState

JANUARY, DECEMBER = 1, 12  # tunable-exempt: calendar months


@dataclass(frozen=True, slots=True)
class ContinueDynasty:
    """Switch a standard campaign to dynasty mode (52.1): a one-off, before or at its end."""

    actor_id: int
    kind: Literal["continue_dynasty"] = "continue_dynasty"


@dataclass(frozen=True, slots=True)
class EndCampaign:
    """At a standard campaign's end: end it, with the campaign summary (52.1)."""

    actor_id: int
    kind: Literal["end_campaign"] = "end_campaign"


type DynastyModeAction = ContinueDynasty | EndCampaign


def start_turn(balance: Balance) -> int:
    """The first dynasty month, January 2040 (turn 360). Nothing in M37 runs before it."""
    return ym_to_turn(balance.dynasty.start_year, JANUARY)


def final_turn(balance: Balance) -> int:
    """The turn after December 2069 (720): a game there is over."""
    return ym_to_turn(balance.dynasty.end_year, DECEMBER) + 1


def in_dynasty_years(state: GameState, balance: Balance) -> bool:
    return state.turn >= start_turn(balance)


def length(state: GameState) -> CampaignLength:
    mode = state.mode
    return mode.length if mode is not None else "standard"


def is_campaign(state: GameState) -> bool:
    return state.mode is None or state.mode.kind == "campaign"


def at_standard_end(state: GameState, balance: Balance) -> bool:
    """A standard campaign with December 2039 played and no choice made yet (52.1)."""
    return (
        state.save_meta.game_state == "active"
        and is_campaign(state)
        and length(state) == "standard"
        and state.turn >= start_turn(balance)
    )


def outcome(state: GameState, balance: Balance) -> str:
    """The game state the player sees: `campaign_end` while a standard campaign waits at its
    end, else the stored one."""
    if at_standard_end(state, balance):
        return "campaign_end"
    return state.save_meta.game_state


def check_can_play(state: GameState, balance: Balance) -> None:
    """Refuse a turn or an action at the standard end (CampaignEndError, 409)."""
    if at_standard_end(state, balance):
        raise CampaignEndError(
            "the standard campaign ended in December 2039: end it or continue in dynasty mode"
        )


def continue_dynasty(state: GameState, balance: Balance) -> GameState:
    if state.ended:
        raise InvalidActionError("the game is over")
    if not is_campaign(state):
        raise InvalidActionError("only a campaign has a dynasty mode")
    if length(state) == "dynasty":
        raise InvalidActionError("this game is already in dynasty mode")
    mode = state.mode if state.mode is not None else GameMode(kind="campaign")
    return replace(state, mode=replace(mode, length="dynasty"))


def end_campaign(state: GameState, balance: Balance) -> GameState:
    if not at_standard_end(state, balance):
        raise InvalidActionError("a campaign can be ended only at December 2039")
    meta = replace(state.save_meta, game_state="campaign_end", ended_turn=state.turn - 1)
    return replace(state, save_meta=meta)


def apply_mode_action(state: GameState, action: DynastyModeAction, balance: Balance) -> GameState:
    if isinstance(action, ContinueDynasty):
        return continue_dynasty(state, balance)
    return end_campaign(state, balance)


def close_at_final(state: GameState, balance: Balance) -> GameState:
    """After December 2069's turn (the new state's turn is final_turn): the game is over."""
    if state.turn < final_turn(balance) or state.save_meta.game_state != "active":
        return state
    meta = replace(state.save_meta, game_state="dynasty_end", ended_turn=state.turn - 1)
    return replace(state, save_meta=meta)

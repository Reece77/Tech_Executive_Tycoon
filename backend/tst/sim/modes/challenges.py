"""Challenge rules (docs/formulas.md 63.2, M51): rules a player adds to a new game or scenario.
Each is enforced as a refusal with the rule named (`check`, called by `apply_action` for every
action, the player's, a delegate's or an automated one), and each multiplies the company score
the result screen shows (`score_mult`, `challenges.<rule>.score_mult`). `hard_rivals` changes no
action: rivals' products weigh in their markets at their quality x
`challenges.hard_rivals.quality_mult` (11.6), the player's group's at their own.

A game without challenge rules has none of this: `check` returns at once and the quality
multiplier is 1, so it plays exactly as before (63.4 target 3)."""

from __future__ import annotations

from typing import Final, Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import ChallengeRefusedError, InvalidModeError
from tst.sim.modes.models import GameMode
from tst.sim.state import GameState, ultimate_owner

type Rule = Literal[
    "bootstrapped", "hardware_only", "no_acquisitions", "one_region", "hard_rivals", "no_automation"
]
RULES: Final[tuple[Rule, ...]] = (
    "bootstrapped",
    "hardware_only",
    "no_acquisitions",
    "one_region",
    "hard_rivals",
    "no_automation",
)
# action kinds each rule refuses outright (others are checked by their content below)
FUNDING: Final = frozenset(
    {
        "start_round",
        "accept_term_sheet",
        "raise_safe",
        "accept_bridge",
        "take_loan",
        "hire_banks",
        "secondary_offering",
    }
)
ACQUISITIONS: Final = frozenset({"bid_for_company", "buy_stake", "buy_out_minorities"})
AUTOMATION: Final = frozenset({"set_area_owner", "set_ceo_authority"})
UNITS: Final = "units"  # categories.yaml revenue_model: a hardware category sells units
REASONS: Final[dict[Rule, str]] = {
    "bootstrapped": "the Bootstrapped challenge: no outside funding",
    "hardware_only": "the Hardware only challenge: only products that sell units",
    "no_acquisitions": "the No acquisitions challenge: no takeovers or stakes",
    "one_region": "the One region challenge: no launches outside your home region",
    "hard_rivals": "the Hard rivals challenge",
    "no_automation": "the No automation challenge: you make every call yourself",
}


LABELS: Final[dict[Rule, tuple[str, str]]] = {  # (label, what it means) for the screens
    "bootstrapped": (
        "Bootstrapped",
        "No outside funding: no rounds, SAFEs, bridges, loans or IPO.",
    ),
    "hardware_only": ("Hardware only", "Only products that sell units: devices, chips, cars."),
    "no_acquisitions": ("No acquisitions", "No takeover bids, stakes or minority buy-outs."),
    "one_region": ("One region", "Sell only in your home region: no region launches."),
    "hard_rivals": ("Hard rivals", "Rivals' products weigh in their markets at 1.2x quality."),
    "no_automation": (
        "No automation",
        "No automation areas, seat authority or CEO scopes: every call is yours.",
    ),
}


def difficulty(wins: int | None, balance: Balance) -> str | None:
    """A scenario's difficulty from the sensible script's wins on seeds 1-10 (63.3): hard at
    or below the first band, medium to the second, else easy; None when not rated."""
    if wins is None:
        return None
    hard, medium = balance.challenges.difficulty_wins
    return "hard" if wins <= hard else "medium" if wins <= medium else "easy"


def rules_of(mode: GameMode | None) -> tuple[str, ...]:
    return () if mode is None else mode.challenges


def validate(chosen: tuple[str, ...]) -> tuple[str, ...]:
    """The rules in RULES order, each once; InvalidModeError for an unknown one."""
    unknown = [r for r in chosen if r not in RULES]
    if unknown:
        raise InvalidModeError(f"unknown challenge {unknown[0]!r}")
    return tuple(r for r in RULES if r in chosen)


def _refuse(rule: Rule) -> ChallengeRefusedError:
    return ChallengeRefusedError(f"Refused by {REASONS[rule]}.")


def check(state: GameState, action: object, data: GameData) -> None:
    """Raise ChallengeRefusedError when one of the game's challenge rules forbids `action`."""
    chosen = rules_of(state.mode)
    if not chosen:
        return
    kind = getattr(action, "kind", "")
    if "bootstrapped" in chosen and kind in FUNDING:
        raise _refuse("bootstrapped")
    if "no_acquisitions" in chosen and kind in ACQUISITIONS:
        raise _refuse("no_acquisitions")
    if "one_region" in chosen and kind == "launch_in_region":
        raise _refuse("one_region")
    if "no_automation" in chosen and (
        kind in AUTOMATION or (kind == "set_authority" and getattr(action, "enabled", False))
    ):
        raise _refuse("no_automation")
    if "hardware_only" in chosen and kind == "create_product":
        category = getattr(action, "category", "")
        if data.category(category).revenue_model != UNITS:
            raise _refuse("hardware_only")


def score_mult(mode: GameMode | None, balance: Balance) -> float:
    """The product of the game's rules' score multipliers (1 without any)."""
    out = 1.0
    for rule in rules_of(mode):
        out *= balance.challenges.rules[rule].score_mult
    return out


def rival_quality_mult(state: GameState, balance: Balance) -> float:
    """The quality rivals' products weigh at in their markets: x quality_mult with Hard rivals."""
    if "hard_rivals" not in rules_of(state.mode):
        return 1.0
    return balance.challenges.hard_rivals_quality_mult


def is_rival_product(state: GameState, company_id: int) -> bool:
    """A product of a company outside the player's group."""
    return ultimate_owner(state, company_id) != state.player.id

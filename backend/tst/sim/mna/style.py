"""How a rival decides (formulas.md 15.3, 28.5): by its personality, or a kept brand by the
personality its parent's directive maps to (grow aggressive, harvest cost_leader, defend
premium). Kept apart so the rival decision code imports only this."""

from __future__ import annotations

from tst.sim.mna.models import DIRECTIVE_PERSONALITY
from tst.sim.state import CompanyState, GameState

DEFAULT = "fast_follower"


def style(state: GameState, company: CompanyState) -> str:
    if company.parent_id is None:
        return company.personality or DEFAULT
    acquisition = next((a for a in reversed(state.acquisitions) if a.target_id == company.id), None)
    return DIRECTIVE_PERSONALITY[acquisition.directive if acquisition is not None else "grow"]

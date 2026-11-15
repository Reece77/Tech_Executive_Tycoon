"""Which companies automation runs for (docs/formulas.md 40.1, 40.8; M27b sub-task 1).

The player's company and every subsidiary of the player's group (31.4). Inside a subsidiary
its CEO (the board's choice, 29.4's leader) may own every area, and the mandate is the
guardrail: a commitment above the mandate's capex limit, or a move into a category or region
the mandate leaves out, becomes a proposal. Proposals made inside a subsidiary are filed with
the player (the player's inbox and proposals), holding the subsidiary's id; approving one runs
the action as the proposing owner (or the subsidiary's CEO), so it posts to the subsidiary's
own books. The founder's actions and the two never-actions (a grey route, a contract's
termination: 40.7 target (c)) record the founder as their required actor on the proposal and
always run as the founder (M36r, Codex review 7 finding 1).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.automation.models import AreaOwner
from tst.sim.org.models import Proposal
from tst.sim.state import GameState, mandate_of

COMPANY_PARAM: Final = "company_id"  # a proposal's param: the group company it acts for
ACTOR_PARAM: Final = "actor"  # a proposal's param: who must carry it out (M36r)
FOUNDER: Final = "founder"  # ACTOR_PARAM's value: only the founder


def founder_only(kind: str | None) -> bool:
    """The founder's actions (M27b) and the never-actions (40.7 target (c)): never a
    delegate's, approved or not."""
    from tst.sim.automation.config import FOUNDER_ACTIONS, NEVER_ACTIONS

    return kind in FOUNDER_ACTIONS or kind in NEVER_ACTIONS


def is_group_subsidiary(state: GameState, company_id: int) -> bool:
    from tst.sim.group.subsidiaries import is_subsidiary

    return is_subsidiary(state, company_id)


def companies(state: GameState) -> list[int]:
    """The player's company first, then its group's subsidiaries by id."""
    from tst.sim.group.subsidiaries import subsidiaries

    return [state.player.id, *sorted(subsidiaries(state))]


def in_scope(state: GameState, company_id: int) -> bool:
    return company_id == state.player.id or is_group_subsidiary(state, company_id)


def subsidiary_ceo(state: GameState, company_id: int) -> int | None:
    """A subsidiary's CEO (31.4: its leader, as the board names it)."""
    from tst.sim.press.names import rival_ceo_id

    if not is_group_subsidiary(state, company_id):
        return None
    return rival_ceo_id(state, company_id)


def guarded(state: GameState, owner: AreaOwner) -> AreaOwner:
    """The owner as it runs this month: inside a subsidiary whose mandate sets a capex limit,
    the money limit is the lower of the two (31.4's mandate is the guardrail)."""
    if owner.company_id == state.player.id:
        return owner
    mandate = mandate_of(state, owner.company_id)
    if mandate is None or mandate.capex_limit_cents <= 0:
        return owner
    return replace(owner, limit_cents=min(owner.limit_cents, mandate.capex_limit_cents))


def outside_mandate(
    state: GameState, company_id: int, category: str | None, region: str | None
) -> bool:
    """A move into a category or region the subsidiary's mandate leaves out (31.4)."""
    if company_id == state.player.id:
        return False
    mandate = mandate_of(state, company_id)
    if mandate is None:
        return False
    if category is not None and mandate.categories and category not in mandate.categories:
        return True
    return region is not None and bool(mandate.regions) and region not in mandate.regions


def acting_for(proposal: Proposal) -> int:
    """The company an automation proposal acts for: its own, or the subsidiary it names."""
    params = dict(proposal.params)
    value = params.get(COMPANY_PARAM)
    return int(value) if value is not None else proposal.company_id


def proposal_actor(state: GameState, proposal: Proposal, founder_id: int) -> int:
    """Who carries out an approved automation proposal: the founder for the player's company,
    for a proposal whose required actor is the founder, and for a founder-only kind (a proposal
    filed before M36r recorded none); inside a subsidiary otherwise the proposing owner while
    still on its staff, else its CEO."""
    import json

    from tst.sim.errors import InvalidActionError

    company = acting_for(proposal)
    params = dict(proposal.params)
    kind = json.loads(str(params.get("action", "{}"))).get("kind")
    if company == state.player.id or params.get(ACTOR_PARAM) == FOUNDER or founder_only(kind):
        return founder_id
    e = state.employment_of(proposal.person_id)
    if e is not None and e.company_id == company and e.status == "active":
        return proposal.person_id
    ceo = subsidiary_ceo(state, company)
    if ceo is None:
        raise InvalidActionError(f"nobody at {state.company(company).name} can carry it out")
    return ceo

"""M&A actions (docs/formulas.md 28, M14): diligence, bids, a deal's mode, abandoning a
deal, accepting an antitrust remedy, and a kept brand's directive. The rules live in
tst.sim.mna; this module checks the actor and spends energy."""

from __future__ import annotations

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerBalances
from tst.sim.mna import antitrust, deals, integration
from tst.sim.mna.antitrust import AcceptRemedy
from tst.sim.mna.deals import AbandonDeal, BidForCompany, SetDealMode, StartDiligence
from tst.sim.mna.integration import SetDirective
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type MnaAction = (
    StartDiligence | BidForCompany | SetDealMode | AbandonDeal | AcceptRemedy | SetDirective
)
MNA_ACTION_TYPES: dict[str, type[MnaAction]] = {
    "start_diligence": StartDiligence,
    "bid_for_company": BidForCompany,
    "set_deal_mode": SetDealMode,
    "abandon_deal": AbandonDeal,
    "accept_remedy": AcceptRemedy,
    "set_directive": SetDirective,
}


def apply_mna(
    state: GameState,
    action: MnaAction,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)

    def spend(s: GameState, cost: int) -> GameState:
        return spend_energy(s, action.actor_id, action.kind, balance, cost=cost)

    match action:
        case StartDiligence():
            out = deals.start_diligence(state, action, company, balances, balance, data, spend)
            return Outcome(out.state, out.entries, out.logs)
        case BidForCompany():
            out = deals.make_offer(state, action, company, rng, balances, balance, data, spend)
            new = out.state
            founder = new.founder_of(company)
            if action.hostile and founder is not None and new.company(company).is_player:
                from tst.sim.founder.persona import note  # M24 (32.4)

                new = note(new, founder.id, "hostile_bid", balance)
                if out.result == "tender_failed":
                    new = note(new, founder.id, "failed_tender", balance)
            return Outcome(new, out.entries, out.logs)
        case SetDealMode():
            return Outcome(deals.set_deal_mode(state, action, company, balance))
        case AbandonDeal():
            return Outcome(deals.abandon_deal(state, action, company))
        case AcceptRemedy():
            new, logs = antitrust.accept_remedy(state, action, company, rng, balance, data)
            return Outcome(new, (), tuple(logs))
        case SetDirective():
            state = spend(state, balance.mna.directive_energy)
            return Outcome(integration.set_directive(state, action, company))

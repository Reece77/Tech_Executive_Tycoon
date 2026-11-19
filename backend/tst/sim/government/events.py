"""The open letter after a defence award (docs/formulas.md 57.4; data/events/government.yaml).

The engine queues `defence_open_letter` (trigger `government`) for the month after an award
whose staff reaction drew a letter. The answer, applied by the engine (`government_step`):

- **carry_on**: the contract stands; U(`resign_share`) of the objectors (rounded, at least one)
  resign (a month's notice), drawn with stream `defence` (4, company_id, turn);
- **withdraw**: the contract is terminated (no more revenue; past performance unaffected) and
  consumer lines win back `withdraw_brand` brand points;
- **ethics_board**: an ethics board costs `board_cents` (6990); no one resigns.

Left unanswered, the first choice (carry_on) applies at Continue."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent
from tst.sim.government import draws
from tst.sim.ledger import BIDS_CLEARANCES, CASH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment, with_product


def government_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    record = state.defence_record(event.company_id)
    if record is None or record.letter_turn is None:
        return state, [], []
    rb = balance.government.reputation
    turn = state.turn
    cid = event.company_id
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if step == "carry_on":
        staff = {e.person_id for e in state.staff(cid) if e.status == "active"}
        objecting = [p for p in record.objectors if p in staff]
        g = draws.gen(RngFactory(state.save_meta.master_seed), turn, draws.REACTION, cid, turn)
        share = rb.resign_share.lo + (rb.resign_share.hi - rb.resign_share.lo) * float(g.random())
        n = max(1, round(share * len(objecting))) if objecting else 0
        order = sorted(objecting, key=lambda _: float(g.random()))
        for pid in order[:n]:
            job = state.employment_of(pid)
            if job is None or job.status != "active":
                continue
            state = with_employment(
                state, replace(job, status="notice", end_turn=turn + 1, end_reason="resigned")
            )
            person = state.person(pid)
            logs.append(
                inbox_item(
                    turn,
                    cid,
                    "resigned",
                    link_kind="person",
                    link_id=pid,
                    name=f"{person.first_name} {person.last_name}",
                )
            )
    elif step == "withdraw" and record.contract_id is not None:
        state = replace(
            state,
            gov_contracts=tuple(
                replace(c, status="terminated", month=None) if c.id == record.contract_id else c
                for c in state.gov_contracts
            ),
        )
        for p in state.products:
            if p.company_id == cid and p.status == "live" and p.category in rb.consumer_categories:
                state = with_product(
                    state, replace(p, brand=min(100.0, p.brand + rb.withdraw_brand))
                )
    elif step == "ethics_board" and rb.board_cents > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=cid,
                memo="Ethics board for defence work",
                debit=BIDS_CLEARANCES,
                credit=CASH,
                amount=rb.board_cents,
            )
        )
    state = replace(
        state,
        defence_records=tuple(
            replace(r, letter_turn=None) if r.company_id == cid else r
            for r in state.defence_records
        ),
    )
    logs.append(inbox_item(turn, cid, "defence_letter_answered", step=step))
    return state, entries, logs

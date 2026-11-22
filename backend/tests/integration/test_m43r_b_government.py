"""M43r lane B, finding 5 (Codex review 9): a classified contract keeps its clearance after its
tender is pruned, across a cold reload; a save from before M43r is handled explicitly."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy import update

from tests.helpers import make_person, with_employee
from tst.db.models import GovernmentRecordRow, SaveMetaRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.facilities.models import Facility
from tst.sim.government import delivery, tenders
from tst.sim.government.models import Bid, Clearance, FacilityClearance, Tender
from tst.sim.ledger import GOVERNMENT_REVENUE
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_facility, with_product

JAN_2031 = 252


def _classified(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int]:
    """A save in January 2031 with a five-year secret defence contract awarded in 2027 (its
    tender past the retention window), cleared staff and a cleared facility."""
    b = loaded.balance
    path = create_save(
        "classified", 7, "funded_spinout", company_name="Def Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2031)
        new = with_company(new, replace(new.player, stage=4))
        pid, ids = new.next_ids.take("product")
        new = replace(
            with_product(
                new,
                Product(
                    id=pid,
                    company_id=new.player.id,
                    category="cloud_hosting",
                    name="Def Cloud",
                    status="live",
                    quality=85.0,
                    feature_points=500.0,
                    brand=40.0,
                    marketing_budget_cents=0,
                    created_turn=0,
                    launched_turn=0,
                ),
            ),
            next_ids=ids,
        )
        award = JAN_2031 - b.government.tenders.history_months - 2
        tender = Tender(
            id=9100,
            government="us",
            area="cloud",
            buyer="defence",
            title="Secret cloud",
            announce_turn=award - 5,
            close_turn=award - 2,
            award_turn=award,
            value_cents=6_000_000_000,
            term_months=60,
            base_months=48,
            contract="fixed_price",
            clearance="secret",
            status="awarded",
        )
        need = b.government.clearances.required["secret"]
        for i in range(need):
            new = with_employee(loaded, new, make_person(loaded, 7100 + i), 10_000_000)
        staff = [e.person_id for e in new.staff(new.player.id)][-need:]
        assert len(staff) >= need
        new = with_facility(
            new,
            Facility(
                id=8100,
                company_id=new.player.id,
                kind="data_centre_general",
                region="north_america",
                capacity=100,
                on_time=100,
                ordered_turn=0,
                ready_turn=0,
                late_turn=0,
                capex_cents=1,
                input_index=1.0,
                capex_paid_cents=1,
                status="live",
            ),
        )
        state, contract = delivery.start(
            replace(new, turn=award), tender, _bid(new, tender, pid), b, loaded.game_data
        )
        new = replace(
            state,
            turn=JAN_2031,
            tenders=(tender,),
            clearances=tuple(
                Clearance(p, new.player.id, "secret", 0, 1, "cleared", "cleared", 1)
                for p in staff[:need]
            ),
            facility_clearances=(FacilityClearance(8100, new.player.id, 0, 1, "cleared"),),
        )
        sync_state(session, old, new)
        session.get(SaveMetaRow, 1).current_turn = JAN_2031  # type: ignore[union-attr]
        session.commit()
    return path, contract.id


def _bid(state: GameState, tender: Tender, pid: int) -> Bid:
    return Bid(1, tender.id, state.player.id, pid, tender.value_cents, (), tender.award_turn)


def _revenue(entries: list) -> int:
    return -sum(
        line.amount for e in entries for line in e.lines if line.account == GOVERNMENT_REVENUE
    )


def test_a_classified_contract_needs_its_clearance_after_the_tender_is_pruned(
    tmp_path: Path, loaded: LoadedData
) -> None:
    b = loaded.balance
    path, cid = _classified(tmp_path, loaded)
    with open_session(path) as session:
        old = load_state(session)
        assert old.tender(9100) is not None
        pruned = tenders.prune(old, b)
        assert pruned.tender(9100) is None  # past the retention window: pruned
        sync_state(session, old, pruned)
        session.commit()
    with open_session(path) as session:
        cold = load_state(session)  # a cold reload: the tender is gone
    assert cold.tender(9100) is None
    contract = next(c for c in cold.gov_contracts if c.id == cid)
    assert contract.clearance == "secret" and contract.status == "active"
    rng = RngFactory(7)
    _, entries, _ = delivery.month(cold, rng, b)
    assert _revenue(entries) > 0  # still cleared: it delivers
    state = replace(cold, clearances=())  # the last qualifying clearance goes
    for _ in range(b.government.delivery.lapse_months):
        state, entries, _ = delivery.month(state, rng, b)
        assert _revenue(entries) == 0
        state = replace(state, turn=state.turn + 1)
    assert next(c for c in state.gov_contracts if c.id == cid).status == "defaulted"


def test_a_save_from_before_m43r_is_handled_explicitly(tmp_path: Path, loaded: LoadedData) -> None:
    """A contract saved without its clearance takes its tender's on load while the tender is
    kept; once the tender is gone it needs the strictest level its buyer's tenders are drawn at."""
    b = loaded.balance
    path, cid = _classified(tmp_path, loaded)
    with open_session(path) as session:
        for row in session.query(GovernmentRecordRow).filter_by(kind="gov_contracts"):
            data = {k: v for k, v in row.data.items() if k != "clearance"}
            session.execute(
                update(GovernmentRecordRow).where(GovernmentRecordRow.n == row.n).values(data=data)
            )
        session.commit()
    with open_session(path) as session:
        kept = load_state(session)
    assert next(c for c in kept.gov_contracts if c.id == cid).clearance == "secret"
    legacy = next(c for c in kept.gov_contracts if c.id == cid)
    gone = replace(kept, tenders=(), gov_contracts=(replace(legacy, clearance=None),))
    assert delivery.requirement(gone, gone.gov_contracts[0], b) == "top_secret"
    civil = replace(gone.gov_contracts[0], buyer="civil")
    assert delivery.requirement(gone, civil, b) == "secret"
    _, entries, _ = delivery.month(gone, RngFactory(7), b)
    assert _revenue(entries) == 0  # cleared at secret only: not enough

"""M15b polish (an M13 follow-up): preferred shares and converted SAFEs become common at the
IPO, the cap table's count unchanged, and the preferred equity moves to common equity."""

from __future__ import annotations

from dataclasses import replace

from tests.unit.test_m13_ipo import LOADED, MRR, OP, eligible, month, step, through_roadshow
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.models import CapEntry
from tst.sim.ledger import COMMON_EQUITY, PREFERRED_EQUITY
from tst.sim.markets_public.public import public_month
from tst.sim.rng import RngFactory
from tst.sim.state import listing_of, with_cap_entry


def test_preferred_shares_convert_to_common_at_the_listing() -> None:
    state = through_roadshow(eligible())
    cid = state.player.id
    eid, ids = state.next_ids.take("cap_entry")
    held = CapEntry(eid, cid, "firm", "preferred_a", 1_000_000, 0, firm="first_round")
    state = with_cap_entry(replace(state, next_ids=ids), held)
    state, _, _ = month(state)
    state, _ = step(state, "price_range")
    before = fd_shares(state, cid)
    priced = listing_of(state, cid)
    assert priced is not None and priced.status == "priced"
    out, entries, _ = public_month(
        state,
        RngFactory(1),
        LOADED.balance,
        LOADED.game_data,
        {cid: MRR},
        {cid: OP},
        {cid: 100_000_000_00},
        {cid: 7_000_000_00},
    )
    assert all(c.share_class == "common" for c in out.cap_entries if c.company_id == cid)
    listing = listing_of(out, cid)
    assert listing is not None and listing.status == "listed"
    assert fd_shares(out, cid) == before + listing.new_shares  # nothing but the new shares
    (moved,) = [e for e in entries if "convert" in e.memo]
    lines = {ln.account: ln.amount for ln in moved.lines}
    assert lines[PREFERRED_EQUITY] == 7_000_000_00 == -lines[COMMON_EQUITY]
    assert all(sum(ln.amount for ln in e.lines) == 0 for e in entries)

"""Explain for M44's numbers (docs/formulas.md 57.2): a bid's score band. The player's own terms
only (price, technical merit, past performance and their weights), each as a band; never a
rival's bid or an award draw (57.7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.government import awards

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def bid_score(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A decided bid's weighted terms, each rounded down to its band (57.2)."""
    if not entity:
        return _none(b, m, "bid")
    bid_id = _id(entity, "bid")
    state = b.state
    bid = next((x for x in state.gov_bids if x.id == bid_id), None)
    if bid is None or bid.company_id != state.player.id:
        raise _bad(f"no bid {bid_id} of yours")
    tender = state.tender(bid.tender_id)
    bal = b.data.balance
    title = tender.title if tender is not None else f"Bid {bid_id}"
    if bid.terms is None or tender is None:
        reasons = "; ".join(bid.reasons) or "the award has not been made yet"
        return b._out(m, entity, None, [], f"No score: {reasons}.", (), [], title)
    w = awards.weights(tender, bal)
    width = bal.government.bids.band

    def band(x: float) -> float:
        return float(awards.band_of(x, bal))

    t = bid.terms

    def line(label: str, x: float, weight: float) -> Item:
        lo = band(x)
        return Item(
            f"{label} (band {lo:.0f}-{lo + width:.0f}) x {weight:.2f}", lo * weight, "points"
        )

    items = [
        line("Price", t.price, w.price),
        line("Technical merit", t.technical, w.technical),
        line("Past performance", t.past_performance, w.past_performance),
    ]
    capture = bal.government.bids.capture_weight
    won = tender.winning_band
    note = (
        "Evaluators score the lowest price 100 and others in proportion; technical merit is the"
        f" product's quality with the capture team's selling ({capture:.0%}); past performance is"
        " your delivered contracts' record. Bands only: rivals' bids are not published, only the"
        " lowest winner's band."
        + (f" Winning band: {won}-{won + width}." if won is not None else "")
    )
    return b._out(m, entity, band(t.weighted), items, note, (), [], title)

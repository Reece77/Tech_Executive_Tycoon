"""M13 persistence: listings, listed companies, guidance, month-end share prices, CEOs and
their decisions survive a save and reload; the live set matches `live_view`, the database
keeps every row, and the CEO counters continue from the largest stored id."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy import func, select

from tst.db.models import CeoDecisionRow, CeoRow, ShareMonthRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import live_view, load_state, read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.markets_public.models import (
    Analyst,
    Ceo,
    CeoDecision,
    Guidance,
    Listing,
    PublicCompany,
    ShareMonth,
)

CID = 1
TURN = 50


def _objects() -> dict[str, tuple[object, ...]]:
    listing = Listing(
        company_id=CID,
        bank="goldman",
        hired_turn=40,
        status="listed",
        filed_late=False,
        roadshow_turn=42,
        ambition="high",
        share_choice="middle",
        dual_class=True,
        demand=1.2345678901234,
        price_choice="raise",
        shares_before=12_000_000_000,
        new_shares=3_000_000_000,
        price_cents=2_150,
        gross_cents=6_450_000_000_000,
        fee_cents=451_500_000_000,
        first_day_return=0.1875,
        close_cents=2_553,
        listed_turn=44,
        ticker="TSTY",
    )
    public = PublicCompany(
        company_id=CID,
        listed_turn=44,
        ticker="TSTY",
        dual_class=True,
        listing_price_cents=2_150,
        price_cents=2_710,
        sentiment=-0.0312345,
        value_cents=40_000_000_000_000,
        analysts=(Analyst(0, 3_000, "buy"), Analyst(3, 2_500, "hold")),
        below_value_months=1,
        below_takeover_months=0,
        last_activist_turn=None,
        last_takeover_turn=47,
        beat_streak=2,
        miss_streak=0,
        results=("beat", "inline", "beat"),
        quarter_revenue_cents=9_000_000_000,
        quarter_op_cents=-1_000_000_000,
        dividend_cents=12,
        lapsed_seats=1,
        pending=("activist_seat",),
    )
    guidance = (
        Guidance(CID, 45, 8_000_000_000, 1_200, 7_900_000_000, 1_150, True),
        Guidance(
            CID,
            48,
            9_000_000_000,
            1_300,
            9_100_000_000,
            1_250,
            False,
            actual_revenue_cents=9_200_000_000,
            actual_margin_bp=1_310,
            result="beat",
            price_before_cents=2_600,
            price_after_cents=2_710,
        ),
    )
    shares = 15_000_000_000
    months = (
        ShareMonth(CID, 10, 900, shares),  # older than the live window: kept in the database
        ShareMonth(CID, 44, 2_553, shares, "listing"),
        ShareMonth(CID, 48, 2_600, shares, "beat"),
        ShareMonth(CID, 49, 2_710, shares),
    )
    ceos = (
        Ceo(3, CID, 501, 20, ("hiring",), ended_turn=30, end_reason="dismissed"),  # long gone
        Ceo(4, CID, 502, 30, ("hiring", "pricing"), ended_turn=45, end_reason="replaced"),
        Ceo(
            7,
            CID,
            503,
            45,
            ("hiring", "pricing", "marketing"),
            low_months=2,
            price_anchors=((11, "smb", 4_900), (12, "enterprise", 120_000)),
        ),
    )
    decisions = (
        CeoDecision(2, CID, 502, 20, "hiring", "Hired a VP.", False),  # older: not loaded
        CeoDecision(
            5,
            CID,
            503,
            47,
            "pricing",
            "Cut the SMB price.",
            True,
            undo=(("kind", "set_price"), ("product_id", 11), ("price_cents", 4_900)),
            overridden_turn=48,
        ),
        CeoDecision(9, CID, 503, 49, "marketing", "Raised the budget.", False),
    )
    return {
        "listings": (listing,),
        "public_companies": (public,),
        "guidance": guidance,
        "share_months": months,
        "ceos": ceos,
        "ceo_decisions": decisions,
    }


def test_m13_round_trip(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "pub", 4, "funded_spinout", company_name="Pub Co", data=loaded, save_dir=tmp_path
    )
    objects = _objects()
    with open_session(path) as session, session.begin():
        read_meta(session).current_turn = TURN
        session.flush()
        before = load_state(session)
        assert before.turn == TURN
        assert before.listings == () and before.ceos == () and before.share_months == ()
        assert before.next_ids.ceo == 1 and before.next_ids.ceo_decision == 1
        sync_state(session, before, replace(before, **objects))  # type: ignore[arg-type]

    with open_session(path) as session:
        state = load_state(session)
        stored_months = session.scalar(select(func.count()).select_from(ShareMonthRow))
        stored_ceos = session.scalar(select(func.count()).select_from(CeoRow))
        stored_decisions = session.scalar(select(func.count()).select_from(CeoDecisionRow))
    assert (stored_months, stored_ceos, stored_decisions) == (4, 3, 3)

    assert state.listings == objects["listings"]
    assert state.public_companies == objects["public_companies"]
    assert state.guidance == objects["guidance"]
    # The live set: the last 36 month ends, CEOs serving or ended in the last 12 months, and
    # decisions of the last 12 months.
    assert state.share_months == objects["share_months"][1:]
    assert state.ceos == objects["ceos"][1:]
    assert state.ceo_decisions == objects["ceo_decisions"][1:]
    assert isinstance(state.ceos[-1].price_anchors[0], tuple)
    assert isinstance(state.ceo_decisions[0].undo[0], tuple)
    assert state.next_ids.ceo == 8 and state.next_ids.ceo_decision == 10
    written = replace(state, **objects)  # type: ignore[arg-type]
    assert live_view(written).share_months == state.share_months
    assert live_view(written).ceos == state.ceos
    assert live_view(written).ceo_decisions == state.ceo_decisions
    assert live_view(state) == state


def test_m13_changes_are_written(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "pub2", 4, "funded_spinout", company_name="Pub Co", data=loaded, save_dir=tmp_path
    )
    objects = _objects()
    with open_session(path) as session, session.begin():
        read_meta(session).current_turn = TURN
        session.flush()
        before = load_state(session)
        sync_state(session, before, replace(before, **objects))  # type: ignore[arg-type]
    with open_session(path) as session, session.begin():
        old = load_state(session)
        public = replace(old.public_companies[0], price_cents=2_800, results=("beat",) * 4)
        ceo = replace(old.ceos[-1], ended_turn=TURN, end_reason="left")
        new = replace(
            old,
            public_companies=(public,),
            share_months=(*old.share_months, ShareMonth(CID, TURN, 2_800, 15_000_000_000)),
            ceos=(*old.ceos[:-1], ceo),
        )
        sync_state(session, old, new)
    with open_session(path) as session:
        state = load_state(session)
    assert state.public_companies == (public,)
    assert state.share_months[-1] == ShareMonth(CID, TURN, 2_800, 15_000_000_000)
    assert state.ceos[-1] == ceo

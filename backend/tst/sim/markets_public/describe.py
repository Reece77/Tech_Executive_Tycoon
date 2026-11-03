"""Small readers of M13 state shared by the board, the event words and the API (25.7, 25.8).
They import only state and data, so the finance and events packages can use them."""

from __future__ import annotations

from collections import Counter

from tst.sim.data_models import Balance, GameData
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.models import PublicCompany, Rating
from tst.sim.state import GameState, ceo_of, listing_of, public_of

RATING_ORDER: tuple[Rating, ...] = ("buy", "hold", "sell")


def consensus_rating(public: PublicCompany) -> Rating | None:
    """The most common rating; a tie goes to hold, then to the rating nearer hold."""
    if not public.analysts:
        return None
    counts = Counter(a.rating for a in public.analysts)
    top = max(counts.values())
    tied = [r for r in RATING_ORDER if counts.get(r, 0) == top]
    return "hold" if "hold" in tied or len(tied) > 1 else tied[0]


def public_patience(state: GameState, company_id: int, balance: Balance) -> float:
    """Directors' patience once listed follows the analysts' consensus (25.7)."""
    public = public_of(state, company_id)
    rating = consensus_rating(public) if public is not None else None
    return balance.public.board.patience[rating] if rating is not None else 0.0


def founder_protected(state: GameState, company_id: int) -> bool:
    """Dual-class shares keep the founder's voting control: the board cannot remove them
    (25.2 step 3; M13 decision)."""
    public = public_of(state, company_id)
    return public is not None and public.dual_class


def public_names(
    state: GameState, data: GameData, balance: Balance, company_id: int
) -> dict[str, str]:
    """{bank}, {price}, {demand}, {ticker} and {ceo} for a `public` template (25.8): the book
    only as a word, never its draw."""
    names: dict[str, str] = {}
    listing = listing_of(state, company_id)
    if listing is not None:
        names["bank"] = data.bank(listing.bank).name
        if listing.price_cents:
            names["price"] = f"${listing.price_cents / pf.PCT:,.2f}"
        if listing.demand is not None:
            names["demand"] = pf.demand_word(listing.demand, balance.ipo)
        if listing.ticker:
            names["ticker"] = listing.ticker
    public = public_of(state, company_id)
    if public is not None:
        names["price"] = f"${public.price_cents / pf.PCT:,.2f}"
        names["ticker"] = public.ticker
    ceo = ceo_of(state, company_id)
    if ceo is not None:
        person = state.person(ceo.person_id)
        names["ceo"] = f"{person.first_name} {person.last_name}"
    return names

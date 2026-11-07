"""Rival CEO storylines (M15b addendum 12): a press piece about a rival's CEO, written from
engine facts only: an interview after their company's launch, a reply when their feud with
the player's founder crosses a story.feud_marks line, and a profile when their company
enters the Top 50 by revenue. The engine writes each as a template in the CEO's voice; the
LLM may rewrite its words within the monthly budget (16.8), never its facts.

At most story.max_per_month pieces a month, and one per rival: a feud reply first, then a
profile, then an interview; ties by rival id."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance
from tst.sim.events.render import full_name
from tst.sim.log import LogItem, inbox_item
from tst.sim.press.names import rival_ceo_id, rival_ceo_name
from tst.sim.rivals.characters import in_player_group
from tst.sim.state import GameState, feud_of

STORY: Final = "rival_story"
MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
PRIORITY: Final = ("reply", "profile", "interview")

# Each piece's headline and body in the rival's voice. {ceo} the CEO, {rival} their company,
# {product} the product launched, {company} the player's company, {founder} its founder,
# {place} the revenue rank, {mark} the feud line crossed.
TITLES: Final[dict[str, str]] = {
    "interview": "{ceo} on {product}",
    "reply": "{ceo} answers {founder}",
    "profile": "Profile: {ceo} of {rival}",
}
VOICE: Final[dict[str, dict[str, str]]] = {
    "aggressive": {
        "interview": "{ceo} sat down with the trade press after {rival} launched {product}: "
        '"We built it to win. Anyone selling in this market should be worried."',
        "reply": "Asked about {founder} and {company}, {ceo} did not hold back: "
        '"They talk. We ship. Watch the numbers."',
        "profile": "{rival} entered the Top 50 by revenue at #{place}. {ceo} says the company "
        '"is only getting started."',
    },
    "premium": {
        "interview": "{ceo} spoke to reporters after {rival} launched {product}: "
        '"We take our time and we get it right. Customers notice."',
        "reply": "{ceo} was asked about {founder} and {company}: "
        '"I would rather talk about our products than theirs."',
        "profile": "{rival} entered the Top 50 by revenue at #{place}. {ceo} credits "
        '"never cutting a corner."',
    },
    "fast_follower": {
        "interview": '{ceo} explained {product} to the press: "Others went first. We went better."',
        "reply": '{ceo} on {founder} and {company}: "Being first is not the same as being best."',
        "profile": "{rival} entered the Top 50 by revenue at #{place}. {ceo} calls it "
        '"patience paying off."',
    },
    "cost_leader": {
        "interview": "{ceo} pitched {product} to the press: "
        '"Same job, smaller bill. That is the story."',
        "reply": "{ceo} on {founder} and {company}: "
        '"Their customers keep calling us about the price."',
        "profile": "{rival} entered the Top 50 by revenue at #{place}. {ceo} says it was "
        '"built on value, one customer at a time."',
    },
}


def _revenue_ranked(state: GameState, turn: int) -> set[int]:
    return {r.company_id for r in state.rankings if r.turn == turn and r.kind == "revenue"}


def candidates(
    start: GameState, state: GameState, balance: Balance
) -> list[tuple[str, int, dict[str, str]]]:
    """(kind, rival id, facts) for this month's possible pieces, best first."""
    player = state.player
    founder = state.founder_of(player.id)
    founder_name = full_name(founder) if founder else "the founder"
    january = state.turn + 1
    new_top = _revenue_ranked(state, january) - _revenue_ranked(state, january - MONTHS_A_YEAR)
    places = {
        r.company_id: r.place for r in state.rankings if r.turn == january and r.kind == "revenue"
    }
    found: list[tuple[str, int, dict[str, str]]] = []
    for rival in state.rivals():
        if rival.failed_turn is not None or in_player_group(state, rival.id):
            continue
        ceo = rival_ceo_name(state, rival.id)
        if ceo is None or rival_ceo_id(state, rival.id) is None:
            continue
        facts = {"ceo": ceo, "rival": rival.name, "company": player.name, "founder": founder_name}
        now = feud_of(state, player.id, rival.id)
        then = feud_of(start, player.id, rival.id)
        was, score = (then.score if then else 0.0), (now.score if now else 0.0)
        crossed = [m for m in balance.story.feud_marks if was < m <= score]
        kinds: list[tuple[str, dict[str, str]]] = []
        if crossed:
            kinds.append(("reply", {**facts, "mark": f"{max(crossed):g}"}))
        if rival.id in new_top:
            kinds.append(("profile", {**facts, "place": str(places[rival.id])}))
        launched = sorted(  # a launch in the news this month (15.5), never a seeded product
            m.product_id
            for m in state.rival_moves
            if m.company_id == rival.id
            and m.turn == state.turn
            and m.action == "launched"
            and m.product_id is not None
        )
        product = state.product(launched[0]) if launched else None
        if product is not None:
            kinds.append(("interview", {**facts, "product": product.name}))
        if kinds:
            kind, f = min(kinds, key=lambda k: PRIORITY.index(k[0]))
            found.append((kind, rival.id, f))
    found.sort(key=lambda x: (PRIORITY.index(x[0]), x[1]))
    return found[: balance.story.max_per_month]


def month_stories(start: GameState | None, state: GameState, balance: Balance) -> list[LogItem]:
    """Phase 11, after the rankings: this month's pieces as inbox items linked to the rival."""
    out = []
    for kind, rival_id, facts in candidates(start or state, state, balance):
        personality = state.company(rival_id).personality or "aggressive"
        voice = VOICE.get(personality, VOICE["aggressive"])
        out.append(
            inbox_item(
                state.turn,
                state.player.id,
                STORY,
                link_kind="rival",
                link_id=rival_id,
                title=TITLES[kind].format(**facts),
                text=voice[kind].format(**facts),
                story=kind,
            )
        )
    return out

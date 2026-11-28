"""Template mode's words (ADR-0023 section 4): suggested replies and the counterpart's lines
without an LLM, from the same public view. Deterministic."""

from __future__ import annotations

from tst.conversations.view import PublicNegotiation

LINES = {
    "far_apart": "We're still a long way apart. The best we can do is {counter}.",
    "moving": "I hear you, and we can move: {counter}.",
    "close": "We're close now. {counter} and we have a deal.",
    "final_offer": "This is as far as we go: {counter}. Take it or leave it.",
    "accepted": "Agreed: {offer}. Let's put it on paper.",
    "walked_threat": "Then we're done here. That offer was never going to work for us.",
    "walked_patience": "We've gone round long enough. We're walking away from this one.",
}
OPENING = "Thanks for sitting down with us. Our position is {counter}."
# M57r-B (item 21): the reply call's fallback, a few words of tone before the engine's line
TONE_FALLBACK = "Let me be straight with you."


def opening_line(p: PublicNegotiation) -> str:
    return OPENING.format(counter=" and ".join(p.counter_shown))


def reply_line(p: PublicNegotiation) -> str:
    last = p.rounds[-1]
    return LINES[last.reason].format(
        counter=" and ".join(last.counter_shown), offer=" and ".join(last.offer_shown)
    )


def suggestions(p: PublicNegotiation, n: int) -> list[str]:
    """Three replies a player might send: a justification from the next unused fact, an
    appeal, and a request to close."""
    offer = " and ".join(p.offer_shown or p.counter_shown)
    unused = [f for i, f in enumerate(p.facts) if i not in p.used_facts]
    fact = unused[0] if unused else (p.facts[0] if p.facts else "the numbers")
    out = [
        f"{fact[0].upper()}{fact[1:]}, so we think there is room to move on your number.",
        "We'd like this to be the start of a long relationship. Can you meet us halfway?",
        f"We can close today at {offer}.",
    ]
    return out[:n]

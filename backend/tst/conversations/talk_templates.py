"""Template mode's words for talks (ADR-0023 section 4): questions, reactions and three
suggested answers without an LLM, from the same public view. Deterministic."""

from __future__ import annotations

from tst.conversations.talk_view import REACTIONS, PublicTalk


def question_line(p: PublicTalk, q: int) -> str:
    return p.questions[q].question


def speak_line(p: PublicTalk, reaction: str | None, next_q: int | None) -> str:
    parts = []
    if reaction is not None:
        parts.append(REACTIONS[reaction])
    if next_q is not None:
        parts.append(question_line(p, next_q))
    elif p.kind == "one_to_one":
        parts.append("Thanks for making the time.")
    else:
        parts.append("Thank you. That's all from me.")
    return " ".join(parts)


def suggestions(p: PublicTalk, q: int, n: int) -> list[str]:
    """Three answers a player might give, by kind."""
    it = p.questions[q]
    if p.kind == "one_to_one":
        out = ["I hear you. Tell me more about what would make this better."]
        if it.offer:
            out.append(f"I want you to grow here: I'll make sure of {it.offer}.")
        else:
            out.append("You're doing excellent work, and I want you to know it's noticed.")
        out.append("I need more from you over the next few months.")
        return out[:n]
    if p.kind == "crisis":
        out = [
            "We're sorry. This should not have happened, and we take full responsibility.",
            "We are still gathering the facts and will say more when we can.",
            "No comment at this time.",
        ]
        return out[:n]
    out = ["We're pleased with where this is going, and we'll let the results speak."]
    if it.offer:
        out.append(f"We'll go further: {it.offer}.")
    elif it.rival:
        out.append(f"{it.rival} should be worried. We're going to win this market.")
    else:
        out.append("This will lead the market. Nothing out there comes close.")
    out.append("No comment.")
    return out[:n]

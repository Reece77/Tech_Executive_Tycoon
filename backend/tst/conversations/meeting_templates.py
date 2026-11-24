"""Template mode's words for meetings (ADR-0023 section 4): questions, reactions and three
suggested answers without an LLM, from the same public view. Deterministic."""

from __future__ import annotations

from tst.conversations.meeting_view import REACTIONS, PublicMeeting


def question_line(p: PublicMeeting, item: int) -> str:
    return p.items[item].question


def speak_line(p: PublicMeeting, reaction: str | None, next_item: int | None) -> str:
    parts = []
    if reaction is not None:
        parts.append(REACTIONS[reaction])
    if next_item is not None:
        parts.append(question_line(p, next_item))
    else:
        parts.append("Thank you. That's everything on the agenda.")
    return " ".join(parts)


def suggestions(p: PublicMeeting, item: int, n: int) -> list[str]:
    """Three answers a player might give: an explanation from the question's first fact, a
    commitment or guidance answer where the question has a figure, and a candid concession."""
    it = p.items[item]
    fact = it.facts[0] if it.facts else "the numbers on the screen"
    out = [f"{fact[0].upper()}{fact[1:]}, and that is what the plan is built on."]
    if it.guidance:
        out.append(f"We reaffirm our guidance: {it.figure}.")
    elif it.figure:
        out.append(f"We commit to {it.figure}.")
    else:
        out.append("We'll come back to you on that next quarter.")
    out.append("You're right to raise it; we haven't got this right yet, and here's what changes.")
    return out[:n]

"""The template explanation (M25 section 1): what the player reads offline, over budget or
before asking. It names the largest drivers of the number's last change and their sizes,
from the breakdown alone ("Churn rose from 2.1% to 3.4%: the appeal gap to the best product
widened 6 points (about +0.8 points of churn) and ...")."""

from __future__ import annotations

from collections.abc import Sequence

from tst.advisor.model import Driver, Explanation, Unit

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
PRECISE_BELOW = 10  # tunable-exempt: percentages under 10 show two decimals
STEADY = 0.005  # tunable-exempt: a relative change this small reads as "held"


def amount(value: float, unit: Unit | None, signed: bool = False) -> str:
    """A number as the screens write it: $12,400, 3.4%, 14 people, 6.0 points."""
    sign = ("+" if value > 0 else "-" if value < 0 else "") if signed else ""
    v = abs(value) if signed else value
    match unit:
        case "cents":
            text = f"${abs(v) / CENTS_PER_DOLLAR:,.0f}"
            return (sign if signed else "-" if v < 0 else "") + text
        case "percent":
            return f"{sign}{v:.2f}%" if abs(v) < PRECISE_BELOW else f"{sign}{v:.1f}%"
        case "count":
            return f"{sign}{v:,.0f}"
        case "months":
            return f"{sign}{v:.1f} months"
        case _:
            return f"{sign}{v:.1f} points" if unit == "points" else f"{sign}{v:.1f}"


def _effect(d: Driver, metric_unit: Unit, metric: str) -> str:
    assert d.effect is not None
    if metric_unit == "percent":  # a share of a rate is in points of it
        return f"{'+' if d.effect >= 0 else '-'}{abs(d.effect):.2f} points of {metric}"
    return amount(d.effect, metric_unit, signed=True)


GENERIC_WORDS = frozenset(
    {
        "the",
        "base",
        "quality",
        "brand",
        "feature",
        "your",
        "rivals'",
        "change",
        "joined",
        "left",
        "new",
        "lost",
        "cash",
        "burn",
        "other",
        "baseline",
        "pay",
        "projected",
    }
)


def _mid(label: str) -> str:
    """A driver's label inside a sentence: common words lower-case, names as they are."""
    first = label.split(" ", 1)[0]
    return label[0].lower() + label[1:] if first.lower() in GENERIC_WORDS else label


def driver_text(d: Driver, metric_unit: Unit, metric: str, *, mid: bool = False) -> str:
    if mid:
        d = Driver(_mid(d.label), d.effect, d.change, d.unit, d.kind)
    if d.kind == "level":  # terms carry a sign; amounts (a price, a segment's size) do not
        unit = d.unit or metric_unit
        return f"{d.label} ({amount(d.effect or 0.0, unit, signed=unit == 'points')})"
    if d.change is not None and d.unit is not None:
        verb = "rose" if d.change > 0 else "fell" if d.change < 0 else "held"
        moved = f"{d.label} {verb}" + (f" {amount(abs(d.change), d.unit)}" if d.change else "")
        if d.effect is not None:
            return f"{moved} (about {_effect(d, metric_unit, metric)})"
        return moved
    assert d.effect is not None
    if metric_unit == "percent":
        return f"{d.label} {_effect(d, metric_unit, metric)}"
    return f"{d.label} {amount(d.effect, metric_unit, signed=True)}"


def ranked(drivers: Sequence[Driver]) -> list[Driver]:
    """Largest first; ties by label, so the text is stable."""
    return sorted((d for d in drivers if d.size > 0), key=lambda d: (-d.size, d.label))


def explain_text(e: Explanation, named: int) -> str:
    """The template explanation: the change and its `named` largest drivers."""
    unit = e.metric.unit
    label = e.subject if e.metric.scope == "account" else e.metric.label  # "Salaries ..."
    lower = label[0].lower() + label[1:]
    before, after = e.before, e.after
    top = ranked(e.drivers)[:named]
    if after is None:
        return f"There is no {lower} to explain yet."
    if before is None or abs(after - before) <= STEADY * max(abs(before), 1.0):
        head = f"{label} is {amount(after, unit)}"
        if before is not None:
            head = f"{label} held at {amount(after, unit)}"
    else:
        verb = "rose" if after > before else "fell"
        head = f"{label} {verb} from {amount(before, unit)} to {amount(after, unit)}"
    if not top:
        return head + "; no single driver stands out in its breakdown."
    texts = [driver_text(d, unit, lower, mid=True) for d in top]
    joined = texts[0] if len(texts) == 1 else ", ".join(texts[:-1]) + " and " + texts[-1]
    if all(d.kind == "level" for d in top):
        return f"{head}. The largest terms now: {joined}."
    return f"{head}: {joined}."

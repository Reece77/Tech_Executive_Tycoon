"""The yearly letter to shareholders (M43 sub-task 2): written each January in the founder's
voice from the conglomerate view's figures for the year just ended (engine facts only: the
player's own books, never a hidden value), by the LLM within 16's budget, else from this
template. Kept as an inbox item, so it stays in History."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from tst.sim.events.render import full_name
from tst.sim.group.conglomerate import CORPORATE, Books, Figures, growth
from tst.sim.state import GameState

LETTER: Final = "letter"  # LLMTextRow kind and inbox template
LETTER_WORDS = 250  # tunable-exempt: the ask's length (a page)
PERCENT = 100  # tunable-exempt: a fraction in percent
TOP = 3  # tunable-exempt: industries named in the template's opening
CENTS = 100  # tunable-exempt: units
THOUSAND, MILLION, BILLION = 1_000, 1_000_000, 1_000_000_000  # tunable-exempt: units
ASK = (
    "Write {founder}'s yearly letter to the shareholders of {company} about {year}, in the "
    "founder's own voice, first person, at most {words} words, starting 'Dear shareholders'. "
    "Plain, candid and specific: how the year went, which businesses earned their capital and "
    "which did not, and where capital went. Use only these facts; keep every name and number "
    "as given and add no new facts or forecasts."
)
SYSTEM = "You write short flavour text for a business game. Grounded, plain English."


def title(year: int) -> str:
    return f"Letter to shareholders, {year}"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x * PERCENT:.1f}%"


def _money(cents: int) -> str:
    """$1.2B, $340.5M, $64k, $900: a letter's figures (integer cents in, words out)."""
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    for unit, word in ((BILLION, "B"), (MILLION, "M")):
        if c >= unit * CENTS:
            return f"{sign}${c / (unit * CENTS):,.1f}{word}"
    if c >= THOUSAND * CENTS:
        return f"{sign}${c // (THOUSAND * CENTS):,}k"
    return f"{sign}${c // CENTS:,}"


def _lower(label: str) -> str:
    """'Chips and fabs' -> 'chips and fabs'; 'AI models' stays."""
    return label[:1].lower() + label[1:] if label[1:2].islower() else label


def facts(
    state: GameState, b: Books, year: int, labels: Mapping[str, str]
) -> tuple[str, list[str]]:
    """(the founder's name, the letter's facts) for `year`, from the books only."""
    founder = state.founder_of(state.player.id)
    name = full_name(founder) if founder is not None else "The founder"
    total = b.group(year)
    prior = b.group(year - 1) if year - 1 in b.years else None
    lines = [
        f"{state.player.name}'s revenue in {year} was {_money(total.revenue)}"
        + (
            f", against {_money(prior.revenue)} in {year - 1}"
            + (f" ({_pct(g[0])} growth)" if (g := growth([prior.revenue, total.revenue])) else "")
            if prior is not None
            else ""
        )
        + ".",
        f"Operating profit was {_money(total.operating_profit)} "
        f"(an operating margin of {_pct(total.operating_margin)}).",
        f"Capital employed at the year end was {_money(total.capital_employed)}"
        f" (a return on capital of {_pct(total.return_on_capital)}).",
    ]
    by = b.by_industry(year)
    ranked = sorted(
        ((k, f) for k, f in by.items() if k != CORPORATE and f.revenue > 0),
        key=lambda kv: (-kv[1].revenue, kv[0]),
    )
    for k, f in ranked:
        lines.append(
            f"{labels.get(k, k)}: revenue {_money(f.revenue)}, operating profit "
            f"{_money(f.operating_profit)}, return on capital {_pct(f.return_on_capital)}."
        )
    uses = b.uses.get(year)
    if uses is not None:
        spent = sorted(uses.capex.items(), key=lambda kv: (-kv[1], kv[0]))
        if spent:
            parts = ", ".join(f"{labels.get(k, k)} {_money(v)}" for k, v in spent)
            lines.append(f"Capital spending in {year}: {parts}.")
        if uses.stakes:
            lines.append(f"Acquisitions and stakes in {year}: {_money(uses.stakes)}.")
        if uses.returned:
            lines.append(f"Returned to shareholders in {year}: {_money(uses.returned)}.")
    return name, lines


def template(founder: str, company: str, year: int, b: Books, labels: Mapping[str, str]) -> str:
    """The letter without the LLM: the same facts in plain paragraphs."""
    total = b.group(year)
    prior = b.group(year - 1) if year - 1 in b.years else None
    g = growth([prior.revenue, total.revenue]) if prior is not None else []
    by = b.by_industry(year)
    ranked = sorted(
        ((k, f) for k, f in by.items() if k != CORPORATE and f.revenue > 0),
        key=lambda kv: (-kv[1].revenue, kv[0]),
    )
    opening = (
        f"Dear shareholders,\n\n{company} took in {_money(total.revenue)} of revenue in {year}"
        + (f", {_pct(g[0])} more than the year before" if g and g[0] >= 0 else "")
        + (f", {_pct(-g[0])} less than the year before" if g and g[0] < 0 else "")
        + f", and made {_money(total.operating_profit)} at the operating line."
    )
    paras = [opening]
    if ranked:
        named = "; ".join(
            f"{labels.get(k, k)} {_money(f.revenue)} at a {_pct(f.operating_margin)} margin"
            for k, f in ranked[:TOP]
        )
        best = max(
            (kv for kv in ranked if kv[1].return_on_capital is not None),
            key=lambda kv: (kv[1].return_on_capital or 0.0, kv[0]),
            default=None,
        )
        line = f"Our largest businesses were {named}."
        if best is not None and len(ranked) > 1:
            line += (
                f" {labels.get(best[0], best[0])} earned the most on the capital it uses "
                f"({_pct(best[1].return_on_capital)})."
            )
        paras.append(line)
    uses = b.uses.get(year)
    if uses is not None and (uses.capex or uses.stakes or uses.returned):
        bits: list[str] = []
        spent = sorted(uses.capex.items(), key=lambda kv: (-kv[1], kv[0]))
        if spent:
            bits.append(
                "we invested "
                + ", ".join(f"{_money(v)} in {_lower(labels.get(k, k))}" for k, v in spent)
            )
        if uses.stakes:
            bits.append(f"spent {_money(uses.stakes)} on acquisitions and stakes")
        if uses.returned:
            bits.append(f"returned {_money(uses.returned)} to you")
        paras.append(f"During {year} " + ", ".join(bits) + ".")
    paras.append(f"Thank you for your support.\n\n{founder}")
    return "\n\n".join(paras)


def prompt(founder: str, company: str, year: int, lines: Sequence[str]) -> tuple[str, str]:
    ask = ASK.format(founder=founder, company=company, year=year, words=LETTER_WORDS)
    return SYSTEM, ask + "\n\n" + "\n".join(f"- {line}" for line in lines)


def has_figures(b: Books, year: int) -> bool:
    """Whether the year has anything to write about."""
    figures: list[Figures] = list(b.by_industry(year).values()) if year in b.years else []
    return any(f.revenue or f.operating_costs for f in figures)

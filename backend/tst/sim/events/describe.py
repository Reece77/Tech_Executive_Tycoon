"""Event effects as plain numbers (docs/formulas.md 23.2, M10b; replaces 16.9's words with a
size): "+3 brand for Pipeline", "costs $8,000", "Priya Shah's morale +5", "-10 founder energy
next month", "+5% brand target for Pipeline for 12 months". Values are what the choice
applies; caps and trigger strengths are never shown.
"""

from __future__ import annotations

from tst.sim.data_models import Balance
from tst.sim.events.data import STAT_LABELS
from tst.sim.events.models import Effect, EventChoice, GameEvent, Modifier
from tst.sim.events.render import full_name
from tst.sim.state import GameState

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
PCT = 100  # tunable-exempt: percent
BP = 10_000  # tunable-exempt: basis points
MINUS = chr(0x2212)  # tunable-exempt: a real minus sign
DO_NOTHING = "Do nothing: no effect"
WHOLE = 0.05  # tunable-exempt: display rounding, shown without decimals below this
PAIR = 2  # tunable-exempt: two people


def signed(x: float) -> str:
    """+5, -10, +2.5: whole numbers without decimals, others to one decimal place."""
    whole = abs(x - round(x)) < WHOLE
    text = f"{abs(x):.0f}" if whole else f"{abs(x):.1f}"
    return f"{'+' if x >= 0 else MINUS}{text}"


def dollars(cents: float) -> str:
    return f"${round(abs(cents) / CENTS_PER_DOLLAR):,}"


def person_label(state: GameState, person_id: int) -> str:
    person = next((p for p in state.people if p.id == person_id), None)
    return full_name(person) if person else "someone who has left"


def who(state: GameState, target: str) -> str:
    """A target as words: a person's name, a unit, a pair, a product, or everyone."""
    kind, _, rest = target.partition(":")
    ids = [int(x) for x in rest.split("-") if x.isdigit()]
    if kind in ("person", "founder") and ids:
        return "your" if kind == "founder" else person_label(state, ids[0])
    if kind == "unit" and ids:
        unit = state.unit(ids[0])
        return unit.name if unit else "the team"
    if kind == "pair" and len(ids) == PAIR:
        return f"{person_label(state, ids[0])} and {person_label(state, ids[1])}"
    if kind == "product" and ids:
        product = state.product(ids[0])
        return product.name if product else "the product"
    return "everyone"


def _possessive(name: str) -> str:
    """'Priya Shah's', 'Everyone's', 'Your'."""
    if name == "your":
        return "Your"
    if name == "everyone":
        return "Everyone's"
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def modifier_text(state: GameState, stat: str, target: str, value_pct: float, months: int) -> str:
    """'+5% brand target for Pipeline for 12 months'."""
    name = who(state, target)
    label = STAT_LABELS.get(stat, stat.replace("_", " "))
    span = f"{months} month{'s' if months != 1 else ''}"
    if stat == "founder_energy":
        return f"{signed(value_pct)}% founder energy each month for {span}"
    place = " across the company" if target.startswith("company") else f" for {name}"
    return f"{signed(value_pct)}% {label}{place} for {span}"


def running_text(state: GameState, m: Modifier) -> str:
    """A running modifier with the months it has left this month included."""
    return modifier_text(state, m.stat, m.target, m.value_pct, m.end_turn - state.turn)


def effect_text(state: GameState, event: GameEvent, effect: Effect, balance: Balance) -> str:
    v = effect.value
    name = who(state, effect.target)
    match effect.type:
        case "morale_delta":
            return f"{_possessive(name)} morale {signed(v)}"
        case "relationship_delta":
            return f"{name} relationship {signed(v)}"
        case "cash_delta":
            return f"{'brings in' if v > 0 else 'costs'} {dollars(v)}"
        case "brand_delta":
            return f"{signed(v)} brand for {name}"
        case "quality_delta":
            return f"{signed(v)} quality for {name}"
        case "customers_pct":
            return f"{signed(v)}% customers for {name}"
        case "growth_boost":
            return f"{signed(v)} skill points for {name}"
        case "reveal_tag":
            return f"you learn more about {name}"
        case "energy_delta":
            return f"{signed(v)} founder energy next month"
        case "board_confidence":
            return f"{signed(v)} board confidence"
        case "salary_change":
            employment = state.employment_of(int(effect.target.partition(":")[2] or 0))
            raise_ = f"{signed(v)}% raise for {name}"
            if employment is None:
                return raise_
            return f"{raise_} (costs {dollars(employment.salary_cents * v / PCT)} a year)"
        case "resign":
            return f"{name} leaves"
        case "retain":
            return f"{name} stays: their notice is withdrawn"
        case "follow_up":
            return "a follow-up decision comes next month"
        case "loan_fee" | "loan_rate" | "loan_repay":
            return _loan_text(state, effect, balance)
        case "modifier":
            return modifier_text(state, effect.stat, effect.target, v, effect.months)
        case "press_step":  # M14b (29.1)
            return PRESS_STEP_TEXT.get(effect.stat, effect.stat)
        case "public_step":  # M13 (25)
            return PUBLIC_STEP_TEXT.get(effect.stat, effect.stat.replace("_", " "))
    return effect.type.replace("_", " ")


# M13 (25): what each IPO or public-company step does, in words (never a hidden number).
PUBLIC_STEP_TEXT: dict[str, str] = {
    "file": "the S-1 is filed; the roadshow starts next month",
    "file_late": "the S-1 is filed a month later",
    "ambition_high": "the bank aims high: a higher price, a weaker first day",
    "ambition_middle": "the bank aims for the middle of the range",
    "ambition_low": "the bank prices to pop: a lower price, a stronger first day",
    "sell_low": "sell 10% of the company as new shares",
    "sell_middle": "sell 15% of the company as new shares",
    "sell_high": "sell 25% of the company as new shares",
    "single_class": "one class of shares",
    "dual_class": "you keep voting control; the shares price 5% lower",
    "price_range": "list at the suggested price next",
    "price_raise": "list 10% above the suggested price",
    "price_cut": "list 15% below the suggested price",
    "pull": "no listing; part of the banks' fees is owed and the board is unhappy",
    "activist_seat": "the fund's nominee joins the board",
    "activist_buyback": "a buyback of 10% of cash next month",
    "activist_fight": "a proxy fight costs 1% of cash",
    "takeover_reject": "the approach is turned down",
    "takeover_talks": "talks lift the share price",
    "ceo_replace": "the CEO goes; you run the company again",
    "ceo_keep": "the CEO stays",
}


def _loan_text(state: GameState, effect: Effect, balance: Balance) -> str:
    """A lender event's choice with its amount (M10, 20.3)."""
    _, _, rest = effect.target.partition(":")
    loan = state.loan(int(rest)) if rest.isdigit() else None
    br = balance.debt.breach
    if loan is None:
        return "the loan has closed"
    if effect.type == "loan_rate":
        points = effect.value * br.rate_up_bp / PCT
        now = loan.rate_bp / PCT
        return f"the rate rises {points:g} points, to {now + points:.2f}%"
    share = br.repay_bp if effect.type == "loan_repay" else br.waiver_fee_bp
    cents = effect.value * loan.balance_cents * share / BP
    if effect.type == "loan_repay":
        return f"repays {dollars(cents)} of the balance from cash now"
    return f"a waiver fee of {dollars(cents)}"


def choice_texts(
    state: GameState, event: GameEvent, choice: EventChoice, balance: Balance
) -> list[str]:
    if not choice.effects:
        return [DO_NOTHING] if choice.do_nothing else []
    return [effect_text(state, event, e, balance) for e in choice.effects]


def month_choices(
    state: GameState, expired: tuple[Modifier, ...], company_id: int, balance: Balance
) -> str | None:
    """The month-end line (23.2): effects applied by this month's answers, and modifiers
    that started or expired. None when there is nothing to say."""
    parts: list[str] = []
    for event in state.events:
        if (
            event.company_id != company_id
            or event.resolved_turn != state.turn
            or event.chosen is None
        ):
            continue
        choice = event.choice(event.chosen)
        if choice is None:
            continue
        texts = [
            effect_text(state, event, e, balance) for e in choice.effects if e.type != "modifier"
        ]
        if texts:
            parts.append(f"{choice.label}: {', '.join(texts)}")
    started = [
        running_text(state, m)
        for m in state.modifiers
        if m.company_id == company_id and m.start_turn == state.turn
    ]
    if started:
        parts.append("Started: " + "; ".join(started))
    gone = [
        modifier_text(state, m.stat, m.target, m.value_pct, m.end_turn - m.start_turn)
        for m in expired
        if m.company_id == company_id
    ]
    if gone:
        parts.append("Expired: " + "; ".join(gone))
    return ". ".join(parts) + "." if parts else None


# M14b (29.1): a press moment's tones, in words (never a hidden number).
PRESS_STEP_TEXT: dict[str, str] = {
    "bold": "a bold claim: brand lifts for 6 months, and it can backfire if results disagree",
    "measured": "a measured answer: a small brand lift, no risk",
    "deflect": "no comment: credibility falls a little",
}

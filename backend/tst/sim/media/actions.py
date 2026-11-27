"""The player's media actions (ADR-0014; docs/formulas.md 65). They take effect at once and spend
the actor's energy (`media.energy`). A video, music or social line is made with `create_product` and
launched as any product; a title is green-lit here.

- **GreenlightTitle** (`greenlight`): a series, film or game with a budget (between the kind's
  `min_budget_share` and `max_budget_mult` of its typical budget at scale), optionally a signed
  creative lead (not leading another title in development), a unit, a sequel's original (a
  released title of the same kind), a game's platforms, monetisation, live service and PC store,
  and a series or film's window (`own`: on one of the company's live video lines).
- **CancelTitle** (`setting`): a title in development is cancelled and its book written off.
- **OverruleLead** (`overrule`): the player's cut over the lead's: the title's reach x (1 +
  `overrule_reach`), and the lead's reaction (tst.sim.media.talent).
- **CutBudget** (`overrule`): a lower budget (not below what is spent), and the lead's reaction.
- **MoveRelease** (`overrule`): the planned month later by `months`, and the lead's reaction.
- **SignLead** (`sign`): an open offer's lead to an overall deal of `years` (within
  `talent.deal_years`); refused without the cash for the up-front share.
- **LicenseTitles** (`license`): titles licensed in for a video line: a fee a year for `years`.
- **SetMediaLine** (`setting`): an ad tier (video, from media.yaml's month), ad load and format
  (social), moderation (social), ad pricing (consumer apps, only from `ads.consumer_apps_from`).
- **SetLiveService** (`setting`): a released free-to-play game's live-service updates on or off.
- **DivestRegion** (`setting`): sell a social line's users in a region a law names (tst.sim.media
  .social).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, MediaRuleError
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.media import talent, titles
from tst.sim.media.config import KINDS, MODERATION_LEVELS, PLATFORMS
from tst.sim.media.data import file, selling
from tst.sim.media.models import Licence, LineSetting, Title
from tst.sim.money import times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

MAX_NAME: Final = 80  # tunable-exempt: a name column's width


@dataclass(frozen=True, slots=True)
class GreenlightTitle:
    actor_id: int
    name: str
    title_kind: str  # series, film, game
    budget_cents: int
    genre: str = "drama"
    lead_person_id: int | None = None
    unit_id: int | None = None
    sequel_of: int | None = None
    platforms: tuple[str, ...] = ()
    monetisation: str = "premium"
    live_service: bool = False
    store: str = "default"
    window: str = "licensed"
    service_product_id: int | None = None
    kind: Literal["greenlight_title"] = "greenlight_title"

    def __post_init__(self) -> None:  # decision_log stores the platforms as a JSON list
        object.__setattr__(self, "platforms", tuple(self.platforms))


@dataclass(frozen=True, slots=True)
class CancelTitle:
    actor_id: int
    title_id: int
    kind: Literal["cancel_title"] = "cancel_title"


@dataclass(frozen=True, slots=True)
class OverruleLead:
    actor_id: int
    title_id: int
    kind: Literal["overrule_lead"] = "overrule_lead"


@dataclass(frozen=True, slots=True)
class CutBudget:
    actor_id: int
    title_id: int
    budget_cents: int
    kind: Literal["cut_budget"] = "cut_budget"


@dataclass(frozen=True, slots=True)
class MoveRelease:
    actor_id: int
    title_id: int
    months: int
    kind: Literal["move_release"] = "move_release"


@dataclass(frozen=True, slots=True)
class SignLead:
    actor_id: int
    year: int
    n: int
    years: int
    kind: Literal["sign_lead"] = "sign_lead"


@dataclass(frozen=True, slots=True)
class LicenseTitles:
    actor_id: int
    product_id: int
    fee_cents: int  # a year
    years: int
    kind: Literal["license_titles"] = "license_titles"


@dataclass(frozen=True, slots=True)
class SetMediaLine:
    actor_id: int
    product_id: int
    ad_tier: bool = False
    ad_load: float = 1.0
    format: str | None = None
    moderation: str = "standard"
    ad_pricing: bool = False
    kind: Literal["set_media_line"] = "set_media_line"


@dataclass(frozen=True, slots=True)
class SetLiveService:
    actor_id: int
    title_id: int
    on: bool
    kind: Literal["set_live_service"] = "set_live_service"


@dataclass(frozen=True, slots=True)
class DivestRegion:
    actor_id: int
    law_id: int
    kind: Literal["divest_region"] = "divest_region"


type MediaAction = (
    GreenlightTitle
    | CancelTitle
    | OverruleLead
    | CutBudget
    | MoveRelease
    | SignLead
    | LicenseTitles
    | SetMediaLine
    | SetLiveService
    | DivestRegion
)
ACTION_TYPES: Final[dict[str, type]] = {
    "greenlight_title": GreenlightTitle,
    "cancel_title": CancelTitle,
    "overrule_lead": OverruleLead,
    "cut_budget": CutBudget,
    "move_release": MoveRelease,
    "sign_lead": SignLead,
    "license_titles": LicenseTitles,
    "set_media_line": SetMediaLine,
    "set_live_service": SetLiveService,
    "divest_region": DivestRegion,
}


def _energy(state: GameState, actor_id: int, what: str, balance: Balance) -> GameState:
    return spend_energy(state, actor_id, what, balance, cost=balance.media.energy[what])


def _own_title(state: GameState, company: int, title_id: int) -> Title:
    t = state.media.title(title_id)
    if t is None or t.company_id != company:
        raise MediaRuleError(f"no title {title_id}")
    return t


def _with_title(state: GameState, title: Title) -> GameState:
    out = tuple(title if t.id == title.id else t for t in state.media.titles)
    return replace(state, media=replace(state.media, titles=out))


def _video_line(state: GameState, company: int, product_id: int | None, balance: Balance) -> int:
    lines = [
        p
        for p in state.company_products(company)
        if p.category == balance.media.streaming and selling(p)
    ]
    if product_id is not None:
        if not any(p.id == product_id for p in lines):
            raise MediaRuleError("that is not one of your live video lines")
        return product_id
    if not lines:
        raise MediaRuleError("a title on your own service needs a live video line")
    return lines[0].id


def greenlight(
    state: GameState,
    action: GreenlightTitle,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.title_kind not in KINDS:
        raise MediaRuleError(f"a title is a {', '.join(KINDS)}")
    name = action.name.strip()
    if not name or len(name) > MAX_NAME:
        raise MediaRuleError("a title needs a name of 1-80 characters")
    kind = balance.media.kind(action.title_kind)
    typical = titles.typical_budget_cents(kind, balance)
    lo, hi = times(typical, kind.min_budget_share), times(typical, kind.max_budget_mult)
    if not lo <= action.budget_cents <= hi:
        raise MediaRuleError(f"a {action.title_kind}'s budget is between {lo} and {hi} cents")
    first = max(1, action.budget_cents // kind.dev_months)
    if account_balance(balances, company, CASH) < first:
        raise InsufficientCashError(f"the first month's production needs {first} cents")
    lead = None
    if action.lead_person_id is not None:
        lead = state.media.lead(action.lead_person_id)
        if lead is None or lead.company_id != company:
            raise MediaRuleError("that person is not one of your signed creative leads")
        busy = any(
            t.lead_person_id == lead.person_id and t.stage == "development"
            for t in state.media.titles
        )
        if busy:
            raise MediaRuleError("that lead is already leading a title in development")
    if action.unit_id is not None:
        unit = state.unit(action.unit_id)
        if unit is None or unit.company_id != company or unit.status != "active":
            raise MediaRuleError("that is not one of your units")
    if action.sequel_of is not None:
        prev = state.media.title(action.sequel_of)
        if prev is None or prev.company_id != company or prev.stage != "released":
            raise MediaRuleError("a sequel follows one of your released titles")
        if prev.kind != action.title_kind:
            raise MediaRuleError("a sequel is the same kind as its original")
    platforms: tuple[str, ...] = ()
    window = "licensed"
    service = None
    if action.title_kind == titles.GAME:
        platforms = tuple(p for p in PLATFORMS if p in action.platforms)
        if not platforms or len(platforms) != len(set(action.platforms)):
            raise MediaRuleError(f"a game is for one or more of {', '.join(PLATFORMS)}")
        if action.monetisation not in ("premium", titles.F2P):
            raise MediaRuleError("a game is premium or free_to_play")
        if action.live_service and action.monetisation != titles.F2P:
            raise MediaRuleError("live service is for free-to-play games")
        if action.store not in ("default", titles.EPIC):
            raise MediaRuleError("a PC game's store is default or epic")
        if action.store == titles.EPIC and titles.PC not in platforms:
            raise MediaRuleError("Epic's store is for PC games")
    elif action.window == titles.OWN:
        window = titles.OWN
        service = _video_line(state, company, action.service_product_id, balance)
    elif action.window != "licensed":
        raise MediaRuleError("a series or film's window is own or licensed")
    state = _energy(state, action.actor_id, "greenlight", balance)
    title = Title(
        id=state.media.next_title_id(),
        company_id=company,
        name=name,
        kind=action.title_kind,
        genre=action.genre[:MAX_NAME] or "drama",
        budget_cents=action.budget_cents,
        greenlit_turn=state.turn,
        dev_months=kind.dev_months,
        release_turn=state.turn + kind.dev_months,
        lead_person_id=lead.person_id if lead is not None else None,
        unit_id=action.unit_id,
        sequel_of=action.sequel_of,
        platforms=platforms,
        monetisation=action.monetisation if action.title_kind == titles.GAME else "premium",
        live_service=action.live_service,
        store=action.store if action.title_kind == titles.GAME else "default",
        window=window,
        service_product_id=service,
    )
    state = replace(state, media=replace(state.media, titles=(*state.media.titles, title)))
    log = inbox_item(
        state.turn,
        company,
        "media_title_greenlit",
        link_kind="studio",
        link_id=title.id,
        title=name,
        kind=action.title_kind,
        budget_cents=action.budget_cents,
        release=format_turn(title.release_turn),
    )
    return Outcome(state, (), (log,))


def _in_development(state: GameState, company: int, title_id: int) -> Title:
    t = _own_title(state, company, title_id)
    if t.stage != "development":
        raise MediaRuleError("that title is not in development")
    return t


def _react(
    state: GameState, title: Title, what: str, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    title = replace(title, events=title.events + 1)
    state = _with_title(state, title)
    state, logs = talent.react(state, title, what, rng, balance, data)
    return state, tuple(logs)


def apply_media(
    state: GameState,
    action: MediaAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.media is None:
        raise MediaRuleError("this game has no media markets")
    company = acting_company(state, action.actor_id)
    match action:
        case GreenlightTitle():
            return greenlight(state, action, balance, data, balances)
        case CancelTitle():
            t = _in_development(state, company, action.title_id)
            state = _energy(state, action.actor_id, "setting", balance)
            t, entries = titles.cancel(t, state)
            return Outcome(_with_title(state, t), tuple(entries), ())
        case OverruleLead():
            t = _in_development(state, company, action.title_id)
            state = _energy(state, action.actor_id, "overrule", balance)
            t = replace(
                t,
                overrules=t.overrules + 1,
                reach=t.reach * (1 + balance.media.talent.overrule_reach),
            )
            state, logs = _react(state, t, "overrule", rng, balance, data)
            return Outcome(state, (), logs)
        case CutBudget():
            t = _in_development(state, company, action.title_id)
            kind = balance.media.kind(t.kind)
            floor = max(
                t.spent_cents,
                times(titles.typical_budget_cents(kind, balance), kind.min_budget_share),
            )
            if not floor <= action.budget_cents < t.budget_cents:
                raise MediaRuleError(f"a cut budget is below the budget and at least {floor} cents")
            state = _energy(state, action.actor_id, "overrule", balance)
            t = replace(t, budget_cents=action.budget_cents, cuts=t.cuts + 1)
            state, logs = _react(state, t, "cut", rng, balance, data)
            return Outcome(state, (), logs)
        case MoveRelease():
            t = _in_development(state, company, action.title_id)
            if action.months < 1:
                raise MediaRuleError("a release moves at least a month later")
            state = _energy(state, action.actor_id, "overrule", balance)
            t = replace(t, release_turn=t.release_turn + action.months, moves=t.moves + 1)
            state, logs = _react(state, t, "move", rng, balance, data)
            return Outcome(state, (), logs)
        case SignLead():
            offer = next(
                (o for o in state.media.offers if o.year == action.year and o.n == action.n), None
            )
            if offer is None or offer.status != "open":
                raise MediaRuleError("that creative lead is not on offer")
            years = balance.media.talent.deal_years
            if not years.lo <= action.years <= years.hi:
                raise MediaRuleError(f"an overall deal runs {years.lo:g}-{years.hi:g} years")
            c = talent.candidate(offer, rng, balance, data)
            fee = talent.fee_cents(c.creative, c.vision, 0.0, balance)
            upfront = times(fee, action.years, balance.media.talent.upfront_share)
            if account_balance(balances, company, CASH) < upfront:
                raise InsufficientCashError(f"the deal's up-front share needs {upfront} cents")
            state = _energy(state, action.actor_id, "sign", balance)
            state, entries, lead = talent.sign(
                state, offer, company, action.years, rng, balance, data
            )
            person = state.person(lead.person_id)
            log = inbox_item(
                state.turn,
                company,
                "media_lead_signed",
                link_kind="person",
                link_id=lead.person_id,
                name=f"{person.first_name} {person.last_name}",
                years=action.years,
                fee_cents=fee,
            )
            return Outcome(state, tuple(entries), (log,))
        case LicenseTitles():
            _video_line(state, company, action.product_id, balance)
            years = balance.media.streaming_service.licence_years
            if not years.lo <= action.years <= years.hi or action.fee_cents <= 0:
                raise MediaRuleError(f"a licence runs {years.lo:g}-{years.hi:g} years at a fee")
            state = _energy(state, action.actor_id, "license", balance)
            lic = Licence(
                id=state.media.next_licence_id(),
                company_id=company,
                product_id=action.product_id,
                fee_cents=action.fee_cents,
                from_turn=state.turn,
                to_turn=state.turn + action.years * 12,  # tunable-exempt: months a year
            )
            media = replace(state.media, licences=(*state.media.licences, lic))
            return Outcome(replace(state, media=media), (), ())
        case SetMediaLine():
            return _set_line(state, company, action, balance, data)
        case SetLiveService():
            t = _own_title(state, company, action.title_id)
            if t.kind != titles.GAME or t.monetisation != titles.F2P:
                raise MediaRuleError("live service is for free-to-play games")
            state = _energy(state, action.actor_id, "setting", balance)
            return Outcome(_with_title(state, replace(t, live_service=action.on)), (), ())
        case DivestRegion():
            from tst.sim.media import social

            state = _energy(state, action.actor_id, "setting", balance)
            state, sold, notes = social.divest(state, company, action.law_id, balance, data)
            return Outcome(state, tuple(sold), tuple(notes))
    raise MediaRuleError("unknown media action")


def _set_line(
    state: GameState, company: int, action: SetMediaLine, balance: Balance, data: GameData
) -> Outcome:
    mb = balance.media
    product = state.product(action.product_id)
    if product is None or product.company_id != company:
        raise MediaRuleError("that is not one of your products")
    old = state.media.setting(product.id) or LineSetting(product_id=product.id)
    new = replace(old)
    if product.category == mb.streaming:
        if action.ad_tier and state.turn < month_to_turn(file(data).ad_tier_from):
            raise MediaRuleError("ad tiers come later")
        new = replace(new, ad_tier=action.ad_tier)
    elif product.category == mb.social:
        lo, hi = mb.ads.load_range.lo, mb.ads.load_range.hi
        if not lo <= action.ad_load <= hi:
            raise MediaRuleError(f"ad load is between {lo:g} and {hi:g}")
        if action.moderation not in MODERATION_LEVELS:
            raise MediaRuleError(f"moderation is {', '.join(MODERATION_LEVELS)}")
        new = replace(new, ad_load=action.ad_load, moderation=action.moderation)
        if action.format is not None and action.format != old.format:
            from tst.sim.media import social

            if action.format not in social.arrived_formats(state, data):
                raise MediaRuleError("that format has not arrived")
            new = replace(new, format=action.format, format_turn=state.turn)
            if old.format is not None:  # a switch costs quality (65.5)
                cut = 1.0 - mb.social_network.switch_quality_cut
                state = _with_product_quality(state, product.id, cut)
    elif product.category == mb.consumer_apps:
        if action.ad_pricing and state.turn < month_to_turn(mb.ads.consumer_apps_from):
            raise MediaRuleError("consumer apps may move to ad pricing from 2026")
        new = replace(new, ad_pricing=action.ad_pricing)
    else:
        raise MediaRuleError("that line has no media settings")
    state = _energy(state, action.actor_id, "setting", balance)
    others = tuple(s for s in state.media.settings if s.product_id != product.id)
    settings = tuple(sorted((*others, new), key=lambda s: s.product_id))
    return Outcome(replace(state, media=replace(state.media, settings=settings)), (), ())


def _with_product_quality(state: GameState, product_id: int, mult: float) -> GameState:
    from tst.sim.state import with_product

    p = state.product(product_id)
    assert p is not None
    return with_product(state, replace(p, quality=p.quality * mult))
